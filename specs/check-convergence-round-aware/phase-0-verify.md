# Phase 0 — Verification Plan (committed BEFORE running)

## Pre-flight
| Check | Command | Pass criteria |
|---|---|---|
| Test file structure | `ls tlmforge/skills/feature-development/tests/` | `__init__.py` + `test_check_convergence.py` exist |
| No pre-existing test contamination | `find tlmforge -name "test_check_convergence.py" -not -path "*/tests/*"` | 0 matches |

## Post-implementation
| Check | Command | Pass criteria |
|---|---|---|
| New tests pass | `python3 -m pytest tlmforge/skills/feature-development/tests/ -v` | All ~17 tests GREEN |
| Test count meets floor | `python3 -m pytest tlmforge/skills/feature-development/tests/ --collect-only -q \| tail -3` | ≥ 17 tests collected |
| Boundary pins exist | `grep -c "test_cap_hit_iteration_eq_max" tlmforge/skills/feature-development/tests/test_check_convergence.py` | ≥ 2 (one for each function) |
| Each test has a docstring | `grep -B1 "def test_" tlmforge/skills/feature-development/tests/test_check_convergence.py \| grep -c '"""'` | ≥ 17 (one docstring per test) |
| No skips / xfail | `grep -E "pytest.skip\|@pytest.mark.skip\|@pytest.mark.xfail" tlmforge/skills/feature-development/tests/test_check_convergence.py` | 0 matches |
| Existing files unchanged | `git diff HEAD~1..HEAD tlmforge/skills/feature-development/check_convergence.py` (after commit) | empty (Phase 0 adds tests only — no source mod) |

## Reproducibility
After commit, a reviewer can reproduce by:
1. `git checkout <phase-0-commit-SHA>`
2. `python3 -m pytest tlmforge/skills/feature-development/tests/ -v`
3. Expect ~17 tests passing in <2s
