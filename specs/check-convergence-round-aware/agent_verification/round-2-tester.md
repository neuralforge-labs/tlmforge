# Tester Round-2 Review — check-convergence-round-aware

Iteration: 2
Reviewer: tester
Date: 2026-05-12

---

## Round-1 Findings: Verdict by Finding

### T1 — _load_json_safely misses UnicodeDecodeError
**Verdict: FIXED**

Evidence: README.md Phase 1, line 211:
> `_load_json_safely` catches `(json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError)`

Line 252 adds `test_load_json_safely_non_utf8` to the Phase 1 test list.
Both the catch clause and the test are explicitly listed. Full fix confirmed.

---

### T2 — cap_hit boundary asymmetry `>` vs `>=`
**Verdict: FIXED**

Evidence: README.md Phase 0, lines 181-182:
- `test_cap_hit_iteration_eq_max_in_evaluate_convergence` pins the `>` semantic (iteration=3/max=3 → cap_hit=False)
- `test_cap_hit_iteration_eq_max_in_two_tier` pins the `>=` semantic for the old function

Phase 3, line 379 adds verification criterion:
> `iteration=3, max=3` is NOT cap_hit (resolves R1-A1/T2 asymmetry; `>` semantic survives)

Phase 3 resolves the asymmetry by removing `evaluate_stage5_two_tier` entirely, leaving only the `>` rule. Boundary pinned in Phase 0 before any code change, resolved in Phase 3. Full fix confirmed.

---

### T3 — evaluate_stage5_dual returns 'retry' instead of 'escalate' at Stage 5
**Verdict: FIXED**

Evidence: README.md Phase 3, lines 322-339 specify internal delegation:
```python
evaluate_convergence(
    reviewer_jsons={"red-team-reviewer": ..., "architect-reviewer": ...},
    expected_roles=["red-team-reviewer", "architect-reviewer"],
    iteration=1,
    max_iterations=1,
)
```
At `iteration=1, max=1` any CRITICAL triggers `cap_hit=True` → `action="escalate"`.
Phase 3 test `test_evaluate_stage5_dual_red_team_critical` (line 366) verifies
`final_converged=False, action="escalate"`. The "retry" path is structurally
impossible at this invocation. Fix confirmed.

---

### T4 — evaluate_stage5_two_tier shim silently discards non-selected tier-1 CRITICALs
**Verdict: FIXED**

Evidence: README.md Phase 3, lines 315-318:
> **REMOVE the old function entirely** — no shim, no DeprecationWarning.

No shim exists to have the discarding bug. The function is deleted in Phase 3
along with its Phase 0 characterization tests (single commit per lines 356-358).
EC5 in tester_edge_cases.json targets this path; the test becomes a removal-
verification test (`test_evaluate_stage5_two_tier_removed` at line 370). Fix confirmed.

---

### T5 — iteration=0 guard missing
**Verdict: FIXED**

Evidence: README.md Phase 1, line 229:
> **R1-T5 — iteration boundary check:** `evaluate_convergence` raises
> `ValueError("iteration must be >= 1")` at entry if `iteration < 1`.

Line 259 adds `test_iteration_zero_raises_value_error`. Fix confirmed.

---

### T6 — Phase 4 integration test has ambiguous 'retry or escalate' assertion
**Verdict: PARTIALLY FIXED**

Evidence: README.md Phase 4, line 399:
> `test_integration_stage3_round_2_with_carryover` — ... → 3 synthetic meta CRITICALs
> → `action="retry"` (or `escalate` if iteration counter says cap)

The ambiguous "or" conditional is still present verbatim. The round-1 fix asked
for this test to be SPLIT into two deterministic tests with exact iteration values.
The description was not updated. A test with two possible valid assertions is not
a test — the implementer will pick one arbitrarily and the other case will be untested.

The finding remains open. The exact test split requested (iteration=2 → retry;
iteration=4 → escalate) must be reflected in the plan.

