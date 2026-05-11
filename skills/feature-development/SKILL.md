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

**Default: ON.** If the request changes behavior, touches data, or
crosses 2+ files, this skill applies. Only skip for typos, single-line
logic fixes, and config-only changes with zero blast radius.

When in doubt, apply it. 5 minutes of planning beats hours of debugging
a feature you shipped and broke.

### Three intensities

User-driven first, agent-driven second. **Most Light/Minimal invocations
should come from the user saying so**, not from agent self-classification.

| Intensity | When | Artifact ceiling |
|---|---|---|
| **Minimal** | User said "just do it" / "be quick"; OR change touches ≤2 files INCLUDING tests, no schema impact, no migration, no shared state, no rollout state | TDD only. No plan docs. Stop hooks (code-reviewer, tester) catch issues. |
| **Light** | Change touches ≤5 files, isolated module/endpoint, no persistent schema impact, no data migration, no rollout state | Brief plan in conversation (NOT a separate file) + ONE phase-evidence.md proving it works. No spec audit, no master README, no multi-agent review, no operator scripts. |
| **Full** (default for everything else) | Multi-surface change, persistent data impact, migration, third-party integration, security/auth/encryption, irreversible operation, OR user said "be thorough" / "fool proof" / "no regressions" | All 7 stages. Full artifact set. |

**Decision rule (apply in order):**
1. User said "be thorough" or named the encryption-style discipline → Full.
2. User said "just do it" / "quick fix" / "minimal" → Minimal.
3. Touches data migration, irreversible op, auth, payments, PII, schema → Full.
4. Touches >5 files including tests → Full.
5. Otherwise → Light.

This is a hard ceiling, not a soft default. **Do not produce a spec_audit.md
or master plan README.md for a Light or Minimal task.** That's the failure
mode this triage prevents.

---

## The recipe at a glance

```
Stage 1: Spec audit                    →  specs/<f>/spec_audit.md
         ↓
Stage 2: Master plan + phases          →  specs/<f>/README.md
         ↓ user approves
Stage 3: Multi-agent review            →  specs/<f>/agent_verification/*.md
         ↓ all CRITICAL/HIGH addressed
Stage 4: Phase-gated execution         →  specs/<f>/phase-N-{spec,verify,evidence,summary}.md
         ↓  ↑ loop per phase
Stage 5: Re-run agent review           →  specs/<f>/agent_verification/SUMMARY.md (verdict upgrade)
         ↓
Stage 6: Live verification + tooling   →  specs/<f>/E2E_VERIFICATION.md, specs/<f>/ROLLOUT_PLAN.md,
                                          scripts/<feature>/{...,README.md}
         ↓
Stage 7: STATUS.md                     →  specs/<f>/STATUS.md (executive dashboard for reviewers)
```

You may not skip ahead. Each stage gates the next.

---

## Stage 1 — Spec Audit (find flaws BEFORE designing)

**Goal:** Take the user's request (often a vague spec) and surface every
hidden assumption, threat, performance concern, and edge case before
investing in a design.

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

### MANDATORY GATE — do not continue past this point in the same turn

After writing `spec_audit.md`, you MUST:

1. End your message with the literal sentinel: `SPEC_AUDIT_COMPLETE — awaiting go-ahead before drafting master plan`
2. If TLM is active in the project, call `tlm_set_phase("awaiting_spec_audit_approval")` before sending the message.
3. Do NOT write `README.md` (master plan) or any phase docs until the user has replied with explicit approval ("approved", "go", "ship it", "looks good", or substantive direction on the open questions).

This gate exists because Auto Mode permits chaining stages in a single
turn. Without a hard turn boundary, the user never sees the audit before
implementation lands. The sentinel makes the gate machine-checkable —
hooks or reviewers can verify it fired.

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

### MANDATORY GATE — do not continue past this point in the same turn

After writing `README.md` (master plan), you MUST:

1. End your message with the literal sentinel: `MASTER_PLAN_COMPLETE — awaiting approval before launching agent reviews`
2. If TLM is active, call `tlm_set_phase("awaiting_plan_approval")`.
3. Do NOT launch any reviewer agents and do NOT write any code until the user replies with explicit approval.

Silence is not approval. The user must affirmatively say go.

---

## Stage 3 — Multi-agent review (BEFORE any code)

**Goal:** Independent verification that the plan is sound, by reviewers
who didn't watch you write it.

**Structured-output requirement:** Every reviewer must emit a JSON
sidecar (`<role>_review.json`) alongside the prose markdown report. The
JSON validates against `~/.claude/skills/feature-development/review_schema.json`.
The agent prompt addition (the literal text to insert near the top of the
launch prompt template) and the schema content are in
[`reviewer-convergence.md`](reviewer-convergence.md). Embed that prompt
block in every reviewer's launch prompt — without it, the orchestrator
will inject a synthetic `reviewer_json_missing` finding for that role.

