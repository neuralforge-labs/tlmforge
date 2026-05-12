# Execution log — lean review architecture

Per-phase tracking log for the plan in `README.md`. The plan is the spec; this is the receipt.

## Phase 1 — Remove 4 Stop hooks  ✅ COMPLETE

**Plan section:** A1
**Files:** `~/dotfiles/claude/global/settings.json` (source of truth; SessionStart sync script propagates to `~/.claude/settings.json`)
**Diff scope:** `-42 / +1` — Stop array `[<4 hook blocks>] → []`
**Verification:** Stop hooks: 0 (was 4); PreToolUse preserved (ExitPlanMode → architect-reviewer); SessionStart preserved; mirror in sync.
**Commit:** dotfiles `e7abd6a`
**Burn impact:** Ends the ~30 opus + ~90 sonnet Stop-hook spawns per typical feature session — the single biggest line item in Claude Max quota burn.

## Phase 2 — Create spec tracking dir  ✅ COMPLETE

**Files added:** `tlmforge/specs/lean-review-architecture/{README.md, EXECUTION_LOG.md}`
**Commit:** tlmforge `48fb3f2`

## Phase 3 — Classification gate (CLAUDE.md) + test discipline (tdd.md)  ✅ COMPLETE

**Plan sections:** A2, A8
**Files:** `~/.claude/CLAUDE.md` + dotfiles mirror; `~/.claude/rules/tdd.md` + dotfiles mirror
**Changes:**
- CLAUDE.md "Feature-Development Skill" section: hardcoded MemX paths replaced with semantic classification gate (security surface / persistent state / cross-module / customer-facing / user language signals). Asymmetric default — both must agree Light to skip Deep. Light path keeps TDD + full-suite + self-review discipline.
- CLAUDE.md "Auto-Review Protocol": acknowledges Stop hooks removed; PreToolUse preserved.
- CLAUDE.md "Tech Lead Mode": delegates to the new gate (no duplicate decision tree).
- tdd.md: test-layer rule (unit always, integration if module-crossing, E2E if user-facing) + full pre-existing suite + zero regressions + evidence-capture requirements.
**Commit:** dotfiles `ae17c7a`

## Phase 4 — phase-auditor agent  ✅ COMPLETE

**Plan section:** A5
**Files:** `tlmforge/agents/phase-auditor.md` (NEW)
**Scope:** Tight contract-checker. Reads phase-N-spec.md (promise), phase-N-evidence.md (receipt), and the phase diff (delivery). Verifies scope contract, test contract (with self-run cross-check against evidence), verification criteria, rollback safety. Does NOT opine on architecture, edge cases, or security.
**Commit:** tlmforge `804dbac`

## Phase 5 — Agent prompt updates  ✅ COMPLETE

**Plan sections:** A4 (round framing), A6 (phase-end roles), A7 (Stage 5 framing)
**Files:** `agents/tester.md`, `agents/architect-reviewer.md`, `agents/threat-modeler.md`, `agents/ux-reviewer.md`, `agents/code-reviewer.md`
**Changes:**
- tester: Stage 3 round 1 emits `tester_edge_cases.json` carryover; Stage 3 round 2/3 verify-your-findings; Stage 4 phase-end re-runs suite + cross-checks evidence; Stage 5 final framing.
- architect-reviewer: round 2/3 framing; Stage 5 holistic + cross-phase framing (NOT re-derivation).
- threat-modeler: round 2/3 framing; explicit "Stage 3 only" note.
- ux-reviewer: round 2/3 framing; conditional Stage 4 phase-end (UI files in diff only); scoped to phase diff at phase-end.
- code-reviewer: Stage 4 phase-end framing (scope to phase diff, read phase spec + evidence).
**Commit:** tlmforge `c26140c`

## Phase 6 — SKILL.md rewrite  ✅ COMPLETE

**Plan sections:** A2, A3, A4, A6, A7
**Files:** `skills/feature-development/SKILL.md`
**Changes:**
- "When to use" + "Three intensities": replaced with classification-gate reference (skill is invoked only on Deep path; Light handled in CLAUDE.md).
- "The recipe at a glance": updated to show 3-round Stage 3 loop, phase-end verification with 4 agents (3 + conditional ux-reviewer), Stage 5 dual single-shot. Notes Stop hooks not involved.
- Stage 3: replaced with bounded 3-round protocol — round 1 cold review (sonnet, parallel), round-1-fixes.md, round 2 verify-your-findings, round 3, ESCALATION.md if unresolved. tester_edge_cases.json as carryover artifact. Full launch prompt templates included.
- Stage 4.3 Execute: TDD now sources scenarios from tester_edge_cases.json, assigns layers, requires full pre-existing suite + zero regressions, captures test output into evidence.
- Stage 4.4 Evidence template: requires per-layer counts + full-suite regression output.
- Stage 4.6: replaced with phase-end verification (code-reviewer + tester + phase-auditor + conditional ux-reviewer); same 3-round cap.
- Stage 5: replaced multi-iteration tier-1/tier-2 with 2 agents single-shot — red-team-reviewer [opus] + architect-reviewer [sonnet] (holistic/cross-phase). No iteration; CRITICALs → FINAL_ESCALATION.md.
**Diff scope:** +487 / -220 lines
**Commit:** tlmforge `89b24b2`

## Phase 7 — reviewer-convergence.md update  ✅ COMPLETE

**Files:** `skills/feature-development/reviewer-convergence.md`
**Changes:**
- Section 0 (per-stage roles): Stage 4 phase-end row added with 4-agent roster; Stage 5 row updated to single-shot dual.
- Section 2 (prompt template): output paths now stage-aware; new round-2/3 prompt block enforcing verify-your-findings framing.
- Section 4 (Stage 5): replaced skip-rule logic. Stage 5 always two single-shot agents — no iteration, no skip.
- New subsection in Section 3: carryover artifacts (tester_edge_cases.json schema, round-N-fixes.md, phase-N-state.md). Distinguishes carryover artifacts from review JSON sidecars.
**Commit:** tlmforge `cba0cd4`

## Phase 8 — Version bump + CHANGELOG + push  ✅ COMPLETE (this commit)

**Files:** `.claude-plugin/plugin.json` (0.4.0 → 0.5.0); `CHANGELOG.md` (0.5.0 entry); this file
**Commit:** tlmforge (pending — this commit)

---

## Final spawn-count picture

| Path | Old | New |
|---|---|---|
| Light/Minimal task | ~4 spawns × N saves (Stop hooks) | **0 spawns** |
| Deep feature, 5 phases | ~145 spawns, ~31 OPUS | ~30-40 spawns, ~1 OPUS |

The Light path eliminates ALL subagent spawns. The Deep path is ~75% lighter than today, with opus invocations reduced from ~31 to 1 (the single Stage 5 red-team-reviewer).
