import os
import pytest
from _lib.env import is_hooks_disabled


@pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "NO", "off", "OFF", ""])
def test_bypass_accepted_values(value, monkeypatch):
    monkeypatch.setenv("TLMFORGE_HOOKS", value)
    assert is_hooks_disabled() is True


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "enabled", "2"])
def test_no_bypass_for_truthy_values(value, monkeypatch):
    monkeypatch.setenv("TLMFORGE_HOOKS", value)
    assert is_hooks_disabled() is False


def test_var_not_set_means_enabled(monkeypatch):
    monkeypatch.delenv("TLMFORGE_HOOKS", raising=False)
    assert is_hooks_disabled() is False
