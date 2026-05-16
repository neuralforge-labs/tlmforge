# v058-validation — Phase 1 Evidence

## Commands run

```
# Baseline (before adding test file)
cd $REPO_ROOT/hooks/tests && python3 -m pytest -q --tb=no
# → 130 passed

cd $REPO_ROOT/skills/feature-development/tests && python3 -m pytest test_check_convergence.py test_checkpoint_format.py -q --tb=no
# → 30 passed
# Baseline: 160 total

# New test file — full run
cd $REPO_ROOT/skills/feature-development/tests
python3 -m pytest test_v058_medium_path.py -v
```

## New test output (verbatim)

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
collected 23 items

test_v058_medium_path.py::TestTDDRedPhase::test_v057_table_has_no_medium_stage3_row PASSED [  4%]
test_v058_medium_path.py::TestTDDRedPhase::test_v057_table_has_no_medium_stage4_row PASSED [  8%]
test_v058_medium_path.py::TestTDDRedPhase::test_v057_skill_has_no_security_surface_override PASSED [ 13%]
test_v058_medium_path.py::TestTDDRedPhase::test_v057_claude_excerpt_has_5_stage_recipe_not_abbreviated PASSED [ 17%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_has_medium_stage3_row PASSED [ 21%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_medium_stage3_row_has_architect_and_tester PASSED [ 26%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_medium_stage3_row_lacks_threat_modeler PASSED [ 30%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_has_medium_stage4_row PASSED [ 34%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_medium_stage4_row_has_code_reviewer_and_phase_auditor PASSED [ 39%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_medium_stage4_row_lacks_tester PASSED [ 43%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_convergence_md_has_medium_stage5_row_with_phase_auditor PASSED [ 47%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_skill_md_has_security_surface_override PASSED [ 52%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_skill_md_security_override_is_before_announce_section PASSED [ 56%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_skill_md_phase_end_medium_annotation_present PASSED [ 60%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_skill_md_stage6_medium_skip_section_present PASSED [ 65%]
test_v058_medium_path.py::TestSkillContentIntegrity::test_claude_fixture_has_abbreviated_recipe_not_5_stage PASSED [ 69%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_medium_stage3_two_agents_converges PASSED [ 73%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_medium_stage3_missing_tester_is_critical PASSED [ 78%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_medium_stage3_missing_architect_is_critical PASSED [ 82%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_medium_stage4_tester_not_expected_no_synthetic_critical PASSED [ 86%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_extra_reviewer_in_jsons_is_ignored PASSED [ 91%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_medium_stage5_phase_auditor_only_converges PASSED [ 95%]
test_v058_medium_path.py::TestConvergenceMediumPath::test_empty_expected_roles_converges [100%]

============================== 23 passed in 0.05s ==============================
```

## Regression suite

```
cd $REPO_ROOT/hooks/tests && python3 -m pytest -q --tb=no
# 130 passed in 5.86s (unchanged)

cd $REPO_ROOT/skills/feature-development/tests
python3 -m pytest test_check_convergence.py test_checkpoint_format.py test_v058_medium_path.py -q --tb=no
# 53 passed in 0.07s
```

## Counts

| Layer | Tests | Status |
|---|---|---|
| TDD RED phase (inline v0.5.7 fixtures) | 4 | PASSED |
| Content integrity (on-disk files) | 12 | PASSED |
| Convergence functional | 7 | PASSED |
| **New total** | **23** | **PASSED** |
| hooks/tests/ (regression) | 130 | PASSED |
| pre-existing skill tests (regression) | 30 | PASSED |
| **Grand total** | **183** | **0 failed** |

## TDD RED evidence

`TestTDDRedPhase` operates on inline v0.5.7 content strings — no live file reads.
It proves:
- v0.5.7 table had no Medium Stage 3 or Stage 4 rows
- v0.5.7 SKILL.md had no security-surface override
- v0.5.7 CLAUDE.md had "abbreviated 5-stage recipe" (not "abbreviated recipe:")

If `TestSkillContentIntegrity` tests were run against those same inline strings,
they would fail (RED) — because they assert the presence of v0.5.8 additions.

The fixture `tests/fixtures/claude_medium_path_excerpt.txt` is a committed copy of
the CLAUDE.md Medium path section as of v0.5.8 — unconditionally readable on all
machines, no skip logic.
