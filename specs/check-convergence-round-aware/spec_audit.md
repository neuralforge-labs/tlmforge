# check-convergence-round-aware — Spec Audit

## What the user asked for

Update `check_convergence.py` to handle the round-aware filename conventions
introduced in tlmforge 0.5.0 (lean review architecture).

The 0.5.0 redesign produces JSON sidecars under stage-aware paths:

- Stage 3 plan review (3-round bounded loop):
  `specs/<feature>/agent_verification/round-{1,2,3}-<role>.json`
- Stage 4 phase-end verification:
  `specs/<feature>/phase-N-verification/<role>.json` (round 1)
  `specs/<feature>/phase-N-verification/round-{2,3}-<role>.json` (if iterating)
- Stage 5 dual single-shot final audit:
  `specs/<feature>/agent_verification/final_audit_<role>.json`

The current script `evaluate_convergence(reviewer_jsons, expected_roles, iteration, max_iterations)`
is filename-agnostic — it takes already-loaded JSON dicts. The change therefore
has two parts:
1. **Filename-loading helpers**: convenience functions that load reviewer JSON
   from the new round-aware paths into the dict shape `evaluate_convergence`
   already accepts.
2. **Stage-specific orchestrators**: thin wrappers that capture the per-stage
   expected_roles + single-shot vs iterative semantics. Stage 5 in 0.5.0 is
   single-shot dual (red-team + architect) — fundamentally different from the
   prior `evaluate_stage5_two_tier`'s iterating tier-1+tier-2 model.

This is a dogfood test of the lean review architecture. Beyond shipping the
code, every Stage 1–7 artifact in this spec dir is verification that the
0.5.0 SKILL.md flow works end-to-end.

## Industry standard / how others do this

- **Pytest discovery model:** convention-over-config — fixed naming
  patterns (`test_*.py`, `Test*` classes) discovered by directory scan.
  tlmforge's round-aware paths follow this pattern: stable conventions,
  no config file required to locate artifacts.
- **CI orchestrators (GitHub Actions, Buildkite):** matrix builds produce
  per-job artifacts at well-defined paths (`artifacts/<job>/<step>.json`).
  Aggregation jobs glob those paths to roll up status. tlmforge's
  convergence rule is the equivalent aggregator.
- **JSON Schema validation (jsonschema lib):** load-then-validate is the
  established pattern. We already validate via `review_schema.json`. No
  change needed there.
- **Anthropic's internal review hook patterns:** I don't have detailed
  prior art on their structure beyond what's public in Claude Code docs.

## Findings (severity-ranked)

### CRITICAL — Decisions needed before any code

#### F1. No test coverage exists for `check_convergence.py` today
- **Spec said:** "handle the new round-aware filenames" — implies adding
  behavior to the script.
- **Industry standard:** modifying any production-impact utility without
  test coverage is a process violation. The script is load-bearing for
  the entire review flow.
- **Problem:** Today `find ... -name "test_*convergence*"` returns empty.
  Both the original `evaluate_convergence` and the obsolete
  `evaluate_stage5_two_tier` ship without unit tests. Adding new round-loading
  helpers without first pinning the existing behavior with tests means we
  can't tell regression from intended change.
- **Recommendation:** Phase 1 of the implementation MUST be "characterization
  tests for existing behavior" — pin current `evaluate_convergence` behavior
  (synthetic injection on missing JSON, meta vs real CRITICAL counting,
  lazy-empty handling, cap-hit messaging) with unit tests BEFORE adding
  new code. Otherwise we're changing behavior we don't know.
- **Decision required:** [INFORMATIONAL] — addressed in plan; no user
  decision needed.

#### F2. Plugin marketplace cache is on 0.3.0; 0.5.0 SKILL.md changes not yet active for users
- **Spec said:** "0.5.0 produces round-aware filenames" — implies the
  redesigned flow is live.
- **Industry standard:** plugin version bumps propagate via marketplace
  refresh; some plugin systems auto-pull on session start, others require
  explicit reload. Claude Code's behavior here is "cache at
  `~/.claude/plugins/cache/<plugin>/<version>/...`, refreshed on
  marketplace pull."
- **Problem:** The Skill invocation in THIS session loaded the OLD 0.3.0
  recipe text from `~/.claude/plugins/cache/tlmforge/tlmforge/0.3.0/`,
  not the 0.5.0 changes I pushed yesterday. Until a marketplace refresh
  / plugin reinstall picks up 0.5.0, end users of the plugin are still
  on the old unbounded-convergence flow even though the repo says 0.5.0.
