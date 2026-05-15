# enforcement-hooks — Final Audit (Architect Reviewer)

**Stage 5, single-shot. No iteration.**
**HEAD SHA (verdict_sha):** `4620576376dc3ff5c7a32160519acff2e3f8f39f`
**Scope:** `git diff def6757..HEAD` — Phases 0 through 5.

---

## VERDICT: NEEDS_REVISION

---

## Summary

The enforcement-hooks feature delivers a structurally sound three-hook discipline layer. The core design is correct — hook wiring, fail-open semantics, JSONL transcript detection, SHA normalization, PSR workflow, and the active-feature marker lifecycle all hold together. Two cross-phase issues rise to the level that prevent a clean APPROVE: a spec-vs-implementation contract gap (the marker-file fallback for Hook 2 was planned in Phase 0 but never implemented, leaving a silent fail-open when `transcript_path` is absent), and a scope-of-interception decision (Hook 3 intercepts `gh pr create` but the master plan explicitly decided NOT to, creating an undocumented behavioral deviation). Both are minor in isolation but together represent a gap between what the plan promised, what the audit trail says, and what ships.

---

## Cross-Phase Contract Consistency

### verdict_sha closed loop — SOUND

The loop is: `review_schema.json` adds the optional `verdict_sha` field → SKILL.md Stage 5 launch prompt instructs reviewers to run `git rev-parse HEAD` and record it → `final_audit_*.json` files carry the field → Hook 3 reads it, normalizes via `git rev-parse <sha>`, and compares to HEAD. All four links are present and consistent.

One deliberate design tension: the schema marks `verdict_sha` as optional (not in `required`) because Stage 3 and Stage 5 files share the schema. This is a known accepted deviation from the original spec wording (which said "required"). The field description in `review_schema.json` (line 31) documents this explicitly: "Intentionally not in the top-level 'required' array because Stage 3 and Stage 5 files share this schema — Hook 3 enforces its presence at runtime on Stage 5 files." The loop is closed; the schema-level optionality is compensated at the hook level. Accept this as the correct pragmatic resolution.

### Active-feature marker lifecycle — SOUND with one gap

Stage 1 write (SKILL.md line 189–199) and Stage 7 delete (SKILL.md line 1139–1147) are both present with Python snippets. The lifecycle instruction explicitly handles interruption: "If Stage 1 is interrupted (gate fires, user abandons), the marker stays — it is harmless and idempotent to re-write." Hook 3's pass-through condition when the marker is absent (line 83–88 of enforce_post_stage5_review.py) means a stale marker left from an abandoned feature will scope Hook 3 to that abandoned feature's audit files indefinitely. This is a low-severity operational gap: if Feature A is abandoned mid-way (marker written, Stage 7 never reached), Feature B's commits will be gated against Feature A's audit directory — which has no `final_audit_*.json` files — so Hook 3 passes through anyway. The practical impact is near-zero: Hook 3 will silently mis-scope its glob but always pass through since there are no audit files. No runbook entry or user-facing documentation exists for this case. This is the accepted behavior per the SKILL.md language "harmless and idempotent to re-write," but the implicit assumption is that Hook 3 will pass through, which only holds while Feature A has no audit files. If Feature A ever gets partial audit files before being abandoned, Feature B's commits would be gated against those. **LOW severity; document the assumption explicitly or add a staleness check.**

### Hook ordering and composition — SOUND

Both Hook 2 and Hook 3 are `PreToolUse[Bash]` entries. On a `git commit` command:
1. Hook 2 fires: checks skill-invoked-in-window OR override phrase. If Claude ran the skill before committing (normal Deep path), Hook 2 passes through.
2. Hook 3 fires: checks HEAD vs verdict_sha.

These compose correctly: Hook 2 gates pre-work discipline; Hook 3 gates post-work audit coverage. They are independent checks with no shared state beyond the transcript file. There is no scenario where Hook 2 blocks what Hook 3 would allow — their block conditions are orthogonal. No ordering issue.

One edge: if a user runs `git commit` directly in a subagent context (no user messages), Hook 2 passes through (EC-1 path) and Hook 3 fires. This is correct: Stage 4 subagents commit at phase end; Hook 3 should still enforce the Stage 5 gate for those commits.

