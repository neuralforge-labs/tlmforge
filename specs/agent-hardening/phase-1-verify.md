# Phase 1 — Verification Plan

## Pre-flight
| Check | Command | Pass criteria |
|---|---|---|
| Confirm stale refs exist before fix | `grep -rn "plans/<feature>" tlmforge/agents/ tlmforge/skills/ \| grep -v "plans/encryption" \| grep -v "dotfiles/claude/plans"` | Non-zero matches (confirms there's work to do) |

## Post-implementation
| Check | Command | Pass criteria |
|---|---|---|
| No stale agent refs | `grep -rn "plans/<feature>" tlmforge/agents/ \| grep -v "plans/encryption"` | 0 matches |
| No stale skill refs | `grep -rn "plans/<feature>" tlmforge/skills/ \| grep -v "plans/encryption" \| grep -v "dotfiles/claude/plans"` | 0 matches |
| Historical refs intact | `grep -c "plans/encryption" tlmforge/skills/feature-development/REVIEW.md` | ≥1 (unchanged) |
| threat-modeler writes to specs/ | `grep "specs/<feature>/agent_verification" tlmforge/agents/threat-modeler.md` | 2 matches |
| red-team-reviewer writes to specs/ | `grep "specs/<feature>/agent_verification" tlmforge/agents/red-team-reviewer.md` | 2 matches |
