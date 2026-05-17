# Phase 1 Code Review — multi-llm-reviewers

**Reviewer:** code-reviewer  
**Date:** 2026-05-17  
**Iteration:** 1  
**Scope:** `ai_review_json_openai.py` + `ai_review_openai.sh` + `tests/test_openai_wrapper.py`  
**Verdict:** NEEDS REVISION

---

## VERDICT: NEEDS REVISION

Two critical issues must be fixed before Phase 1 ships. Both involve the silent-skip
invariant — the #1 user requirement — being broken in ways no existing test catches.

---

## Changes Reviewed

- `skills/feature-development/ai_review_json_openai.py` — full OpenAI Responses API
  integration replacing the Phase 0 stub
- `skills/feature-development/ai_review_openai.sh` — shell wrapper (unchanged from Phase 0
  other than `--mode` pass-through)
- `skills/feature-development/tests/test_openai_wrapper.py` — extended with 15 Phase 1 tests

## Context Checked

- `specs/multi-llm-reviewers/README.md` — master plan, threat model, phase promises
- `skills/feature-development/review_schema.json` — output schema, `iteration minimum: 1`
- `specs/multi-llm-reviewers/phase-1-evidence.md` — implementation claims
- `specs/multi-llm-reviewers/agent_verification/tester_edge_cases.json` — 15 EC scenarios
- `specs/multi-llm-reviewers/phase-1-verification/tester.md` + `tester.json` — tester findings
- `specs/multi-llm-reviewers/phase-1-verification/phase-auditor.json` — auditor findings

---

## Test Assessment

- Tests present: Yes
- Test quality: Good (well-structured, use of monkeypatch and mock correctly, AAA pattern consistent)
- TDD compliance: Tests appear to have been written first (Phase 0 tests confirmed RED against stub; Phase 1 tests confirmed RED then GREEN)
- Test count: 84 passed (31 OpenAI wrapper + 53 pre-existing), 0 failed
- Coverage gaps: 6 gaps identified (4 carried from tester, 2 newly found by this reviewer)

---

## Critical Issues (must fix)

### [CRIT-1] `skip()` inner function never logs — 4 pre-flight paths produce zero log output

**File:** `skills/feature-development/ai_review_json_openai.py`, lines 180-197

The `skip()` inner function defined at line 180 accepts a `reason: str` parameter but the
function body (lines 181-182) never calls `_log_failure(reason)`. It calls `_write_atomic`
and `sys.exit(2)` — that is all.

As a consequence, the four pre-flight skip paths produce no log entry:
- Line 185: `TLMFORGE_ENABLE_OPENAI` not set
- Line 189: `OPENAI_API_KEY` not set
- Line 192: `TLMFORGE_OPENAI_SDK_ABSENT=1`
- Line 197: `import openai` fails (`ImportError`)

The spec (README.md line 64) states: "Log the failure reason to
`~/.cache/tlmforge/llm_reviewer.log` for user debugging." The spec also lists logging
explicitly in the Phase 1 step list. A user whose key is expired or whose flag is unset
receives no log entry and no way to diagnose why the reviewer silently disappears.

Note: the later skip paths (empty diff at line 212, plan mode failures at lines 218-230,
and the final retry failure at line 271) DO call `_log_failure()` before `skip()`. This
inconsistency suggests the early pre-flight paths were written before `_log_failure()` was
wired into `skip()`, and the wiring was never completed.

**Why this matters:** If a user sets `TLMFORGE_ENABLE_OPENAI=1` but has a bad or expired
`OPENAI_API_KEY`, the reviewer silently skips every review round with no log entry. The user
has no signal to diagnose whether the key is wrong, the flag is missing, or the SDK is absent.
The entire point of `~/.cache/tlmforge/llm_reviewer.log` is to surface exactly this case.

**Required fix:**
```python
def skip(reason: str) -> None:
    _log_failure(reason)              # ADD THIS LINE
    _write_atomic(output_path, _skipped_json(iteration))
    sys.exit(2)
```

