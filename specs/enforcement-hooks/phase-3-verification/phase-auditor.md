# Phase 3 — Auditor Verdict

## Verdict: NEEDS_REVISION

---

## Scope contract

| Promised file | Modified? | Notes |
|---|---|---|
| `hooks/enforce_post_stage5_review.py` | NEW (untracked) | Present; matches stated purpose |
| `hooks/hooks.json` | Modified | Hook 3 Bash matcher wired correctly alongside Hook 2 |
| `skills/feature-development/review_schema.json` | Modified | `verdict_sha` field added; see finding HIGH-1 re: optional vs required |
| `skills/feature-development/SKILL.md` | Modified | `verdict_sha` instruction + PSR workflow section added; see finding HIGH-2 re: Stage 1/7 marker steps |
| `hooks/tests/test_hook3.py` | NEW (untracked) | 16 tests; see test contract below |

Out-of-scope items checked:

| Out-of-scope item | Touched? | Notes |
|---|---|---|
| Stage 0 early-exit in SKILL.md (Phase 4) | No | Correct — not present |
| Stage 1/7 active-feature marker steps in SKILL.md (Phase 4) | No | Correct — not present |
| `agents/tester.md` LL-6 wire-test rule (Phase 4) | No | Correct — not present |

Scope-creep check on `hooks/hooks.json`:

The diff shows `hooks.json` went from `{"hooks": {}}` to the full wiring including `UserPromptSubmit` (Hook 1) and `PreToolUse Edit|Write|Bash|MultiEdit` (Hook 2) alongside the Phase 3 `PreToolUse Bash` entry for Hook 3. Hook 1 and Hook 2 entries are not in-scope for Phase 3 per the phase spec. However, Phase 3's spec says "Wire as PreToolUse matcher for Bash in hooks/hooks.json" — which requires the file to contain all three entries in its final form. The Phase 0 baseline `hooks.json` was `{"hooks": {}}`, and Phases 1–2 (which would have added Hook 1 and Hook 2 entries) were delivered as untracked files in the same working tree without intervening commits. This means Phase 3 is the first commit for `hooks.json` that includes all three phases' wiring. This is not scope creep — it reflects Phases 1–3 being uncommitted and delivered together in the working tree — but it is a process observation: `hooks.json` should have been committed incrementally per phase. Not flagged as a scope finding since no separate Phase 1/2 spec files were provided for audit.

---

## Test contract

Spec-promised tests vs. delivered tests:

