## Feature-Development Skill — MANDATORY (not optional)

**Read this first. The enforcement hooks will block mutations if you violate it.**

For ANY task beyond a trivial one-liner (typo, single rename, config value change
with zero behavioral impact) — you MUST invoke `Skill(tlmforge:feature-development)`
BEFORE any Edit/Write/Bash-mutation tool call.

The skill auto-classifies at Stage 0 and proceeds immediately. Do NOT ask the user
to confirm intensity — announce it in one sentence ("Going Medium — [reason]") and
start. The user can say "go deeper" or "go lighter" to adjust.

**To bypass for genuinely trivial work:** include "be quick" / "just do it" /
"trivial fix" in the prompt. These signal Light/Minimal — the skill exits at Stage 0.

**Auto Mode does NOT override this.** Auto Mode permits autonomous execution within
the rules; this rule is part of the rules.

## Directory Convention

**Spec/plan directory:** Always use `specs/` (not `plans/`) for all feature specs, plans, and audit docs. Each repo has its own `specs/` directory at its root.
