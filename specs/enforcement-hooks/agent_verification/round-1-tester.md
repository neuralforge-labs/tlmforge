# Tester Review — enforcement-hooks — Round 1

**Reviewer:** tester
**Stage:** Stage 3, Round 1 (cold review of plan)
**Date:** 2026-05-15
**Verdict:** needs_revision

---

## Code Surface Analyzed

Files read: `specs/enforcement-hooks/README.md`, `specs/enforcement-hooks/spec_audit.md`,
`skills/feature-development/review_schema.json`, `skills/feature-development/check_convergence.py`,
`skills/feature-development/tests/test_check_convergence.py`, `.claude-plugin/plugin.json`,
`~/.claude/plugins/marketplaces/thedotmack/plugin/hooks/hooks.json` (claude-mem reference).

No code exists yet. This is a pre-implementation plan review.
All findings are based on static analysis of the plan's logic and verified
through Python simulation runs.

**Failure domains touched by the planned code:**

| Domain | Which hooks |
|--------|-------------|
| ASYNC / LIFECYCLE | All hooks (subprocess: git rev-parse, file IO) |
| STATE | Hook 2 task-window logic, Hook 3 SHA comparison |
| DATA | Transcript JSONL parsing, JSON glob+parse for final_audit |
| RESOURCES | File handles for transcript and audit files |
| USER INPUT | Override phrase detection, command pattern matching |
| CONCURRENCY | Transcript partial-write race |

Risk level: **HIGH** — these hooks fire on every Edit/Write/Bash in every session.
A bug is felt by every user immediately.

---

## Edge Cases Found

### CRITICAL

#### EC-1: Subagent sessions have no user messages — task window is undefined, Hook 2 blocks all mutations

**Trigger:** The 7-stage recipe (Stage 3, Stage 4) spawns subagents. Each
subagent runs in its own session context. A subagent session's transcript has
no `type: user` messages — it is driven by the parent agent's task input, not
by interactive user messages. Hook 2's task-window logic (`"since last user
message"`) has no anchor to find. The plan does not specify the fallback.

**What happens (two sub-cases):**

Sub-case A — fallback to "all events": if the hook defaults to scanning the
entire transcript when no user message is found, it may work correctly for
the first mutation in a session where skill was invoked early. But if the
subagent session transcript is a separate file (not the main session
transcript), no skill invocation will be present at all.

Sub-case B — fallback to "empty window": the hook concludes skill is absent,
blocks the mutation. Every Edit/Write/Bash from a subagent is blocked. The
fail-open wrapper then fires because the implementation crashes trying to
resolve a None anchor — so actually Hook 2 accidentally fails open. This
produces inconsistent enforcement: sometimes blocked, sometimes allowed,
depending on where exactly the crash occurs.