After this fix, all four pre-flight paths automatically log before skipping. The existing
tests for these paths (`test_exit2_skip_when_flag_unset`, `test_exit2_skip_when_key_unset_flag_set`,
`test_exit2_skip_when_openai_not_importable`) should be extended to assert that the log file
contains an entry (mirror the pattern used in `test_auth_error_exits_2_skipped_logged`).

---

### [CRIT-2] `_write_atomic` unhandled exception on write failure exits code 1 with traceback — violates exit-code contract

**File:** `skills/feature-development/ai_review_json_openai.py`, lines 52-67

The `_write_atomic` function at line 67 re-raises any exception that occurs during the
tempfile write or `os.replace()`. When this exception propagates unhandled through `main()`,
Python exits with code 1 and prints a traceback to stderr. No sidecar JSON is written.

This violates the exit-code contract in three ways:
1. Exit code 1 is not in the documented contract (0, 2, 64 are the only valid exits).
2. No sidecar JSON means the convergence engine sees a missing reviewer file and injects a
   false `reviewer_json_missing` CRITICAL.
3. A traceback to stderr may leak path information (the tempfile path includes the output
   directory).

The `_write_atomic` is called from two call sites: line 181 (inside `skip()`) and line 275
(the happy-path write). A disk-full failure at either site produces exit 1.

The spec (README.md line 97) says: "`status=error` reserved for implementation bugs (e.g.,
disk full on atomic write) — not for LLM provider unavailability." This implies `status=error`
should be written and exit 2 should be used, OR the spec implicitly accepts that infrastructure
failures produce a non-zero non-2 exit. However, since no caller handles exit 1, and the
convergence engine treats any non-zero non-skipped exit as unexpected, exit 1 with no sidecar
is the worst outcome.

**Required fix:** Wrap both `_write_atomic` call sites in `main()` so infrastructure failures
produce a defined exit. The minimal safe fix is to catch at the top level:

```python
# At the bottom of main(), replace the final two lines:
try:
    final = _normalize_response(result, iteration)
    _write_atomic(output_path, final)
except Exception as exc:
    _log_failure(f"write failed: {exc}")
    # Best-effort: try to write skipped sidecar; if this also fails, exit 1 is acceptable
    try:
        _write_atomic(output_path, _skipped_json(iteration))
    except Exception:
        pass
    sys.exit(2)
sys.exit(0)
```

The `skip()` call site is harder — if `_write_atomic` raises inside `skip()`, there is no
sidecar to write. For that path, wrapping `skip()` body in a try/except is sufficient since
the sidecar write is the operation that failed.

---

## High Issues (should fix)

### [HIGH-1] `iteration=0` passes shell validation but violates `review_schema.json minimum: 1`

**File:** `skills/feature-development/ai_review_openai.sh`, line 36  
**File:** `skills/feature-development/ai_review_json_openai.py`, lines 164-165

The shell wrapper validates `--iteration` with `^[0-9]+$`, which accepts `0`. The Python
script does `int(args.iteration)` with no minimum check. The output JSON will contain
`"iteration": 0`, which fails the schema's `"minimum": 1` constraint.

Any downstream schema validator (or the convergence engine if it validates iteration) will
reject the file. The behavior is undefined: it could be treated as a missing reviewer
(false CRITICAL) or silently accepted with incorrect iteration tracking.

No test covers `--iteration 0` through either the shell wrapper or the Python script.

**Required fix:**
- Shell: change regex to `^[1-9][0-9]*$` (requires at least 1, no leading zeros).
  Alternatively keep `^[0-9]+$` but add `[[ "$ITERATION" -lt 1 ]]` check immediately after.
- Python: add `if iteration < 1: print("ERROR: ..."); sys.exit(64)` after the `int()` parse.
- Test: add `test_exit64_when_iteration_zero` covering both the shell and Python paths.

---

