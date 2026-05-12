# Round-2 fixes — main Claude's response

All 3 reviewers convergently flagged that round-1 fixes were INCOMPLETE:
Phase 3 was updated to "remove entirely" but Scope, Decisions, Architecture
diagram, Risk audit, Verification criteria, and Threat Model sections still
referenced the old "deprecated shim" approach. These are textual consistency
fixes — the plan's architectural decisions stand.

## Fixes applied to README.md

| Reviewer finding | Fix location |
|---|---|
| Architect A3 (CRITICAL escalation) + Tester NEW-1 + Threat-modeler TH5 NOT_FIXED — plan self-contradictory on `evaluate_stage5_two_tier` fate | **5 sections updated:** Scope "In" bullet, Architecture diagram "Obsolete (deprecated)" block, Risk audit F3, Decisions made, Verification criterion #5 — all now say REMOVE / ImportError, not deprecate |
| Architect N1 + Tester NEW-2 — test count floor (>= 25) stale | Verification criterion #2 raised to >= 45 with updated per-phase breakdown |
| Architect A6 + Tester T6 — Phase 4 integration test ambiguous "retry or escalate" | Phase 4 test list splits into two pinned tests: `_retry` (iteration<max) and `_escalate` (iteration>max). Explicit cap_hit boundary documented |
| Threat-modeler TH1 PARTIALLY (Stage 5 expected_iteration unspecified) | Phase 2 `load_final_audit_jsons` description now states it passes `expected_iteration=1`; `_load_json_safely` treats `None` as invalid (raises, not silently skips) |
| Threat-modeler NEW-1 — threat model section disavows defenses Phase 1 implements | Threat model section rewritten: "What we're defending against" now lists 5 Phase 1 hardenings (forgery cross-check, schema validation, path containment, OOM guard, ImportError) explicitly. "What we're NOT defending against" narrowed to HMAC + concurrent writes |

## Findings NOT addressed (deferred)

- **Tester T7 (hyphenated role names in Phase 2 tests)** — minor wording
  clarification deferred to Stage 4 implementation; not a plan-level
  blocker. Will surface again if Phase 2 implementation produces unclear
  test names.

## Round-3 scope

All consistency fixes applied; the plan now points in one direction across
every section. Round 3 should verify just the textual consistency — no
new architectural changes are needed. Expected outcome: all 3 reviewers
approve at iteration=3.
