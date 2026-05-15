import json
from typing import Optional


def load_transcript_entries(path: str) -> list:
    """Load all parseable JSONL entries from the transcript file."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return []

    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip truncated or malformed lines
    return entries


def find_last_user_index(entries: list) -> Optional[int]:
    """Return the index of the last user-type entry, or None."""
    for i in range(len(entries) - 1, -1, -1):
        if entries[i].get("type") == "user":
            return i
    return None


def skill_invoked_since(entries: list, since: int) -> bool:
    """Return True if a Skill(tlmforge:feature-development) call appears at or after `since`."""
    for entry in entries[since:]:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            inp = block.get("input", {})
            if isinstance(inp, dict) and inp.get("skill") == "tlmforge:feature-development":
                return True
    return False
