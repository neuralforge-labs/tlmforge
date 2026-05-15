import os

_DISABLED_VALUES = {"0", "false", "no", "off", ""}


def is_hooks_disabled() -> bool:
    val = os.environ.get("TLMFORGE_HOOKS")
    if val is None:
        return False
    return val.strip().lower() in _DISABLED_VALUES