- **Recommendation:** This is OUT OF SCOPE for the convergence-script
  update, but MUST be flagged as a deferred follow-up. The right fix is
  "publish the 0.5.0 release to the marketplace; verify cache picks it
  up; add a sanity check in CI that the version in plugin.json matches
  the version in the SKILL.md docstring or some other static marker."
  Captured in Stage 7 STATUS.md.
- **Decision required:** [INFORMATIONAL] — out of scope here, flagged
  for follow-up.

### HIGH — Should fix before merge

#### F3. `evaluate_stage5_two_tier` is now obsolete (Stage 5 is single-shot dual in 0.5.0)
- **Spec said:** new flow has Stage 5 = 2 agents single-shot, no iteration.
- **Industry standard:** when behavior changes, either keep the old API
  with deprecation warning OR remove it entirely. Half-keeping is the
  worst — it ships dead code that future readers won't know is dead.
- **Problem:** The current function models tier-1+tier-2 iteration with
  a shared counter, "iteration 3.5" semantics, requires_user_override
  logic. None of that maps to 0.5.0 Stage 5 (single shot, no iteration,
  CRITICALs → `FINAL_ESCALATION.md`).
- **Recommendation:** Replace with a new `evaluate_stage5_dual(red_team_json,
  architect_json)` function. Keep `evaluate_stage5_two_tier` as a wrapper
  that raises `DeprecationWarning` and delegates to the new function with
  a compatibility shim (or removes if no in-tree callers).
- **Decision required:** [INFORMATIONAL] — Phase 3 of plan.

#### F4. Round-aware path loading needs an ATOMIC scan to avoid mid-write reads
- **Spec said:** load round-1/2/3-<role>.json for the current iteration.
- **Industry standard:** filesystem-based artifact stores need either (a)
  atomic write via `.tmp` + `mv` (already documented in
  reviewer-convergence.md §6) OR (b) a producer-consumer barrier
  (sentinel file, manifest).
- **Problem:** If `evaluate_convergence` is called WHILE a reviewer is
  still writing its JSON, `json.load` could see a partial file. The
  atomic-write contract exists but is enforced at the reviewer side, not
  on the loader. A defensive loader should handle malformed JSON
  gracefully — treat it as missing-file → synthetic
  `reviewer_json_missing`.
- **Recommendation:** Loader wraps `json.load` in try/except (catching
  `json.JSONDecodeError` AND `OSError`). On failure, fall through to the
  same path as "file absent" — synthetic meta CRITICAL gets injected by
  `evaluate_convergence` already.
- **Decision required:** [INFORMATIONAL] — Phase 2 of plan.

