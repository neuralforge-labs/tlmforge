import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def make_transcript(entries):
    """Build a JSONL string from a list of entry dicts."""
    return '\n'.join(json.dumps(e) for e in entries) + '\n'


@pytest.fixture
def user_entry():
    def _make(content="do the task", session_id="test-session"):
        return {
            "type": "user",
            "sessionId": session_id,
            "message": {"role": "user", "content": content},
        }
    return _make


@pytest.fixture
def skill_entry():
    def _make(skill="tlmforge:feature-development"):
        return {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_test",
                        "name": "Skill",
                        "input": {"skill": skill},
                    }
                ],
            },
        }
    return _make


@pytest.fixture
def edit_entry():
    def _make(path="/tmp/x.py"):
        return {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_edit",
                        "name": "Edit",
                        "input": {"file_path": path, "old_string": "a", "new_string": "b"},
                    }
                ],
            },
        }
    return _make


@pytest.fixture
def tmp_transcript(tmp_path):
    """Write a transcript JSONL to a temp file and return its path."""
    def _write(entries):
        path = tmp_path / "transcript.jsonl"
        path.write_text(make_transcript(entries))
        return str(path)
    return _write


def _make_user(content="do something"):
    return {"type": "user", "message": {"role": "user", "content": content}}


@pytest.fixture
def large_transcript_many_short(tmp_path):
    """~1MB transcript with many short lines."""
    entries = []
    target = 1024 * 1024
    size = 0
    while size < target:
        e = _make_user("do something interesting")
        line = json.dumps(e)
        entries.append(e)
        size += len(line) + 1
    path = tmp_path / "large_short.jsonl"
    path.write_text('\n'.join(json.dumps(e) for e in entries) + '\n')
    return str(path)


@pytest.fixture
def large_transcript_few_long(tmp_path):
    """~1MB transcript with a few very long lines."""
    entries = []
    target = 1024 * 1024
    size = 0
    i = 0
    while size < target:
        big_content = "x" * 50000
        e = _make_user(big_content)
        entries.append(e)
        size += len(json.dumps(e)) + 1
        i += 1
        if i > 100:
            break
    path = tmp_path / "large_long.jsonl"
    path.write_text('\n'.join(json.dumps(e) for e in entries) + '\n')
    return str(path)
