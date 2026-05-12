# Convergence-loop redesign — lean review architecture

## Context

The Claude Max $200/mo quota burned 1/3 in a single day. At that rate the plan
covers ~3 days, not a month. The agent-invocation map shows ~145 subagent spawns
per typical 5-phase feature, ~31 of them on opus. Biggest line item: the
**tester Stop hook fires opus on every save** (~30 invocations per feature,
each re-reading files + re-enumerating edge cases on overlapping surface).

The current 7-stage flow has reviewers re-doing the same analysis at 3+ stages
with nothing carrying forward. Same agent, overlapping inputs, no cross-stage
handoff.

**The redesign:** eliminate continuous Stop-hook review. Replace with a small
number of well-gated review points: a plan-review iterative loop (max 3 rounds,
findings carry forward), a per-phase end verification (promised-vs-delivered
+ test-execution check), and a final 2-agent audit (adversarial + holistic).
Also: a Light/Minimal path for small work that preserves TDD discipline without
spawning any subagents.

**Critically:** all gating is semantic (Claude self-classifies + user confirms),
not path-based. The plugin is generic and cannot assume MemX-specific directories.

**Target:** ~28-40 subagent spawns per Deep feature run, **0 spawns** per Light
run. Net ~75-85% reduction vs today.

---

## New flow

```
                            ╭───────────────────╮
                            │ Classification    │
                            │  gate (no spawn)  │
                            ╰─────────┬─────────╯
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                                ▼
      ╔══ LIGHT/MINIMAL ══╗                            ╔══ DEEP ══╗
      ║  Main agent only  ║                            ║  Skill   ║
      ║  (0 subagent      ║                            ║  invoked ║
      ║   spawns)         ║                            ╚══════════╝
      ╚═══════════════════╝
              │
              ▼
   1. Identify applicable test layers (unit/integration/E2E)
   2. Write tests FIRST                                  ┌─────────────────────────────┐
   3. Run tests → confirm RED                            │ Stage 1: Spec audit         │
   4. Implement                                          │ (main Claude only)          │
   5. Run new + FULL test suite → GREEN, 0 regressions   └─────────┬───────────────────┘
   6. Self-review checklist (TDD, security, surprises)             │
   7. Commit + push                                                ▼
                                                        ┌─────────────────────────────┐
                                                        │ Stage 2: Master plan        │
                                                        │ (main Claude only)          │
                                                        └─────────┬───────────────────┘
                                                                  │
                                                                  ▼
                                                   Stage 3: Plan review — max 3 rounds
                                                   ┌─────────────────────────────────┐
                                                   │ R1: architect + tester +        │
                                                   │     threat-modeler (+ ux if UI) │
                                                   │   parallel; read spec+plan;     │
                                                   │   → round-1-<rev>.{md,json}     │
                                                   ├─────────────────────────────────┤
                                                   │ Claude fixes plan →             │
                                                   │   round-1-fixes.md              │
                                                   ├─────────────────────────────────┤
                                                   │ R2: SAME reviewers read THEIR   │
                                                   │   round-1 findings + fix;       │
                                                   │   verdict OK/NotOK              │
                                                   ├─────────────────────────────────┤
                                                   │ R3 (if needed): same again      │
                                                   ├─────────────────────────────────┤
                                                   │ If still NotOK → ESCALATION.md  │
                                                   │   → ask user                    │
                                                   └─────────┬───────────────────────┘
                                                             │
                                                             ▼
                                                Stage 4: Phase execution (per phase)
                                                ┌─────────────────────────────────┐
                                                │ Main Claude implements with TDD:│
                                                │  1. Read tester_edge_cases.json │
                                                │     (Stage 3 scenarios)         │
                                                │  2. For each scenario → assign  │
                                                │     a test layer (unit/integr/  │
                                                │     E2E). Add new scenarios     │
                                                │     ONLY if impl surfaces them. │
                                                │  3. Write tests FIRST (per      │
                                                │     scenario at its layer)      │
                                                │  4. Run → RED                   │
                                                │  5. Implement                   │
                                                │  6. Run new + FULL suite → GREEN│
                                                │     + 0 regressions             │
                                                │  7. Capture test run output     │
                                                │     into phase-N-evidence.md    │
                                                │ NO Stop hooks during this!      │
                                                ├─────────────────────────────────┤
                                                │ Phase end (3 agents + 1 cond.): │
                                                │  - code-reviewer                │
                                                │  - tester (confirms ALL layers  │
                                                │    present + all passing)       │
                                                │  - phase-auditor (promise vs    │
                                                │    delivered, incl. tests)      │
                                                │  - ux-reviewer (CONDITIONAL on  │
                                                │    UI files in phase diff)      │
                                                │ Output: phase-N-verification/   │
                                                │ Same 3-round cap as Stage 3     │
                                                └─────────┬───────────────────────┘
                                                          │
                                                          ▼
                                                Stage 5: Final audit — 2 agents
                                                ┌─────────────────────────────────┐
                                                │  red-team-reviewer [opus]       │
                                                │    full diff, adversarial       │
                                                │  architect-reviewer [sonnet]    │
                                                │    full diff, holistic +        │
                                                │    cross-phase design check     │
                                                │  Both single-shot, parallel     │
                                                │  Output: final_audit.{md,json}  │
                                                └─────────┬───────────────────────┘
                                                          │
                                                          ▼
                                                Stage 6: Live verification (unchanged)
                                                          │
                                                          ▼
                                                Stage 7: STATUS.md (unchanged)

PreToolUse hook on ExitPlanMode (architect-reviewer): UNCHANGED.
NO other Stop hooks. NO hardcoded path-based gating anywhere.
```

