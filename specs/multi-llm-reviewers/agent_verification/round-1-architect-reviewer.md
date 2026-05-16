# multi-llm-reviewers — Architect Review Round 1

## VERDICT: NEEDS REVISION

## Summary

The plan adds OpenAI (`gpt-5.5`) and Gemini as optional auxiliary reviewers to
the tlmforge feature-development skill at Stages 3, 4, and 5. The overall
approach is architecturally sound — the skipped-JSON contract, the env-var
opt-in, and the Phase-gated structure are all correct. However there are three
issues that must be resolved before code is written: a hidden coupling between
the new reviewer names and `check_convergence.py`'s caller that the plan
does not instruct the implementer to handle, an API design mismatch that will
produce wrong behavior under the Responses-API deprecation path for Chat
Completions, and a concrete data-corruption risk from concurrent writes to
the same output file.

---

## Instruction Compliance

The plan covers everything the spec asked for: OpenAI integration, Gemini
extension, exit-code contract, config surface, SKILL.md docs, and tests.
No requirements are missed or misinterpreted. Phase sequencing is logical.

---

## Critical Issues (must fix before proceeding)

### C1. `expected_roles` coupling is unresolved — plan silently breaks convergence (architecture)

The plan states "No changes to `check_convergence.py`" and that "existing
`status=skipped` handling already covers absent optional reviewers." This is
only half-true and the half that is missing is the dangerous one.

`check_convergence.py::evaluate_convergence` takes an explicit `expected_roles`
list from its caller. If `openai` is in that list and the script exits 2 (key
absent), the convergence engine fires a `reviewer_json_missing` meta CRITICAL
because the skipped JSON sidecar IS written but the caller decides the roster,
not the script. If `openai` is NOT in that list, its JSON output is silently
ignored even when it produces real CRITICALs.

The plan acknowledges this in spec_audit.md (F3) and says "SKILL.md
orchestration should add them to `expected_roles` only when the feature flag is
explicitly set" — but the master plan (README.md) never translates that into a
concrete Phase 3 SKILL.md deliverable. Phase 3 says only "document the
auxiliary LLM reviewer integration." It lists no specific template or logic for
how the Claude orchestrating agent should build the `expected_roles` list
conditionally.

This means the implementer of Phase 3 has no mechanical spec to follow.
Without explicit guidance, the most natural thing to write is a static
`expected_roles` list that either always includes or never includes the
auxiliary reviewers — both of which are wrong.

**Suggested fix:** Phase 3 must include a concrete SKILL.md template that
shows the conditional roster construction:

```
expected_roles = ["architect-reviewer", "tester", "threat-modeler"]
if TLMFORGE_ENABLE_OPENAI=1 and OPENAI_API_KEY set:
    expected_roles += ["openai"]
    run ai_review_openai.sh → round-N-openai.json
if TLMFORGE_ENABLE_GEMINI=1 and GEMINI_API_KEY set:
    expected_roles += ["gemini"]
    run ai_review_json.sh → round-N-gemini.json
```

The JSON `reviewer` field in the OpenAI script must be the string `"openai"`
(not `"gpt-5.5"` or `"openai-gpt5.5"`) since convergence uses the `reviewer`
field from the JSON, not from `expected_roles`, when surfacing findings.
The plan does not specify this string anywhere.

### C2. Chat Completions API is deprecated for reasoning models — gpt-5.5 behavior is wrong (architecture)

The plan specifies `client.chat.completions.create(model=model, messages=[...])`
as the implementation pattern. Based on current OpenAI documentation, Chat
Completions remains supported for `gpt-5.5`, but starting with GPT-5.4, tool
calling is not supported in Chat Completions with `reasoning: none`. More
critically, the Responses API is the recommended path for all new integrations
and is where new features (caching improvements, tool support) are being added;
Chat Completions is in maintenance mode.

For a code review use-case, where we want structured JSON output and optionally
could use `reasoning_effort=high`, using Chat Completions means:
(a) we cannot use `output_text` helper for cleaner JSON extraction,
(b) we get worse cache utilization (40-80% worse per OpenAI docs), and
(c) the plan will need to be revised again soon as Chat Completions loses
feature parity.

This is not "it'll crash today" — it is "this is the wrong API surface to
build on and creates migration debt immediately." Given that the plan explicitly
calls out the Responses API in spec_audit.md (F8) as the recommended path (and
notes the TLM server already uses it), choosing Chat Completions in the master
plan without justification is an unforced error.

