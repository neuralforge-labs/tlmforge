# Changelog

## 0.5.11 (2026-05-17)

### Two mandatory user-approval gates in feature-development skill

**Stage 0.5 — Understanding confirmation:** Before writing any spec or plan,
Claude states its understanding in 2–3 sentences, lists open questions tagged
`[BLOCKING]` or `[INFORMATIONAL]`, and uses `AskUserQuestion` if any blocking
questions exist or the understanding is non-trivial. Stage 1 begins only after
the user confirms. Applies to all work requests (Light, Medium, Deep).

**Stage 3→4 approval gate:** After multi-agent review converges (SUMMARY.md
written, all reviewers approved, zero CRITICALs), Claude calls `ExitPlanMode`
with the master plan (`specs/<feature>/README.md`) and a reviewer-findings table
showing what each reviewer flagged and how each finding was resolved. Stage 4
begins only after the user explicitly approves. Applies to both Medium and Deep
paths.

**Opt-out:** Set `TLMFORGE_APPROVAL_GATES=0` to disable both gates (consistent
with the existing `TLMFORGE_HOOKS=0` escape-hatch convention).

---

## 0.5.10 (2026-05-16)

### Hook 2 made advisory

Hook 2 (mutation gate) now prints a reminder to stderr instead of blocking.
Exit code is always 0 — writes and bash commands are never prevented
regardless of whether the skill was invoked.

**Migration:** No action required. Bypass phrases and `TLMFORGE_HOOKS=0` still
work but are no longer needed to get past Hook 2.

---

## 0.5.9 (2026-05-16)

### Medium path regression tests

Added 23 automated regression tests guarding all v0.5.8 Medium path fixes.
Total test count: 183 (130 hooks + 30 pre-existing skill + 23 new). Zero regressions.

**Test classes:**
- `TestTDDRedPhase` (4) — inline v0.5.7 fixture strings prove tests would be RED before the fix
- `TestSkillContentIntegrity` (12) — reviewer-convergence.md Medium-path table rows; SKILL.md
  phase-end annotations; committed CLAUDE.md fixture
- `TestConvergenceMediumPath` (7) — `evaluate_convergence()` with Medium `expected_roles`;
  confirms no spurious synthetic CRITICALs for excluded roles

**Files added:**
- `skills/feature-development/tests/test_v058_medium_path.py`
- `skills/feature-development/tests/fixtures/claude_medium_path_excerpt.txt`

### Migration

None — additive test coverage only. No behavior change.

---

## 0.5.8 (2026-05-16)

### Medium path fixes (post-commit review of v0.5.7)

Three CRITICALs and three warnings found by post-commit architect-reviewer and
code-reviewer review of v0.5.7 were resolved before the regression tests landed.

**Fixes applied:**
- `reviewer-convergence.md`: Medium vs Deep path reviewer rosters clarified in the
  per-stage table; tester's role at phase-end explicitly limited to Deep path
- `SKILL.md`: Security-surface override added to classification rules — auth flow, secret
  handling, PII access controls, cryptography, or session/token mechanics always Deep
  regardless of change size; Stage 4 scenario sourcing (no `tester_edge_cases.json` on
  Medium path); Stage 6 explicitly skipped for Medium path features
- `CLAUDE.md`: Medium path recipe summary updated to match SKILL.md; security-surface
  override mirrored in the classification table

### Migration

No breaking changes. All fixes are clarifications and guards — no existing behavior removed.

---

## 0.5.7 (2026-05-16)

### Three-way classification gate (Light / Medium / Deep)

The prior skill had a two-state system (Deep or "minimal / skip it"). v0.5.7
introduces a formal Medium path for bug fixes, refactors, and improvements to
existing behavior that don't add new product surfaces.

**Medium path recipe:**
```
Stage 0: Classify → announce → proceed
Stage 1: Abbreviated spec audit (root cause, fix scope, rollback, test plan)
Stage 2: Fix plan (simplified README.md)
Stage 3: Single-round review — architect-reviewer + tester (no threat-modeler)
Stage 4: TDD execution with phase-end code-reviewer + phase-auditor
Stage 5: phase-auditor final compliance check (no red-team)
Stage 7: Abbreviated STATUS.md
```