---

## Architectural changes

### A1. Eliminate all four Stop hooks

**Files:** `~/.claude/settings.json` + `~/dotfiles/claude/global/settings.json`

Remove from `hooks.Stop`:
- tester (opus) — was firing on every code change
- code-reviewer (sonnet) — was firing on every code change
- ux-reviewer (sonnet) — was firing on UI changes
- process-compliance (sonnet) — was firing on every assistant turn

**Keep:**
- `hooks.PreToolUse[ExitPlanMode]` → architect-reviewer (safety net for plans outside the skill)
- `hooks.SessionStart` → sync-claude-settings.py (unrelated)

### A2. Classification gate (replaces both ambiguous-task gate and TIER1 hook)

**Files:** `~/.claude/CLAUDE.md` + `~/dotfiles/claude/global/CLAUDE.md` (the
"Feature-Development Skill — MANDATORY" rule)
**Files:** `$REPO_ROOT/skills/feature-development/SKILL.md` (When-to-use section)

**Generic semantic classification — no project-specific paths.**

Before doing any non-trivial work, Claude main agent self-classifies the task
along these dimensions:

- **Security surface:** does this touch auth, encryption, secrets, credentials,
  PII handling, access control, or session/token mechanics?
- **Persistent state:** does this change a database schema, run a migration,
  alter file-format contracts, modify config that production systems read, or
  perform any irreversible operation?
- **Cross-module scope:** does this touch >5 files OR cross 2+ modules/services/
  packages OR change a public API contract that other code depends on?
- **Customer-facing impact:** does this change a UI surface, a public API
  response shape, an error message users see, or a billing/quota path?
- **User language signals:** did the user say "be quick" / "trivial" / "just
  do it" (→ Light) OR "production" / "important" / "fool-proof" / "thorough"
  (→ Deep)?
- **Task ambiguity:** is there a clear right answer or are there multiple
  reasonable approaches the user might prefer differently?

Claude proposes a verdict: **Deep** or **Light/Minimal**. Then asks via
AskUserQuestion:

```
This task looks like [N files, ~M LOC, area: <area description>].
Signals: <which dimensions triggered>.
My read: <Deep|Light>.

  (a) Confirm Light/Minimal — main agent does TDD + self-review, no subagent spawns
  (b) Override to Deep — full skill: plan + multi-agent review + per-phase verification
  (c) Other
```

**Decision rule (asymmetric, defaults to safety):**