---

### T7 — Phase 2 tests use generic role names, not hyphenated real names
**Verdict: NOT FIXED**

Evidence: README.md Phase 2, lines 291-299. The tests listed are:
- `test_load_stage3_round_jsons_all_present`
- `test_load_stage3_round_jsons_missing_one`
- `test_load_stage3_round_jsons_round_3` (line 293)
- `test_load_phase_end_round_jsons_round_1`
- etc.

None of these test descriptions specify role names. Round-1 finding asked the
plan to name roles explicitly (e.g., `code-reviewer`, `red-team-reviewer`) in
the test inputs to exercise hyphenated path construction. The descriptions still
read generically; an implementer writing these tests will naturally reach for
`architect`, `tester` (single-word) because the plan doesn't constrain them.

EC9 in tester_edge_cases.json covers this with a concrete test stub using
`code-reviewer` and `red-team`. The plan should add a test that uses those
exact role names. Not fixed in README.md.

---

## New Findings (Genuinely Missed in Round 1)

### NEW-1 — "Decisions made" section contradicts Phase 3 removal decision (medium)

README.md lines 444-448 still describe the OLD deprecation-shim approach:
> **Deprecated `evaluate_stage5_two_tier` calls `evaluate_stage5_dual`
> internally** — collapses tier-1 trio to "use whichever architect-reviewer
> appears in tier1_jsons" + tier-2 to red-team. Imperfect but back-compatible
> enough for the no-op grace period. Future cleanup removes the wrapper entirely.

Phase 3 (lines 315-318) explicitly chose REMOVAL over deprecation. This
"Decisions made" bullet was not updated. An implementer reading the plan
sequentially may see this decision and implement the shim instead of the removal.

Additionally, README.md line 503 (Verification criteria, item 5) still says:
> `evaluate_stage5_two_tier` emits `DeprecationWarning` on call

This contradicts the removal — the function won't exist after Phase 3 so
this criterion will always fail.

TDD plan table (line 489) says:
> `evaluate_stage5_dual` single-shot semantics; **deprecation warning**

Three separate places still reflect the superseded shim approach.

**Impact:** Implementer confusion — the plan says two contradictory things.
If the implementer follows "Decisions made" they build a shim; if they follow
Phase 3 they delete the function. This is a medium-severity plan defect
(not critical because Phase 3 wording is unambiguous, but the contradiction
increases the chance the implementer pauses or makes the wrong call).

**Fix:** Update "Decisions made" bullet at line 444 to read:
> **`evaluate_stage5_two_tier` is REMOVED (not deprecated).** Per round-1
> review (R1-A3/T4/TH5): shim silently discards CRITICALs and
> DeprecationWarning is suppressible. Zero in-tree callers confirmed by grep.
> Phase 0 characterization tests for this function are deleted in the same
> Phase 3 commit.

Update verification criterion #5 (line 503) to:
> `evaluate_stage5_two_tier` does NOT exist in `check_convergence.py`
> (verified by `grep -c "def evaluate_stage5_two_tier" check_convergence.py` → 0)

Update TDD plan table row for Phase 3 (line 489) to remove "deprecation warning."

---

### NEW-2 — Test count floor (line 500) is stale after Phase 1 expansion (low)

README.md line 500:
> Test count >= 25 (Phase 0: ~15, Phase 1: ~7, Phase 2: ~9, Phase 3: ~8, Phase 4: ~5)

Round-1 fixes expanded Phase 1 from ~7 to ~15 tests. Phase 3 dropped from
~8 to ~6 tests (shim removal reduced test count). The round-1 fixes summary
(round-1-fixes.md, line 163) gives the updated total as ~52. The verification
criterion should read `>= 50` or `>= 52`, not `>= 25`. At `>= 25` the
criterion is trivially satisfied and provides no guard against Phase 1 tests
being skipped.

**Fix:** Update line 500 to `Test count >= 50`.

---

## tester_edge_cases.json Carryover Artifact Verification

