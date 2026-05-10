---
reviewer: architect-reviewer
reviewed: 2026-04-30
subject: ~/.claude/skills/feature-development/SKILL.md
basis: encryption work at plans/encryption/, scripts/encryption/, agent_verification/
---

# REVIEW: feature-development SKILL.md

## VERDICT: NEEDS REVISION

Strong bones. The seven-stage arc is sound and directly mirrors what actually
happened in the encryption rollout. Most content is concrete and defensible.
But there are three failure modes that will cause real agents to do the wrong
thing, and one technical claim that will break.

---

## CRITICAL

### C1. Stage 3 agent-launch mechanism is not specified — agents won't fire

**Severity: CRITICAL**

The skill says "Launch 3-4 review agents in parallel in a single message" with
a `Agent("architect-reviewer")` pseudo-syntax. This is not a real Claude Code
API. There is no `Agent()` constructor, no `.run()` method, and no mechanism
described for how the agent gets the review role, the working directory, or the
file paths.

The actual mechanism in this repo — based on the auto-review hooks in CLAUDE.md
— is that background agents are launched as subagents (via the hooks system or
explicitly by the implementing agent). The skill invents a calling convention
that doesn't exist.

A future agent reading this will either:
1. Try to call `Agent(...)` as if it were a function → error
2. Interpret it as pseudo-code and write its own agent invocation — producing
   something inconsistent with how this codebase actually runs agents
3. Skip Stage 3 entirely because the mechanism is unclear

**Fix:** Replace the fake `Agent(...)` syntax with the actual invocation pattern
used in this codebase. Based on CLAUDE.md, agents are launched as subagents.
Specify concretely: "Use the Task tool to launch each reviewer as a subagent.
Pass the full agent prompt below as the task description. Do not summarize it."
Or, if the intent is to use the hooks system, say so explicitly and explain when
hooks fire vs. when the implementing agent must explicitly trigger them.

---

### C2. "Stop here" gates are advisory, not enforced — agents will barrel through

**Severity: CRITICAL**

The skill has two explicit stop gates:

- Stage 1: "Stop here. Surface the audit to the user. Don't draft the plan
  until they've answered the open questions."
- Stage 2: "Stop here. Get explicit user approval on the master plan before any
  code. 'Approved' / 'go' / 'ship it' — not silence."

These are prose sentences. An agent operating in auto mode (as this one is, per
CLAUDE.md "Auto Mode Active") has explicit permission to "execute immediately"
and "minimize interruptions." That instruction directly overrides the skill's
"stop here" prose. In auto mode, an agent will write the spec_audit.md, then
immediately write README.md, then immediately start Stage 3 — all in one
response — because CLAUDE.md's auto mode instruction outranks the skill's
prose.

The encryption story worked because the user was actively engaged in the
conversation and pushed back. The skill cannot rely on that.

**Fix:** The gates must create an actual interruption that auto mode cannot
override. Options:

1. **Explicit user-confirmation line in a machine-readable format** so hooks or
   TLM can enforce it. E.g., after Stage 1, the implementing agent MUST call
   `tlm_set_phase("awaiting_spec_audit_approval")` before writing any plan docs.
   Stage 2 MUST call `tlm_set_phase("awaiting_plan_approval")`. Any agent that
   skips the phase transition triggers a compliance failure.

2. **If TLM enforcement isn't available:** rephrase as a *user-observable
   checkpoint* — "End your message here with: 'SPEC AUDIT COMPLETE — awaiting
   your go-ahead before drafting the master plan.' Do not continue until the
   user replies." That's still advisory, but at least the response boundary
   forces a pause.

Currently: both gates are decorative text that auto mode will skip.

---

## HIGH

### H1. Light intensity will never be chosen — the trigger definition is circular

**Severity: HIGH**

The skill defines Light as appropriate for: "2-file isolated bug fix; analytics/
logging only; reversible config."

But the skill's own trigger description says it applies to "anything that isn't a
trivial one-liner." A 2-file bug fix that requires tests is, by CLAUDE.md's own
Medium classification, a "non-trivial bug fix touching 3+ files" once you count
the test file. So the Light criteria overlap exactly with what CLAUDE.md
(Medium) already handles without this skill.

In practice: an agent classifying "add a feature flag" will reason "this is not
a trivial one-liner, so this skill applies; the table says default is Full; I
will do Full." The agent never has enough confidence to choose Light because the
"Full (default)" nudge is too strong and Light's criteria are not distinct from
CLAUDE.md's existing Medium category.

Result: every non-trivial task becomes a 7-stage, 20-artifact process. A
"add loading spinner" feature will get a spec_audit.md with 5+ forced findings,
a master plan, 5 agent reviews, 4 docs per phase — before a single line of UI
code. That overhead will cause the operator to stop using the skill.

**Fix:** Make Light's criteria EXCLUSIVE from the trigger conditions. Options:

- Give Light a concrete doc ceiling: "Light = produce only: brief plan in
  conversation + single phase-evidence.md. No spec_audit, no master README,
  no multi-agent review."