#### F5. Round-3 escalation path needs an `evaluate_round` helper that returns the right action
- **Spec said:** "round 3 unresolved → ESCALATION.md + ask user."
- **Industry standard:** the convergence rule should emit a structured
  action recommendation (`{action: "advance" | "retry" | "escalate"}`)
  rather than only the boolean `converged` + a user_message string. The
  caller (SKILL.md orchestration in main Claude's reasoning) decides
  what to do based on the action.
- **Problem:** Current `evaluate_convergence` returns `converged: bool`
  and a free-text `user_message`. The "advance to round N+1 vs escalate
  to user" decision is implicit in the message text — fragile, requires
  caller-side regex.
- **Recommendation:** Add `action: "advance" | "retry" | "escalate"` to
  the return dict. `advance` when converged. `retry` when not converged
  and iteration < max_iterations. `escalate` when cap_hit (iteration >=
  max_iterations) AND not converged.
- **Decision required:** [INFORMATIONAL] — Phase 2 of plan.

### MEDIUM

#### F6. tester_edge_cases.json is a new carryover artifact, not a review sidecar — must NOT be counted toward convergence
- **Problem:** The new flow has tester producing TWO artifacts at Stage
  3 round 1: `round-1-tester.json` (review sidecar) + `tester_edge_cases.json`
  (carryover for Stage 4). The loader must NOT confuse the carryover for
  a missing review sidecar.
- **Recommendation:** Loaders glob ONLY `round-{N}-<role>.json` and
  `final_audit_<role>.json`. The carryover artifact has a distinct name
  (`tester_edge_cases.json`) — it's safely excluded by the glob pattern.
  Document this in a comment.
- **Decision required:** [INFORMATIONAL]

#### F7. Phase-end round paths are nested differently than Stage 3 paths
- **Problem:** Stage 3 round-N files live in `agent_verification/`. Phase-end
  round-N files live in `phase-N-verification/`. A naive loader that just
  globs `agent_verification/round-*-*.json` won't find phase-end artifacts.
- **Recommendation:** Two distinct helpers: `load_stage3_round_jsons(feature_dir, round_n)`
  and `load_phase_end_round_jsons(feature_dir, phase_n, round_n)`. They
  share an internal `_load_json_safely(path)` helper for the I/O.
- **Decision required:** [INFORMATIONAL]

#### F8. ux-reviewer is conditional — how does the loader handle "expected but skipped"?
- **Problem:** ux-reviewer fires at Stage 3 only when the plan describes
  UI, and at Stage 4 phase-end only when UI files are in the phase diff.
  When NOT firing, no JSON is produced — and that's correct, not a missing
  file.
- **Recommendation:** The loader accepts an explicit `expected_roles` list
  from the caller (current behavior). The CALLER decides whether to
  include ux-reviewer in expected_roles based on the feature scope. If
  ux-reviewer is in expected_roles but the JSON is absent, that IS an
  error (`reviewer_json_missing` fires correctly). If ux-reviewer is NOT
  in expected_roles, no error. This is already the right design — needs
  explicit documentation only.
- **Decision required:** [INFORMATIONAL]

### LOW

#### F9. Backwards-compat naming for in-flight features mid-rollout
- **Problem:** Features started under 0.4.0 may have JSON sidecars at
  the OLD flat path (`agent_verification/<role>_review.json`). If the
  same feature continues into 0.5.0 territory mid-roll-out, the loader
  would miss them.
- **Recommendation:** This is an OPERATIONAL concern (manual file
  renaming during migration) not a code concern. Document in CHANGELOG
  (already done in 0.5.0 release notes). No special-case code in the
  loader.
- **Decision required:** [INFORMATIONAL]

## Coverage of mandatory surfaces

- **(a) Security surface (auth, secrets, injection, IDOR, PII):** N/A —
  pure utility script reading local JSON files. No network calls, no
  credentials, no user input handling beyond filesystem paths derived
  from the spec dir. The only injection concern is a malformed JSON
  file producing unexpected dict shapes — handled by F4's defensive
  loader recommendation.
- **(b) Concurrency / race conditions / idempotency:** Already addressed
  in F4. The atomic-write contract on writers + defensive read on this
  loader together provide safety. No locks needed (single-reader pattern;
  the loader is called once per iteration by main Claude's orchestration).
- **(c) Failure modes under partial failure:** Addressed in F4 (malformed
  JSON), F6 (correct artifact discrimination), F7 (path nesting), F8
  (conditional reviewer). Cap-hit messaging (F5's `escalate` action) is
  the partial-success path.
- **(d) Cost impact:** Zero — local script, no API calls. The actual
  cost lever is REDUCING reviewer agent spawns, which the 0.5.0 redesign
  already addresses upstream of this code.
- **(e) Rollback safety / blast radius:** Highest. Single Python file
  edit, no schema changes, no DB. Rollback: `git revert` the commit.
  Existing callers (zero in-tree per `grep` audit) wouldn't break because
  we're keeping the original `evaluate_convergence` signature and only
  ADDING new helpers + new Stage 5 function. The deprecated
  `evaluate_stage5_two_tier` becomes a no-op wrapper.

## Open questions for the user

(None — this is a dogfood test with pre-confirmed Deep scope and explicit
"no clarifying questions" directive. All open questions are marked
[INFORMATIONAL] above and resolved within the plan.)

## Dogfood-test findings already surfaced

These are findings about the 0.5.0 redesign itself, surfaced by attempting
to invoke its skill in a fresh session:

- **DF1 [HIGH]:** Plugin marketplace cache held an OLD copy of SKILL.md
  (v0.3.0) even after session restart. The Skill tool loaded the cached
  v0.3.0 recipe text, not the 0.5.0 redesign I pushed to GitHub. Captured
  in F2 above. Requires marketplace publish + cache refresh as separate
  follow-up.

- **DF2 [INFORMATIONAL]:** `~/.claude/skills/feature-development/` has its
  own copy of `check_convergence.py` that's byte-identical to the
  plugin's. Unclear if this is a manual user copy, an auto-mirror, or
  stale. Edits to the plugin's copy may or may not propagate. Flag for
  follow-up: clarify which copy is canonical and whether the duplicate
  should be removed or auto-synced.
