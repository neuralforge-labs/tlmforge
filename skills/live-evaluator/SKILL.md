---
name: live-evaluator
description: |
  Use this skill in Stage 6 of feature-development to perform live verification with a
  fresh-context, skeptical-QA-framed agent — separate from the implementer that wrote
  the code. Triggers on "live verify this", "evaluate this end-to-end", "QA this against
  the deployed environment", or via feature-development Stage 6 launch. Forces evaluation
  to come from an adversarial reviewer, not the praised-by-its-author implementer.

  Output: a verification report at `plans/<feature>/E2E_VERIFICATION.md` with reproducible
  commands, observed evidence, and a pass/fail per acceptance criterion.
---

# Live evaluator — fresh-context skeptical QA

The implementer's context is full of "I just made this work" — they're optimistic about
what works. Stage 6 verification needs an adversarial perspective from a reviewer that
DIDN'T write the code. This skill defines that pattern.

## When to use

**Triggers:**
- feature-development Stage 6 ("Live verification + operator tooling")
- User says "live verify this" / "QA this against the deployed env"
- After deploying a feature to a staging/canary environment, before promoting to prod

**When NOT to use:**
- Unit / integration test verification — that's Stage 4 / Stage 5 territory
- Pure code review — code-reviewer / red-team-reviewer handle that
- Smoke tests on synthetic features — direct execution is fine; this skill is for real-environment verification

## How it works

The skill is launched via `Agent(subagent_type="general-purpose", model="sonnet", ...)` with
a fresh context (the launch prompt is self-contained — no prior conversation history).
Inside the prompt:

1. **Skeptical-QA framing** ("you are a skeptical QA engineer; assume every check is wrong
   until you've reproduced it yourself") — counteracts implementer-praises-own-work bias.
2. **Acceptance criteria** are listed verbatim from `plans/<feature>/STATUS.md` or
   `phase-N-spec.md`'s "Verification criteria" section.
3. **Tool-use plan** — the agent uses Bash for backend (`curl`, `pytest`, log greps) and
   Playwright MCP for UI (clicks the actual UI, validates rendered output) when configured.
4. **Evidence capture** — every "yes this works" claim must be backed by a captured
   command output, screenshot, or DB row.

The output goes to `plans/<feature>/E2E_VERIFICATION.md` with the exact commands and
observed responses, so a future operator can reproduce.

## Launch prompt template

When feature-development Stage 6 fires (or when the user asks for live verification):

```
You are a SKEPTICAL QA engineer. You did not write this code. Your job: verify
acceptance criteria from the deployed environment, capturing reproducible
evidence for each check.

Feature path: plans/<feature>/
Acceptance criteria: <paste from STATUS.md / phase-N-spec.md>
Deployed environment: <URL / namespace / staging vs prod>
Tools you have: Bash (curl, pytest, log greps), [Playwright MCP if configured]

Procedure for each criterion:
1. State what success looks like (pin the exact expected output / behavior)
2. Run the command / click the UI element to test it
3. Capture the evidence (command output, screenshot, DB row)
4. State PASSED / FAILED with the captured evidence inline
5. If FAILED, do NOT attempt to fix — surface the failure with reproduction steps

Adversarial framing: assume every "expected" claim is wrong until you've
reproduced it yourself. The implementer is optimistic; you are not.

Save your verification report to: plans/<feature>/E2E_VERIFICATION.md

Format:
  # <Feature> — Live Verification

  Verified by: live-evaluator (general-purpose, sonnet, fresh context)
  Environment: <env>
  Date: <ISO 8601>

  ## Criterion 1: <description>
  Expected: <pin the exact behavior>
  Command: <exact reproducible command>
  Observed:
  ```
  <captured output>
  ```
  Verdict: PASSED / FAILED

  ## Criterion 2: ...

  ## Summary
  N/M criteria passed. Failures: <list>.
```

## Why this matters (research-backed)

- Anthropic's [harness-design post](https://www.anthropic.com/engineering/harness-design-long-running-apps)
  explicitly flags implementer-praises-own-work bias as a Stage-6 hazard: "the evaluator
  must be tuned separately… to avoid confidently praising work."
- [Verdent's SWE-bench report](https://www.verdent.ai/blog/swe-bench-verified-technical-report)
  shows separating evaluator from generator measurably increases bug-catch rate on real
  codebases.

## Playwright MCP integration (if available)

If the user has Playwright MCP configured in `~/.claude/settings.json`, the live-evaluator
can click UI elements directly:

```
For UI criteria, use the Playwright MCP tools:
  - playwright__navigate(url) → load the page
  - playwright__click(selector) → interact
  - playwright__screenshot(name) → capture evidence
  - playwright__assert_visible(selector, expected_text) → check rendered output
```

Without Playwright MCP, the skill falls back to:
- `curl` for API endpoints
- "verify the page renders correctly" handed back to the user with explicit reproduction steps

## Calibration discipline

- **Don't fix bugs you find.** Surface them. Stage 6 is verification, not implementation. If
  the user wants the bug fixed, they re-engage Stage 4.
- **Capture evidence inline.** Don't just say "tests pass" — paste the output. Reviewers of
  the audit trail need to see the receipts.
- **One criterion at a time.** Don't batch "verify all 5 criteria" — go through them serially
  with explicit pass/fail per criterion. Helps the user identify exactly what failed.
- **Stop on environment errors.** If the deployed environment is broken (500s, missing
  service), stop and report — don't try to verify against a broken env.

## Output checklist

The E2E_VERIFICATION.md is "done" when:

- [ ] Every acceptance criterion has Expected / Command / Observed / Verdict
- [ ] Evidence is captured INLINE (not just referenced as "see logs")
- [ ] Environment is named (staging vs prod, namespace, version SHA)
- [ ] Failures are surfaced WITHOUT being fixed
- [ ] A summary line shows N/M passed
