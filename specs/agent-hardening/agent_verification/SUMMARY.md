# Agent Verification — Consolidated (Iteration 1)

| Agent | Verdict | Notes |
|---|---|---|
| architect-reviewer | NEEDS_REVISION | 2 CRITICAL, 4 HIGH, 5 MEDIUM — could not write sidecar (Bash denied write to specs/) |
| tester | FIX BEFORE SHIPPING | 3 CRITICAL, 3 HIGH, 2 MEDIUM — artifacts written |
| threat-modeler | NEEDS_REVISION | 4 HIGH, 3 MEDIUM, 1 LOW — could not write sidecar (lacks Write in tools list) |

**Note on missing sidecars:** architect-reviewer and threat-modeler agents lack Write capability or had Bash restrictions in this invocation — findings captured directly from their chat replies above. The `reviewer_json_missing` synthetic would block convergence; findings are addressed directly in this summary. Root cause (threat-modeler lacking Write) is itself a gap that Phase 2 of this plan does NOT fix (out of scope — only code-reviewer and ux-reviewer are in scope). Flagging for follow-up.

---

## What was actually broken

### Category 1: CRITICAL plan bugs (must fix before Phase 1 starts)

**C-1 (architect): `plugin.json` path is wrong**
Plan references `tlmforge/plugin.json`. Actual manifest is at `tlmforge/.claude-plugin/plugin.json` (verified). Phase 6 as written creates a file the marketplace ignores; real version stays at 0.3.0. Fix: update all references in plan to `.claude-plugin/plugin.json`.

**C-2 (architect + tester): Phase 1 scope missing two skill files**
`skills/live-evaluator/SKILL.md` (5 refs) and `skills/property-test-generator/SKILL.md` (3 refs) both have `plans/<feature>/` path bugs. Phase 1's grep test would pass green while the bug ships in those files. Fix: expand Phase 1 scope; broaden verification grep; carve out `plans/encryption/` and `~/dotfiles/claude/plans/` historical references explicitly.

### Category 2: Stop-hook fallback path (CRITICAL — tester EC-3 / architect H-2)

code-reviewer and ux-reviewer will have Write capability after Phase 2, and hardened prompts after Phase 3 that say "write code_review.md / ux_review.md." But neither the Stop-hook settings.json prompt nor the agent prompts define WHERE to write when there is no active feature context. Without this, every Stop-hook invocation will either write to an arbitrary path or fail. Fix in Phase 3: detect context via `TLMFORGE_FEATURE_DIR` env var; write to `specs/<feature>/agent_verification/` when set, `.tmp/<role>_review/<timestamp>.md` otherwise.

### Category 3: Tester needs test-runner detection + graceful degrade (CRITICAL — EC-2)

Plan instructs tester to run `pytest --cov`. tlmforge is a multi-language plugin used by Python, JS, Flutter, Go projects. Hardcoded pytest crashes on non-Python and blocks convergence with `status: "error"`. Fix in Phase 3: tester detects runner from `pyproject.toml`, `package.json`, `pubspec.yaml`, `go.mod`; degrades gracefully to coverage-skipped (status: ok, severity: medium) or counts-only.

### Category 4: Process-compliance hook LLM judgment needs a hard floor (HIGH — architect H-3)

Pure LLM judgment for TIER1+override has two failure modes: (a) fails open on timeout — worse than today's behavior, (b) non-deterministic across runs. Fix: keep hard LOC/file floor (same thresholds as plan's table). LLM can ESCALATE below the floor (catch a dangerous 1-line auth change) but can NEVER DOWNGRADE above it. Above the floor: block regardless of what the LLM thinks. Below the floor: LLM judgment applies.

### Category 5: Stage 4.6 diff baseline (CRITICAL — EC-1)

`HEAD~1..HEAD` reviews last commit only; phases produce multiple commits. Already fixed in SKILL.md during review: now uses `phase-N-state.md` `git_sha:` as phase-boundary anchor.

### Category 6: Stage 1→2 gate self-classification risk (HIGH — EC-4, architect H-1)

New conditional gate relies on Claude classifying questions as `[GATE-BLOCKING]`. Both tester and architect flagged this. Resolution applied in SKILL.md: `[GATE-BLOCKING]` structural tags make the gate deterministic (not LLM judgment), PLUS unconditional TIER1 override. This preserves "humans out of the loop for normal work" while protecting auth/payments/PII/migrations unconditionally.

### Category 7: Phase 4.6 underspecification (HIGH — architect H-4)

Per-phase re-review needs: (a) commit cadence (same commit as evidence? or separate?), (b) unblock path when HIGH finding blocks next phase. Will specify in phase-5-spec.md.

### Category 8: EC-7 per-phase tester scope bleeding (MEDIUM)

Tester in Stage 4.6 must scope findings to "code WITHIN this phase's diff" — not cross-phase gaps. Cross-phase gaps are expected and must be severity: low / category: meta. Will add to Phase 3 tester hardening.

---

## Deferred (with rationale)

- **Threat modeler H-1 (prompt injection via diff):** Valid concern; out of scope for this hardening. Will address in a follow-up security-hardening feature.
- **Threat modeler H-2 (unscoped Write paths):** Partially addressed via path scoping in prompts (Phase 3). Full allowlist enforcement (hook-level) deferred.
- **Threat modeler H-3 (feature slug path traversal):** Will add slug validation to SKILL.md in Phase 5.
- **Threat modeler M-3 (Edit enables retroactive tampering):** Noted; counter-argument is convergence script reads JSON not MD, so tampering MD doesn't affect gate. Low practical risk.
- **EC-5 (UPSTREAM_APPROVAL.md):** Valid concept; high process overhead. Deferred pending simpler implementation (auto-write by ExitPlanMode hook).
- **M-4 (architect — upgrade path for in-flight iterations):** Will add CHANGELOG migration note in Phase 6.
- **architect-reviewer / threat-modeler missing Write capability:** Out of scope for this plan. Follow-up feature.

---

## Plan fixes required before Phase 1

1. Update `README.md`: `.claude-plugin/plugin.json` everywhere (C-1)
2. Update `README.md`: Expand Phase 1 scope to include live-evaluator + property-test-generator (C-2)
3. Update `README.md`: Add Stop-hook fallback path + `TLMFORGE_FEATURE_DIR` as explicit design decision
4. Update `README.md`: Clarify process-compliance hook keeps hard LOC floor as the baseline; LLM escalates only

---

## Re-run criteria

After Phase 1-5 land, re-run architect-reviewer + tester + threat-modeler against the diff.
Expected verdict changes:
- architect: NEEDS_REVISION → APPROVE (C-1, C-2, H-3 addressed)
- tester: FIX BEFORE SHIPPING → SHIP IT (EC-1 through EC-8 addressed)
- threat-modeler: NEEDS_REVISION → APPROVE_WITH_WARNINGS (HIGH findings addressed; deferred items documented)
