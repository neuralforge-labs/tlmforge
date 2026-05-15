#!/usr/bin/env python3
"""
PostToolUse hook — fires after Skill(tlmforge:feature-development) completes.
Writes a per-session marker file so PreToolUse can confirm skill was invoked
without relying on transcript timing (transcript is written per response turn,
not per tool call — reading it mid-turn misses in-progress invocations).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))
from env import is_hooks_disabled
from safe import fail_open

MARKER_DIR = os.environ.get("TLMFORGE_MARKER_DIR") or os.path.expanduser("~/.cache/tlmforge")


def marker_path(session_id: str) -> str:
    return os.path.join(MARKER_DIR, f"skill_invoked_{session_id}")


@fail_open
def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if is_hooks_disabled():
        sys.exit(0)

    skill = payload.get("tool_input", {}).get("skill", "")
    if skill != "tlmforge:feature-development":
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    os.makedirs(MARKER_DIR, exist_ok=True)
    open(marker_path(session_id), "w").close()
    sys.exit(0)


if __name__ == "__main__":
    main()
