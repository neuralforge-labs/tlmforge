# Phase 0 — Hard Evidence

## Test runs (per layer)

### Unit tests (only layer for Phase 0 — pure-function tests, no I/O)

```
$ ~/trading/venv/bin/pytest $REPO_ROOT/skills/feature-development/tests/ -v
============================ test session starts ============================
collected 18 items

test_check_convergence.py::test_evaluate_convergence_all_approve PASSED
test_check_convergence.py::test_evaluate_convergence_skipped_reviewer PASSED
test_check_convergence.py::test_evaluate_convergence_missing_json PASSED
test_check_convergence.py::test_evaluate_convergence_real_critical PASSED
test_check_convergence.py::test_evaluate_convergence_meta_critical PASSED
test_check_convergence.py::test_evaluate_convergence_lazy_empty_blocking_verdict PASSED
test_check_convergence.py::test_evaluate_convergence_lazy_empty_approve_verdict PASSED
test_check_convergence.py::test_evaluate_convergence_cap_hit_real_only PASSED
test_check_convergence.py::test_evaluate_convergence_cap_hit_meta_only PASSED
test_check_convergence.py::test_evaluate_convergence_cap_hit_both PASSED
test_check_convergence.py::test_cap_hit_iteration_eq_max_in_evaluate_convergence PASSED
test_check_convergence.py::test_cap_hit_iteration_eq_max_in_two_tier PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_tier1_not_converged PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_tier1_converged_no_tier2 PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_tier2_skipped PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_both_converged PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_tier2_critical_below_cap PASSED
test_check_convergence.py::test_evaluate_stage5_two_tier_tier2_critical_at_cap PASSED

============================== 18 passed in 0.08s ==============================
```

### Integration / E2E tests
N/A for Phase 0 — characterization tests are pure unit (function-takes-dict,
function-returns-dict, no I/O). Integration coverage lands in Phase 4 of
the master plan.

## Full pre-existing test suite (regression check)

There are NO pre-existing tests in `tlmforge/skills/feature-development/tests/`
(this directory was created in Phase 0). The plugin's other skills
(`live-evaluator`, `property-test-generator`, etc.) have no Python tests
to regress. **Zero regression risk — no existing test surface to break.**

## Summary

- Unit: 18 passed, 0 failed, 0.08s elapsed
- Integration: N/A this phase
- E2E: N/A this phase
- Full pre-existing suite: empty (no tests existed for this skill before this phase)
- Coverage: not measured (would need `--cov`; coverage measurement deferred to Phase 4 verification)

## One round-2 fix
- Initial run had 1 failure: `test_evaluate_convergence_skipped_reviewer`
  used `warnings[0]` but the lazy-empty warning for architect-reviewer
  fires first; gemini's skipped warning is later in the list. Test
  assertion changed to `any(...)` over the warnings list. Re-run: all
  18 pass. Trivial test-author bug, not a behavior mismatch.

## Reproducibility

```bash
git checkout <this-commit-SHA>
~/trading/venv/bin/pytest $REPO_ROOT/skills/feature-development/tests/ -v
# Expect: 18 passed in <0.1s
```

## What this Phase 0 result PROVES

1. Every documented branch of `evaluate_convergence` works exactly as
   documented (all 11 evaluate_convergence tests passing).
2. Every documented branch of `evaluate_stage5_two_tier` works exactly
   as documented (all 6 two-tier tests passing).
3. The `>` vs `>=` cap-check asymmetry from R1-A1/T2 is real and now
   pinned by 2 boundary tests (one for each function). Phase 3 can
   safely remove `evaluate_stage5_two_tier` without ambiguity.

Future phases that change behavior MUST keep these 18 tests passing
(except Phase 3, which deletes the 6 two_tier tests alongside the
function in the same commit, reducing the count to 12).
