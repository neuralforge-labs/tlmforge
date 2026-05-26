# tlmforge vs. the alternatives

This document compares tlmforge against the most-used AI coding frameworks and Claude Code plugins. Every tool here is genuinely useful — the question is what problem each one was designed to solve, and where the design trade-offs land.

---

## The landscape in 2026

Three open-source tools now dominate the conversation about structured AI coding workflows:

- **obra/superpowers** (174K+ stars) — Jesse Vincent's agentic skills framework: a 7-phase TDD-first methodology for Claude Code
- **garrytan/gstack** (89K+ stars) — Garry Tan's personal Claude Code configuration: 23 role-based slash commands that simulate an engineering team
- **neuralforge-labs/tlmforge** — spec-driven, multi-agent, mechanically enforced development workflow

All three agree on something important: *raw Claude Code without structure ships bugs*. Where they differ is in *how* they add structure, and what they're willing to trade to get it.

---

## Side-by-side

| Capability | superpowers | gstack | tlmforge |
|---|:---:|:---:|:---:|
| Structured methodology before code | ✓ (7-phase) | Partial (role-based skills) | ✓ (spec audit + master plan) |
| Auto task classification by complexity | ✗ | ✗ | ✓ (Light / Medium / Deep) |
| Spec audit / plan review by independent agent | ✗ (reverted to self-review — see below) | ✗ | ✓ (automatic, Stage 3) |
| Cross-model independent review (on-demand) | ✗ | ✓ `/codex` uses OpenAI Codex CLI | ✓ (automatic gates) |
| Dedicated threat-modeler at design time (before code) | ✗ | ✗ | ✓ (Stage 3) |
| Security audit (OWASP / STRIDE) | ✗ | ✓ `/cso` (on-demand, not a gate) | ✓ (Stage 5, Opus red-team, automatic gate) |
| Mechanical enforcement via hooks | ✗ | ✗ | ✓ (blocks mutations) |
| SHA-anchored commit lock after final audit | ✗ | ✗ | ✓ |
| Phase-gated execution with verification artifacts | ✗ | ✗ | ✓ (4 artifacts/phase) |
| Bounded review loops with carry-forward findings | ✗ | ✗ | ✓ (3-round cap) |
| TDD enforcement (hooks block code before tests) | ✓ (process-based) | ✗ | ✓ (mechanical) |
| Escape hatch for trivial work | ✗ | N/A | ✓ |
| Works across multiple IDEs / AI tools | ✓ (v5+) | ✓ (10 agents) | Claude Code only |

---

## tlmforge vs. obra/superpowers

Superpowers is the most directly comparable tool. Jesse Vincent arrived at a similar conclusion — AI coding needs process — and built a rigorous 7-phase methodology: Brainstorm → Worktree → Plan → Execute → TDD → Review → Complete. It's excellent work, and the 174K stars reflect it.

**The key difference is what happened when superpowers tried multi-agent plan review.**

Superpowers originally had a bounded multi-round review loop for specs and plans — a fresh subagent reviewing the brainstorm output and the written plan, with up to 5 iterations (later reduced to 3). In v5.0.6 they abandoned it entirely and replaced it with inline self-review checklists. Their own release note states:

