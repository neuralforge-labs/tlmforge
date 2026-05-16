# v058-validation — Tester Review (Round 1)

## Verdict: NEEDS_REVISION

## Edge cases found

### EC-1 (CRITICAL): Pre-fix bug pin test is tautological
The planned Test 6 (`TestConvergenceMediumPath`) calls `evaluate_convergence()` with
`expected_roles=[..., "threat-modeler"]` and no threat-modeler JSON. This always injects
a `reviewer_json_missing` CRITICAL — it tests the function itself, not v0.5.8's fix.
An accidental revert of the Medium rows in reviewer-convergence.md would NOT cause this
test to fail.

### EC-2 (HIGH): Test 4 is vacuous (superset-of-Deep agents)
`evaluate_convergence(expected_roles=["code-reviewer","phase-auditor"], jsons={all 3 Deep})`
trivially converges because `evaluate_convergence` iterates `expected_roles`, not
`reviewer_jsons.keys()`. Extra keys in `jsons` are always ignored. This tests nothing
about v0.5.8.

### EC-3 (MEDIUM): No test pin for extra-reviewer-in-jsons-is-ignored behavior
The implicit assumption (extra jsons keys ignored) is untested. If someone refactors
`evaluate_convergence` to iterate `reviewer_jsons.keys()` instead, this would cause
spurious CRITICALs but no existing test would catch it.

### EC-4 (MEDIUM): Cross-section substring searches produce false positives for absence checks
Global `in content` searches for "threat-modeler" would pass even if threat-modeler
only appears in Deep rows. A revert of the Medium row would go undetected if the Deep
row still exists. Row-scoped regex is required for absence assertions.

### EC-5 (LOW): Empty expected_roles edge case not covered
`evaluate_convergence(expected_roles=[], reviewer_jsons={}, iteration=1)` is not tested.
Its behavior (trivially converges with 0 meta criticals) should be pinned.

## Resolution

All 5 findings addressed in `round-1-fixes.md` — see that file for the concrete changes.
