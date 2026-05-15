# Round 3 Architect Review — enforcement-hooks

## VERDICT: APPROVE

## Summary

Round 3 review of the enforcement-hooks master plan after round-2 fixes.
All three prior critical/medium/low findings are fully resolved. One nit
(dual-PSR intermediate state test) is substantially addressed. One new
documentation nit found — a stale "Stage 5b" label survived in the Phase 4
internal verification block — but it is not a blocker.

---

## Round-2 Findings Disposition

### CRITICAL — NF1: Reminder text contradiction (Phase 1 systemMessage)

**Verdict: FIXED**

Evidence: Lines 278–283 of README.md. The injected systemMessage now reads:
`be quick`, `just do it`, or `trivial fix` — and explicitly states
"(Bare 'minimal' / 'trivial' are NOT accepted — they appear too often in
technical prose.)". This exactly matches the override library at lines
237–239 and 568–569. The user-visible contract now matches the
implementation.

---

### MEDIUM — Stale `.claude-plugin/hooks.json` ref in Verification Criteria

**Verdict: FIXED**

Evidence: Line 626 now reads:
"All 3 hooks ship in `hooks/`, wired in `hooks/hooks.json` at plugin root"

The wrong path `.claude-plugin/hooks.json` is gone.

---

### LOW — Stale "Stage 5b post-commit" label in top-level Verification Criteria

**Verdict: FIXED**

Evidence: Line 637 now reads:
"SKILL.md has Stage 0 + PSR (post-Stage-5 re-review) subsection +
active-feature marker steps"

The deprecated "Stage 5b" label is gone from the top-level checklist.

---

### NIT — Phase 5 integration test only adds both PSR files simultaneously

**Verdict: FIXED (substantially)**

Evidence: Lines 499–503. The integration test now sequences:
(1) HEAD=A → Hook 3 allows commit;
(2) Advance HEAD to B → Hook 3 blocks;
(3) Add both PSR markers (red-team + architect) with internal verdict_sha=B
    → Hook 3 allows.

The dual-file requirement is confirmed by the unit test
`test_hook3_psr_marker_sha_mismatch.py`. The integration test does not
independently stage "only red-team PSR present" as an intermediate state,
but this was a nit, not a critical, and the unit layer covers the logic.
Acceptable at this level.

---

### NEW-2 (from round-2 tester) — Active-feature marker path not repo-root-resolved

**Verdict: FIXED**

Evidence: Lines 378–383. Phase 3 implementation now calls
`git rev-parse --show-toplevel` FIRST (single call), resolves
`<repo_root>/specs/.tlmforge_active_feature` for the marker read, and reuses
the already-resolved repo_root for the subsequent glob. The redundant second
`--show-toplevel` call is explicitly removed ("repo root already resolved
above; reuse for all subsequent paths"). Test `test_hook3_cwd_subdirectory.py`
is updated to cover both marker + glob path resolution (line 427–428).

---

## New Findings (Round 3)

### NIT — Stale "Stage 5b section" label in Phase 4 internal verification block

**File:** specs/enforcement-hooks/README.md, line 474
**Severity:** Nit / documentation only

The round-2 fix correctly updated the TOP-LEVEL Verification Criteria
(line 637) from "Stage 5b" to "PSR (post-Stage-5 re-review)". However, the
Phase 4 internal verification block at line 474 was not updated and still
reads:

    "Stage 5b section has post-commit re-review subsection"

This is the same stale label at a different location in the file. An
implementer checking off Phase 4 completion against this checklist would look
for a "Stage 5b section" in SKILL.md that doesn't exist under that name.

Suggested fix: change line 474 to:
    "SKILL.md PSR (post-Stage-5 re-review) subsection exists"

This is NOT a blocker. The implementation guidance and the SKILL.md content
description are already correct throughout the plan; only this local checklist
item is stale.

---

## What's Good

- All three critical/medium/low findings from round 2 are cleanly resolved
  with specific textual evidence.
- The override phrase list is now fully consistent across all three locations
  where it appears: Hook 2 architecture diagram (lines 140–143), Phase 2
  block message (line 322), Hook 3 architecture diagram (line 173), Phase 3
  implementation steps (line 398), and Phase 1 reminder text (lines 278–283).
- The NEW-2 cwd-subdirectory fix is thorough: single `--show-toplevel` call,
  explicit reuse annotation, and test coverage updated.
- The integration test in Phase 5 (lines 494–503) now forms a coherent
  end-to-end scenario covering all three hooks in sequence.
- The plan remains correctly scoped — no scope creep introduced during fixes.