> *"The subagent review loop (dispatching a fresh agent to review plans/specs) doubled execution time (~25 min overhead) without measurably improving plan quality. Regression testing across 5 versions with 5 trials each showed identical quality scores regardless of whether the review loop ran."*
> — [superpowers v5.0.6 release notes](https://github.com/obra/superpowers/blob/main/RELEASE-NOTES.md)

The result: "Self-review catches 3-5 real bugs per run in ~30s instead of ~25 min, with comparable defect rates."

Note: superpowers' task-level implementation review (in the Subagent-Driven Development skill) still uses fresh review subagents — spec compliance then code quality, per task. What was abandoned was specifically the plan/spec review loop — the equivalent of tlmforge's Stage 3.

**tlmforge takes the opposite approach to the same efficiency problem.** Rather than replace independent plan review with self-review, tlmforge redesigned the review loop to make independent review efficient:

- **Bounded 3-round loops with carry-forward findings** — reviewers in rounds 2 and 3 verify their own prior findings instead of re-deriving from scratch. This eliminates the token waste that drove superpowers' 25-min overhead.
- **Light path uses zero subagent spawns** — trivial tasks have no review overhead at all.
- **Sonnet for all review agents, Opus only at Stage 5** — the adversarial red-team pass is the one place where Opus's reasoning depth pays off.
- **Result**: ~30–40 spawns for a 5-phase Deep feature, vs. the ~145 that the naïve approach requires.

**Other structural differences:**
- tlmforge has a dedicated **threat-modeler** agent that reviews the design at Stage 3 before any code exists. superpowers has no equivalent.
- tlmforge's **SHA-anchored commit lock** blocks commits that drift past the final audit SHA. superpowers has no equivalent gate.
- tlmforge's **tester_edge_cases.json** carries reviewer findings forward from Stage 3 into Stage 4 as a TDD seed. superpowers doesn't carry findings forward as structured artifacts.
- tlmforge's **red-team-reviewer** (Opus, cold-started) runs as the final gate specifically hunting IDOR, TOCTOU, injection, and timing attacks. superpowers has no equivalent final adversarial pass.
- superpowers supports Claude Code, Cursor, Gemini CLI, GitHub Copilot CLI, Codex — tlmforge is Claude Code only.

**Honest summary:** If you want a battle-tested, IDE-agnostic skills framework with a large ecosystem and proven task-level multi-agent execution, superpowers is the right choice. If you want independent multi-agent *plan review* kept in the loop (rather than replaced with self-review) — with a threat-modeler, an adversarial final gate, and a SHA commit lock — that's what tlmforge provides.

---

## tlmforge vs. garrytan/gstack

gstack is Garry Tan's personal Claude Code configuration, open-sourced. It's grown substantially from its original "23 specialists and 8 power tools" framing — the current [docs/skills.md](https://github.com/garrytan/gstack/blob/main/docs/skills.md) lists 35+ skills across roles: CEO, Designer, Staff Engineer, QA Lead, Release Manager, Doc Engineer, Chief Security Officer, and more. It also supports 10 AI coding agents beyond Claude Code. The 89K stars reflect its real-world utility for founders and solo developers.

**What gstack actually has for review and security:**

- **`/review`** — Staff Engineer code review, run against the diff. Same Claude session.
- **`/codex`** — Spawns OpenAI Codex CLI for independent cross-model review. Three modes: code review (pass/fail gate), adversarial challenge ("tries to break your code"), and open consultation. Source: [`codex/SKILL.md`](https://github.com/garrytan/gstack/blob/main/codex/SKILL.md) describes it as "the '200 IQ autistic developer' second opinion."
- **`/cso`** — Chief Security Officer mode: OWASP Top 10 + STRIDE threat modeling + secrets archaeology + dependency supply chain + CI/CD + LLM/AI security. Two audit modes (daily: 8/10 confidence gate; comprehensive: monthly deep scan). Trend tracking across runs. Source: [`cso/SKILL.md`](https://github.com/garrytan/gstack/blob/main/cso/SKILL.md).

These are real capabilities. `/codex` in particular is genuinely independent cross-model review — not "same model with a different hat."

**What gstack doesn't have that tlmforge does:**

All three of those review skills — `/review`, `/codex`, `/cso` — are **user-invoked, on-demand**. None of them are automatic gates. You can ship code without ever running them. They're powerful tools that require you to remember to use them.

- No spec audit before code. gstack's `/office-hours` and `/plan-ceo-review` are excellent product-thinking tools, but they don't produce a structured spec audit that gates Stage 2. You can skip straight to implementation.
- No phase gates. No mechanism enforces that Phase N was verified before Phase N+1.
- No verification artifacts. No `phase-N-evidence.md`, no `tester_edge_cases.json`, no `final_audit_red-team.json` — nothing proves a gate was passed.
- No mechanical TDD enforcement. No hook that blocks file mutations before tests exist.
- No SHA-anchored commit lock. Nothing blocks commits that drift past the last review.
- `/cso` and `/codex` are post-implementation, not design-time. There's no threat-modeler that attacks the plan before any code is written.

**Honest summary:** gstack is a genuinely capable productivity toolkit with real cross-model review (`/codex`) and structured security auditing (`/cso`). It's designed for founders who want maximum velocity with good-enough review discipline. tlmforge is designed for codebases where "good-enough" isn't acceptable — where you need automatic gates that fire on every feature, not tools that require you to remember to invoke them.

---

## tlmforge vs. vanilla Claude Code

**What vanilla Claude Code gives you:** A capable coding assistant that writes code on demand. No structure, no enforcement, no review process.

**What accumulates without structure:** Claude will write code the moment you ask, skip specs if you don't ask for them, write tests after implementation if you don't insist, and commit without adversarial review. For throwaway scripts, fine. For a 20,000-line production codebase maintained over months, the correctness debt compounds.

**What tlmforge adds:** Classification gate before any code is written. Mandatory spec audit for non-trivial work. Independent reviewer agents at well-defined gates. TDD enforcement via hooks. Adversarial final pass before commit. SHA anchor blocking drift past the audit.

---

## tlmforge vs. Aider

[Aider](https://github.com/paul-gauthier/aider) is one of the best open-source AI pair programmers. Battle-tested, multi-model, excellent git integration, fast iteration.

Aider and tlmforge solve different problems. Aider optimizes for fast iteration with human oversight. tlmforge optimizes for structured, verified delivery of production features. They can coexist: Aider for fast exploration, tlmforge for features that need to ship with confidence.

What tlmforge adds that Aider doesn't have: spec audit, multi-agent plan review, phase-gated TDD, adversarial final gate.

---

## tlmforge vs. "just write a better CLAUDE.md"

The common alternative is adding process instructions to your system prompt. Tell Claude to write a spec first. Remind it to write tests.

This doesn't hold at scale:
- Instructions are suggestions. Claude skips them under context pressure.
- There's no mechanical enforcement. The mutation hook, the SHA lock, the approval-gate — these fire regardless of what Claude thinks it should do.
- Instructions don't produce verifiable artifacts. tlmforge produces `spec_audit.md`, `tester_edge_cases.json`, `phase-N-evidence.md`, `final_audit_red-team.json` — artifacts you can read, diff, and audit.
- The same model checking its own work has the same blind spots. Cold-started independent agents don't.

---

## Who should use what

| If you want... | Use |
|---|---|
| Broadest IDE support + proven 7-phase methodology | superpowers |
| Role-based productivity prompts for fast solo shipping | gstack |
| Multi-agent independent review + mechanical enforcement + commit gate | **tlmforge** |
| Fastest AI coding iteration, any model | Aider |
| Autonomous task execution (minimal human gates) | OpenHands |
| Exploration now + production delivery later | superpowers or gstack + tlmforge |

tlmforge occupies one specific slot: it's the only open-source Claude Code plugin that provides genuine multi-agent independent review with an efficiency architecture designed to make that review practical — not just described.
