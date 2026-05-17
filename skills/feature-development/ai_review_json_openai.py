#!/usr/bin/env python3
"""ai_review_json_openai.py — OpenAI Responses API reviewer for tlmforge.

Exit codes:
  0  — review written (status=ok or status=ok with findings)
  2  — graceful skip (flag unset, key absent, SDK missing, empty diff,
       invalid marker, all provider failures); JSON written with status=skipped
 64  — usage error (missing --output, --iteration, non-integer --iteration,
       output parent directory does not exist, invalid --mode)

DO NOT add debug prints that might leak OPENAI_API_KEY.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REVIEWER_NAME = "openai"
SCHEMA_VERSION = "1.0"
VALID_MODES = {"code", "plan"}
DEFAULT_MODEL = "gpt-5.5"

VALID_SEVERITIES = {"critical", "high", "medium", "low", "nit"}
VALID_VERDICTS = {"approve", "approve_with_warnings", "needs_revision", "do_not_ship"}
VALID_CATEGORIES = {
    "security", "auth", "null_safety", "bug", "logic_error", "race_condition",
    "data_loss", "missing_error_handling", "test_coverage", "tdd_violation",
    "architecture", "backwards_compat", "performance", "observability",
    "documentation", "style", "meta",
}

SYSTEM_PROMPT = (
    'Review the provided content against the feature-development discipline. '
    'Output ONLY a JSON object. Lowercase severity. Category from enum: '
    'security, auth, null_safety, bug, logic_error, race_condition, data_loss, '
    'missing_error_handling, test_coverage, tdd_violation, architecture, '
    'backwards_compat, performance, observability, documentation, style, meta. '
    'suggested_fix REQUIRED if severity=critical. '
    'Top-level fields: reviewer ("openai"), schema_version ("1.0"), '
    'iteration (integer), status ("ok"), '
    'verdict (approve|approve_with_warnings|needs_revision|do_not_ship), '
    'findings (array). Output JSON only, no prose.'
)


def _write_atomic(output_path: Path, data: dict) -> None:
    """Write JSON to output_path atomically via tempfile + os.replace."""
    output_dir = output_path.parent
    tmp = tempfile.NamedTemporaryFile(
        dir=output_dir, suffix=".tmp", delete=False, mode="w", encoding="utf-8"
    )
    try:
        tmp.write(json.dumps(data))
        tmp.close()
        os.replace(tmp.name, output_path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _skipped_json(iteration: int) -> dict:
    return {
        "reviewer": REVIEWER_NAME,
        "schema_version": SCHEMA_VERSION,
        "iteration": iteration,
        "status": "skipped",
        "verdict": "approve",
        "findings": [],
    }


def _log_failure(reason: str) -> None:
    log_path_env = os.environ.get("TLMFORGE_LLM_LOG")
    if log_path_env:
        log_path = Path(log_path_env)
    else:
        log_path = Path.home() / ".cache" / "tlmforge" / "llm_reviewer.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} openai: {reason}\n")
    except OSError:
        pass


def _is_truncated(response: object) -> bool:
    """Return True if the Responses API response indicates incomplete output."""
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete is not None:
        return True
    status = getattr(response, "status", None)
    if status == "incomplete":
        return True
    return False


def _validate_response_json(text: str) -> dict | None:
    """Parse and validate the JSON from OpenAI. Returns dict or None on failure."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    required = {"reviewer", "schema_version", "verdict", "findings"}
    if not required.issubset(data.keys()):
        return None
    if not isinstance(data.get("findings"), list):
        return None
    if data.get("verdict") not in VALID_VERDICTS:
        return None
    # Validate enum fields in findings
    for finding in data["findings"]:
        if not isinstance(finding, dict):
            return None
        sev = finding.get("severity", "")
        cat = finding.get("category", "")
        if sev not in VALID_SEVERITIES:
            return None
        if cat not in VALID_CATEGORIES:
            return None
    return data


