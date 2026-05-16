# v0.5.8 Validation — Fix Plan (Medium)

## Context

v0.5.8 shipped 8 content changes (3 CRITICALs + 5 other fixes) to the Medium path.
No automated test guards them. This plan adds `test_v058_medium_path.py` alongside
the existing `test_checkpoint_format.py` and `test_check_convergence.py` to close that gap.

## Scope

**In:** `skills/feature-development/tests/test_v058_medium_path.py` (new file)
**Out:** No changes to existing tests, SKILL.md, or any hook.

## Phases

### Phase 1 — validation test suite

**Goal:** Write and run `test_v058_medium_path.py` with two test classes.

**Steps:**
1. Write failing tests first (pre-confirm RED against inline fixtures that simulate v0.5.7 state)
2. Run against actual files → confirm GREEN for all content tests
3. Confirm functional convergence tests are GREEN

**Files modified:**
- `skills/feature-development/tests/test_v058_medium_path.py` (new)

**Tests added (21 total):**

`TestSkillContentIntegrity` (15 tests):
- reviewer-convergence.md has Medium rows for Stage 3, 4, 5
- Stage 3 Medium row: has architect-reviewer + tester, lacks threat-modeler
- Stage 4 Medium row: has code-reviewer + phase-auditor, lacks tester (as Agent call)
- Stage 5 Medium row: has phase-auditor, lacks red-team-reviewer
- SKILL.md §4.3: Medium variant present, references round-1-tester.md prose
- SKILL.md §4.3: Deep variant still references tester_edge_cases.json
- Phase-end Step 4: Medium annotation present, says tester is NOT launched
- Stage 6: "Stage 6 — Medium path: skipped" section present
- Stage 6: Medium skip block references Stage 7
- Medium at-a-glance: Stage 7 present, Stage 6 absent from diagram
- Security-surface override: present in SKILL.md, forces Deep, covers auth+PII
- Security-surface override: is between table and Announce section
- Medium checklist: has round-2 conditional items
- Minimal checklist: no "Stop hooks" reference
- CLAUDE.md: has "abbreviated recipe", not "5-stage recipe"

`TestConvergenceMediumPath` (6 tests):
- Medium Stage 3 with 2 agents converges correctly (no synthetic for threat-modeler)
- Medium Stage 3 missing tester → meta CRITICAL (tester IS expected for Medium Stage 3)
- Medium Stage 4 phase-end with code-reviewer + phase-auditor converges (no synthetic for tester)
- Medium Stage 4 with all 3 Deep agents → still converges (superset of expected)
- Medium Stage 5 with phase-auditor only → converges (no synthetic for red-team)
- Pre-fix bug pinned: if threat-modeler is listed in expected_roles for Medium Stage 3, but absent → meta CRITICAL

**Rollback:** Delete the file.

## TDD plan

- Write `TestSkillContentIntegrity` first, verify all 15 tests are GREEN (files already patched)
- Write `TestConvergenceMediumPath` → some are trivially GREEN, but the pre-fix bug pin test
  proves the tests are meaningful (shows what would have failed before v0.5.8)

## Verification criteria

- `python3 -m pytest skills/feature-development/tests/test_v058_medium_path.py -v` → 21 passed
- `python3 -m pytest hooks/tests/ skills/feature-development/tests/ -v` → 151+ passed, 0 failed
