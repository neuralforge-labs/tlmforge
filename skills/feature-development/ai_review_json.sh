#!/usr/bin/env bash
# ai_review_json.sh — Gemini wrapper with structured JSON output for the
# feature-development skill's Stage 5 multi-agent re-review convergence.
#
# Exit codes:
#   0 = wrapper completed; output JSON was written (may be status=ok or
#       status=error with synthetic CRITICAL if Gemini envelope-failed twice)
#   2 = absent — graceful skip (gemini binary missing, or GEMINI_API_KEY not set,
#       or GEMINI_API_KEY_ABSENT=1 forced for tests)
#  64 = usage error (missing args)
#
# Requires: GEMINI_API_KEY env var. If unset, exits 2 (graceful skip).
# DO NOT add `set -x` — it would leak the API key value to stderr/logs.

set -euo pipefail

OUTPUT=""
ITERATION=""
GEMINI_BIN="${GEMINI_BIN:-gemini}"
MODEL="gemini-2.5-pro"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --iteration) ITERATION="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ai_review_json.sh --output PATH --iteration N"
      exit 64
      ;;
    *) echo "unknown arg: $1" >&2; exit 64 ;;
  esac
done

if [[ -z "$OUTPUT" || -z "$ITERATION" ]]; then
  echo "ERROR: --output and --iteration required" >&2
  exit 64
fi

# --- Atomic write helpers ---

atomic_write() {
  local tmpfile="${OUTPUT}.tmp"
  printf '%s\n' "$1" > "$tmpfile"
  mv "$tmpfile" "$OUTPUT"
}

write_skipped() {
  atomic_write "{\"reviewer\":\"gemini\",\"schema_version\":\"1.0\",\"iteration\":${ITERATION},\"status\":\"skipped\",\"verdict\":\"approve\",\"findings\":[]}"
}

write_error() {
  local finding="$1"
  local fix="${2:-Check that GEMINI_API_KEY is set and the gemini CLI is installed.}"
  atomic_write "{\"reviewer\":\"gemini\",\"schema_version\":\"1.0\",\"iteration\":${ITERATION},\"status\":\"error\",\"verdict\":\"needs_revision\",\"findings\":[{\"severity\":\"critical\",\"category\":\"meta\",\"file\":\"architecture\",\"line\":null,\"finding\":\"${finding}\",\"suggested_fix\":\"${fix}\"}]}"
}

# --- Pre-flight checks ---

# Test escape hatch
if [[ "${GEMINI_API_KEY_ABSENT:-0}" == "1" ]]; then
  write_skipped
  exit 2
fi

# 1. Gemini binary check (graceful skip)
if ! command -v "$GEMINI_BIN" >/dev/null 2>&1; then
  write_skipped
  exit 2
fi

# 2. API key check (graceful skip if not set)
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  write_skipped
  exit 2
fi

export GEMINI_API_KEY

# --- Gemini call (with retry) ---

GEMINI_PROMPT='Review the diff against the feature-development discipline. Output ONLY a JSON object that validates against the review_schema.json in this plugin. Lowercase severity. Pick category from the enum (security, auth, null_safety, bug, logic_error, race_condition, data_loss, missing_error_handling, test_coverage, tdd_violation, architecture, backwards_compat, performance, observability, documentation, style, meta). suggested_fix REQUIRED if severity=critical. Top-level fields: reviewer (set to "gemini"), schema_version "1.0", iteration ('"${ITERATION}"'), status "ok", verdict (approve|approve_with_warnings|needs_revision|do_not_ship), findings (array). Output JSON only, no prose.'

call_gemini() {
  git diff HEAD 2>/dev/null | "$GEMINI_BIN" -m "$MODEL" -p "$GEMINI_PROMPT" 2>/dev/null || true
}

is_valid_review() {
  python3 - <<'PY' "$1" >/dev/null 2>&1
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(1)
needed = ["reviewer", "schema_version", "verdict", "findings"]
if not all(k in d for k in needed):
    sys.exit(1)
if "error" in d and isinstance(d.get("error"), dict) and "findings" not in d:
    sys.exit(1)
sys.exit(0)
PY
}

is_error_envelope() {
  python3 - <<'PY' "$1" >/dev/null 2>&1
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(1)
sys.exit(0 if "error" in d and isinstance(d.get("error"), dict) and "findings" not in d else 1)
PY
}

output="$(call_gemini)"

if ! is_valid_review "$output"; then
  output="$(call_gemini)"
  if ! is_valid_review "$output"; then
    if is_error_envelope "$output"; then
      write_error "gemini_unavailable — Gemini API returned error envelope after 1 retry"
    else
      write_error "gemini_unavailable — Gemini output failed shape validation after 1 retry"
    fi
    exit 0
  fi
fi

final="$(python3 - <<PY "$output" "$ITERATION"
import json, sys
d = json.loads(sys.argv[1])
d["iteration"] = int(sys.argv[2])
d.setdefault("status", "ok")
d["reviewer"] = "gemini"
d["schema_version"] = "1.0"
print(json.dumps(d))
PY
)"

atomic_write "$final"
exit 0
