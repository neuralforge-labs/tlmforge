"""
Tests for the phase-end reviewer checkpoint format.

All fixtures are generated programmatically — no pre-written agent output.
Every run is self-contained and idempotent.
"""
import os
import re
import pytest

# ---------------------------------------------------------------------------
# Canonical checkpoint content (what a well-formed checkpoint looks like)
# ---------------------------------------------------------------------------

PHASE1_CHECKPOINT = """\
# code-reviewer checkpoint — Phase 1 — format_version: 1

## Skip list (do NOT re-read unless in future evidence as modified)
- `src/greeter.py` — greet(name) handles None/empty via `if not name:`
- `tests/test_greeter.py` — 3 unit tests; assert on return value

## Changed this phase
- `src/greeter.py` (new)
- `tests/test_greeter.py` (new)

## Patterns established
- Python stdlib only, no third-party imports
- pytest with direct function calls, no fixtures

## Running concerns
- type annotation gap: `name: str` but None is a valid/tested input

## Next phase scope (from spec)
- Files expected: src/formatter.py, tests/test_formatter.py
"""

PHASE2_CHECKPOINT = """\
# code-reviewer checkpoint — Phase 2 — format_version: 1

## Skip list (do NOT re-read unless in future evidence as modified)
- `src/greeter.py` — unchanged from Phase 1; annotation gap still open
- `tests/test_greeter.py` — unchanged from Phase 1
- `src/formatter.py` — format_greeting(name, style) wraps greet(); three branches
- `tests/test_formatter.py` — 3 unit tests; assert on exact strings

## Changed this phase
- `src/formatter.py` (new)
- `tests/test_formatter.py` (new)

## Patterns established
- Layered delegation: formatter wraps greeter without duplicating guards

## Running concerns
- annotation gap from Phase 1 propagates into formatter.py (Optional[str] fix deferred)
- unknown style values fall through silently to title — undocumented behaviour
"""

PHASE1_EVIDENCE = """\
# Phase 1 Evidence

## New files
- `src/greeter.py`
- `tests/test_greeter.py`

## Modified files
(none)

## Test run
3 passed in 0.12s
"""

PHASE2_EVIDENCE = """\
# Phase 2 Evidence

## New files
- `src/formatter.py`
- `tests/test_formatter.py`

## Modified files
(none — src/greeter.py and tests/test_greeter.py unchanged)

## Test run
6 passed in 0.14s
"""

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def feature_dir(tmp_path):
    checkpoints = tmp_path / "agent-checkpoints"
    checkpoints.mkdir()
    specs = tmp_path / "specs"
    specs.mkdir()

    (checkpoints / "code-reviewer-phase-1.md").write_text(PHASE1_CHECKPOINT)
    (checkpoints / "code-reviewer-phase-2.md").write_text(PHASE2_CHECKPOINT)
    (specs / "phase-1-evidence.md").write_text(PHASE1_EVIDENCE)
    (specs / "phase-2-evidence.md").write_text(PHASE2_EVIDENCE)

    return tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section(content, heading):
    """Extract text under a ## heading, up to the next ## or end of file."""
    m = re.search(rf"## {re.escape(heading)}.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    return m.group(1) if m else ""


def _files_in_section(content, heading):
    """Extract file paths (contain / or .) from backtick-quoted items in a section."""
    raw = re.findall(r"`([^`]+)`", _section(content, heading))
    return [s for s in raw if "/" in s or (s.count(".") == 1 and " " not in s)]


# ---------------------------------------------------------------------------
# Structure: required sections present
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "format_version",
    "Skip list",
    "Changed this phase",
    "Patterns established",
    "Running concerns",
]

@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_has_required_sections(feature_dir, phase):
    path = feature_dir / "agent-checkpoints" / f"code-reviewer-phase-{phase}.md"
    content = path.read_text()
    for section in REQUIRED_SECTIONS:
        assert section in content, f"Phase {phase} checkpoint missing: '{section}'"


