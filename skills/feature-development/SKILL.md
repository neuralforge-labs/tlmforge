---
name: feature-development
description: Use this skill for ALL feature development work — new features, non-trivial bug fixes, refactors touching 3+ files, integrations, migrations, anything that changes user-facing behavior or touches production data. The ONLY exception is very small bug fixes (typo, single-line logic fix, config change with zero behavioral impact). Triggers on ANY implementation request that isn't a trivial one-liner — "add X", "implement Y", "build Z", "integrate W", "refactor X", "migrate Y", "ship X", "make X work", "fix X" (when fix requires multi-file changes), or any feature that modifies more than one file. Enforces the spec-audit → master-plan → multi-agent-review → phase-gated TDD execution → re-review → live verification → operator tooling workflow with detailed artifacts in `specs/<feature>/` so any reviewer can audit the trail end-to-end.
---

# Feature Development — The Hands-Off Recipe

This skill is the **operating manual** for building features the way the
MemX CMEK encryption rollout went: every architectural choice captured
before code was written, every phase reviewed by independent agents,
every claim backed by reproducible evidence, every step reversible. By
the end an external reviewer can audit the full trail and reach the
same conclusion you did.

The encryption story (`specs/encryption/`) is the **worked example** for
this recipe — read it once if you've never done a feature this way.

---

## When to use

