#!/usr/bin/env python3
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_lib'))

from env import is_hooks_disabled
from overrides import has_override
from transcript import load_transcript_entries, find_last_user_index
from safe import fail_open

# Use search (not match) so compound commands like `cd . && git commit` are caught.
# gh pr create is intentionally excluded per master-plan decision.
GIT_MUTATION_RE = re.compile(
    r'\b(git\s+commit|git\s+push|gh\s+pr\s+merge)\b',
    re.IGNORECASE,
)

# verdict_sha must be a hex SHA (4–40 chars). Rejects refs like "HEAD", "main".
_SHA_RE = re.compile(r'^[0-9a-fA-F]{4,40}$')

# active_feature must be a safe path component — no slashes, no wildcards.
_FEATURE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

DENY_MSG = """\
[tlmforge] Stage 5 re-review required.

HEAD has changed since the final audit (red-team / architect) was recorded.
New commits were made without a post-Stage-5 re-review (PSR).

To unblock, one of:
  (a) Run Stage 5 again (re-review — red-team + architect — single-shot) and
      save the result as:
        specs/<feature>/agent_verification/final_audit_<role>_psr_<HEAD>.json
  (b) Set TLMFORGE_HOOKS=0 to bypass enforcement for this session.

Current HEAD has drifted past the audited SHA.
"""


def _run(cmd: list, cwd: str = None, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=cwd,
    )


def _normalize_sha(sha: str, cwd: str) -> str:
    """Expand short or full SHA to 40-char form; return '' on failure."""
    r = _run(["git", "rev-parse", sha], cwd=cwd)
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


@fail_open
def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print("[tlmforge] Hook 3: malformed stdin, failing open.", file=sys.stderr)
        sys.exit(0)

    if is_hooks_disabled():
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    cmd = payload.get("tool_input", {}).get("command", "")
    if not GIT_MUTATION_RE.search(cmd):
        sys.exit(0)

    # Find repo root from cwd
    run_cwd = os.getcwd()
    r = _run(["git", "rev-parse", "--show-toplevel"], cwd=run_cwd)
    if r.returncode != 0:
        sys.exit(0)
    repo_root = r.stdout.strip()

    # Read active feature marker
    marker_path = os.path.join(repo_root, "specs", ".tlmforge_active_feature")
    if not os.path.isfile(marker_path):
        sys.exit(0)
    with open(marker_path, encoding="utf-8", errors="replace") as f:
        active_feature = f.read().strip()
    # C-3: reject path-traversal and glob-expansion in feature name
    if not active_feature or not _FEATURE_NAME_RE.match(active_feature):
        sys.exit(0)

    # Glob final audit files
    av_dir = os.path.join(repo_root, "specs", active_feature, "agent_verification")
    audit_pattern = os.path.join(av_dir, "final_audit_*.json")
    audit_files = [
        p for p in glob.glob(audit_pattern)
        if "_psr_" not in os.path.basename(p)
    ]
    if not audit_files:
        sys.exit(0)

    # Extract verdict_sha values from audit files.
    # Distinguish:
    #   - field absent → Stage 3 file, no enforcement, skip
    #   - field present but not hex → invalid (C-1: reject git refs like "HEAD")
    #   - field present and hex → enforce
    verdict_shas = []
    invalid_sha_found = False
    for fpath in audit_files:
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        sha = data.get("verdict_sha")
        if sha is None:
            continue  # field absent → Stage 3 file, skip
        if isinstance(sha, str) and _SHA_RE.match(sha.strip()):
            verdict_shas.append(sha.strip())
        else:
            # C-1: field present but not a valid hex SHA → block, don't ignore
            invalid_sha_found = True

    if not verdict_shas:
        if invalid_sha_found:
            print(DENY_MSG, file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    # Get HEAD
    r = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if r.returncode != 0:
        # EC-2: fresh repo with no commits — warn and pass through
        print(
            "[tlmforge] Hook 3: git rev-parse HEAD failed (no commits?), failing open.",
            file=sys.stderr,
        )
        sys.exit(0)
    head_sha = r.stdout.strip()

    # Normalize verdict_shas; if any matches HEAD → pass through
    for vsha in verdict_shas:
        normalized = _normalize_sha(vsha, repo_root)
        if normalized and normalized == head_sha:
            sys.exit(0)

    # HEAD drifted. Check override phrase in last user message.
    transcript_path = payload.get("transcript_path")
    if transcript_path and os.path.isfile(transcript_path):
        entries = load_transcript_entries(transcript_path)
        last_user_idx = find_last_user_index(entries)
        if last_user_idx is not None:
            user_content = entries[last_user_idx].get("message", {}).get("content", "")
            if isinstance(user_content, list):
                # Skip tool_result blocks — they carry tool output, not user intent
                text = " ".join(
                    b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
                    else ""
                    for b in user_content
                )
            else:
                text = str(user_content)
            if has_override(text):
                sys.exit(0)

    # Check for valid PSR marker(s).
    psr_pattern = os.path.join(av_dir, f"final_audit_*_psr_{head_sha}.json")
    psr_files = glob.glob(psr_pattern)
    for psr_path in psr_files:
        try:
            with open(psr_path, encoding="utf-8", errors="replace") as f:
                psr_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        psr_sha = psr_data.get("verdict_sha")
        if not psr_sha or not isinstance(psr_sha, str):
            continue
        psr_sha = psr_sha.strip()
        # C-1: reject refs in PSR files too
        if not _SHA_RE.match(psr_sha):
            continue
        normalized_psr = _normalize_sha(psr_sha, repo_root)
        if normalized_psr and normalized_psr == head_sha:
            sys.exit(0)

    # Block
    print(DENY_MSG, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
