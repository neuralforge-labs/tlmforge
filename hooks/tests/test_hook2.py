import json
import os
import subprocess
import sys
import pytest

HOOK2 = os.path.join(os.path.dirname(__file__), '..', 'enforce_skill_invoked.py')


def run_hook2(payload: dict, env_extra: dict = None, transcript_entries: list = None,
              transcript_path: str = None) -> tuple[int, str]:
    """Run hook2. Returns (returncode, stderr)."""
    env = os.environ.copy()
    env.pop("TLMFORGE_HOOKS", None)
    if env_extra:
        env.update(env_extra)

    if transcript_entries is not None and transcript_path is None:
        import tempfile
        lines = '\n'.join(json.dumps(e) for e in transcript_entries) + '\n'
        tf = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        tf.write(lines)
        tf.flush()
        payload["transcript_path"] = tf.name
        tf.close()

    result = subprocess.run(
        [sys.executable, HOOK2],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stderr


def make_payload(tool_name="Edit", cmd=None):
    p = {"session_id": "test-session", "tool_name": tool_name, "tool_input": {}}
    if cmd:
        p["tool_input"]["command"] = cmd
    return p


def user_entry(content="do the task"):
    return {"type": "user", "message": {"role": "user", "content": content}}


def skill_entry():
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "tlmforge:feature-development"}}
    ]}}


# --- Allow cases ---

def test_skill_in_task_window_allows(tmp_path):
    entries = [user_entry(), skill_entry()]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_override_be_quick_allows(tmp_path):
    entries = [user_entry("be quick add a button")]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_override_just_do_it_allows(tmp_path):
    entries = [user_entry("just do it")]
    payload = make_payload("Write")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_override_trivial_fix_allows(tmp_path):
    entries = [user_entry("trivial fix the typo")]
    payload = make_payload("Bash")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_read_tool_not_checked(tmp_path):
    """Read is not a mutating tool — always pass through."""
    entries = [user_entry()]  # no skill, no override
    payload = make_payload("Read")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_non_mutation_agent_tool_allowed(tmp_path):
    """Agent tool not in mutation set — pass through."""
    entries = [user_entry()]
    payload = make_payload("Agent")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


def test_bypass_tlmforge_hooks_0(tmp_path):
    entries = [user_entry()]  # no skill, no override
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries, env_extra={"TLMFORGE_HOOKS": "0"})
    assert rc == 0


def test_bypass_tlmforge_hooks_false(tmp_path):
    entries = [user_entry()]
    payload = make_payload("Write")
    rc, _ = run_hook2(payload, transcript_entries=entries, env_extra={"TLMFORGE_HOOKS": "false"})
    assert rc == 0


def test_subagent_no_user_messages_allows(tmp_path):
    """EC-1: transcript with no user entries → pass-through (subagent session)."""
    entries = [skill_entry(), {"type": "assistant", "message": {"content": []}}]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 0


# --- Deny cases ---

def test_no_skill_no_override_denies(tmp_path):
    entries = [user_entry("add a login button")]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 2


def test_bash_mutation_without_skill_denies(tmp_path):
    entries = [user_entry("add a login button")]
    payload = make_payload("Bash", cmd="echo hello")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 2


def test_skill_in_old_task_window_denies(tmp_path):
    """Skill in first task window must not count for second task window."""
    entries = [
        user_entry("first task"),  # idx 0
        skill_entry(),              # idx 1 (in window 1)
        user_entry("second task"), # idx 2 — new task starts, skill not re-invoked
    ]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 2


def test_bare_minimal_does_not_override_denies(tmp_path):
    """Bare 'minimal' must not bypass the gate."""
    entries = [user_entry("make minimal changes")]
    payload = make_payload("Edit")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 2


def test_bare_trivial_does_not_override_denies(tmp_path):
    entries = [user_entry("the trivial solution")]
    payload = make_payload("Write")
    rc, _ = run_hook2(payload, transcript_entries=entries)
    assert rc == 2


def test_deny_message_is_actionable(tmp_path):
    """Block message must mention how to proceed."""
    entries = [user_entry("add encryption")]
    payload = make_payload("Edit")
    rc, stderr = run_hook2(payload, transcript_entries=entries)
    assert rc == 2
    assert "Skill" in stderr or "feature-development" in stderr
    assert "be quick" in stderr or "override" in stderr.lower()


# --- Fail-open ---

def test_bad_transcript_path_fails_open():
    payload = make_payload("Edit")
    payload["transcript_path"] = "/nonexistent/transcript.jsonl"
    rc, stderr = run_hook2(payload)
    assert rc == 0  # fail open
    assert stderr  # must warn


def test_missing_transcript_path_key_fails_open():
    """No transcript_path key in stdin at all → fall back gracefully."""
    payload = {"session_id": "s1", "tool_name": "Edit", "tool_input": {}}
    rc, stderr = run_hook2(payload)
    assert rc == 0  # fail open — no transcript info available