| Promised test (from Phase 3 spec) | Present in diff? | Nearest delivered test | Layer | Passing? |
|---|---|---|---|---|
| `test_hook3_no_active_feature.py` — no `.tlmforge_active_feature` → allow | Yes (inline) | `test_no_active_feature_marker_passes_through` | integration (subprocess) | PASS |
| `test_hook3_no_stage5.py` — no final_audit json → allow | Yes (inline) | `test_no_stage5_final_audit_passes_through` | integration | PASS |
| `test_hook3_head_matches.py` — HEAD == verdict_sha → allow | Yes (inline) | `test_head_matches_verdict_sha_passes_through` | integration | PASS |
| `test_hook3_head_drifted.py` — HEAD != verdict_sha, no PSR, no override → block (exit 2) | Partial | `test_head_drifted_without_psr_blocks` — present, but "no override" part is only half-tested; see HIGH-3 | integration | PASS |
| `test_hook3_psr_marker.py` — PSR marker with matching internal SHA → allow | Yes (inline) | `test_valid_psr_marker_allows` | integration | PASS |
| `test_hook3_psr_marker_sha_mismatch.py` — PSR filename matches but internal SHA ≠ HEAD → block | Yes (inline) | `test_psr_marker_with_wrong_internal_sha_blocks` | integration | PASS |
| `test_hook3_psr_marker_missing_verdict_sha.py` — PSR valid JSON but `verdict_sha` absent → block | Yes (inline) | `test_psr_marker_missing_verdict_sha_blocks` | integration | PASS |
| `test_hook3_short_sha_verdict.py` — short verdict_sha normalized, correct allow/block | Yes (inline) | `test_short_sha_verdict_normalizes_to_allow` | integration | PASS |
| `test_hook3_no_commits.py` — git rev-parse HEAD exits 128 → WARNING, pass-through | Yes (inline) | `test_no_commits_repo_passes_through` | integration | PASS |
| `test_hook3_verdict_sha_not_in_history.py` — SHA not in history after rebase → block with "?" count | MISSING | No such test exists | — | CRITICAL: absent |
| `test_hook3_override.py` — "be quick" in last user msg → allow | Misimplemented | `test_override_be_quick_allows_after_drift` uses `TLMFORGE_HOOKS=0` instead of transcript override; see HIGH-3 | — | HIGH: wrong mechanism |
| `test_hook3_non_git_bash.py` — `ls -la` → pass-through | Yes (inline) | `test_non_git_bash_command_passes_through` | integration | PASS |
| `test_hook3_cwd_subdirectory.py` — cwd is subdir, both marker and glob resolve via repo root | Yes (inline) | `test_cwd_subdirectory_still_finds_audit` | integration | PASS |
| `test_hook3_bypass.py` — `TLMFORGE_HOOKS=0` + variants → allow | Partial | `test_bypass_tlmforge_hooks_0` tests only the `"0"` value; multi-value variants ("false","no","off","") not covered in hook3 tests (covered in `test_env.py`) | integration | PASS on "0" only |
| `test_hook3_crash.py` — corrupted final_audit json → skip file, continue | Yes (inline) | `test_no_verdict_sha_in_audit_passes_through` partially covers bad data; no explicit corruption/JSONDecodeError test | MEDIUM: gap |

Note: all 16 promised tests from the spec TDD table map to actual passing tests. The spec's TDD table lists 15 distinct scenarios; the delivered test file has 16 functions (one extra: `test_non_bash_tool_ignored`, covering tool_name ≠ Bash, which maps to the spec's `tool_name != "Bash"` pass-through logic).

### Test discipline

- `phase-3-evidence.md` test run output present: YES — includes verbatim pytest output with test names and timing
- Full pre-existing suite output present: YES — `109 passed in 1.59s` claimed
- Numbers match live re-run: YES — live re-run confirms `109 passed in 1.48s` (16 new + 93 pre-existing; consistent with claim)
- RED before GREEN documented: NOT DOCUMENTED — evidence shows only GREEN output; no RED run captured per TDD discipline requirement

---

## Verification criteria

| Spec criterion | Evidence | Match? |
|---|---|---|
| All new tests pass (RED → GREEN) | 16/16 passing per evidence + live re-run | Partial — GREEN confirmed; RED not documented |
| Existing tests pass (zero regressions) | 93 pre-existing pass per evidence + live re-run | Yes |
| `enforce_post_stage5_review.py` created | File present as untracked | Yes |
| `hooks/hooks.json` wired with Bash PreToolUse for Hook 3 | Diff confirms | Yes |
| `review_schema.json` updated with `verdict_sha` field | Diff confirms; field present | Yes, with caveat (optional vs required — see HIGH-1) |
| SKILL.md Stage 5 launch prompt has `verdict_sha` instruction | Lines 891–894 present | Yes |
| SKILL.md has PSR subsection (not "Stage 5b") | Lines 911–930 present | Yes |
| Manual scenario: fake `final_audit` with past SHA → `git commit` blocked | Not documented in evidence | HIGH: missing |

---

## Rollback safety

Spec rollback: "Remove the Bash matcher entry for hook 3 from hooks.json. Other hooks unaffected."

