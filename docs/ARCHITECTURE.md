# tlmforge — Architecture

> Living document. Edit this whenever the flow changes. SKILL.md is the
> normative source; this is the diagram + commentary.

## The lean review architecture (0.5.x)

```
                      USER REQUEST
                           │
                           ▼
  ┌────────────────────────────────────────────────────────────────────┐
  │ Classification gate (main Claude self-classifies, user confirms)   │
  │                                                                     │
  │ Semantic signals — judge the WORK, not file paths:                  │
  │   • Security surface (auth / encryption / secrets / PII / IDOR)     │
  │   • Persistent state (schema / migration / irreversible op)         │
  │   • Cross-module scope (>5 files / multi-module / public API)       │
  │   • Customer-facing impact (UI / public API / billing path)         │
  │   • User language signals ("be quick" / "thorough" / "production")  │
  │   • Task ambiguity                                                  │
  │                                                                     │
  │ Asymmetric default:                                                 │
  │   both must agree Light → Light                                     │
  │   either says Deep → Deep                                           │
  │                                                                     │
  │ Clearly Light (skip the ask): "be quick" + single-file no-surface   │
  │ Clearly Deep  (skip the ask): "thorough"/"production-grade"/        │
  │                                explicit migration/schema/auth/PII   │
  │ Else: AskUserQuestion(Light | Deep | Other)                         │
  └────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴────────────────┐
            ▼                                   ▼
  ╔═══ LIGHT/MINIMAL ══╗                ╔══════ DEEP ══════╗
  ║  Main agent only   ║                ║ Invoke skill     ║
  ║  ZERO subagent     ║                ║ Stages 1–7       ║
  ║  spawns            ║                ╚══════════════════╝
  ╚════════════════════╝                          │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 1: Request audit (main only)                  │
            │      │   Audits the user's REQUEST (not a pre-existing     │
            │      │   spec doc — none exists yet). Surfaces hidden      │
            │      │   assumptions, threats, edge cases, costs,          │
            │      │   rollback risks. Produces the structured spec.     │
            │      │   → specs/<f>/spec_audit.md                         │
            │      │                                                     │
            │      │ Open questions tagged [GATE-BLOCKING] or            │
            │      │ [INFORMATIONAL]. Gate fires ONLY on                 │
            │      │ [GATE-BLOCKING]. No hardcoded keyword list — the    │
            │      │ classification gate at task entry already filtered  │
            │      │ for serious work.                                   │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 2: Master plan (main only)                   │
            │      │   → specs/<f>/README.md                            │
            │      │                                                     │
            │      │ Conditional gate fires IFF the plan introduces      │
            │      │ NEW unapproved decisions. Else: proceed same turn.  │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 3: Plan review — bounded 3-round loop         │
            │      │                                                     │
            │      │  Round 1 (cold, parallel) — all [sonnet]:           │
            │      │    • architect-reviewer                             │
            │      │    • tester    (also emits tester_edge_cases.json)  │
            │      │    • threat-modeler                                 │
            │      │    • ux-reviewer (only if UI in plan)               │
            │      │       → round-1-<reviewer>.{md,json}                │
            │      │                                                     │
            │      │  Main fixes plan → round-1-fixes.md                 │
            │      │                                                     │
            │      │  Round 2 (verify-your-findings, same reviewers):    │
            │      │    Each reads round-1-<own>.json + round-1-fixes.md │
            │      │    FIXED / PARTIALLY / NOT_FIXED per prior finding  │
            │      │    NEW findings only if genuinely missed in R1      │
            │      │       → round-2-<reviewer>.{md,json}                │
            │      │                                                     │
            │      │  If all approve: → Stage 4                          │
            │      │  Else: main fixes → round-2-fixes.md → Round 3      │
            │      │                                                     │
            │      │  Round 3: same protocol against round-2             │
            │      │       → round-3-<reviewer>.{md,json}                │
            │      │                                                     │
            │      │  Still NOT approved after R3 → ESCALATION.md →      │
            │      │       prompt user (accept / extend / abandon)       │
            │      │                                                     │
            │      │  → agent_verification/SUMMARY.md                    │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 4: Phase execution (FOR EACH PHASE N)         │
            │      │                                                     │
            │      │  Main implements with TDD:                          │
            │      │   1. Read tester_edge_cases.json (Stage 3 carryover)│
            │      │   2. For each scenario → assign test layer          │
            │      │      (unit always; integration if module-crossing;  │
            │      │       E2E if user-facing flow)                      │
            │      │   3. Write tests FIRST → run → RED                  │
            │      │   4. Implement minimum code                         │
            │      │   5. Run NEW tests + FULL pre-existing suite        │
            │      │      → GREEN + 0 regressions                        │
            │      │   6. Capture test-run output into phase-N-evidence  │
            │      │                                                     │
            │      │  4 artifacts per phase:                             │
            │      │   phase-N-<topic>.md      (spec)                    │
            │      │   phase-N-verify.md       (committed BEFORE run)    │
            │      │   phase-N-evidence.md     (committed AFTER run)     │
            │      │   phase-N-summary.md      (honest retro)            │
            │      │   phase-N-state.md        (git_sha anchor)          │
            │      │                                                     │
            │      │  NO Stop hooks during phase impl ← was 30+ spawns   │
            │      │                                                     │
            │      │  Phase-end (also 3-round-cap, same protocol):       │
            │      │    Parallel:                                        │
            │      │      • code-reviewer  [sonnet]                      │
            │      │      • tester         [sonnet] (re-runs suite)      │
            │      │      • phase-auditor  [sonnet] (promise-vs-deliver) │
            │      │      • ux-reviewer    [sonnet] IF UI files in diff  │
            │      │       → phase-N-verification/<reviewer>.{md,json}   │
            │      │                                                     │
            │      │  All approve → next phase                           │
            │      │  Round 3 unresolved → ESCALATION.md                 │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼ (after all phases)
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 5: Final audit — 2 single-shot agents         │
            │      │                                                     │
            │      │   • red-team-reviewer    [opus]   (impl-adversarial)│
            │      │   • architect-reviewer   [sonnet] (cross-phase      │
            │      │                                    holistic design) │
            │      │                                                     │
            │      │   Parallel. NO iteration. The one opus spawn.       │
            │      │   → final_audit_<reviewer>.{md,json}                │
            │      │                                                     │
            │      │   Both approve → Stage 6                            │
            │      │   Either CRITICAL → FINAL_ESCALATION.md →           │
            │      │       user decision                                 │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 6: Live verification (live-evaluator skill)   │
            │      │   Fresh-context QA agent re-runs against deployed   │
            │      │   environment                                       │
            │      │   → specs/<f>/E2E_VERIFICATION.md                   │
            │      └────────────────────────────────────────────────────┘
            │                                     │
            │                                     ▼
            │      ┌────────────────────────────────────────────────────┐
            │      │ Stage 7: STATUS.md (main only)                      │
            │      │   Executive dashboard                                │
            │      │   → specs/<f>/STATUS.md                             │
            │      │   Append <project>/learnings.md (one-time           │
            │      │      surprises captured for the next feature's      │
            │      │      Stage 1)                                       │
            │      └────────────────────────────────────────────────────┘
            │
            ▼
  ╔══════════════════════════════════════════════════════════════════╗
  ║ Light/Minimal flow (main agent reviewer-in-one)                  ║
  ║                                                                  ║
  ║  1. Identify scenarios + assign test layers                      ║
  ║     (unit always; +integration if crossing; +E2E if user-facing) ║
  ║  2. Write tests FIRST → run → confirm RED                        ║
  ║  3. Implement minimum code                                       ║
  ║  4. Run NEW + FULL pre-existing suite → GREEN + 0 regressions    ║
  ║  5. Self-review checklist:                                       ║
  ║      • TDD compliance per new function                           ║
  ║      • No commented-out / TODO / dead code                       ║
  ║      • No new secrets/auth/state outside scope                   ║
  ║         → if yes: PAUSE + re-ask classification gate (Deep?)     ║
  ║  6. Commit + push                                                ║
  ║                                                                  ║
  ║  Mid-task escalation: scope expands → re-ask gate                ║
  ╚══════════════════════════════════════════════════════════════════╝
```

