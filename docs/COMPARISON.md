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
| Structured methodology before code | ✓ (7-phase) | Partial (role prompts) | ✓ (spec audit + master plan) |
| Auto task classification by complexity | ✗ | ✗ | ✓ (Light / Medium / Deep) |
| Truly independent cold-started reviewer agents | ✗ (reverted — see below) | ✗ (same model, role prompts) | ✓ (8 agents, distinct framing) |
| Dedicated threat-modeler at design time | ✗ | ✗ | ✓ (Stage 3) |
| Adversarial red-team review as final gate | ✗ | Partial (same-model framing) | ✓ (Stage 5, Opus) |
| Mechanical enforcement via hooks | ✗ | ✗ | ✓ (blocks mutations) |
| SHA-anchored commit lock after final audit | ✗ | ✗ | ✓ |
| Phase-gated execution with verification artifacts | ✗ | ✗ | ✓ (4 artifacts/phase) |
| Bounded review loops with carry-forward findings | ✗ | ✗ | ✓ (3-round cap) |
| TDD enforcement (hooks block code before tests) | ✓ (process-based) | ✗ | ✓ (mechanical) |
| Escape hatch for trivial work | ✗ | N/A | ✓ |
| Works across multiple IDEs / AI tools | ✓ (v5+) | ✓ | Claude Code only |

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

gstack is Garry Tan's personal Claude Code configuration, open-sourced. Its core insight: give Claude a role, and it performs better within that role. The 23 skills simulate a team: CEO, Designer, Staff Engineer, QA Lead, Release Manager, Doc Engineer. It's a productivity tool, and the 89K stars reflect its real-world utility.

**The fundamental difference is what "multi-agent" means.**

gstack uses role-based *prompts* — different instructions given to the same model within the same session. The "adversarial review" skill tells Claude to "think like an attacker and a chaos engineer." That's a useful framing. But it's the same model, with the same in-context knowledge of the implementation it's reviewing.

tlmforge's reviewer agents are cold-started with no implementation context — they only see what they're given to review. The threat-modeler doesn't know how the feature will be built; it attacks the design. The red-team-reviewer doesn't know what shortcuts the implementation agent made; it finds the holes. That independence is the mechanism by which agents catch things the implementation agent rationalized away.

**Other differences:**
- gstack has no phase gates. There's no mechanism enforcing that each phase was verified before the next started.
- gstack has no verification artifacts. No `phase-N-evidence.md`, no `tester_edge_cases.json`, no `final_audit_red-team.json`. The work happens but nothing proves it happened.
- gstack has no mechanical TDD enforcement. It's a role framing, not a hook that blocks mutations.
- gstack has no SHA-anchored commit lock.
- gstack's adversarial review is one agent with an adversarial framing; tlmforge's Stage 5 uses Opus in a cold-started session specifically hunting IDOR, TOCTOU, injection, timing attacks, and prompt injection.

**Honest summary:** gstack is an excellent velocity tool — it makes Claude Code faster and more structured for solo developers and founders. If you're shipping fast and willing to catch bugs post-ship, gstack is well-designed for that pace. tlmforge is designed for the opposite tradeoff: slower up front, correct at the end. For production codebases where bugs have real costs, the verification gates matter.

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