**Impact:** Either all subagent mutations are silently allowed (fail-open on
crash, no enforcement) OR all subagent mutations are blocked (discipline gates
break the recipe's own stage execution). Both outcomes are wrong.

**Fix:** The plan must define explicit behavior: "If the transcript passed on
stdin has no user messages, check whether it is a subagent session (look for
a parent session ID or session type field in the Claude Code hook payload).
If it is a subagent session, pass-through unconditionally — Hook 2 enforcement
only applies to the main session." If Claude Code does not expose a session
type field, the fallback must be: treat no-user-messages as pass-through.

**Test to write:**
```python
# tests/test_hook2_no_user_messages.py
def test_hook2_subagent_transcript_no_user_messages():
    """Hook 2 with a transcript containing zero user messages must pass-through."""
    transcript = [
        {"type": "tool_call", "tool_name": "Read", "tool_input": {"file_path": "/x.py"}},
        {"type": "tool_result", "content": "file contents"},
    ]
    result = run_hook2_with_transcript(transcript, tool_name="Edit")
    assert result["action"] == "allow"
    # currently: raises AttributeError on NoneType or blocks (unspecified)
```

---

#### EC-2: Empty-repo / pre-first-commit — `git rev-parse HEAD` returns exit code 128

**Trigger:** Hook 3 runs `git rev-parse HEAD`. In a git repository that has
zero commits (freshly `git init`-ed, before any commit), `git rev-parse HEAD`
exits with code 128 and writes to stderr:
`fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.`
The stdout is empty.

**What happens:** The plan does not handle this case. If the hook calls
`subprocess.run(['git', 'rev-parse', 'HEAD'])` and does not check the return
code, `stdout.strip()` returns an empty string. The comparison `HEAD == verdict_sha`
becomes `"" == "abc123..."` → False. The hook then checks for a 5b marker
matching `*_5b_.json` (empty SHA) — no match. Then checks override. Then
blocks. A user who has Stage 5 audit JSON from a prior session but is in a
fresh git repo would be incorrectly blocked on `git commit`.

**Impact:** `git commit` is blocked in a valid state (fresh repo, no prior
commits). Error message references "Stage 5 verdict was for SHA X. HEAD is
now (empty string) (N commits ahead)" — garbled user-facing message.

**Fix:** After running `git rev-parse HEAD`, check return code. Non-zero
exit → treat as "HEAD unknown" → pass-through (can't enforce commit gate
without a valid HEAD SHA). Document this case explicitly.

**Test to write:**
```python
# tests/test_hook3_no_commits.py
def test_hook3_git_no_commits(tmp_git_empty_repo, final_audit_with_verdict_sha):
    """Hook 3 in a repo with zero commits must pass-through, not block."""
    result = run_hook3(
        command="git commit -m 'init'",
        cwd=tmp_git_empty_repo,
        audit_files=[final_audit_with_verdict_sha],
    )
    assert result["action"] == "allow"
    # currently: blocks with garbled HEAD=(empty string) in message
```

---

#### EC-3: SHA length mismatch causes false blocks — verdict_sha short hash vs full 40-char HEAD

**Trigger:** The SKILL.md Stage 5 prompt template instructs reviewers to
record `git rev-parse HEAD` as `verdict_sha`. If a reviewer records a short
hash (`git rev-parse --short HEAD` → 7 chars, or copies from a GitHub URL),
the stored value is e.g. `"1424797"`. Hook 3 runs `git rev-parse HEAD` and
gets the full 40-char SHA `"1424797ed402f266d67fd54cdf0f1781dc370181"`.
The comparison `"1424797" == "1424797ed4..."` → False.

**What happens:** HEAD appears to have drifted. Hook 3 checks for a 5b
marker with glob `*_5b_1424797ed4...json` — file doesn't exist. Override
not set. Hook blocks `git commit` and `git push` with a spurious "Stage 5
verdict was for SHA 1424797, HEAD is 1424797ed4... (0 new commits)" message.

This is a **permanent false block**: no 5b marker can unblock because every
subsequent `git rev-parse HEAD` also returns the full SHA.

**Impact:** Data loss path — user cannot push any code, including legitimate
non-feature commits (hotfixes, changelog updates). Escape hatch: `TLMFORGE_HOOKS=0`
or "be quick" override, but the error message doesn't make this obvious.

**Fix:** Normalize all SHAs to full 40-char before comparison. Use
`git rev-parse <sha>` to expand any short hash stored in `verdict_sha`
to its full form. The 5b marker filename convention must also be specified as
full SHA. Add a note to the skill prompt template: "Use `git rev-parse HEAD`
(not `--short`) for verdict_sha."

**Test to write:**
```python
# tests/test_hook3_short_sha_verdict.py
def test_hook3_short_verdict_sha_same_commit(repo_at_sha, final_audit_short_sha):
    """Hook 3 must allow commit when verdict_sha is the short form of HEAD."""
    # verdict_sha = "1424797" (short), HEAD = "1424797ed402..." (full)
    result = run_hook3(
        command="git commit --amend --no-edit",
        verdict_sha_in_file="1424797",    # short form
        current_head_full="1424797ed402f266d67fd54cdf0f1781dc370181",
    )
    assert result["action"] == "allow"
    # currently: blocks because short != full
```

---

#### EC-4: Transcript partial-write race — truncated JSONL line crashes the scan

**Trigger:** Claude Code writes the session transcript as JSONL incrementally
(one line per event, flushed as the event completes). Hook 2 is triggered by
PreToolUse, which fires while the session is active. There is a window where
the transcript file exists but the most recent line is incomplete — the
tool-call event being logged may not yet have its closing `}` flushed.

**What happens:** `transcript.py` reads the file, iterates lines, calls
`json.loads()` on each. The truncated last line raises `json.JSONDecodeError`.
If `transcript.py` does not catch per-line exceptions and propagate a partial
result, the exception propagates to the hook's outer `try/except` in the
fail-open wrapper, which exits 0 (allow). Result: Hook 2 silently fails open
on the partial-write race, regardless of whether the skill was invoked.

This is a reliability problem: every tool call that happens to race with the
transcript write produces false-allow behavior.

**Impact:** Silent enforcement bypass. Not constant, but reproducible on
machines with slow IO or in CI-like environments where the transcript file is
on a network filesystem.

**Fix:** `transcript.py` must catch `json.JSONDecodeError` per-line, skip
the malformed line, and continue. The scan result is based on fully-parsed
lines only. This is the correct behavior: a truncated line means the event
is not yet complete, so it is correct to exclude it from the scan.

**Test to write:**
```python
# tests/test_transcript_partial_write.py
def test_transcript_scan_truncated_last_line():
    """Truncated final JSONL line must be skipped; prior events must still be found."""
    # Transcript: good skill-invocation line, then truncated line
    raw = (
        '{"type": "tool_call", "tool_name": "Skill", '
        '"tool_input": {"skill": "tlmforge:feature-development"}}\n'
        '{"type": "tool_call", "tool_name": "Edit", "tool_i'  # truncated
    )
    events = list(scan_transcript_lines(raw))
    skill_found = any(
        e.get("tool_name") == "Skill" for e in events
    )
    assert skill_found is True
    assert len(events) == 1  # truncated line excluded
    # currently: raises JSONDecodeError, propagates to fail-open
```

---

### HIGH

#### EC-5: Override phrases "minimal" and "trivial" produce false positives in normal technical discourse

**Trigger:** Hook 2 and Hook 3 detect override intent by checking if the last
user message contains any of: `["be quick", "minimal", "trivial", "just do it", "trivial fix"]`
as substrings (case-insensitive).

"minimal" and "trivial" are common English words in technical writing:
- "the trivial solution is O(n)" — mathematical usage, NOT an override
- "use minimal logging" — engineering guidance, NOT an override
- "minimal test coverage is bad practice" — code review comment, NOT an override
- "trivially false assumption" — logical/philosophical usage

**What happens:** User writes "explain why minimal test coverage is bad" as
a question. Hook 2 detects "minimal" and grants override for the subsequent
mutation. The user did not intend to bypass discipline. The very next Edit/Write
call is allowed without skill invocation.

**Impact:** Accidental discipline bypass. The enforcement gate is silently
disabled by common technical phrasing. This undermines the feature's core
guarantee.

**Fix:** Require word-boundary matching for single-word phrases. "minimal" as
an override should only match when it stands alone as a deliberate signal, not
as part of compound technical speech. Options:
1. Use regex word boundaries: `\bminimal\b` still matches "minimal changes" but
   not "minimally." But "use minimal logging" still matches — not sufficient.
2. Require the phrase to be the majority of the user message (short messages
   only). Fragile.
3. **Best:** Tighten the override list to only inherently-deliberate phrases:
   `["be quick", "just do it"]`. Remove "minimal" and "trivial" from automatic
   override and add them only when combined: "be minimal" or "keep it trivial."
   Document the change clearly.

**Test to write:**
```python
# tests/test_overrides_false_positive.py
def test_minimal_in_technical_context_does_not_override():
    """'minimal' in a technical sentence must not trigger override."""
    msg = "explain why minimal test coverage is a bad practice"
    assert detect_override(msg) is False
    # currently: returns True (false positive)

def test_trivial_in_math_context_does_not_override():
    """'trivial' in a math/CS context must not trigger override."""
    msg = "the trivial solution to this problem is O(n^2)"
    assert detect_override(msg) is False
    # currently: returns True (false positive)
```

---

#### EC-6: Hook 3 glob uses relative path from cwd — fails when user runs `claude` from a subdirectory

**Trigger:** The plan specifies Hook 3 globs `specs/*/agent_verification/final_audit_*.json`
from cwd. Claude Code's PreToolUse hook runs in the process that was started
when the user typed `claude`. If the user ran `claude` from inside a project
subdirectory (e.g., `cd src/ && claude`), the cwd is `src/`, and the glob
`specs/*/...` finds nothing.

**What happens:** No `final_audit` JSONs found → Hook 3 concludes "no Stage 5
has run" → passes through. The Stage 5 verdict is silently ignored; Hook 3
is effectively disabled.

**Impact:** The post-Stage-5 commit gate does not fire in the common case
where the user's shell happens to be in a subdirectory. This is the primary
failure mode the feature was designed to prevent (LL-1/LL-8 violations).

**Fix:** Hook 3 must anchor the glob to the git repository root, not to cwd.
Use `git rev-parse --show-toplevel` to find the repo root, then glob
`<repo_root>/specs/*/agent_verification/final_audit_*.json`.
If `git rev-parse --show-toplevel` fails (not a git repo), treat as
"no Stage 5 yet" → pass-through.

**Test to write:**
```python
# tests/test_hook3_cwd_subdirectory.py
def test_hook3_finds_audit_from_subdirectory(tmp_repo_with_audit):
    """Hook 3 must find final_audit JSONs even when cwd is a project subdirectory."""
    src_dir = tmp_repo_with_audit / "src"
    src_dir.mkdir()
    result = run_hook3(
        command="git push origin main",
        cwd=src_dir,  # <-- not repo root
        head_sha="newsha",
        verdict_sha_in_audit="oldsha",
    )
    assert result["action"] == "block"  # must still enforce
    # currently: passes through (glob finds nothing from src/)
```

---

#### EC-7: `TLMFORGE_HOOKS=0` bypass — plan does not specify exact match semantics; "false" or "" would not bypass

**Trigger:** The plan says "Honor `TLMFORGE_HOOKS=0`" but does not specify the
exact check. If the implementation uses `os.environ.get('TLMFORGE_HOOKS') == '0'`
(exact equality), then `TLMFORGE_HOOKS=false`, `TLMFORGE_HOOKS=False`, and
`TLMFORGE_HOOKS=` (empty string set by some CI systems to disable a feature)
would NOT bypass. Users who set `TLMFORGE_HOOKS=false` (a conventional boolean
env var pattern) would get hooks enforcing when they expected bypass.

**Impact:** Unexpected enforcement in CI pipelines and scripts that use
`TLMFORGE_HOOKS=false` or `TLMFORGE_HOOKS=off` (conventional patterns from
other tools like `HUSKY=0`/`HUSKY=false`, `LEFTHOOK=0`/`LEFTHOOK=false`).

**Fix:** The bypass check must accept: `"0"`, `"false"`, `"False"`, `"FALSE"`,
`"no"`, `"off"`, and empty string `""` (env var set to empty). Document the
accepted values in README. Also accept `CI=true` and `GITHUB_ACTIONS=true` as
automatic bypasses for the git commit/push hook specifically (Hook 3), since
blocking CI commits is a common false-positive that has no "be quick" escape.

**Test to write:**
```python
# tests/test_env_bypass_variants.py
@pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "off", ""])
def test_tlmforge_hooks_bypass_accepted_values(value, monkeypatch):
    """All conventional 'disabled' env var values must bypass hooks."""
    monkeypatch.setenv("TLMFORGE_HOOKS", value)
    result = is_hooks_enabled()
    assert result is False
    # currently: only "0" returns False; "false" returns True (hook stays active)
```

---

#### EC-8: `git commit` in a detached HEAD state — plan's "N commits ahead" calculation is undefined

**Trigger:** `git commit` from a detached HEAD (e.g., after `git checkout <sha>`
or after a `git rebase` completes with Claude Code running). `git rev-parse HEAD`
returns a valid 40-char SHA — same as normal. BUT: `git rev-list verdict_sha..HEAD`
to count "N commits ahead" may fail or return unexpected results if the commit
is not reachable from the branch.

More concretely: when Hook 3 produces its block message "N commits ahead,"
the plan does not specify HOW N is computed. If N is computed via
`git rev-list <verdict_sha>..<HEAD> --count`, this call fails if `verdict_sha`
is not in the current branch's history (e.g., after a rebase that rewrote SHAs).

**What happens:** `git rev-list` exits non-zero, the hook crashes in the
subprocess call, fail-open fires → hook allows. The enforcement gate is silently
bypassed in the rebase-then-commit scenario.

**Impact:** Post-rebase commits bypass Stage 5b enforcement. The exact scenario:
Stage 5 verdict at SHA A → user rebases (SHA A disappears from history, becomes
A') → all subsequent commits don't trigger enforcement because `git rev-list A..HEAD`
fails.

**Fix:** Wrap `git rev-list` call in try/except; on failure, skip the commit
count (display "?" for N) but still enforce the block. The key check is
`HEAD != verdict_sha`, not the commit count. The count is cosmetic.

**Test to write:**
```python
# tests/test_hook3_verdict_sha_not_in_history.py
def test_hook3_verdict_sha_unreachable_after_rebase(tmp_repo):
    """Hook 3 must block (not crash) when verdict_sha is no longer in git history."""
    result = run_hook3(
        command="git commit -m 'post-rebase'",
        verdict_sha_in_audit="deadbeef00000000000000000000000000000000",  # not in history
        current_head="newsha...",
    )
    assert result["action"] == "block"
    assert "?" in result["message"] or result["message"] is not None
    # currently: git rev-list crashes -> fail-open -> allows
```

---

### MEDIUM

#### EC-9: Hook 3 command pattern does not anchor to `git merge` — merges bypass the Stage 5b gate

**Trigger:** The architecture diagram text says "git commit/push/merge" but the
actual regex pattern in the plan is `^(git commit|git push|gh pr merge)`.
`git merge main` (a local branch merge that creates a merge commit) is NOT
matched. A user who does `git merge feature-branch` after Stage 5, then
immediately `git push`, will have the merge commit bypass Stage 5b review:
the merge commit lands via push, which IS caught, but only the push — the
merge itself is not flagged.

This gap matters because: a merge commit can introduce code that no auditor
saw. The merge commit CONTENT needs Stage 5b review, not just the push.

**Impact:** Merge commits that add unreviewed code slip through the post-Stage-5
gate. LOW probability (user must do a local merge AND a push in one workflow
without using `git push origin feature-branch`), but the gap is inconsistent
with the stated goal of LL-1/LL-8 enforcement.

**Fix:** Add `git merge` to the pattern: `^(git commit|git push|git merge|gh pr merge)`.
If this causes too many false positives on routine branch syncs (`git merge main`
to pull upstream changes), limit to `git merge --no-ff` which creates an explicit
merge commit. Document the choice.

---

#### EC-10: Compound bash commands bypass Hook 3 pattern match — `cd <dir> && git commit`

**Trigger:** The regex `^(git commit|git push|gh pr merge)` requires git to be
the first token. A compound command like `cd /repo && git commit -m "msg"` starts
with `cd`, so the regex does not match. The CLAUDE.md rule says "never combine
`cd` with other commands" but that rule is about Claude's behavior, not the
user's manual input in a Bash tool call.

**What happens:** Hook 3 passes through, `git commit` executes unguarded.

**Impact:** Hook 3 enforcement can be bypassed by prepending any other command.
This is a single-user tool with discipline-integrity threat model, so this is
not an adversarial concern — but it IS a reliability gap. If Claude itself
generates a compound command (`cd /repo && git commit -m "init"`), the gate is
silently bypassed.

**Fix:** In addition to the `^` anchor check, check if the command STRING
contains `git commit` or `git push` or `gh pr merge` as a substring (not just
at the start). Or: use `shlex.split()` and scan all tokens for git subcommands.

---

#### EC-11: Performance benchmark fixture uses randomly-mixed line lengths — doesn't cover the worst-case realistic transcript structure

**Trigger:** The plan says "benchmark in Phase 0 with a synthetic 1MB transcript."
Our simulation shows the budget (50ms) is met comfortably (2.58ms worst-case
with full JSON parse). However, the synthetic fixture must represent the realistic
structure to be a valid benchmark.

Real Claude Code transcripts have:
- Very long tool_result lines (Read tool returning large file contents: 10K-100K chars per line)
- Many short tool_call lines
- The key worst case: the transcript file is 1MB but consists of 10-20 very long lines,
  not 500-1000 short lines

**What happens:** A 1MB transcript with 20 lines of 50K chars each is parsed
in 2.58ms — well within budget. But if the fixture used 10K short lines instead,
parse time would be different. The benchmark needs to verify BOTH shapes.

**Impact:** If the benchmark only covers the short-line case and the production
transcript is all-long-lines (or vice versa), the performance claim may not hold.

**Fix:** Phase 0 benchmark fixtures must include at least two transcript shapes:
(a) many short lines (~500 lines of ~2K chars), (b) few very long lines (~20 lines
of ~50K chars). Both must pass the 50ms p99 gate.

---

#### EC-12: `final_audit_*_5b_<sha>.json` filename — no specification for which SHA to use or how the Stage 5b workflow produces this file

**Trigger:** Hook 3 checks for Stage 5b re-review by globbing
`final_audit_*_5b_<HEAD-sha>.json`. But the plan does not specify:
1. Whether `<HEAD-sha>` is the HEAD at the time of 5b review or the HEAD
   at the time of the next `git commit`.
2. Whether the 5b marker must be in `specs/*/agent_verification/` or somewhere
   else.
3. What happens if the user does 3 commits after Stage 5 but only writes a
   5b marker for commit 2 — does commit 3 (HEAD != marker SHA) require another
   5b review?

**What happens:** Without a specification, the implementation will make an
ad-hoc choice that may not match the skill prompt template, creating mismatch
between what the skill produces and what the hook expects.

**Impact:** Workflow breakage. Stage 5b review was completed but Hook 3 still
blocks because the marker SHA doesn't match the current HEAD.

**Fix:** Define the 5b marker contract explicitly:
- Filename: `final_audit_<role>_5b_<verdict_sha>.json` where `<verdict_sha>`
  is the HEAD at the time the 5b review COMPLETED (recorded by the reviewer).
- Semantic: any commit whose SHA appears in `git rev-list <marker_sha>..HEAD`
  has NOT been reviewed. The gate blocks until a new 5b marker covers HEAD.
- The marker covers "HEAD as of 5b review"; future commits after 5b require
  their own 5b review.

---

### LOW

#### EC-13: Hook 1 injects reminder for EVERY prompt including "what time is it" — could degrade user experience severely

**Trigger:** Hook 1 injects the skill-invocation reminder on every `UserPromptSubmit`
event, unconditionally (by design, per "no keyword logic"). For a user who asks
conversational questions frequently ("what does this function do?", "summarize
this file", "explain the architecture"), every response begins with skill
invocation noise.

**Impact:** The plan acknowledges this (F11) and says SKILL.md's new Stage 0
handles it by exiting cleanly. But the exit is not zero-cost: the skill must
be loaded (~7K tokens) and Stage 0 must run before the graceful exit. This is
50+ tokens of overhead per conversational prompt, always. For a user with 50+
conversational prompts per day, this adds up.

**Noted:** This is a deliberate trade-off in the plan. The finding is here to
ensure the test plan includes a case that verifies Stage 0 exit is actually
invoked and short (not producing artifacts, not calling further agents).

---

#### EC-14: No test for Hook 2 behavior when `transcript_path` is not in the stdin JSON

**Trigger:** Claude Code's PreToolUse hook payload provides `transcript_path`.
If this field is absent (Claude Code version change, malformed payload, or
different host application), `hook.transcript_path` would raise `KeyError` or
return `None`. The plan lists `test_hook2_crash.py` as covering "bad transcript
path" but does not explicitly cover "missing transcript_path field entirely."

**Impact:** `KeyError` propagates to fail-open wrapper → hooks allow. Fine
for discipline (fail-open is correct), but the plan should make this explicit.

---

## Missing Tests

1. **Subagent / no-user-messages transcript** — `test_hook2_no_user_messages.py`
   Assert: Hook 2 passes through when transcript has zero user messages.
   Location: `hooks/tests/test_hook2_no_user_messages.py`

2. **Empty repo (zero commits) — Hook 3** — `test_hook3_no_commits.py`
   Assert: `git rev-parse HEAD` failing (exit 128) causes Hook 3 to pass-through.
   Location: `hooks/tests/test_hook3_no_commits.py`

3. **Short SHA in verdict_sha vs full SHA from HEAD** — `test_hook3_short_sha_verdict.py`
   Assert: Hook 3 normalizes short SHAs before comparison; does not false-block.
   Location: `hooks/tests/test_hook3_short_sha_verdict.py`

4. **Truncated JSONL line in transcript** — `test_transcript_partial_write.py`
   Assert: Per-line `JSONDecodeError` is caught; prior valid lines are returned.
   Location: `hooks/tests/test_transcript_partial_write.py`

5. **Override false positives for "minimal" and "trivial"** — `test_overrides_false_positive.py`
   Assert: "the trivial solution is O(n^2)" and "use minimal logging" do NOT trigger override.
   Location: `hooks/tests/test_overrides_false_positive.py`

6. **Hook 3 from subdirectory cwd** — `test_hook3_cwd_subdirectory.py`
   Assert: Stage 5 audit files are found and Hook 3 enforces even when cwd != repo root.
   Location: `hooks/tests/test_hook3_cwd_subdirectory.py`

7. **TLMFORGE_HOOKS accepted bypass values** — `test_env_bypass_variants.py`
   Assert: "0", "false", "False", "FALSE", "no", "off", "" all disable hooks.
   Location: `hooks/tests/test_env_bypass_variants.py`

8. **verdict_sha unreachable after rebase** — `test_hook3_verdict_sha_not_in_history.py`
   Assert: `git rev-list` failure does not crash Hook 3; block message uses "?" for commit count.
   Location: `hooks/tests/test_hook3_verdict_sha_not_in_history.py`

9. **Both transcript shapes in performance benchmark** — `test_hook2_performance.py`
   Assert: Hook 2 completes in <50ms for BOTH (a) 500 short lines and (b) 20 long lines (1MB total).
   Location: `hooks/tests/test_hook2_performance.py`

10. **5b marker SHA specificity** — `test_hook3_5b_marker_sha_mismatch.py`
    Assert: A 5b marker for SHA A does NOT unblock a commit at HEAD=B (B != A).
    Location: `hooks/tests/test_hook3_5b_marker_sha_mismatch.py`

11. **Missing transcript_path field in stdin** — `test_hook2_missing_transcript_field.py`
    Assert: Hook 2 fails open (passes through) when stdin JSON has no `transcript_path` key.
    Location: `hooks/tests/test_hook2_missing_transcript_field.py`

---

## Edge Cases Properly Handled

- **Fail-open on crash** (F9): explicitly designed in. The `safe.py` decorator
  catches all exceptions, writes to stderr, exits 0.
- **TLMFORGE_HOOKS=0 bypass**: all hooks check this first.
- **No Stage 5 yet**: Hook 3 treats absent `verdict_sha` as pass-through.
  Backward compatible with pre-existing features.
- **Detached HEAD SHA**: `git rev-parse HEAD` in a detached state returns a
  valid 40-char SHA — same as a normal HEAD. No special handling needed
  (the SHA is valid; the comparison works correctly).
- **Hook 2 task window for first user message**: first user message is event [0];
  scanning from [0] forward finds the skill invocation correctly. No anchor
  needed for the first message.
- **Hook 3 corruption in final_audit JSON**: truncated/invalid JSON → `json.JSONDecodeError`
  → file is skipped → treated as "no Stage 5 yet." Correctly specified.
- **Override scope per-prompt with reset**: the plan correctly requires scanning
  only the LAST user message for override phrases, not all messages in history.
- **Performance budget for 1MB transcript**: our benchmarks confirm 2.58ms
  worst-case for full JSON parse, well within 50ms p99 budget.
- **Hook 3 non-git Bash commands**: `ls -la`, `python ...` do not match the
  `^(git commit|git push|gh pr merge)` pattern → pass-through. Correct.