**Classification rule:** "Am I changing what already exists, or adding something new?"
Changing/fixing → Medium. Adding new capability → Deep.

**Auto-classify and proceed.** No `AskUserQuestion` confirmation gate. Announce
the chosen path in one sentence and start. The user can say "go deeper" or "go lighter"
at any point to adjust.

**SKILL.md additions:**
- Stage 0 rewritten: dual-job step (early-exit for non-work prompts + classification gate)
- Stage 1: abbreviated spec audit template for Medium path (6-section format)
- Stage 2: simplified fix-plan README template for Medium path
- Stage 3: single-round 2-agent variant documented (no convergence loop)
- Stage 4: Medium path sourcing from tester prose instead of `tester_edge_cases.json`
- Stage 5: phase-auditor-only compliance check for Medium path; Stage 6 skipped
- Quick checklist: separate Medium intensity section added

**CLAUDE.md additions:**
- Classification gate section rewritten for 3-way system
- Medium path recipe summary added to "at a glance" section

### Migration

No breaking changes. Existing Deep-path features are unaffected. The classification
gate fires on new work only.

---

## 0.5.6 (2026-05-16)

### Fix: infinite retry loop caused by same-turn transcript gap

**Issue:** The enforcement hook checked the transcript for skill invocation within
the current "task window." When the skill was invoked and then tools were called in
the SAME assistant turn, the skill invocation appeared AFTER the tool calls in the
transcript — because the transcript is written at turn boundaries, not in real time.
The hook then found no invocation prior to the tool calls and re-injected the
reminder, causing an infinite loop where every tool call triggered another reminder.

**Fix:** Replaced the same-turn transcript scan with a marker-file approach.

**Hook 2 (PostToolUse — new):** When the `tlmforge:feature-development` skill tool
is invoked, a marker file is written to `.tmp/tlmforge_skill_invoked_<session-id>`.
The mutation gate (PreToolUse) now reads this marker file instead of scanning the
live transcript — the marker is always present by the time any subsequent tool fires
in the same turn.

**Hook 2 (PreToolUse — updated):** Mutation gate reads the marker file; if present
and fresh (same session), allows the mutation. Marker is cleared at session start.

### Migration

No breaking changes. The marker file lives in `.tmp/` and is gitignored. Sessions
without a marker (e.g., first tool call after install) behave identically to before —
the gate fires and requires skill invocation or an override phrase.

---

## 0.5.5 (2026-05-15)

### Enforcement hooks — three-hook automatic gate system

tlmforge now ships three Claude Code hooks that fire automatically after
`claude plugin add`. No manual configuration required.

**Hook 1 — skill reminder (UserPromptSubmit)**
Injects a `systemMessage` before every response reminding Claude to invoke
`tlmforge:feature-development` before doing any work. The skill's Stage 0
exits cleanly for conversational/read-only prompts — the reminder is
low-friction for non-work messages.

**Hook 2 — mutation gate (PreToolUse: Edit/Write/Bash/MultiEdit)**
Blocks all file mutations if `tlmforge:feature-development` was not invoked
in the current task window. Override phrases (`be quick` / `just do it` /
`trivial fix`) bypass the gate for that single task. Bare "minimal" or
"trivial" are rejected (too common in technical prose).

**Hook 3 — post-Stage-5 gate (PreToolUse: Bash git/gh)**
Blocks `git commit`, `git push`, and `gh pr merge/create` if HEAD has drifted
past the SHA recorded in the Stage 5 final audit JSON (`verdict_sha` field).
Unblock by writing a PSR marker (`final_audit_<role>_psr_<HEAD>.json` with
matching internal `verdict_sha`) or setting `TLMFORGE_HOOKS=0`.

**Bypass options**
- `TLMFORGE_HOOKS=0` (or `false`/`no`/`off`) — disables all hooks for the session
- Override phrases in prompt — bypasses Hook 2 per-task
- `claude plugin remove tlmforge` — removes all hooks permanently

