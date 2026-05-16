# Round 1 Tester Review — multi-llm-reviewers

**Verdict: needs_revision** — 7 CRITICALs, 3 HIGHs identified.

## Summary

The plan's general shape (exit-code contract, skipped-JSON sidecar, env-var opt-in,
no changes to check_convergence.py) is correct. However, the plan contains 7 critical
failure modes that will cause bugs in production: schema-invalid error output, silent
false approvals on empty diffs, truncated responses accepted silently, uppercase enum
values bypassing convergence, wrong file reviewed on missing marker, missing output
directory causing undefined exit code, and reviewer field mismatch causing permanent
meta CRITICALs.

## CRITICAL Findings

**EC-1** (bug): Error handler missing `suggested_fix` on synthetic CRITICAL — blocks
convergence permanently with no actionable message. Fix: mirror Gemini `write_error()`
exactly, with `json.dumps()`.

**EC-2** (logic_error): `mode=code` with empty diff silently produces `status=ok` approve
at Stage 3 before any code exists. Fix: check for empty diff, write_skipped exit 2.

**EC-3** (data_loss): Truncated OpenAI response (`finish_reason=length`) but valid JSON
accepted as complete. Fix: check truncation flag, retry, fail to skipped.

**EC-4** (logic_error): OpenAI uppercase severity ("CRITICAL") passes shape validation
but `check_convergence.py`'s case-sensitive comparison ignores it — silent false
convergence. Fix: validate enum values before accepting response.

**EC-5** (bug): Absent active-feature marker + double-slash path resolves to
`specs/README.md` (wrong document). Fix: explicit marker existence check.

**EC-6** (missing_error_handling): Missing output parent directory causes exit 1
(undefined), no sidecar written. Fix: check dirname exists, exit 64 if not.

**EC-7** (bug): `reviewer` field not pinned to `"openai"` — if derived from model name,
key mismatch causes permanent `reviewer_json_missing` meta CRITICAL. Fix: hardcode
`REVIEWER_NAME = "openai"`.

## HIGH Findings

**EC-8**: Non-integer `--iteration` causes undefined exit code. Fix: validate and exit 64.

**EC-9**: Feature name with spaces causes bash word-splitting. Fix: quote subshell
expansions; validation regex also catches spaces.

**EC-10**: No test for schema enum mismatch in test plan — highest-value missing test.
Fix: add to Phase 1 plan.

## Edge Cases Properly Handled

- Graceful skip on missing flag/key/SDK — designed correctly
- Retry once on invalid JSON — matches Gemini script pattern
- `status=skipped` sidecar always written before exit 2 — convergence clean
- Both flag AND key required — prevents surprise billing

## Carryover

See `tester_edge_cases.json` — 15 scenarios for Stage 4 TDD seeding.
