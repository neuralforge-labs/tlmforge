# tlmforge vs. the alternatives

This document compares tlmforge against the most commonly used AI coding tools and agent frameworks. All comparisons reflect design philosophy and capability — not benchmark scores. Every project here is genuinely useful; the question is which problems each one was designed to solve.

---

## The core distinction

Most AI coding tools are optimized for one thing: **how fast can the model produce a diff?**

tlmforge is optimized for a different thing: **how do you ensure that diff is correct, secure, and maintainable?**

These are compatible goals, not competing ones. tlmforge sits on top of Claude Code — it doesn't replace the model or the IDE. It adds the process layer that experienced engineering teams know matters: spec before code, independent review of plans, TDD enforcement, adversarial security review before ship.

---

## tlmforge vs. Claude Code (vanilla)

**What vanilla Claude Code gives you:** A capable coding assistant that writes code on demand. No structure, no enforcement, no review process.

**What that means in practice:** Claude will write code the moment you ask, skip specs if you don't ask for them, write tests after implementation if you don't remind it, and commit without any adversarial review. For a one-off script this is fine. For a 10,000-line production codebase, the lack of process accumulates into correctness debt.

**What tlmforge adds on top:**
- A classification gate before any code is written (Light / Medium / Deep)
- A mandatory spec audit for non-trivial work
- Phase-gated execution with independent agents at each gate
- TDD discipline enforced mechanically — the mutation hook fires before any Edit/Write/Bash
- An adversarial red-team reviewer as the last gate before commit
- A SHA anchor that blocks commits which drift past the final audit

**When vanilla Claude Code is enough:** Exploratory work, throwaway scripts, single-session tasks where correctness doesn't matter. tlmforge's bypass phrases (`be quick`, `just do it`, `trivial fix`) exist precisely for these cases.

---

## tlmforge vs. Aider

[Aider](https://github.com/paul-gauthier/aider) is one of the best open-source AI pair programmers available. It's battle-tested, supports many models, and has an excellent watch-mode for fast iteration.

**Where Aider excels:**
- Broad model support (not Claude-only)
- Mature git integration (auto-commits, smart diffs)
- Great for experienced developers who want fast iteration and stay in the loop
- Watch mode for rapid edit cycles

**Where tlmforge adds what Aider doesn't have:**
- Structured spec audit — Aider doesn't force you to write a spec before code
- Multi-agent review — Aider uses a single model; tlmforge routes work to 8 specialized agents at defined gates
- Phase-gated verification — Aider doesn't enforce that Phase N was verified before Phase N+1
- Adversarial review — no equivalent of the red-team-reviewer stage in Aider

**Honest take:** If you're prototyping and want the fastest possible iteration loop, Aider is excellent. If you're building something that will live in production and be maintained by a team, the process discipline tlmforge adds is worth the additional gates.

**Can they coexist?** Aider and tlmforge serve different parts of the workflow. You could use Aider for fast exploration and tlmforge for production-quality feature development — they don't step on each other.

---

## tlmforge vs. OpenHands (formerly OpenDevin)

[OpenHands](https://github.com/All-Hands-AI/OpenHands) is an open-source autonomous agent platform — the open-source answer to Devin-style fully automated development.

**OpenHands' design philosophy:** Maximize autonomy. Give the agent a task and let it run end-to-end: browse the web, write code, run tests, fix failures. Minimal human intervention.

**tlmforge's design philosophy:** Human-in-the-loop by design. Every non-trivial task gets a spec. Plans are reviewed and approved before implementation starts. Phases verify what they promised before the next phase begins.

**The tradeoff:**
- OpenHands trades verification for autonomy. Great for tasks where "mostly correct" is fine and you'll review the diff anyway.
- tlmforge trades autonomy for correctness. Adds gates that require human approval at key decision points.

**Where tlmforge differs concretely:**
- OpenHands has no concept of a spec audit — it writes code immediately
- OpenHands has no adversarial review stage — it doesn't deliberately try to break its own output
- OpenHands doesn't enforce TDD — tests may come after implementation or not at all
- OpenHands is model-agnostic; tlmforge is Claude Code-specific and uses Claude's subagent architecture

**Honest take:** OpenHands is impressive for autonomous task execution. tlmforge is a better fit for teams that want AI assistance within a professional software engineering process, not a replacement for that process.

---

## tlmforge vs. SWE-agent / Devin-style benchmark agents

[SWE-agent](https://github.com/SWE-agent/SWE-agent) and similar benchmark-oriented agents are designed to maximize performance on software engineering benchmarks (SWE-bench, HumanEval, etc.).

**What benchmark agents optimize for:** Solving isolated, well-specified tasks from a fixed test corpus. The input is a GitHub issue, the output is a passing test. Everything is judged by whether the tests pass.

**What real production development requires:**
- Writing the spec from ambiguous requirements (no pre-written issue)
- Making architectural decisions with long-term maintainability in mind
- Writing tests that genuinely catch bugs (not just pass)
- Coordinating across multiple phases of work
- Reviewing your own output adversarially before it ships

None of these are measured by benchmark scores.

**Where tlmforge is different:**
- tlmforge starts from an ambiguous task description, not a well-formed issue
- tlmforge produces a spec audit as the first artifact — it forces ambiguity resolution
- tlmforge uses independent reviewer agents rather than the same model checking its own work
- tlmforge doesn't optimize for any benchmark — it optimizes for shipping correct software in production

**Honest take:** SWE-bench is a useful proxy. It doesn't measure what matters to a real engineering team. tlmforge is designed for production development workflows, not benchmark performance.

---

## tlmforge vs. "more prompting"

A common alternative to structured tooling is "I'll just add process instructions to my system prompt." Write a big CLAUDE.md, ask Claude to write a spec first, remind it to write tests.

**Why this doesn't hold:**
- Instructions in a system prompt are suggestions. Claude will skip steps under time/context pressure.
- There's no mechanical enforcement. The mutation gate, the post-Stage-5 SHA lock, the approval-gate AskUserQuestion — these fire regardless of what Claude thinks it should do.
- Instructions don't produce verifiable artifacts. tlmforge produces `spec_audit.md`, `tester_edge_cases.json`, `phase-N-evidence.md`, `final_audit_red-team.json` — concrete audit trails you can read and diff.
- A system prompt doesn't spawn independent agents. The same model checking its own work doesn't catch the same bugs a fresh, cold-started reviewer would.

**What tlmforge does that prompting can't:** Mechanical enforcement via hooks, independent cold-started agents per role, SHA-anchored audit trail, convergence-bounded review loops, carryover artifacts that feed forward across stages.

---

## Summary

| If you want... | Use... |
|---|---|
| Fastest possible AI coding, any model | Aider |
| Fully autonomous task execution | OpenHands |
| Benchmark-validated AI code solutions | SWE-agent |
| AI-assisted dev within a professional process | **tlmforge** |
| Fast exploration, then production-grade delivery | Both Aider + tlmforge |

tlmforge doesn't try to be the fastest or the most autonomous. It's the only open-source tool that adds production-grade process discipline to AI-assisted feature development — spec audit, multi-agent review, TDD enforcement, adversarial audit — without requiring you to hire a team to enforce it manually.
