# Phase 1 Tester Verification — multi-llm-reviewers

**Reviewer:** tester  
**Date:** 2026-05-17  
**Scope:** `ai_review_json_openai.py` + `tests/test_openai_wrapper.py` (Phase 1 implementation)  
**Verdict:** APPROVE WITH WARNINGS

---

## Test Suite Results

Command run:
```
python3 -m pytest skills/feature-development/tests/ --ignore=skills/feature-development/tests/fixtures -v 2>&1
```

Results:
- **84 passed, 0 failed** in 0.75s
- OpenAI wrapper tests: **31 passed** (16 Phase 0 + 15 Phase 1)
- Pre-existing tests: **53 passed, 0 regressions**

Evidence claim cross-check: Evidence doc claims "84 passed in 0.71s". Observed: 84 passed in 0.75s. Counts match exactly. CONFIRMED.

---

## EC Scenario Coverage Matrix

| ID | Description | Covered? | Test name | Notes |
|----|-------------|----------|-----------|-------|
| EC-1 | Auth error → skipped + logged | YES | `test_auth_error_exits_2_skipped_logged` | Asserts exit 2, status=skipped, log exists |
| EC-2 | Empty diff → skipped | YES | `test_empty_diff_exits_2_skipped` | Asserts exit 2, status=skipped, responses.create not called |
| EC-3 | Truncated response → retry → skipped + logged | YES | `test_truncated_response_exits_2_skipped_logged` | Uses `incomplete_details = MagicMock()` (truthy) |
| EC-4 | Uppercase severity CRITICAL → retry → valid | YES | `test_retry_on_uppercase_severity_then_valid` + `test_both_calls_invalid_json_exits_2_skipped_logged` | Retry-to-valid and both-fail paths |
| EC-5 | mode=plan absent marker → skipped | YES | `test_plan_absent_marker_exits_2_skipped` | Asserts exit 2, status=skipped |
| EC-6 | Output parent dir missing → exit 64 | YES | `test_exit64_when_output_parent_missing` | Asserts returncode 64 |
| EC-7 | reviewer field hardcoded "openai" | YES | `test_reviewer_field_always_openai` | LLM returns "gpt-99-turbo"; asserts overwritten to "openai" |
| EC-8 | Non-integer --iteration → exit 64 | YES | `test_exit64_when_iteration_noninteger` | Asserts returncode 64 |
| EC-9 | Marker with spaces → skipped | YES | `test_plan_marker_with_spaces_exits_2_skipped` | regex fullmatch rejects spaces |
| EC-10 | Schema enum mismatch (invalid category) | PARTIAL | None explicit for category | Implementation rejects invalid category in `_validate_response_json` but no regression test |
| TM-C1 | Bash permission injection via OPENAI_API_KEY= | N/A | Not a unit-testable code concern | Implementation uses Python SDK, not shell; no injection surface |
| TM-C2 | Path traversal in marker | YES | `test_plan_path_traversal_marker_exits_2_skipped` | `../etc/passwd` rejected by fullmatch regex → skipped |
| TM-H2 | Error message JSON injection via log | NOT AN ISSUE | N/A | Log is plain text (line 91), not JSON — no injection surface |
| ARCH-C2 | Responses API used not Chat Completions | YES | Implementation line 237: `client.responses.create()` | Static verification; no chat.completions anywhere |
| ARCH-C3 | Atomic write — no partial file | PARTIAL | `test_no_tmp_file_left_behind` covers skipped path only | No test for missing .tmp after status=ok write |

---

## Findings

### WARNING (will cause bugs under unusual conditions)

#### [W-1] `test_no_tmp_file_left_behind` only covers the skipped path

The atomic write test (`TestPhase0AtomicWrite::test_no_tmp_file_left_behind`) runs without
`TLMFORGE_ENABLE_OPENAI` set, so the script exits 2 (skipped) and the atomic write is exercised
for the `_skipped_json()` payload only. The Phase 1 happy path — where `_write_atomic` is called
with a `status=ok` review — has no assertion that no `.tmp` file is left behind after a successful
write. If an intermediate refactor broke the `os.replace()` call path for the non-skipped code
branch, this test would not catch it.

- **Impact:** Regression guard for ARCH-C3 is half-coverage only.
- **Fix:** Add one test in `TestPhase1RealCallPaths` that calls `tmp_path.glob("*.tmp")` after
  a successful `status=ok` write and asserts the list is empty.
- **File:** `skills/feature-development/tests/test_openai_wrapper.py`

#### [W-2] EC-10 (invalid category in findings) has no regression guard