@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_has_format_version_1(feature_dir, phase):
    path = feature_dir / "agent-checkpoints" / f"code-reviewer-phase-{phase}.md"
    assert "format_version: 1" in path.read_text()


@pytest.mark.parametrize("phase", [1, 2])
def test_checkpoint_header_names_phase(feature_dir, phase):
    path = feature_dir / "agent-checkpoints" / f"code-reviewer-phase-{phase}.md"
    first_line = path.read_text().splitlines()[0]
    assert f"Phase {phase}" in first_line


def test_final_phase_checkpoint_may_omit_next_scope(feature_dir):
    """'Next phase scope' is optional on the last phase."""
    content = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-2.md").read_text()
    # No assertion that it IS present — just that the absence doesn't break anything.
    # The test documents the design decision.
    assert "format_version: 1" in content  # still a valid checkpoint


# ---------------------------------------------------------------------------
# Skip-list rule: skip-list files must not appear as modified in next phase
# ---------------------------------------------------------------------------

def test_phase1_skip_list_files_not_modified_in_phase2(feature_dir):
    phase1_ckpt = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-1.md").read_text()
    phase2_evid = (feature_dir / "specs" / "phase-2-evidence.md").read_text()

    skip_files = _files_in_section(phase1_ckpt, "Skip list")
    modified_files = _files_in_section(phase2_evid, "Modified files")

    assert skip_files, "Phase 1 skip list must not be empty"
    for f in skip_files:
        assert f not in modified_files, (
            f"'{f}' is in Phase 1 skip list but marked modified in Phase 2 evidence — "
            "agent should re-read it, not skip"
        )


def test_phase2_skip_list_grows_to_include_phase1_files(feature_dir):
    """Phase 2 skip list must include Phase 1 files (they're still known, still skippable)."""
    phase1_ckpt = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-1.md").read_text()
    phase2_ckpt = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-2.md").read_text()

    phase1_skip = _files_in_section(phase1_ckpt, "Skip list")
    phase2_skip = _files_in_section(phase2_ckpt, "Skip list")

    for f in phase1_skip:
        assert f in phase2_skip, (
            f"'{f}' was in Phase 1 skip list but missing from Phase 2 skip list — "
            "unchanged files should carry forward"
        )


# ---------------------------------------------------------------------------
# Changed-this-phase: new files must appear there
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase,expected", [
    (1, ["src/greeter.py", "tests/test_greeter.py"]),
    (2, ["src/formatter.py", "tests/test_formatter.py"]),
])
def test_changed_section_includes_phase_new_files(feature_dir, phase, expected):
    path = feature_dir / "agent-checkpoints" / f"code-reviewer-phase-{phase}.md"
    content = path.read_text()
    changed = _section(content, "Changed this phase")
    for f in expected:
        assert f in changed, f"Phase {phase} 'Changed this phase' missing: {f}"


# ---------------------------------------------------------------------------
# Running concerns: must carry forward
# ---------------------------------------------------------------------------

def test_phase1_concern_appears_in_phase2(feature_dir):
    """A concern raised in Phase 1 must be visible in Phase 2's running concerns."""
    phase1 = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-1.md").read_text()
    phase2 = (feature_dir / "agent-checkpoints" / "code-reviewer-phase-2.md").read_text()

    phase1_concerns = _section(phase1, "Running concerns")
    phase2_concerns = _section(phase2, "Running concerns")

    assert phase1_concerns.strip(), "Phase 1 must have at least one running concern for this test"
    # Extract the first meaningful keyword from phase 1's concern and check it appears in phase 2
    keywords = re.findall(r"\b\w{5,}\b", phase1_concerns)
    assert keywords, "Could not extract keywords from Phase 1 concerns"
    # At least one keyword from the Phase 1 concern should appear somewhere in Phase 2
    assert any(kw.lower() in phase2.lower() for kw in keywords[:5]), (
        "No keyword from Phase 1 running concerns found in Phase 2 checkpoint — "
        "concerns should be carried forward"
    )
