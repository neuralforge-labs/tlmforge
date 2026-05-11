# Phase 1 — Path fixes (plans/ → specs/)

## Goal
Replace all `plans/<feature>/` path references with `specs/<feature>/` in agent and skill files.
This closes the gap where agents write JSON sidecars to `plans/` but the convergence script
and orchestrator look in `specs/`.

## Scope
**In:** path string replacement only — no logic changes
**Out:** historical references (`plans/encryption/`, `~/dotfiles/claude/plans/`) — leave untouched

## Files to be modified
- `tlmforge/agents/threat-modeler.md` — lines 134, 137 (agent_verification paths)
- `tlmforge/agents/red-team-reviewer.md` — lines 185, 186 (agent_verification paths)
- `tlmforge/skills/feature-development/reviewer-convergence.md` — multiple refs (§2, §3, §6, §9)
- `tlmforge/skills/live-evaluator/SKILL.md` — ~5 refs to plans/<feature>/
- `tlmforge/skills/property-test-generator/SKILL.md` — ~3 refs to plans/<feature>/

## Tests to be added
None — verification via grep assertion below.

## Verification criteria
- [ ] `grep -rn "plans/<feature>" tlmforge/skills/ tlmforge/agents/ | grep -v "plans/encryption" | grep -v "dotfiles/claude/plans"` returns 0 matches
- [ ] `grep -n "plans/<feature>" tlmforge/agents/threat-modeler.md` returns 0 matches
- [ ] `grep -n "plans/<feature>" tlmforge/agents/red-team-reviewer.md` returns 0 matches

## Rollback
`git revert HEAD` — instant, no data risk
