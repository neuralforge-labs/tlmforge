# Why process discipline matters more as codebases grow

This document explains the design philosophy behind tlmforge — why it works the way it does, and what problem it actually solves.

---

## The speed trap

AI coding tools make the first 20% of a feature trivial. You describe what you want, the model writes it, the tests pass, you ship. Velocity is high.

The problem shows up at 50%, 70%, 90% of the codebase. The model writes code that looks correct but violates an invariant it doesn't know about. It skips a test because the task felt simple. It adds a shortcut that works now but creates a security hole in three months. It makes an architectural decision that conflicts with a decision made three features ago.

None of this is the model's fault. The model doesn't have memory across sessions. It doesn't know your codebase's implicit invariants. It doesn't know which shortcuts are safe and which ones will bite you. And it certainly doesn't know to be adversarial about its own output.

The solution isn't a smarter model. The solution is process.

---

## What process actually means

Senior engineers don't write better code because they're smarter. They write better code because they've internalized a process:

1. Understand the requirement fully before writing anything
2. Consider edge cases, failure modes, and security implications upfront
3. Design before implementing
4. Get independent review on the design
5. Write tests before implementation
6. Verify that each piece does what it claimed before building on top of it
7. Have an adversary look for what you missed

This isn't bureaucracy. Every step exists because someone got burned without it. Specs catch misunderstood requirements before a week of implementation is thrown away. Independent review catches architecture mistakes that the author is too close to see. Tests written before implementation actually test the right thing. Adversarial review finds the security bug you rationalized away.

AI coding tools, by default, skip all of this. tlmforge adds it back — mechanically, not as suggestions.

---

## Why mechanical enforcement matters

You could write instructions in your CLAUDE.md telling Claude to write a spec first. Claude will do this most of the time. Under time pressure, in a long session, when the task feels trivial — it'll skip it.

tlmforge's hooks don't care about context. The mutation gate fires before every Edit/Write/Bash call, regardless of session length or how simple the task seems. The post-Stage-5 SHA lock doesn't check whether the task was "probably fine." The convergence check doesn't accept "I think the reviewers would have approved this."

Mechanical enforcement is the only kind that holds at the margins. The margins are where the bugs live.

---

## Why independent agents, not the same model

The core insight behind tlmforge's multi-agent architecture: **the model that wrote the code has the same blind spots as the model that reviews it.**

A single model reviewing its own architecture will justify the same shortcuts it made when building it. A single model reviewing its own tests will consider them complete if they match its own mental model of correctness.

tlmforge uses cold-started, purpose-specific agents:

- The `threat-modeler` doesn't know what the implementation looks like yet — it reviews the plan with fresh eyes from a security-adversary perspective
- The `phase-auditor` has one job: does the evidence match the promise? It doesn't know or care whether the implementation was elegant
- The `red-team-reviewer` is explicitly framed as an adversary looking for ways to break the system — a frame the implementation agent never takes

Different framings catch different bugs. This is why code review exists in software teams. tlmforge brings the same principle to AI-assisted development.

---

## Why three intensity levels

Process discipline has a cost: time, tokens, context. Applying the full 7-stage Deep recipe to a typo fix is absurd.

tlmforge's classification gate exists to make the cost proportional to the risk:

- **Light** — the main agent handles it inline. Zero subagent spawns. The discipline is still there (TDD, self-review checklist) but no external agents fire.
- **Medium** — abbreviated spec audit, single-round review, phase-end verification. ~13–15 subagent spawns.
- **Deep** — full recipe. ~30–40 spawns, 1 Opus invocation for the adversarial pass.

The classifier is semantic, not keyword-based. "Add a type annotation" is Light even if it touches an auth file. "Change the session expiry logic" is Deep even if it's one line. The model judges the work, not the filename.

The escape hatches (`be quick`, `TLMFORGE_HOOKS=0`) exist because legitimate urgent work happens. The bypass is there when you need it. It's not the default.

---

## What tlmforge doesn't try to be

**It's not autonomous.** tlmforge is explicitly human-in-the-loop. Approval gates at Stage 1→2 and Stage 3→4 require your sign-off before implementation starts. You're in control of the decisions; the agents review and advise.

**It's not a benchmark optimizer.** tlmforge doesn't optimize for SWE-bench scores or HumanEval pass rates. It optimizes for correctness and maintainability in production codebases over time.

**It's not a replacement for engineers.** The reviewer agents produce findings; you decide which findings to act on. The escalation paths (ESCALATION.md, FINAL_ESCALATION.md) always end with a human decision. tlmforge automates the process, not the judgment.

---

## The design principles

1. **Spec before code** — no implementation until the feature request is analyzed and a plan exists
2. **Independent review** — cold-started agents with specific framings, not the same model checking itself
3. **TDD enforcement** — tests first, mechanical, with RED→GREEN verification
4. **Phase gates** — each phase proves what it promised before the next begins
5. **Bounded loops** — review rounds have a hard cap; escalation paths handle the rest
6. **Proportional cost** — Light/Medium/Deep classification prevents over-engineering the process itself
7. **Mechanical enforcement** — hooks that fire regardless of context, not instructions that get skipped
8. **Honest escalation** — when something can't converge, tlmforge says so and asks you to decide, rather than pretending it converged