| Claude says | User says | Outcome |
|---|---|---|
| Light | Light | Light/Minimal path |
| Light | Deep | Deep path (user override wins) |
| Deep | Light | Deep path (Claude's caution wins; user can rerun with explicit "be quick" if certain) |
| Deep | Deep | Deep path |

In words: **either party can escalate to Deep; both must agree on Light to skip
the deep process.**

**No hardcoded paths anywhere.** A backend file at `services/payments/charge.py`
in one project and at `lib/billing/processor.ts` in another both register on
"security surface + persistent state" — the classifier looks at the WORK, not
the path string.

### A3. Light/Minimal path with self-review discipline

**File:** `$REPO_ROOT/skills/feature-development/SKILL.md`
(replaces the current "Minimal intensity" section)

Light/Minimal mode means: no subagent spawns, no formal plan docs, no
agent_verification artifacts. But the main agent still owns full discipline:

1. **Identify applicable test layers.** Always: unit. Add integration if the
   change crosses module/service boundaries. Add E2E if the change affects a
   user-facing flow. The main agent decides; if uncertain, skews toward more
   tests.
2. **Write tests FIRST (TDD)** for every layer applicable to the change.
3. **Run tests — confirm RED.** A test that passes before implementation is
   worthless.
4. **Implement the minimum code.**
5. **Run new tests AND the FULL existing test suite.** Confirm GREEN across
   the board AND zero regressions on pre-existing tests.
6. **Self-review checklist** (main agent reviews its own work before declaring
   done):
   - TDD compliance: every new function has a test that covers its behavior
   - No commented-out / TODO / dead code
   - No new magic constants without named binding
   - No new secret-handling, auth, or state mutation that wasn't strictly
     required by the task (if any → re-classify as Deep)
   - No "surprise" behavior changes outside the task's scope
7. **Commit + push.** Commit message describes the change concretely.

If at any step the work expands past what Light/Minimal can handle (e.g.,
discovers a security surface mid-implementation, or finds the change needs to
span >5 files), the main agent **pauses and re-asks the classification gate** —
asking the user whether to escalate to Deep.

**This is NOT "inline = unreviewed."** The main agent is reviewer-in-one. The
discipline survives; only the subagent spawns are skipped.

### A4. Stage 3 plan-review loop with 3-round cap

**File:** `$REPO_ROOT/skills/feature-development/SKILL.md`
**File:** `$REPO_ROOT/skills/feature-development/reviewer-convergence.md`

Replace today's unbounded convergence with a 3-round protocol.

**Round 1 (cold):** parallel — architect-reviewer + tester + threat-modeler
(plus ux-reviewer if UI in scope). Each reads `spec_audit.md` + `README.md`.
Writes `agent_verification/round-1-<reviewer>.{md,json}`.

**Claude main:** consolidates round-1 findings, fixes the plan, writes
`agent_verification/round-1-fixes.md` describing what changed and why per finding.

**Round 2 (verification):** SAME reviewers relaunched with prompt:
- "Read your `round-1-<your-role>.json`. Read `round-1-fixes.md`. Read updated
  README.md. For each of YOUR round-1 findings: verdict FIXED / PARTIALLY /
  NOT_FIXED with file:line evidence. Add new findings only if you see
  something NEW that didn't exist in round 1."
- Output: `agent_verification/round-2-<reviewer>.{md,json}`
- Top-level verdict: `approve | needs_revision`

**Round 3 (final):** same framing against round-2 findings.

**If round 3 still not all approved → write `agent_verification/ESCALATION.md`** listing:
- Outstanding findings per reviewer
- Why Claude couldn't resolve them in 3 rounds
- User decision required: accept risk / extend / revise spec / abandon

### A5. New `phase-auditor` agent

**File:** `$REPO_ROOT/agents/phase-auditor.md` (NEW)

```yaml
---
name: phase-auditor
description: |
  Verifies that a single phase's implementation delivered exactly what its
  phase-N-spec.md promised — including test coverage and execution. Reads
  phase-N-spec.md, phase-N-evidence.md, and the phase diff. Checks: was
  every "in scope" item touched? Were "out of scope" items respected? Was
  the rollback path implemented as promised? Were verification criteria
  met? Are the promised tests present, executed, and passing? Does NOT
  opine on architecture, edge cases, or security — those are other
  reviewers' jobs.
tools: Read, Grep, Glob, Bash, Write, Edit
model: sonnet
---
```

Prompt structure: read phase-N-spec, phase-N-evidence, run `git diff
<phase-start-sha>..HEAD`. Build promise-vs-delivered table including a
dedicated test-coverage section:

- For each promised test in phase-N-spec → exists in diff? passing? at right layer?
- Did `phase-N-evidence.md` include actual test run output (not just claim of run)?
- Were the FULL test suite results captured (regression check)?

Severity:
- CRITICAL: a promised item wasn't delivered, or a promised test is missing/failing
- HIGH: a promised item was delivered incorrectly, or test run output is absent from evidence
- MEDIUM: scope creep detected (delivered more than promised)

### A6. Stage 4 phase-end verification (replaces Stage 4.6)

**File:** `$REPO_ROOT/skills/feature-development/SKILL.md`

At the end of each phase, launch in parallel:

- **code-reviewer** [sonnet]: TDD compliance, pattern consistency, security on
  impl. Reads phase diff + touched files.
- **tester** [sonnet]: did the phase add tests at every applicable layer (unit
  / integration / E2E)? Reads `tester_edge_cases.json` (from Stage 3 tester
  round-1 carryover) + phase diff. Validates coverage AND runs the test suite
  itself to verify pass/fail status against what evidence claims. Cross-checks
  evidence.md against actual test runner output.
- **phase-auditor** [sonnet]: was the phase-N-spec promise kept, including
  test promises?
- **ux-reviewer** [sonnet] — CONDITIONAL: only fires if the phase diff
  contains UI files (file extension or path patterns from a generic
  detection list, not project-specific).

Output: `specs/<feature>/phase-N-verification/<reviewer>.{md,json}`. Same
3-round cap. Round 3 unresolved → ESCALATION.md.

### A7. Stage 5 final audit — 2 single-shot agents

**File:** `$REPO_ROOT/skills/feature-development/SKILL.md`

Two agents in parallel, each single-shot (no iteration):

- **red-team-reviewer** [opus]: adversarial impl review on full diff. "You
  are a malicious user with full code knowledge." Hunts IDOR / TOCTOU / escape
  bugs / token replay / oracle attacks / timing attacks.
- **architect-reviewer** [sonnet]: holistic + cross-phase design check on full
  diff. "Did design debt accumulate across phases? Are inter-phase contracts
  consistent? Did any phase's choice limit another phase's options?"

Output: `specs/<feature>/final_audit_red_team.{md,json}` and
`final_audit_architect.{md,json}`.

If either finds CRITICALs → `agent_verification/FINAL_ESCALATION.md`, prompt
user. Otherwise → Stage 6.

### A8. Test-execution discipline (NEW — fills the gap)

**File:** `$REPO_ROOT/skills/feature-development/SKILL.md`
**File:** `~/.claude/rules/tdd.md` (extend with layer-discipline rule)

Throughout Stage 4 and the Light/Minimal path, the main agent is responsible for:

1. **Sourcing test scenarios and assigning them to layers** at the start of each phase / Light task:

   **Deep path (Stage 4):** read `tester_edge_cases.json` produced by the
   Stage 3 tester as the **seed** list of scenarios. For each scenario, assign
   it to the right test layer. Add new scenarios only if implementation
   surfaces something Stage 3 couldn't have anticipated (e.g., an edge case
   that only becomes visible once the code exists). The scenarios list is
   updated in place — same file, new entries flagged with `source: "impl"` so
   phase-end tester knows they weren't in Stage 3's set.

   **Light/Minimal path:** no Stage 3 happened, so main agent identifies
   scenarios AND layers. Skews toward more tests when uncertain — there's no
   second pair of eyes from a tester subagent here, so the safety margin has
   to compensate.

   **Layer assignment rules (apply in both paths):**
   - **Unit tests:** always required for any new logic
   - **Integration tests:** required when the change crosses module / service
     boundaries, or touches I/O (database, network, file, queue)
   - **E2E tests:** required when the change affects a user-facing flow OR
     a public API contract OR an interaction across services that an end user
     would observe
   - "Wherever there is a possibility of writing tests, more is better — as
     long as it does not become burdensome." Default to more tests; pull back
     only if a layer adds 10× the work for incremental value.

