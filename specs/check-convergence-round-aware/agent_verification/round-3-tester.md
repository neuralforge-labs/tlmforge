# Round-3 Tester Verification

Iteration: 3 (final). Scope: verify only round-2 findings T6, T7, NEW-1, NEW-2.

---

## T6 — Phase 4 integration test ambiguous "retry or escalate"

**Status: NOT_FIXED**

Round-2 finding: the single ambiguous test needed splitting into two deterministic
tests with pinned iteration inputs and exactly one asserted action each.

Round-2 fix claimed: test split into `_retry` (iteration=2, max=3) and `_escalate`
(iteration=3, max=3).

Evidence from README.md line 417:

> `test_integration_stage3_round_2_with_carryover_escalate` — same setup at
> `iteration=3, max_iterations=3` → all 3 missing → `action="escalate"`
> (cap hit, given `>` semantic adopted in Phase 3 — iteration > max so
> iteration=4 would also escalate; **but at iteration=3 the cap test is
> whether we have ANY findings + iteration==max → action="retry" still since
> cap_hit is False**). The split documents the boundary: cap_hit triggers AT
> iteration > max, so iteration=4 → escalate, iteration=3 → retry.

The test is named `_escalate` but the inline rationale concludes `action="retry"`.
The description contradicts its own name. An implementer reading this test entry
cannot determine which value to assert. The core ambiguity from round-1 / round-2
is still present — it migrated from "retry or escalate" to "escalate (but actually
retry)" inside the same entry.

The correct fix is to use `iteration=4, max_iterations=3` for the `_escalate`
test (matching the Phase 3 `>` semantic), not `iteration=3, max_iterations=3`.
That would make the name, description, and asserted value consistent. Alternatively,
the current reasoning at line 417 shows the correct answer is `retry` for
iteration=3,max=3 — so this test should be renamed `_retry_at_cap_boundary` and
assert `action="retry"`, then a separate entry with iteration=4 asserts `action="escalate"`.

**File:line:** README.md:417

---

## T7 — Phase 2 test descriptions omit real role names (hyphenated)

**Status: NOT_FIXED**

Round-2 finding: Phase 2 test list contains no test explicitly using
`code-reviewer` or `red-team-reviewer` as role-name inputs.

Round-2 fix: deferred to Stage 4 implementation ("minor wording clarification").

README.md lines 308-316 (Phase 2 test list) are unchanged. No test in Phase 2
names `code-reviewer` or `red-team-reviewer` explicitly. Phase 4 tests (lines
418-419) DO name `code-reviewer`, `tester`, `phase-auditor`, `ux-reviewer` — but
those are integration tests for the phase-end loader, not unit tests for the
path-construction logic in `load_stage3_round_jsons`. A future refactor that
mangled hyphenated role name handling in the Stage 3 loader would still have no
test catching it.

Deferring to implementation is acceptable here since this is a plan-level
specification gap (not a runtime logic error), but it means the plan does NOT
cover this path and the round-2 verdict of NOT_FIXED stands.

**File:line:** README.md:308-316

---

## NEW-1 — Plan self-contradictory on shim (5 sections still describe deprecated approach)

**Status: PARTIALLY_FIXED**

Round-2 finding: 5 sections still referenced the old shim/DeprecationWarning
approach. Scope "In", Architecture diagram, Risk audit F3, Decisions made, and
TDD table row for Phase 3.

Evidence of fixes applied:
- README.md:38 — Scope "In" now says "REMOVE `evaluate_stage5_two_tier` entirely" — FIXED
- README.md:141-145 — Architecture diagram says "REMOVED...DELETED in Phase 3" — FIXED
- README.md:440 — Risk audit F3 says "REMOVE function entirely. No shim" — FIXED
- README.md:462-467 — Decisions made says "REMOVED, not deprecated...ImportError" — FIXED
- README.md:522 — Verification criterion #5 says "does NOT exist...raises ImportError" — FIXED

Remaining stale location:
- README.md:508 (TDD plan table row for Phase 3) still reads:
  `| 3 | (extends above) | evaluate_stage5_dual single-shot semantics; **deprecation warning** | RED before impl |`

The phrase "deprecation warning" in the TDD table describes what the Phase 3
tests verify. With the function removed (not deprecated), there is no deprecation
warning to test — the plan instead calls for `test_evaluate_stage5_two_tier_removed`
which asserts `ImportError` (README.md:387). The table row has not been updated
to reflect this, creating a residual contradiction that will mislead an implementer
scanning the TDD plan table.

**File:line:** README.md:508

---

## NEW-2 — Test count floor stale

**Status: FIXED**

README.md:519 now reads:
`Test count >= 45 (Phase 0: ~17, Phase 1: ~15, Phase 2: ~9, Phase 3: ~6, Phase 4: ~5 — post round-1 expansion; total ~52)`

Raised from >= 25 to >= 45 with per-phase breakdown. Matches round-1-fixes.md
updated totals.

---

## Summary

| Finding | Round-2 status | Round-3 status |
|---|---|---|
| T6 — Phase 4 ambiguous retry/escalate | PARTIALLY | NOT_FIXED |
| T7 — Phase 2 hyphenated role names | NOT_FIXED | NOT_FIXED (deferred, acknowledged) |
| NEW-1 — Shim contradiction in 5 sections | medium | PARTIALLY_FIXED (1 of 5 sections missed: TDD table line 508) |
| NEW-2 — Test count floor stale | low | FIXED |

## Verdict: needs_revision

Two issues prevent approval:

1. T6 is still broken. The `_escalate` test entry (README.md:417) has a
   self-contradicting description that concludes `action="retry"` for the
   same inputs the test is supposed to assert `action="escalate"`. An
   implementer WILL get this wrong. Minimum fix: change the `_escalate` test to
   use `iteration=4, max_iterations=3` (which actually produces escalate under
   the `>` semantic).

2. NEW-1 has one remaining stale location (README.md:508 "deprecation warning"
   in TDD table). This is a one-word fix but it perpetuates the exact
   contradiction that caused round-1 and round-2 findings.

T7 is a known deferred gap — not a blocker for this round since it was explicitly
deferred to implementation.
