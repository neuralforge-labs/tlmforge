# v0.5.8 Validation — Spec Audit (Medium)

## What broke / what needs to change

v0.5.8 shipped 8 content changes to SKILL.md, reviewer-convergence.md, and ~/.claude/CLAUDE.md
fixing the Medium path. No automated tests guard those changes — an accidental revert would be
silent. Additionally, the root failure mode (Medium runs injecting synthetic `reviewer_json_missing`
CRITICALs because reviewer-convergence.md only had Deep-path rows) needs a functional regression
test, not just a content assertion.

## Fix approach

Two test layers:
1. **Content integrity tests** — assert each v0.5.8 change is present in the actual files on disk.
   Acts as a regression guard: if anyone reverts a change, the test goes RED.
2. **Functional convergence tests** — call `evaluate_convergence()` directly with Medium-specific
   `expected_roles` (the values the v0.5.8 table now documents). Verify no synthetic CRITICALs
   are injected. Also pin the pre-fix bug behavior to document what was wrong.

Alternative considered: test against the convergence table by parsing it. Rejected — fragile.
Testing `evaluate_convergence()` directly is cleaner and more meaningful.

## Files in scope

- `skills/feature-development/tests/test_v058_medium_path.py` — new test file (2 test classes)

## Rollback

Delete `test_v058_medium_path.py`. Zero risk to existing functionality.

## Test plan

- `TestSkillContentIntegrity` — 15 assertions across SKILL.md, reviewer-convergence.md,
  and ~/.claude/CLAUDE.md verifying each v0.5.8 change is present
- `TestConvergenceMediumPath` — 6 `evaluate_convergence()` calls verifying Medium path
  expected_roles produce correct convergence behavior (no spurious CRITICALs)

## Open questions

[INFORMATIONAL] The tests read ~/.claude/CLAUDE.md which is outside the repo. Tests skip
gracefully if that file is absent — no action needed.
