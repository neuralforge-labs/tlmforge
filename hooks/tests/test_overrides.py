import pytest
from _lib.overrides import has_override


# --- Positive cases (should trigger override) ---

@pytest.mark.parametrize("msg", [
    "be quick",
    "Be Quick",
    "BE QUICK",
    "just be quick",
    "please be quick about this",
])
def test_be_quick_triggers(msg):
    assert has_override(msg) is True


@pytest.mark.parametrize("msg", [
    "just do it",
    "Just Do It",
    "can you just do it",
    "just do it now",
])
def test_just_do_it_triggers(msg):
    assert has_override(msg) is True


@pytest.mark.parametrize("msg", [
    "trivial fix",
    "Trivial Fix",
    "this is a trivial fix",
    "trivial fix needed",
])
def test_trivial_fix_triggers(msg):
    assert has_override(msg) is True


# --- Negative cases: bare "minimal" and "trivial" must NOT trigger ---

@pytest.mark.parametrize("msg", [
    "minimal",
    "minimal config",
    "use minimal logging",
    "explain why minimal test coverage is bad",
    "add minimal dependencies",
    "keep it minimal",
    "minimal viable version",
])
def test_bare_minimal_does_not_trigger(msg):
    assert has_override(msg) is False


@pytest.mark.parametrize("msg", [
    "trivial",
    "the trivial solution is O(n^2)",
    "trivially false assumption",
    "this is a trivial problem",
    "trivial to implement",
])
def test_bare_trivial_does_not_trigger(msg):
    assert has_override(msg) is False


# --- Other negative cases ---

@pytest.mark.parametrize("msg", [
    "",
    "add a login button",
    "refactor the auth module",
    "fix the bug in payments",
    "explain what this file does",
    "be thorough",
])
def test_non_override_messages(msg):
    assert has_override(msg) is False
