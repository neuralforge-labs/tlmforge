
## enforcement-hooks — 2026-05-15

- Surprise: Stage 5 red-team found C-1 (git ref as verdict_sha bypasses Hook 3) which looks like "nobody would do this" but requires only a one-line JSON edit — hex-only validation is the right default for any SHA field used in security logic; lesson: validate SHA format before passing to `git rev-parse`
- Pattern that worked: `@fail_open` with explicit `except SystemExit: raise` — zero session-bricking failures across all edge cases (empty repo, missing transcript, corrupt JSON)
- Pitfall avoided: regex `.match()` for gate hooks — use `.search()` when the full command string may contain the pattern after shell operators (`&&`, `;`)
- Surprise: the phase-auditor run (from a prior session) sat in the repo unread for 54 minutes — future features should read all agent results before declaring phase complete

## v058-validation — 2026-05-16

- Surprise: "add missing tests" looks like Medium but is actually Light — no behavior change, only verification. Lesson: always ask "does this change any existing behavior?" before classifying.
- Pattern that worked: `TestTDDRedPhase` with inline v0.5.7 fixture strings as a committed RED-phase record — avoids the "can't prove RED because files are already patched" problem.
- Pitfall avoided: row-scoped regex for absence assertions (`_medium_row()`) — global substring search would have passed even if "threat-modeler" only appeared in Deep rows, making the test useless as a revert guard.
- Pitfall avoided: pre-fix functional test that looked meaningful but was tautological (evaluate_convergence injects synthetic for ANY missing expected role, not just post-v0.5.8 ones). Caught by Stage 3 reviewers before implementation.