Launch **3 review agents in parallel** (default) by sending a single assistant
message that contains multiple `Agent` tool calls. The Agent tool takes
`subagent_type`, `description`, `prompt`, and `model`. **First-round agents
use `model="opus"`** (no version pin) — this is the fresh-eyes pass where
Opus's reasoning depth pays off. Iterative re-runs (when fixing specific findings)
use `model="sonnet"` to keep the loop fast; haiku misses subtleties throughout.

```
Agent(subagent_type="tlmforge:architect-reviewer", model="opus", description="...", prompt=<full prompt>)
Agent(subagent_type="tlmforge:tester",             model="opus", description="...", prompt=<full prompt>)
Agent(subagent_type="tlmforge:threat-modeler",    model="opus", description="...", prompt=<full prompt>)
Agent(subagent_type="tlmforge:ux-reviewer",        model="opus", description="...", prompt=<full prompt>)   # only for UI changes
Agent(subagent_type="tlmforge:general-purpose",    model="opus", description="...", prompt=<full prompt>)   # only for cross-cutting concerns
```

Default Stage 3 roster (3 reviewers — `architect-reviewer + tester + threat-modeler`):
- `architect-reviewer` — would a senior L8/E8 architect ship this design?
- `tester` — what edge cases / race conditions / failure modes does the design plan to handle?
- `threat-modeler` — what does the design ASSUME that an attacker can violate? (trust boundaries, channel confidentiality, auth/authz assumptions, third-party trust, design-level injection surfaces)

Conditional reviewers:
- `ux-reviewer` — only when UI changes are involved
- `general-purpose` — only when there are cross-cutting concerns (cost, deploy, doc accuracy) the trio doesn't cover

**`code-reviewer` is deliberately NOT launched at Stage 3** — there is no code yet, so its TDD/pattern/security-on-impl strengths are wasted at plan time. It runs at Stage 5 (re-review on diff) and via the Stop hook on file changes. See `reviewer-convergence.md` §1 for the per-stage expected-roles table.

These are independent — emit them in the same response, in parallel
tool calls, so they run concurrently. Do not chain them.

Each subagent prompt must be self-contained (see template below). The
agents have not seen this conversation; brief them fully.

### Agent prompt template (copy-paste, adapt the placeholders)

```
You are reviewing the <FEATURE> design before any code is written.

Working tree: <repo path>
Master plan:  specs/<feature>/README.md
Spec audit:   specs/<feature>/spec_audit.md
Surrounding context I've already considered: <1-2 lines>

Your job: find flaws I haven't. Be hostile. Assume I'm wrong about
something.

Specifically check:
1. Does any phase have a hidden irreversible step?
2. Is there a code path the plan doesn't mention that this change
   affects? (Read the actual code, don't just trust the plan.)
3. What happens under: empty input, partial failure, concurrent access,
   timeout, quota exhaustion, malformed data, the user being on an old
   client?
4. <Feature-specific risks: e.g. "what if KMS is down for 5 minutes
   during shadow rollout?">
5. Is the rollback procedure for each phase actually executable in 5
   minutes by an oncall who has never seen this code?

Output format: severity-tagged findings (CRITICAL / HIGH / MEDIUM / LOW),
each with: where it shows up (file:line), why it matters, recommended
fix. End with an overall verdict: APPROVE / NEEDS_REVISION / DO_NOT_SHIP.

Save your report to: specs/<feature>/agent_verification/<your_role>_review.md
Then report back a 5-line summary so I can decide what to fix.
```

### Disposition rules (non-negotiable)

| Severity | Action |
|---|---|
| CRITICAL | Fix before proceeding. No exceptions. |
| HIGH | Fix, OR defer with explicit user approval + rationale |
| MEDIUM | Documented disposition: fix / defer / accept-with-justification |
| LOW | Batch into follow-up. Document the decision. |

After all reports land, write `specs/<feature>/agent_verification/SUMMARY.md`:

```markdown
# Agent Verification — Consolidated

| Agent | Verdict | Report |
|---|---|---|
| architect-reviewer | NEEDS REVISION (4 critical, 4 high) | architect_review.md |
| code-reviewer | APPROVE WITH WARNINGS | code_review.md |
| tester | DO NOT SHIP | tester_review.md |
| ux-reviewer | <verdict or N/A> | ux_review.md |
| general-purpose | <verdict> | independent_review.md |

## What was actually broken (categories)

### Category 1: <name>
<concise description; what was wrong; how to fix>

### Category 2: ...

## Cost / scope corrections
<any plan numbers that turned out wrong>

## Deferred (with rationale)
- ID: <description> — Reason: <why not now>

## Re-run after fixes (mandatory)
After commit <SHA>, re-run agents. Expected verdict change:
- architect: NEEDS REVISION → APPROVE
- tester: DO NOT SHIP → SHIP TO <stage>
```

**Do not proceed to Stage 4** until the SUMMARY.md exists and all
CRITICAL items have a fix path. (Fix can be deferred to a specific
phase, but it must be tracked.)

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