This skill is invoked **only after the classification gate** (defined in
`~/.claude/CLAUDE.md`'s "Feature-Development Skill" section) routes a task to
the **Deep** path. The decision is made by Claude main + user confirmation
using semantic signals (security surface, persistent state, cross-module
scope, customer-facing impact, user language) — NOT hardcoded file paths.

If you're invoked, you're on the Deep path. Light/Minimal tasks never reach
this skill — they're handled inline by the main agent with TDD + full test
suite + self-review.

### Deep path — what this skill does (this whole document)

The Deep path runs the full 7-stage recipe: spec audit → master plan →
bounded 3-round plan review → phase-gated TDD execution with phase-end
verification → dual single-shot final audit → live verification → status
dashboard.

### When NOT in this skill (Light/Minimal — handled in CLAUDE.md)

If you're reading this because you were unsure: ask the classification gate
first. The user picks Light or Deep before any planning artifacts get
created. Producing `spec_audit.md` and `README.md` for a task the user
wanted handled inline is the failure mode this triage prevents.

### Mid-task escalation

If a task started as Light/Minimal and discovers mid-implementation that it
expanded into Deep territory (e.g., found a security surface, scope exceeded
~5 files, schema change appeared), the main agent **must pause and re-ask
the classification gate**. The user may escalate to Deep, at which point
this skill takes over from Stage 1.

---

## The recipe at a glance

```
Stage 1: Request audit (main Claude)         →  specs/<f>/spec_audit.md
         ↓  conditional gate (only if ANY [GATE-BLOCKING] open question)
Stage 2: Master plan (main Claude)           →  specs/<f>/README.md
         ↓  conditional gate (only if plan introduces unapproved decisions)
Stage 3: Plan review — bounded 3-round loop
   R1: architect + tester + threat-modeler   →  agent_verification/round-1-<reviewer>.{md,json}
         (+ ux-reviewer if UI in scope)        + tester_edge_cases.json (carryover)
         ↓  main Claude fixes plan + writes round-1-fixes.md
   R2: SAME reviewers VERIFY their R1 findings → round-2-<reviewer>.{md,json}
         ↓  main Claude fixes again if needed
   R3: same — final verdict                  →  round-3-<reviewer>.{md,json}
         ↓  if still NotOK → ESCALATION.md + ask user
Stage 4: Phase execution (per phase, with TDD + full-suite + 0 regressions)
         Main Claude implements with TDD:
            - reads tester_edge_cases.json as scenario seed
            - assigns each scenario to a layer (unit/integration/E2E)
            - writes tests FIRST → RED → impl → GREEN + 0 regressions
            - captures test-run output into phase-N-evidence.md
         Phase-end verification (3 agents + 1 conditional, max 3 rounds):
            code-reviewer + tester + phase-auditor [+ ux-reviewer if UI]
                                                  →  specs/<f>/phase-N-verification/<reviewer>.{md,json}
         ↓  loop per phase
Stage 5: Final audit (2 single-shot agents, parallel)
   red-team-reviewer (adversarial impl)      →  agent_verification/final_audit_red_team.{md,json}
   architect-reviewer (holistic cross-phase) →  agent_verification/final_audit_architect.{md,json}
         ↓  if CRITICALs → FINAL_ESCALATION.md + ask user
Stage 6: Live verification + tooling          →  specs/<f>/E2E_VERIFICATION.md, ROLLOUT_PLAN.md,
                                                  scripts/<feature>/{...,README.md}
         ↓
Stage 7: STATUS.md                            →  specs/<f>/STATUS.md (executive dashboard)
```

You may not skip ahead. Each stage gates the next. Stop hooks are NOT involved
— review happens at the well-defined gates above (Stage 3 rounds, Stage 4
phase-end, Stage 5 final).

---

## Stage 1 — Request audit (produces `spec_audit.md`)

**Goal:** Audit the **user's request** — treat that request AS the
incoming spec — and surface every hidden assumption, threat, performance
concern, edge case, and irreversible step in it BEFORE investing in a
design.

The output IS the structured spec. "Spec audit" is forward-looking — the
artifact being produced (`spec_audit.md`) is the audit of the user's
stated intent. There is no pre-existing spec document being reviewed at
this stage; Stage 1 is the act of turning a vague-or-precise human
request into a structured artifact with surfaced unknowns.

This is the **single most valuable artifact**. The encryption README's
F1-F16 audit is what made everything that followed solid.

**Read project learnings first.** Before writing the audit, check for
`<project-root>/learnings.md` (a hybrid per-project log appended to by
prior features at Stage 7 — see Stage 7 below). If present, read up to
the last 100 KB; treat malformed UTF-8 with `errors="replace"` and
proceed if absent / unreadable / binary (graceful absence is the
default — never block on a missing or corrupted learnings file).
Distill the most-recent 3-5 entries into the spec audit's findings
*only if relevant*; do not just copy entries forward. Stale or
project-irrelevant learnings should be ignored, not parroted.

Save to `specs/<feature>/spec_audit.md`:

```markdown
# <Feature> — Spec Audit

## What the user asked for
<2-3 sentences, plain English>

## Industry standard / how others do this
<Bullet 2-4 prior-art comparisons. Be honest about your knowledge.>

## Findings (severity-ranked)

### CRITICAL — Decisions needed before any code

#### F1. <Short title>
- **Spec said:** <quote or paraphrase>
- **Industry standard:** <what's normal>
- **Problem:** <concrete failure mode with numbers if possible>
- **Recommendation:** <what to do>
- **Decision required:** <yes/no question for the user>

#### F2. ...

### HIGH — Should fix before [enforcement / launch / migration]

#### F6. ...

### MEDIUM / LOW
...

## Open questions for the user
1. ...
2. ...
```

**Coverage rule (instead of a numeric floor):** the audit must explicitly
address each of these surfaces. If any has zero findings, state explicitly
why it's a non-issue for this feature:

- (a) Security surface (auth, secrets, injection, IDOR, PII)
- (b) Concurrency / race conditions / idempotency
- (c) Failure modes under partial failure (network, KMS down, quota, timeout)
- (d) Cost impact (real numbers; flag guesses)
- (e) Rollback safety / blast radius

Padding with manufactured LOW findings is worse than fewer real ones.

### Stage 1 → Stage 2 gate (conditional — only when human input is needed)

After writing `spec_audit.md`, evaluate whether the audit contains **open questions
that only the user can answer** — product decisions, scope choices, or irreversible
tradeoffs that aren't derivable from the codebase or the user's stated request.

The gate is structural, not a judgment call. In the spec audit's "Open questions
for the user" section, tag every question as `[GATE-BLOCKING]` or `[INFORMATIONAL]`:

- `[GATE-BLOCKING]` — a fork in the road only the user can resolve (scope,
  irreversible tradeoff, product decision). Default to this tag when uncertain.
- `[INFORMATIONAL]` — a risk Claude will address in the plan; no user decision needed.

**The gate fires if ANY question is tagged `[GATE-BLOCKING]`. That is the entire rule.**
No hardcoded keyword list (auth/payment/etc.); the plugin is generic and shouldn't
assume project-specific sensitivity terms. If a sensitive area was genuinely touched,
it surfaces as a `[GATE-BLOCKING]` question during the audit — trust the audit's
own tagging discipline. The classification gate at task entry (see
`~/.claude/CLAUDE.md`) already routed Deep work to this skill; we don't need a
second classifier here.

**If gate fires:**
End your message with: `SPEC_AUDIT_COMPLETE — [GATE-BLOCKING] questions require your input: [list them]`
Do NOT proceed to Stage 2 until the user replies.

**If gate does not fire (no `[GATE-BLOCKING]` questions):**
Proceed directly to Stage 2 in the same turn. The user approved the goal; agents
own quality.

The asymmetry is intentional: a false positive (unnecessary gate) costs one round-trip.
A false negative (skipped gate on a product decision) can cost a wasted feature.

---

## Stage 2 — Master Plan

**Goal:** Translate the audited spec into an executable plan with
numbered phases, each one independently shippable and reversible.

Create `specs/<feature>/README.md`:

```markdown
# <Feature> — Master Plan

## Context
<3-5 sentences: why, what problem, what success looks like>

## Scope
**In:** ...
**Out (explicitly):** ...

## Threat model / requirements / constraints
What we're defending against. What we're NOT.

## Architecture
ASCII diagrams for every changed flow. Box-and-arrow for system layout.
Visual is essential — text alone is not enough.

## Sensitive surface inventory
Every field / table / route / function / screen the change touches.
Be exhaustive. This is the blast-radius bookkeeping.

## Phases
Each phase: goal | steps | files modified | tests added | verification | rollback.
No phase larger than one session of work.
No irreversible phase without an explicit user gate.

## Risk audit
Severity-tagged list of flaws/risks the plan glosses over. Carry forward
from spec_audit.md plus anything new.

## Decisions made
Bulleted: what was chosen, why, what alternatives were rejected.

## Cost analysis
Real numbers. Mark guesses as guesses with citation.

## Open questions for the user
Things that need explicit sign-off before implementation.

## TDD plan
Test files to create per phase, what they verify, expected RED→GREEN.
The TDD plan covers pre-planned phases only. Sub-phases (5b, 5c, etc.)
are designed at the time they are created, not pre-allocated here.

## Verification criteria
How to prove the feature works. Measurable, not subjective.
```

**Phase numbering rules** (follow encryption's pattern):
- Phase 0 = infrastructure / scaffolding (KMS keyring creation)
- Phase 1 = pure crypto / pure logic (TDD-heavy, no integration)
- Phase 2..N = integration into product surfaces, one surface per phase
- Last phase(s) = irreversible cleanup (plaintext stripping, key destruction)
- Sub-phases (`5b`, `5c`, `5d`) get added LATER when post-rollout review
  finds gaps. Don't pre-allocate them.

### Stage 2 → Stage 3 gate (conditional — only when plan introduces new decisions)

After writing `README.md`, evaluate whether the plan introduces **decisions or tradeoffs the
user hasn't already approved** — scope changes, architectural choices that weren't in the
original brief, irreversible operations that need explicit sign-off.

**If yes (plan contains new unapproved decisions):**
End your message with: `MASTER_PLAN_COMPLETE — new decisions in the plan need your sign-off: [list them]`
Wait for explicit approval before launching agents.

**If no (plan faithfully executes the already-approved intent):**
Launch Stage 3 agents immediately in the same turn. Agents are the gate — human doesn't need
to approve what they already approved. The convergence loop handles quality from here.

The only other reason to gate: the plan includes an **irreversible production operation**
(data migration, schema drop, key destruction). Gate those explicitly regardless of prior approval.

---

## Stage 3 — Plan review (bounded 3-round loop)

**Goal:** Independent verification that the plan is sound, by reviewers who
didn't watch you write it. **Hard cap: 3 rounds.** If unresolved findings
remain after round 3, escalate to the user — do NOT spin indefinitely.

**Structured-output requirement:** Every reviewer emits a JSON sidecar
(`<role>_review.json`) alongside the prose markdown report. The JSON validates
against `~/.claude/skills/feature-development/review_schema.json`. The agent
prompt addition (literal text to insert into every launch prompt) is in
[`reviewer-convergence.md`](reviewer-convergence.md). Without it, the
convergence script injects a synthetic `reviewer_json_missing` finding for
that role.

**Model selection:** All Stage 3 reviewer subagents use `model="sonnet"`
(no version pin). Opus is reserved for `red-team-reviewer` at Stage 5 only.
Sonnet handles plan-level reasoning at this surface; iterating with sonnet
is what makes the 3-round loop affordable.

### Default Stage 3 roster

- `architect-reviewer` — would a senior L8/E8 architect ship this design?
- `tester` — what edge cases / race conditions / failure modes does the design plan to handle?
  Also emits the carryover artifact `tester_edge_cases.json` at round 1 (see "Carryover artifacts" below).
- `threat-modeler` — what does the design ASSUME that an attacker can violate?

**Conditional reviewer:**
- `ux-reviewer` — only when the plan describes UI work

**Not at Stage 3:** `code-reviewer` (no code yet — runs at Stage 4 phase-end);
`red-team-reviewer` (impl-only — runs at Stage 5); `phase-auditor` (phase-bound
— runs at Stage 4 phase-end).

### Round 1 — cold review (parallel)

Emit all reviewer subagents in a single assistant message with multiple
parallel `Agent` tool calls. The agents haven't seen this conversation — brief
them fully via launch prompt. Each agent reads `spec_audit.md` + `README.md`
and writes `agent_verification/round-1-<reviewer>.{md,json}`.

```
Agent(subagent_type="tlmforge:architect-reviewer", model="sonnet", description="...", prompt=<round-1 launch prompt>)
Agent(subagent_type="tlmforge:tester",             model="sonnet", description="...", prompt=<round-1 launch prompt>)
Agent(subagent_type="tlmforge:threat-modeler",     model="sonnet", description="...", prompt=<round-1 launch prompt>)
# + Agent(subagent_type="tlmforge:ux-reviewer", model="sonnet", ...) only if UI scope
```

### Round 1 launch prompt template (copy-paste, fill placeholders)

```
You are reviewing the <FEATURE> design before any code is written.
This is ROUND 1 (cold review).

Working tree: <repo path>
Master plan:  specs/<feature>/README.md
Spec audit:   specs/<feature>/spec_audit.md
Iteration: 1

Your job: find flaws I haven't. Be hostile. Assume I'm wrong about something.

Specifically check (apply your role-specific lens):
1. Does any phase have a hidden irreversible step?
2. Is there a code path the plan doesn't mention that this change affects?
3. What happens under: empty input, partial failure, concurrent access,
   timeout, quota exhaustion, malformed data, old client?
4. <Feature-specific risks>
5. Is the rollback procedure for each phase actually executable in 5
   minutes by an oncall who has never seen this code?

Output format: severity-tagged findings (CRITICAL / HIGH / MEDIUM / LOW),
each with: where it shows up (file:line), why it matters, recommended fix.
Overall verdict: approve / needs_revision / do_not_ship.

Save BOTH:
- agent_verification/round-1-<your-role>.md (prose)
- agent_verification/round-1-<your-role>.json (per the JSON schema in reviewer-convergence.md)

[For tester ONLY] Also emit agent_verification/tester_edge_cases.json — the
carryover artifact. Every CRITICAL/HIGH edge case you raise gets a corresponding
entry. See tester.md "Stage 3 Round 1" section for the schema.
```

### After Round 1 — main Claude fixes

Read all `round-1-<reviewer>.json` files. Address each CRITICAL and HIGH
finding by editing the plan / spec_audit. Write
`agent_verification/round-1-fixes.md` describing what changed and why per
finding (1-2 sentences each). This file is the carryover input for round 2.

### Round 2 — verification (parallel)

Launch the SAME reviewers with the verify-your-findings framing. They read
their own round-1 findings file + the fixes doc + the updated plan. They do
NOT re-derive findings from scratch.

```
Agent(subagent_type="tlmforge:architect-reviewer", model="sonnet", description="...", prompt=<round-2 launch prompt>)
# (same for tester, threat-modeler, ux-reviewer)
```

### Round 2 launch prompt template

```
You are reviewing the <FEATURE> design at ROUND 2.

You reviewed this plan once before. Your round-1 findings are at:
  agent_verification/round-1-<your-role>.json

Main Claude has now fixed the plan in response. The fixes summary is at:
  agent_verification/round-1-fixes.md

The updated plan is at:
  specs/<feature>/README.md

Iteration: 2

Your job:
1. For each of YOUR round-1 findings: verdict FIXED / PARTIALLY / NOT_FIXED
   with file:line evidence in the updated plan.
2. Add NEW findings only for issues you genuinely missed in round 1 — not
   the same finding from a different angle. New signal, not re-derivation.

Save BOTH:
- agent_verification/round-2-<your-role>.md
- agent_verification/round-2-<your-role>.json

Top-level verdict: approve (all your prior findings fixed, no new criticals)
or needs_revision (any not_fixed or new critical).
```

### After Round 2

If **every reviewer's verdict is `approve` AND every round-2 JSON has zero
CRITICAL findings**: proceed to Stage 4.

If any reviewer is `needs_revision` OR any CRITICAL remains: main Claude
fixes again, writes `round-2-fixes.md`, launches Round 3.

### Round 3 — final verification

Same framing as Round 2, against round-2 findings.

If **every reviewer approves and zero CRITICALs**: proceed to Stage 4.

If unresolved findings remain after Round 3: write
`agent_verification/ESCALATION.md`:

```markdown
# ESCALATION — round 3 unresolved findings

## Outstanding by reviewer

### architect-reviewer
- <finding-id> [severity]: <one-line summary> — current state: <NOT_FIXED|PARTIAL>
- ...

### tester
- ...

## Why Claude couldn't resolve in 3 rounds
<1-2 paragraphs — honest account, not excuses>

## User decision required

  (a) Accept the residual risk and ship the plan as-is
  (b) Extend rounds (re-launch round 4 — costs more credits)
  (c) Revise the spec / re-scope the feature
  (d) Abandon — close this feature
```

Surface the escalation to the user via a clear chat message. Do NOT proceed
to Stage 4 without an explicit decision.

### Carryover artifacts (Stage 3 → Stage 4)

- `agent_verification/tester_edge_cases.json` — produced by tester at Round 1.
  Main Claude reads this at Stage 4 as the scenario seed for TDD. Phase-end
  tester reads it as the coverage-validation checklist. (Schema in `tester.md`.)
- All `round-N-<reviewer>.json` files persist for audit trail.

### Final summary (write after Round 2 or 3 approval)

Write `specs/<feature>/agent_verification/SUMMARY.md`:

```markdown
# Agent Verification — Stage 3 Consolidated

| Reviewer | R1 verdict | R2 verdict | R3 verdict | Final |
|---|---|---|---|---|
| architect-reviewer | needs_revision (4C/4H) | needs_revision (1H) | approve | APPROVE |
| tester | do_not_ship (3C) | approve | n/a | APPROVE |
| threat-modeler | needs_revision (2H) | approve | n/a | APPROVE |

## What was actually broken (categories from round 1)
### Category 1: <name>
<concise description; what was wrong; how Claude fixed it>

## Deferred (with rationale)
- <ID>: <description> — deferred to Phase <N> per <reason>

## Carryover artifact
tester_edge_cases.json — <N> scenarios for main Claude to seed Stage 4 TDD.
```

**Do not proceed to Stage 4** until SUMMARY.md exists, every reviewer's final
verdict is `approve`, AND zero CRITICAL findings remain in the final round JSONs.

---

## Stage 4 — Phase-gated execution (TDD, 4 docs per phase)

**Goal:** Build one phase at a time with hard evidence at every gate.

**State handoff to Stage 5.** At the END of each Stage 4 phase, write
`specs/<feature>/phase-N-state.md` containing a frontmatter block with
the current `git_sha:` (abbreviated, e.g., `c66e25a`) and three short
sections: commits-landed, tests-now-passing, anything-that-surprised-me.
Stage 5's re-review reads this file to start cold without re-deriving
context. The `git_sha` lets Stage 5 detect staleness — if HEAD has moved
beyond that SHA, Stage 5 emits a loud warning but proceeds. See
`reviewer-convergence.md` §5 for the state.md format.

For each phase, produce **4 files** in `specs/<feature>/`:

### 4.1 `phase-N-<topic>.md` — the phase spec (write FIRST)

```markdown
# Phase N — <topic>

## Goal
<1-2 sentences>

## Scope
**In:** ...
**Out (explicitly):** ...

## Files to be modified (exhaustive)
- backend/path/to/file.py: <what changes>
- ...

## Tests to be added
- tests/test_X.py::test_Y_does_Z — verifies <behavior>
- ...

## Verification criteria (becomes phase-N-verify.md targets)
- [ ] All new tests pass (RED → GREEN)
- [ ] Existing tests pass (zero regressions)
- [ ] Build clean
- [ ] Live verification: <specific commands or smoke flow>
- [ ] Phase-specific: <e.g. "encrypted_<field> appears in Firestore">

## Rollback
| Action | Time | Data risk |
|---|---|---|
| Revert commit, redeploy | 5 min | None |
| Set feature flag off | 2 min | None |

## Risks deferred to next phase
- ...
```

### 4.2 `phase-N-verify.md` — the verification PLAN (before running)

This is the document that says **what we will check, with which command,
and what passing looks like** — written before you run anything.

```markdown
# Phase N — Verification Plan

## Pre-flight
| Check | Command | Pass criteria |
|---|---|---|
| Tests fail without impl | <cmd> | RED on new tests |
| Existing tests pass | <cmd> | <count> green |

## Post-implementation
| Check | Command | Pass criteria |
|---|---|---|
| New tests pass | <cmd> | <count> green |
| No regressions | <cmd> | same baseline count |
| Build clean | <cmd> | exit 0, no new warnings |
| Live smoke | <cmd> | <expected output> |
| Evidence: <thing> | <how to capture> | <what to look for> |
```

**Why two separate files** (verify.md and evidence.md) instead of one
file with two sections: a reviewer can confirm the pass criteria were
written *before* the run by checking commit timestamps. A single file
can be silently edited after the fact to make the criteria match the
results; two separately committed files cannot. This is the only
guarantee that "we knew what passing looked like before we ran it."

Commit `phase-N-verify.md` BEFORE running tests. Commit
`phase-N-evidence.md` AFTER. Two distinct commits.

### 4.3 Execute

The TDD discipline (`~/.claude/rules/tdd.md`) — applied per test layer:

1. **Source scenarios.** Read `agent_verification/tester_edge_cases.json`
   (produced by Stage 3 tester at Round 1) as the **scenario seed**. For each
   edge case, assign a test layer (unit / integration / E2E). Add new
   scenarios only if implementation surfaces something Stage 3 missed —
   mark these with `source: "impl"` in the JSON so the phase-end tester
   knows they were impl-time additions.
2. **Identify applicable layers:**
   - Unit: always required for new logic
   - Integration: required when crossing module/service boundaries OR
     touching I/O (DB, network, file, queue)
   - E2E: required when affecting a user-facing flow OR public API contract
3. **Write tests FIRST** for every applicable layer.
4. **Run new tests — confirm RED.** A test that passes before impl is
   worthless.
5. **Implement** the minimum code.
6. **Run new tests AND the FULL pre-existing test suite — confirm GREEN
   across the board AND zero regressions on pre-existing tests.** The
   "no-blast-radius" check is non-optional.
7. **Build / compile clean.**
8. **Capture test-run output into `phase-N-evidence.md`** (see 4.4) —
   actual command output with counts per layer, total elapsed, coverage
   numbers if available, and explicit confirmation that pre-existing tests
   still pass.

### 4.4 `phase-N-evidence.md` — what was OBSERVED (after running)

This is the receipt. A reviewer copies the commands and reproduces them.
Phase-end tester re-runs the suite and cross-checks the numbers in this
file against live output — discrepancies are CRITICAL findings.

```markdown
# Phase N — Hard Evidence

## Test runs (per layer)

### Unit tests
$ <runner command>
# Full output, including pass/fail counts and elapsed time.

### Integration tests (if applicable)
$ <runner command>
# ...

### E2E tests (if applicable)
$ <runner command>
# ...

## Full pre-existing test suite (regression check — REQUIRED)
$ <full-suite command>
# Full output. Must show zero new failures vs the pre-phase baseline.

## Summary
- Unit: <count> passed, <count> failed, <elapsed>
- Integration: <count> passed, <count> failed, <elapsed>
- E2E: <count> passed, <count> failed, <elapsed>
- Full pre-existing suite: <count> passed, <count> failed (must be unchanged from pre-phase)
- Coverage (if available): <percentage>; uncovered lines: <list>

## Build
$ <build command>
# Relevant output.

## Live samples (when applicable)
- DB document / table row after the change: <shape>
- API response: <json>
- Logs: <grep result>

## Before vs after
- Before: <state>
- After: <state>

## Reproducibility
A reviewer can reproduce all of the above by:
1. Checkout commit <SHA>
2. Run <command>
3. Observe <result>
```

### 4.5 `phase-N-summary.md` — retrospective with HONEST weaknesses

```markdown
# Phase N — Summary

## Status: ✅ COMPLETE / ⚠ PARTIAL / ❌ BLOCKED

## What was built
<Bulleted, concrete>

## Tests
| Category | Count | Status |
|---|---|---|
| New unit tests | N | ✅ |
| Existing tests | M | ✅ no regressions |

**Total new tests: N. Zero regressions.**

## Deviations from plan
<List or "None">

## Honest weaknesses (a hostile reviewer would attack)
1. <Specific weakness with concrete failure mode>
2. ...

## Risks deferred to Phase N+1
- ...

## Next phase entry criteria
- [x] All N new tests pass
- [x] M existing tests pass
- [x] Phase committed and pushed
- [ ] <any remaining gate>
```

### 4.6 Phase-end verification (after each phase)

After `phase-N-summary.md` is written and committed, run end-of-phase
verification — 3 agents in parallel (+ 1 conditional). Same 3-round cap as
Stage 3: if findings persist after round 3, escalate to user. This catches
bugs at phase boundary before they compound into the next phase, AND
verifies that promised tests are present and passing.

**Diff baseline:** Use the `git_sha:` recorded in
`specs/<feature>/phase-N-state.md` frontmatter (written at phase start, per
§4 State handoff requirement). This anchors the diff to the actual phase
boundary — phases produce multiple commits (spec, verify, impl, evidence,
summary), so `HEAD~1..HEAD` would only see the last commit.

```bash
PHASE_START_SHA=$(grep '^git_sha:' specs/<feature>/phase-N-state.md | awk '{print $2}')
git diff ${PHASE_START_SHA}..HEAD   # full phase diff
```

### Phase-end roster (3 agents, +1 conditional)

Launch in parallel, single assistant message with multiple Agent tool calls:

```
Agent(subagent_type="tlmforge:code-reviewer", model="sonnet", ...)
Agent(subagent_type="tlmforge:tester",        model="sonnet", ...)
Agent(subagent_type="tlmforge:phase-auditor", model="sonnet", ...)
# + Agent(subagent_type="tlmforge:ux-reviewer", model="sonnet", ...) only if UI files in phase diff
```

Detect UI condition with a generic file-extension/path heuristic (e.g.
`.tsx`, `.vue`, `.dart` with material/cupertino imports, `.html/.css`,
Android `res/layout/`). When uncertain, fall through to "no UX review" —
no false-positive risk.

### Round 1 launch prompt template (each reviewer)

```
You are reviewing the phase diff for <FEATURE> Phase <N>.
This is ROUND 1 of phase-end verification.

Feature dir:       specs/<feature>/
Phase spec:        specs/<feature>/phase-N-<topic>.md   (the promise)
Phase evidence:    specs/<feature>/phase-N-evidence.md  (the receipt)
Phase start SHA:   <PHASE_START_SHA>
Scope:             git diff ${PHASE_START_SHA}..HEAD only — cross-phase
                   concerns are NOT in scope at phase end (Stage 5 covers those).
Iteration: 1

Your role-specific framing:
- code-reviewer:  TDD compliance, pattern consistency, security on impl,
                  no dead code, no surprises. Apply your full checklist
                  to the phase diff only.
- tester:         Read agent_verification/tester_edge_cases.json. For each
                  edge case, confirm a test exists in the phase diff at the
                  right layer (unit/integration/E2E). RUN THE SUITE
                  YOURSELF and cross-check against phase-N-evidence.md
                  claimed numbers — discrepancy is CRITICAL.
- phase-auditor:  Promise-vs-delivered. Was every "in scope" item in
                  phase-N-spec.md delivered? Were the promised tests
                  delivered, at the right layer, and passing? Do not
                  opine on architecture or edge cases.
- ux-reviewer:    Accessibility + platform-convention check on the UI
                  files in the phase diff. Scope to phase diff only,
                  not whole-app UX.

Output BOTH:
- specs/<feature>/phase-N-verification/<your-role>.md   (prose)
- specs/<feature>/phase-N-verification/<your-role>.json (per the JSON schema)
```

### Round 2 / Round 3 (if needed)

If any reviewer returns `needs_revision` or any CRITICAL appears: main
Claude fixes, writes `phase-N-verification/round-1-fixes.md`, re-launches
the SAME reviewers with verify-your-findings framing (same protocol as
Stage 3 Round 2). Cap at 3 rounds.

If unresolved after Round 3: write
`phase-N-verification/ESCALATION.md` and prompt the user — same format
as Stage 3's escalation.

### Phase-end verdict aggregation

After every reviewer approves and zero CRITICALs remain in the round-N
JSONs, write `phase-N-verification/SUMMARY.md`:

```markdown
# Phase N — Verification Summary

| Reviewer | R1 | R2 | R3 | Final |
|---|---|---|---|---|
| code-reviewer | approve | n/a | n/a | APPROVE |
| tester        | needs_revision (1H) | approve | n/a | APPROVE |
| phase-auditor | approve | n/a | n/a | APPROVE |
| ux-reviewer   | (n/a — no UI in diff) | — | — | SKIPPED |

## What was caught and fixed
<one-line summary per round>

## Gate decision
- All reviewers approve, zero CRITICALs → proceed to Phase N+1
```

**Blocking rule:** Do not start Phase N+1 until `phase-N-verification/SUMMARY.md`
exists with all reviewers final-verdict = `approve`, OR the user has
acknowledged an `ESCALATION.md` and explicitly approved proceeding with
known residual findings.

### Commit cadence

Commit + push at the end of each phase, with the phase summary doc in
the same commit. The commit message references the phase: `feat(<area>):
phase N — <topic>`. Don't batch multiple phases into one commit.

### When a phase fails review or surfaces unknowns

Add a sub-phase (`phase-Nb-<topic>.md`, `phase-Nc-...`) with the same
4-file structure. The encryption work has 5b/5c/5d for exactly this
reason: agents found gaps post-rollout, each gap got its own auditable
mini-phase. Do **NOT** silently rework the original phase doc — that
destroys the audit trail.

---

## Stage 5 — Final audit (2 agents, single-shot, parallel)

**Goal:** A final cross-cutting check on the complete feature diff — covering
two angles per-phase reviewers couldn't see:
1. **Adversarial impl:** "You are a malicious user with full code knowledge.
   What can you break?"
2. **Holistic / cross-phase design:** "Did design debt accumulate across
   phases? Are inter-phase contracts consistent? Any irreversible operation
   land without being flagged in any phase spec?"

Two agents in parallel, each single-shot — **no iteration at Stage 5.** This
is the last gate, not a convergence loop. If either finds CRITICALs, escalate
to user.

### The two agents

```
Agent(subagent_type="tlmforge:red-team-reviewer", model="opus",   ...)
Agent(subagent_type="tlmforge:architect-reviewer", model="sonnet", ...)
```

- `red-team-reviewer` [opus]: adversarial impl on full diff. Single shot.
  Hunts IDOR / TOCTOU / escape-sequence bugs / token replay / oracle attacks
  / timing attacks. Opus depth justified — this is the one place opus is
  used per feature, and it's where deep reasoning pays off.
- `architect-reviewer` [sonnet]: holistic + cross-phase design check on
  full diff. NOT a re-derivation of design from scratch — focuses
  specifically on inter-phase consistency, accumulated debt, and any
  irreversible operation that slipped through without explicit acknowledgment
  in a phase spec.

**Not at Stage 5:**
- `code-reviewer`: every phase's code-reviewer at Stage 4 phase-end already
  saw it. Cross-phase code quality concerns roll up via
  `architect-reviewer`'s holistic pass.
- `tester`: phase-end tester verified per-phase tests. Cross-phase
  integration testing belongs at Stage 6 live verification.
- `threat-modeler`: only at Stage 3 (design time). Adversarial impl-time
  review is red-team-reviewer's lane.
- `phase-auditor`: phase-bound; doesn't fire at Stage 5.

### Stage 5 launch prompt template

```
You are running Stage 5 final audit on <FEATURE>.

Feature dir:       specs/<feature>/
Full diff scope:   git diff <feature-start-sha>..HEAD
                   (the feature-start-sha is the SHA at the end of Stage 3
                    Round-N — before Stage 4 Phase 1 started)
Single shot:       NO iteration. One pass, one verdict.

Role-specific framing:
- red-team-reviewer:  "Malicious user with full code knowledge." Hunt
                      IDOR / TOCTOU / escape bugs / token replay / oracle
                      attacks / timing attacks. Adversarial impl-time
                      review.
- architect-reviewer: Holistic + cross-phase. Look for design debt
                      accumulated across phases, inter-phase contract
                      consistency, irreversible operations that should
                      have been flagged but weren't.

Output:
- agent_verification/final_audit_<your-role>.md   (prose)
- agent_verification/final_audit_<your-role>.json (per JSON schema)

Verdict: approve | needs_revision | do_not_ship.
```

### Outcomes

- **Both approve, zero CRITICALs:** write `agent_verification/SUMMARY.md`
  marking Stage 5 complete, proceed to Stage 6.
- **Either has CRITICALs:** write `agent_verification/FINAL_ESCALATION.md`
  listing the findings. Surface to user. Options: fix and re-run Stage 5
  (a fresh pair of single-shot calls, not iterative); accept residual risk
  with documented justification; abandon.

**There is no automatic iteration at Stage 5.** The phase-end gates were
the iterative loops. Stage 5 is the punctuation, not another loop.

---

## Stage 6 — Live verification + operator tooling

**Goal:** Prove the feature works on a real deployed environment, and
hand the operator everything they need to roll it out, monitor it, and
roll it back.

### 6.1 Live e2e

- Tests that hit a deployed environment, not mocks. Use a dedicated
  test user (e.g. `encryption_test@memx.app`).
- A canonical reproducibility script:
  ```
  scripts/<feature>/run_<feature>_lifecycle.sh
  # Exit 0 = healthy. Non-zero = regression.
  ```

### 6.2 `specs/<feature>/E2E_VERIFICATION.md`

Real evidence from the deployed environment:
- Sample database records (redact PII)
- Real API roundtrip output
- Per-phase live test results
- Reproducibility instructions (exact commands)

### 6.3 `specs/<feature>/ROLLOUT_PLAN.md` (when gradual rollout needed)

```markdown
# <Feature> Rollout Plan

## Pre-flight checklist (must all be ✓)
```bash
# Each check with its exact command and pass criteria
```

## Phase A — <description> (zero data risk)
**Goal:** <what changes>
**Effect:** <what users see / don't see>
**Verification:** <how to confirm>
**Stop conditions:** <metric / error pattern that triggers rollback>
**Rollback:** <exact command, time to execute>

## Phase B — ...

## Phase F — irreversible cleanup (LAST)
Only after weeks of clean operation in earlier phases.
```

### 6.4 Operator scripts directory (conditional)

**Required when the feature has any of:**
- Per-entity rollout state (per-user feature flags, gradual ramp)
- Data migration (forward or reverse)
- Irreversible operation that needs a documented recovery path
- An on-call runbook beyond "redeploy main"

**NOT required when** the feature is:
- A new API endpoint with no persistent schema impact
- A UI screen / notification type / ranking tweak
- A feature-flagged behavior change with no migration

For those, the lifecycle health check can be as simple as: "run existing
integration tests, confirm exit 0." The `scripts/<feature>/` directory
is optional.

**When required**, put scripts in `scripts/<feature>/` and write a
`README.md` that documents the workflows:

```markdown
# <Feature> operator toolkit

All scripts default to **dry-run**. They need `--confirm` (or
`--execute`) to mutate.

## Read-only inventories
| Script | Purpose |
|---|---|
| ... | ... |

## Per-user / per-entity operations
### <Workflow name>
```bash
# 1. <step>
<exact command>
# 2. <step>
<exact command>
```

### <Reverse workflow name>
...

## Common workflows
**"How do I X?"**
```bash
<command>
```
```

The discipline here: **a workflow that isn't documented in the README
doesn't exist**. If you wrote a script and didn't add it to the README,
the next operator (including future you) won't find it.

---

## Stage 7 — STATUS.md (the executive dashboard)

**Goal:** A single document a reviewer can open to understand the
feature's state without reading anything else.

**Append to project learnings.** After STATUS.md is written, append a
short dated section to `<project-root>/learnings.md` (create the file
if it doesn't exist; format below). Atomic write (`*.tmp` → `mv`) so a
concurrent read never sees a partial file. Capture only what was
*surprising or non-obvious* about this feature — patterns that worked,
anti-patterns avoided, second-order effects. Skip routine "added X
endpoint" stuff. Stage 1 of the NEXT feature reads this file.

```markdown
## <feature-name> — <YYYY-MM-DD>

- Surprise: <one-line>; lesson: <one-line>
- Pattern that worked: <one-line>
- Pitfall avoided: <one-line>
```

`specs/<feature>/STATUS.md`:

```markdown
# <Feature> — Status

**TL;DR:** <2-3 sentences on what's done and what's next>

## Phase status
| Phase | What | Tests added | Commit | Status |
|---|---|---|---|---|
| 0 | <topic> | n/a | <SHA> | ✅ |
| 1 | <topic> | +75 | <SHA> | ✅ |
| ... | ... | ... | ... | ✅ |

**Total new tests: N. Passing tests: M. Regressions: 0.**

## Test counts across phases
```
Pre-feature baseline:    M passing
After Phase 1:           M+a passing (+a)
...
```

## Architecture (ASCII diagram)
<reproduce the master plan diagram>

## <Surface 1> instrumented
| File | Function | Status |
|---|---|---|
| ... | ... | ✅ |

## Operator runbook
<concise pointers to ROLLOUT_PLAN.md and scripts/<feature>/README.md>

## What's NOT done (post-launch follow-ups)
- ID: <description> — deferred because <reason>

## Honest assessment for an external reviewer
**Strengths:**
- ...

**Weaknesses (a hostile reviewer would attack):**
- ...

Net: <ready / not ready> for <stage>.
```

This is the document linked from PR descriptions, status updates, and
handoff notes. Keep it current — when STATUS.md goes stale, the audit
trail breaks.

---

## Required artifact structure

For a feature `<f>`, the final state of `specs/<f>/`:

```
specs/<f>/
├── spec_audit.md                Stage 1 — flaws in the original spec
├── README.md                    Stage 2 — master plan
├── STATUS.md                    Stage 7 — executive dashboard
├── ROLLOUT_PLAN.md              Stage 6 — operator runbook (if gradual)
├── E2E_VERIFICATION.md          Stage 6 — live evidence
├── phase-0-<topic>.md           Stage 4 — phase spec
├── phase-0-verify.md            Stage 4 — verification plan
├── phase-0-evidence.md          Stage 4 — observed evidence
├── phase-0-summary.md           Stage 4 — retrospective + honest weaknesses
├── phase-1-<topic>.md
├── phase-1-verify.md
├── phase-1-evidence.md
├── phase-1-summary.md
├── ... (one quartet per phase, plus sub-phases when needed)
└── agent_verification/
    ├── architect_review.md      Stages 3 + 5 (review + re-review)
    ├── code_review.md
    ├── tester_review.md
    ├── ux_review.md             (if UI)
    ├── independent_review.md
    └── SUMMARY.md               Consolidated verdicts + verdict upgrades

scripts/<f>/                     Stage 6 — operator tooling
├── README.md                    Workflows (enforce, revert, audit, ...)
├── run_<f>_lifecycle.sh         Single canonical health-check
├── inventory_<thing>.py         Read-only auditing
├── set_<thing>_<state>.py       Per-entity state flips
├── migrate_<thing>.py           Bulk operations (dry-run by default)
└── restore_<thing>.py           Reverse migration (when applicable)
```

---

## Worked example: encryption rollout

Use `specs/encryption/` as the canonical reference. It has every
artifact in this skill, and it shipped successfully through dev →
staging → prod with arpit1712 in enforce mode. Specific files to study:

**Caveat:** the encryption work predates this skill's artifact naming.
In that project the spec audit was embedded inside README.md (lines
9-100, the F1-F16 section), and there is no standalone `spec_audit.md`
under `specs/encryption/`. Going forward, this skill requires
`spec_audit.md` as a separate file — the embedded form was a
historical convenience that loses the "audit before plan" gate.
Everything else in the encryption directory matches the template.

| Skill stage | Encryption artifact |
|---|---|
| Spec audit | `specs/encryption/README.md` lines 9-100 (F1-F16) — embedded, not separate |
| Master plan | `specs/encryption/README.md` (full) |
| Multi-agent review | `specs/encryption/agent_verification/SUMMARY.md` |
| Phase 4 quartet | `phase-1-{crypto-core,verify,evidence,summary}.md` |
| Sub-phase pattern | `phase-5d-{missed-writes,missed-reads,flake-triage,...}.md` |
| Re-run review | `agent_verification/SUMMARY.md` "Re-run after fix" |
| Live verification | `E2E_VERIFICATION.md` |
| Rollout plan | `ROLLOUT_PLAN.md` |
| Operator tooling | `scripts/encryption/README.md` |
| STATUS.md | `specs/encryption/STATUS.md` |

The story arc:
1. User's original spec was good but had 16 gaps (F1-F16 in audit)
2. Master plan answered the gaps; user approved
3. 4 agents reviewed plan + early code; found 4 categories of real bugs
4. Main agent fixed everything; re-running agents upgraded verdicts
5. Live e2e against real KMS; lifecycle script committed
6. Per-user rollout: shadow → enforce on test user → staging → prod
7. Operator scripts let any future operator flip a user in either
   direction with one command

When you're tempted to skip a stage on YOUR feature, re-read this and
ask: which stage of the encryption story would you have skipped, and
which bug would have shipped to prod as a result?

---

## TDD — non-negotiable

Repeats from `.claude/rules/tdd.md` because it's that important:

1. Write tests FIRST
2. **Run tests — verify RED** (skipping this is the #1 reason features ship broken)
3. Implement minimum code
4. Run tests — verify GREEN, including ALL existing tests
5. Refactor

A test that passes before implementation is worthless.

---

## Anti-patterns (all observed in real failure modes)

1. **"Skip the audit, I know what to do"** — produces plans that miss
   half the surface. The encryption F1-F16 were not obvious without the
   audit step.
2. **One giant commit** — bisecting + reviewing 50-file commits wastes
   human time. Phases exist for a reason.
3. **Verifying by reading the code** — reading is not verifying. Run it,
   capture output, show evidence.
4. **Mocked-only verification** — mocks lie. Always include live e2e.
5. **Generic agent prompts** — a 3-line prompt produces a 3-line review.
   Brief agents thoroughly with the master plan path, the spec audit
   path, and the specific risks you want them to attack.
6. **Skipping the re-review** — fixing CRITICAL findings without
   re-confirming with the same agents leaves you trusting yourself to
   grade your own homework.
7. **Silent reworking of phase docs** — when a sub-phase is needed,
   make a new doc (`phase-5d-...`). Editing the original destroys
   the audit trail.
8. **Removing safety nets first** — plaintext stripping, key destruction,
   schema drops are LAST phases, after weeks of clean operation.
9. **Writing scripts/<feature>/X.py without README.md** — undiscoverable
   tools = no tools.
10. **Letting STATUS.md go stale** — the executive dashboard is only
    useful if it's true.

---

## Quick checklist before declaring "done"

**Full intensity** (skip items marked OPTIONAL when not applicable):

Stage gates:

- [ ] `specs/<f>/spec_audit.md` exists; coverage of (security, concurrency, failure modes, cost, rollback) is explicit
- [ ] `SPEC_AUDIT_COMPLETE` sentinel was sent; user replied with go-ahead
- [ ] `MASTER_PLAN_COMPLETE` sentinel was sent; user replied with approval
- [ ] `agent_verification/{architect,code,tester,...}_review.md` all present
- [ ] `agent_verification/SUMMARY.md` lists categories, fixes, deferred items
- [ ] All CRITICAL + HIGH findings addressed (or deferred with user approval)
- [ ] If any reviewer was NEEDS_REVISION/DO_NOT_SHIP at first pass: agents re-ran after fixes; verdicts upgraded; documented in SUMMARY.md
- [ ] If all reviewers approved at first pass: explicit "Stage 5 skipped" note in SUMMARY.md

Per phase:

- [ ] `phase-N-<topic>.md` (spec written first)
- [ ] `phase-N-verify.md` committed BEFORE the test run (separate commit)
- [ ] Tests written first, verified RED then GREEN
- [ ] All existing tests still pass (zero regressions)
- [ ] Build/compile clean
- [ ] `phase-N-evidence.md` with reproducible commands + observed output, committed AFTER the run
- [ ] `phase-N-summary.md` with honest weaknesses
- [ ] Phase committed + pushed (one commit per phase, plus the verify-before-evidence split)

Live + operator:

- [ ] Live e2e tests pass against deployed environment
- [ ] `specs/<f>/E2E_VERIFICATION.md` has real evidence
- [ ] **OPTIONAL** (only when feature has rollout state / migration / irreversible op): `specs/<f>/ROLLOUT_PLAN.md`
- [ ] **OPTIONAL** (same condition): `scripts/<f>/README.md` documents every operator workflow
- [ ] **OPTIONAL** (same condition): `scripts/<f>/run_<f>_lifecycle.sh` exists, exits 0. For non-data features, lifecycle = existing integration tests pass.
- [ ] `specs/<f>/STATUS.md` cross-references everything for an external reviewer

Final:

- [ ] All commits on main (or feature branch if explicitly instructed); no long-lived branches
- [ ] No CRITICAL/HIGH findings open without an explicit deferral

**Light intensity:**

- [ ] Brief plan stated in conversation
- [ ] Tests written first, RED → GREEN
- [ ] All existing tests pass
- [ ] Build/compile clean
- [ ] One `phase-evidence.md` (or commit body) showing it works
- [ ] No `spec_audit.md`, no `README.md` master plan, no `agent_verification/`

**Minimal intensity:**

- [ ] TDD: tests first, RED → GREEN
- [ ] Build clean
- [ ] Stop hooks (code-reviewer, tester) caught no issues

If a Full-intensity checkbox is unchecked, the feature is **not done**.

---

## Lessons from real incidents — deviations to prevent

The patterns below are drawn from actual deviations observed in production
incidents. They are MORE binding than the general guidance above because
real bugs shipped from each one. Treat each as an explicit hardstop.

### LL-1. Multi-agent review applies to EVERY commit in an incident, not just the first

**What happened:** The fix commit for an incident got architect review.
Subsequent commits (rescue script, integration test, operator tooling)
did not. A code-reviewer audit run AFTER push found a CRITICAL bug
(`FeatureFlags()` no-arg call → TypeError on every full run) that would
have been caught pre-push.

**Rule:** During an incident, every commit that adds NEW code (not just
tweaks to the in-flight fix) requires its own pre-commit review pass.
This includes:
- Rescue / cleanup scripts
- Integration tests being added
- Operator tooling
- Infrastructure changes adjacent to the fix

The "I already got review on the fix" reasoning does NOT extend to follow-up
commits. Each commit is its own review surface.

### LL-2. Round-3 reviews against the original spec catch what bug-fixes miss

**What happened:** An incident fix landed (5 paths). An audit found 5
more (Incident 2). Both rounds were reviewed for bug correctness.
Nobody re-reviewed against the ORIGINAL encryption spec. A round-3
spec-drift review then surfaced 4 MORE bugs including a security
violation (plaintext leak in `recurring_series.base_message`) and a
silent zero-results bug (keyword search fallback not decrypted).

**Rule:** After ANY incident touching a previously-audited subsystem,
schedule an explicit round-3 review against the original spec / threat
model. The reviewer's job is to find DRIFT between current behavior
and what the spec promised — not to re-check the bug fix.

This is now Stage 5b in the discipline:
- Stage 3: Multi-agent review (pre-coding)
- Stage 5: Re-review (post-fix, verdict upgrade)
- **Stage 5b: Spec-drift review** (after any major incident, against the
  original spec doc) — orthogonal to per-fix reviews

### LL-3. "Flake" is a SPECIFIC diagnosis, not a default explanation

**What happened:** Integration tests failed during a major rollout. They
were dismissed as "pre-existing LLM-flakes per phase-5d-llm-flakes-deep-dive.md."
Several actually matched bug patterns from the rollout
(`test_edit_single_instance_text` "Expected 3+ instances, got 0" was
DIRECT evidence of an append-data-loss bug). Real signal lost in the
"flake" classification.

**Rule:** During / after a major rollout, every integration test failure
gets investigated INDIVIDUALLY before being classified. The classifier
must:
1. Read the prior flake doc (if cited)
2. Compare the SPECIFIC symptom (assertion error, log line, status code)
   against the documented flake pattern
3. If symptoms diverge OR the test was passing before the rollout, it's
   a NEW failure mode — investigate

"Flake" requires evidence: intermittency (passes on retry), no
correlation with recent code changes, documented prior occurrence
matching the same symptom.

### LL-4. Background subsystems must be in scope for every encryption-touching change

**What happened:** Phase 5d encryption work tested the strip behavior
in isolation. Background subsystems that consumed sensitive fields
post-strip (embedding generation, PostHog analytics, recurring_series
metadata, append-modify) were silently broken. Each was a separate
"oh that path too" moment over multiple audits.

**Rule:** For ANY change to a sensitive-data hook (encryption, masking,
redaction, etc.), the spec audit MUST enumerate:
- Every WRITE caller of the affected dict (synchronous and background)
- Every READ caller of the affected dict
- Every external consumer (analytics, logs, downstream services,
  serialization to webhooks/queues)
- Every adjacent collection that stores derived data (embeddings,
  trails, audit logs, search indexes, summaries)

The spec_audit.md checklist (Stage 1 coverage requirement) gains a new
entry: **(f) Downstream consumers / background subsystems**. If any
have zero findings, state explicitly why.

### LL-5. Tests must pin ORDERING invariants, not just correctness

**What happened:** A fix had the form "capture local BEFORE strip mutates
dict." A correctness test verified the captured value was right. The
ORDERING (capture-before-strip) was not pinned. A future revert that
moves the capture line below the strip would silently re-introduce the
bug AND pass the existing test.

**Rule:** When a fix shape is "X must happen before Y," add a source-grep
ordering test that asserts X appears in source code BEFORE Y in the
same function. Use `inspect.getsource()` + `.find()` positions or
similar AST-light approach.

Apply this pattern wherever the bug class is "ordering of operations
matters" — in particular: capture-before-strip, decrypt-before-read,
flag-before-mutate, write-before-publish.

### LL-6. Tests must exercise main() entry-point wiring, not just helpers

**What happened:** A rescue script's helper functions had 17 unit tests.
All passed. The script's `main()` was never exercised. A trivial wiring
bug (`FeatureFlags()` instead of `FeatureFlags(db=...)`) would have
crashed every full run with `TypeError`. Caught only by code-reviewer
running source-grep AFTER the script was on main.

**Rule:** Every script with a `main()` function gets at least one test
that proves the entry point can construct its dependencies correctly.
Either:
- A unit test that imports `main` and inspects the source for known
  required wiring (e.g. "must pass `db=` to FeatureFlags")
- A unit test that calls `main()` with a fully-mocked external surface
  and asserts the expected sequence of dependency constructors fires
- A smoke command (`--help` or `--inventory-only`) that validates
  bootstrap without doing real work

Helper-only test coverage is necessary but not sufficient.

### LL-7. Operator commands MUST run in background with redirected output

**What happened:** Long-running pytest suites and migration scripts were
run in foreground. The user had to manually background them twice. A
`tail -25` pipe ate all output from a 10-min dry-run, wasting the run.

**Rule:** Default for ANY command expected to take >60s:
- `Bash(run_in_background=true)` with `> .tmp/<name>.log 2>&1` redirection
- Use `Monitor` tool to stream progress events
- Never pipe through `tail -N` / `head -N` — that buffers and may eat
  output if the producer is killed mid-run

(Already encoded as a memory; cited here so the skill carries the
guidance even when memories are cleared.)

### LL-8. Don't claim "done" until the next round of audit confirms

**What happened:** "All 5 reminder paths fixed and deployed" was claimed.
A subsequent audit found 5 MORE related bugs (Incident 2). Then "all
audit fixes deployed" was claimed. A round-3 spec-drift review found
4 MORE bugs (Round 3). At each step the prior claim was overconfident.

**Rule:** "Done" is a STAGED claim. The progression is:
1. **"Code change complete"** — implementation + tests landed.
2. **"Deployed"** — change is live in the target environment.
3. **"Verified by independent audit"** — a fresh agent that did NOT
   write the fix has confirmed it covers the documented scope.
4. **"Closed"** — operating quietly for the agreed soak period.

You may claim (1), (2), (3), or (4) — but always with the qualifier.
"Done" without a qualifier is a process violation. Especially during
incidents, prefer "deployed and pending round-N review" over "done."

### LL-9. Don't over-state impact when communicating

**What happened:** A bug in keyword-FALLBACK search was described as
"every user keyword search → I couldn't find any relevant memories."
True scope: only the fallback path (rare query types), not the primary
semantic search. The over-statement caused unnecessary alarm and
prioritization confusion.

**Rule:** When describing a bug's user-visible impact:
- Specify which code path it affects (primary vs fallback, sync vs
  background, write vs read)
- Specify which users / which actions / under what conditions
- If unsure, say "I don't yet know the user-visible scope" — better
  than overclaiming

The discipline applies to both incident triage and post-mortem write-ups.

### LL-10. Auto Mode does NOT override the skill's discipline gates

**What happened:** Auto Mode's "execute immediately" framing was used
to rationalize skipping spec_audit.md, master plan, multi-agent review,
and sentinel-then-wait gates on follow-up commits during an incident.
The user pushed back twice ("WTF why are you not following the skill").

**Rule:** Auto Mode permits autonomous *execution* of the skill's
recipe. It does NOT permit skipping stages OF the recipe. The skill's
mandatory gates (sentinels, multi-agent review, TDD red-then-green) fire
regardless of Auto Mode state.

In incident response specifically, the gates compress (Light intensity)
but do NOT disappear:
- Spec audit becomes a 1-paragraph in-conversation summary
- Multi-agent review still fires (architect at minimum)
- TDD discipline holds (RED before GREEN)
- Re-review fires before deploy

If you find yourself skipping a gate "because incident urgency," that's
exactly when the gate is most important.

### LL-11. Test environment requires explicit env-var + state setup

**What happened:** Multiple test runs failed because of environment
mismatches: `KMS_NUM_BUCKETS` mismatch (default 1000 vs prod 100),
`GEMINI_API_KEY` not fetched from secret manager. The failures looked
like real bugs, wasted investigation time, masked actual issues.

**Rule:** Before running ANY integration test, verify:
- All required env vars are set (KMS_NUM_BUCKETS, GEMINI_API_KEY,
  GCP_PROJECT_ID, KMS_PROJECT, etc.)
- Test user state matches expectations (encryption_mode, tier, opt-in flags)
- Target environment is the intended one (--api-url=...)
- Output goes to `.tmp/<name>.log` (per LL-7)

If a test fails with a Python `KeyError` / `TypeError` / "0/N" / "None
returned," the FIRST hypothesis is environment misconfiguration, not
production bug.

### LL-12. The discipline applies to operator tooling as much as to product code

**What happened:** Operator scripts (rescue, migrate, delete) were
written rapidly during an incident with light review. A rescue script
had a CRITICAL crash bug (`FeatureFlags()` no-arg). A migrate script's
default `KMS_NUM_BUCKETS=1000` quietly corrupted detection logic.

**Rule:** A script that touches prod data — even read-only — is a
production-impact change. Apply the full skill discipline:
- spec_audit.md identifying the data surface and failure modes
- Multi-agent review BEFORE code is run on prod
- TDD with main()-entry tests
- Dry-run + `--confirm` defensive defaults
- Architect re-review of the script BEFORE any `--confirm` invocation

The "it's just operator tooling" reasoning gets you a CRITICAL bug
1-2 days into the incident.

---

## Anti-patterns this skill is now hardened against

If you find yourself doing one of these, stop. The skill says no.

- **"Auto Mode lets me skip review"** → No. LL-10.
- **"It's just a follow-up commit, the fix was reviewed"** → No. LL-1.
- **"That test always flakes during a rollout"** → No, until you've
  symptom-matched. LL-3.
- **"Background subsystems are out of scope"** → No. LL-4.
- **"The fix is correct, ordering doesn't matter"** → It might. Pin it. LL-5.
- **"Helper unit tests are enough"** → No, exercise main(). LL-6.
- **"I'll background the long command later"** → No. Default background. LL-7.
- **"Done"** → Replace with "deployed and pending round-N review." LL-8.
- **"This affects every user every time"** → Be precise about scope. LL-9.
- **"Operator scripts don't need the full skill"** → They do. LL-12.
Don't say it's done. Don't merge. Don't deploy.