### PSR naming vs Stage 5b — SOUND

SKILL.md line 958–959: "Do not call these files 'Stage 5b' — that name is reserved for spec-drift review (see LL-2 section below). The correct term is 'PSR' (post-Stage-5 re-review)." LL-2 (line 1374–1377) defines Stage 5b as spec-drift review. The two are clearly separated. The PSR subsection is self-contained and does not reference or collide with Stage 5b. No naming confusion remains in the shipped text.

---

## Critical Issues

**None rising to CRITICAL at the cross-phase level.** The C-1 finding from phase-3-verification (missing `test_hook3_verdict_sha_not_in_history`) was resolved in Phase 3: `test_sha_not_in_repo_history_blocks` (line 280 in test_hook3.py) uses a phantom SHA (`"a" * 40`) and asserts exit 2. The test is sound.

---

## High Issues

### H-1: Hook 3 intercepts `gh pr create` — contradicts master plan decision

`enforce_post_stage5_review.py` line 16–18:
```python
GIT_MUTATION_RE = re.compile(
    r'^\s*(git\s+commit|git\s+push|gh\s+pr\s+(merge|create))',
```

The master plan (README.md) explicitly decided: "Hook 3 does NOT gate `gh pr create` (commit/push/merge enough)." This was listed as informational default #4 in the open questions section and carried forward into the Decisions Made section as the accepted resolution. The implementation contradicts this decision by also intercepting `gh pr create`.

This is not a correctness defect in isolation — intercepting `gh pr create` is defensible — but it is an undocumented scope change that:
(a) violates the explicitly documented decision in the master plan
(b) is not tested (no test exercises a `gh pr create` command against Hook 3)
(c) would surprise operators who read the README (which documents only `git commit` / `git push` / `gh pr merge`)
(d) the phase-3-evidence.md doesn't mention this addition

The deviation went unnoticed because the phase-auditor's scope contract table didn't call it out, and the integration test (`test_integration.py`) only tests `git push`.

**Fix:** Either (a) remove `|create` from the regex and document that `gh pr create` is not gated (aligning with the decision), OR (b) update the master plan Decisions Made section and README to document that the scope was extended to include `gh pr create`, and add a test for it.

### H-2: Marker-file fallback for Hook 2 — planned but not implemented, fails open silently

The master plan (README.md lines 136, 230, 310) describes a marker-file fallback for Hook 2: when `transcript_path` is absent from stdin, Hook 1 writes `~/.claude/tlmforge_skill_invoked_<session_id>` and Hook 2 reads it. Phase 0 evidence confirms `transcript_path` IS present in PreToolUse payloads (via existing ExitPlanMode hook evidence) and commits to "primary path is transcript-based" — but the fallback was still planned as a safety net.

The shipped `enforce_skill_invoked.py` has no marker-file fallback. When `transcript_path` is absent (lines 39–43), it warns to stderr and exits 0 (fail-open). This means any Claude Code version that omits `transcript_path` from PreToolUse payloads silently disables Hook 2 enforcement.

This is acceptable **only** if the empirical Phase 0 validation is conclusive and `transcript_path` is guaranteed stable across Claude Code versions. The phase-0-evidence.md says it was verified against the existing ExitPlanMode hook — which is an indirect confirmation (not a direct live PreToolUse capture). The marker-file fallback exists in the plan but not in the code.

**Fix:** Either (a) explicitly document in README and SKILL.md that the fallback was dropped because `transcript_path` is confirmed stable, OR (b) implement the fallback. At minimum, the README's hook behavior table should note the dependency on `transcript_path`.

---

## Warnings

### W-1: Stage 0 early-exit — guidance is heuristic, not mechanical

SKILL.md Stage 0 (lines 97–110) instructs Claude to exit "if the user's prompt is conversational, exploratory, or read-only." Examples: "what does this file do?", "explain X", "summarize Y." This is prose guidance to an LLM — there is no mechanical trigger. The boundary between "explain X" (Stage 0 exit) and "explain X and then fix it" (Deep path) is inherently fuzzy.