def _normalize_response(data: dict, iteration: int) -> dict:
    """Force correct reviewer/schema_version/iteration fields."""
    data["reviewer"] = REVIEWER_NAME
    data["schema_version"] = SCHEMA_VERSION
    data["iteration"] = iteration
    data.setdefault("status", "ok")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output")
    parser.add_argument("--iteration")
    parser.add_argument("--mode", default="code")
    parser.add_argument("-h", "--help", action="store_true")

    args, unknown = parser.parse_known_args()

    if args.help:
        print("Usage: ai_review_json_openai.py --output PATH --iteration N [--mode plan|code]")
        sys.exit(64)

    if unknown:
        print(f"ERROR: unknown arguments: {unknown}", file=sys.stderr)
        sys.exit(64)

    # --- Validate required args ---
    if not args.output or not args.iteration:
        print("ERROR: --output and --iteration required", file=sys.stderr)
        sys.exit(64)

    try:
        iteration = int(args.iteration)
    except ValueError:
        print(f"ERROR: --iteration must be an integer, got: {args.iteration!r}", file=sys.stderr)
        sys.exit(64)

    if iteration < 1:
        print(f"ERROR: --iteration must be >= 1, got: {iteration}", file=sys.stderr)
        sys.exit(64)

    if args.mode not in VALID_MODES:
        print(f"ERROR: --mode must be one of {sorted(VALID_MODES)}, got: {args.mode!r}", file=sys.stderr)
        sys.exit(64)

    output_path = Path(args.output)
    if not output_path.parent.exists():
        print(f"ERROR: output directory does not exist: {output_path.parent}", file=sys.stderr)
        sys.exit(64)

    # --- Pre-flight checks (all → graceful skip) ---
    def skip(reason: str) -> None:
        _log_failure(reason)
        _write_atomic(output_path, _skipped_json(iteration))
        sys.exit(2)

    if os.environ.get("TLMFORGE_ENABLE_OPENAI") != "1":
        skip("TLMFORGE_ENABLE_OPENAI not set")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        skip("OPENAI_API_KEY not set")

    if os.environ.get("TLMFORGE_OPENAI_SDK_ABSENT") == "1":
        skip("openai SDK absent (TLMFORGE_OPENAI_SDK_ABSENT=1)")

    try:
        import openai
    except ImportError:
        skip("openai SDK not importable")

    # --- Gather content to review ---
    model = os.environ.get("TLMFORGE_OPENAI_MODEL", DEFAULT_MODEL)

    if args.mode == "code":
        try:
            diff_bytes = subprocess.check_output(
                ["git", "diff", "HEAD"], stderr=subprocess.DEVNULL
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            diff_bytes = b""
        content = diff_bytes.decode("utf-8", errors="replace")
        if not content.strip():
            skip("empty git diff")
    else:
        # mode=plan: read active-feature marker and load README.md
        cwd = Path.cwd()
        marker_path = cwd / "specs" / ".tlmforge_active_feature"
        if not marker_path.exists():
            skip("active-feature marker absent")
        raw_feature = marker_path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw_feature:
            skip("active-feature marker is empty")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", raw_feature):
            skip(f"active-feature marker invalid: {raw_feature!r}")
        readme_path = cwd / "specs" / raw_feature / "README.md"
        if not readme_path.exists():
            skip(f"README not found: {readme_path}")
        content = readme_path.read_text(encoding="utf-8", errors="replace")

    # --- Call OpenAI Responses API (with retry once) ---
    def call_api() -> object | None:
        try:
            client = openai.OpenAI(api_key=api_key)
            return client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
            )
        except openai.APIError as exc:
            _log_failure(f"API error: {exc}")
            return None
        except Exception as exc:
            _log_failure(f"unexpected error: {exc}")
            return None

    def attempt(response: object | None) -> dict | None:
        if response is None:
            return None
        if _is_truncated(response):
            _log_failure("response truncated (incomplete_details set)")
            return None
        raw = getattr(response, "output_text", None)
        if not raw:
            _log_failure("response has no output_text")
            return None
        return _validate_response_json(raw)

    resp1 = call_api()
    result = attempt(resp1)

    if result is None:
        resp2 = call_api()
        result = attempt(resp2)

    if result is None:
        _log_failure("both attempts failed — writing skipped")
        skip("both API attempts failed or returned invalid response")

    final = _normalize_response(result, iteration)
    try:
        _write_atomic(output_path, final)
    except Exception as exc:
        _log_failure(f"atomic write failed: {exc}")
        try:
            _write_atomic(output_path, _skipped_json(iteration))
        except Exception:
            pass
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
