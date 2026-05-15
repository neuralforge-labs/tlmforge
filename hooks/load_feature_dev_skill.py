#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))

from env import is_hooks_disabled
from safe import fail_open

REMINDER = (
    "Before responding, invoke `Skill(tlmforge:feature-development)`. "
    "The skill's Stage 0 exits cleanly if this isn't a work request; "
    "its classification gate is authoritative for Light vs Deep. "
    "To bypass enforcement on this message, include `be quick`, `just do it`, "
    "or `trivial fix` in your prompt. "
    "(Bare \"minimal\" / \"trivial\" are NOT accepted — they appear too often in technical prose.)"
)


@fail_open
def main():
    if is_hooks_disabled():
        print(json.dumps({}))
        sys.exit(0)

    try:
        json.load(sys.stdin)  # consume stdin; payload not needed for Hook 1
    except (json.JSONDecodeError, ValueError):
        pass  # fail-open handled by @fail_open for unexpected errors;
              # for invalid JSON on a reminder hook, still emit the reminder

    print(json.dumps({"systemMessage": REMINDER}))
    sys.exit(0)


if __name__ == "__main__":
    main()
