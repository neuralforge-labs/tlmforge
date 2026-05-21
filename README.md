# tlmforge

A Claude Code plugin that brings spec-driven discipline and adversarial multi-agent review to AI-assisted feature development.

## The problem

As your codebase grows, AI coding assistants produce more bugs — not because the model gets worse, but because there is no structure enforcing that a plan exists before code is written, that independent reviewers have checked the work, or that each phase is verified before the next begins. The result is fast output that slowly degrades in correctness.

tlmforge adds that structure. Every feature goes through a spec audit before any code is touched, independent agents review the plan and the output, and nothing ships until the review gate clears.

## How it works

tlmforge auto-classifies every task into one of three intensity levels and announces its choice before starting:

- **Light** — trivial change (typo, rename, config tweak). Main agent handles it inline with TDD and self-review. Zero subagent spawns.
- **Medium** — fix or refactor of existing behavior. Abbreviated spec audit → single-round architect + tester review → phase-gated TDD → phase-auditor sign-off.
- **Deep** — new capability or surface. Full 7-stage recipe: spec audit → master plan → bounded multi-agent plan review → phase-gated TDD execution → adversarial red-team audit → live verification → operator tooling.

The hooks enforce the workflow mechanically — Claude cannot write or commit code until the appropriate skill stage has been completed for the current task.

## Install

```bash
claude plugin marketplace add neuralforge-labs/tlmforge
claude plugin install tlmforge@neuralforge-labs
```

**Restart Claude Code after install.** Plugin manifests are cached per session; a restart is required for the agents and hooks to take effect.

Invoke on any task:

```
/tlmforge:feature-development
```

Or just describe your task — the `UserPromptSubmit` hook reminds Claude to invoke the skill automatically.

## What's included

**Hooks** — auto-active after install, no configuration needed

| Hook | Trigger | Behaviour |
|---|---|---|
| Skill reminder | Every user prompt | Reminds Claude to invoke the feature-development skill before starting work |
| Mutation guard | Before Edit / Write / Bash | Advisory reminder if the skill was not invoked for the current task |
| Post-Stage-5 gate | Before `git commit` / `git push` / `gh pr merge` | Blocks if HEAD has drifted past the SHA recorded in the final audit |

Disable for a session: `TLMFORGE_HOOKS=0`. Bypass for a single task: include `be quick`, `just do it`, or `trivial fix` in your prompt.

**Skills**

| Skill | Purpose |
|---|---|
| `tlmforge:feature-development` | The core recipe — Light / Medium / Deep paths |
| `tlmforge:property-test-generator` | Generates Hypothesis property tests from invariants |
| `tlmforge:test-impact-graph` | AST-based reverse dependency graph — run only tests affected by your diff |
| `tlmforge:golden-eval` | Drift detection against a fixed task corpus |
| `tlmforge:live-evaluator` | Fresh-context QA for Stage 6 live verification |

**Agents** — spawned automatically by the skill at the right stage

| Agent | Stage | Role |
|---|---|---|
| `tlmforge:architect-reviewer` | Stage 3 + Stage 5 | Architecture soundness, over-engineering, hallucinated APIs |
| `tlmforge:threat-modeler` | Stage 3 (Deep) | Design-time adversarial review — trust boundaries, auth assumptions, PII flows |
| `tlmforge:tester` | Stage 3 + Stage 4 phase-end | QA — failure modes, timing conditions, edge cases |
| `tlmforge:general-purpose` | Stage 3 (Deep) | Cost, deployment feasibility, docs accuracy, ops readiness |
| `tlmforge:code-reviewer` | Stage 4 phase-end | TDD enforcement, test quality, full-file context review |
| `tlmforge:phase-auditor` | Stage 4 phase-end + Stage 5 (Medium) | Verifies each phase delivered what its spec promised |
| `tlmforge:ux-reviewer` | Stage 3 + Stage 4 (UI phases) | Layout, accessibility, interaction patterns |
| `tlmforge:red-team-reviewer` | Stage 5 (Deep) | IDOR, TOCTOU, injection, timing attacks, prompt injection |

## Learn more

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — flow diagram, classification gate, spawn-count comparison, escalation paths
- **[skills/feature-development/SKILL.md](skills/feature-development/SKILL.md)** — the complete recipe with all stage instructions

## Requirements

- Claude Code (any recent version)
- Python 3.9+
- `pip install jsonschema pyyaml`

## License

Apache-2.0 — see [LICENSE](LICENSE).

---

TLMForge is built by [Arpit Tripathi](https://www.linkedin.com/in/arpit-tripathi/).

**Issues:** [github.com/neuralforge-labs/tlmforge/issues](https://github.com/neuralforge-labs/tlmforge/issues)

Looking for a premium offering built on top of TLMForge? Sign up at [tlmforge.dev](https://tlmforge.dev/).
