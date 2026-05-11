# agent-hardening — Master Plan

## Context

tlmforge claims to enforce production-quality review through convergence loops and adversarial
agents. The infrastructure is mostly real — 4 Stop hooks, PreToolUse architect-reviewer,
`check_convergence.py` on disk. But three categories of gaps undermine the claim: agents that
can't physically write files (missing `Write` tool), paths that don't match (agents write to
`plans/`, convergence script looks in `specs/`), and a hook that lets "be quick" bypass TIER1
review unconditionally. This hardening closes all three.

Success: every reviewer writes a traceable artifact, convergence script finds what it needs,
and TIER1 changes with user overrides get LLM-assessed risk rather than a free pass.

## Scope

**In:**
- Fix `Write` + `Edit` missing from code-reviewer and ux-reviewer tools lists
- Fix `plans/` → `specs/` in threat-modeler, red-team-reviewer, reviewer-convergence.md
- Harden tester prompt: run real coverage, generate test stubs, write tester_coverage.md
- Harden code-reviewer prompt: file:line test gap table, write code_review.md artifact
- Harden ux-reviewer prompt: structured findings table with file:line refs, write ux_review.md
- Fix process-compliance hook: TIER1 detection before override check + LLM judgment (not LOC thresholds)
- Add per-phase lightweight re-review step to SKILL.md Stage 4 (blocks on CRITICAL + HIGH)
- Version bump plugin.json 0.3.0 → 0.4.0

**Out (explicitly):**
- No new hooks beyond adjusting the existing process-compliance one
- No changes to architect-reviewer, threat-modeler, red-team-reviewer prompts (beyond path fix)
- No changes to check_convergence.py
- No changes to the JSON schema or convergence thresholds

## Architecture

```
Before:
  code-reviewer (tools: Read/Grep/Glob/Bash)  →  prose output only, can't write file
  ux-reviewer   (tools: Read/Grep/Glob/Bash/WebSearch/WebFetch)  →  prose only
  threat-modeler  →  writes to plans/<f>/agent_verification/  →  NOT FOUND by convergence script
  red-team-reviewer  →  writes to plans/<f>/agent_verification/  →  NOT FOUND
  process-compliance hook: Step 4 (override check) → Step 5 (TIER1)  →  override wins always

After:
  code-reviewer (tools: Read/Grep/Glob/Bash/Write/Edit)  →  writes code_review.md + JSON
  ux-reviewer   (tools: Read/Grep/Glob/Bash/Write/Edit/WebSearch/WebFetch)  →  writes ux_review.md
  threat-modeler  →  writes to specs/<f>/agent_verification/  →  FOUND by convergence script
  red-team-reviewer  →  writes to specs/<f>/agent_verification/  →  FOUND
  process-compliance hook: Step 3 (TIER1 detect) → Step 4 (LLM risk judgment if TIER1+override)
                           → Step 5 (override fast-path, non-TIER1 only)

  Stage 4 (per-phase):
    4.1 phase-N-spec.md
    4.2 phase-N-verify.md
    4.3 Execute (TDD: RED→GREEN)
    4.4 phase-N-evidence.md
    4.5 phase-N-summary.md
    4.6 [NEW] Lightweight re-review: tester + code-reviewer on phase diff
        → phase-N-review.md  (blocks next phase on CRITICAL or HIGH)
```

## Sensitive surface inventory

| File | What changes |
|---|---|
| `tlmforge/agents/code-reviewer.md` | Frontmatter tools list + prompt (artifact writing, file:line gaps) |
| `tlmforge/agents/ux-reviewer.md` | Frontmatter tools list + prompt (structured output, artifact writing) |
| `tlmforge/agents/tester.md` | Prompt only (coverage run, test stubs, artifact writing) |
| `tlmforge/agents/threat-modeler.md` | Path strings only: plans/ → specs/ |
| `tlmforge/agents/red-team-reviewer.md` | Path strings only: plans/ → specs/ |
| `tlmforge/skills/feature-development/reviewer-convergence.md` | Path strings: plans/ → specs/ |
| `tlmforge/skills/feature-development/SKILL.md` | Add Stage 4.6 per-phase re-review step |
| `~/.claude/settings.json` | Process-compliance hook prompt reorder + LLM judgment logic |
| `~/dotfiles/claude/global/settings.json` | Mirror of above |
| `tlmforge/.claude-plugin/plugin.json` | Version bump 0.3.0 → 0.4.0 |

