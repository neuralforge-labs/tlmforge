"""
End-to-end integration test for the three-hook enforcement system.

Simulates a full feature-development session:
  1. Hook 1 reminder injected on every prompt
  2. Hook 2 blocks mutation without skill, allows after skill invoked
  3. Hook 3 allows commit at audited SHA, blocks after drift, allows after PSR
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), '..')
HOOK1 = os.path.join(HOOKS_DIR, 'load_feature_dev_skill.py')
HOOK2 = os.path.join(HOOKS_DIR, 'enforce_skill_invoked.py')
HOOK3 = os.path.join(HOOKS_DIR, 'enforce_post_stage5_review.py')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_hook(script, payload, env_extra=None, cwd=None):
    env = os.environ.copy()
    env.pop("TLMFORGE_HOOKS", None)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(
        [sys.executable, script],
        input=json.dumps(payload),
        capture_output=True, text=True,
        env=env,
        cwd=cwd or os.getcwd(),
    )
    return r.returncode, r.stdout, r.stderr


def _write_transcript(entries, tmp_dir):
    tf = tempfile.NamedTemporaryFile(
        mode='w', suffix='.jsonl', dir=tmp_dir, delete=False
    )
    tf.write('\n'.join(json.dumps(e) for e in entries) + '\n')
    tf.flush()
    tf.close()
    return tf.name


def _git_setup(path):
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    (path / "README.md").write_text("init\n") if hasattr(path, 'write_text') else \
        open(os.path.join(str(path), "README.md"), 'w').write("init\n")
    p = str(path)
    subprocess.run(["git", "add", "README.md"], cwd=p, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init", "--no-gpg-sign"],
                   cwd=p, capture_output=True, env=env)
    return p, env


def _head(repo):
    r = subprocess.run(["git", "rev-parse", "HEAD"],
                       capture_output=True, text=True, cwd=repo)
    return r.stdout.strip()


def _advance(repo, env):
    dummy = os.path.join(repo, "dummy.txt")
    with open(dummy, 'w') as f:
        f.write("advance\n")
    subprocess.run(["git", "add", "dummy.txt"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "advance", "--no-gpg-sign"],
                   cwd=repo, capture_output=True, env=env)
    return _head(repo)


def _write_audit(av_dir, fname, verdict_sha):
    os.makedirs(av_dir, exist_ok=True)
    data = {
        "reviewer": "red-team-reviewer",
        "schema_version": "1.0",
        "iteration": 1,
        "verdict": "approve",
        "verdict_sha": verdict_sha,
        "findings": [],
    }
    with open(os.path.join(av_dir, fname), 'w') as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Hook 1 — reminder injected on every prompt
# ---------------------------------------------------------------------------

def test_hook1_injects_system_message(tmp_path):
    payload = {"session_id": "s1", "prompt": "add a login button", "transcript_path": ""}
    rc, stdout, _ = _run_hook(HOOK1, payload)
    assert rc == 0
    out = json.loads(stdout)
    assert "systemMessage" in out
    assert "feature-development" in out["systemMessage"]


def test_hook1_bypassed_by_env(tmp_path):
    payload = {"session_id": "s1", "prompt": "add a login button"}
    rc, stdout, _ = _run_hook(HOOK1, payload, env_extra={"TLMFORGE_HOOKS": "0"})
    assert rc == 0
    out = json.loads(stdout)
    assert "systemMessage" not in out


# ---------------------------------------------------------------------------
# Hook 2 — blocks mutation without skill, allows with skill or override
# ---------------------------------------------------------------------------

def test_hook2_blocks_edit_without_skill(tmp_path):
    entries = [{"type": "user", "message": {"role": "user", "content": "add encryption"}}]
    transcript = _write_transcript(entries, str(tmp_path))
    payload = {"session_id": "s1", "tool_name": "Edit", "tool_input": {},
               "transcript_path": transcript}
    rc, _, stderr = _run_hook(HOOK2, payload)
    assert rc == 2
    assert "feature-development" in stderr


def test_hook2_allows_edit_after_skill_invoked(tmp_path):
    entries = [
        {"type": "user", "message": {"role": "user", "content": "add encryption"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "tlmforge:feature-development"}}
        ]}},
    ]
    transcript = _write_transcript(entries, str(tmp_path))
    payload = {"session_id": "s1", "tool_name": "Edit", "tool_input": {},
               "transcript_path": transcript}
    rc, _, _ = _run_hook(HOOK2, payload)
    assert rc == 0


def test_hook2_allows_with_be_quick_override(tmp_path):
    entries = [{"type": "user", "message": {"role": "user", "content": "be quick fix typo"}}]
    transcript = _write_transcript(entries, str(tmp_path))
    payload = {"session_id": "s1", "tool_name": "Write", "tool_input": {},
               "transcript_path": transcript}
    rc, _, _ = _run_hook(HOOK2, payload)
    assert rc == 0


# ---------------------------------------------------------------------------
# Hook 3 — full lifecycle: audit @ SHA_A, advance to SHA_B, PSR unblocks
# ---------------------------------------------------------------------------

def test_hook3_full_lifecycle(tmp_path):
    repo, git_env = _git_setup(tmp_path)

    sha_a = _head(repo)

    # Set up active-feature marker and Stage 5 audit at SHA_A
    av_dir = os.path.join(repo, "specs", "myfeature", "agent_verification")
    marker = os.path.join(repo, "specs", ".tlmforge_active_feature")
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, 'w') as f:
        f.write("myfeature\n")
    _write_audit(av_dir, "final_audit_red-team-reviewer.json", sha_a)

    # --- Hook 3 allows git push at SHA_A (HEAD == verdict_sha) ---
    payload_push = {
        "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
    }
    rc, _, _ = _run_hook(HOOK3, payload_push, cwd=repo)
    assert rc == 0, "Hook 3 should allow push when HEAD matches verdict_sha"

    # --- Advance HEAD to SHA_B ---
    sha_b = _advance(repo, git_env)
    assert sha_b != sha_a

    # --- Hook 3 blocks git commit at SHA_B (drift without PSR) ---
    payload_commit = {
        "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'post-stage5'"},
    }
    rc, _, stderr = _run_hook(HOOK3, payload_commit, cwd=repo)
    assert rc == 2, "Hook 3 should block commit after HEAD drifts past audit SHA"
    assert stderr

    # --- Add valid PSR marker at SHA_B ---
    _write_audit(av_dir, f"final_audit_red-team-reviewer_psr_{sha_b}.json", sha_b)

    # --- Hook 3 allows again after valid PSR ---
    rc, _, _ = _run_hook(HOOK3, payload_push, cwd=repo)
    assert rc == 0, "Hook 3 should allow push after valid PSR marker"


def test_hook3_non_git_command_always_passes(tmp_path):
    repo, _ = _git_setup(tmp_path)
    payload = {"session_id": "s1", "tool_name": "Bash",
               "tool_input": {"command": "ls -la"}}
    rc, _, _ = _run_hook(HOOK3, payload, cwd=repo)
    assert rc == 0


def test_hook3_bypassed_by_env(tmp_path):
    repo, git_env = _git_setup(tmp_path)
    sha_a = _head(repo)
    av_dir = os.path.join(repo, "specs", "myfeature", "agent_verification")
    marker = os.path.join(repo, "specs", ".tlmforge_active_feature")
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, 'w') as f:
        f.write("myfeature\n")
    _write_audit(av_dir, "final_audit_red-team-reviewer.json", sha_a)
    _advance(repo, git_env)  # drift

    payload = {"session_id": "s1", "tool_name": "Bash",
               "tool_input": {"command": "git push origin main"}}
    rc, _, _ = _run_hook(HOOK3, payload, cwd=repo, env_extra={"TLMFORGE_HOOKS": "0"})
    assert rc == 0


def test_hook3_override_phrase_bypasses_after_drift(tmp_path):
    repo, git_env = _git_setup(tmp_path)
    sha_a = _head(repo)
    av_dir = os.path.join(repo, "specs", "myfeature", "agent_verification")
    marker = os.path.join(repo, "specs", ".tlmforge_active_feature")
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, 'w') as f:
        f.write("myfeature\n")
    _write_audit(av_dir, "final_audit_red-team-reviewer.json", sha_a)
    _advance(repo, git_env)  # drift

    transcript_entries = [
        {"type": "user", "message": {"role": "user", "content": "be quick push this"}}
    ]
    transcript = _write_transcript(transcript_entries, str(tmp_path))
    payload = {
        "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "transcript_path": transcript,
    }
    rc, _, _ = _run_hook(HOOK3, payload, cwd=repo)
    assert rc == 0