**SKILL.md additions**
- Stage 0 early-exit: skill exits cleanly for conversational/read-only prompts
- Active-feature marker: Stage 1 writes `specs/.tlmforge_active_feature`; Stage 7 deletes it
- PSR (post-Stage-5 re-review) workflow documented
- Stage 5 launch prompt now requires `verdict_sha` in audit JSON output
- LL-6b wire-test rule: UI integration tests must exercise the full wire path

**review_schema.json**
Added optional `verdict_sha` field for Stage 5 final audit files.

### Migration

No breaking changes. Hook behavior is additive. Existing features in `specs/`
without a `.tlmforge_active_feature` marker are unaffected by Hook 3 (it
passes through when no marker exists). Hook 2 passes through sessions where
the transcript path is absent (older Claude Code versions).

---

## 0.5.4 (2026-05-13)

### License: UNLICENSED → MIT

The plugin is now MIT-licensed. Previous releases shipped with
`"license": "UNLICENSED"` in `plugin.json` and "Private. Do not
redistribute." in README — incompatible with the open-source
distribution the marketing copy described. Fixed.

- New top-level `LICENSE` file (MIT, copyright 2026)
- `plugin.json` license field: `UNLICENSED` → `MIT`
- README license section updated to point at `LICENSE`

### Install docs: explicit "restart your session" guidance

Documented the cache-refresh requirement that the
`check-convergence-round-aware` dogfood surfaced as DF1/DF3/DF5: Claude
Code caches plugin manifests per session, so newly added agents and
updated `tools:` lists don't take effect until the session restarts.
The README install section now spells this out with the specific
symptoms of a stale cache (`agent type not found`, never-converging
loops) so an installer can self-diagnose.

### Migration

None — pure docs + license metadata. No behavior change.

---

## 0.5.3 (2026-05-12)

### Stage 1 renamed: "Request audit" → "Feature request analysis"

0.5.2's rename to "Request audit" was a step forward but still slightly
clinical. "Feature request analysis" is more accessible — it's the
industry-standard term for the activity (analyze the user's feature
request, surface hidden assumptions, ask back where decisions are
needed). Same behavior, clearer name.

- SKILL.md Stage 1 section header + recipe-at-a-glance diagram updated
- `docs/ARCHITECTURE.md` flow chart updated

Artifact filename `spec_audit.md` is unchanged — it's the structured
spec produced by the analysis, and renaming it would break references in
every existing `specs/<feature>/` dir and every reviewer agent prompt.

### Migration

None — pure label change. No behavior change.

---

## 0.5.2 (2026-05-12)

### Stage 1→2 gate: remove hardcoded keyword trigger

0.5.1's SKILL.md said the Stage 1→2 gate fires on `[GATE-BLOCKING]`
questions **OR** the presence of any TIER1 keyword (`auth`, `payment`,
`encryption`, `PII`, `migration`, `IAM`, `RBAC`, `token`, `password`).

That's the same anti-pattern as hardcoded paths: the plugin is generic
and shouldn't assume project-specific sensitivity terms. If a sensitive
area was genuinely touched, the audit tags it as `[GATE-BLOCKING]` —
trust the audit's own discipline.

**Fix in 0.5.2:** Stage 1→2 gate fires on `[GATE-BLOCKING]` tags only.
No keyword list. The classification gate at task entry (in
`~/.claude/CLAUDE.md`) already routed Deep work to this skill; we don't
need a second classifier inside Stage 1.

### Stage 1 renamed: "Spec audit" → "Request audit (produces spec_audit.md)"

"Spec audit" was backward-looking — sounded like there's an existing
spec doc to audit. There isn't, at Stage 1. The act IS turning the
user's request into a structured spec by auditing its hidden assumptions,
threats, failure modes, costs, and rollback risks. The artifact filename
stays `spec_audit.md` (forward-looking — the audit is the spec).

### NEW: `docs/ARCHITECTURE.md`

Living flow-chart document for the lean review architecture. Linked from
README.md. Updated whenever the flow changes (stage gate conditions,
reviewer roster, classification logic, carryover artifacts, escalation
protocol).

### Migration

None — pure clarification + gate-simplification. Anyone relying on the
TIER1 keyword OR-trigger should re-audit their workflow: if a feature
needed user sign-off because it touched (e.g.) auth, that surfaced as a
`[GATE-BLOCKING]` question. The keyword shortcut was redundant.

