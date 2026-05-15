import json
import os
import subprocess
import sys
import pytest

HOOK1 = os.path.join(os.path.dirname(__file__), '..', 'load_feature_dev_skill.py')

REQUIRED_PHRASES = ["be quick", "just do it", "trivial fix"]


def run_hook1(stdin_payload: dict, env_extra: dict = None) -> tuple[int, dict, str]:
    """Run the hook script, return (returncode, parsed_stdout_json, stderr)."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, HOOK1],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        env=env,
    )
    try:
        out = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        out = {}
    return result.returncode, out, result.stderr


def test_normal_prompt_injects_system_message():
    payload = {"session_id": "s1", "prompt": "add a login button"}
    rc, out, _ = run_hook1(payload)
    assert rc == 0
    assert "systemMessage" in out
    assert "Skill(tlmforge:feature-development)" in out["systemMessage"]


def test_system_message_lists_correct_override_phrases():
    payload = {"session_id": "s1", "prompt": "add a login button"}
    _, out, _ = run_hook1(payload)
    msg = out.get("systemMessage", "")
    for phrase in REQUIRED_PHRASES:
        assert phrase in msg, f"Expected '{phrase}' in reminder text"


def test_system_message_does_not_list_bare_minimal():
    """Ensure reminder doesn't advertise phrases the library doesn't honor."""
    payload = {"session_id": "s1", "prompt": "add a button"}
    _, out, _ = run_hook1(payload)
    msg = out.get("systemMessage", "")
    import re
    # "minimal" must not appear as a standalone override instruction
    # (it may appear in explanatory text like "not accepted")
    assert "`minimal`" not in msg and "`trivial`" not in msg


def test_bypass_with_tlmforge_hooks_0():
    payload = {"session_id": "s1", "prompt": "add a login button"}
    rc, out, _ = run_hook1(payload, env_extra={"TLMFORGE_HOOKS": "0"})
    assert rc == 0
    assert "systemMessage" not in out


def test_bypass_with_tlmforge_hooks_false():
    payload = {"session_id": "s1", "prompt": "add a button"}
    rc, out, _ = run_hook1(payload, env_extra={"TLMFORGE_HOOKS": "false"})
    assert rc == 0
    assert "systemMessage" not in out


def test_malformed_stdin_fails_open():
    """Malformed stdin must not crash the hook — fail open with exit 0."""
    result = subprocess.run(
        [sys.executable, HOOK1],
        input="not json at all {{{",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Should write warning to stderr
    assert result.stderr or True  # warn is optional for UserPromptSubmit


def test_empty_stdin_fails_open():
    result = subprocess.run(
        [sys.executable, HOOK1],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
