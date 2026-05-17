# Phase 1 — Auditor Verdict (Final, Iteration 2)

## Verdict: NEEDS_REVISION

---

## Scope contract

| Promised file | Modified in Phase 1 diff? | Notes |
|---|---|---|
| `skills/feature-development/ai_review_json_openai.py` | YES | Full Responses API implementation delivered; all 10 in-scope items present |
| `skills/feature-development/ai_review_openai.sh` | NO | HIGH: spec promised "pass `--mode` through" update AND the HIGH-1 `>= 1` iteration fix for the shell layer; `--mode` was already wired in Phase 0 so that part is moot, but the HIGH-1 regex fix (`^[1-9][0-9]*$`) is absent from all committed history — it exists only as an uncommitted working-tree change |
| `specs/multi-llm-reviewers/phase-1-evidence.md` | YES | Evidence file updated and accurate on counts |

Out-of-scope items respected:
- `check_convergence.py` — not touched. PASS
- `review_schema.json` — not touched. PASS
- Existing Claude subagent prompts/hooks — not touched. PASS
- TLM server — not touched. PASS

No uncommitted scope creep beyond the shell wrapper regression described above.

---

## Test contract

| Promised test | Present? | Layer | Passing? |
|---|---|---|---|
| `mode=code` mocked diff → valid schema JSON, `reviewer="openai"`, exit 0 | YES (`test_mocked_diff_exits_0_status_ok`) | unit | PASS |
| `mode=plan` mocked README → valid schema JSON, exit 0 | YES (`test_mocked_plan_exits_0_status_ok`) | unit | PASS |
| `mode=code` empty diff → exit 2, status=skipped, OpenAI not called | YES (`test_empty_diff_exits_2_skipped`) | unit | PASS |
| First call invalid JSON → retry → second valid → exit 0, status=ok | YES (`test_retry_on_invalid_json_then_valid`) | unit | PASS |
| First call uppercase severity ("CRITICAL") → retry → second valid → exit 0 | YES (`test_retry_on_uppercase_severity_then_valid`) | unit | PASS |
| Both calls invalid JSON → status=skipped, exit 2, failure logged | YES (`test_both_calls_invalid_json_exits_2_skipped_logged`) | unit | PASS |
| Auth error (mocked) → status=skipped, exit 2, failure logged | YES (`test_auth_error_exits_2_skipped_logged`) | unit | PASS |
| Truncated response → retry → still truncated → status=skipped, exit 2, failure logged | YES (`test_truncated_response_exits_2_skipped_logged`) | unit | PASS |
| `mode=plan` + absent marker → exit 2, status=skipped | YES (`test_plan_absent_marker_exits_2_skipped`) | unit | PASS |
| `mode=plan` + marker with path traversal ("../foo") → exit 2, status=skipped | YES (`test_plan_path_traversal_marker_exits_2_skipped`) | unit | PASS |
| `mode=plan` + marker with spaces ("my feature") → exit 2 (invalid chars) | YES (`test_plan_marker_with_spaces_exits_2_skipped`) | unit | PASS |
| `reviewer` field in all output paths is exactly `"openai"` | YES (`test_reviewer_field_always_openai`) | unit | PASS |
| All output JSON validates against `review_schema.json` | YES (`test_all_output_json_validates_schema`) | unit | PASS |
| All critical findings in `status=ok` output have `suggested_fix` (len >= 8) | YES (`test_critical_findings_have_suggested_fix`) | unit | PASS |
| CRIT-1: skip() calls `_log_failure` (flag unset path) | YES (`test_preflight_skip_flag_unset_logs_to_file`) | unit | PASS |
| CRIT-1: skip() calls `_log_failure` (key unset path) | YES (`test_preflight_skip_key_unset_logs_to_file`) | unit | PASS |
| CRIT-2: final `_write_atomic` failure → skipped fallback + exit 2 + log | YES (`test_write_failure_falls_back_to_exit2_and_logs`) | unit | PASS |
| HIGH-1: `--iteration 0` → exit 64 (Python script) | YES (`test_iteration_zero_exits_64`) | unit | PASS |
| HIGH-1: `--iteration 0` → exit 64 (shell wrapper) | NO (test only exercises Python script via `run_script`; shell wrapper fix not committed) | — | NOT VERIFIED |
| HIGH-2: invalid verdict enum → both retries exhausted → skipped | YES (`test_invalid_verdict_enum_both_retries_exits_2_skipped`) | unit | PASS |

