# Round 2 Fixes — enforcement-hooks

## NF1 (CRITICAL — architect-reviewer, also flagged by tester + threat-modeler)

**Finding:** Hook 1 `systemMessage` reminder text still listed "minimal" and
"trivial" as valid bypass phrases. The override library was correctly updated
by EC-5 to reject bare "minimal"/"trivial". A user following Hook 1's own
instructions would be silently blocked by Hook 2.

**Fix:** Phase 1 reminder text updated to list only `["be quick", "just do it",
"trivial fix"]`. Added parenthetical: "Bare 'minimal' / 'trivial' are NOT
accepted — they appear too often in technical prose."

## NF2 (MEDIUM — tester — NEW-2; also WARNINGS from architect)

**Finding:** Active-feature marker file read in Phase 3 implementation was not
explicitly anchored to repo root. When Claude runs from a subdirectory, reading
`specs/.tlmforge_active_feature` without path resolution fails silently → Hook 3
concludes no active feature → PSR gate skipped.

**Fix:** Phase 3 implementation steps now call `git rev-parse --show-toplevel`
FIRST (single call at top of hook), then use `<repo_root>/specs/.tlmforge_active_feature`
for the marker read AND `<repo_root>/specs/<feature>/agent_verification/` for
the glob. The redundant second `--show-toplevel` call in the glob step removed.
`test_hook3_cwd_subdirectory.py` description updated to cover both marker + glob.

## Stale references (architect WARNINGS)

- Verification Criteria "`.claude-plugin/hooks.json`" → "`hooks/hooks.json` at plugin root"
- Verification Criteria "Stage 5b post-commit subsection" → "PSR (post-Stage-5 re-review) subsection + active-feature marker steps"

## NOT fixed

**LOW (threat-modeler) — fail-open warning only to stderr, not stdout.**
Intentional: Hook 1 emits to stdout (systemMessage); Hook 2/3 deny via exit(2)
to stderr; crash-path warning to stderr only. Emitting warning to stdout would
pollute the systemMessage channel and could confuse Claude. Deferred to
tlmforge:doctor (Phase 6).
