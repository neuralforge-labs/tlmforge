# agent-hardening — Spec Audit

## What the user asked for

Harden tlmforge's agent definitions and process-compliance hook so the claimed convergence
enforcement is actually delivered. Specifically: agents must produce verifiable artifacts
(not just prose), the tester must check real coverage, the UX reviewer must write structured
findings to the specs dir, and the process-compliance hook must not let a large TIER1 change
bypass review with "be quick."

## Industry standard / how others do this

- **Google code review:** LGTM requires all review comments addressed. Security changes require
  an additional security reviewer sign-off. Review comments are tracked in Critique (not prose
  that disappears after the session).
- **Meta (Facebook):** Phabricator diffs require acceptance from all "blocking" reviewers.
  Test plans are written in the diff description and verified by CI. Coverage gates block merge.
- **Amazon:** PRs require automated coverage report + two reviewer approvals. Security-sensitive
  changes need AppSec team review regardless of size.
- **Common pattern:** Reviewers produce structured, addressable comments that are tracked to
  resolution — not prose that gets forgotten. Coverage is a number, not an assessment.

## Findings (severity-ranked)

### CRITICAL — Decisions needed before any code

#### F1. `code-reviewer` and `ux-reviewer` cannot write files — tools list missing `Write`

- **Spec said:** "Code-reviewer must produce file:line test gap table, write artifact" and
  "UX reviewer must write findings table to specs dir"
- **Industry standard:** Reviewers write structured findings to a persistent location that
  the convergence script can read
- **Problem:** `code-reviewer` has `tools: Read, Grep, Glob, Bash`. `ux-reviewer` has
  `tools: Read, Grep, Glob, Bash, WebSearch, WebFetch`. Neither includes `Write` or `Edit`.
  Any prompt instruction to "write to specs/" will silently fail — the agent will describe
  what it would write but cannot actually write it.
- **Recommendation:** Add `Write` (and `Edit`) to both agents' tools lists
- **Decision required:** Should `Edit` also be added? (Needed to append to existing files like
  SUMMARY.md in iterative re-runs)

#### F2. Process-compliance hook: user override check (Step 4) fires BEFORE TIER1 check (Step 5)

- **Spec said:** For TIER1 paths with large changes, "be quick" should not bypass
- **Industry standard:** Security-critical changes require review regardless of developer
  preference (Amazon AppSec, Google Security review)
- **Problem:** The hook's step ordering is: Step 4 (user override → return ok) then Step 5
  (TIER1 fast-path). Step 4 unconditionally returns `{ok: true}` if any override keyword is
  present, without checking TIER1 or scope. A 200-LOC payment flow rewrite + "be quick" = ok.
- **Recommendation:** Reorder: detect TIER1 first, then apply the proportional LOC/file-count
  threshold before checking user override. Only allow override if change is small (≤2 files,
  ≤50 LOC) even on TIER1 paths.
- **Decision required:** Thresholds: ≤2 source files AND ≤50 LOC for TIER1 + override = allow?

#### F3. Per-phase lightweight re-review is described but has no defined output schema

- **Spec said:** "After each Phase 4 phase completes, run tester and code-reviewer against
  the phase diff, write phase-N-review.md"
- **Problem:** The skill's Stage 4 section has no mention of a per-phase re-review step.
  Without an explicit slot in Stage 4 (e.g., after step 4.4), Claude will skip it. The output
  format (phase-N-review.md) also needs a template so it's consistently structured.
- **Recommendation:** Add a step 4.6 in Stage 4: "Lightweight phase re-review" with explicit
  instructions to run tester + code-reviewer against `git diff HEAD~1..HEAD` and write
  `phase-N-review.md`
- **Decision required:** Should this lightweight re-review block the next phase on CRITICAL
  only, or on HIGH as well?

### HIGH — Should fix before shipping

#### F4. `plans/` vs `specs/` path inconsistency breaks convergence script

