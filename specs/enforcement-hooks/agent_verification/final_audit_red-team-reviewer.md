# Stage 5 Final Audit — Red-Team Reviewer

**Feature:** enforcement-hooks
**Reviewer:** red-team-reviewer (single-shot)
**Verdict SHA (HEAD at audit time):** `4620576376dc3ff5c7a32160519acff2e3f8f39f`
**Verdict:** `do_not_ship`

The trio approved the diff for correctness against benign use. As a malicious user
with full code knowledge whose goal is to ship without a real Stage 5 re-review,
I found **three CRITICAL** trivial bypasses of Hook 3 plus **two HIGH** bypasses
of Hook 2. None require any cleverness; each is a one-line attack.

The whole point of these hooks is "make it so a developer can't accidentally ship
without the discipline." For Hook 3 in particular, the bar should be: the only
unblock paths are (a) actually re-running Stage 5 to write a PSR, or (b) the
explicit `TLMFORGE_HOOKS=0` opt-out. Today the bar is much lower.

---

## CRITICAL findings

### C-1. `verdict_sha = "HEAD"` (or any git ref) makes Hook 3 unblock forever

**File:** `hooks/enforce_post_stage5_review.py` line 46–51 (`_normalize_sha`) +
line 127–130 (the verdict_sha match loop).

**Code:**

```python
def _normalize_sha(sha: str, cwd: str) -> str:
    r = _run(["git", "rev-parse", sha], cwd=cwd)
    if r.returncode != 0:
        return ""
    return r.stdout.strip()
...
for vsha in verdict_shas:
    normalized = _normalize_sha(vsha, repo_root)
    if normalized and normalized == head_sha:
        sys.exit(0)
```

`git rev-parse` resolves not only abbreviated SHAs but also any ref (`HEAD`,
branch names, tag names, `HEAD~1`, etc.). The audit JSON's `verdict_sha` is
treated as a string fed to `git rev-parse` — there is no validation that it
is a 40-char hex string.

**Attack chain:**

1. Developer wants to ship without re-running Stage 5.
2. Edits `specs/<feature>/agent_verification/final_audit_red-team-reviewer.json`
   and sets `"verdict_sha": "HEAD"` (one keystroke change).
3. Makes any number of post-audit commits.
4. `git commit` / `git push` always passes Hook 3, because `_normalize_sha("HEAD")`
   resolves to whatever the current HEAD is, and the equality check trivially
   succeeds.

**Reproduced (verbatim):**

```
$ cd /tmp/hook3_attack && cat specs/myfeature/agent_verification/final_audit_red-team-reviewer.json
{"reviewer":"red-team-reviewer","schema_version":"1.0","iteration":1,
 "verdict":"approve","verdict_sha":"HEAD","findings":[]}
$ git rev-parse HEAD
9e5963c4cfbf3ef876ddcd03210ceca3bf1ad5be   # <-- post-drift, NOT the audited SHA
$ echo '...' | python3 enforce_post_stage5_review.py
exit=0   # PASSES
```

`verdict_sha = "main"` / `"master"` / any branch name behaves identically.

**Impact:** the entire purpose of Hook 3 (block commits after audit drift) is
defeated by a single-character edit to the audit file. The PSR workflow becomes
optional. Severity: **critical** — this is the gate the feature is supposed to
enforce.

**Suggested fix:** validate `verdict_sha` is a 40-char hex string BEFORE feeding
it to `git rev-parse`. Reject anything that doesn't match
`re.fullmatch(r"[0-9a-f]{40}", vsha)`. Also validate the PSR `verdict_sha`
identically (same `_normalize_sha` call site at line 161).

---

### C-2. Hook 3 regex bypassed by trivial command shape variation

**File:** `hooks/enforce_post_stage5_review.py` line 16–19.

**Code:**

```python
GIT_MUTATION_RE = re.compile(
    r'^\s*(git\s+commit|git\s+push|gh\s+pr\s+(merge|create))',
    re.IGNORECASE,
)
```