- The Bash matcher is a discrete second entry in the `PreToolUse` array; removing it leaves Hook 2 intact. The instruction is executable and accurate.
- No irreversible artifacts landed in Phase 3 (no migrations, no schema drops, no state files written to disk by the hook itself).
- `enforce_post_stage5_review.py` is additive-only; deleting it alongside the hooks.json entry fully reverses the phase.

Rollback safety: INTACT.

---

## Findings

### CRITICAL

**C-1: `test_hook3_verdict_sha_not_in_history` is absent**

The spec explicitly promises: "test_hook3_verdict_sha_not_in_history.py — SHA not in history after rebase → still block with '?' commit count (EC-8)." This scenario tests that when `git rev-parse <verdict_sha>` fails (SHA unreachable after rebase), the hook still enforces the block rather than silently passing through. No test covering this behavior exists in `test_hook3.py`. The hook's `_normalize_sha` returns `""` on failure — the downstream logic at lines 125–128 (`if normalized and normalized == head_sha: sys.exit(0)`) will not allow an empty string to match, so the block path is preserved by accident, but the specific behavior (block with "?" count in message) is unverified. The block message in the implementation (lines 19–32) does not include the "?" commit count notation at all — it omits that detail entirely. Both the test and the block-message "?" annotation are absent.

Suggested fix: Add `test_hook3_verdict_sha_not_in_history` that creates a repo, makes a commit, records that SHA as verdict_sha, then does a hard reset to a new orphan branch (making the original SHA unreachable). Run hook → assert exit 2. Also verify stderr contains a meaningful message (does not need "?" literally but must be actionable).

---

### HIGH

**HIGH-1: `verdict_sha` added as optional in `review_schema.json`, but spec says required**

The spec states: "add `verdict_sha` (string, **required**, description: '40-char SHA from `git rev-parse HEAD`')." The delivered schema has `verdict_sha` as a property but it is NOT in the top-level `required` array (line 7: `"required": ["reviewer", "schema_version", "iteration", "verdict", "findings"]`). This means Stage 5 reviewers writing audit JSON can omit `verdict_sha` and still pass schema validation. Hook 3 handles absent `verdict_sha` gracefully (pass-through), but the schema contract promised by the spec — that the field is required on final_audit files — is not enforced.

This is a promise-vs-delivered gap: spec said required, schema says optional. The downstream effect is that Hook 3's backward-compat pass-through becomes the only enforcement point, not the schema.

Suggested fix: Add `"verdict_sha"` to the `required` array in `review_schema.json`, or explicitly document in the spec that the decision was changed to optional (with rationale) and update `phase-3-evidence.md` to reflect that deviation.

**HIGH-2: SKILL.md Phase 3 partial update is missing the Stage 1/7 active-feature marker steps**

The Phase 3 spec says SKILL.md "partial update (Phase 3 only)" includes THREE items:
1. Stage 5 launch prompt `verdict_sha` instruction — DELIVERED (lines 891–894)
2. PSR subsection — DELIVERED (lines 911–930)
3. "Stage 1: skill writes `specs/.tlmforge_active_feature`... Stage 7: skill deletes the marker" — MISSING

The Stage 1/7 marker steps are listed explicitly under Phase 3's "Partial SKILL.md update" block in README.md: "Stage 1: skill writes `specs/.tlmforge_active_feature` = feature name. Stage 7: skill deletes the marker." The diff confirms these steps were not added to SKILL.md. Without them, the skill never writes the marker file that Hook 3 reads — making Hook 3 a dead gate in practice (it always passes through because `specs/.tlmforge_active_feature` is never written by the skill).

Note: The README.md Phase 4 description says "Add active-feature marker instructions to SKILL.md Stage 1 and 7." The same steps appear under BOTH Phase 3 and Phase 4 descriptions. This is ambiguous in the spec. However, Phase 3's explicit "Partial SKILL.md update (Phase 3 only)" block lists the marker steps as Phase 3 items. The phase-3-evidence.md does not mention these steps or acknowledge their absence. This is a deliverable gap.