---

## 0.5.1 (2026-05-12)

### Fatal-bug fix on 0.5.0 reviewer agents

**Issue:** Three reviewer agents shipped in 0.5.0 — `architect-reviewer`,
`threat-modeler`, `red-team-reviewer` — were missing `Write` and `Edit` in
their `tools:` frontmatter. The 0.5.0 lean review architecture REQUIRES
these agents to write JSON sidecars at round-aware paths. Without `Write`,
they produce prose-only output. The convergence script then injects
`reviewer_json_missing` synthetic CRITICALs every round and **never
converges** — a fatal bug for anyone using Stage 3 plan review or Stage 5
final audit under 0.5.0.

**Discovered:** during a dogfood test of the 0.5.0 lean review architecture
itself (DF4 in `specs/check-convergence-round-aware/STATUS.md`). The dogfood
also empirically attacked the convergence gate and confirmed pre-existing
forgery surfaces — those are tracked separately as deferred Phase 1 work.

**Fix:** added `Write, Edit` to the `tools:` frontmatter of all three agents.
The other reviewer agents (`code-reviewer`, `tester`, `ux-reviewer`,
`phase-auditor`) already had the right tools list.

### Also in 0.5.1

- **18 characterization tests for `check_convergence.py`** at
  `skills/feature-development/tests/test_check_convergence.py`. These pin
  every documented branch of `evaluate_convergence` (11 tests) and
  `evaluate_stage5_two_tier` (6 tests) plus the boundary asymmetry between
  them (2 tests). They're the safety net for upcoming round-aware loader
  work (Phase 1+ of the `check-convergence-round-aware` spec).
- **CHANGELOG.md 0.5.0 corrected** with a "Known gap" preamble that
  honestly states the round-aware loaders + action enum +
  `evaluate_stage5_dual` are designed but NOT YET IMPLEMENTED in
  `check_convergence.py`. They live in Phase 1-4 of the
  `check-convergence-round-aware` spec.

### Migration

None — pure additive fix. Upgrade unconditionally if you're on 0.5.0.

### Operational note

Plugin marketplace cache may need to refresh before 0.5.1 changes are
visible to your running Claude Code session. If you see "agent type not
found" errors for `phase-auditor` or convergence loops that never reach
zero CRITICALs, your cache is stale.

---

## 0.5.0 (2026-05-12)

### ⚠️ Known gap — Phase 1 of check-convergence-round-aware NOT YET SHIPPED

The 0.5.0 SKILL.md, agent prompts, and reviewer-convergence.md describe a
round-aware filename convention and stage-aware loaders (`load_stage3_round_jsons`,
`load_phase_end_round_jsons`, `load_final_audit_jsons`) plus an `action` field
on the convergence result plus a single-shot `evaluate_stage5_dual` replacing
the old two-tier function.

**`check_convergence.py` itself does NOT yet implement these.** The 0.5.0
release contains:
- ✅ Lean SKILL.md flow (Stages 1-7 with bounded 3-round loops)
- ✅ Agent prompts updated for round-aware behavior + stage-specific framing
- ✅ New `phase-auditor` agent file (NOTE: not invocable until plugin cache
  refreshes — see DF5 in `specs/check-convergence-round-aware/STATUS.md`)
- ✅ `tester_edge_cases.json` carryover artifact protocol documented
- ✅ Phase 0 of `check-convergence-round-aware`: 18 characterization tests
  pinning current behavior
- ⏳ Phases 1-4 of `check-convergence-round-aware` DEFERRED (round-aware
  loaders, defensive hardening, single-shot dual). See spec dir.

**Security implication of the deferral:** As shipped today, the convergence
gate is forgeable by anything that can write to `agent_verification/` (empirically
confirmed at Stage 5 red-team review). The defenses are designed and spec'd
(see `specs/check-convergence-round-aware/`) but not yet code. Phase 1
implementation lands those defenses.

### Lean review architecture

Major redesign of the convergence loop to reduce subagent spawns by ~75-99% per feature. Driven by Claude Max quota pressure: the prior architecture ran ~145 subagent spawns per typical 5-phase feature (≈31 of them on opus), the single biggest line item being the tester Stop hook firing opus on every save.

