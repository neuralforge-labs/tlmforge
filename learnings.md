
## enforcement-hooks — 2026-05-15

- Surprise: Stage 5 red-team found C-1 (git ref as verdict_sha bypasses Hook 3) which looks like "nobody would do this" but requires only a one-line JSON edit — hex-only validation is the right default for any SHA field used in security logic; lesson: validate SHA format before passing to `git rev-parse`
- Pattern that worked: `@fail_open` with explicit `except SystemExit: raise` — zero session-bricking failures across all edge cases (empty repo, missing transcript, corrupt JSON)
- Pitfall avoided: regex `.match()` for gate hooks — use `.search()` when the full command string may contain the pattern after shell operators (`&&`, `;`)
- Surprise: the phase-auditor run (from a prior session) sat in the repo unread for 54 minutes — future features should read all agent results before declaring phase complete
