# Round 2 Architect Review — check-convergence-round-aware

**Reviewer:** architect-reviewer
**Iteration:** 2 (tracking R1 findings)
**Verdict:** needs_revision

---

## VERDICT: NEEDS REVISION

## Summary

Most round-1 findings were well-addressed, but a three-way internal contradiction about
whether `evaluate_stage5_two_tier` is removed vs. deprecated was introduced and remains
unresolved, plus the medium-severity integration test ambiguity (A6) was not fixed.

---

## Round-1 Finding Status

### A1 — CRITICAL: `>` vs `>=` cap-check inconsistency
**Status: FIXED**

README.md lines 181-182 add two explicit boundary-pin tests:
- `test_cap_hit_iteration_eq_max_in_evaluate_convergence` — pins `iteration=3, max=3 → cap_hit=False` (`>` semantic)
- `test_cap_hit_iteration_eq_max_in_two_tier` — pins `iteration=3, max=3 → cap_hit=True` (`>=` semantic)

Phase 3 verification criterion (line 379) explicitly states: "`iteration=3, max=3` is NOT cap_hit (resolves R1-A1/T2 asymmetry; `>` semantic survives)."

---

### A2 — CRITICAL: `reviewer-convergence.md` §3 body scope too narrow
**Status: FIXED**

Phase 3 (line 362) now explicitly updates §3 body + §4. Verification criterion (line 378) adds:
- `grep -E "tier-1.*trio\|tier-2" reviewer-convergence.md` → 0 matches in normative sections
- §3 body must cite `round-1-<role>.json` / `final_audit_<role>.json` (NOT flat `<role>_review.json`)

---

### A3 — HIGH: Back-compat shim silently discards CRITICALs
**Status: NOT FIXED — introduced new internal contradiction (escalated to CRITICAL)**

The fix-as-described (remove `evaluate_stage5_two_tier` entirely, Phase 3 line 311) is the
right call. However, three other sections of the plan were NOT updated to match:

1. **Scope section, line 38-39:** Still reads: "Mark `evaluate_stage5_two_tier` as deprecated
   (raises `DeprecationWarning`, delegates to `evaluate_stage5_dual` for tier-2 only)"
2. **Decisions Made, lines 444-448:** Still reads: "Deprecated `evaluate_stage5_two_tier` calls
   `evaluate_stage5_dual` internally — collapses tier-1 trio to 'use whichever architect-reviewer
   appears in tier1_jsons' + tier-2 to red-team. Imperfect but back-compatible enough for the
   no-op grace period. Future cleanup removes the wrapper entirely."
3. **Final verification criteria, line 503:** Still reads: "`evaluate_stage5_two_tier` emits
   `DeprecationWarning` on call" — which contradicts the Phase 3 removal decision.

An implementer reading top-to-bottom sees "add DeprecationWarning" in the Scope, "deprecated
calls dual internally" in Decisions Made, and "removes the function" in Phase 3. These are
three contradictory instructions. The TDD plan table (line 489) also says Phase 3 verifies
"deprecation warning" — also contradicting Phase 3's own removal spec.

**Required fix:** Update all four contradicting locations to match Phase 3's "REMOVE, no shim" decision:
- Scope line 38-39: change "Mark as deprecated (raises DeprecationWarning...)" to "Remove `evaluate_stage5_two_tier` entirely (no shim)"
- Decisions Made lines 444-448: replace the "Deprecated calls dual internally" paragraph with "Remove, don't deprecate. No suppressible DeprecationWarning."
- Final verification criteria line 503: change to "`evaluate_stage5_two_tier` is absent (`ImportError` on import)"
- TDD plan table line 489: change "deprecation warning" to "removal (`ImportError` test)"

---

### A4 — HIGH: `evaluate_stage5_dual` return shape unspecified
**Status: FIXED**

Lines 319-350 provide a fully pinned spec: internal delegation to `evaluate_convergence(reviewer_jsons={...}, iteration=1, max_iterations=1)`, explicit `action` promotion (`"advance"` → `"ship"`), and a concrete return dict at lines 341-350. The delegation pattern eliminates duplication.

---

### A5 — MEDIUM: Phase 0 TDD wording contradiction (characterization tests can't be RED)
**Status: FIXED**

Lines 190-194 replace the contradictory criterion with: "All ~17 tests pass on initial run against unmodified `check_convergence.py` (characterization tests are GREEN by definition)" plus the docstring requirement.

---

### A6 — MEDIUM: `test_integration_stage3_round_2_with_carryover` still ambiguous
**Status: NOT FIXED**

Line 399 still reads: `action="retry"` **(or `escalate` if iteration counter says cap)**

No iteration/max_iterations values are specified. The fix summary (round-1-fixes.md) does not mention A6 at all — it was not addressed. An implementer will pick arbitrarily between `retry` and `escalate`.

**Required fix:** Specify concrete parameter values on line 399. The unambiguous form is:
- `iteration=2, max_iterations=3` → assert `action="retry"` (cap not hit, round 2 of 3 allowed)
- Add a second variant: `iteration=4, max_iterations=3` → assert `action="escalate"` (cap hit)

---

## New Findings

### N1 — HIGH: Test count in final verification criteria is stale
**Location:** README.md line 500

The final "done when" criteria (line 500) states: "Test count >= 25 (Phase 0: ~15, Phase 1: ~7, Phase 2: ~9, Phase 3: ~8, Phase 4: ~5)"

But the round-1 fixes GREW the test counts significantly:
- Phase 0: ~15 → ~17 (per fixes summary line 160)
- Phase 1: ~7 → ~15 (per fixes summary line 162; also Phase 1 section says "≈15")
- Phase 3: ~8 → ~6 (per fixes summary line 164)

The plan's own updated phase sections say Phase 1 has ~15 tests, but the verification criteria says ~7. Total in the updated per-phase spec is ~17+~15+~9+~6+~5 = ~52 (per fixes summary line 166). The floor "Test count >= 25" is now so low it provides no quality gate — an implementation that skips half the tests would pass the criterion. A tester checking line 500 against reality will find an unstable number.

**Required fix:** Update line 500 to reflect the new per-phase actuals: "Test count >= 45 (Phase 0: ~17, Phase 1: ~15, Phase 2: ~9, Phase 3: ~6, Phase 4: ~5)" — or at minimum sync the count in the final criteria to match the per-phase test lists.

---

## Suggestions (nice to have)

### S1 — Phase 3 single-commit clarity
Phase 3 (line 355) says the removal + test deletion happen in "single-commit per Phase 3." This is correct but should be explicit in the verification criteria so the tester knows to check `git log --oneline -1` confirms it's one commit, not two.

---

## What's Good

- The `evaluate_stage5_dual` delegation pattern (lines 319-350) is clean and eliminates code duplication. This is the right call.
- Phase 1's security-hardening surface (6 defenses in one helper) is well-organized. Mapping each defense to its R1 finding source makes traceability explicit.
- The path-containment + role-allowlist as independent defenses (defense-in-depth) is correct.
- Phase 0 boundary-pin tests for the `>` vs `>=` discrepancy are precisely specified with both sides of the asymmetry captured.
- Phase 3 removal verification grep (`grep -n "evaluate_stage5_two_tier" check_convergence.py` → 0) pins the absence, not just the presence of the replacement.
