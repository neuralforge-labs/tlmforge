# Round 1 Architect Review — check-convergence-round-aware

**Reviewer:** architect-reviewer
**Iteration:** 1 (cold review, no prior rounds)
**Verdict:** needs_revision

---

## VERDICT: NEEDS REVISION

## Summary

The master plan is architecturally sound and well-structured. Three issues require
fixing before implementation begins: a pre-existing cap-check inconsistency that the
characterization tests must pin (not silently inherit), an under-scoped `reviewer-convergence.md`
update that will leave stale prose pointing at 0.4.0 paths, and an underspecified
back-compat shim whose structural mismatch is acknowledged but not resolved.

---

## Instruction Compliance

The plan faithfully addresses all requirements from the spec audit:
- F1 (no existing tests) → Phase 0 characterization
- F3 (obsolete two-tier) → Phase 3 deprecation + new dual function
- F4 (malformed JSON crash) → `_load_json_safely`
- F5 (caller has to regex action) → `action` field in return dict
- F6/F7/F8 → distinct loaders, correct path patterns, ux-reviewer conditional handling
- Integration test in Phase 4 covers the full pipeline

No scope creep observed. Out-of-scope items (DF1, DF2, migration) are correctly deferred.

---

## Critical Issues (must fix before proceeding)

### C1. Existing cap-check inconsistency is NOT called out in the characterization test plan

`evaluate_convergence` (line 135): `cap_hit = iteration > max_iterations`
`evaluate_stage5_two_tier` (line 364): `if iteration >= max_iterations:`

These are semantically different. With `max_iterations=3`:
- `evaluate_convergence` cap fires at iteration=4 (meaning iteration 3 is the last allowed clean round)
- `evaluate_stage5_two_tier` cap fires at iteration=3 (meaning tier-1 converging at the LAST allowed round triggers the "user override required" branch)

This inconsistency is a real bug in the current code. The plan's Phase 0 characterization tests
(`test_evaluate_stage5_two_tier_tier2_critical_at_cap`) will SILENTLY INHERIT whichever behavior
exists today without flagging the discrepancy. The plan must explicitly call out this semantic
difference in the Phase 0 test descriptions, add a test that probes `iteration=3 vs iteration=4`
in both functions, and decide the intended semantics BEFORE Phase 3 replaces `evaluate_stage5_two_tier`.
If `evaluate_stage5_dual` inherits `evaluate_convergence`'s `>` semantics, existing behavior changes.
If it uses `>=`, the inconsistency persists in a new form.

**Suggested fix:** Add a test `test_cap_semantics_consistency` in Phase 0 that asserts both functions
agree on the boundary. Document in Phase 3 whether `evaluate_stage5_dual` follows `>` or `>=`, and
why. The Phase 0 section must state: "NOTE: `evaluate_stage5_two_tier` uses `>=` while
`evaluate_convergence` uses `>` — pin both behaviors explicitly; Phase 3 must resolve which is correct."

### C2. `reviewer-convergence.md` update scope is too narrow — §3 prose is also stale

The plan says "update §0 and §4 references." But §3 of `reviewer-convergence.md` (the convergence
rule description) contains TWO stale items:

1. §3 item 1: "Collect all `<role>_review.json` files in `specs/<feature>/agent_verification/`" —
   this is the 0.4.0 flat path. Under 0.5.0 it should cite `round-N-<role>.json` patterns via the
   new loaders.
2. §3 item 2: "Stage 5 tier-1 default: architect-reviewer + code-reviewer + tester + gemini-if-present;
   Stage 5 tier-2: red-team-reviewer" — entirely obsolete. 0.5.0 Stage 5 is
   `red-team-reviewer + architect-reviewer`, single shot.

If these are not updated, the document is self-contradicting: §0 says one thing, §3 says another.
Future reviewers (and agents reading this document as prompt context) will get conflicting information.

**Suggested fix:** Add §3 items 1 and 2 to the list of stale content that Phase 3 must update.
The scope in "Files modified: reviewer-convergence.md — update §0/§4 references" must be
broadened to include §3 body text.

---

## Warnings (should fix)

### W1. Back-compat shim's structural mismatch is unresolved at plan time

The plan says: "Deprecated `evaluate_stage5_two_tier` calls `evaluate_stage5_dual` internally —
collapses tier-1 trio to 'use whichever architect-reviewer appears in tier1_jsons' + tier-2 to
red-team. Imperfect but back-compatible enough."

"Imperfect" is doing a lot of work here. The original `evaluate_stage5_two_tier` takes
`tier1_jsons: dict` (a role→JSON map of 3–4 reviewers) and `tier2_red_team_json: Optional[dict]`.
The new `evaluate_stage5_dual` takes `red_team_json` and `architect_json` (two specific named
inputs). Collapsing tier-1 to "whichever architect-reviewer appears" means:
- If `tier1_jsons` has no `architect-reviewer` key, the shim maps to `None` → synthetic
  CRITICAL injected → behavior change that caller never expected from the deprecated path.
- The tier-1 CRITICAL count from the other tier-1 reviewers (code-reviewer, tester) is silently
  DISCARDED. This is a behavioral regression that could cause a "converged" result where the
  original function would have returned "not converged."

The test `test_evaluate_stage5_two_tier_delegates_to_dual` needs to explicitly cover the case where
tier-1 has a real CRITICAL from `code-reviewer` (not `architect-reviewer`) and assert that this
case is handled — either by preserving the CRITICAL or by documenting that the shim intentionally
drops it and why that's acceptable for a grace-period wrapper.

