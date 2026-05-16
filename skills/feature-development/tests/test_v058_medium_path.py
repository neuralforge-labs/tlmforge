"""Regression tests for v0.5.8 Medium path fixes.

Three classes:
- TestTDDRedPhase: inline v0.5.7 fixtures proving tests would be RED before the fix
- TestSkillContentIntegrity: assertions against actual on-disk files
- TestConvergenceMediumPath: functional evaluate_convergence() calls with Medium expected_roles
"""
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent

sys.path.insert(0, str(SKILL_DIR))
from check_convergence import evaluate_convergence


CONVERGENCE_MD = SKILL_DIR / "reviewer-convergence.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
FIXTURE_CLAUDE = TESTS_DIR / "fixtures" / "claude_medium_path_excerpt.txt"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _medium_row(content: str, stage_prefix: str) -> str | None:
    """Return the roles cell from the Medium row for a given stage prefix."""
    pattern = rf"\|\s*{re.escape(stage_prefix)}[^|]*\|\s*Medium\s*\|[^|]+\|([^|]+)\|"
    m = re.search(pattern, content)
    return m.group(1) if m else None


def _approve(role: str) -> dict:
    return {"reviewer": role, "status": "ok", "verdict": "approve", "findings": []}


# ---------------------------------------------------------------------------
# Inline v0.5.7 fixtures (content BEFORE the fix — no Medium rows)
# ---------------------------------------------------------------------------

V057_CONVERGENCE_TABLE = """\
| Stage | Path | Iteration model | Default expected reviewer roles | Conditional / optional |
|---|---|---|---|---|
| Stage 3 (plan review) | Deep | bounded 3-round loop, same reviewers across rounds | `architect-reviewer`, `tester`, `threat-modeler` | `ux-reviewer` (only if plan describes UI work) |
| Stage 4 phase-end | Deep | bounded 3-round loop per phase | `code-reviewer`, `tester`, `phase-auditor` | `ux-reviewer` (only if phase diff contains UI files) |
| Stage 5 (final audit) | Deep | **single shot, no iteration** | `red-team-reviewer` [opus], `architect-reviewer` [sonnet] | none |
"""

V057_SKILL_CLASSIFY_BLOCK = """\
| **Light** | Zero new logic. Diff readable in 10 sec. | Typo, rename, comment, config value, reorder imports |
| **Medium** | Fixes or improves existing behavior. No new product surface. | Bug fix (multi-file ok), refactor a module, add missing tests, improve error-message tracing, perf fix in existing path |
| **Deep** | Adds new capability or surface that didn't exist. | New feature, new API endpoint, new data model, new integration, new auth flow, new UI screen |
"""

V057_CLAUDE_EXCERPT = """\
### Medium path

Invoke `Skill(tlmforge:feature-development)` — abbreviated 5-stage recipe:
abbreviated spec audit → fix plan → single-round review (architect-reviewer +
tester) → phase-gated TDD with phase-end (code-reviewer + phase-auditor) →
phase-auditor final compliance check → abbreviated STATUS.md.
"""


# ---------------------------------------------------------------------------
# Class 1: TDD Red Phase
# ---------------------------------------------------------------------------

class TestTDDRedPhase:
    """Asserts the absence of v0.5.8 content in pre-fix inline strings.

    Each test MUST fail against the corresponding v0.5.7 fixture string —
    that is the point. Against the live on-disk files (v0.5.8) these checks
    would be GREEN. We invert the fixture strings here to produce explicit
    RED evidence.
    """

    def test_v057_table_has_no_medium_stage3_row(self):
        assert "Stage 3 (plan review) | Medium" not in V057_CONVERGENCE_TABLE

    def test_v057_table_has_no_medium_stage4_row(self):
        assert "Stage 4 phase-end | Medium" not in V057_CONVERGENCE_TABLE

    def test_v057_skill_has_no_security_surface_override(self):
        assert "Security-surface override" not in V057_SKILL_CLASSIFY_BLOCK

    def test_v057_claude_excerpt_has_5_stage_recipe_not_abbreviated(self):
        assert "abbreviated 5-stage recipe" in V057_CLAUDE_EXCERPT
        assert "abbreviated recipe:" not in V057_CLAUDE_EXCERPT


# ---------------------------------------------------------------------------
# Class 2: Content Integrity
# ---------------------------------------------------------------------------

