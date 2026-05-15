import sys
import pytest
from _lib.safe import fail_open


def test_normal_function_runs():
    calls = []
    @fail_open
    def fn():
        calls.append(1)
    with pytest.raises(SystemExit) as exc:
        fn()
    assert exc.value.code == 0
    assert calls == [1]


def test_exception_causes_exit_0(capsys):
    @fail_open
    def fn():
        raise ValueError("something broke")
    with pytest.raises(SystemExit) as exc:
        fn()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "tlmforge" in captured.err.lower() or "enforcement" in captured.err.lower() or "error" in captured.err.lower()


def test_system_exit_2_propagates():
    """DENY path: sys.exit(2) must not be swallowed by fail_open."""
    @fail_open
    def fn():
        sys.exit(2)
    with pytest.raises(SystemExit) as exc:
        fn()
    assert exc.value.code == 2


def test_system_exit_0_propagates():
    @fail_open
    def fn():
        sys.exit(0)
    with pytest.raises(SystemExit) as exc:
        fn()
    assert exc.value.code == 0


def test_attribute_error_is_caught(capsys):
    @fail_open
    def fn():
        raise AttributeError("no such attr")
    with pytest.raises(SystemExit) as exc:
        fn()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.err  # warning must go to stderr
