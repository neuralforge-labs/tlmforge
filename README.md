# tlmforge

A Claude Code plugin that enforces production-grade feature development discipline through adversarial multi-agent review and mechanical convergence.

**The core idea:** you cannot ship until independent adversarial reviewers — with a mathematically enforced agreement metric — say the work is done.

📐 **Architecture diagram + commentary:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the living flow chart for the lean review architecture (classification gate, 7-stage Deep path, Light path, escalation paths, spawn-count math). Updated whenever the flow changes.

## What's inside

**Hooks (3 — auto-active after install)**
| Hook | When | What it does |
|---|---|---|
| Hook 1 — skill reminder | Every user prompt | Injects a `systemMessage` reminding Claude to invoke `tlmforge:feature-development` before doing work |
| Hook 2 — mutation reminder | Before Edit / Write / Bash / MultiEdit | Prints a reminder if the skill was not invoked in the current task window — advisory only, does not block |
| Hook 3 — post-Stage-5 gate | Before `git commit` / `git push` / `gh pr merge` | Blocks if HEAD has drifted past the SHA recorded in the Stage 5 final audit. Unblock by running a PSR (post-Stage-5 re-review) or setting `TLMFORGE_HOOKS=0` |

**Bypass / escape hatches**
- `TLMFORGE_HOOKS=0` (also `false` / `no` / `off`) — disables all three hooks for the session. Set in your shell before starting Claude Code, or export mid-session.
- Override phrases in your prompt — `be quick` / `just do it` / `trivial fix` — bypass Hook 2 for that single task. Bare "minimal" or "trivial" are NOT accepted (too common in technical prose).
- `tlmforge plugin remove` — nuclear option; removes all hooks permanently.

**Skills (5)**
| Skill | What it does |
|---|---|
| `tlmforge:feature-development` | 7-stage recipe: spec audit → master plan → multi-agent review → phase-gated TDD → re-review → live verification → operator tooling |
| `tlmforge:property-test-generator` | Converts invariants → Hypothesis property tests |
| `tlmforge:test-impact-graph` | AST-based reverse dependency graph — run only the tests affected by your diff |
| `tlmforge:golden-eval` | Drift detection: run a fixed task corpus against your Claude config, flag regressions |
| `tlmforge:live-evaluator` | Fresh-context skeptical QA for Stage 6 live verification |

**Agents (2)**
| Agent | When it fires |
|---|---|
| `tlmforge:threat-modeler` | Stage 3 — attacks design assumptions before any code is written (trust boundaries, auth assumptions, PII flows) |
| `tlmforge:red-team-reviewer` | Stage 5 tier-2 — single adversarial shot on finished code (IDOR, TOCTOU, timing attacks, prompt injection) |

## How it differs from superpowers

[superpowers](https://github.com/obra/superpowers) gives you workflow structure — brainstorm → plan → subagent dispatch → spec/quality review loop. It's excellent.

tlmforge adds a different layer on top: **convergence enforcement**. Instead of prose "approved/not approved", reviewers emit structured JSON against a strict severity schema. A Python convergence rule counts real CRITICALs, detects lazy-empty verdicts, injects synthetic findings for missing JSON, and blocks shipping until the metric hits zero. Plus adversarial agents specifically calibrated to attack your assumptions rather than review your implementation.

The two are complementary. Use superpowers for task dispatch and execution structure. Use tlmforge for the review quality gate.

## Install

```bash
claude plugin add github:neuralforge-labs/tlmforge
```

**Restart your Claude Code session after install or upgrade.** Claude Code caches plugin manifests per session — without a restart, newly added agents (like `phase-auditor`) won't appear in the agent registry, and updated `tools:` lists on existing agents won't take effect. Symptoms of a stale cache: `agent type not found` errors, or Stage 3 / Stage 5 convergence loops that never reach zero CRITICALs.

Once restarted, invoke the skill on any task:

```
/tlmforge:feature-development
```

## Optional: Gemini cross-model diversity

Set `GEMINI_API_KEY` in your environment to enable a 4th reviewer (Gemini) at Stage 5. If the key isn't set, the wrapper exits gracefully and the trio continues without it.

```bash
export GEMINI_API_KEY=your-key-here
```

## Requirements

- Claude Code (any recent version)
- Python 3.9+ (for convergence rule and test impact graph)
- `pip install jsonschema pyyaml` (for convergence rule)

## License

MIT — see [LICENSE](LICENSE).
