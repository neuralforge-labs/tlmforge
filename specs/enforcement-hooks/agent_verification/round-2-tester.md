# Round 2 Tester Review — enforcement-hooks

**Iteration:** 2
**Reviewer:** tester
**Verdict:** approve_with_warnings

---

## Prior Findings Resolution

### EC-1 (Subagent no user messages) — FIXED

Phase 2 spec explicitly: "If transcript has NO user-message entries (subagent session):
pass-through immediately." Architecture box also shows this path. Test
`test_hook2_no_user_messages.py` listed. Evidence: README.md lines 307-308, 140.

### EC-2 (git rev-parse HEAD exit 128) — FIXED

Phase 3 spec: "Run `git rev-parse HEAD`. Check returncode: Exit 128 (no commits, fresh
repo): WARNING to stderr, pass-through." Risk table also calls this out. Test
`test_hook3_no_commits.py` listed. Evidence: README.md lines 385-388, 543, 420.

### EC-3 (Short SHA normalization) — FIXED

Phase 3 spec: "Normalize verdict_sha to 40 chars: `git rev-parse <verdict_sha>`. On
failure (SHA not in history, e.g. after rebase): still enforce..." SKILL.md Stage 5
prompt addition includes "(full 40-char hash, not `--short`)". Test
`test_hook3_short_sha_verdict.py` listed. Evidence: README.md lines 389-391, 358-359, 417.

### EC-4 (Partial-write JSONDecodeError) — FIXED

Phase 0 transcript.py spec: "wrap `json.loads(line)` in per-line `try/except
JSONDecodeError` — skip malformed/truncated lines, continue." Test
`tests/test_transcript.py` covers "partial-write truncated line → skipped, no crash."
Evidence: README.md lines 233-235, 249.

### EC-5 (Override false positives) — FIXED (with residual: see NEW-1)

Architecture box shows updated list: `["be quick", "just do it", "trivial fix"]` with
explicit note "(bare 'minimal'/'trivial' removed — false positives)". Hook logic is
correctly specified in Phase 0/2. However Phase 1 reminder text still lists bare
`minimal` and `trivial` as override phrases — contradicting the fix. See NEW-1.
Evidence: README.md lines 142-145 (fixed), 283 (still broken).

### EC-6 (Subdirectory cwd) — FIXED

Phase 3 spec: "Use `git rev-parse --show-toplevel` to find repo root." Architecture box
confirms. Test `test_hook3_cwd_subdirectory.py` listed. Evidence: README.md lines
379-380, 162-163, 425. Partial gap in marker file read path: see NEW-2.

### EC-7 (TLMFORGE_HOOKS variants) — FIXED

Phase 0 env.py: accepts `{"0", "false", "no", "off", ""}` case-insensitive. Both
architecture boxes confirm. Test `tests/test_env.py` covers all variants and negatives.
Evidence: README.md lines 243-244, 148, 174, 255-256.

### EC-8 (Rebase verdict_sha not in history) — FIXED

Phase 3 spec: normalization failure → still enforce, display "?" for commit count.
Test `test_hook3_verdict_sha_not_in_history.py` listed. Evidence: README.md lines
389-392, 421.

### HIGH-1 (CI=true removed) — FIXED

Architecture box Hook 1: "sole bypass; no CI auto-detect." Decisions section explicitly
rejects CI=true and GITHUB_ACTIONS. Risk table confirms. Evidence: README.md lines
103, 557, 533.

### HIGH-2 (Skill fixture from live session) — FIXED

Phase 0 empirical validation: capture real Skill invocation JSONL and commit to
`hooks/tests/fixtures/skill_invocation_sample.jsonl`. Listed in sensitive surface
inventory. Evidence: README.md lines 228-229, 194.

### HIGH-3 (PSR marker internal SHA validation) — FIXED

Phase 3 spec: "open and verify `verdict_sha` field inside == HEAD (filename match
alone is not sufficient)." Architecture box shows "(SHA validated internally)". Test
`test_hook3_psr_marker_sha_mismatch.py` listed. Evidence: README.md lines 394-395,
169, 415.

---

## New Findings

### NEW-1 — Hook 1 reminder text contradicts override phrase list (MEDIUM)

**Severity:** medium
**Category:** documentation / logic_error
**File:** hooks/load_feature_dev_skill.py (Phase 1 spec)

The Phase 1 reminder text (README.md line 283) reads:
> "To bypass enforcement on this message, include `be quick`, `minimal`, `trivial`, or
> `just do it` in your prompt."

This lists `minimal` and `trivial` as effective overrides — but EC-5's fix explicitly
removed both from the override phrase list due to false positives. The actual hook logic
(Phase 0 overrides.py, Phase 2 enforce_skill_invoked.py) correctly excludes them. The
mismatch means: a user who reads the reminder and types "use minimal config" or
"trivial solution: change X" will expect bypass but get blocked. This breaks user trust
in the override mechanism.

**Fix:** Update Phase 1 reminder text to list only the three retained phrases:
"To bypass enforcement on this message, include `be quick`, `just do it`, or
`trivial fix` in your prompt." Update `test_hook1_normal.py` to assert the
reminder text does not contain bare `minimal` or `trivial` as standalone override terms.

---

### NEW-2 — Active-feature marker file read not anchored to repo root (LOW)

**Severity:** low
**Category:** bug
**File:** hooks/enforce_post_stage5_review.py (Phase 3 spec)

Phase 3 spec correctly anchors the glob to `git rev-parse --show-toplevel` (EC-6 fix),
but the read of `specs/.tlmforge_active_feature` is specified as a bare path — no
mention of repo root anchoring. If the user runs claude from a project subdirectory,
reading `specs/.tlmforge_active_feature` relative to cwd will fail (file not found),
and Hook 3 will pass-through as if no active feature exists, silently skipping the
PSR gate.

The test `test_hook3_cwd_subdirectory.py` is listed but does not explicitly call out
verifying that the marker file is also found (it focuses on the glob). The fix for EC-6
is necessary but not sufficient.

**Fix:** Add to Phase 3 spec: "Read `<repo_root>/specs/.tlmforge_active_feature`
anchored to git rev-parse --show-toplevel output, same as the glob." Update
`test_hook3_cwd_subdirectory.py` assertion to verify the active-feature marker file
is also resolved from repo root, not from cwd.

---

## Edge Cases Properly Handled

- EC-2: Returncode check is a proper integer check, not a string comparison on stdout.
- EC-3: Normalization via `git rev-parse <sha>` before comparison; graceful rebase
  degradation still blocks rather than silently passing.
- EC-4: Per-line try/except is semantically correct — a truncated line represents an
  incomplete event, not an error.
- EC-8: Still blocks with "?" commit count on rebase history loss — does not silently
  pass through, which was the dangerous outcome.
- HIGH-3: Internal SHA validation requirement explicitly stated, tested, and the
  rationale ("prevents accidental cp/rename bypasses") is documented in the spec.
- Multi-feature scoping (H2 from architect): Active-feature marker eliminates the
  mtime-based race entirely. Clean design.
- Fail-open: safe.py decorator covers all hooks; each hook has a crash test.
- TLMFORGE_HOOKS multi-value: Covers all conventional boolean-false representations
  including empty string (set by some CI tools).
- Subagent pass-through: Explicitly handled before any transcript read, avoiding
  both the fail-open and the block paths for Stage 3/4 reviewer agents.