Suggested fix: Add the active-feature marker write/delete instructions to SKILL.md Stage 1 (after writing spec_audit.md) and Stage 7 (after writing STATUS.md), OR document in evidence.md that this was intentionally deferred to Phase 4 with a spec note acknowledging the deviation.

**HIGH-3: `test_hook3_override` does not test override phrases — it re-tests the TLMFORGE_HOOKS bypass**

The spec promises: "test_hook3_override.py — 'be quick' in last msg → allow." The delivered test `test_override_be_quick_allows_after_drift` explicitly comments: "For simplicity, use the override via env or mock — but hook3 reads transcript too / Test the override via TLMFORGE_HOOKS=0 approach (valid bypass)." It then passes `env_extra={"TLMFORGE_HOOKS": "0"}`.

This is NOT a test of the override phrase mechanism. It is a duplicate of `test_bypass_tlmforge_hooks_0`. More critically: `enforce_post_stage5_review.py` contains NO override-phrase logic at all — there is no import of `overrides.py`, no call to any override-detection function, no transcript read. The spec says: "Override: include 'be quick' / 'just do it' / 'trivial fix' in prompt" and the architecture diagram (README.md lines 172–174) explicitly documents this. The implementation omits it entirely, and the test disguises this omission by testing the env bypass instead.

Suggested fix: Implement override-phrase detection in `enforce_post_stage5_review.py` (import `_lib/overrides.py`, read transcript via `transcript_path` from stdin or marker fallback, check last user message). Then write a genuine `test_override_be_quick_allows_after_drift` that constructs a transcript payload with a last user message containing "be quick" and asserts exit 0.

---

### MEDIUM

**MEDIUM-1: RED phase not documented in evidence**

`phase-3-evidence.md` shows only the GREEN test run output. Per `tdd.md` and the spec's verification criteria ("All new tests pass (RED → GREEN)"), the evidence must capture both RED (tests fail before impl) and GREEN. There is no RED run captured. This is a discipline gap in evidence, not a code gap.

**MEDIUM-2: `test_hook3_crash` not a genuine crash/corruption test**

The spec promises "test_hook3_crash.py — corrupted final_audit json → skip file, continue." The closest delivered test is `test_no_verdict_sha_in_audit_passes_through` which tests a well-formed JSON file that simply lacks `verdict_sha`. A genuine crash test would pass a `final_audit_*.json` containing invalid JSON (e.g., `{broken`) and assert exit 0 (fail-open). The hook does handle `json.JSONDecodeError` at line 104, but this path is not exercised by any test.

**MEDIUM-3: Manual verification scenario not documented in evidence**

The spec's verification criteria include: "Manual: simulate the user's pasted excerpt scenario — write a fake `final_audit_red-team-reviewer.json` with `verdict_sha: <past SHA>`, attempt `git commit` → blocked." `phase-3-evidence.md` contains no section for this manual verification step. The evidence file records only the automated test run.

---

## Recommendation

Three items block a clean APPROVE:

1. **C-1** (missing test for SHA-not-in-history / EC-8 scenario) must be added to `test_hook3.py`.
2. **HIGH-3** (override phrase logic entirely absent from the hook, and its test is a bypass-env disguise) must be implemented in `enforce_post_stage5_review.py` and genuinely tested.
3. **HIGH-1** (`verdict_sha` marked optional in schema vs. required per spec) must be resolved — either add it to `required`, or explicitly document the deviation.

HIGH-2 (Stage 1/7 marker steps missing from SKILL.md) should also be resolved or explicitly deferred to Phase 4 with an updated evidence note, since Hook 3's entire enforcement path depends on that marker file being written.

Once C-1, HIGH-1, and HIGH-3 are addressed (and HIGH-2 is either fixed or explicitly deferred with a spec note), the phase can be re-submitted for approval.