- **Problem:** `threat-modeler.md` writes to `plans/<feature>/agent_verification/`.
  `red-team-reviewer.md` writes to `plans/<feature>/agent_verification/`. `reviewer-convergence.md`
  instructs the orchestrator to collect JSON from `plans/<feature>/agent_verification/`. But
  the SKILL.md and CLAUDE.md both use `specs/<feature>/agent_verification/`. The convergence
  script (`check_convergence.py`) reads from whichever path the orchestrator passes it — if
  the orchestrator says `specs/` but agents write to `plans/`, the JSON files are never found
  and convergence permanently fails with `reviewer_json_missing` synthetics.
- **Recommendation:** Replace all `plans/<feature>/` with `specs/<feature>/` in
  threat-modeler.md, red-team-reviewer.md, and reviewer-convergence.md
- **No decision needed:** This is a clear bug

#### F5. Tester agent: coverage instructions missing; no artifact write step in the prompt

- **Problem:** The tester prompt tells Claude to find edge cases but never instructs it to
  run the test suite, read coverage output, or generate test stubs. A tester that says
  "you should add a test for X" produces no traceable artifact. The convergence script can't
  differentiate "tester reviewed and found nothing critical" from "tester reviewed cursorily."
- **Recommendation:** Add explicit steps to the tester's prompt: (1) run test suite + coverage,
  (2) report actual numbers, (3) generate test stubs for CRITICAL/HIGH gaps as code (not
  description), (4) write `tester_coverage.md` in addition to `tester_review.md`
- **Note:** Tester already has `Write` in tools — this is a prompt-only change

#### F6. UX reviewer: no structured output, no per-finding file:line

- **Problem:** UX reviewer currently produces prose. "Consider improving contrast" cannot be
  verified as fixed. The convergence script expects a JSON sidecar from every reviewer, but
  the UX reviewer prompt never mentions writing JSON or even writing to a file. In Stop hook
  mode (no specs/ context), there's no fallback output location either.
- **Recommendation:** Add structured output instructions (findings table with component,
  file:line, violation, severity, fix) and a mandatory `ux_review.md` write step. In Stop hook
  mode, write to `.tmp/ux_review/` as fallback.
- **Blocked by F1:** Tools list must include `Write` first

### MEDIUM

#### F7. `reviewer-convergence.md` gem path reference may also be stale

- **Problem:** `reviewer-convergence.md` line 236 shows the gemini script invocation using
  `plans/<feature>/agent_verification/gemini_review.json`. This will produce a file in the
  wrong directory.
- **Recommendation:** Fix in the same batch as F4

#### F8. Phase-N-review.md write in Stop hook mode (no specs/ context)

- **Problem:** The per-phase re-review (F3) runs inside Stage 4 where specs/ exists. But
  tester and code-reviewer also run as Stop hooks (outside Stage 4). If the per-phase re-review
  instructions are added to Stage 4, they won't affect Stop hook mode. The two flows need to
  stay cleanly separated.
- **Recommendation:** The per-phase re-review in Stage 4 explicitly cites `specs/<feature>/`
  context. Stop hook mode uses `.tmp/` as fallback. No cross-contamination.

### LOW

#### F9. No version bump in plugin.json after these changes

- These are behavioral changes to agents that users have installed. Bumping the version signals
  the marketplace that an update is available.
- **Recommendation:** Bump `plugin.json` version (0.3.0 → 0.4.0) after all changes land

## Open questions for the user

1. **F1:** Should `Edit` be added to code-reviewer and ux-reviewer tools in addition to `Write`?
   (Edit is needed for appending to existing SUMMARY.md in iterative re-runs)
2. **F2:** Confirm TIER1 + override thresholds: ≤2 source files AND ≤50 LOC = allow with warning?
3. **F3:** Per-phase re-review: block next phase on CRITICAL only, or CRITICAL + HIGH?