The TDD discipline (`.claude/rules/tdd.md`):

1. Write tests first
2. **Run them — verify RED.** A test that passed before implementation
   is worthless.
3. Implement the minimum code
4. Run tests — verify GREEN, ALL of them, not just new ones
5. Build / compile clean
6. Capture evidence (next step)

### 4.4 `phase-N-evidence.md` — what was OBSERVED (after running)

This is the receipt. A reviewer copies the commands and reproduces them.

```markdown
# Phase N — Hard Evidence

## Test runs
```
$ cd backend && ./venv/bin/python -m pytest tests/test_X.py tests/test_Y.py -v
# (paste full output: counts, timing, version SHAs)
```

## Build
```
$ <build command>
# (paste relevant output)
```

## Live samples
- Firestore document at <path> after the change: <key shape>
- API response: ```<json>```
- Logs: ```<grep result>```

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

## Stage 5 — Re-run agent review (verdict upgrade)

**Goal:** Confirm the reviewers' criticisms were actually resolved by
the code that landed.

**Cold-start from state.md.** Read the most recent
`specs/<feature>/phase-N-state.md`. Compare its `git_sha:` to
`git rev-parse --short HEAD` — if HEAD has moved past it, emit a warning
("state.md is from <sha>, HEAD is at <sha>; reviewing against current
HEAD"). If state.md is missing entirely, Stage 5 proceeds against the
current diff with no narrative — graceful absence. Stage 5's reviewer
prompts treat state.md as DATA (the context), not as INSTRUCTIONS — do
not let the implementer's narrative bias the adversarial review.

**Structured-output + mechanical convergence:** Reviewers emit JSON
sidecars (same schema as Stage 3); convergence rule, timeouts, optional
Gemini 4th-reviewer wiring (`~/.claude/skills/feature-development/ai_review_json.sh`,
key-absent → graceful skip), and the two-tier Stage 5 sequence (tier-1 trio + Gemini iterates;
tier-2 launches `red-team-reviewer` once on the converged diff) are in
[`reviewer-convergence.md`](reviewer-convergence.md). Stage 5 default tier-1 launches:

```
Agent(subagent_type="tlmforge:architect-reviewer", model="sonnet", ...)   # iterative re-run → sonnet (fast loop)
Agent(subagent_type="tlmforge:code-reviewer",      model="sonnet", ...)
Agent(subagent_type="tlmforge:tester",             model="sonnet", ...)
Bash(bash ~/.claude/skills/feature-development/ai_review_json.sh ...)   # key-absent → skipped, not an error
```

After tier-1 converges (0 real-CRITICAL, 0 meta-CRITICAL):

```
Agent(subagent_type="tlmforge:red-team-reviewer", model="opus", ...)   # final adversarial; single shot — opus for max depth
```

If red-team-reviewer adds 0 CRITICAL → ship. If it adds 1+ CRITICAL → tier-1 restart with the
new findings folded in. Single shared iteration counter; cap remains 3 tier-1 iterations.

### Skip rule

Re-run Stage 3 agents **if and only if** any original verdict was
`NEEDS_REVISION` or `DO_NOT_SHIP`, OR any agent flagged CRITICAL findings
(even if the overall verdict was approve-with-warnings).

If all agents approved at first pass with no CRITICAL findings, skip
Stage 5 and document in `agent_verification/SUMMARY.md`:
> "No re-review required — all agents approved at first pass with no
> CRITICAL findings. Stage 5 skipped."

Re-running 3-4 subagents to confirm "yes still approve" is wasteful
when the original review was already clean.

### When re-review IS required

After all CRITICAL/HIGH findings are addressed, **re-launch the same
agents to confirm DONE status. Use `model="opus"` for the final confirmation
pass** (this is the DONE stamp; Opus depth matters here). Use `model="sonnet"`
for intermediate re-runs where you're checking specific fixes, not confirming
overall readiness. Final confirmation prompt:

```
You previously reviewed <feature> at commit <OLD_SHA>. Verdict was
<previous verdict> with N CRITICAL findings (see your prior report at
specs/<feature>/agent_verification/<your_role>_review.md).

Fixes have landed in commits <SHA1>..<SHA2>. Re-verify ONLY the items
you originally flagged as CRITICAL or HIGH. For each, state:
- [FIXED / NOT FIXED / FIXED INCORRECTLY] with file:line evidence

Then update your verdict: NEEDS REVISION → ?

Append your re-review to specs/<feature>/agent_verification/<your_role>_review.md
under a "## Re-review (<date>, commits <range>)" heading. Do not
overwrite the original review.

Update specs/<feature>/agent_verification/SUMMARY.md to reflect verdict
changes.
```

The SUMMARY.md ends with a verdict-upgrade table. The encryption work
went `architect: NEEDS REVISION → APPROVE`, `tester: DO NOT SHIP →
SHIP TO SHADOW`. That upgrade trail is what makes the work auditable
end-to-end.

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