## Phases

### Phase 1 — Path fixes (plans/ → specs/)
**Goal:** Mechanical text replacement so agents write to the right directory.
**Files:** threat-modeler.md, red-team-reviewer.md, reviewer-convergence.md, skills/live-evaluator/SKILL.md, skills/property-test-generator/SKILL.md
**Verification grep (tightened):**
```bash
grep -rn "plans/<feature>" tlmforge/skills/ tlmforge/agents/ \
  | grep -v "plans/encryption" \
  | grep -v "dotfiles/claude/plans"
# must return 0 matches
```
**Historical carve-outs (do NOT change):** `plans/encryption/` references in REVIEW.md (historical worked example); `~/dotfiles/claude/plans/gold-standard-pickup` in reviewer-convergence.md line 313 (filesystem path to test suite).
**Rollback:** git revert, instant, no data risk

### Phase 2 — Add Write + Edit to agent tools lists
**Goal:** code-reviewer and ux-reviewer can now physically write files.
**Files:** code-reviewer.md (frontmatter), ux-reviewer.md (frontmatter)
**Tests:** grep confirms tools list includes Write and Edit in both files
**Rollback:** git revert, instant

### Phase 3 — Harden agent prompts (tester, code-reviewer, ux-reviewer)
**Goal:** Agents produce verifiable artifacts, not just prose.
**Files:** tester.md (prompt), code-reviewer.md (prompt), ux-reviewer.md (prompt)
**Tests:**
- Prompt grep: tester.md contains "tester_coverage.md" and "pytest --cov"
- Prompt grep: code-reviewer.md contains "code_review.md" and "file:line"
- Prompt grep: ux-reviewer.md contains "ux_review.md" and "File:line"
**Rollback:** git revert, instant

### Phase 4 — Fix process-compliance hook (TIER1 + LLM judgment)
**Goal:** TIER1 changes with "be quick" get LLM risk assessment, not a free pass.
**Files:** ~/.claude/settings.json, ~/dotfiles/claude/global/settings.json
**Tests:**
- Hook step order grep: TIER1 detection block appears before user override return
- Hook prompt contains "read the diff, understand what it actually does"
**Rollback:** git revert settings.json + dotfiles mirror, instant

### Phase 5 — Fix SKILL.md: per-phase re-review + remove always-on human gates
**Goal:** (a) Catch bugs per-phase before they compound. (b) Remove mandatory human-approval
sentinels that fire unconditionally — human gates should only fire when there are unresolved
questions requiring a product decision. Agents are the gate once intent is confirmed.

**Specific gate changes:**
- Stage 1→2 sentinel: only gate if spec audit contains CRITICAL open questions needing human
  input. If no blocking questions, proceed to Stage 2 automatically.
- Stage 2→3 sentinel: remove unconditional gate. If the plan was derived from a user-approved
  upstream plan (plan mode, prior conversation), proceed straight to Stage 3. Only gate if
  the plan introduces decisions the user hasn't seen.
- Stage 3→4: already agent-gated (SUMMARY.md + zero CRITICALs). No change needed.
- Irreversible operations (prod deploy, migration execution): KEEP the human gate. These are
  the only places it belongs.

**Files:** SKILL.md
**Tests:**
- grep: SKILL.md contains "phase-N-review.md" and "Lightweight phase re-review"
- grep: SKILL.md Stage 1 gate is conditional ("only if CRITICAL open questions")
- grep: SKILL.md Stage 2 gate is conditional ("only if new decisions not previously approved")
- grep: SKILL.md contains "CRITICAL or HIGH" blocking language for per-phase re-review
**Rollback:** git revert, instant