**Suggested fix:** Phase 1 implementation must use `client.responses.create()`
with `model=model, input=[{"role": "user", "content": diff_content}]` and
access the result via `response.output_text`. This is a one-call-site change
with no architectural impact, but it needs to be specified before tests are
written, because the mocked call surface differs between the two APIs.

### C3. Concurrent parallel invocations write to the same output file without coordination (architecture)

The plan's architecture diagram shows all Stage 3 reviewers running "parallel
in SKILL.md orchestration." Each new script accepts `--output PATH`. If the
orchestrating agent launches multiple review agents in the same `agent_verification/`
directory in the same round (the standard Deep path does exactly this), two
things can go wrong:

1. If the caller passes the same `--output` path to two different scripts by
   mistake (easy to do when wiring up orchestration), the atomic write in
   `ai_review_json.sh` (tmp + mv) provides no protection because both scripts
   write to their own `.tmp` and then race to `mv` the final file.
2. The skipped-JSON sidecar is written to the same `$OUTPUT` path as the
   real-result JSON. If the script exits 2 mid-run after a partial write to
   `$OUTPUT.tmp` and a signal is received before the `mv`, the final path
   contains a truncated partial write (the `set -euo pipefail` exits on the
   signal but the `mv` never ran). This leaves `OUTPUT` either stale (previous
   round's content) or nonexistent, causing convergence to inject a
   `reviewer_json_missing` meta CRITICAL — a false positive.

The second scenario is a real failure mode under signal pressure (e.g., Claude
kills a timed-out subprocess). The existing `ai_review_json.sh` has the same
issue but it only runs one-at-a-time today; with parallel orchestration of
multiple new scripts this becomes more likely to surface.

**Suggested fix:** The Python script should write output atomically using
`tempfile.NamedTemporaryFile(dir=output_dir, delete=False)` + `os.replace()`.
`os.replace()` is atomic on POSIX. The shell wrapper's atomic_write pattern is
correct; the Python script must replicate it with `os.replace`, NOT
`shutil.move` (which has TOCTOU on cross-filesystem moves). Document this as
a requirement in Phase 1's implementation steps.

---

## Warnings (should fix)

### W1. `gpt-5.5` vs `gpt-5.5-2026-04-23` — version pinning absent (architecture)

The alias `gpt-5.5` resolves to the latest patch of that series, currently
`gpt-5.5-2026-04-23`. This means the model under test will silently change when
OpenAI releases `gpt-5.5-2026-07-xx`. For a review tool where reproducibility
matters (the same diff should produce similar findings across runs), using an
unversioned alias is a problem: a finding that passes Round 1 may resurface on
Round 2 if the model updated between calls.

This is mitigated by the `max_iterations=3` cap and the `TLMFORGE_OPENAI_MODEL`
override, but neither mitigation is documented for operators. The SKILL.md
section (Phase 3) should note: "For reproducible reviews, pin to a dated alias
e.g. `gpt-5.5-2026-04-23`."

### W2. `mode=plan` sends the full README.md without a token budget guard (architecture)

The plan says `mode=plan` reads
`specs/$(cat specs/.tlmforge_active_feature)/README.md` and sends it as the
user message. A Deep-path README.md can legitimately be 8K-20K tokens (the
plan itself is already ~300 lines). `gpt-5.5` has a 1M context window so
overflow is not the concern — cost is. At $5/1M input tokens, a 20K-token plan
plus system prompt sent 3 times per round across 3 rounds is ~$0.90 just for
plan review. The plan's cost analysis does not account for `mode=plan` input
volume at all (it estimates 5K-20K tokens for code review, not plan review
where the plan text IS the input).

More importantly: there is no truncation logic. If a README.md grows to
100K tokens (unlikely today but plausible for a large feature), the script
will happily send it all without warning. Add a token-count pre-check (rough
`len(text) / 4`) with a configurable `TLMFORGE_MAX_PLAN_TOKENS` guard that
writes a `status=error` finding if exceeded rather than silently over-spending.

### W3. `is_valid_review()` in `ai_review_json.sh` does not check `"status"` field — new scripts must not copy this gap (architecture)

Looking at `ai_review_json.sh` lines 87-101: `is_valid_review()` checks for
`reviewer`, `schema_version`, `verdict`, `findings` but does NOT check that
`status` is present or is one of `["ok", "skipped", "error"]`. The review
schema marks `status` as optional with a default of `"ok"`, so missing status
is technically valid per schema. However, `check_convergence.py` uses
`review.get("status", OK)` which silently defaults missing status to `"ok"`,
meaning a malformed LLM response that omits `status` will be treated as a
real review. The new Python script's validation logic should explicitly
set `status="ok"` before writing (the plan already says this via `d.setdefault("status", "ok")`
pattern from the Gemini script — just call it out explicitly as a requirement
in Phase 1 so the implementer doesn't skip it).

### W4. Phase 0 stub produces `status=skipped` JSON — this will cause a false positive if Phase 0 tests pass before Phase 1 is complete (architecture)

Phase 0's stub always writes `status=skipped` and exits 2. The TDD plan says
Phase 0 has a RED state where "mode=code real-call test fails RED." But if
Phase 0 tests pass and someone runs the full convergence suite (e.g., CI), the
stub being registered in `expected_roles` would surface as a
`reviewer_json_missing` (file not written at all) or silently skipped (if file
is written with skipped status). This is fine IF Phase 0 tests never run the
full convergence pipeline — but the plan doesn't say that explicitly.

Make it explicit in the Phase 0 test specification: "Phase 0 tests MUST NOT
add `openai` to any `expected_roles` list passed to `check_convergence.py`.
Phase 0 tests are exit-code contract tests only."

### W5. No test for the `specs/.tlmforge_active_feature` containing unexpected whitespace or a trailing newline (architecture)

`specs/.tlmforge_active_feature` currently contains `multi-llm-reviewers`
(confirmed). Shell command substitution `$(cat specs/.tlmforge_active_feature)`
strips trailing newlines correctly. But the Python script in Phase 1 uses
`open(...).read()` which does NOT strip newlines — `"multi-llm-reviewers\n"`
would produce a path like
`specs/multi-llm-reviewers\n/README.md` that will not resolve. The plan says
Phase 1 reads via Python. Add `.strip()` to the file read and add a test for
the trailing-newline case.

---

## Suggestions (nice to have)

### S1. Cost exposure at $5/1M is higher than the plan estimates

The plan's cost analysis uses "$2.50-$10/1M tokens" marked as GUESS. Now that
`gpt-5.5` pricing is confirmed at $5/1M input + $30/1M output, the
"typical review" estimate should be updated. At 20K input + 2K output,
one call costs $0.10 + $0.06 = $0.16. Twelve calls across a full Deep
feature = ~$1.92. Not prohibitive, but the plan's guess range of $0.12-$2.40
should be anchored to the confirmed pricing.

### S2. System prompt injection via diff content

The plan sends the raw `git diff HEAD` output as the user message. A diff that
contains lines like `+# Output ONLY a JSON object...` could confuse the model.
This is low severity since we're sending to a sufficiently large model, but
the prompt should inject the diff content inside a clearly delimited block
(e.g., triple-backtick fenced code block) to reduce prompt injection surface.
The Gemini script pipes directly to the CLI without this protection — the new
Python script should do better.

### S3. Phase 3 (SKILL.md docs) has no tests and "phase-auditor verifies at phase end"

Documentation-only phases with no mechanical verification are where plans rot.
The phase-auditor at Deep-path phase-end runs against the actual code, not the
docs. Consider adding one integration test: given a SKILL.md with the new
section, assert that the env-var table contains `TLMFORGE_ENABLE_OPENAI`,
`TLMFORGE_ENABLE_GEMINI`, and `TLMFORGE_OPENAI_MODEL`. This is a grep-level
test, not complex, but it creates a regression barrier.

---

## What's Good

- The exit-code contract (0/2/64) is cleanly specified and mirrors the existing
  Gemini script exactly. No new exit-code semantics invented.
- The skipped-JSON sidecar on exit 2 is the right pattern. The convergence
  engine's `status=skipped` path was designed for exactly this.
- The `set -euo pipefail` without `set -x` constraint is called out
  explicitly in both the architecture and the threat model — this is the
  correct security posture for secret-adjacent shell scripts.
- The retry-once-on-invalid-JSON pattern mirrors `ai_review_json.sh` exactly.
  Consistent failure modes across LLM scripts reduce operational surprise.
- Phase sequencing is well-considered: scaffold → integrate → extend Gemini →
  document. Each phase has a clear rollback. Phase 0 being testable without a
  live key is the right design.
- The `TLMFORGE_OPENAI_MODEL` override env var correctly separates the default
  from the override, and the "model-not-found → status=error with synthetic
  CRITICAL, exit 0" behavior is the right fail-safe (does not block CI, does
  surface the problem).
- `gpt-5.5` is confirmed as a real, currently-available API model identifier
  (resolved to `gpt-5.5-2026-04-23`). The risk note in the plan about the
  model name being a display name was valid caution; it turns out `gpt-5.5`
  IS the correct Chat Completions model id.
