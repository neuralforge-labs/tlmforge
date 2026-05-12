# check-convergence-round-aware — Status

**TL;DR:** This feature is a **dogfood test** of tlmforge 0.5.0's lean review
architecture. Phase 0 (characterization tests for `check_convergence.py`)
shipped with 18 GREEN tests. Phases 1-4 (defensive hardening, round-aware
loaders, single-shot dual, integration tests) are DEFERRED. The dogfood
caught 3 pre-existing CRITICALs in the convergence script + 5 plugin-
distribution issues (DF1-DF5). Stage 5 red-team confirmed the gate is
empirically forgeable today; Phase 1 implementation is the fix.

## Phase status

| Phase | What | Tests added | Status | Commit |
|---|---|---|---|---|
| 0 | Characterization tests (pin existing behavior) | +18 | ✅ COMPLETE | `54605b7` |
| 1 | `_load_json_safely` + hardening + `action` enum | +15 planned | ⏳ DEFERRED | — |
| 2 | Stage-specific path loaders | +9 planned | ⏳ DEFERRED | — |
| 3 | `evaluate_stage5_dual` + REMOVE `evaluate_stage5_two_tier` | +6 planned, -6 deleted (the two_tier characterization tests) | ⏳ DEFERRED | — |
| 4 | Integration tests on real fixture dirs | +5 planned | ⏳ DEFERRED | — |

**Total new tests landed: 18. Passing tests: 18/18 in 0.04-0.08s. Regressions: 0** (no pre-existing tests to break).

## Stage gate trace

| Stage | Outcome | Artifacts |
|---|---|---|
| 1 Spec audit | Gate did NOT fire (no [GATE-BLOCKING], no TIER1 keywords) | `spec_audit.md` |
| 2 Master plan | Gate did NOT fire (no new unapproved decisions) | `README.md` |
| 3 Plan review (3-round) | Soft-converged at R3 with 0 CRITICALs | `agent_verification/round-{1,2,3}-*.{md,json}`, `round-{1,2}-fixes.md`, `SUMMARY.md`, `tester_edge_cases.json` |
| 4 Phase 0 + phase-end | Phase 0 GREEN. Phase-end 2/3 reviewers APPROVED + 1 N/A (DF5 — phase-auditor not registered) | `phase-0-*.md`, `phase-0-verification/*.{md,json}` |
| 5 Final audit (dual) | red-team `do_not_ship` (CRITICAL: gate forgeable as-shipped); architect `needs_revision` (CHANGELOG/STATUS gaps) | `final_audit_red-team-reviewer.{md,json}`, `final_audit_architect-reviewer.{md,json}`, `FINAL_ESCALATION.md` |
| 6 Live verification | DEFERRED (single-feature dogfood; production live-verify is N/A for partial-ship Phase 0) | — |
| 7 STATUS.md | This file | — |

## Dogfood findings (the actual value of this test)

### What the 3-round Stage 3 loop caught

| # | Severity | Finding | Where |
|---|---|---|---|
| F1 | CRITICAL | Pre-existing `>` vs `>=` cap-check asymmetry between `evaluate_convergence` and `evaluate_stage5_two_tier`. At iteration=3, max=3, the two functions disagree on `cap_hit`. **Latent bug since the file was written.** | check_convergence.py:135 vs :364 |
| F2 | CRITICAL | `_load_json_safely` planned to catch `JSONDecodeError + OSError` but `UnicodeDecodeError` (ValueError subclass) would bypass both. | Phase 1 spec |
| F3 | HIGH | `iteration=0` would produce schema-invalid synthetic output | Phase 1 spec |
| F4 | CRITICAL (TH) | Gate forgery — no provenance check on review JSONs | Phase 1 spec |
| F5 | HIGH (TH) | Schema-absent JSON `{}` bypasses convergence via default values | Phase 1 spec |
| F6 | HIGH (TH) | Path traversal via crafted `feature_dir` / role | Phase 1 spec |
| F7 | MEDIUM (TH) | No file-size guard → OOM via large JSON | Phase 1 spec |
| F8 | HIGH | Original "deprecate the shim" plan silently discards non-architect CRITICALs and is suppressible. Resolved by REMOVE not deprecate. | Phase 3 spec |
| F9 | HIGH | Plan was self-contradictory across 5 sections (Phase 3 said REMOVE, Scope/Decisions/Verification said deprecate). Caught convergently by all 3 reviewers in Round 2. | README.md (fixed) |

### What Stage 5 caught

| # | Severity | Finding |
|---|---|---|
| FA1 | CRITICAL (red-team, **empirically tested**) | Convergence gate is forgeable today. Phase 1 lands the fix. |
| FA2 | HIGH (architect) | CHANGELOG.md overclaims 0.5.0 features as live | **FIXED in this commit** |
| FA3 | MEDIUM (architect) | STATUS.md missing | **FIXED in this commit (this file)** |
| FA4 | MEDIUM (architect) | reviewer-convergence.md §3 silently stale | Deferred to Phase 3 |

### What the dogfood revealed about the plugin itself