**Suggested fix:** Either (a) have the shim aggregate all tier-1 CRITICALs before delegating,
or (b) document explicitly that the shim is "best-effort" and the caller must migrate before any
real use of the deprecated path. Add a test that covers the silent-discard case.

### W2. Phase 0 "verify RED" criteria is ambiguous for characterization tests

The plan states: "Tests RED before existing code is touched (sanity check that they actually test
something)." Characterization tests by definition are written to PASS against the current code —
that is their purpose. Running them red first is impossible for tests that characterize current
behavior. The plan conflates TDD RED-first discipline (for new behavior) with characterization
testing (which locks existing behavior and should be green immediately).

This matters because the Phase 0 verification criterion is self-contradictory: "All ~15 tests pass
on initial run against unmodified `check_convergence.py`" AND "Tests RED before existing code is
touched." Both cannot be true for characterization tests.

**Suggested fix:** Clarify that Phase 0 tests are characterization tests and should be GREEN on
first run against the unmodified code. The RED-first discipline applies only to Phase 1+ tests
(which test NEW behavior before the code exists). The verification criterion should say:
"Phase 0: run GREEN immediately (they pin existing behavior). Phase 1+: run RED first, then GREEN
after implementation."

### W3. `evaluate_stage5_dual` return shape is not specified in the plan

The plan says it returns `{final_converged, action, ...}` and "same shape conventions as the
iterative ones." But `evaluate_convergence` returns 8 keys including `findings_by_role`,
`real_critical_count`, `meta_critical_count`, `warnings`. The Stage 5 dual function receives
exactly 2 inputs (named parameters, not a `reviewer_jsons` dict). Does it still return
`findings_by_role`? Does it return `real_critical_count`/`meta_critical_count`? If yes, where
does it get those counts (it has no `evaluate_convergence` call described)?

Without a specified return shape, the test `test_evaluate_stage5_dual_both_approve` can't be
written unambiguously — the implementer has to guess what keys to assert.

**Suggested fix:** Add a concrete return-shape spec to Phase 3, e.g.:
```
{
  "final_converged": bool,
  "action": "ship" | "escalate",
  "red_team_critical_count": int,
  "architect_critical_count": int,
  "user_message": str,
  "findings_by_role": dict   # {red-team: json, architect: json}
}
```
Or explicitly say it delegates to `evaluate_convergence` internally (passing the two jsons as a
`reviewer_jsons` dict with `expected_roles=["red-team-reviewer", "architect-reviewer"]`) which
would reuse all existing logic cleanly.

---

## Suggestions (nice to have)

### S1. Consider delegating `evaluate_stage5_dual` to `evaluate_convergence`

The cleanest implementation of `evaluate_stage5_dual` would be:
```python
def evaluate_stage5_dual(red_team_json, architect_json):
    reviewer_jsons = {"red-team-reviewer": red_team_json, "architect-reviewer": architect_json}
    result = evaluate_convergence(reviewer_jsons, list(reviewer_jsons.keys()), iteration=1, max_iterations=1)
    result["action"] = "ship" if result["converged"] else "escalate"
    result["final_converged"] = result["converged"]
    return result
```
This delegates entirely to the tested core, avoids duplicating CRITICAL-counting logic, and
automatically inherits any future improvements to `evaluate_convergence`. The plan doesn't mention
this approach — worth evaluating during Phase 3.

### S2. `test_integration_stage3_round_2_with_carryover` test description needs clarification

The test says "round-1 files + `tester_edge_cases.json` + `round-1-fixes.md` present; load round-2
files (which don't exist yet) → all 3 missing → 3 synthetic meta CRITICALs → `action='retry'`
(or `escalate` if iteration counter says cap)."

The "or escalate" is ambiguous — what iteration counter is used in the test? Specify `iteration=2,
max_iterations=3` → `action="retry"`. The ambiguity will cause the implementer to pick arbitrarily.

### S3. Phase 4 evidence requirement: add pytest command verbatim

Phase 4's verification criterion says "phase-4-evidence.md contains the actual pytest output."
Add the exact command to run: `python3 -m pytest tlmforge/skills/feature-development/tests/ -v
--cov=tlmforge/skills/feature-development/check_convergence --cov-report=term-missing` so the
tester knows exactly what output to capture.

---

## What's Good

- Phase ordering is correct: characterization tests (Phase 0) before any code changes, then
  additive phases, then the destructive deprecation (Phase 3). This is exactly right.
- The decision to NOT inject synthetics in the loaders (preserving single responsibility) is
  sound architecture. The convergence logic lives in one place.
- `_load_json_safely` catching both `json.JSONDecodeError` AND `OSError` covers the partial-write
  race correctly.
- The `action` enum addition to `evaluate_convergence` is a clean, non-breaking extension of
  the return dict. Existing callers that don't check `action` are unaffected.
- The `expected_roles` delegation to the caller for ux-reviewer conditional inclusion is the
  right abstraction boundary.
- `tmp_path`-based fixtures for integration tests correctly prevent test pollution of real
  `specs/` directories.
- The scope boundary (marketplace publish, duplicate file cleanup explicitly out-of-scope) is
  appropriately tight.
- Rollback via `git revert HEAD` per phase is realistic and sufficient for a pure Python,
  no-schema-change, no-DB change.
- Cost analysis is honest (zero API calls, pure token cost).
