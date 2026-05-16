# Round 2 Fixes — multi-llm-reviewers

## Summary

Round 2 produced: Architect — 2 CRITICALs + 1 HIGH; Tester — 2 CRITICALs + 1 HIGH;
Threat-modeler — 0 CRITICALs (approve_with_warnings). All 4 CRITICALs share the same
root cause: the silent-skip policy (added post-round-1 per user requirement) propagated
to the constraints section but not to the Phase 1 test expectations or Verification
Criteria. All 4 CRITICALs fixed below. HIGHs addressed.

---

## Architect findings (round 2)

### NEW-C1 — Phase 1 test plan: three tests still expect `status=error + exit 0`
**Finding:** Lines 235-238 specify `status=error + meta CRITICAL, exit 0` for auth error,
both-retries-invalid-JSON, and truncated-response scenarios — contradicts constraint
at §Phase 1 lines 202-207.
**Fix:** Changed all three test cases to: `status=skipped, exit 2, failure logged`.
README.md lines 236-238 updated.

### NEW-C2 — Verification criterion 1 expects `status=error` on fake API key
**Finding:** Line 374 `exits 0, JSON has status=error` — fake key is an auth error
(provider failure), must be skipped not errored.
**Fix:** Changed criterion 1 to `exits 2, status=skipped, reviewer="openai"`. Added
criterion 1b for the mocked happy-path (exits 0, status=ok). README.md line 374 updated.

### NEW-H1 (architect) — Echo in Phase 0 marker write creates trailing newline, breaks `.strip()` note
**Finding:** Phase 0 spec says `echo "multi-llm-reviewers" > .tlmforge_active_feature`
which produces a trailing newline. The W1 fix (`.strip()`) handles it, but the spec
should clarify the echo behavior.
**Fix:** Phase 0 steps note already documents `.strip()` applied to marker read.
No additional change needed — the fix was correctly documented in round-1-fixes.

---

## Tester findings (round 2)

### NEC-1 — Phase 1 test plan: status=error for provider failures
**Same as NEW-C1 above. Fixed identically.**

### NEC-2 — Verification criterion 1: status=error on fake key
**Same as NEW-C2 above. Fixed identically.**

### NEC-3 — Plan never confirms review_schema.json accepts "skipped"
**Finding:** Plan relies on check_convergence.py handling status=skipped but never
verifies schema compatibility or documents minimum skipped-sidecar fields.
**Fix:** Confirmed `review_schema.json` status enum already includes `"skipped"` —
no schema change needed. Added explicit minimum skipped-sidecar field list to
Phase 1 constraints section: `reviewer`, `schema_version`, `iteration`,
`status="skipped"`, `findings=[]`. README.md Phase 1 constraints updated.

---

## Threat-modeler findings (round 2)

Verdict was `approve_with_warnings` — no CRITICALs. No fixes required for convergence.

### Medium finding: silent-skip creates stealthy reviewer-suppression window
Accepted risk — opt-in only, same risk exists for Gemini today. Noted in risk audit.

### Nit: stale "status=error" text in architecture section
**Fix:** Updated exit-code contract comment at line 97 to clarify status=error is
reserved for implementation bugs only, not LLM provider failures.

---

## What was NOT fixed (deferred)

- Threat-modeler medium: stealthy suppression attack — accepted, same as Gemini today
- Architect NEW-H1 nit: already handled by .strip() in Phase 0 — no new change needed