**Stop hooks removed entirely.** The four Stop hooks (tester, code-reviewer, ux-reviewer, process-compliance) that fired after every assistant turn where files changed are gone. Replaced by review at well-defined gates (Stage 3 plan rounds, Stage 4 phase-end, Stage 5 final audit), or by main-agent self-review in the Light path. `PreToolUse[ExitPlanMode]` (architect-reviewer) and `SessionStart` (sync script) preserved.

**Classification gate (semantic, not path-based).** Before any non-trivial work, Claude self-classifies the task by semantic signals (security surface, persistent state, cross-module scope, customer-facing impact, user language signals) and asks the user to confirm. **Asymmetric default to safety**: either Claude or the user can escalate to Deep; both must agree on Light to skip the deep process. No hardcoded project-specific paths anywhere — the plugin is generic and works across any codebase.

**Light/Minimal path with self-review discipline.** Light tasks no longer fire ANY subagent. The main agent owns full discipline: identify test layers (unit/integration/E2E), write tests first, run RED → impl → GREEN, run FULL pre-existing test suite with zero regressions, self-review checklist. Discipline survives without subagent spawns. Mid-task scope expansion → pause and re-ask the gate.

**Stage 3 — bounded 3-round plan review loop.** Replaces unbounded convergence. Round 1: architect + tester + threat-modeler (+ ux-reviewer if UI) review cold, parallel. Main Claude fixes plan, writes `round-1-fixes.md`. Round 2: SAME reviewers verify YOUR prior findings (not re-derive). Round 3: same. If unresolved after Round 3: `ESCALATION.md` + ask user. Sonnet for all reviewers (opus only at Stage 5). Tester emits `tester_edge_cases.json` carryover artifact at Round 1.

**Stage 4 — TDD with full test discipline and phase-end verification.** TDD now explicitly sources scenarios from `tester_edge_cases.json` (Stage 3 carryover) as a seed. Main Claude assigns each scenario to a test layer (unit/integration/E2E), writes tests first, runs RED, implements, runs new tests + FULL pre-existing suite. Phase-N-evidence.md must include per-layer test counts AND full-suite regression output. Phase-end verification: 3 agents + 1 conditional in parallel (code-reviewer + tester + new `phase-auditor` [+ ux-reviewer if UI in phase diff]), same 3-round cap as Stage 3, escalates to user on round 3 unresolved.

**New `phase-auditor` agent.** Tight-scope reviewer for phase-end. Reads `phase-N-spec.md` (promise), `phase-N-evidence.md` (receipt), and the phase diff (delivery). Verifies scope contract, test contract (re-runs the suite itself; mismatch with evidence is CRITICAL), verification criteria, rollback safety. Does NOT opine on architecture, edge cases, or security — strictly promise-vs-delivered.

**Stage 5 — single-shot dual audit.** Replaces iterative tier-1+tier-2 review. Two agents in parallel, no iteration: `red-team-reviewer` [opus] for adversarial impl (the one opus invocation per feature) + `architect-reviewer` [sonnet] for holistic + cross-phase design check. CRITICALs at this stage → `FINAL_ESCALATION.md` + ask user.

### Spawn-count impact

| Path | Old | New |
|---|---|---|
| Light/Minimal task | ~4 spawns × N saves (Stop hooks) | **0 spawns** (main agent only) |
| Deep feature, 5 phases | ~145 spawns, ~31 OPUS | ~30-40 spawns, ~1 OPUS |

### Files changed

