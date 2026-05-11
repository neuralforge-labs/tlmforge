# Tester review — agent-hardening plan (iteration 1)

Reviewer: tester (opus)
Scope: edge cases and failure modes in the master plan and spec audit BEFORE any code is
written. Source files read:

- $REPO_ROOT/specs/agent-hardening/README.md
- $REPO_ROOT/specs/agent-hardening/spec_audit.md
- $REPO_ROOT/agents/tester.md
- $REPO_ROOT/agents/ux-reviewer.md
- $REPO_ROOT/skills/feature-development/reviewer-convergence.md
- $REPO_ROOT/skills/feature-development/SKILL.md (Stage 4 region)
- $REPO_ROOT/skills/feature-development/check_convergence.py
- $REPO_ROOT/skills/feature-development/ai_review_json.sh

Cross-checked `plans/` references repo-wide.

## VERDICT: FIX BEFORE SHIPPING

The plan is largely sound, but six concrete failure modes will cause production bugs unless
addressed in the phase docs before code is written. Most relate to undefined behavior at
the boundary between "Stage 4 context" and "Stop hook context," plus latent `plans/`
references the plan undercounts.

---

## Findings (severity-ranked)

### CRITICAL

#### EC-1 — Per-phase re-review `git diff HEAD~1..HEAD` is the wrong baseline

- **Trigger**: Phase 1 lands as a single commit. Phase 2 begins. At end of Phase 2,
  Stage 4.6 runs `git diff HEAD~1..HEAD`. But Phase 2 produced MULTIPLE commits
  (phase-2-spec, phase-2-verify, impl commits, phase-2-evidence, phase-2-summary — per
  SKILL.md §4.2 which mandates verify and evidence as distinct commits). `HEAD~1..HEAD`
  reviews only the LAST commit (the summary doc), missing the actual impl diff. Worse:
  if the previous phase's last commit was from a DIFFERENT feature (Phase 1 of feature B
  interleaved during long-running feature A), `HEAD~1..HEAD` spans a feature boundary and
  reviews unrelated code.
- **What happens**: Tester/code-reviewer in Stage 4.6 review the wrong diff. Phase summary
  doc has no real code changes — they return "no findings" trivially. CRITICAL bugs in the
  actual phase implementation slip through. The "block next phase on CRITICAL/HIGH"
  contract is silently violated because no CRITICAL is ever found.
- **Impact**: Silent failure of the entire per-phase gate. The plan's headline new
  control becomes decorative.
- **Fix**: The per-phase re-review must diff against a phase-boundary marker, not
  `HEAD~1`. Two options, pick one in phase-5-spec.md:
  (a) Tag/record the SHA at phase start in `phase-N-state.md` frontmatter (already exists
  per reviewer-convergence.md §9 — `git_sha:`). Re-review diffs against
  `<phase-N-start-sha>..HEAD`.
  (b) Use `git merge-base` against a known feature-start SHA recorded in
  `specs/<feature>/README.md` frontmatter.
  Option (a) is already half-built; prefer it.
- **Test**: Add a test (or grep assertion) in phase-5-verify.md that the Stage 4.6
  instruction text in SKILL.md contains `phase-N-start` or equivalent boundary anchor
  language, NOT `HEAD~1..HEAD`. Also: a smoke test that simulates two interleaved
  features and asserts the diff scope is correct.

#### EC-2 — Tester `pytest --cov` instruction crashes on non-Python projects and on Python projects without pytest-cov installed

- **Trigger**: tlmforge plugin is consumed by a user whose project is JS/TS/Flutter/Go,
  or by a Python project where `pytest-cov` is not in the venv. Stage 4.6 launches tester.
  tester.md prompt (after Phase 3 hardening) instructs Bash `pytest --cov=<pkg>`.
- **What happens**: Bash exits non-zero. The tester agent has no fallback path defined in
  the plan. The agent either (a) emits `status: "error"` (which the convergence script
  treats as a synthetic CRITICAL — see check_convergence.py L23, blocks convergence
  forever), or (b) emits no JSON, triggering `reviewer_json_missing` synthetic CRITICAL.
  Either way: the feature blocks at phase 1 on projects that aren't Python+pytest+coverage.
- **Impact**: The tester becomes a hard requirement for a specific toolchain.
  tlmforge is published to a marketplace; this breaks every non-Python adopter.