## What the hooks look like in 0.5.x

```
Removed:
  Stop hook: tester              (was opus on every save)
  Stop hook: code-reviewer       (was sonnet on every save)
  Stop hook: ux-reviewer         (was sonnet on every UI save)
  Stop hook: process-compliance  (was sonnet on every assistant turn)

Kept:
  PreToolUse[ExitPlanMode] → architect-reviewer  (cheap safety net for
                                                  plans outside the skill)
  SessionStart → dotfiles sync (mechanical, not review)
```

## Spawn-count comparison (typical 5-phase feature)

| Path | Pre-0.5.0 | 0.5.x |
|---|---|---|
| Light/Minimal task | ~4 × N saves (Stop hooks fire on every code change) | **0** |
| Deep feature, 5 phases | ~145 spawns, ~31 OPUS | ~30–40 spawns, 1 OPUS |
| Total opus invocations | ~31 | **1** (red-team at Stage 5) |

The single biggest win is removing the tester Stop hook (opus, on every save).
Second biggest is bounding Stage 3 to 3 rounds with carry-forward findings
(reviewers verify their own prior findings instead of re-deriving from scratch
each round).

## Why no hardcoded keywords

The 0.5.0 redesign deliberately removed all path-based and keyword-based
gating. The plugin is generic — it doesn't know whether a project's
auth code lives at `backend/auth/`, `lib/security/`, `services/iam/`, or
somewhere else entirely. Hardcoded lists are wrong twice over:

1. They fail on projects whose conventions don't match the list (false
   negatives — sensitive work slips through ungated).
2. They falsely fire on projects where the list-words appear in benign
   contexts (false positives — unnecessary gating overhead).

The single classifier is the **classification gate at task entry** —
semantic signals, judged by the LLM, confirmed by the user, asymmetric
default to safety. Once routed to Deep, every Stage 1 audit tags its own
open questions `[GATE-BLOCKING]` or `[INFORMATIONAL]`. The Stage 1→2 gate
fires solely on those tags. No second classifier inside the skill.

## Carryover artifacts (avoid re-derivation across stages)

| Artifact | Produced by | Consumed by | Purpose |
|---|---|---|---|
| `tester_edge_cases.json` | tester at Stage 3 Round 1 | main Claude at Stage 4 (TDD seed); tester at Stage 4 phase-end (coverage validation) | Scenarios enumerated once, reused across stages |
| `round-N-fixes.md` | main Claude after each Stage 3 round | Stage 3 reviewers in round N+1 (verify-your-findings framing) | Reviewers know what to look for |
| `phase-N-state.md` | main Claude at phase start | Stage 4 phase-end agents; Stage 5 architect | `git_sha` anchor for phase-diff scoping |

## Escalation paths

When the bounded loops cap out without convergence:

- **Stage 3 round 3 unresolved** → write `agent_verification/ESCALATION.md`
  listing outstanding findings + ask user. Options: accept residual risk /
  extend rounds (cost more credits) / revise spec / abandon.
- **Stage 4 phase-end round 3 unresolved** → write
  `phase-N-verification/ESCALATION.md`. Same options.
- **Stage 5 CRITICAL** → write `agent_verification/FINAL_ESCALATION.md`.
  Stage 5 has no automatic retry — if CRITICALs exist, the user decides
  whether to fix-and-rerun (a fresh single-shot pair, not iteration),
  accept the residual risk with documented justification, or abandon.

## Known gaps (deferred to future releases)

- **`check_convergence.py` round-aware loader implementation** —
  characterization tests for the current script shipped in 0.5.1 (Phase 0);
  Phases 1–4 (defensive loader hardening, stage-specific path loaders,
  single-shot dual evaluator, integration tests) deferred. Today the
  script still expects flat `<role>_review.json` paths. Spec at
  `specs/check-convergence-round-aware/`.
- **Plugin marketplace cache refresh** — DF1 from the 0.5.x dogfood. Until
  the marketplace cache mechanism refreshes installed clients, end users
  see the old plugin behavior even after a version bump. Tracked
  separately as an operational fix.

## How to keep this doc current

Edit this file whenever:
- A stage gate condition changes
- A new reviewer agent is added (or removed)
- The Light/Deep classification logic changes
- A new carryover artifact is introduced
- The escalation protocol changes
- Spawn-count numbers change materially

The flow chart ASCII art is verbose but self-contained — copy-paste-edit
is fine. SKILL.md remains the normative source; if the two disagree,
SKILL.md wins, and this doc must be updated to match.