The carryover artifact at:
`specs/check-convergence-round-aware/agent_verification/tester_edge_cases.json`

Contains 12 edge cases (EC1–EC12).

Status after round-2 plan review:

| EC | Title | Status for Stage 4 |
|---|---|---|
| EC1 | non-UTF-8 bytes → UnicodeDecodeError | VALID — test_load_json_safely_non_utf8 is in Phase 1 list |
| EC2 | cap boundary iteration=3/max=3 (evaluate_convergence) | VALID — test_cap_hit_iteration_eq_max_in_evaluate_convergence in Phase 0 |
| EC3 | cap boundary asymmetry evaluate_stage5_two_tier | PARTIALLY VALID — the function is removed in Phase 3; EC3's test_stub targets the old function. Stage 4 implementer should note: Phase 0 characterization test EC3 pins CURRENT behavior; Phase 3 deletion removes the function and its tests. EC3's stub is valid for Phase 0 only |
| EC4 | evaluate_stage5_dual no 'retry' on CRITICAL | VALID — test_evaluate_stage5_dual_red_team_critical in Phase 3 covers this |
| EC5 | shim must not discard tier-1 CRITICALs | SUPERSEDED — function is removed, not shimmed. Stage 4 should convert EC5's goal into test_evaluate_stage5_two_tier_removed (ImportError). The EC5 stub is no longer the right test for this concern, but the underlying risk (quiet CRITICAL discard) is eliminated by removal |
| EC6 | DeprecationWarning on every call | SUPERSEDED — function removed; DeprecationWarning cannot be emitted by a removed function. Stage 4 should skip EC6 as written and rely on test_evaluate_stage5_two_tier_removed |
| EC7 | iteration=0 raises ValueError | VALID — test_iteration_zero_raises_value_error in Phase 1 |
| EC8 | Phase 4 ambiguous 'retry or escalate' assertion | OPEN — T6 above is partially fixed. Stage 4 must still split the test per EC8 stubs |
| EC9 | hyphenated role names in loader tests | OPEN — T7 above is not fixed. Stage 4 must use real role names per EC9 stub |
| EC10 | load_final_audit_jsons must not load tester_edge_cases.json | VALID — test_load_final_audit_jsons_ignores_carryover in Phase 2 |
| EC11 | path with spaces must not break path construction | VALID — no test in plan currently covers this; Stage 4 should add it |
| EC12 | phase-end round-1 uses bare path (no round-N prefix) | VALID — test_load_phase_end_round_jsons_round_1 in Phase 2 covers this partially; EC12's stub adds the negative case (wrong file is NOT used) |

Two edge cases are SUPERSEDED (EC5, EC6) due to the removal decision.
Stage 4 should treat them as: delete the superseded stubs, replace with
test_evaluate_stage5_two_tier_removed (ImportError pin).

EC3 is valid for Phase 0 only; the stub fires against unmodified code.
The carryover artifact is still correctly populated for Stage 4 consumption
with these three notes (EC3/EC5/EC6 interpretation guidance).

---

## Summary

| R1 Finding | Verdict |
|---|---|
| T1 — UnicodeDecodeError | FIXED |
| T2 — cap_hit boundary asymmetry | FIXED |
| T3 — evaluate_stage5_dual no retry | FIXED |
| T4 — shim discards tier-1 CRITICALs | FIXED (via removal) |
| T5 — iteration=0 guard | FIXED |
| T6 — ambiguous Phase 4 assertion | PARTIALLY FIXED |
| T7 — hyphenated role names in tests | NOT FIXED |

New findings: 2 (NEW-1: medium — contradictory "Decisions made" text; NEW-2: low — stale test count floor)

Overall plan verdict: **needs_revision** — T6 and T7 remain open, NEW-1 is a
real implementer confusion risk. None are critical blockers but the
contradictory "Decisions made" section (NEW-1) could cause an incorrect
implementation at Phase 3.