### [HIGH-2] `_validate_response_json` does not validate the `verdict` enum

**File:** `skills/feature-development/ai_review_json_openai.py`, lines 107-130

`_validate_response_json` checks that `verdict` is present (line 115) but does not check
that its value is one of `approve|approve_with_warnings|needs_revision|do_not_ship`. If the
LLM returns `"verdict": "APPROVE"` (uppercase) or `"verdict": "reject"` (not in enum), the
function returns the dict as valid and `_normalize_response` writes it through unchanged.

The `review_schema.json` (line 27-28) defines verdict as a strict enum. A written file with
an invalid verdict value will fail schema validation downstream. The retry logic — which
exists specifically to handle malformed LLM output — will never trigger for this case.

This is analogous to the severity/category enum validation that IS present (lines 121-129)
and for which a retry is correctly triggered. The verdict field was simply missed.

**Required fix:**
```python
VALID_VERDICTS = {"approve", "approve_with_warnings", "needs_revision", "do_not_ship"}

# In _validate_response_json, after the required fields check:
if data.get("verdict") not in VALID_VERDICTS:
    return None
```

Add a test: mock returns `"verdict": "APPROVE"` on attempt 1 and a valid verdict on
attempt 2; assert exit 0 with valid verdict in output.

---

## Warnings (should fix — carried from tester, confirmed)

### [WARN-1] `test_no_tmp_file_left_behind` covers only the skipped code path

**File:** `skills/feature-development/tests/test_openai_wrapper.py`, lines 192-196

The test runs without `TLMFORGE_ENABLE_OPENAI` set, so the script exits 2 and
`_write_atomic` is only exercised for the `_skipped_json()` payload. The Phase 1
happy path — where `_write_atomic` is called with a `status=ok` review — has no
assertion that no `.tmp` file remains after exit 0. ARCH-C3 regression guard is
half-coverage.

### [WARN-2] EC-10: invalid `category` in findings has no regression test

**File:** `skills/feature-development/tests/test_openai_wrapper.py`

`_validate_response_json` correctly rejects findings with an invalid `category`
value. No test verifies this path. Removing the category check would not fail any test.

### [WARN-3] `_is_truncated` branch 2 (`response.status == "incomplete"`) is untested

**File:** `skills/feature-development/tests/test_openai_wrapper.py`

Only branch 1 (`incomplete_details is not None`) is covered by
`test_truncated_response_exits_2_skipped_logged`. Branch 2 has no coverage.

---

## Pattern Violations

### Shell wrapper has dead branching logic at lines 47-54

The `if/else` at lines 47-54 of `ai_review_openai.sh` checks `TLMFORGE_ENABLE_OPENAI`
and `OPENAI_API_KEY`, then calls the Python script in both branches with identical
arguments. The two branches are functionally identical — no early exit, no different
behavior. This is dead branching: the condition result is never used. The correct
pattern (used by similar wrappers in this codebase) is a single unconditional delegation
to the Python script, which handles all pre-flight checks itself.

The phase-auditor flagged this as `low/meta`. This reviewer elevates it to a pattern
violation because it creates a maintenance trap: a future developer adding branch-specific
logic (e.g., "skip the Python call entirely if flag is unset for performance") would
introduce a divergence that breaks the pre-flight contract.

---

## Test Gap Table