Test discipline:
- `phase-1-evidence.md` test run output present: YES — command, counts, timing all present
- Full pre-existing suite output present: YES — "53 passed, 0 regressions" stated and confirmed by live re-run
- Numbers match live re-run: YES — live run produced exactly 93 passed, 0 failed, 0.83s (evidence claimed 93 passed in 0.91s; the timing difference is environmental, not a discrepancy)

---

## Verification criteria

| Spec criterion | Evidence | Match? |
|---|---|---|
| (1) fake key → exit 2, status=skipped, reviewer="openai" | Covered by `test_exit2_skip_when_key_unset_flag_set` and `test_skipped_json_has_reviewer_openai` | PASS |
| (1b) valid mocked response → exit 0, status=ok, reviewer="openai", schema-valid | Covered by `test_mocked_diff_exits_0_status_ok` + `test_all_output_json_validates_schema` | PASS |
| (2) no TLMFORGE_ENABLE_OPENAI → exit 2, status=skipped | Covered by `test_exit2_skip_when_flag_unset` | PASS |
| (3) Gemini GEMINI_API_KEY_ABSENT=1 + `--mode plan` → exit 2, skipped | Phase 2 criterion; out of Phase 1 scope | N/A |
| (4) path traversal marker → exit 2, skipped | Covered by `test_plan_path_traversal_marker_exits_2_skipped` | PASS |
| (5) All pre-existing 23 tests pass | Evidence says 53; 53 passed live (original spec said 23; that was written before Phase 0 added 20 more; live count is correct) | PASS |
| (6) New tests pass | 40 OpenAI wrapper tests all GREEN (live-verified) | PASS |

---

## Rollback safety

Spec says: "Revert `ai_review_json_openai.py` to Phase 0 stub (git revert the Phase 1 commit)."

The Phase 1 commit (44c0a78) touches exactly two files:
- `skills/feature-development/ai_review_json_openai.py` — fully reversible
- `skills/feature-development/tests/test_openai_wrapper.py` — fully reversible

`git revert 44c0a78` is runnable and leaves Phase 0 state intact. Rollback is safe.

Note: the shell wrapper HIGH-1 fix is currently a working-tree-only change. Rolling back Phase 1 would not affect it, but it is also not captured in any commit, creating a gap in rollback documentation. If the working tree change were lost (e.g., `git restore`), the `^[0-9]+$` regex would silently allow `--iteration 0` through the shell layer.

---

## Findings

### HIGH

**H-1 — Shell wrapper HIGH-1 fix not committed**
- File: `skills/feature-development/ai_review_openai.sh`, line 36
- The spec required Phase 1 to fix `--iteration` validation in both the Python script AND the shell wrapper (spec section "HIGH-1 fix": `--iteration` must be >= 1, exit 64 in both shell and Python). The Python fix is committed and tested. The shell wrapper fix (`^[0-9]+$` → `^[1-9][0-9]*$`) exists only in the working tree — it is absent from the Phase 1 commit (44c0a78) and from all of git history. `git show 44c0a78:skills/feature-development/ai_review_openai.sh` returns the Phase 0 version with `^[0-9]+$`. A `git push` from any other working tree or a `git restore` would lose this fix silently.
- The test `test_iteration_zero_exits_64` passes because it invokes the Python script directly (`sys.executable, str(SCRIPT)`), not via the shell wrapper. The shell-layer gap is untested in the committed suite.
- Fix required: commit the working-tree change to `ai_review_openai.sh` and add a companion test that invokes the shell wrapper script (via `subprocess.run(["bash", str(SHELL_SCRIPT)], ...)`) with `--iteration 0` and asserts exit code 64.

### MEDIUM

None.

---

## Recommendation

One HIGH finding blocks APPROVE. To unblock:

1. Commit the uncommitted `ai_review_openai.sh` change (line 36: `^[1-9][0-9]*$` regex and updated error message). This is a one-line diff already present in the working tree.
2. Add a test that exercises the shell wrapper directly (not via `run_script` which calls the Python script) with `--iteration 0` and verifies exit 64. This can be a new test in `TestPhase1CodeReviewerFixes` or a dedicated shell-wrapper integration test.
3. Update `phase-1-evidence.md` with the new test run output showing 94+ passed.

No re-architecture required. The Python implementation is complete and correct; this is purely a commit-hygiene and test-coverage gap on the shell layer.
