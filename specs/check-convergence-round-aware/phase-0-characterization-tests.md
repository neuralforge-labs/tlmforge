# Phase 0 — Characterization tests

## Goal
Pin existing behavior of `check_convergence.py` with unit tests BEFORE any code changes. Safety net for Phase 1+.

## Scope
**In:** Unit tests for every branch of `evaluate_convergence` and `evaluate_stage5_two_tier`. Boundary pins for the `>` vs `>=` cap asymmetry surfaced in R1-A1/T2.
**Out:** New behavior, refactoring, the (eventually removed) two-tier function itself.

## Files to be modified
- `tlmforge/skills/feature-development/tests/__init__.py` (new, empty)
- `tlmforge/skills/feature-development/tests/test_check_convergence.py` (new, ~17 tests)

## Tests to be added
See full list in master plan README.md §Phase 0.

## Verification criteria
- [ ] All ~17 tests pass on initial run (GREEN by definition — characterization)
- [ ] Each test has a docstring stating which branch it pins
- [ ] `python3 -m pytest tlmforge/skills/feature-development/tests/ -v` exits 0
- [ ] No `xfail`, no `pytest.skip`

## Rollback
`git revert HEAD` — instant, removes tests/ dir.

## Risks deferred to next phase
- Cap asymmetry resolution (Phase 3 removes `evaluate_stage5_two_tier`)
- Defensive loader hardenings (Phase 1)