- **Fix**: Phase-3 prompt for tester must include detection-and-graceful-degrade:
  1. Detect runner (pytest? jest? flutter test? go test?) by reading `pyproject.toml`,
     `package.json`, `pubspec.yaml`, `go.mod`.
  2. If no recognized runner: emit `status: "ok"` with a `category: "test_coverage"`
     finding at severity `medium` ("No test runner detected — coverage skipped"),
     NOT a CRITICAL and NOT `status: "error"`.
  3. If runner exists but coverage tool missing (e.g. pytest but no pytest-cov):
     run tests without coverage, report counts only, finding at severity `low`
     ("Coverage tool not installed — counts-only report"). Still `status: "ok"`.
  4. Only `status: "error"` if the test suite itself crashes unexpectedly.
- **Test**: phase-3-verify.md must include a smoke test where tester is launched against
  a JS project and a Python-without-pytest-cov project. Both must produce
  `status: "ok"` JSON and convergence must succeed.

#### EC-3 — code-reviewer / ux-reviewer in Stop hook mode have no `specs/<feature>/` to write to

- **Trigger**: User edits a file outside any feature flow (e.g. a hotfix on main). The
  Stop hook fires code-reviewer. Phase 3 hardening tells code-reviewer "write
  code_review.md" — but there is no `specs/<feature>/agent_verification/` directory
  because no feature is in flight.
- **What happens**: Three possible bad outcomes, all undefined in the plan:
  (a) Agent picks a wrong feature directory (most recent `specs/*/` it finds) and
      pollutes that feature's audit trail with unrelated review output.
  (b) Agent uses `Write` against a path that doesn't exist; `Write` errors; agent
      retries with arbitrary fallbacks; randomness ensues.
  (c) Agent writes to `./code_review.md` at repo root, leaving litter every Stop hook.
- **Impact**: Audit trail corruption (worst), repo litter (mild). Either way the
  artifact-writing contract is meaningless because the orchestrator can't find the file.
- **Fix**: Phase 3 prompt MUST specify Stop-hook fallback explicitly:
  - If invoked inside Stage 4 (env or CWD contains active feature spec): write to
    `specs/<feature>/agent_verification/<role>_review.md`.
  - Otherwise (Stop hook): write to `.tmp/<role>_review/<timestamp>.md` (the F8
    recommendation in spec_audit.md — make it normative, not advisory). Same for JSON
    sidecar. Convergence script never reads `.tmp/`, so no contamination risk.
  - Detection rule must be explicit and deterministic (e.g., env var
    `TLMFORGE_FEATURE_DIR` set by the orchestrator). Do NOT rely on "most recent specs
    dir" heuristics — they are racy and wrong on multi-feature repos.
- **Test**: phase-3-verify.md grep: code-reviewer.md and ux-reviewer.md prompts both
  contain a "Stop hook fallback: .tmp/" block. Smoke test: invoke code-reviewer with no
  feature context, assert artifact lands under `.tmp/` and not under `specs/`.

---

### HIGH

#### EC-4 — Stage 1→2 conditional gate: "no blocking questions" is a Claude-side classification with no verifier