### Phase 6 — Version bump + CHANGELOG
**Goal:** Signal to marketplace users that an update is available. Note tool permission changes explicitly.
**Files:** `.claude-plugin/plugin.json`
**Tests:** `python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert d['version']=='0.4.0'"`
**Migration note in CHANGELOG:** Users with in-flight Stage 3/5 iterations that wrote JSON sidecars to `plans/<feature>/agent_verification/` will need to `cp -r plans/<feature>/agent_verification/ specs/<feature>/agent_verification/` before resuming.
**Rollback:** git revert, instant

### Phase 7 — Marketing content (blog + LinkedIn + Twitter/X)
**Goal:** Articulate tlmforge's unique positioning for public launch.
**Output files** (in `tlmforge/marketing/`):
- `blog-post.md` — full-length technical blog post: the problem (humans in the quality loop), the design (convergence enforcement, adversarial pair at design vs impl time, TDD stop hooks), comparison vs gstack, real-world what-it-looks-like walkthrough
- `linkedin-post.md` — narrative post: "I built a plugin that removes the human from the code review loop without removing quality. Here's how."
- `twitter-thread.md` — 8-10 tweet thread: hook, problem, solution, differentiators, CTA
- `positioning.md` — one-liner, tagline, elevator pitch, 3 competitor comparisons (gstack, Karpathy rules, nothing)

**Core message across all:** You state intent once. From there, adversarial agents own correctness — convergence-enforced, not trust-based. Nothing ships until all agents agree. That's not a copilot. That's a quality gate.

**No rollback needed** — purely additive output files

## Risk audit

| Risk | Severity | Mitigation |
|---|---|---|
| Hook rewrite breaks existing non-TIER1 behavior | MEDIUM | Steps 5-7 of hook unchanged; only TIER1 path adds new logic before existing steps |
| Prompt changes make agents produce different output format | LOW | Additions only; no existing instructions removed |
| `plans/` references in legacy `specs/encryption/` artifacts | LOW | reviewer-convergence.md §5 already says legacy dirs are read-only historical — not touched |
| SKILL.md Stage 4.6 makes Claude forget to run it | LOW | Explicit step with blocking language; will be caught by process-compliance hook if skipped |

## Decisions made

- **LLM judgment instead of LOC thresholds (F2):** The process-compliance hook runs as an LLM
  agent. It should read the diff and reason about actual production impact, not count lines.
  One-line auth bypass = dangerous. 200-line spelling fix = harmless. Thresholds can't express
  this distinction; LLM judgment can.
- **Edit added alongside Write (F1):** Needed for iterative re-runs where agents append to
  existing SUMMARY.md files rather than creating new ones.
- **Per-phase re-review blocks on CRITICAL + HIGH (F3):** HIGH findings in phase N will compound
  in phase N+1. Block early to prevent debt accumulation.

## TDD plan

All phases are documentation/prompt/config changes. Tests are `grep` assertions confirming the
right content was written. No executable unit tests — the changes are text content in markdown
and JSON files.

| Phase | Test file | What it verifies |
|---|---|---|
| All phases | Manual grep commands in phase-N-verify.md | Content presence in modified files |

## Verification criteria

1. `grep -r "plans/<feature>/agent_verification" tlmforge/agents/ tlmforge/skills/` returns 0 matches
2. `code-reviewer.md` and `ux-reviewer.md` tools lists include `Write` and `Edit`
3. `tester.md` prompt includes coverage run command and `tester_coverage.md` write step
4. `code-reviewer.md` prompt includes file:line test gap table and `code_review.md` write step
5. `ux-reviewer.md` prompt includes findings table with file:line and `ux_review.md` write step
6. Process-compliance hook: TIER1 detection block appears before user override fast-path
7. Process-compliance hook: contains LLM judgment instruction for TIER1 + override cases
8. `SKILL.md` contains per-phase re-review step (4.6) with `phase-N-review.md` output
9. `plugin.json` version is `0.4.0`