2. **Writing tests FIRST** for every scenario at its assigned layer (TDD).

3. **Running tests after each implementation step:**
   - New tests → confirm GREEN
   - **FULL pre-existing test suite** → confirm zero regressions (this is the
     "no-blast-radius" check)

4. **Capturing test run output into `phase-N-evidence.md`:**
   - Command(s) run (verbatim)
   - Count of tests per layer (e.g., "unit: 42 passed, integration: 8 passed,
     e2e: 3 passed")
   - Total elapsed time
   - Coverage numbers if a coverage runner is available
   - Confirmation that pre-existing tests still pass (e.g., "regression: 156
     pre-existing tests, all passing")

5. **Phase-end verification cross-checks:**
   - tester runs the suite itself and compares against evidence.md's claims
   - phase-auditor checks: are the promised tests (from phase-N-spec) present
     and passing? Is the test layer set complete?
   - If evidence.md claims "all passing" but tester finds failures → CRITICAL

**This applies to BOTH the Deep path (Stage 4) AND the Light/Minimal path.**
The main agent owns test execution either way; it's just verified differently
(by subagent at phase end in Deep, by self-review in Light).

### A9. Keep PreToolUse architect hook

**Unchanged.** Cheap safety net for plans created outside the skill (regular
plan mode work).

---

## Files to modify

| File | Change |
|---|---|
| `~/.claude/settings.json` | Remove 4 Stop hooks; keep PreToolUse + SessionStart |
| `~/dotfiles/claude/global/settings.json` | Mirror |
| `~/.claude/CLAUDE.md` | "Feature-Development Skill" rule rewritten: classification gate with semantic signals, no hardcoded paths |
| `~/dotfiles/claude/global/CLAUDE.md` | Mirror |
| `~/.claude/rules/tdd.md` | Add layer-discipline rule (unit always, integration if module-crossing, E2E if user-facing); add full-suite-no-regression requirement |
| `$REPO_ROOT/agents/phase-auditor.md` | **NEW** — promise-and-test verification |
| `$REPO_ROOT/agents/tester.md` | Stage 3 emits `tester_edge_cases.json`; Stage 4 phase-end verifies all test layers present + runs the suite itself to cross-check evidence claims |
| `$REPO_ROOT/agents/architect-reviewer.md` | Round 2/3 framing; Stage 5 framing for holistic/cross-phase check |
| `$REPO_ROOT/agents/threat-modeler.md` | Round 2/3 framing |
| `$REPO_ROOT/agents/code-reviewer.md` | Stage 4 phase-end framing |
| `$REPO_ROOT/agents/ux-reviewer.md` | Round 2/3 framing if invoked; conditional Stage 4 phase-end invocation when UI files in diff |
| `$REPO_ROOT/skills/feature-development/SKILL.md` | Classification gate; Light/Minimal path with self-review; Stage 3 round protocol; Stage 4 phase-end + test discipline; Stage 5 dual-agent; remove hardcoded path references |
| `$REPO_ROOT/skills/feature-development/reviewer-convergence.md` | Document 3-round cap; carry-forward protocol; new agent roster per stage; phase-auditor entry |
| `$REPO_ROOT/.claude-plugin/plugin.json` | Version bump 0.4.0 → 0.5.0 |

---

## Persistence layout

```
specs/<feature>/
├── spec_audit.md
├── README.md
├── agent_verification/
│   ├── round-1-<reviewer>.{md,json}
│   ├── round-1-fixes.md
│   ├── round-2-<reviewer>.{md,json}
│   ├── round-2-fixes.md (if needed)
│   ├── round-3-<reviewer>.{md,json} (if needed)
│   ├── ESCALATION.md (if 3 rounds insufficient)
│   ├── tester_edge_cases.json    ← Stage 3 tester carryover artifact
│   └── SUMMARY.md
├── phase-N-{spec, verify, evidence, summary, state}.md
├── phase-N-verification/
│   ├── code-reviewer.{md,json}
│   ├── tester.{md,json}
│   ├── phase-auditor.{md,json}
│   ├── ux-reviewer.{md,json} (only if UI files in phase diff)
│   └── round-N-* (if iteration needed)
├── final_audit_red_team.{md,json}
├── final_audit_architect.{md,json}
├── FINAL_ESCALATION.md (if CRITICALs at Stage 5)
├── E2E_VERIFICATION.md
└── STATUS.md
```

---

## Spawn count comparison

| Path | Current flow | New flow |
|---|---|---|
| Light/Minimal task | Stop hooks fired (~4 spawns × N saves) | **0 spawns** (main agent only) |
| Deep feature, 5 phases | ~145 spawns, ~31 OPUS | ~30-40 spawns, ~1 OPUS (red-team) |
| **Reduction** | — | **~75-99% per feature, ~100% for Light tasks** |

---

## Risk audit

| Risk | Severity | Mitigation |
|---|---|---|
| Light/Minimal path expands scope mid-work and ships unreviewed | MEDIUM | Mid-task escalation rule in A3: if Claude discovers security/state/scope creep mid-implementation, pause + re-ask classification gate |
| Claude self-classifies wrong (says Light when actually Deep) | MEDIUM | User confirmation step is the second check. Asymmetric default to Deep on disagreement. Re-classification escape hatch mid-work |
| Test-execution discipline degrades to "I ran tests, trust me" without actual runs | MEDIUM | tester at phase-end RE-RUNS the suite itself and compares to evidence.md claims. Discrepancy → CRITICAL finding |
| 3-round cap leaves CRITICAL findings unresolved | LOW | ESCALATION.md surfaces unresolved items to user; user decides next move. Bounded iteration is a feature |
| New `phase-auditor` lacks historical calibration | MEDIUM | Tight prompt scope ("promise vs delivered, including tests, nothing else") + structured output. Start with one feature, observe verdict quality |
| Round-2 reviewers re-derive instead of verify | MEDIUM | Round-2 prompt EXPLICITLY: "verify each of YOUR round-1 findings; new findings only if NEW." Pin via grep test |
| Eliminating Stop hooks loses real-time review during dev | MEDIUM | Phase-end batch verification covers the surface. Trade continuous coverage for batch coverage at well-defined gates. Light path keeps discipline via self-review |
| Cross-phase issues missed without Stage 5 architect | LOW | Stage 5 now has architect-reviewer with explicit holistic/cross-phase framing |
| Generic UI detection (no project paths) misses some UI files | LOW | Use file extension + content heuristics (e.g., `.tsx`, `.vue`, `.dart`, content imports of UI frameworks). Fall through to "no UX review" if uncertain — no false-positive risk, only false-negative on exotic stacks |

---

## TDD / verification plan

| Phase | Test | Pass criteria |
|---|---|---|
| A1 | `grep -c '"tester"' ~/.claude/settings.json` in Stop hooks block | 0 |
| A1 | `grep -c '"process-compliance"' ~/.claude/settings.json` | 0 |
| A1 | PreToolUse hook preserved | `grep "PreToolUse" ~/.claude/settings.json` → present |
| A2 | No hardcoded MemX-specific path strings in SKILL.md or CLAUDE.md | `grep -E 'backend/memx_app\|scripts/encryption\|memx-ui-v2' SKILL.md CLAUDE.md` → 0 matches |
| A2 | Classification gate language present | `grep -i "Light\|Minimal\|Deep\|classification" SKILL.md CLAUDE.md` → ≥3 |
| A2 | Asymmetric-default rule documented | `grep -i "both must agree\|either.*Deep" SKILL.md` → ≥1 |
| A3 | Light path discipline documented | `grep -i "self-review\|main agent" SKILL.md` (Light section) → ≥3 |
| A4 | 3-round cap documented | `grep -c "round-1\|round-2\|round-3\|3-round\|3 rounds" SKILL.md` → ≥3 |
| A4 | Carry-forward language explicit | `grep "round-1-fixes\|YOUR round-1 findings" SKILL.md` → ≥1 |
| A5 | phase-auditor.md exists with correct frontmatter | `grep "^name: phase-auditor" agents/phase-auditor.md` |
| A5 | phase-auditor includes test verification | `grep -i "test.*present\|test.*passing" agents/phase-auditor.md` → ≥1 |
| A6 | Phase-end roster (code-reviewer + tester + phase-auditor) in SKILL.md | `grep "phase-auditor" SKILL.md` → ≥1 |
| A6 | ux-reviewer conditional at phase-end | `grep -i "ux-reviewer.*if UI\|ux-reviewer.*condition" SKILL.md` → ≥1 |
| A7 | Stage 5 has 2 agents | `grep -B2 -A8 "Stage 5" SKILL.md` shows both red-team-reviewer and architect-reviewer |
| A8 | Test layers explicit | `grep -i "unit.*integration.*e2e\|test layers" SKILL.md tdd.md` → ≥1 |
| A8 | Full-suite regression requirement | `grep -i "full.*test suite\|0 regression\|zero regression" SKILL.md tdd.md` → ≥1 |
| A8 | phase-N-evidence requires test run output | `grep -i "test run output\|test command" SKILL.md` → ≥1 |
| A9 | PreToolUse hook unchanged | diff vs current settings.json shows only Stop hook removals + Stage hook prompt updates |

**End-to-end verification:**

1. **Spawn-count baseline** — pre-deploy, measure spawns on a sample feature run.
2. **Light path test:** announce a 2-file change. Confirm classification gate fires, user can pick Light. Main agent does TDD + tests + commits. Zero subagent spawns.
3. **Deep path test:** announce a 6-file change touching security surface. Confirm gate fires, both Claude and user agree Deep. Skill engages full new flow.
4. **Mid-task escalation:** start Light path, midway have Claude discover a security surface in the diff. Confirm Claude pauses + re-asks gate.
5. **3-round cap:** intentionally introduce a CRITICAL that Claude can't fix in 3 rounds. Confirm ESCALATION.md is written and user prompted.
6. **Test discipline:** in a phase, write code without running the full suite first. Confirm phase-end tester catches the missing evidence and flags CRITICAL.
7. **Generic classifier:** repeat the Light/Deep test on a non-MemX-shaped project (e.g., a JS frontend, a Go service, a Flutter app). Confirm classification works without path-specific rules.

---

## Decisions made

- **Generic classification only.** No project-specific path strings anywhere in
  the plugin. Semantic signals (security surface, state changes, scope,
  customer-facing impact, user language) classify the work.
- **Asymmetric default to Deep.** Either Claude or the user can escalate to
  Deep; both must agree on Light to skip. Bias to safety.
- **Light path is "main agent reviews itself," not "unreviewed."** TDD + full
  test suite + self-review checklist. Discipline survives.
- **Test layers + full-suite regression are first-class.** Unit always;
  integration when module-crossing; E2E when user-facing. Pre-existing tests
  must pass (no regressions). Evidence files must include actual run output.
- **3-round cap on plan review and phase-end verification.** Bounded iteration,
  escalation to user on round 3.
- **Sonnet by default; opus only for red-team-reviewer at Stage 5.**
- **Stage 3 keeps the trio** (architect + tester + threat-modeler); ux-reviewer
  conditional on UI scope.
- **New phase-auditor role** with tight "promise vs delivered + tests" scope.
- **Stage 5 is 2 agents** (red-team + architect) to preserve cross-phase
  holistic review while staying single-shot.
- **PreToolUse architect hook stays** as cheap insurance for plans created
  outside the skill.
- **No caching knob.** Claude Code CLI auto-caches stable prefixes. Lever is
  invocation count, not per-invocation cost.

---

## Version bump

`.claude-plugin/plugin.json` 0.4.0 → **0.5.0**.

**CHANGELOG note:**

> Lean review architecture. Stop hooks (tester, code-reviewer, ux-reviewer,
> process-compliance) removed entirely. Replaced by:
>
> 1. **Classification gate** — Claude classifies tasks by semantic signals
>    (security, state, scope, customer-facing, user language), user confirms.
>    Both must agree Light to skip deep process; either says Deep → Deep.
>    No hardcoded paths.
> 2. **Light/Minimal path** — main agent does TDD + full test suite + self-review,
>    zero subagent spawns.
> 3. **Deep path** — Stage 3 bounded 3-round plan review with findings
>    carry-forward; Stage 4 per-phase verification (code-reviewer + tester +
>    phase-auditor + conditional ux-reviewer); Stage 5 dual single-shot audit
>    (red-team + architect for cross-phase holistic check).
> 4. **Test discipline** — all applicable layers (unit / integration / E2E),
>    full pre-existing suite passing, run output in evidence.md, tester
>    re-runs suite at phase end to cross-check evidence claims.
> 5. **New `phase-auditor` agent** — tight scope on promised-vs-delivered
>    including test promises.
>
> ~75-99% spawn reduction per feature (Light: 100%; Deep: ~75%). Stage 5 stays
> at 2 agents to preserve cross-phase review.

**Migration:** existing features with `phase-N-review.md` from old Stage 4.6
are read-only history. New features write to
`phase-N-verification/<reviewer>.{md,json}`.
