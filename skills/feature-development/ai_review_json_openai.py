#!/usr/bin/env python3
"""ai_review_json_openai.py — OpenAI Responses API reviewer for tlmforge.

Exit codes:
  0  — review written (status=ok); Phase 0 stub never exits 0
  2  — graceful skip (flag unset, key absent, SDK missing, empty diff,
       invalid marker, all provider failures); JSON written with status=skipped
 64  — usage error (missing --output, --iteration, non-integer --iteration,
       output parent directory does not exist, invalid --mode)

Phase 0: stub — always writes status=skipped and exits 2.
Phase 1: implements the real Responses API call.

DO NOT add debug prints that might leak OPENAI_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REVIEWER_NAME = "openai"
SCHEMA_VERSION = "1.0"
VALID_MODES = {"code", "plan"}


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
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            f.write(f"{ts} openai: {reason}\n")
    except OSError:
        pass


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

    if args.mode not in VALID_MODES:
        print(f"ERROR: --mode must be one of {sorted(VALID_MODES)}, got: {args.mode!r}", file=sys.stderr)
        sys.exit(64)

    output_path = Path(args.output)
    if not output_path.parent.exists():
        print(f"ERROR: output directory does not exist: {output_path.parent}", file=sys.stderr)
        sys.exit(64)

    # --- Pre-flight checks (all → graceful skip) ---
    def skip(reason: str) -> None:
        _write_atomic(output_path, _skipped_json(iteration))
        sys.exit(2)

    if os.environ.get("TLMFORGE_ENABLE_OPENAI") != "1":
        skip("TLMFORGE_ENABLE_OPENAI not set")

    if not os.environ.get("OPENAI_API_KEY"):
        skip("OPENAI_API_KEY not set")

    if os.environ.get("TLMFORGE_OPENAI_SDK_ABSENT") == "1":
        skip("openai SDK absent (TLMFORGE_OPENAI_SDK_ABSENT=1)")

    try:
        import openai  # noqa: F401
    except ImportError:
        skip("openai SDK not importable")

    # --- Phase 0 stub: always skip ---
    # Phase 1 replaces this with the real Responses API call.
    _write_atomic(output_path, _skipped_json(iteration))
    sys.exit(2)


if __name__ == "__main__":
    main()