- Give Light a concrete trigger: "If the change touches ≤ 3 files (including
  tests), the blast radius is isolated (one endpoint, one module, no shared
  state), and no data migration is involved: use Light."
- Add a third tier "Minimal" that's literally just TDD + code-reviewer
  auto-hook.

Also: the skill says "User can override: 'be thorough' → full; 'just do it' →
light." This is good, but should be the PRIMARY trigger for Light, not a note
at the end. Most legitimate Light invocations will come from user override, not
from agent self-classification.

---

### H2. Spec audit "minimum 5 findings" rule manufactures theater

**Severity: HIGH**

Stage 1 states: "A spec audit with fewer than 5 findings was not scrutinized
hard enough. The encryption audit had 16 across CRITICAL/HIGH/MEDIUM/LOW."

This is a bureaucratic floor that incentivizes padding. A "add rate limiting to
the admin endpoint" feature legitimately has 1-2 critical findings and maybe 2
medium ones. Demanding 5 findings will cause an agent to manufacture LOW-severity
findings ("consider documenting this") to hit the floor, producing noise that
buries the real signal.

The encryption audit had 16 because encryption is an inherently complex,
multi-surface, threat-modeled domain. Most features are not that. The
correlation between "thorough audit" and "N >= 5 findings" does not hold for
smaller features — even on Full intensity.

**Fix:** Remove the numeric floor. Replace with a qualitative gate: "The spec
audit must explicitly address: (a) security surface, (b) concurrent access or
race conditions, (c) failure modes under partial failure, (d) cost impact, and
(e) rollback safety. If any of these have zero findings, state explicitly why
it's a non-issue for this feature." That forces completeness without
incentivizing padding.

---

## MEDIUM

### M1. "Re-run agent review" (Stage 5) lacks a hard gate on when to skip it

**Severity: MEDIUM**

Stage 5 says "After all CRITICAL/HIGH findings are addressed, re-launch the
same agents." The Quick Checklist has: "Agents re-ran after fixes; verdicts
upgraded; documented in SUMMARY.md."

In the encryption story, Stage 5 happened because agents found 4 categories of
real bugs at Stage 3. But for a smaller feature where Stage 3 produces only
MEDIUM/LOW findings (or the code-reviewer says APPROVE), re-running agents
means launching 3-4 subagents to verify "yes we still approve." That's
expensive and pointless.

The skill has no rule for this case. An agent will either always re-run (wasteful)
or skip silently (defeats the intent).

**Fix:** Add a conditional: "Re-run Stage 3 agents if and only if any original
agent verdict was NEEDS_REVISION or DO_NOT_SHIP. If all agents approved at
Stage 3, proceed directly to Stage 6. Document the skip rationale in SUMMARY.md
as: 'No re-review required — all agents approved at first pass.'"

---

### M2. Phase verify.md vs evidence.md separation will collapse in practice

**Severity: MEDIUM**

Stage 4.2 introduces `phase-N-verify.md` as the verification PLAN written
before running anything, and 4.4 as `phase-N-evidence.md` which is the observed
output. The intent — "plan verification BEFORE running it" — is correct and
valuable. The encryption work shows this worked.

But the skill doesn't explain why these are two separate files rather than
two sections in one file. An agent that doesn't understand the "why" will
merge them: write phase-N-verify.md, run tests, paste results into the same
file, call it evidence.md, skip the separate file. That destroys the "plan
before run" guarantee.

**Fix:** Add one sentence of rationale: "These are separate files so that a
reviewer can confirm the pass criteria were written before the run (by checking
commit timestamps). A single file can be edited after the fact; two separately
committed files cannot be trivially falsified."

---

### M3. operator-tooling requirements are too prescriptive for non-data-touching features

**Severity: MEDIUM**

Stage 6.4 requires `scripts/<feature>/` with: a README, a lifecycle health-check
script, inventory scripts, per-entity state-flip scripts, bulk-operation scripts,
reverse migration scripts. The Quick Checklist mandates: `scripts/<f>/run_<f>_lifecycle.sh`
exists.

For features that don't touch persistent data or operator-facing rollout state,
this is pure overhead. Examples: adding a new API endpoint, a new UI screen,
a notification type, a ranking tweak. None of these need operator scripts or
lifecycle health checks beyond "does the endpoint return 200."

The encryption scripts directory exists because encryption has: per-user state
that operators need to flip, an irreversible migration path, a rollback
procedure that requires decrypting stored data. That's not true for most features.

**Fix:** Gate operator tooling explicitly: "Required for: features with
per-entity rollout state, data migrations, or irreversible operations.
Optional for: feature-flagged behavior changes with no persistent schema impact.
For optional cases, the lifecycle check can be as simple as: 'run existing
integration tests, confirm exit 0.' The scripts/ directory is not required."

---

## LOW

### L1. Worked-example cross-references point to internal file locations that
will drift

**Severity: LOW**

The skill references `plans/encryption/README.md lines 9-100 (F1-F16)` as
the spec audit location. The spec audit is embedded in the README, not in a
separate spec_audit.md — which is what the skill itself requires. This is an
inconsistency that will confuse an agent that reads the worked example and
then looks at the required artifact structure: the example doesn't match the
template.