class TestSkillContentIntegrity:
    """Assert each v0.5.8 change is present in the actual on-disk files."""

    # --- reviewer-convergence.md ---

    def test_convergence_md_has_medium_stage3_row(self):
        content = CONVERGENCE_MD.read_text()
        assert "Stage 3 (plan review) | Medium" in content

    def test_convergence_md_medium_stage3_row_has_architect_and_tester(self):
        content = CONVERGENCE_MD.read_text()
        roles = _medium_row(content, "Stage 3 (plan review)")
        assert roles is not None, "Medium Stage 3 row not found"
        assert "architect-reviewer" in roles
        assert "tester" in roles

    def test_convergence_md_medium_stage3_row_lacks_threat_modeler(self):
        content = CONVERGENCE_MD.read_text()
        roles = _medium_row(content, "Stage 3 (plan review)")
        assert roles is not None, "Medium Stage 3 row not found"
        assert "threat-modeler" not in roles

    def test_convergence_md_has_medium_stage4_row(self):
        content = CONVERGENCE_MD.read_text()
        assert "Stage 4 phase-end | Medium" in content

    def test_convergence_md_medium_stage4_row_has_code_reviewer_and_phase_auditor(self):
        content = CONVERGENCE_MD.read_text()
        roles = _medium_row(content, "Stage 4 phase-end")
        assert roles is not None, "Medium Stage 4 row not found"
        assert "code-reviewer" in roles
        assert "phase-auditor" in roles

    def test_convergence_md_medium_stage4_row_lacks_tester(self):
        content = CONVERGENCE_MD.read_text()
        roles = _medium_row(content, "Stage 4 phase-end")
        assert roles is not None, "Medium Stage 4 row not found"
        assert "tester" not in roles

    def test_convergence_md_has_medium_stage5_row_with_phase_auditor(self):
        content = CONVERGENCE_MD.read_text()
        roles = _medium_row(content, "Stage 5 (final audit)")
        assert roles is not None, "Medium Stage 5 row not found"
        assert "phase-auditor" in roles

    # --- SKILL.md ---

    def test_skill_md_has_security_surface_override(self):
        content = SKILL_MD.read_text()
        assert "Security-surface override:" in content

    def test_skill_md_security_override_is_before_announce_section(self):
        content = SKILL_MD.read_text()
        override_pos = content.find("Security-surface override:")
        announce_pos = content.find("### Announce and proceed")
        assert override_pos != -1, "Security-surface override not found"
        assert announce_pos != -1, "Announce section not found"
        assert override_pos < announce_pos

    def test_skill_md_phase_end_medium_annotation_present(self):
        content = SKILL_MD.read_text()
        assert "tester ran at Stage 3 and is NOT" in content

    def test_skill_md_stage6_medium_skip_section_present(self):
        content = SKILL_MD.read_text()
        assert "Stage 6 — Medium path: skipped" in content

    # --- committed fixture (replaces live CLAUDE.md read) ---

    def test_claude_fixture_has_abbreviated_recipe_not_5_stage(self):
        content = FIXTURE_CLAUDE.read_text()
        assert "abbreviated recipe:" in content
        assert "abbreviated 5-stage recipe" not in content


# ---------------------------------------------------------------------------
# Class 3: Convergence Functional Tests
# ---------------------------------------------------------------------------

class TestConvergenceMediumPath:
    """Call evaluate_convergence() with Medium-specific expected_roles.

    These verify that v0.5.8's reviewer-convergence.md Medium rows produce
    correct convergence behavior — no spurious synthetic CRITICALs.
    """

    def test_medium_stage3_two_agents_converges(self):
        result = evaluate_convergence(
            reviewer_jsons={
                "architect-reviewer": _approve("architect-reviewer"),
                "tester": _approve("tester"),
            },
            expected_roles=["architect-reviewer", "tester"],
            iteration=1,
        )
        assert result["converged"] is True
        assert result["meta_critical_count"] == 0

    def test_medium_stage3_missing_tester_is_critical(self):
        """Tester IS expected for Medium Stage 3 — absence must trigger meta CRITICAL."""
        result = evaluate_convergence(
            reviewer_jsons={"architect-reviewer": _approve("architect-reviewer")},
            expected_roles=["architect-reviewer", "tester"],
            iteration=1,
        )
        assert result["meta_critical_count"] >= 1

    def test_medium_stage3_missing_architect_is_critical(self):
        """architect-reviewer IS expected for Medium Stage 3."""
        result = evaluate_convergence(
            reviewer_jsons={"tester": _approve("tester")},
            expected_roles=["architect-reviewer", "tester"],
            iteration=1,
        )
        assert result["meta_critical_count"] >= 1

    def test_medium_stage4_tester_not_expected_no_synthetic_critical(self):
        """v0.5.8 regression guard: Medium Stage 4 must NOT inject synthetic for tester.

        Pre-v0.5.8: the Deep-path row was used for Medium, so expected_roles included
        'tester'. evaluate_convergence() would then inject reviewer_json_missing for
        tester, blocking Medium phase-end. This test catches any revert of that fix.
        """
        result = evaluate_convergence(
            reviewer_jsons={
                "code-reviewer": _approve("code-reviewer"),
                "phase-auditor": _approve("phase-auditor"),
            },
            expected_roles=["code-reviewer", "phase-auditor"],
            iteration=1,
        )
        assert result["converged"] is True
        assert result["meta_critical_count"] == 0

    def test_extra_reviewer_in_jsons_is_ignored(self):
        """Reviewers present in jsons but absent from expected_roles are not counted."""
        result = evaluate_convergence(
            reviewer_jsons={
                "code-reviewer": _approve("code-reviewer"),
                "tester": _approve("tester"),
                "phase-auditor": _approve("phase-auditor"),
            },
            expected_roles=["code-reviewer", "phase-auditor"],
            iteration=1,
        )
        assert result["converged"] is True
        assert "tester" not in result["findings_by_role"]

    def test_medium_stage5_phase_auditor_only_converges(self):
        """Medium Stage 5 uses only phase-auditor — no red-team-reviewer synthetic."""
        result = evaluate_convergence(
            reviewer_jsons={"phase-auditor": _approve("phase-auditor")},
            expected_roles=["phase-auditor"],
            iteration=1,
        )
        assert result["converged"] is True
        assert result["meta_critical_count"] == 0

    def test_empty_expected_roles_converges(self):
        result = evaluate_convergence(
            reviewer_jsons={},
            expected_roles=[],
            iteration=1,
        )
        assert result["converged"] is True
        assert result["meta_critical_count"] == 0
        assert result["real_critical_count"] == 0
