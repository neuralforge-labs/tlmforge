import json
import os
import subprocess
import sys
import pytest
import tempfile

HOOK3 = os.path.join(os.path.dirname(__file__), '..', 'enforce_post_stage5_review.py')


def run_hook3(cmd: str, env_extra: dict = None, repo_root: str = None,
              active_feature: str = None, final_audits: list = None,
              psr_markers: list = None, cwd: str = None,
              transcript_entries: list = None) -> tuple[int, str]:
    """
    Run hook3 with synthetic state.
    - active_feature: name to write to specs/.tlmforge_active_feature
    - final_audits: list of (filename, json_dict) to write into specs/<feature>/agent_verification/
    - psr_markers: list of (filename, json_dict) for PSR marker files
    - transcript_entries: list of JSONL dicts to write as a temp transcript
    """
    env = os.environ.copy()
    env.pop("TLMFORGE_HOOKS", None)
    if env_extra:
        env.update(env_extra)

    if repo_root:
        if active_feature:
            marker_path = os.path.join(repo_root, "specs", ".tlmforge_active_feature")
            os.makedirs(os.path.dirname(marker_path), exist_ok=True)
            with open(marker_path, 'w') as f:
                f.write(active_feature)

            if final_audits or psr_markers:
                av_dir = os.path.join(repo_root, "specs", active_feature, "agent_verification")
                os.makedirs(av_dir, exist_ok=True)
                for fname, data in (final_audits or []):
                    with open(os.path.join(av_dir, fname), 'w') as f:
                        json.dump(data, f)
                for fname, data in (psr_markers or []):
                    with open(os.path.join(av_dir, fname), 'w') as f:
                        json.dump(data, f)

    payload = {
        "session_id": "test-session",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    }

    tf_name = None
    if transcript_entries is not None:
        tf = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        tf.write('\n'.join(json.dumps(e) for e in transcript_entries) + '\n')
        tf.flush()
        tf_name = tf.name
        tf.close()
        payload["transcript_path"] = tf_name

    run_cwd = cwd or repo_root or os.getcwd()
    result = subprocess.run(
        [sys.executable, HOOK3],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=run_cwd,
    )
    if tf_name:
        os.unlink(tf_name)
    return result.returncode, result.stderr


def make_audit(verdict_sha: str) -> dict:
    return {
        "reviewer": "red-team-reviewer",
        "schema_version": "1.0",
        "iteration": 1,
        "verdict": "approve",
        "verdict_sha": verdict_sha,
        "findings": [],
    }


# --- Pass-through cases ---

def test_non_bash_tool_ignored(tmp_git_repo):
    """Non-Bash tools always pass through."""
    payload = {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": "/x"}}
    result = subprocess.run(
        [sys.executable, HOOK3],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=tmp_git_repo,
    )
    assert result.returncode == 0


def test_non_git_bash_command_passes_through(tmp_git_repo):
    rc, _ = run_hook3("ls -la", repo_root=tmp_git_repo, active_feature="myfeature")
    assert rc == 0


def test_no_active_feature_marker_passes_through(tmp_git_repo):
    """No .tlmforge_active_feature file → no active feature → pass through."""
    rc, _ = run_hook3("git commit -m 'test'", repo_root=tmp_git_repo)
    assert rc == 0


def test_no_stage5_final_audit_passes_through(tmp_git_repo):
    """Active feature exists but no final_audit_*.json → no Stage 5 yet → pass through."""
    rc, _ = run_hook3(
        "git commit -m 'test'",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[],
    )
    assert rc == 0


def test_no_verdict_sha_in_audit_passes_through(tmp_git_repo):
    """Audit file exists but has no verdict_sha → treat as no Stage 5 → pass through."""
    audit_no_sha = {"reviewer": "red-team", "schema_version": "1.0", "verdict": "approve", "findings": []}
    rc, _ = run_hook3(
        "git commit -m 'test'",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", audit_no_sha)],
    )
    assert rc == 0


def test_bypass_tlmforge_hooks_0(tmp_git_repo, make_audit_at_head):
    audit, head_sha = make_audit_at_head
    # Advance HEAD by creating a new commit
    new_sha = advance_head(tmp_git_repo)
    rc, _ = run_hook3(
        "git commit -m 'another'",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        env_extra={"TLMFORGE_HOOKS": "0"},
    )
    assert rc == 0


def test_head_matches_verdict_sha_passes_through(tmp_git_repo, make_audit_at_head):
    audit, head_sha = make_audit_at_head
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
    )
    assert rc == 0


def test_short_sha_verdict_normalizes_to_allow(tmp_git_repo, make_audit_at_head):
    """EC-3: Short SHA in verdict_sha must compare equal to full HEAD."""
    _, head_sha = make_audit_at_head
    short_sha = head_sha[:7]
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(short_sha))],
    )
    assert rc == 0


def test_valid_psr_marker_allows(tmp_git_repo, make_audit_at_head):
    """Valid PSR marker with matching internal SHA allows push."""
    _, head_sha = make_audit_at_head
    old_sha = "dead" * 10  # fake old sha
    new_sha = advance_head(tmp_git_repo)
    # new HEAD is now new_sha — get the actual new HEAD
    new_head = get_head(tmp_git_repo)
    psr = make_audit(new_head)
    psr_fname = f"final_audit_red-team_psr_{new_head}.json"
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        psr_markers=[(psr_fname, psr)],
    )
    assert rc == 0


def test_override_be_quick_allows_after_drift(tmp_git_repo, make_audit_at_head):
    """Override phrase 'be quick' in last user message bypasses the block."""
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    transcript = [{"type": "user", "message": {"role": "user", "content": "be quick push this"}}]
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        transcript_entries=transcript,
    )
    assert rc == 0