Similarly, the summary table maps "Spec audit" to `README.md lines 9-100`
which means the worked example DOES NOT HAVE a `spec_audit.md`. An agent
reading the directory structure at `ls plans/encryption/` will not find
spec_audit.md — because it doesn't exist in the reference implementation.

**Fix:** Either (a) acknowledge explicitly "the encryption work predates this
skill's artifact naming — in that project the spec audit was embedded in
README.md; going forward it must be a separate spec_audit.md" or (b) extract
the F1-F16 section from README.md into a standalone spec_audit.md so the
worked example matches the template.

---

### L2. Sub-phase naming rule "don't pre-allocate 5b/5c/5d" conflicts with
master plan TDD section

**Severity: LOW**

Stage 2 says: "Sub-phases (5b, 5c, 5d) get added LATER when post-rollout
review finds gaps. Don't pre-allocate them."

But Stage 2 also requires a "TDD plan" section in README.md: "Test files to
create per phase, what they verify, expected RED→GREEN." If sub-phases can't
be pre-allocated, the TDD plan in the README is necessarily incomplete for
anything that ends up needing a 5b. That's fine in principle — the skill
acknowledges sub-phases are added reactively — but the instruction conflicts
with the implication that the README's TDD plan is comprehensive.

**Fix:** Add one sentence to the TDD plan section: "The TDD plan covers
pre-planned phases only. Sub-phases (5b, 5c, etc.) are planned at the time
they are created, not in this master TDD plan."

---

### L3. "No long-lived feature branches" is aspirational, not enforced

**Severity: LOW**

The Quick Checklist final item: "All commits on main; no long-lived feature
branches." CLAUDE.md says "Push directly to main branch by default. Only create
feature branches when explicitly instructed." So the checklist item is already
the default — stating it doesn't add enforcement. An agent on an issue branch
(i-NNN) would check this box anyway because it's on a feature branch that it
was explicitly told to use.

Not worth fixing, but worth knowing: this checklist item is inert for the
cases where it matters.

---

## What's Good

1. **The 4-document-per-phase structure is excellent and concrete.** An agent
   can copy-paste the templates and fill in the blanks. The separation of
   phase spec / verify plan / evidence / summary is the single biggest process
   improvement here and is well-justified by the encryption example.

2. **The agent prompt template (Stage 3) is genuinely useful.** The 5-question
   checklist (irreversible steps, code paths not in the plan, edge cases, rollback
   in 5 minutes, feature-specific risks) produces the kind of hostile review that
   found real bugs in the encryption work. The placeholder for question 4 is a
   good reminder to customize per-feature.

3. **Anti-patterns section is grounded in real failures.** Every item in the
   10-point anti-patterns list traces to an actual failure mode observed in the
   encryption work (the audit trail, silent sub-phase rewrites, STATUS.md going
   stale). This is not generic advice.

4. **The operator-tooling section reflects the actual encryption scripts.**
   The workflow structure (read-only inventory → per-entity flip → bulk migration
   → reverse migration) and the "all scripts default to dry-run" discipline are
   exactly what the encryption scripts implement. This is battle-tested.

5. **Disposition rules table for agent findings (Stage 3) is non-negotiable
   and correctly escalates CRITICAL.** The table is clear enough that an agent
   cannot misread it.

6. **The verdict-upgrade concept (Stage 5) is the right mechanism.** Re-running
   the same agents with focused prompts that reference their original findings
   creates an auditable chain: "Agent said X was broken → we fixed it → same
   agent confirmed it's fixed." That's more rigorous than a self-certification.

---

## Summary of Required Changes

| # | Severity | Fix |
|---|----------|-----|
| C1 | CRITICAL | Replace fake `Agent()` syntax with actual subagent invocation pattern |
| C2 | CRITICAL | Make stop-gates create real response boundaries, not just prose |
| H1 | HIGH | Make Light criteria exclusive from Full; define a doc ceiling for Light |
| H2 | HIGH | Remove numeric floor (>=5 findings); replace with domain-coverage checklist |
| M1 | MEDIUM | Add skip condition for Stage 5 re-review when Stage 3 was all-APPROVE |
| M2 | MEDIUM | Explain why verify.md and evidence.md are separate files (audit trail) |
| M3 | MEDIUM | Gate operator-tooling requirement on feature type (data-touching vs. not) |
| L1 | LOW | Acknowledge spec_audit.md doesn't exist in worked example; fix or note |
| L2 | LOW | TDD plan note: sub-phases are planned at creation time, not up-front |
| L3 | LOW | (Inert) — no action needed |

---

## VERDICT: NEEDS REVISION

The seven-stage arc, the 4-doc-per-phase structure, the agent prompt templates,
and the anti-patterns are all solid. This is not a rewrite. The two CRITICALs
must be fixed before this skill is used in production: C1 will cause agents to
invent a non-existent API for launching reviewers, and C2 will cause agents in
auto mode to skip the two most important gates in the entire process. Fix those
two and the skill is substantially correct.