This is a known limitation of the design: Hook 1 fires on every prompt, the skill decides whether to exit. The plan explicitly chose "no keyword classification" per feedback memory. The Stage 0 prose is as specific as it can be given the constraint. Not a defect — but reviewers should know this is the weakest link in the enforcement chain: a misclassification at Stage 0 leaks past all gates with no mechanical backstop.

### W-2: Compound bash commands bypass Hook 3

`cd /repo && git commit -m "msg"` does not match `GIT_MUTATION_RE` because the regex anchors to the start of the command string. The plan explicitly deferred this as EC-10 with "Low real-world frequency." The deferral is documented in SUMMARY.md. Acceptable as a known gap.

### W-3: `gh pr create` test coverage absent

If `gh pr create` is intentionally in scope (see H-1), there is no test asserting that a `gh pr create` command is intercepted and blocked after HEAD drift. The integration test only tests `git push`. This is either a missing test (if `gh pr create` stays) or a code removal (if it's removed per H-1).

### W-4: TDD RED phase not captured in evidence

Phase 3 evidence shows only GREEN output. The phase-auditor noted this (MEDIUM-1); it persists into the final state. The discipline requirement is RED before GREEN. The absence of RED evidence means the audit trail cannot prove TDD was followed rather than tests-written-after-implementation.

---

## Suggestions

### S-1: Abandoned-feature runbook entry

SKILL.md says the marker is "harmless and idempotent to re-write" if interrupted. Consider adding a one-line operator note: "To clean up a stale marker from an abandoned feature, delete `specs/.tlmforge_active_feature`." Currently a user who abandons a feature mid-way would need to know this implicitly.

### S-2: Hook 3 block message could include HEAD drift count

The current block message (enforce_post_stage5_review.py lines 21–33) says "HEAD has changed since the final audit" but does not show how many commits ahead. The original spec specified showing N commits ahead (e.g., "3 commits ahead"). The implementation omits this. Not blocking, but useful for operator context.

### S-3: Multi-value `TLMFORGE_HOOKS` variants not tested in hook3-specific tests

`test_env.py` covers all variants; `test_hook3.py` only tests `"0"`. The phase-auditor noted this (LOW). Since `test_env.py` unit-tests `is_hooks_disabled()` exhaustively and all three hooks call that function, this is covered at the unit layer. The integration gap is minor.

---

## What's Good

- **Empirical Phase 0 validation.** The plan required live session capture before any transcript-parsing code was written. This is exactly the right discipline for API-shape uncertainty. The captured fixture (`skill_invocation_sample.jsonl`) anchors the detection logic to reality.

- **PSR marker double-validation.** Hook 3 validates both the filename pattern (`final_audit_*_psr_<HEAD>.json`) and the internal `verdict_sha` field. A file copied/renamed to bypass the gate is rejected. This is correct defensive design.

- **`@fail_open` implementation.** The decorator correctly re-raises `SystemExit` (so `sys.exit(2)` blocks propagate), catches `Exception` for genuine crashes, and falls through to `sys.exit(0)` after normal returns. No edge case missed.

- **Subagent pass-through (EC-1).** Hook 2 explicitly detects zero-user-message sessions and passes through immediately. Without this, Stage 3/4 reviewer subagents would be permanently blocked. This was identified in Stage 3 and correctly implemented.

- **SHA normalization for short/rebased SHAs.** `_normalize_sha()` calls `git rev-parse <sha>` to expand short SHAs and gracefully returns `""` if the SHA is unreachable, then continues to block (phantom SHA → no match → block). The EC-8 test covers this.

- **Active-feature marker scoping.** The `specs/.tlmforge_active_feature` design cleanly solves multi-feature cross-contamination. Single-feature-at-a-time is the right assumption for a sequential workflow tool.

- **120 passing tests, 0 regressions.** Test coverage is comprehensive across unit, integration (subprocess-based hook invocation), and E2E (full lifecycle in test_integration.py). The test infrastructure (conftest.py fixtures, tmp_git_repo helpers) is well-structured and reusable.

- **Stage 3 convergence was genuine.** The SUMMARY.md shows 10 real categories of bugs found and fixed across 3 rounds — wrong API shapes, wrong file paths, unverified assumptions, missing override logic. The process caught real issues before implementation, which is exactly the purpose of Stage 3.
