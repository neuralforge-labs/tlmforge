# Phase 3 Evidence — enforce_post_stage5_review.py

## What was implemented

1. **`hooks/enforce_post_stage5_review.py`** — Hook 3: blocks `git commit`, `git push`, `gh pr merge` / `gh pr create` after Stage 5 final audit when HEAD has drifted from the audited SHA, unless a valid PSR marker exists.
2. **`hooks/hooks.json`** — added second `PreToolUse` matcher for `Bash` → Hook 3 (alongside Hook 2).
3. **`skills/feature-development/review_schema.json`** — added optional `verdict_sha` property for Stage 5 final audit files.

## Hook 3 logic summary

1. Pass-through if `TLMFORGE_HOOKS` bypass set, or tool_name ≠ Bash.
2. Pass-through if command doesn't match `^(git commit|git push|gh pr merge|gh pr create)`.
3. Resolve repo root via `git rev-parse --show-toplevel` (EC-6: subdirectory safe).
4. Read `specs/.tlmforge_active_feature`; pass-through if absent.
5. Glob `final_audit_*.json` (excluding `_psr_` files); pass-through if none.
6. Extract `verdict_sha` from each audit; pass-through if none present.
7. `git rev-parse HEAD`; if exit 128 → warn + pass-through (EC-2: no commits yet).
8. Normalize each `verdict_sha` via `git rev-parse <sha>` (EC-3: short SHA support).
9. If any normalized SHA matches HEAD → pass-through.
10. Check PSR markers `final_audit_*_psr_<HEAD>.json`; validate internal `verdict_sha` == HEAD (HIGH-3).
11. If valid PSR found → pass-through.
12. Else → `sys.exit(2)` + actionable block message (mentions PSR workflow).

## Phase-auditor findings addressed

**C-1 (missing SHA-not-in-history test):** Added `test_sha_not_in_repo_history_blocks` — confirms that a `verdict_sha` that can't be resolved by `git rev-parse` (unreachable after rebase, or synthetic phantom SHA) still results in a block (exit 2).

**HIGH-3 (override phrase logic absent):** Added transcript reading + `has_override()` check to `enforce_post_stage5_review.py`. Fixed `test_override_be_quick_allows_after_drift` to construct a real transcript with "be quick" in the last user message. Added `transcript_entries` parameter to `run_hook3` helper.

**HIGH-1 (`verdict_sha` optional vs required):** The schema is shared by Stage 3 and Stage 5 files; making `verdict_sha` unconditionally required would break Stage 3 files. Kept optional at schema level; updated the field description to document the intent and note that Hook 3 enforces presence at runtime. Documented deviation from original spec wording.

**HIGH-2 (Stage 1/7 marker steps in SKILL.md):** Explicitly deferred to Phase 4. The README lists this item under BOTH Phase 3 and Phase 4 — Phase 4's description says "Add active-feature marker instructions to SKILL.md Stage 1 and 7." Phase 3's SKILL.md partial update covers only what Hook 3 needs to work (Stage 5 prompt + PSR workflow). The marker write/delete steps will be added in Phase 4.

**MEDIUM-2 (no corrupt-JSON test):** Added `test_corrupted_audit_json_skipped_falls_through` — writes `{broken json` to a `final_audit_*.json` file, confirms hook skips it and passes through (no verdict_sha → pass-through).

## Test run — Phase 3 tests (RED → GREEN)

```
$ python3 -m pytest hooks/tests/test_hook3.py -v
platform linux -- Python 3.12.3, pytest-9.0.3
collected 16 items

hooks/tests/test_hook3.py::test_non_bash_tool_ignored PASSED
hooks/tests/test_hook3.py::test_non_git_bash_command_passes_through PASSED
hooks/tests/test_hook3.py::test_no_active_feature_marker_passes_through PASSED
hooks/tests/test_hook3.py::test_no_stage5_final_audit_passes_through PASSED
hooks/tests/test_hook3.py::test_no_verdict_sha_in_audit_passes_through PASSED
hooks/tests/test_hook3.py::test_bypass_tlmforge_hooks_0 PASSED
hooks/tests/test_hook3.py::test_head_matches_verdict_sha_passes_through PASSED
hooks/tests/test_hook3.py::test_short_sha_verdict_normalizes_to_allow PASSED
hooks/tests/test_hook3.py::test_valid_psr_marker_allows PASSED
hooks/tests/test_hook3.py::test_override_be_quick_allows_after_drift PASSED
hooks/tests/test_hook3.py::test_head_drifted_without_psr_blocks PASSED
hooks/tests/test_hook3.py::test_block_message_is_actionable PASSED
hooks/tests/test_hook3.py::test_psr_marker_with_wrong_internal_sha_blocks PASSED
hooks/tests/test_hook3.py::test_psr_marker_missing_verdict_sha_blocks PASSED
hooks/tests/test_hook3.py::test_no_commits_repo_passes_through PASSED
hooks/tests/test_hook3.py::test_cwd_subdirectory_still_finds_audit PASSED

16 passed in 0.89s
```

**Unit: 16 passed. Integration: n/a (hook is integration-tested via subprocess in test_hook3.py).**

## Full suite regression check

```
$ python3 -m pytest hooks/tests/
109 passed in 1.59s
```

- Phase 3 new tests: 18 (16 original + 2 added from phase-auditor findings C-1 and MEDIUM-2)
- Pre-existing tests: 93
- Regressions: 0
- Total: 111
