# v058-validation — Phase 1 Summary

## What was done

Created `skills/feature-development/tests/test_v058_medium_path.py` (23 tests)
and `skills/feature-development/tests/fixtures/claude_medium_path_excerpt.txt`
(committed fixture replacing the live CLAUDE.md read).

## Tests shipped

**TestTDDRedPhase (4)** — inline v0.5.7 fixture strings prove tests would have
been RED before the fix. Shows the Medium rows were genuinely absent in v0.5.7.

**TestSkillContentIntegrity (12)** — row-scoped regex assertions against actual
on-disk files: Medium rows in reviewer-convergence.md (Stage 3, 4, 5); security-
surface override position in SKILL.md; phase-end Medium annotation; Stage 6 skip
section; committed CLAUDE.md fixture.

**TestConvergenceMediumPath (7)** — functional `evaluate_convergence()` calls:
- Stage 3 two-agent convergence (Green)
- Stage 3 missing tester → meta CRITICAL (verifies tester IS expected)
- Stage 3 missing architect → meta CRITICAL
- Stage 4 v0.5.8 regression guard: `expected_roles=["code-reviewer","phase-auditor"]` → 0 synthetics (the actual fix)
- Extra reviewer in jsons is silently ignored
- Stage 5 phase-auditor-only convergence
- Empty expected_roles converges cleanly

## Reviewer findings addressed

All C1/EC-1 (tautological pre-fix test), H1 (CLAUDE.md skip), H2 (TDD RED),
M1 (unanchored count), M2/EC-2 (vacuous superset test), EC-3 (extra reviewer
ignored), EC-4 (row-scoped assertions), EC-5 (empty expected_roles) resolved.

## Evidence

- 23 new tests: all PASSED
- hooks/tests/ regression: 130 PASSED (unchanged)
- skill tests regression: 30 PASSED (unchanged)
- Grand total: 183 passed, 0 failed