`_validate_response_json` correctly rejects findings with an invalid `category` value (e.g.,
`"NOT_A_CATEGORY"` is not in `VALID_CATEGORIES`), causing a retry and eventual skip. However,
there is no test that specifically verifies this path. If someone later removes the category
validation from `_validate_response_json` (e.g., to be more permissive), no test will fail.

- **Impact:** False-convergence failure mode has no regression guard — the exact scenario
  called out in EC-10.
- **Fix:** Add a test: mock returns a valid JSON with `"category": "not_a_real_category"` on
  both attempts; assert exit 2, status=skipped.
- **File:** `skills/feature-development/tests/test_openai_wrapper.py`

#### [W-3] `response.status == "incomplete"` truncation path is untested

`_is_truncated()` has two detection branches (lines 99–103):
1. `response.incomplete_details is not None`
2. `response.status == "incomplete"`

`test_truncated_response_exits_2_skipped_logged` exercises only branch 1 (sets
`incomplete_details = MagicMock()`, which is truthy). Branch 2 — where `incomplete_details`
is None but `status` is `"incomplete"` — has no test coverage. If branch 2 is ever broken
(e.g., attribute name changes), tests stay green while truncated responses silently pass through.

- **Impact:** Silent acceptance of a partial-JSON review as complete.
- **Fix:** Add a test with `truncated_resp.incomplete_details = None` and
  `truncated_resp.status = "incomplete"`; assert exit 2, status=skipped.
- **File:** `skills/feature-development/tests/test_openai_wrapper.py`

### LOW (minor gaps, no production impact expected)

#### [L-1] Generic exception path in `call_api()` is untested

`call_api()` catches `openai.APIError` at line 244 and a bare `Exception` at line 247. The
`test_auth_error_exits_2_skipped_logged` test covers the `APIError` branch. The `except Exception`
branch (network timeout, OS error, etc.) has no dedicated test. The behavior is correct (both
return None → retry → skip) but there is no regression guard for the generic path.

- **Impact:** Low — behavior is identical to the APIError path. But if someone tightens the
  except clause to only `APIError`, the generic path silently stops working.
- **Fix:** Add a test where `responses.create` raises `RuntimeError("timeout")` and assert
  exit 2, status=skipped.

#### [L-2] Log assertions check existence only, not content

Three tests (`test_auth_error_exits_2_skipped_logged`, `test_both_calls_invalid_json_exits_2_skipped_logged`,
`test_truncated_response_exits_2_skipped_logged`) assert `log_file.exists()` but do not check
log file content. A broken log call that creates an empty file would pass these tests. Not a
correctness issue for the reviewer output (the JSON is the source of truth), but reduces
observability confidence.

---

## Edge Cases Properly Handled

The following are correctly implemented and tested:

- All 4 pre-flight skip conditions (flag unset, key absent, SDK absent, SDK not importable) write
  `status=skipped` + exit 2 — the critical user requirement is fully satisfied for these paths.
- Retry logic: first attempt failure triggers exactly one retry; both failures → skipped.
- `reviewer` field normalization: LLM output overridden to `"openai"` by `_normalize_response()`.
- Path traversal in marker: `re.fullmatch(r'[a-zA-Z0-9_-]+', raw_feature)` blocks `../` patterns.
- Trailing newline in marker: `.strip()` before regex makes `"my-feature\n"` valid.
- Marker with spaces: rejected by fullmatch → skipped.
- `response.status == "completed"` and `incomplete_details = None` combination correctly passes
  the truncation check.
- `_write_atomic` uses `tempfile.NamedTemporaryFile` + `os.replace()`: atomic on POSIX. Temp
  file is in the same directory as output (required for `os.replace()` atomicity across filesystems).
- Responses API used (`client.responses.create`) — Chat Completions API (`client.chat.completions`)
  not present anywhere in the implementation.
- Empty `output_text` (falsy) correctly logs and returns None from `attempt()`.
- OPENAI_API_KEY is passed to `openai.OpenAI(api_key=api_key)` via Python, never to a shell command.

---

## Missing Tests Summary

1. **ARCH-C3 status=ok atomic write cleanup** — `test_no_tmp_file_left_behind` for Phase 1
   happy path: run with mocked valid response, then `assert list(tmp_path.glob("*.tmp")) == []`.

2. **EC-10 invalid category enum** — mock both calls returning `"category": "NOT_A_CAT"`;
   assert exit 2, status=skipped.

3. **EC-3 / _is_truncated branch 2** — `incomplete_details=None` + `status="incomplete"`;
   assert exit 2, status=skipped, log exists.

4. **Generic exception in call_api** — `responses.create` raises `RuntimeError`; assert exit 2,
   status=skipped, log exists.

All four are LOW-to-WARNING severity. None are blockers for shipping Phase 1.
