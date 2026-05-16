# v058-validation — Round 1 Plan Fixes

## Findings addressed

### C1 (architect-reviewer) / EC-1 (tester): Pre-fix bug pin test is tautological

**Finding:** Test 6 (`TestConvergenceMediumPath`) calls `evaluate_convergence()` with
`expected_roles=[..., "threat-modeler"]` and no threat-modeler JSON. This injects a
synthetic `reviewer_json_missing` CRITICAL unconditionally — it tests the function's
own behavior, not v0.5.8's change. An accidental revert of the Medium rows in
reviewer-convergence.md would NOT be caught.

**Fix:** Remove the standalone functional "pre-fix bug pin" test. Replace with a
`TestTDDRedPhase` class containing inline v0.5.7 content strings that prove the
content integrity tests would have been RED before the fix. Also add a row-scoped
content assertion: parse the Medium Stage 3 row from the table and assert
`threat-modeler` is absent from that row's roles cell (not just from the whole doc).

### H1 (architect-reviewer): CLAUDE.md skip-on-absent silently drops a test

**Finding:** `~/.claude/CLAUDE.md` is outside the repo. Skip-on-absent means test 15
is silently not run on any machine without that file, making the test non-reproducible.

**Fix:** Create `skills/feature-development/tests/fixtures/claude_medium_path_excerpt.txt`
as a committed fixture containing the relevant CLAUDE.md fragment. All machines can
read it. The content integrity test reads this fixture unconditionally — no skip.

### H2 (architect-reviewer): TDD plan contradicts itself on RED phase

**Finding:** TDD plan section said "verify all 15 GREEN (files already patched)"
while Phase steps mentioned inline v0.5.7 fixtures for RED. These contradict.

**Fix:** Add explicit `TestTDDRedPhase` class. Tests in this class use inline v0.5.7
content strings (table without Medium rows, SKILL.md text from before the fix) and
assert the absence of patterns that v0.5.8 added. This class goes RED on v0.5.7
content and GREEN trivially because the inline strings are the fixtures — no
live file reads in this class. Evidence section captures the RED run output.

### M1 (architect-reviewer): "151+" unanchored baseline

**Fix:** Baseline established before implementation: 130 (hooks/tests) + 30 (skill
tests) = 160 existing. New file adds 22 tests → expected total: 182 passed.
Verification criterion updated to: `160 + 22 = 182 expected, 0 failed`.

### M2 (architect-reviewer) / EC-2 (tester): Test 4 is vacuous (superset-of-Deep)

**Finding:** `evaluate_convergence(expected_roles=["code-reviewer","phase-auditor"],
reviewer_jsons={all 3 Deep})` trivially converges because `evaluate_convergence`
iterates `expected_roles`, not `reviewer_jsons.keys()`. Extra keys are always ignored.

**Fix:** Replace test 4 with the actual regression guard:
`evaluate_convergence(expected_roles=["code-reviewer","phase-auditor"], jsons only
those two)` → asserts `converged=True, meta_critical_count=0`. This proves Medium
Stage 4 does NOT inject a synthetic CRITICAL for tester being absent — which is
exactly what the v0.5.8 fix prevents. Add a separate test
`test_extra_reviewer_in_jsons_is_ignored` to cover EC-3 explicitly.

### EC-4 (tester): Cross-section substring matches produce false positives

**Finding:** Global `in content` searches for e.g. "threat-modeler" would pass even
if threat-modeler only appears in Deep rows. A revert of the Medium row deletion
would go undetected if the Deep row still exists.

**Fix:** All absence assertions use a row-scoped regex: extract the `| Medium |` row
for the relevant stage, then assert on that row's roles cell content only.

### EC-5 (tester): Empty expected_roles edge case not pinned

**Finding:** Calling `evaluate_convergence` with `expected_roles=[]` was not tested.

**Fix:** Add `test_empty_expected_roles_converges` as the 7th convergence test.

## Updated test count: 22 total

`TestTDDRedPhase` (4 tests):
- v0.5.7 table has no Medium Stage 3 row
- v0.5.7 table has no Medium Stage 4 row
- v0.5.7 SKILL.md has no security-surface override paragraph
- v0.5.7 CLAUDE.md excerpt has "5-stage recipe" text

`TestSkillContentIntegrity` (11 tests):
- reviewer-convergence.md: Medium Stage 3 row exists with correct agents
- reviewer-convergence.md: Medium Stage 3 row has no threat-modeler
- reviewer-convergence.md: Medium Stage 4 row exists with correct agents
- reviewer-convergence.md: Medium Stage 5 row exists with phase-auditor
- SKILL.md: security-surface override paragraph present
- SKILL.md: security-surface override between table and Announce section
- SKILL.md: §4.3 medium annotation present
- SKILL.md: phase-end medium annotation present
- SKILL.md: Stage 6 medium skip section present
- SKILL.md: medium checklist has conditional round-2 items
- claude_medium_path_excerpt.txt fixture: has "abbreviated recipe" not "5-stage"

`TestConvergenceMediumPath` (7 tests):
- Medium Stage 3 with 2 agents (architect + tester) → converges
- Medium Stage 3 missing tester → meta CRITICAL (tester IS expected)
- Medium Stage 4 (code-reviewer + phase-auditor) → converges, 0 synthetics (v0.5.8 regression guard)
- Medium Stage 4 extra reviewer in jsons → ignored, still converges
- Medium Stage 5 (phase-auditor only) → converges
- Medium Stage 3 missing architect-reviewer → meta CRITICAL (architect IS expected)
- Empty expected_roles → converges with 0 meta criticals

## TDD discipline

RED phase: run `TestTDDRedPhase` with inline v0.5.7 strings → confirm RED (assertions
on absent-pattern deliberately fail against v0.5.7 content).
GREEN phase: run full file → all 22 pass, 160 + 22 = 182 total, 0 regressions.