- `settings.json` (live + dotfiles mirror): all four Stop hooks removed, PreToolUse preserved
- `~/.claude/CLAUDE.md` (+ dotfiles): Feature-Development Skill rule rewritten — classification gate, semantic signals, asymmetric default, Light path with self-review
- `~/.claude/rules/tdd.md` (+ dotfiles): test-layer rule (unit always, integration when crossing boundaries, E2E when user-facing) + full-suite zero-regression requirement
- `tlmforge/agents/phase-auditor.md`: NEW
- `tlmforge/agents/tester.md`: Stage 3 round-1 emits `tester_edge_cases.json`; Stage 4 phase-end runs the suite itself and cross-checks evidence; round-2/3 framing
- `tlmforge/agents/architect-reviewer.md`: round-2/3 framing; Stage 5 holistic + cross-phase framing
- `tlmforge/agents/threat-modeler.md`: round-2/3 framing
- `tlmforge/agents/ux-reviewer.md`: round-2/3 framing; conditional Stage 4 phase-end framing
- `tlmforge/agents/code-reviewer.md`: Stage 4 phase-end framing
- `tlmforge/skills/feature-development/SKILL.md`: classification-gate reference; Stage 3 bounded loop; Stage 4 TDD with layer discipline + new phase-end protocol; Stage 5 single-shot dual audit
- `tlmforge/skills/feature-development/reviewer-convergence.md`: per-stage roster updated; round-aware prompt template; Stage 5 skip rule replaced; carryover artifact section added

### Migration

Existing features with `phase-N-review.md` from old Stage 4.6 are read-only history. New features write to `phase-N-verification/<reviewer>.{md,json}` instead.

If you have in-flight features that wrote JSON sidecars to the old non-round-numbered paths (e.g., `agent_verification/tester_review.json` from previous unbounded convergence), the new convergence script expects round-aware paths. Either restart the feature under the new flow or rename old files to `round-1-<reviewer>.json`.

---

## 0.4.0 (2026-05-11)

### Fixes

- **Path fix (plans/ → specs/):** All agent output paths corrected to `specs/<feature>/agent_verification/`. Fixes a silent bug where threat-modeler and red-team-reviewer wrote JSON sidecars to `plans/` while the convergence script looked in `specs/` — causing convergence to always inject synthetic `reviewer_json_missing` findings for those roles.

- **Artifact writing (code-reviewer, ux-reviewer):** Added `Write` and `Edit` to both agents' tools lists. They now physically write `code_review.md` and `ux_review.md` artifacts to `specs/<feature>/agent_verification/` instead of producing prose-only output.

- **Process-compliance hook (TIER1 override):** Fixed a security hole where "be quick" / "just do it" keywords bypassed TIER1 path enforcement (auth, encryption, payments, PII, migrations) unconditionally. TIER1 detection now fires before the override check. TIER1 + override goes through LLM judgment: hard floor (>2 files or >50 LOC blocks unconditionally), LLM judgment below the floor can escalate dangerous one-line changes.

### Hardening

- **Tester agent:** Now runs the actual test suite (Python/JS/Flutter/Go runner auto-detected), reports real coverage numbers and uncovered line ranges, generates executable test stubs for CRITICAL/HIGH findings. Writes `tester_review.md` + `tester_coverage.md` artifacts. Scopes findings to phase diff when running as Stage 4.6 per-phase re-review.

- **Code-reviewer agent:** Now builds a file:line test gap table for every changed source file, writes `code_review.md` artifact. Uses `TLMFORGE_FEATURE_DIR` env var to detect feature context vs Stop-hook mode.

- **UX-reviewer agent:** Now writes a structured findings table (Component | File:line | Issue | Severity | Fix) to `ux_review.md`. Explicitly required to say "no issues found" rather than silencing — silence is treated as a missing artifact by the convergence check.

- **Per-phase re-review (Stage 4.6):** After each Phase 4 phase completes, tester + code-reviewer run against the phase diff (anchored to `phase-N-state.md git_sha`, not just `HEAD~1`). CRITICAL or HIGH findings block the next phase. Output written to `phase-N-review.md`.

- **Conditional human gates:** Stage 1→2 gate now fires only when findings are tagged `[GATE-BLOCKING]` or the feature touches TIER1 keywords. Stage 2→3 gate fires only when the plan introduces decisions not already approved. Unconditional sentinels removed — agents are the quality gate once intent is confirmed.

### Migration note

If you have in-flight features with JSON sidecars already written to `plans/<feature>/agent_verification/`, copy them before resuming:

```bash
cp -r plans/<feature>/agent_verification/ specs/<feature>/agent_verification/
```

This is a one-time migration step. New iterations will write to `specs/` automatically.