| # | Severity | Finding | Status |
|---|---|---|---|
| DF1 | HIGH | Plugin marketplace cache stuck on 0.3.0; 0.5.0 SKILL.md not active for the running session (Skill loaded the cached 0.3.0 recipe text) | Open — needs marketplace publish + cache refresh |
| DF2 | LOW | Duplicate `check_convergence.py` at `~/.claude/skills/feature-development/` (byte-identical to plugin's) | Open — clarify mirror behavior |
| DF3 | HIGH | Subagent file edits don't propagate to running session. threat-modeler couldn't `Write` its JSON sidecars across all 3 Stage 3 rounds — main Claude saved them manually. Per saved memory `feedback_subagent_files_need_session_restart`, this needs a fresh session OR plugin cache refresh. | Open — same root cause as DF1 |
| DF4 | CRITICAL | 3 reviewer agents (architect, threat-modeler, red-team) had no Write+Edit in tools list. 0.5.0 design requires them to write JSON sidecars; without Write the convergence script injects `reviewer_json_missing` and never converges. | **FIXED** mid-dogfood (`edfa9f4`) |
| DF5 | HIGH | New `phase-auditor` agent file exists but isn't in the Agent tool's registry (cache still on 0.3.0 roster). Phase-end verification couldn't include the auditor; main Claude did the manual fallback. | Open — same root cause as DF1 |

## What this dogfood test PROVED about the lean review architecture

1. **Stage 3 bounded 3-round loop works.** Caught 3 pre-existing CRITICALs in a load-bearing utility that had zero test coverage for months. Found 5 new security hardenings the original spec missed. R2 reviewers convergently caught my incomplete R1 fixes (5 plan sections inconsistent). R3 soft-converged on cosmetic residuals only.
2. **Carryover artifact (`tester_edge_cases.json`) works.** Tester emitted it at R1. Tester R2 confirmed it was intact for Stage 4 consumption.
3. **Round-2 verify-your-findings framing works.** Reviewers correctly tracked which prior findings were FIXED / PARTIALLY / NOT_FIXED with file:line evidence in the updated plan, not re-derivation.
4. **Stage 4 phase-end gate works.** Tester re-ran the suite independently and cross-checked evidence claims. Code-reviewer applied full checklist scoped to the phase diff only. (Phase-auditor blocked by DF5 — not architectural.)
5. **Stage 5 dual single-shot works.** Red-team **empirically attacked** the gate (wrote forged JSONs, observed bypass). Architect found cross-cutting doc-integrity issues. Both contributed unique findings.
6. **The escalation path triggered correctly.** Stage 5 CRITICAL → `FINAL_ESCALATION.md` → user decision. Bounded iteration discipline held.

## What this dogfood test REVEALED about deployment gaps

The plugin's design (0.5.0) is sound, but its DISTRIBUTION is broken:
- Cached plugin doesn't refresh to a new pushed version (DF1)
- New agents in a pushed version aren't picked up until cache refresh (DF5)
- Edits to existing agents' tools lists don't propagate in-session (DF3)

**These are not architectural failures of the lean review design.** They're
operational gaps in the marketplace pipeline. Fixing them is a separate
follow-up; this dogfood ran successfully despite them by manually saving
files when subagents couldn't write.

## Operator runbook for the partial-ship state

If you (or another operator) needs to use this script today:
- **Recognize: the convergence gate is forgeable.** Trust-zone enforcement
  is operational (control over who can write to `agent_verification/`),
  not cryptographic.
- **Phase 1 fix is the next chunk of work.** Spec is complete in this
  spec dir; round-1-fixes.md + round-2-fixes.md + final README.md describe
  the defenses in detail.
- **Until Phase 1 lands, do not use this as a security gate in any context
  where the spec dir is writable by adversarial code.**

## Honest assessment for an external reviewer

**Strengths:**
- The dogfood test surfaced REAL pre-existing bugs (cap-check asymmetry, encoding bypass) that would have lived in production indefinitely without these tests.
- Every Stage 3 round produced auditable findings JSONs + .md files in the spec dir; rollback is `git revert` with no data risk.
- Stage 5 red-team didn't just abstract-design-review — it empirically attacked the live script and confirmed bypasses. This is the impl-time adversarial pass working as designed.
- The plugin's 5 distribution issues (DF1-DF5) are surfaced and documented for separate operational fix.

**Weaknesses (a hostile reviewer would attack):**
- **Only Phase 0 of 4 shipped.** Most of the actual feature value (defensive loader, round-aware paths, single-shot dual) is deferred. The CHANGELOG 0.5.0 entry was over-claimed before this final edit.
- **The plugin's marketplace cache issue (DF1) means none of this 0.5.0 lean architecture is active for users.** Until cache refreshes, end users still run 0.3.0's unbounded convergence + Stop hook architecture.
- **Phase-auditor invocation failed.** A "complete" Stage 4 phase-end gate per the new design requires 3 agents; the gate fell back to 2 + manual coverage. Not a fatal flaw of the design but a current operational gap.

**Net:** the lean review architecture's design is validated by this dogfood.
The implementation of the convergence script is PARTIAL (Phase 0 only).
The plugin's distribution layer needs DF1+DF3+DF5 addressed before end
users can benefit from the 0.5.0 design.
