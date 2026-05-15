#!/usr/bin/env python3
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))

from env import is_hooks_disabled
from overrides import has_override
from transcript import load_transcript_entries, find_last_user_index, skill_invoked_since
from safe import fail_open

MUTATION_TOOLS = {"Edit", "Write", "Bash", "MultiEdit"}

DENY_MSG = (
    "tlmforge: feature-development skill not invoked for this task.\n"
    "Invoke `Skill(tlmforge:feature-development)` to proceed, OR re-prompt\n"
    "with `be quick` / `just do it` / `trivial fix` to override."
)


@fail_open
def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # Malformed stdin — fail open
        print("[tlmforge] Hook 2: malformed stdin, failing open.", file=sys.stderr)
        sys.exit(0)

    if is_hooks_disabled():
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in MUTATION_TOOLS:
        sys.exit(0)

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        # No transcript path — no information available, fail open with warning
        print("[tlmforge] Hook 2: no transcript_path in payload, failing open.", file=sys.stderr)
        sys.exit(0)

    if not os.path.isfile(transcript_path):
        print(
            f"[tlmforge] Hook 2: transcript not found at {transcript_path}, failing open.",
            file=sys.stderr,
        )
        sys.exit(0)

    entries = load_transcript_entries(transcript_path)

    last_user_idx = find_last_user_index(entries)

    if last_user_idx is None:
        # Subagent session — no user messages, pass through (EC-1)
        sys.exit(0)

    # Check override in last user message
    last_user = entries[last_user_idx]
    user_content = last_user.get("message", {}).get("content", "")
    if isinstance(user_content, list):
        # Only join text-type blocks — skip tool_result blocks (carry tool output, not user intent)
        text = " ".join(
            b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
            else ""
            for b in user_content
        )
    else:
        text = str(user_content)

    if has_override(text):
        sys.exit(0)

    # Task window = since last user message
    window_start = last_user_idx + 1

    if skill_invoked_since(entries, since=window_start):
        sys.exit(0)

    # Block
    print(DENY_MSG, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