The regex anchors at start-of-string and only matches `git` as the first token.
Any compound or wrapped form bypasses:

| Command (typed by user/Claude)        | Hook 3 sees |
| ------------------------------------- | ----------- |
| `git commit -m foo`                   | BLOCKS      |
| `cd . && git commit -m foo`           | **passes**  |
| `true; git commit -m foo`             | **passes**  |
| `eval "git commit -m foo"`            | **passes**  |
| `/usr/bin/git commit -m foo`          | **passes**  |
| `env GIT_DIR=.git git commit -m foo`  | **passes**  |
| `sh -c "git commit -m foo"`           | **passes**  |

**Reproduced (verbatim):**

```
$ echo '{"...","tool_input":{"command":"cd . && git commit -m foo"}}' \
  | python3 enforce_post_stage5_review.py
exit=0   # bypasses, even with HEAD drifted past audit
```

**Attack chain:** the malicious developer simply types `cd . && git commit ...`
or invokes `/usr/bin/git`. Hook 3 never even examines the audit state. No edits
to any file required.

**Impact:** Hook 3's whole gating purpose collapses for anyone who knows shell
syntax. Severity: **critical**.

**Suggested fix:** parse the command with `shlex.split`, then walk the resulting
argv tree across shell operators (`&&`, `;`, `|`, command substitution, `eval`,
`sh -c`). For each effective argv, check if `os.path.basename(argv[0]) == "git"`
and `argv[1] in {"commit", "push"}`, OR `argv[0] == "gh"` and the next two
tokens match `pr (merge|create)`. Defense-in-depth: also reject any command
that contains the substring ` git commit` / ` git push` / ` gh pr merge` /
` gh pr create` after stripping path prefixes — even if the parser misses
something exotic, the substring sweep catches it.

---

### C-3. Active-feature marker accepts path traversal — audit file may live anywhere

**File:** `hooks/enforce_post_stage5_review.py` line 82–98.

**Code:**

```python
marker_path = os.path.join(repo_root, "specs", ".tlmforge_active_feature")
...
active_feature = f.read().strip()
...
av_dir = os.path.join(repo_root, "specs", active_feature, "agent_verification")
audit_pattern = os.path.join(av_dir, "final_audit_*.json")
audit_files = [p for p in glob.glob(audit_pattern) if "_psr_" not in os.path.basename(p)]
```

`active_feature` is concatenated unsanitized into the search path. There is no
check that the resulting path stays within `specs/`. Two exploitable shapes:

1. **Traversal:** `active_feature = "../evil"` → audit dir becomes
   `<repo>/specs/../evil/agent_verification` which resolves to `<repo>/evil/...`,
   any directory the attacker controls.
2. **Glob expansion:** `active_feature = "*"` → audit dir contains a literal `*`
   that `glob.glob` expands. Any audit file under any feature dir can satisfy
   the check, including stale audits from unrelated features.

**Reproduced (verbatim):**

```
$ echo "../evil" > specs/.tlmforge_active_feature
$ cat evil/agent_verification/final_audit_red-team-reviewer.json
{"...", "verdict_sha": "<current HEAD>"}    # placed by attacker
$ echo '...' | python3 enforce_post_stage5_review.py
exit=0   # passes
```

