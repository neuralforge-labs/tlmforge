"""Tests for ai_review_json_openai.py (Phase 0 + Phase 1).

Phase 0 tests are GREEN against the stub (which always writes status=skipped).
Phase 1 tests are RED against the stub and GREEN once the Responses API call
is implemented.

Run with:
  python3 -m pytest skills/feature-development/tests/test_openai_wrapper.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "ai_review_json_openai.py"
SCHEMA_FILE = SKILL_DIR / "review_schema.json"

# Load the review schema once for validation helper
with open(SCHEMA_FILE) as f:
    _SCHEMA = json.load(f)

VALID_SEVERITIES = {"critical", "high", "medium", "low", "nit"}
VALID_CATEGORIES = {
    "security", "auth", "null_safety", "bug", "logic_error", "race_condition",
    "data_loss", "missing_error_handling", "test_coverage", "tdd_violation",
    "architecture", "backwards_compat", "performance", "observability",
    "documentation", "style", "meta",
}


def run_script(args: list[str], env_overrides: dict[str, str] | None = None,
               extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # Remove keys that might accidentally opt-in
    env.pop("TLMFORGE_ENABLE_OPENAI", None)
    env.pop("OPENAI_API_KEY", None)
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        env=env,
    )


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def validate_schema_fields(data: dict) -> None:
    """Minimal schema check — required top-level fields."""
    for field in ("reviewer", "schema_version", "iteration", "verdict", "findings"):
        assert field in data, f"missing field: {field}"
    assert data["schema_version"] == "1.0"
    assert isinstance(data["findings"], list)


# ============================================================================
# Phase 0 — exit-code contract and stub behavior (all GREEN against stub)
# ============================================================================

class TestPhase0ExitCodes:
    def test_exit64_when_output_missing(self, tmp_path):
        result = run_script(["--iteration", "1"])
        assert result.returncode == 64

    def test_exit64_when_iteration_missing(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out])
        assert result.returncode == 64

    def test_exit64_when_iteration_noninteger(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out, "--iteration", "abc"])
        assert result.returncode == 64

    def test_exit64_when_output_parent_missing(self, tmp_path):
        out = str(tmp_path / "nonexistent_dir" / "r.json")
        result = run_script(
            ["--output", out, "--iteration", "1"],
            env_overrides={"TLMFORGE_ENABLE_OPENAI": "1", "OPENAI_API_KEY": "fake"},
        )
        assert result.returncode == 64

    def test_exit2_skip_when_flag_unset(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out, "--iteration", "1"])
        assert result.returncode == 2
        data = load_json(out)
        assert data["status"] == "skipped"
        assert data["reviewer"] == "openai"

    def test_exit2_skip_when_key_unset_flag_set(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(
            ["--output", out, "--iteration", "1"],
            env_overrides={"TLMFORGE_ENABLE_OPENAI": "1"},
        )
        assert result.returncode == 2
        data = load_json(out)
        assert data["status"] == "skipped"

    def test_exit2_skip_when_openai_not_importable(self, tmp_path):
        """Test the TLMFORGE_OPENAI_SDK_ABSENT escape hatch for CI environments."""
        out = str(tmp_path / "r.json")
        result = run_script(
            ["--output", out, "--iteration", "1"],
            env_overrides={
                "TLMFORGE_ENABLE_OPENAI": "1",
                "OPENAI_API_KEY": "fake",
                "TLMFORGE_OPENAI_SDK_ABSENT": "1",
            },
        )
        assert result.returncode == 2
        data = load_json(out)
        assert data["status"] == "skipped"


class TestPhase0SkippedJsonShape:
    def test_skipped_json_has_reviewer_openai(self, tmp_path):
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "1"])
        data = load_json(out)
        assert data["reviewer"] == "openai"

    def test_skipped_json_has_correct_iteration(self, tmp_path):
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "7"])
        data = load_json(out)
        assert data["iteration"] == 7

    def test_skipped_json_validates_schema(self, tmp_path):
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "1"])
        data = load_json(out)
        validate_schema_fields(data)
        assert data["status"] == "skipped"
        assert data["findings"] == []

    def test_skipped_json_is_valid_json(self, tmp_path):
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "1"])
        with open(out) as f:
            content = f.read()
        json.loads(content)  # raises if invalid

    def test_default_mode_is_code(self, tmp_path):
        """Verify the script accepts no --mode and defaults cleanly."""
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out, "--iteration", "1"])
        assert result.returncode == 2  # skipped (flag unset), not a crash

    def test_mode_plan_accepted(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out, "--iteration", "1", "--mode", "plan"])
        assert result.returncode == 2  # skipped, not crashed

    def test_mode_invalid_exits_64(self, tmp_path):
        out = str(tmp_path / "r.json")
        result = run_script(["--output", out, "--iteration", "1", "--mode", "invalid"])
        assert result.returncode == 64


class TestPhase0AtomicWrite:
    def test_output_file_is_complete_json_after_write(self, tmp_path):
        """Atomic write: file should never contain partial JSON."""
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "1"])
        with open(out) as f:
            content = f.read()
        # Valid JSON from first byte to last — no truncation
        data = json.loads(content)
        assert "reviewer" in data

    def test_no_tmp_file_left_behind(self, tmp_path):
        out = str(tmp_path / "r.json")
        run_script(["--output", out, "--iteration", "1"])
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == [], f"tmp files left behind: {leftover}"


# ============================================================================
# Phase 1 — real API call paths (RED against Phase 0 stub)
# ============================================================================

class TestPhase1RealCallPaths:
    """These tests are RED against the Phase 0 stub (stub always exits 2).
    They turn GREEN when Phase 1 implements the Responses API call."""

    def _make_mock_response(self, findings: list | None = None,
                            verdict: str = "approve") -> MagicMock:
        """Build a mock openai.responses.create return value (non-truncated)."""
        payload = {
            "reviewer": "openai",
            "schema_version": "1.0",
            "iteration": 1,
            "status": "ok",
            "verdict": verdict,
            "findings": findings or [],
        }
        mock_resp = MagicMock()
        mock_resp.incomplete_details = None  # MagicMock attrs are truthy by default
        mock_resp.status = "completed"
        mock_resp.output_text = json.dumps(payload)
        return mock_resp

    def _run_main(self, mock_openai, argv, env_overrides=None,
                  extra_patches=None) -> tuple[int, Any]:
        """Load the script and call main() with given argv and module patches.

        Returns (exit_code, output_path_str_from_argv).
        """
        import importlib.util
        # Use a fresh module for each call to avoid state leakage
        spec = importlib.util.spec_from_file_location(f"_oai_{id(self)}", SCRIPT)
        mod = importlib.util.module_from_spec(spec)

        patches = [patch.dict("sys.modules", {"openai": mock_openai})]
        if extra_patches:
            patches.extend(extra_patches)

        ctx = patch("sys.argv", argv)
        with ctx:
            for p in patches:
                p.start()
            try:
                spec.loader.exec_module(mod)
                with pytest.raises(SystemExit) as exc_info:
                    mod.main()
            finally:
                for p in reversed(patches):
                    p.stop()
        return exc_info.value.code

    def test_mocked_diff_exits_0_status_ok(self, tmp_path, monkeypatch):
        """mode=code with mocked valid OpenAI response → exit 0, status=ok."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.responses.create.return_value = self._make_mock_response()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff --git a/f\n+added")],
        )
        assert code == 0
        data = load_json(out)
        assert data["status"] == "ok"
        assert data["reviewer"] == "openai"
        validate_schema_fields(data)

    def test_mocked_plan_exits_0_status_ok(self, tmp_path, monkeypatch):
        """mode=plan with mocked valid OpenAI response → exit 0, status=ok."""
        out = str(tmp_path / "r.json")
        feature_dir = tmp_path / "specs" / "my-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "README.md").write_text("# my-feature plan\n")
        (tmp_path / "specs" / ".tlmforge_active_feature").write_text("my-feature\n")

        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.responses.create.return_value = self._make_mock_response()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "plan"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("pathlib.Path.cwd", return_value=tmp_path)],
        )
        assert code == 0
        data = load_json(out)
        assert data["status"] == "ok"

    def test_empty_diff_exits_2_skipped(self, tmp_path, monkeypatch):
        """mode=code with empty git diff → exit 2, status=skipped, OpenAI not called."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"   \n  ")],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"
        mock_client.responses.create.assert_not_called()

    def test_retry_on_invalid_json_then_valid(self, tmp_path, monkeypatch):
        """First call returns garbage JSON, retry returns valid → exit 0, status=ok."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        valid_resp = MagicMock()
        valid_resp.incomplete_details = None
        valid_resp.status = "completed"
        valid_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "approve", "findings": [],
        })
        invalid_resp = MagicMock()
        invalid_resp.incomplete_details = None
        invalid_resp.status = "completed"
        invalid_resp.output_text = "not json at all {"

        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [invalid_resp, valid_resp]
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff content here")],
        )
        assert code == 0
        data = load_json(out)
        assert data["status"] == "ok"
        assert mock_client.responses.create.call_count == 2

    def test_retry_on_uppercase_severity_then_valid(self, tmp_path, monkeypatch):
        """First call returns uppercase severity CRITICAL, retry returns valid → exit 0."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        invalid_resp = MagicMock()
        invalid_resp.incomplete_details = None
        invalid_resp.status = "completed"
        invalid_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "needs_revision",
            "findings": [{"severity": "CRITICAL", "category": "bug",
                          "file": "f.py", "finding": "bad", "suggested_fix": "fix it"}],
        })
        valid_resp = MagicMock()
        valid_resp.incomplete_details = None
        valid_resp.status = "completed"
        valid_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "needs_revision",
            "findings": [{"severity": "critical", "category": "bug",
                          "file": "f.py", "finding": "bad", "suggested_fix": "fix it"}],
        })

        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [invalid_resp, valid_resp]
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff content here")],
        )
        assert code == 0
        data = load_json(out)
        assert data["status"] == "ok"

    def test_both_calls_invalid_json_exits_2_skipped_logged(self, tmp_path, monkeypatch):
        """Both retries return invalid JSON → exit 2, status=skipped, logged."""
        out = str(tmp_path / "r.json")
        log_file = tmp_path / "llm_reviewer.log"
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("TLMFORGE_LLM_LOG", str(log_file))

        bad_resp = MagicMock()
        bad_resp.incomplete_details = None  # not truncated — should try JSON parse and fail
        bad_resp.status = "completed"
        bad_resp.output_text = "not json {"
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [bad_resp, bad_resp]
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff content here")],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"
        assert data["reviewer"] == "openai"
        assert log_file.exists(), "failure must be logged"

    def test_auth_error_exits_2_skipped_logged(self, tmp_path, monkeypatch):
        """Auth error (mocked openai.APIError) → exit 2, status=skipped, logged."""
        out = str(tmp_path / "r.json")
        log_file = tmp_path / "llm_reviewer.log"
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "bad-key")
        monkeypatch.setenv("TLMFORGE_LLM_LOG", str(log_file))

        class FakeAPIError(Exception):
            pass

        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.APIError = FakeAPIError
        mock_client.responses.create.side_effect = FakeAPIError("invalid key")
        mock_openai.OpenAI.return_value = mock_client

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff content here")],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"
        assert log_file.exists()

    def test_truncated_response_exits_2_skipped_logged(self, tmp_path, monkeypatch):
        """Truncated response (incomplete_details set) → retry → still truncated → exit 2, skipped."""
        out = str(tmp_path / "r.json")
        log_file = tmp_path / "llm_reviewer.log"
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("TLMFORGE_LLM_LOG", str(log_file))

        truncated_resp = MagicMock()
        truncated_resp.output_text = '{"reviewer": "openai", "findings": ['
        truncated_resp.incomplete_details = MagicMock()  # non-None → truncated

        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [truncated_resp, truncated_resp]
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"diff content here")],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"
        assert log_file.exists()

    def test_plan_absent_marker_exits_2_skipped(self, tmp_path, monkeypatch):
        """mode=plan with absent active-feature marker → exit 2, status=skipped."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai = MagicMock()
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "plan"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("pathlib.Path.cwd", return_value=tmp_path)],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"

    def test_plan_path_traversal_marker_exits_2_skipped(self, tmp_path, monkeypatch):
        """mode=plan with marker '../etc/passwd' → exit 2, skipped (path traversal blocked)."""
        out = str(tmp_path / "r.json")
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / ".tlmforge_active_feature").write_text("../etc/passwd\n")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai = MagicMock()
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "plan"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("pathlib.Path.cwd", return_value=tmp_path)],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"

    def test_plan_marker_with_spaces_exits_2_skipped(self, tmp_path, monkeypatch):
        """mode=plan with marker 'my feature' (spaces) → exit 2, skipped."""
        out = str(tmp_path / "r.json")
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / ".tlmforge_active_feature").write_text("my feature\n")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai = MagicMock()
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "plan"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("pathlib.Path.cwd", return_value=tmp_path)],
        )
        assert code == 2
        data = load_json(out)
        assert data["status"] == "skipped"

    def test_plan_marker_with_trailing_newline_works(self, tmp_path, monkeypatch):
        """mode=plan with marker 'my-feature\\n' from echo → strip → valid feature name."""
        out = str(tmp_path / "r.json")
        specs_dir = tmp_path / "specs"
        feature_dir = specs_dir / "my-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "README.md").write_text("# plan\n")
        (specs_dir / ".tlmforge_active_feature").write_text("my-feature\n")

        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_resp = MagicMock()
        mock_resp.incomplete_details = None
        mock_resp.status = "completed"
        mock_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "approve", "findings": [],
        })
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_resp
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "plan"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("pathlib.Path.cwd", return_value=tmp_path)],
        )
        assert code == 0, "trailing newline must not cause skip"
        data = load_json(out)
        assert data["reviewer"] == "openai"

    def test_reviewer_field_always_openai(self, tmp_path, monkeypatch):
        """reviewer must be 'openai' regardless of TLMFORGE_OPENAI_MODEL."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("TLMFORGE_OPENAI_MODEL", "gpt-99-turbo")

        mock_resp = MagicMock()
        mock_resp.incomplete_details = None
        mock_resp.status = "completed"
        mock_resp.output_text = json.dumps({
            "reviewer": "gpt-99-turbo",  # LLM might write this; must be overwritten
            "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "approve", "findings": [],
        })
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_resp
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"some diff content")],
        )
        assert code == 0
        data = load_json(out)
        assert data["reviewer"] == "openai"

    def test_all_output_json_validates_schema(self, tmp_path, monkeypatch):
        """status=ok output must have all required schema fields."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_resp = MagicMock()
        mock_resp.incomplete_details = None
        mock_resp.status = "completed"
        mock_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "approve", "findings": [],
        })
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_resp
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"some diff content")],
        )
        assert code == 0
        data = load_json(out)
        validate_schema_fields(data)

    def test_critical_findings_have_suggested_fix(self, tmp_path, monkeypatch):
        """All critical findings in status=ok output must have suggested_fix."""
        out = str(tmp_path / "r.json")
        monkeypatch.setenv("TLMFORGE_ENABLE_OPENAI", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_resp = MagicMock()
        mock_resp.incomplete_details = None
        mock_resp.status = "completed"
        mock_resp.output_text = json.dumps({
            "reviewer": "openai", "schema_version": "1.0", "iteration": 1,
            "status": "ok", "verdict": "needs_revision",
            "findings": [{"severity": "critical", "category": "bug",
                          "file": "f.py", "finding": "bad thing here",
                          "suggested_fix": "do the right thing"}],
        })
        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_resp
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = Exception

        argv = [str(SCRIPT), "--output", out, "--iteration", "1", "--mode", "code"]
        code = self._run_main(
            mock_openai, argv,
            extra_patches=[patch("subprocess.check_output", return_value=b"some diff content")],
        )
        assert code == 0
        data = load_json(out)
        for finding in data["findings"]:
            if finding["severity"] == "critical":
                assert "suggested_fix" in finding
                assert len(finding["suggested_fix"]) >= 8