| File | Changed lines | Test file | Coverage |
|---|---|---|---|
| `ai_review_json_openai.py` | 180-182 (skip function) | `test_openai_wrapper.py` | CRITICAL: `skip()` never calls `_log_failure`. Pre-flight paths (flag unset, key absent, SDK absent/unimportable) not logged. Existing tests do not assert log file presence for these paths. |
| `ai_review_json_openai.py` | 52-67 (_write_atomic) | `test_openai_wrapper.py` | No test for write failure path (disk full, permissions error). Exit-code contract on exception is unspecified and results in exit 1 + traceback. |
| `ai_review_json_openai.py` | 164-165 (iteration parse) | `test_openai_wrapper.py` | No test for `--iteration 0`; violates schema `minimum: 1`. |
| `ai_review_json_openai.py` | 107-130 (_validate_response_json) | `test_openai_wrapper.py` | `verdict` enum not validated; no test for invalid verdict value triggering retry. |
| `ai_review_json_openai.py` | 96-104 (_is_truncated) | `test_openai_wrapper.py` | Branch 2 (`status == "incomplete"`) untested (W-3 from tester, confirmed). |
| `ai_review_json_openai.py` | 247-249 (except Exception) | `test_openai_wrapper.py` | Generic exception path in `call_api()` untested (L-1 from tester, confirmed). |
| `ai_review_openai.sh` | 36 (iteration regex) | — | No shell-level test for `--iteration 0` accepting when schema requires minimum: 1. |

---

## Suggestions

- The `attempt()` function logs "response truncated (incomplete_details set)" at line 255
  regardless of which `_is_truncated` branch fired. Consider: "response truncated" without
  the parenthetical, or pass the reason from `_is_truncated` back to the caller.

- The `SYSTEM_PROMPT` at line 47 hardcodes `iteration (<N>)` literally — the actual
  iteration number is never interpolated into the prompt. The LLM is told to use `<N>` as
  the literal value. This does not cause a functional bug (because `_normalize_response`
  overwrites the iteration field), but it means the LLM's output will always have the
  literal string `<N>` in the iteration field before normalization. This is harmless but
  could confuse future debugging if someone removes `_normalize_response`.

- Consider adding a `TLMFORGE_OPENAI_TIMEOUT` env var path for future use. Connection
  timeouts currently fall through to the bare `except Exception` handler, which is correct
  but untestable without the env override pattern already used for the SDK absence check.

---

## What's Good

- The silent-skip invariant is correctly implemented for all LLM provider failure paths that
  flow through `call_api()` and `attempt()`: `APIError`, generic exceptions, truncation,
  invalid JSON, enum mismatch, both retries exhausted. Every one of these writes
  `status=skipped` and exits 2. The #1 user requirement is met for the full API call phase.

- `REVIEWER_NAME = "openai"` is a module-level constant and `_normalize_response` always
  overwrites the `reviewer` field. There is zero possibility of a model name leaking into
  the output regardless of `TLMFORGE_OPENAI_MODEL` value. EC-7 is fully closed.

- The Responses API is used exclusively. `client.responses.create()` at line 237.
  `client.chat.completions` does not appear anywhere in the file. ARCH-C2 is fully closed.

- Atomic write is correctly implemented: `NamedTemporaryFile(dir=output_dir, ...)` +
  `os.replace()`. The `dir=output_dir` parameter is critical for POSIX atomicity guarantee
  (same filesystem as destination). This was identified in ARCH-C3 and is correctly done.

- Path traversal is blocked by `re.fullmatch(r'[a-zA-Z0-9_-]+', raw_feature)` before any
  path construction. `.strip()` is applied before validation so trailing newlines from
  shell `echo` do not cause false rejections. TM-C2 is fully closed.

- The `OPENAI_API_KEY` is passed directly to `openai.OpenAI(api_key=api_key)` in Python —
  never interpolated into a shell command, never logged. TM-H2 is not applicable and
  TM-C1 is addressed by the permission structure (outside this file's scope).

- All JSON output goes through `json.dumps()`. Error messages from OpenAI (which can contain
  quotes, newlines, Unicode) are only written to the plain-text log file, never into the
  JSON output. The JSON boundary is safe.

- Test structure is clean: AAA pattern throughout, `monkeypatch.setenv` correctly isolated,
  `MagicMock` for SDK, `importlib.util.spec_from_file_location` for module isolation.
  `side_effect = [resp1, resp2]` correctly tests retry sequencing.

- TDD discipline appears genuine: Phase 1 tests were written during Phase 0, confirmed
  RED against the stub, and turned GREEN only after the Phase 1 implementation.
