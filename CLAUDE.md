## Feature-Development Skill — MANDATORY (not optional)

**Read this first. The Stop-hook process audit will reject your completion if you violate it.**

For ANY task that creates/modifies ≥3 source files, OR touches production code paths (`backend/memx_app/`, `memx-ui-v2/lib/`, anything called `*_migration*`, `*_schema*`, anything under `scripts/encryption/`, `scripts/kms/`), OR involves data migration/schema/auth/encryption/PII, OR matches keywords in the user's request (add / build / implement / migrate / refactor / enforce / fix-multi-file / ship / make-X-work) — you MUST invoke `Skill(tlmforge:feature-development)` BEFORE any Edit/Write/Bash-mutation tool call.

The feature-development skill (tlmforge plugin: `tlmforge:feature-development`) is the canonical 7-stage recipe (spec audit → master plan → multi-agent review → phase-gated TDD → re-review → live verification → operator tooling). Skipping it means: no audit trail, no independent review, no rollback path.

**To bypass for genuinely small/quick work:** the user must explicitly say "be quick" / "minimal" / "just do it" / "trivial fix" in their prompt. You cannot self-classify as Light/Minimal — only the user's explicit phrasing unlocks that.

**Auto Mode does NOT override this.** Auto Mode permits autonomous execution within the rules; this rule is part of the rules.

If you're unsure whether a task qualifies, default to invoking the skill. The cost of an unnecessary invocation is 5 minutes of plan; the cost of a skipped invocation is hours of rework.

## Directory Convention

**Spec/plan directory:** Always use `specs/` (not `plans/`) for all feature specs, plans, and audit docs. Each repo has its own `specs/` directory at its root.
