# tlmforge

**The missing process layer for Claude Code.**

Claude Code writes code fast. tlmforge makes sure it's *correct* — by enforcing a spec audit before any code is touched, running 8 independent agents against your plan and your output, and blocking commits that haven't cleared an adversarial red-team review.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.15-brightgreen.svg)](.claude-plugin/plugin.json)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-orange.svg)](https://claude.ai/code)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)

---

## The gap no other tool fills

Every AI coding assistant optimizes for *velocity*. You type, it writes, the diff lands in seconds.

None of them solve what actually causes production bugs: **no process**. There's nothing enforcing that:

- A spec exists before a single line is written
- An independent agent has reviewed the plan for logic holes
- Tests were written before implementation, not after
- Each phase was verified complete before the next started
- A security-focused adversary looked for IDOR, injection, and auth bypasses

tlmforge adds that process. Not as a suggestion — mechanically, via hooks. Claude literally cannot write or commit code until the appropriate workflow stage has been completed for the current task.

---

## How tlmforge compares

| Capability | Claude Code (vanilla) | Aider | OpenHands | SWE-agent | tlmforge |
|---|:---:|:---:|:---:|:---:|:---:|
| Spec audit before any code | ✗ | ✗ | ✗ | ✗ | **✓** |
| Auto task classification (Light / Medium / Deep) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Independent multi-agent plan review | ✗ | ✗ | Partial | ✗ | **✓** (3-round bounded) |
| TDD enforcement — tests before impl | Best-effort | Best-effort | Best-effort | ✗ | **✓** (hooks block mutations) |
| Phase-gated execution with verification artifacts | ✗ | ✗ | ✗ | ✗ | **✓** (4 artifacts/phase) |
| Adversarial red-team audit | ✗ | ✗ | ✗ | ✗ | **✓** (Stage 5, Opus) |
| Threat modeling at design time | ✗ | ✗ | ✗ | ✗ | **✓** (Stage 3) |
| Calibrated: skips process for trivial tasks | N/A | ✗ | ✗ | ✗ | **✓** (bypass phrases) |
| Works on any codebase, no hardcoded paths | ✓ | ✓ | ✓ | ✓ | **✓** |
| Open source | ✓ | ✓ | ✓ | ✓ | **✓** |

> Full comparison with rationale: [docs/COMPARISON.md](docs/COMPARISON.md)

---

## Three intensity levels — auto-classified

tlmforge announces its choice before starting. You can say `"go deeper"` or `"go lighter"` at any point.

**Light** — Zero new logic. Typo, rename, config tweak.
→ Main agent handles inline with TDD and self-review. **Zero subagent spawns.**

**Medium** — Fix or refactor of existing behavior. No new product surface.
→ Abbreviated spec audit → single-round architect + tester review → phase-gated TDD → phase-auditor sign-off.

**Deep** — New capability or surface that didn't exist before.
→ Full 7-stage recipe (below).

The classification is *semantic*, not keyword-based — the model judges the work, not a pattern matcher. Security surfaces (auth, crypto, PII, sessions) auto-escalate to Deep regardless of scope.

---

## The 7-stage Deep path

```
Stage 1  Feature request analysis → spec_audit.md
         Hidden assumptions, threats, costs, rollback risks surfaced before planning.

Stage 2  Master plan → specs/<feature>/README.md
         Structured implementation plan. Gate fires only on unapproved decisions.

Stage 3  Bounded 3-round plan review (parallel, cold)
         architect-reviewer + tester + threat-modeler [+ ux-reviewer if UI]
         Round 2+3: reviewers verify their own prior findings (no re-derivation).
         Tester emits tester_edge_cases.json — becomes TDD seed at Stage 4.

Stage 4  Phase-gated TDD execution
         For each phase: tests first → RED → implement → GREEN → full regression suite.
         Phase-end: code-reviewer + tester + phase-auditor [+ ux-reviewer if UI diff].
         4 artifacts per phase: spec, verify, evidence, summary.

Stage 5  Single-shot dual final audit (parallel, no iteration)
         red-team-reviewer [Opus]    — IDOR, TOCTOU, injection, timing, prompt injection
         architect-reviewer [Sonnet] — cross-phase holistic design review
         CRITICALs → FINAL_ESCALATION.md → you decide.

Stage 6  Live verification
         Fresh-context QA agent runs against the deployed environment.

Stage 7  STATUS.md executive dashboard + learnings.md
```

Nothing advances until the current stage clears. Escalation paths at every gate give you the choice: accept residual risk, extend rounds, revise, or abandon.

---

## 8 specialized agents

Each agent has one job. Spawned automatically at the right stage — you never invoke them directly.

| Agent | Stage | Job |
|---|---|---|
| `architect-reviewer` | 3, 5 | Architecture soundness, over-engineering, hallucinated APIs |
| `threat-modeler` | 3 (Deep) | Trust boundaries, auth assumptions, PII flows — design time |
| `tester` | 3, 4-end | Failure modes, edge cases, timing — emits TDD seed JSON at Stage 3 |
| `general-purpose` | 3 (Deep) | Cost, deployment feasibility, docs accuracy, ops readiness |
| `code-reviewer` | 4-end | TDD compliance, test quality, full-file context (not just diffs) |
| `phase-auditor` | 4-end, 5 | Promise vs. delivered — did this phase do what its spec said? |
| `ux-reviewer` | 3, 4 (UI) | Layout, accessibility, interaction patterns, platform conventions |
| `red-team-reviewer` | 5 (Deep) | IDOR, TOCTOU, injection, timing attacks, prompt injection |

---

## Token efficiency — not naïve multi-agent

The obvious multi-agent approach burns through context: spawn a reviewer on every save, run opus everywhere, converge without a cap. That approach averages ~145 subagent spawns for a 5-phase feature, ~31 of them on Opus.

tlmforge's lean architecture cuts that by 75–99%:

| Path | Naïve approach | tlmforge 0.5.x |
|---|---|---|
| Light task | ~4 spawns × every save | **0 spawns, 0 Opus** |
| Medium feature (5 phases) | N/A (path didn't exist) | **~13–15 spawns, 0 Opus** |
| Deep feature (5 phases) | ~145 spawns, ~31 Opus | **~30–40 spawns, 1 Opus** |

Opus is reserved for exactly one job: the adversarial red-team pass at Stage 5. Everything else runs on Sonnet.

How: bounded review loops (3 rounds max, carry-forward findings), stop-hook removal (review at defined gates, not after every file write), and the Light path using zero subagents.

---

## Install

```bash
claude plugin marketplace add neuralforge-labs/tlmforge
claude plugin install tlmforge@neuralforge-labs
```

**Restart Claude Code after install.** Plugin manifests are cached per session.

Then just describe your task. The `UserPromptSubmit` hook reminds Claude to invoke the skill automatically. Or invoke directly:

```
/tlmforge:feature-development
```

**Bypass for trivial work:** include `be quick`, `just do it`, or `trivial fix` in your prompt.  
**Disable for a session:** `TLMFORGE_HOOKS=0`

---

## What's included

**3 enforcement hooks** — auto-active after install, no configuration needed

| Hook | Trigger | Behavior |
|---|---|---|
| Skill reminder | Every user prompt | Reminds Claude to invoke feature-development before starting work |
| Mutation gate | Before Edit / Write / Bash | Advisory reminder if skill wasn't invoked for current task |
| Post-Stage-5 gate | Before `git commit` / `git push` / `gh pr merge` | Blocks if HEAD drifted past the final-audit SHA |

**5 companion skills**

| Skill | Purpose |
|---|---|
| `tlmforge:feature-development` | Core recipe — Light / Medium / Deep |
| `tlmforge:property-test-generator` | Generates Hypothesis property tests from behavioral invariants |
| `tlmforge:test-impact-graph` | AST reverse-dep graph — runs only tests affected by your diff |
| `tlmforge:golden-eval` | Drift detection: run a fixed task corpus, flag regressions vs baseline |
| `tlmforge:live-evaluator` | Fresh-context QA agent for Stage 6 live verification |

---

## Requirements

- Claude Code (any recent version)
- Python 3.9+
- `pip install jsonschema pyyaml`

---

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — full flow diagram, spawn-count analysis, escalation paths, carryover artifacts
- [docs/COMPARISON.md](docs/COMPARISON.md) — tlmforge vs Aider, OpenHands, SWE-agent, vanilla Claude Code
- [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md) — why process discipline matters more as codebases grow
- [CHANGELOG.md](CHANGELOG.md) — version history (0.2.0 → 0.5.x)

---

## License

Apache-2.0 — [LICENSE](LICENSE). Copyright 2026 Neural Forge Technologies LLP.

---

Built by [Arpit Tripathi](https://www.linkedin.com/in/arpit-tripathi/).  
**Issues / bugs:** [github.com/neuralforge-labs/tlmforge/issues](https://github.com/neuralforge-labs/tlmforge/issues)  
**Premium offering:** [tlmforge.dev](https://tlmforge.dev/)
