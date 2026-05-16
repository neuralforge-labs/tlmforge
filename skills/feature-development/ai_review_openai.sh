#!/usr/bin/env bash
# ai_review_openai.sh — thin shell wrapper for ai_review_json_openai.py.
#
# Exit codes:
#   0  = review written (status=ok)
#   2  = graceful skip: TLMFORGE_ENABLE_OPENAI unset, OPENAI_API_KEY absent,
#        or Python script chose to skip (empty diff, invalid marker, etc.)
#  64  = usage error (missing args, non-integer iteration, missing output dir)
#
# DO NOT add `set -x` — it would leak OPENAI_API_KEY to stderr/logs.

set -euo pipefail

OUTPUT=""
ITERATION=""
MODE="code"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)    OUTPUT="$2";    shift 2 ;;
    --iteration) ITERATION="$2"; shift 2 ;;
    --mode)      MODE="$2";      shift 2 ;;
    -h|--help)
      echo "Usage: ai_review_openai.sh --output PATH --iteration N [--mode plan|code]"
      exit 64
      ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 64 ;;
  esac
done

if [[ -z "$OUTPUT" || -z "$ITERATION" ]]; then
  echo "ERROR: --output and --iteration required" >&2
  exit 64
fi

if [[ ! "$ITERATION" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --iteration must be a non-negative integer, got: $ITERATION" >&2
  exit 64
fi

OUTPUT_DIR="$(dirname "$OUTPUT")"
if [[ ! -d "$OUTPUT_DIR" ]]; then
  echo "ERROR: output directory does not exist: $OUTPUT_DIR" >&2
  exit 64
fi

if [[ "${TLMFORGE_ENABLE_OPENAI:-}" != "1" ]] || [[ -z "${OPENAI_API_KEY:-}" ]]; then
  python3 "$(dirname "$0")/ai_review_json_openai.py" \
    --output "$OUTPUT" --iteration "$ITERATION" --mode "$MODE"
  exit $?
fi

python3 "$(dirname "$0")/ai_review_json_openai.py" \
  --output "$OUTPUT" --iteration "$ITERATION" --mode "$MODE"
exit $?