# --- Block cases ---

def test_head_drifted_without_psr_blocks(tmp_git_repo, make_audit_at_head):
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    rc, stderr = run_hook3(
        "git commit -m 'post-stage5'",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
    )
    assert rc == 2
    assert stderr  # must have actionable block message


def test_block_message_is_actionable(tmp_git_repo, make_audit_at_head):
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    rc, stderr = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
    )
    assert rc == 2
    assert "psr" in stderr.lower() or "re-review" in stderr.lower() or "stage 5" in stderr.lower()


def test_psr_marker_with_wrong_internal_sha_blocks(tmp_git_repo, make_audit_at_head):
    """HIGH-3: PSR marker filename matches but internal SHA is wrong → block."""
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    new_head = get_head(tmp_git_repo)
    # PSR marker filename has correct new_head but internal SHA is wrong
    wrong_psr = make_audit("wrongsha" + "0" * 32)
    psr_fname = f"final_audit_red-team_psr_{new_head}.json"
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        psr_markers=[(psr_fname, wrong_psr)],
    )
    assert rc == 2


def test_psr_marker_missing_verdict_sha_blocks(tmp_git_repo, make_audit_at_head):
    """Tester LOW-1: PSR file without verdict_sha field → treat as no valid PSR."""
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    new_head = get_head(tmp_git_repo)
    psr_no_sha = {"reviewer": "red-team", "schema_version": "1.0", "verdict": "approve", "findings": []}
    psr_fname = f"final_audit_red-team_psr_{new_head}.json"
    rc, _ = run_hook3(
        "git push",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        psr_markers=[(psr_fname, psr_no_sha)],
    )
    assert rc == 2


def test_no_commits_repo_passes_through(tmp_no_commits_repo):
    """EC-2: git rev-parse HEAD exits 128 in a fresh empty repo → pass through with warning."""
    rc, stderr = run_hook3(
        "git commit -m 'init'",
        repo_root=tmp_no_commits_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit("somesha"))],
    )
    assert rc == 0  # pass through
    assert stderr  # must warn


def test_sha_not_in_repo_history_blocks(tmp_git_repo):
    """EC-8: verdict_sha unreachable (e.g. after rebase) → still blocks."""
    phantom_sha = "a" * 40  # guaranteed not in any repo
    rc, stderr = run_hook3(
        "git commit -m 'test'",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(phantom_sha))],
    )
    assert rc == 2
    assert stderr


def test_corrupted_audit_json_skipped_falls_through(tmp_git_repo, make_audit_at_head):
    """MEDIUM-2: corrupt JSON in final_audit file → skip it → no verdict_sha → pass-through."""
    _, head_sha = make_audit_at_head
    av_dir = os.path.join(tmp_git_repo, "specs", "myfeature", "agent_verification")
    os.makedirs(av_dir, exist_ok=True)
    marker_path = os.path.join(tmp_git_repo, "specs", ".tlmforge_active_feature")
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    with open(marker_path, 'w') as f:
        f.write("myfeature")
    with open(os.path.join(av_dir, "final_audit_bad.json"), 'w') as f:
        f.write("{broken json")
    rc, _ = run_hook3(
        "git push origin main",
        repo_root=tmp_git_repo,
        active_feature=None,  # marker already written above
    )
    assert rc == 0  # corrupt file → no valid verdict_sha → pass-through


def test_cwd_subdirectory_still_finds_audit(tmp_git_repo, make_audit_at_head):
    """EC-6: Running from a subdirectory must still find the final_audit via repo root."""
    _, head_sha = make_audit_at_head
    advance_head(tmp_git_repo)
    subdir = os.path.join(tmp_git_repo, "src")
    os.makedirs(subdir, exist_ok=True)
    rc, _ = run_hook3(
        "git push",
        repo_root=tmp_git_repo,
        active_feature="myfeature",
        final_audits=[("final_audit_red-team.json", make_audit(head_sha))],
        cwd=subdir,
    )
    assert rc == 2  # blocked — found the audit even from subdir, HEAD drifted


# --- Helpers ---

def get_head(repo_root: str) -> str:
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=repo_root,
    )
    return result.stdout.strip()


def advance_head(repo_root: str) -> str:
    """Create an extra commit and return new HEAD sha."""
    import subprocess
    dummy = os.path.join(repo_root, "dummy.txt")
    with open(dummy, 'w') as f:
        f.write("advance\n")
    subprocess.run(["git", "add", "dummy.txt"], cwd=repo_root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "advance HEAD", "--no-gpg-sign"],
                   cwd=repo_root, capture_output=True, env={
                       **os.environ,
                       "GIT_AUTHOR_NAME": "Test",
                       "GIT_AUTHOR_EMAIL": "t@t.com",
                       "GIT_COMMITTER_NAME": "Test",
                       "GIT_COMMITTER_EMAIL": "t@t.com",
                   })
    return get_head(repo_root)


@pytest.fixture
def tmp_git_repo(tmp_path):
    """A temp git repo with one commit."""
    import subprocess
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    readme = tmp_path / "README.md"
    readme.write_text("init\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init", "--no-gpg-sign"],
                   cwd=tmp_path, capture_output=True, env=env)
    return str(tmp_path)


@pytest.fixture
def tmp_no_commits_repo(tmp_path):
    """A temp git repo with NO commits (fresh init only)."""
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    return str(tmp_path)


@pytest.fixture
def make_audit_at_head(tmp_git_repo):
    """Return (audit_dict, head_sha) where audit_dict.verdict_sha == current HEAD."""
    head_sha = get_head(tmp_git_repo)
    return make_audit(head_sha), head_sha
