#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))

from env import is_hooks_disabled
from safe import fail_open

MARKER_DIR = os.environ.get("TLMFORGE_MARKER_DIR") or os.path.expanduser("~/.cache/tlmforge")

REMINDER = (
    "Invoke Skill(tlmforge:feature-development) for non-trivial work. "
    "Bypass: 'be quick' / 'just do it' / 'trivial fix'. "
    "Skip if already invoked for current task."
)


@fail_open
def main():
    if is_hooks_disabled():
        print(json.dumps({}))
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Delete session marker on each new user prompt — resets the task window
    # so skill approval from a prior task can't carry into the new one.
    session_id = payload.get("session_id", "")
    if session_id:
        marker = os.path.join(MARKER_DIR, f"skill_invoked_{session_id}")
        try:
            os.remove(marker)
        except FileNotFoundError:
            pass

    print(json.dumps({"systemMessage": REMINDER}))
    sys.exit(0)


if __name__ == "__main__":
    main()
