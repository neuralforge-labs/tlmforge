import json
import time
import pytest
from _lib.transcript import (
    load_transcript_entries,
    find_last_user_index,
    skill_invoked_since,
)


# --- Basic parsing ---

def test_empty_transcript(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    entries = load_transcript_entries(str(path))
    assert entries == []


def test_single_entry(tmp_transcript, user_entry):
    path = tmp_transcript([user_entry()])
    entries = load_transcript_entries(path)
    assert len(entries) == 1
    assert entries[0]["type"] == "user"


def test_multiple_entries(tmp_transcript, user_entry, skill_entry):
    path = tmp_transcript([user_entry(), skill_entry(), user_entry()])
    entries = load_transcript_entries(path)
    assert len(entries) == 3


def test_nonexistent_file_returns_empty():
    entries = load_transcript_entries("/nonexistent/transcript.jsonl")
    assert entries == []


def test_partial_write_truncated_line(tmp_path):
    """Truncated last line must be skipped, not raise."""
    good = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "tlmforge:feature-development"}}]}})
    truncated = '{"type": "assistant", "message": {"role": "assi'  # truncated mid-JSON
    path = tmp_path / "partial.jsonl"
    path.write_text(good + '\n' + truncated)
    entries = load_transcript_entries(str(path))
    # Only the complete first line should parse
    assert len(entries) == 1
    assert entries[0]["type"] == "assistant"


def test_blank_lines_skipped(tmp_path):
    path = tmp_path / "blanks.jsonl"
    path.write_text('\n\n{"type": "user", "message": {"role": "user", "content": "hi"}}\n\n')
    entries = load_transcript_entries(str(path))
    assert len(entries) == 1


# --- find_last_user_index ---

def test_find_last_user_index_no_entries():
    assert find_last_user_index([]) is None


def test_find_last_user_index_no_user_entries(skill_entry):
    entries = [skill_entry()]
    assert find_last_user_index(entries) is None


def test_find_last_user_index_single_user(user_entry):
    entries = [user_entry()]
    assert find_last_user_index(entries) == 0


def test_find_last_user_index_multiple_users(user_entry, skill_entry, edit_entry):
    entries = [user_entry(), skill_entry(), edit_entry(), user_entry(), edit_entry()]
    assert find_last_user_index(entries) == 3


# --- skill_invoked_since ---

def test_skill_found_in_window(user_entry, skill_entry, edit_entry):
    entries = [user_entry(), skill_entry(), edit_entry()]
    assert skill_invoked_since(entries, since=1) is True


def test_skill_not_in_window(user_entry, edit_entry):
    entries = [user_entry(), edit_entry()]
    assert skill_invoked_since(entries, since=1) is False


def test_skill_before_window_not_counted(user_entry, skill_entry, edit_entry):
    # skill at index 1, then user at 2, window starts at 3
    entries = [user_entry(), skill_entry(), user_entry(), edit_entry()]
    assert skill_invoked_since(entries, since=3) is False


def test_skill_at_window_start_counted(skill_entry, edit_entry):
    entries = [skill_entry(), edit_entry()]
    assert skill_invoked_since(entries, since=0) is True


def test_no_entries_returns_false():
    assert skill_invoked_since([], since=0) is False


# --- Performance: <50ms p99 on 1MB transcripts ---

def test_perf_many_short_lines(large_transcript_many_short):
    start = time.monotonic()
    entries = load_transcript_entries(large_transcript_many_short)
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 50, f"Took {elapsed_ms:.1f}ms on many-short-lines 1MB transcript"
    assert len(entries) > 0


def test_perf_few_long_lines(large_transcript_few_long):
    start = time.monotonic()
    entries = load_transcript_entries(large_transcript_few_long)
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 50, f"Took {elapsed_ms:.1f}ms on few-long-lines 1MB transcript"
    assert len(entries) > 0
