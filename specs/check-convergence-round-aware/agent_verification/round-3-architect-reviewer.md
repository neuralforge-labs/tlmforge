# Round 3 Architect Review — check-convergence-round-aware

**Reviewer:** architect-reviewer
**Iteration:** 3 (final — verifying R2 findings only)
**Verdict:** needs_revision

---

## VERDICT: NEEDS REVISION

## Summary

Two of three round-2 findings are fully fixed. A6 is partially fixed (two
pinned tests now exist but the escalate test description is internally
self-contradictory). One new finding: the TDD plan table Phase 3 row still
says "deprecation warning" — a residual from A3 that was missed in the
round-2 fixes.

---

## Round-2 Finding Status

### A3 (CRITICAL) — Three-way contradiction on `evaluate_stage5_two_tier` fate
**Status: FIXED**

All four locations updated correctly:

- **Scope lines 38-39:** "**REMOVE** `evaluate_stage5_two_tier` entirely (R1-A3/T4/TH5: no in-tree callers per spec audit; suppressible DeprecationWarning is worse than cleanly absent)" — correct.
- **Architecture diagram lines 141-145:** "REMOVED ... DELETED in Phase 3 ... `ImportError` replaces silent drift" — correct.
- **Risk audit F3 (line 440):** "REMOVE function entirely. No shim" — correct.
- **Decisions Made (lines 463-467):** "REMOVED, not deprecated ... `ImportError` on import is a loud failure mode" — correct.
- **Verification criterion #5 (line 522):** "`evaluate_stage5_two_tier` does NOT exist — `from check_convergence import evaluate_stage5_two_tier` raises `ImportError`" — correct.

One residual: TDD plan table line 508 still says "deprecation warning" for
Phase 3 — logged as new finding N2 below.

---

### A6 (MEDIUM) — Phase 4 integration test ambiguous "retry or escalate"
**Status: PARTIALLY FIXED**

Two split tests now exist (lines 416-417):
- `test_integration_stage3_round_2_with_carryover_retry` — iteration=2, max_iterations=3 → `action="retry"`. Unambiguous. FIXED.
- `test_integration_stage3_round_2_with_carryover_escalate` — the description (line 417) is internally self-contradictory. It begins "iteration=3, max_iterations=3 → ... `action='escalate'` (cap hit)" then immediately says "cap_hit triggers AT iteration > max, so iteration=4 → escalate, iteration=3 → retry."

The test name ends in `_escalate` but the explanation says iteration=3 gives `retry`. An implementer will not know what fixture values to use or what to assert. The intended pinned value (iteration=4, max_iterations=3) is stated only parenthetically at the end of a sentence that opens with iteration=3.

**Required fix:** Rewrite line 417 as two unambiguous sentences. Something like:
"Fixture uses `iteration=4, max_iterations=3` (cap_hit=True because 4>3) → all 3 files missing → `action="escalate"`. This documents the boundary: iteration=3 gives `retry`; iteration=4 gives `escalate`."

---

### N1 (HIGH) — Test count floor stale
**Status: FIXED**

Verification criterion #2 (line 519): "Test count >= 45 (Phase 0: ~17, Phase 1: ~15, Phase 2: ~9, Phase 3: ~6, Phase 4: ~5 — post round-1 expansion; total ~52)" — matches per-phase test lists. Floor is meaningful.

---

## New Findings

### N2 — MEDIUM: TDD plan table Phase 3 row still says "deprecation warning"
**Location:** README.md line 508

```
| 3 | (extends above) | `evaluate_stage5_dual` single-shot semantics; deprecation warning | RED before impl |
```

This "deprecation warning" language was supposed to be updated as part of the
A3 fix. Every other section now says "REMOVE / ImportError" but this cell was
missed. An implementer reading the TDD plan table sees a contradiction with
Phase 3's own spec.

**Required fix:** Change the Phase 3 "What they verify" cell to:
"`evaluate_stage5_dual` single-shot semantics; removal of `evaluate_stage5_two_tier` (ImportError test)"

---

## Critical Issues (must fix before proceeding)

- None. The A6 ambiguity and N2 residual are medium severity. The plan is
  executable — the retry test is clean, and the escalate test's intent is
  recoverable from context. The TDD table cell is cosmetic relative to the
  detailed Phase 3 spec which is consistent.

## Warnings (should fix)

- A6 PARTIAL: `test_integration_stage3_round_2_with_carryover_escalate` description contradicts itself. Fix the fixture values to `iteration=4, max_iterations=3` and remove the ambiguous `iteration=3` parenthetical.
- N2: TDD plan table line 508 "deprecation warning" is a residual from A3. One-word fix.

## Suggestions (nice to have)

- The A6 escalate test description is long enough that it could be split into
  the test description line and a separate comment. Keeping it as one line
  risks future readers ignoring the parenthetical boundary note.

## What's Good

- A3 fix was thorough across 5 locations — Scope, Architecture diagram, Risk
  audit, Decisions Made, and Verification criterion all now point in the same
  direction.
- N1 fix is precise: the per-phase breakdown matches the phase sections and
  the total is realistic, making this an actual quality gate.
- The A6 retry test (`iteration=2, max_iterations=3 → action="retry"`) is
  now fully pinned and unambiguous.
- Phase 3's removal spec is self-consistent: the Phase 3 section, Phase 3
  verification criteria, and the removal-pin test all agree on ImportError.
