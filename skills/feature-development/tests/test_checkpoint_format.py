"""
Tests for the phase-end reviewer checkpoint format.

Validates that checkpoint files written by agents have the required sections
and that the skip-list / changed-this-phase distinction is correct.
Uses the toy-feature fixture (two phases, one reviewer) as the reference.
"""
import os
import re
import pytest

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "toy-feature")
CHECKPOINTS = os.path.join(FIXTURES, "agent-checkpoints")
SPECS = os.path.join(FIXTURES, "specs")

# "Next phase scope" is optional on the final phase — agent may omit it
REQUIRED_SECTIONS = [
    "format_version",
    "Skip list",
    "Changed this phase",
    "Patterns established",
    "Running concerns",
]
OPTIONAL_SECTIONS = ["Next phase scope"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Checkpoint structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_has_required_sections(phase):
    path = os.path.join(CHECKPOINTS, f"code-reviewer-phase-{phase}.md")
    content = load(path)
    for section in REQUIRED_SECTIONS:
        assert section in content, f"Phase {phase} checkpoint missing: '{section}'"


@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_has_format_version_1(phase):
    path = os.path.join(CHECKPOINTS, f"code-reviewer-phase-{phase}.md")
    assert "format_version: 1" in load(path)


@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_header_names_phase(phase):
    path = os.path.join(CHECKPOINTS, f"code-reviewer-phase-{phase}.md")
    first_line = load(path).splitlines()[0]
    assert f"Phase {phase}" in first_line


# ---------------------------------------------------------------------------
# Skip-list rule: files in skip list must not appear as modified in evidence
# ---------------------------------------------------------------------------

def _skip_list_files(checkpoint_content):
    """Extract file paths from the '## Skip list' section."""
    section = re.search(
        r"## Skip list.*?\n(.*?)(?=\n##|\Z)", checkpoint_content, re.DOTALL
    )
    if not section:
        return []
    return re.findall(r"`([^`]+)`", section.group(1))


def _modified_files(evidence_content):
    """Extract file paths from the '## Modified files' section."""
    section = re.search(
        r"## Modified files.*?\n(.*?)(?=\n##|\Z)", evidence_content, re.DOTALL
    )
    if not section:
        return []
    return re.findall(r"`([^`]+)`", section.group(1))


def test_phase2_skip_list_files_not_in_phase2_modified():
    """Files the Phase 1 checkpoint says to skip must not appear as modified in Phase 2 evidence."""
    checkpoint = load(os.path.join(CHECKPOINTS, "code-reviewer-phase-1.md"))
    evidence = load(os.path.join(SPECS, "phase-2-evidence.md"))
    skip_files = _skip_list_files(checkpoint)
    modified_files = _modified_files(evidence)
    assert skip_files, "Phase 1 checkpoint skip list should not be empty"
    for f in skip_files:
        assert f not in modified_files, (
            f"'{f}' is in Phase 1 skip list but marked as modified in Phase 2 evidence — "
            "agent should have re-read it, not skipped"
        )


def test_phase1_new_files_appear_in_phase1_changed_section():
    """Files introduced in Phase 1 should be listed under 'Changed this phase'."""
    checkpoint = load(os.path.join(CHECKPOINTS, "code-reviewer-phase-1.md"))
    section = re.search(
        r"## Changed this phase.*?\n(.*?)(?=\n##|\Z)", checkpoint, re.DOTALL
    )
    assert section, "Missing 'Changed this phase' section"
    changed = section.group(1)
    assert "greeter.py" in changed
    assert "test_greeter.py" in changed


def test_running_concerns_carried_forward():
    """A concern raised in Phase 1 checkpoint should be traceable in Phase 2 checkpoint."""
    phase1 = load(os.path.join(CHECKPOINTS, "code-reviewer-phase-1.md"))
    phase2 = load(os.path.join(CHECKPOINTS, "code-reviewer-phase-2.md"))
    # Phase 1 flagged the str annotation gap — phase 2 should mention it
    assert "annotation" in phase1.lower() or "str" in phase1
    # Phase 2 reviewer should have seen and addressed it
    assert "annotation" in phase2.lower() or "Optional" in phase2 or "str" in phase2


# ---------------------------------------------------------------------------
# Evidence file structure (sanity checks for the fixture itself)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase,expected_new", [
    (1, ["src/greeter.py", "tests/test_greeter.py"]),
    (2, ["src/formatter.py", "tests/test_formatter.py"]),
])
def test_evidence_lists_new_files(phase, expected_new):
    evidence = load(os.path.join(SPECS, f"phase-{phase}-evidence.md"))
    for f in expected_new:
        assert f in evidence, f"Phase {phase} evidence missing expected new file: {f}"