- **Trigger**: Spec audit contains an ambiguous open question (e.g. "should we use JWT or
  session cookies?"). Claude reads it, decides it's not "CRITICAL," skips the gate,
  proceeds to Stage 2, picks JWT, writes the plan, builds the code. User wanted sessions.
- **What happens**: Misclassification is silent. The user never sees the question. By
  the time they read the master plan, the decision is already encoded. The "saves time
  on trivial features" benefit pays for itself in occasional but expensive misalignment.
- **Impact**: Quiet drift from user intent. Worst on critical/auth/payment paths — the
  exact paths where the human gate matters most.
- **Fix**: The condition must be a HARD structural check, not an LLM judgment:
  - Spec audit's "Open questions for the user" section must use a tagged format:
    `[GATE-BLOCKING]` or `[INFORMATIONAL]` per question.
  - Stage 1→2 gate fires if ANY question is tagged `[GATE-BLOCKING]`.
  - Claude must default to `[GATE-BLOCKING]` when in doubt (asymmetric safety: false
    positive = 1 extra round-trip; false negative = wasted feature work).
  - Additional structural rule: if the spec audit mentions any TIER1 keyword (auth,
    payment, encryption, PII, migration, IAM, RBAC, token, password), Stage 1 gate fires
    unconditionally regardless of question tags.
- **Test**: phase-5-verify.md grep: SKILL.md Stage 1→2 gate language includes
  `[GATE-BLOCKING]` and the TIER1-keyword override. Add a Python unit test against a
  helper function `should_stage1_gate(audit_text) -> bool` so the rule is testable
  without LLM-in-the-loop.

#### EC-5 — Stage 2→3 conditional gate: "previously approved upstream plan" has no auditable marker

- **Trigger**: User has an offhand conversation about feature X, no plan mode invoked.
  Claude generates a master plan in Stage 2 that includes new decisions the user did not
  see. Stage 2→3 condition says "skip if derived from user-approved upstream plan."
  Claude self-classifies "yes, the user mentioned X earlier" and skips.
- **What happens**: Same drift risk as EC-4. Worse: there is no on-disk artifact proving
  the upstream plan was approved.
- **Impact**: Same as EC-4. The "human gate when there are new decisions" promise is
  unenforceable.
- **Fix**: Require an on-disk approval artifact: `specs/<feature>/UPSTREAM_APPROVAL.md`
  with frontmatter containing source (ExitPlanMode hash / chat turn id / prior PR URL) and
  the user's literal approval phrase. If absent, the gate fires. This makes
  "previously approved" verifiable, not asserted.
- **Test**: phase-5-verify.md: grep for `UPSTREAM_APPROVAL.md` requirement in SKILL.md
  Stage 2 gate text.

#### EC-6 — `plans/` references remain in `skills/live-evaluator/SKILL.md` and `skills/property-test-generator/SKILL.md`

- **Trigger**: Plan scope (README.md §Scope) lists only threat-modeler, red-team-reviewer,
  and reviewer-convergence.md for path fixes. Phase 1 grep test:
  `grep -r "plans/<feature>/agent_verification" tlmforge/agents/ tlmforge/skills/`
  excludes these files because they reference `plans/<feature>/E2E_VERIFICATION.md` and
  `plans/<feature>/STATUS.md` — NOT `agent_verification/`.
- **What happens**: After the plan ships, users invoking the `live-evaluator` or
  `property-test-generator` skills are told to write reports to `plans/<feature>/`
  but tlmforge's actual convention (per CLAUDE.md and SKILL.md) is `specs/<feature>/`.
  Reports land in a directory that doesn't exist or in a directory the orchestrator
  never reads. Repeat of the F4 bug, just in different skills.
- **Impact**: Reintroduces the exact bug Phase 1 is meant to fix, just outside the
  audited surface. Future feature-development runs that compose `live-evaluator` for E2E
  verification will silently lose the verification report.
- **Fix**: Expand Phase 1 scope to include:
  - `skills/live-evaluator/SKILL.md` (4 references)
  - `skills/property-test-generator/SKILL.md` (3 references)
  - `skills/feature-development/REVIEW.md` (3 references — these are historical
    references to `plans/encryption/` and should be kept as-is per existing legacy-dir
    policy; document the carve-out explicitly so phase verification grep doesn't fail).
  - `skills/feature-development/reviewer-convergence.md` line 274: `plans/<feature>/phase-N-state.md`
    is missed by current scope description (only §3 mentions are listed).
  - `skills/feature-development/reviewer-convergence.md` line 313:
    `~/dotfiles/claude/plans/gold-standard-pickup/phase-1/tests/` is a historical filesystem
    path — keep as legacy reference, document carve-out.
- **Test**: phase-1-verify.md grep must be tightened:
  `grep -rn "plans/<feature>" tlmforge/skills/ tlmforge/agents/ | grep -v "plans/encryption" | grep -v "dotfiles/claude/plans"`
  returns 0 matches.

---

### MEDIUM

#### EC-7 — Stage 4.6 blocks on CRITICAL+HIGH but tester routinely emits HIGH findings on legitimate work-in-progress

- **Trigger**: Phase 1 implements core schema; phase 2 adds the API layer. At end of
  phase 1, tester finds "no API tests yet — HIGH." Stage 4.6 blocks phase 2. But phase 2
  IS the API layer; the finding will resolve naturally.
- **What happens**: False-positive blocking. The user is forced to either suppress the
  finding (corrupting the audit trail) or write throwaway API tests for code that
  doesn't exist yet.
- **Impact**: Stage 4.6 produces friction proportional to the size of the feature.
  Multi-phase features become unworkable.
- **Fix**: The per-phase re-review prompt must explicitly scope findings to "what is
  IN this phase's diff," not "what is missing from the codebase overall." Add to phase-3
  hardening of tester.md: "When invoked in per-phase mode (Stage 4.6), report only on
  code WITHIN the phase diff. Cross-phase gaps (tests for code that doesn't exist yet)
  are EXPECTED and must be `severity: low` with `category: meta`, not HIGH."
- **Test**: phase-3-verify.md grep tester.md contains "per-phase mode" and
  "WITHIN the phase diff."

#### EC-8 — code-reviewer instructed to use `Write` may overwrite an in-progress code_review.md from a concurrent Stop hook

- **Trigger**: User edits file A, Stop hook fires code-reviewer (call 1). Before call 1
  finishes, user edits file B, Stop hook fires again (call 2). Both target the same
  `code_review.md` path (Stop hook fallback or Stage 4.6 file). `Write` overwrites.
- **What happens**: Findings from call 1 are lost. Audit trail incomplete.
- **Impact**: Silent data loss in reviewer output. Convergence script reads whichever
  write finished last.
- **Fix**: Phase 3 prompt for code-reviewer must use atomic-write contract
  (already documented in reviewer-convergence.md §6: write `.tmp` then `mv`) AND a
  timestamp/PID suffix for Stop hook mode so concurrent invocations don't collide:
  `.tmp/code_review/<iso-timestamp>-<pid>.md`. The Stop hook's own consumer (if any)
  reads the most-recent file by mtime.
- **Test**: phase-3-verify.md asserts code-reviewer.md prompt contains "atomic write" and
  Stop-hook timestamped path.

---

### LOW

#### EC-9 — Phase 6 version bump doesn't update the schema_version field

- **Trigger**: Phase 6 bumps `plugin.json` to 0.4.0. Reviewer JSON schema_version is
  pinned at "1.0" in reviewer-convergence.md §1. New reviewers (post-hardening) produce
  schema_version: "1.0" the same as old reviewers, but their `category` enum values may
  differ if any new categories were added.
- **What happens**: No immediate failure. But the version-bump signal is meaningless for
  detecting reviewer-output format compatibility.
- **Impact**: Future migration pain if the schema actually changes. Not a Phase-6 bug
  per se.
- **Fix**: Out of scope for this hardening, but document in phase-6-spec.md that
  schema_version is intentionally NOT bumped (no schema changes in this hardening).

---

## Plan strengths (edge cases properly handled)

- F4 path-consistency fix correctly identifies the primary three files
  (threat-modeler, red-team-reviewer, reviewer-convergence.md). The convergence script
  itself is path-agnostic (verified by reading `check_convergence.py` — paths are passed
  as args, no hardcoded `plans/`). Same for `ai_review_json.sh` — uses `--output` arg.
  So Phase 1 fix does close the orchestrator-side path; the gap is only in OTHER skills
  (EC-6 above).
- Phase ordering (path fix → tools → prompts → hook → SKILL → version) respects
  dependencies: hardening prompts that reference Write must wait for Write to be in the
  tools list (F1 → F5/F6).
- Risk audit row "Hook rewrite breaks existing non-TIER1 behavior" correctly identifies
  the dominant risk of the Phase 4 hook change.
- Adding `Edit` alongside `Write` (F1 decision) is correct — iterative re-runs need
  append, not overwrite.

---

## Missing tests (must be added to phase-N-verify.md files)

1. **Phase 1**: Tighten the grep test to cover `live-evaluator` and `property-test-generator`
   skills, with explicit carve-outs for `plans/encryption/` and `~/dotfiles/claude/plans/`
   historical references. (EC-6)
2. **Phase 3 (tester.md)**: Add smoke tests for non-Python projects, Python-without-
   pytest-cov projects, and crashing-test-suite case. Assert each produces correct
   `status` and severity, NOT a hard error. (EC-2)
3. **Phase 3 (code-reviewer.md, ux-reviewer.md)**: Smoke test launching each agent
   outside any feature flow; assert artifact lands under `.tmp/` not `specs/`. (EC-3)
4. **Phase 3 (tester.md, code-reviewer.md)**: Grep that the prompts include explicit
   "per-phase mode" scoping language; smoke test that cross-phase gaps are not HIGH. (EC-7)
5. **Phase 3 (code-reviewer.md)**: Grep for atomic-write + timestamped path under
   `.tmp/`. (EC-8)
6. **Phase 5 (SKILL.md Stage 4.6)**: Grep that re-review instruction uses a
   phase-boundary anchor (NOT `HEAD~1..HEAD`). Smoke test simulating a multi-commit phase
   to assert the full phase diff is reviewed. (EC-1)
7. **Phase 5 (SKILL.md Stage 1 gate)**: Grep for `[GATE-BLOCKING]` tag protocol and the
   TIER1-keyword unconditional override. Unit test of a `should_stage1_gate()` helper. (EC-4)
8. **Phase 5 (SKILL.md Stage 2 gate)**: Grep for `UPSTREAM_APPROVAL.md` requirement. (EC-5)

---

## Recommended phase additions

- **New Phase 1b** (or expanded Phase 1): include `live-evaluator/SKILL.md` and
  `property-test-generator/SKILL.md` path fixes. Document the legacy carve-outs.
- **New Stage 4.6 design doc** in `specs/agent-hardening/`: a one-page note on the
  phase-boundary SHA anchor approach (using `phase-N-state.md` `git_sha:` frontmatter),
  so Phase 5 implementation has a clear target.