**Attack chain:** an attacker writes `../<dir>` (or `*`) into the marker,
places a forged audit JSON in that dir (which is NOT under `specs/`, so
git doesn't notice it as a feature artifact), and Hook 3 happily reads it.
Combined with C-1, the audit file's `verdict_sha` doesn't even need to be
real — `"HEAD"` is fine.

**Impact:** moves the audit file outside the feature's tracked directory,
making it harder for reviewers to see that an audit was forged at all.
Severity: **critical** (combined with C-1, the bypass is undetectable in
the normal `specs/` audit trail).

**Suggested fix:** after reading the marker, validate
`re.fullmatch(r"[A-Za-z0-9_\-]+", active_feature)` (no slashes, no dots, no
glob chars). Optionally also assert that
`os.path.commonpath([repo_root + "/specs", os.path.realpath(av_dir)])`
equals `repo_root + "/specs"` after resolution.

---

## HIGH findings

### H-1. Hook 2 bypassed by override phrase appearing in tool-result content

**File:** `hooks/enforce_skill_invoked.py` line 54–73 +
`hooks/_lib/transcript.py` line 25–30.

**Code:**

```python
last_user_idx = find_last_user_index(entries)
...
last_user = entries[last_user_idx]
user_content = last_user.get("message", {}).get("content", "")
...
else:
    text = str(user_content)

if has_override(text):
    sys.exit(0)
```

In Claude Code's transcript format, **tool results are wrapped in
`type: "user"` JSONL entries** (the model SDK convention — the assistant emits
a `tool_use`, the runtime appends a `user`-typed message containing the
`tool_result`). `find_last_user_index` returns the index of the last
`type=="user"` entry without distinguishing human turns from tool-result
wrappers. So if any tool's output text reaches the transcript and contains
"be quick" / "just do it" / "trivial fix", Hook 2 unblocks.

**Reproduced (verbatim):**

```
$ cat /tmp/transcript_attack3.jsonl
{"type":"user","message":{"role":"user","content":"add encryption please"}}
{"type":"assistant","message":{"role":"assistant","content":[
  {"type":"tool_use","name":"Bash","input":{"command":"echo be quick"}}]}}
{"type":"user","message":{"role":"user","content":"be quick"}}   # <-- tool_result wrapper

$ echo '{"...","tool_name":"Edit","transcript_path":"/tmp/transcript_attack3.jsonl"}' \
  | python3 enforce_skill_invoked.py
exit=0   # PASSES — the human never typed "be quick"
```

**Attack chain:**

1. Developer prompts "add encryption" (no override). Hook 2 should now block
   any Edit/Write/Bash unless the skill is invoked.
2. Developer asks Claude to run a Bash command that prints "be quick" (e.g.
   `cat /tmp/notes.txt` where notes.txt happens to contain that phrase, or
   `git log --grep=quick` which surfaces a commit message).
3. After that Bash returns, the next Edit is unblocked because Hook 2 looked
   at the tool_result content and saw "be quick".

**Why HIGH not CRITICAL:** the user/Claude has to deliberately produce a tool
output containing the phrase, OR a benign tool output happens to contain
"be quick" (which is a common phrase). It's exploitable but requires a small
contrivance. With C-1/C-2/C-3 as critical, this one rounds down.

**Suggested fix:** in `find_last_user_index`, walk content blocks and exclude
entries whose only non-empty content is `tool_result`-typed blocks. A "human
turn" is a user entry whose content is a plain string OR a list containing at
least one block whose `type` is in `{"text"}` (not `tool_result`). Fall back
to the prior human turn if the most-recent user entry is purely tool-result.

---

### H-2. Hook 2 trusts transcript file the developer fully controls

**File:** `hooks/enforce_skill_invoked.py` line 39–52.

**Code:**

```python
transcript_path = payload.get("transcript_path")
...
if not os.path.isfile(transcript_path):
    ...
    sys.exit(0)

entries = load_transcript_entries(transcript_path)
```

The transcript file lives on the developer's local disk and is appended to by
Claude Code, but nothing prevents a developer from editing it between hook
invocations. A developer can simply append a forged
`{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill",
"input":{"skill":"tlmforge:feature-development"}}]}}` line to satisfy
`skill_invoked_since`. This will be invisible to anyone reviewing the git log,
because the transcript is not committed.

**Why HIGH not CRITICAL:** the threat model is "single-user developer who
wants to bypass" — and that developer can just set `TLMFORGE_HOOKS=0`. The
transcript-edit attack is no easier than the documented opt-out. Calling it
out anyway because it means **the audit trail is fully malleable** and a
later forensic review of the transcript cannot establish that the skill was
genuinely invoked.

**Suggested fix:** there is no clean fix — the transcript is local-only. Accept
the reality and document in `SKILL.md` that "Hook 2 enforces the discipline of
running the skill, not its actual invocation; the gate is honor-based and the
opt-out is `TLMFORGE_HOOKS=0`." If you want stronger evidence, add a
side-channel: have the skill's first action be writing a marker file in
`specs/<feature>/.skill_invoked` and have Hook 2 check for it instead of
parsing the transcript.

---

## MEDIUM findings

### M-1. `_DISABLED_VALUES` includes empty string — silent foot-gun

**File:** `hooks/_lib/env.py` line 3–10.

```python
_DISABLED_VALUES = {"0", "false", "no", "off", ""}
```

`TLMFORGE_HOOKS=""` (set but empty) disables all hooks. Some shells, CI envs,
and `env -u`-style invocations can leave a variable set-but-empty. A user
running `unset TLMFORGE_HOOKS` is fine, but `TLMFORGE_HOOKS= ` (note
trailing space) followed by `.lower().strip()` → `""` → disabled. This is
not exploitable per se but is a usability surprise that could lead to silent
disablement.

**Why MEDIUM:** this is the documented behavior (the reviewers approved
explicitly setting "" as disabled). I'm flagging it because the SKILL.md user-
facing docs say "set `TLMFORGE_HOOKS=0` to bypass" and don't mention that
empty-string also bypasses — a future user setting `TLMFORGE_HOOKS=1` thinking
they're enabling won't notice that an upstream `unset && export` left it as "".

**Suggested fix:** either remove `""` from `_DISABLED_VALUES` (the strict
"unset" semantics is more predictable) OR document explicitly that an
empty-string value disables the hooks.

---

### M-2. Hook 3 `cwd` is the developer's PWD, not necessarily the repo

**File:** `hooks/enforce_post_stage5_review.py` line 75–79.

```python
run_cwd = os.getcwd()
r = _run(["git", "rev-parse", "--show-toplevel"], cwd=run_cwd)
if r.returncode != 0:
    sys.exit(0)
```

If the user invokes Claude Code from outside any git repo (e.g. `cd /tmp &&
claude`), `git rev-parse --show-toplevel` fails and Hook 3 exits 0 — even if
the actual `git commit` they're about to run targets a different repo via
`-C` or environment vars. Niche, but a documented escape hatch.

**Why MEDIUM:** requires the user to invoke Claude from outside a repo, which
is unusual. Not a primary attack vector.

**Suggested fix:** if `run_cwd` is not in a git repo, also extract a `-C` path
from the candidate command and check that. If both fail, fail closed (block)
rather than open.

---

## LOW / nit findings

### L-1. `safe.fail_open` swallows `KeyboardInterrupt` indirectly

**File:** `hooks/_lib/safe.py` line 5–18.

```python
except SystemExit:
    raise
except Exception as exc:
    ...
```

`KeyboardInterrupt` derives from `BaseException`, not `Exception`, so it is
NOT caught — that's fine. But if a hook is killed with SIGTERM mid-run, the
gate is silently bypassed because the wrapper's `sys.exit(0)` at the end
runs after the cleanup of any non-SystemExit exception. The current code
behaves correctly under SIGINT (KeyboardInterrupt propagates and the process
dies with non-zero exit, which Claude Code interprets as a hook failure).
This is fine — flagged for completeness only.

---

## Verdict

**`do_not_ship`** until C-1, C-2, C-3 are fixed. Each is a single-character or
single-line bypass of the very gate this feature is supposed to enforce. The
trio (architect, code-reviewer, tester) all approved because they tested
against the **correct** input shape — none of them probed whether a
malicious-but-knowledgeable user could trivially evade the gate.

The H-* findings are advisory; the C-* findings are blockers. The remediation
for all three CRITICALs is straightforward (40-char hex regex + shlex-based
git command parsing + active-feature marker validation) and should take well
under an hour each.
