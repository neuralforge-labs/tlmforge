# enforcement-hooks — Master Plan

## Context

tlmforge ships a 7-stage feature-development discipline today, but the
discipline depends on Claude (or the user) **remembering** to invoke the
skill at the right moments. In practice, two failure modes recur:

1. **Skill never invoked at all.** A new user installs tlmforge, types
   "add a button to send messages," and Claude proceeds without ever
   loading SKILL.md. The discipline doesn't run.
2. **Skill invoked but ignored mid-task.** Claude declares "Stage 5 GATE
   OPEN" at SHA X, then ships 4 more substantive commits at SHAs Y/Z
   that no auditor sees. LL-1 / LL-8 violated. (Real example pasted by
   the user from another session.)

This feature builds the **structural enforcement layer** that makes
both failure modes mechanically impossible. Three hooks plus a SKILL.md
tightening. The hooks are the gate; the skill is the recipe; together
they remove the "remember to do it" load from both Claude and the user.

## Scope

**In:**
- 3 new hook scripts under `hooks/`:
  - `load_feature_dev_skill.py` (UserPromptSubmit)
  - `enforce_skill_invoked.py` (PreToolUse on Edit, Write, Bash)
  - `enforce_post_stage5_review.py` (PreToolUse on Bash matching git/gh)
- 1 shared lib under `hooks/_lib/`: transcript scan, override detection,
  marker file IO, fail-open wrapper
- `hooks/hooks.json` at plugin root — wires the hooks (`.claude-plugin/`
  contains only `plugin.json`; hooks live in `hooks/`)
- `specs/.tlmforge_active_feature` marker file — written by skill at Stage 1
  start, cleared at Stage 7; Hook 3 reads this to scope its glob
- SKILL.md updates (in two phases): Phase 3 partial (Stage 5 prompt template
  `verdict_sha` instruction + PSR workflow); Phase 4 full (Stage 0 early-exit,
  LL-6 wire-test, active-feature marker steps)
- `tester.md` agent prompt update (the LL-6 wire-test rule)
- `final_audit` JSON schema update: `verdict_sha:` field (required)
- `hooks/tests/fixtures/skill_invocation_sample.jsonl` — real Skill
  tool-call JSONL record captured from a live session (Phase 0)
- Hook tests under `hooks/tests/`
- README install section: hook behavior, override phrases,
  `TLMFORGE_HOOKS=0` env var (sole bypass)
- CHANGELOG 0.5.5 entry

**Out (explicitly):**
- `tlmforge:doctor` slash command (deferred — F13, Phase 6 if pulled in)
- Telemetry / opt-in metrics (out of scope; separate decision)
- Hook-shipped paid product features (out of scope)
- Auto-classification by keyword (explicitly REJECTED per
  `feedback-no-keyword-classifiers`)
- Refactoring `check_convergence.py` (deferred to its own spec)

## Threat model / requirements / constraints

The "threat model" frame here is **discipline integrity**, not
adversarial security (per `feedback-threat-model-calibration` —
single-user CLI tool, no external attackers).

What we're defending against:
- Claude (or user) forgetting to invoke the skill on a Deep task
- Claude bypassing its own discipline mid-task ("Stage 5 done" then 4
  more commits)
- Silent enforcement failure (hook crashes, hook silently passes)

What we're NOT defending against:
- Malicious user forging skill invocations to evade the gate (single-user
  tool; the user is not the threat)
- Malicious code in the user's repo manipulating hook state
- Adversarial reading of the transcript file

Constraints:
- Hooks must be FAIL-OPEN (a crashing hook must not brick the session)
- PreToolUse hooks must be sub-50ms p99 (else every Edit gets slow)
- No keyword classification anywhere in hook logic (per saved feedback)
- Override mechanism must be discoverable and easy to invoke
- Must work on a fresh `claude plugin add` install with zero manual setup

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Claude Code session                                              │
│                                                                   │
│  ┌─────────────────┐                                              │
│  │ User types      │                                              │
│  │ "add encryption"│                                              │
│  └────────┬────────┘                                              │
│           │                                                       │
│           ▼                                                       │
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  Hook 1: UserPromptSubmit                                  ║  │
│  ║  load_feature_dev_skill.py                                 ║  │
│  ║                                                            ║  │
│  ║  • Always emits the same system-reminder:                  ║  │
│  ║    "Invoke Skill(tlmforge:feature-development) before     ║  │
│  ║     responding. Skill's classification gate is             ║  │
│  ║     authoritative for Light vs Deep AND for whether       ║  │
│  ║     this is even a work request."                          ║  │
│  ║  • No keyword logic. No conditional injection.             ║  │
│  ║  • Honors TLMFORGE_HOOKS=0 (sole bypass; no CI auto-detect).║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                              │
│  │ Claude reads    │   ──► Sees the reminder, invokes the skill. │
│  │ injected ctx    │       Skill loads SKILL.md (~6-8K tokens,   │
│  │ + user prompt   │       cached after first load in session).   │
│  └────────┬────────┘                                              │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                              │
│  │ Skill Stage 0   │   ──► (NEW) "Is this a work request at all?" │
│  │ no-op detector  │       If conversational/exploratory: exit    │
│  └────────┬────────┘       cleanly, no further ceremony.          │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                              │
│  │ Skill Stage 1+  │   ──► Classification gate, spec audit, etc. │
│  └────────┬────────┘                                              │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────┐                                              │
│  │ Claude attempts │                                              │
│  │ Edit / Write /  │                                              │
│  │ Bash mutation   │                                              │
│  └────────┬────────┘                                              │
│           │                                                       │
│           ▼                                                       │
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  Hook 2: PreToolUse[Edit, Write, Bash]                     ║  │
│  ║  enforce_skill_invoked.py                                  ║  │
│  ║                                                            ║  │
│  ║  Reads transcript_path from stdin (empirically verified   ║  │
│  ║  in Phase 0). Falls back to marker-file if absent.        ║  │
│  ║  Scans for:                                                ║  │
│  ║    A) Skill(tlmforge:feature-development) tool-call shape ║  │
│  ║       since last user msg (window verified via fixture).   ║  │
│  ║  If no user msgs (subagent session): pass-through.        ║  │
│  ║    B) Override phrase in LAST user message only:          ║  │
│  ║       ["be quick", "just do it", "trivial fix"]           ║  │
│  ║       (bare "minimal"/"trivial" removed — false positives) ║  │
│  ║                                                            ║  │
│  ║  If A or B: pass-through (allow mutation).                 ║  │
│  ║  Else: DENY — sys.exit(2) + stderr block message.        ║  │
│  ║                                                            ║  │
│  ║  Honors TLMFORGE_HOOKS=0 (also "false","no","off","").   ║  │
│  ║  Fails open on crash.                                      ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
│           │                                                       │
│           ▼ (if Bash and command matches git/gh patterns)        │
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  Hook 3: PreToolUse[Bash] matcher: git commit/push, gh    ║  │
│  ║  enforce_post_stage5_review.py                             ║  │
│  ║                                                            ║  │
│  ║  Triggers on tool_input.command matching:                  ║  │
│  ║    ^(git commit|git push|gh pr merge)                      ║  │
│  ║                                                            ║  │
│  ║  Reads specs/.tlmforge_active_feature → scopes glob to   ║  │
│  ║  specs/<feature>/agent_verification/final_audit_*.json.  ║  │
│  ║  Uses git rev-parse --show-toplevel for repo root.        ║  │
│  ║  Normalizes verdict_sha to 40 chars before compare.       ║  │
│  ║  Checks HEAD returncode (exit 128 = no commits → allow).  ║  │
│  ║                                                            ║  │
│  ║  If verdict_sha AND HEAD != verdict_sha AND no PSR marker ║  │
│  ║  (final_audit_*_psr_<HEAD>.json, SHA validated internally):║  │
│  ║    BLOCK via sys.exit(2) + stderr:                        ║  │
│  ║    "Stage 5 verdict at SHA X. HEAD is Y (N commits).     ║  │
│  ║     Run red-team+architect on `git diff X..HEAD`, write  ║  │
│  ║     final_audit_*_psr_<HEAD>.json, then re-push."        ║  │
│  ║                                                            ║  │
│  ║  Override: ["be quick","just do it","trivial fix"].       ║  │
│  ║  Honors TLMFORGE_HOOKS=0 (also "false","no","off","").   ║  │
│  ║  Fails open on crash; git errors: WARNING + pass-through. ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Sensitive surface inventory

Every component the change touches:

- `hooks/load_feature_dev_skill.py` — NEW
- `hooks/enforce_skill_invoked.py` — NEW
- `hooks/enforce_post_stage5_review.py` — NEW
- `hooks/_lib/transcript.py` — NEW (parse Claude Code transcript JSONL)
- `hooks/_lib/overrides.py` — NEW (override phrase detection)
- `hooks/_lib/safe.py` — NEW (fail-open wrapper)
- `hooks/_lib/env.py` — NEW (TLMFORGE_HOOKS=0 bypass, multi-value)
- `hooks/_lib/__init__.py` — NEW
- `hooks/tests/` — NEW (pytest scaffold + fixtures)
- `hooks/tests/fixtures/skill_invocation_sample.jsonl` — NEW (real Skill call)
- `hooks/hooks.json` — NEW (at plugin root, alongside `.claude-plugin/`)
- `.claude-plugin/plugin.json` — version bump 0.5.4 → 0.5.5
- `skills/feature-development/SKILL.md` — Stage 0 added; Stage 5b extended;
  Stage 4.5 tester wire-test rule added
- `agents/tester.md` — wire-test requirement (LL-6) explicit
- `skills/feature-development/review_schema.json` — `verdict_sha` field
  added to final_audit schema
- `README.md` — install section, hook behavior, override docs
- `CHANGELOG.md` — 0.5.5 entry

Every Claude Code session with tlmforge installed will run the new hooks.
A bug in any hook is felt by every user.

## Phases

Each phase is independently shippable and reversible. The plan favors
small phases over big ones; the structural-enforcement value lands at
Phase 1, with each subsequent phase adding one more enforcement layer.

### Phase 0 — Scaffolding (no enforcement yet)

**Goal:** Establish `hooks/` directory, shared lib, plugin manifest
wiring, test harness. No new behavior — just plumbing.

**Steps:**
- Create `hooks/`, `hooks/_lib/`, `hooks/tests/`, `hooks/tests/fixtures/` dirs
- **First commit:** Write `hooks/hooks.json` = `{"hooks": {}}` (no-op manifest).
  Validates that Claude Code loads a plugin-root hooks file without errors.
- **Empirical validation (blocks all further Phase 0 work):**
  Deploy a 5-line diagnostic PreToolUse hook that writes full stdin JSON to
  `/tmp/tlmforge_hook_stdin_<pid>.json`. Run a live Claude session, trigger
  a Bash tool call, capture the file. Verify that `transcript_path` is present
  in the payload and document the exact JSON schema. Also capture one real
  `Skill(tlmforge:feature-development)` invocation and commit the JSONL line
  to `hooks/tests/fixtures/skill_invocation_sample.jsonl`. If `transcript_path`
  is absent → pivot to marker-file: Hook 1 writes
  `~/.claude/tlmforge_skill_invoked_<session_id>`; Hook 2 reads it.
- Implement `hooks/_lib/transcript.py` (read transcript JSONL using the
  verified schema from above; yield events filtered by type and time window;
  wrap `json.loads(line)` in per-line `try/except JSONDecodeError` — skip
  malformed/truncated lines, continue)
- Implement `hooks/_lib/overrides.py` (detect override phrases — case-
  insensitive word-boundary match on `["be quick", "just do it", "trivial fix"]`;
  bare `"minimal"` and `"trivial"` removed — too many false positives in
  technical prose)
- Implement `hooks/_lib/safe.py` (decorator: catches exceptions, writes
  warning to stderr, exits 0 = allow)
- Implement `hooks/_lib/env.py` (single source of truth for bypass; accepts
  `TLMFORGE_HOOKS` values `{"0", "false", "no", "off", ""}` case-insensitive)
- Add `hooks/tests/conftest.py` with synthetic transcript fixtures (two shapes:
  many-short-lines and few-long-lines, both at 1MB, for the perf benchmark)

**Tests added (Phase 0):**
- `tests/test_transcript.py` — read empty / single-event / 1MB transcripts
  (both shape fixtures); partial-write truncated line → skipped, no crash
- `tests/test_overrides.py` — every override phrase + negative cases:
  "minimal config" does NOT trigger; "trivially false" does NOT trigger;
  "trivial fix" DOES trigger; "be quick" DOES trigger
- `tests/test_safe.py` — exception inside decorated fn → exit 0 + stderr
- `tests/test_env.py` — `TLMFORGE_HOOKS` values: `"0"`, `"false"`, `"no"`,
  `"off"`, `""` all bypass; `"1"`, `"true"`, `"yes"` do not

**Verification:**
- All new tests pass (RED → GREEN)
- Existing repo tests pass (zero regressions)
- `claude plugin reload tlmforge` (or session restart) loads the manifest
  without errors

**Rollback:** Revert commit. No user-visible change.

### Phase 1 — Hook 1 (UserPromptSubmit reminder injector)

**Goal:** Always inject the "invoke the skill" reminder.

**Steps:**
- Implement `hooks/load_feature_dev_skill.py`:
  - Read JSON from stdin (Claude Code's prompt-submit payload)
  - If `TLMFORGE_HOOKS=0` (multi-value per env.py): emit `{}`, exit 0
  - Else: emit `{"systemMessage": "<reminder text>"}` to stdout
    (verified against hookify production plugin — `systemMessage` is the
    correct key; `additionalContext` is ignored)
- Wire `UserPromptSubmit` event in `hooks/hooks.json`
- Reminder text (final, no keywords):
  > Before responding, invoke `Skill(tlmforge:feature-development)`. The
  > skill's Stage 0 will exit cleanly if this isn't a work request; its
  > Stage 1 classification gate is authoritative for Light vs Deep. To
  > bypass enforcement on this message, include `be quick`, `just do it`,
  > or `trivial fix` in your prompt. (Bare "minimal" / "trivial" are NOT
  > accepted — they appear too often in technical prose.)

**Tests added (Phase 1):**
- `tests/test_hook1_normal.py` — stdin → expected stdout JSON shape
- `tests/test_hook1_bypass.py` — `TLMFORGE_HOOKS=0` → pass-through
- `tests/test_hook1_crash.py` — malformed stdin → fail-open + stderr

**Verification:**
- All Phase 0 + Phase 1 tests pass
- Manual: in a fresh session with the plugin installed, type any prompt;
  observe the system-reminder in Claude's response context

**Rollback:** Remove `UserPromptSubmit` entry from `hooks.json`. Reminder
stops firing immediately.

### Phase 2 — Hook 2 (PreToolUse mutation gate)

**Goal:** Block Edit/Write/Bash if skill not invoked AND no override.

**Steps:**
- Implement `hooks/enforce_skill_invoked.py`:
  - Read JSON from stdin (`tool_name`, `tool_input`, `transcript_path`)
  - If `TLMFORGE_HOOKS=0` or `tool_name` not in `{Edit, Write, Bash}`:
    pass-through
  - If transcript has NO user-message entries (subagent session): pass-through
    immediately (subagents run at Stage 3/4; they must not be blocked)
  - Read transcript via `_lib/transcript.py` using the verified JSONL schema;
    use marker-file fallback if `transcript_path` is absent from stdin
  - Task window = events since the last user message (if ≥1 user message
    exists); window_start = session start if only one message
  - Check (A): Skill tool-call entry matching the verified JSON shape from
    `skill_invocation_sample.jsonl` in the task window?
  - Check (B): Override phrase in the LAST user message only (word-boundary
    match on `["be quick", "just do it", "trivial fix"]`)?
  - If A or B: pass-through
  - Else: DENY — write 3-line block message to stderr, `sys.exit(2)`
- Wire `PreToolUse` event with matchers `Edit|Write|Bash` in `hooks/hooks.json`
- Block message:
  > tlmforge: feature-development skill not invoked for this task.
  > Invoke `Skill(tlmforge:feature-development)` to proceed, OR re-prompt
  > with `be quick` / `just do it` / `trivial fix` to override.

**Tests added (Phase 2):**
- `tests/test_hook2_skill_present.py` — skill in transcript → allow
- `tests/test_hook2_override_present.py` — override in last user msg → allow
- `tests/test_hook2_neither.py` — no skill + no override → block (exit 2)
- `tests/test_hook2_skill_in_old_task.py` — skill invoked 3 user-messages
  ago, current task window has neither → block (per F1 per-prompt reset)
- `tests/test_hook2_no_user_messages.py` — transcript has zero user-message
  entries (subagent session) → pass-through immediately (EC-1)
- `tests/test_hook2_bypass.py` — `TLMFORGE_HOOKS=0` → allow regardless
- `tests/test_hook2_non_mutation.py` — Read tool → pass-through unchecked
- `tests/test_hook2_crash.py` — bad transcript path + missing transcript_path
  key in stdin → fail-open (exit 0 + stderr warning)

**Verification:**
- All prior tests pass
- Performance: synthetic 1MB transcript → hook latency <50ms p99
- Manual: in a fresh session, try `Edit` without invoking skill →
  blocked. Add "be quick" to prompt → allowed. Invoke skill → allowed.

**Rollback:** Remove `PreToolUse` entry. Mutations stop being gated.

### Phase 3 — Hook 3 (post-Stage-5 commit/push/merge gate) + schema + SKILL.md partial

**Goal:** Block commits/pushes/merges past the Stage 5 verdict SHA without
post-Stage-5 re-review (PSR). Also ships `verdict_sha` schema update AND
the Stage 5 launch prompt instruction (so reviewers start emitting the field
immediately). The PSR workflow doc in SKILL.md ships here too — Hook 3 can't
reference a workflow that doesn't exist yet.

**Steps:**
- Update `skills/feature-development/review_schema.json`: add `verdict_sha`
  (string, required, description: "40-char SHA from `git rev-parse HEAD`")
  to the `final_audit_*` schema object
- **Partial SKILL.md update (Phase 3 only — not the full Phase 4 update):**
  - Stage 5 launch prompt template: add "Before writing JSON output, run
    `git rev-parse HEAD` (full 40-char hash, not `--short`) and record as
    `verdict_sha` — required for post-Stage-5 gating."
  - Add PSR subsection to SKILL.md Stage 5 area (using distinct name
    "post-Stage-5 re-review" / abbreviation PSR, NOT "Stage 5b" which
    already means spec-drift review per LL-2):
    > **Post-Stage-5 re-review (PSR).** New commits after Stage 5 verdict
    > require a single-shot dual re-review on the new diff only
    > (red-team-reviewer + architect-reviewer, parallel). Reviewers write
    > `final_audit_<role>_psr_<HEAD-sha>.json` with `verdict_sha = HEAD`
    > at review time. Hook 3 unblocks after both PSR files exist for HEAD.
  - Stage 1: skill writes `specs/.tlmforge_active_feature` = feature name.
    Stage 7: skill deletes the marker.
- Implement `hooks/enforce_post_stage5_review.py`:
  - Read JSON from stdin
  - If `TLMFORGE_HOOKS=0` (multi-value per env.py) or `tool_name != "Bash"`:
    pass-through
  - Extract command. If not matching `^(git\s+commit|git\s+push|gh\s+pr\s+merge)`:
    pass-through
  - Use `git rev-parse --show-toplevel` first to find repo root (handles
    any cwd). Then read `<repo_root>/specs/.tlmforge_active_feature` to
    get active feature name. If git fails or file absent → pass-through
    (no active feature, not in a Stage 5-gated workflow)
  - (repo root already resolved above; reuse for all subsequent paths)
  - Glob `<repo_root>/specs/<active_feature>/agent_verification/final_audit_*.json`
  - If glob is empty → pass-through (no Stage 5 yet; nothing to enforce)
  - For each file, parse JSON, extract `verdict_sha` (skip if absent or
    corrupt — `JSONDecodeError` → continue)
  - Run `git rev-parse HEAD`. Check returncode:
    - Exit 128 (no commits, fresh repo): WARNING to stderr, pass-through
    - Other non-zero: WARNING to stderr (differentiate from generic crash),
      pass-through
  - Normalize verdict_sha to 40 chars: `git rev-parse <verdict_sha>`. On
    failure (SHA not in history, e.g. after rebase): still enforce (HEAD !=
    verdict_sha is still true), display "?" for commit count in block message
  - If normalized HEAD == normalized verdict_sha: pass-through
  - Check PSR marker: glob `final_audit_*_psr_<HEAD>.json` in same dir.
    If found, open and verify `verdict_sha` field inside == HEAD (filename
    match alone is not sufficient — prevents accidental cp/rename bypasses)
  - Check override phrase in last user message
  - Else: DENY via `sys.exit(2)` + stderr block message. Atomic write for
    any state files: write to `<path>.tmp`, then `os.replace()`
- Wire as `PreToolUse` matcher for `Bash` in `hooks/hooks.json`
- Block message:
  > tlmforge: Stage 5 verdict at SHA <X>. HEAD is <Y> (? commits since
  > rebase / N commits ahead). Per LL-1/LL-8: run red-team-reviewer +
  > architect-reviewer on `git diff <X>..<Y>`, write
  > final_audit_<role>_psr_<Y>.json for each, then re-push.
  > Override: include `be quick` / `just do it` / `trivial fix` in prompt.

**Tests added (Phase 3):**
- `tests/test_hook3_no_active_feature.py` — no `.tlmforge_active_feature` → allow
- `tests/test_hook3_no_stage5.py` — no final_audit json in active feature → allow
- `tests/test_hook3_head_matches.py` — HEAD == verdict_sha (normalized) → allow
- `tests/test_hook3_head_drifted.py` — HEAD != verdict_sha, no PSR marker,
  no override → block (exit 2)
- `tests/test_hook3_psr_marker.py` — PSR marker with matching internal SHA → allow
- `tests/test_hook3_psr_marker_sha_mismatch.py` — PSR marker filename matches
  but internal verdict_sha ≠ HEAD → block (HIGH-3)
- `tests/test_hook3_psr_marker_missing_verdict_sha.py` — PSR marker is valid
  JSON but `verdict_sha` field absent → treat as no valid PSR → block
- `tests/test_hook3_short_sha_verdict.py` — verdict_sha is short hash → normalize
  to 40 chars before compare; correct allow/block (EC-3)
- `tests/test_hook3_no_commits.py` — `git rev-parse HEAD` exits 128 → WARNING,
  pass-through (EC-2)
- `tests/test_hook3_verdict_sha_not_in_history.py` — SHA not in history after
  rebase → still block with "?" commit count (EC-8)
- `tests/test_hook3_override.py` — "be quick" in last msg → allow
- `tests/test_hook3_non_git_bash.py` — `ls -la` → pass-through unchecked
- `tests/test_hook3_cwd_subdirectory.py` — cwd is project subdir, not repo root
  → uses git rev-parse --show-toplevel for BOTH marker file AND glob; both
  resolve correctly (EC-6 + NEW-2)
- `tests/test_hook3_bypass.py` — `TLMFORGE_HOOKS=0` + variants → allow
- `tests/test_hook3_crash.py` — corrupted final_audit json → skip file, continue

**Verification:**
- All prior tests pass
- Manual: simulate the user's pasted excerpt scenario — write a fake
  `final_audit_red-team-reviewer.json` with `verdict_sha: <past SHA>`,
  attempt `git commit` → blocked

**Rollback:** Remove the `Bash` matcher entry for hook 3 from
`hooks.json`. Other hooks unaffected.

### Phase 4 — SKILL.md remaining updates (Stage 0, LL-6 wire-test, active-feature marker)

**Goal:** Complete the SKILL.md updates not already shipped in Phase 3
(PSR workflow + verdict_sha instruction are done). This phase handles
the discipline entry/exit behavior and the tester wire-test rule.

**Steps:**
- Add **Stage 0 — Non-work-request early exit** at top of SKILL.md
  (before Stage 1):
  > If the user's prompt is conversational, exploratory, or read-only
  > ("what does this file do?", "explain X", "summarize Y"), exit
  > cleanly with a one-line confirmation. Do not produce a spec_audit,
  > do not invoke the classification gate. The hook's reminder applies
  > to all prompts; the skill's job at Stage 0 is to gracefully exit
  > when there's no feature to develop.
- Add **active-feature marker** instructions to SKILL.md Stage 1 and 7:
  > Stage 1 (immediately after writing spec_audit.md): write
  > `specs/.tlmforge_active_feature` = the feature directory name
  > (e.g., `enforcement-hooks`). Stage 7 (after STATUS.md is written):
  > delete `specs/.tlmforge_active_feature`.
- Add **Stage 4.5 / LL-6 wire-test rule** to `agents/tester.md`:
  > For any UI-rendering change (page composition, component prop
  > threading, button text, conditional rendering), require an
  > integration test that exercises the **wire path** end-to-end
  > (e.g., `pricing/page.tsx → TierCards → rendered button text`).
  > Helper-only or component-only tests are not sufficient. This is
  > the LL-6 anti-pattern: tests that pass while the wiring is broken.

**Tests added (Phase 4):**
- N/A — doc-only changes. Verification via manual review.

**Verification:**
- SKILL.md has new Stage 0 section
- SKILL.md PSR (post-Stage-5 re-review) subsection exists (not "Stage 5b")
- tester.md has LL-6 wire-test rule
- `review_schema.json` has `verdict_sha` field

**Rollback:** Revert commit. Hooks still work but skill prose reverts to
prior state.

### Phase 5 — Docs + integration tests + release

**Goal:** README, CHANGELOG, end-to-end test that simulates a real
user session.

**Steps:**
- README install section:
  - Document hook behavior at install
  - Document override phrases
  - Document `TLMFORGE_HOOKS=0` env var bypass
  - Document `tlmforge plugin remove` as the nuclear option
- CHANGELOG 0.5.5 entry: enforcement-hooks layer landed
- Bump `.claude-plugin/plugin.json` version 0.5.4 → 0.5.5
- Add `hooks/tests/test_integration.py` — end-to-end:
  - Start with empty transcript → Hook 1 reminder injected (`systemMessage`)
  - Add user message "add encryption" → Hook 2 blocks Edit/exit(2) (no skill)
  - Skill invoked → `specs/.tlmforge_active_feature` marker written
  - Add `Skill(tlmforge:feature-development)` tool call → Hook 2 allows Edit
  - Stage 5 final_audit JSON written with `verdict_sha=A` (40-char hash)
    → Hook 3 allows `git commit` while HEAD=A
  - Advance HEAD to B → Hook 3 blocks `git commit`, `git push` (exit 2)
  - Add PSR marker `final_audit_red-team_psr_B.json` + architect equivalent,
    both with internal `verdict_sha=B` → Hook 3 allows again

**Tests added (Phase 5):**
- `tests/test_integration.py` (above)

**Verification:**
- All tests across all phases pass
- README renders correctly on GitHub
- CHANGELOG entry matches the project's existing voice (see 0.5.0-0.5.4)
- Manual install test: fresh `claude plugin add github:neuralforge-labs/tlmforge`
  + restart session → hooks fire as documented

**Rollback:** Revert release commit. Plugin reverts to 0.5.4 behavior.

### Phase 6 (OPTIONAL — DEFERRED) — `tlmforge:doctor`

**Goal:** Diagnostic command for users hitting hook issues.

Skipping unless user pulls in. Captured here so future-self knows the
plan exists. Estimated: half a day.

## Risk audit

Carrying forward from `spec_audit.md`:

| Risk | Severity | Mitigation | Phase |
|---|---|---|---|
| Hook crashes brick session | CRITICAL | F9 fail-open wrapper | Phase 0 |
| Hook 2 latency >50ms blocks workflow | HIGH | F4 perf budget + benchmark | Phase 2 |
| False-positive skill detection (prose match) | HIGH | F5 structured JSON match | Phase 2 |
| First-run UX feels intrusive | MEDIUM | F11 brief SessionStart reminder + clear blocks | Phase 1, 2 |
| Plugin cache stale (DF1) means hooks don't update | HIGH | Documented in README per 0.5.4; SessionStart restart guidance | Phase 5 |
| Override "be quick" in mid-message context could be unintended | MEDIUM | Match in last user message only, not anywhere in transcript | Phase 0 (overrides lib) |
| `git commit` from CI / release script blocked | MEDIUM | `TLMFORGE_HOOKS=0` (sole bypass); CI must set this explicitly; CI=true NOT auto-detected | Phase 5 |

Newly identified during plan write:

| Risk | Severity | Mitigation | Phase |
|---|---|---|---|
| Hook scripts are bash → python; need `python3` on PATH | MEDIUM | hooks.json shebangs check `python3` exists; otherwise hook fails open with stderr message pointing at install instructions | Phase 0 |
| Stage 5 reviewers need to start emitting `verdict_sha` | LOW | Explicit SKILL.md Stage 5 prompt instruction ships with Phase 3 schema update; absent field → pass-through (backward compat) | Phase 3 |
| Multi-feature: wrong feature's verdict blocks another feature's commits | HIGH | Active-feature marker `specs/.tlmforge_active_feature` scopes Hook 3 to one feature at a time | Phase 3 |
| PSR marker bypassed by copying/renaming file with wrong internal SHA | MEDIUM | Hook 3 opens PSR marker file and validates internal `verdict_sha == HEAD`; filename match alone insufficient | Phase 3 |
| git rev-parse HEAD fails (empty repo, no-git cwd) | MEDIUM | returncode check: non-zero → WARNING + pass-through | Phase 3 |
| verdict_sha becomes unreachable after rebase | MEDIUM | SHA normalization fails gracefully; still block but show "?" for commit count | Phase 3 |

## Decisions made

- **No keyword classification in hooks.** Confirmed by saved feedback
  memory `feedback-no-keyword-classifiers`.
- **Hook 1 always fires; skill itself classifies.** Per user direction.
- **Override scope: per-prompt with reset on next user message.** Confirmed.
- **Plugin-shipped hooks (auto-active on install).** Confirmed — obvious;
  `hooks/hooks.json` at plugin root (not `.claude-plugin/`).
- **`TLMFORGE_HOOKS=0` is the ONLY bypass.** Confirmed (F3). CI=true and
  GITHUB_ACTIONS are NOT honored — too easy to accidentally have in
  local shell. CI pipelines should set `TLMFORGE_HOOKS=0` explicitly.
  Bypass accepts values `{"0","false","no","off",""}` case-insensitive.
- **Deny via `sys.exit(2)` + stderr.** Verified against real installed
  Claude Code plugins (security-guidance, hookify). Not JSON stdout.
- **UserPromptSubmit reminder via `{"systemMessage": "..."}`.** Verified
  against hookify production plugin.
- **"Stage 5b" name NOT used for post-commit re-review.** SKILL.md already
  uses "Stage 5b" for spec-drift review (LL-2). Post-commit re-review
  named "post-Stage-5 re-review" (PSR); marker files `*_psr_<sha>.json`.
- **Override phrases: `["be quick", "just do it", "trivial fix"]`.**
  Removed bare `"minimal"` and `"trivial"` — too many false positives.
- **Subagent sessions (no user messages) → Hook 2 pass-through.**
  Stage 3/4 reviewer subagents must not be blocked.
- **Active-feature marker file `specs/.tlmforge_active_feature`.**
  Hook 3 scopes glob to this feature's audit files; avoids multi-feature
  cross-contamination.
- **Fail-open on hook crash.** Bug in tlmforge must not brick user
  sessions. Trade-off documented in F9.
- **Python (not Node).** Matches existing `check_convergence.py` runtime.
- **Specs go in `$REPO_ROOT/specs/enforcement-hooks/`.**
  Per project CLAUDE.md directory convention.

## Cost analysis

- **Token cost per user-day:** Hook 1 reminder ≈ 50 tokens × 50 prompts/
  day = 2,500 tokens. SKILL.md load ≈ 7,000 tokens × ~5 tasks/day × ~80%
  cache-hit rate (Anthropic prompt cache) = ~7,000 fresh tokens (one full
  load) per user-day. Total: ~10K tokens/user/day. Negligible.
- **Latency cost:** Hook 1 sub-10ms (no IO beyond stdout write). Hook 2
  budget 50ms (transcript scan). Hook 3 budget 100ms (git rev-parse +
  json reads). Per Edit: +50-100ms. Per `git commit`: +100ms. Acceptable.
- **Implementation cost:** ~1 day of focused work for Phases 0-5. Phase 6
  (doctor) deferred.

## Open questions for the user

(See `spec_audit.md` for full list. Three [GATE-BLOCKING] items repeated
here for visibility.)

1. **F1** — Override scope: per-prompt with reset on next user message?
2. **F2** — Distribution: plugin-shipped (auto)?
3. **F3** — Bypass mechanism: `TLMFORGE_HOOKS=0` env var?

Plus three informational confirmations defaulted in the plan:

4. Hook 3 does NOT gate `gh pr create` (commit/push/merge enough)
5. `tlmforge:doctor` deferred to follow-up
6. SKILL.md gains a Stage 0 "non-work prompt" early-exit clause

## TDD plan

| Phase | Layer | Tests |
|---|---|---|
| 0 | Unit | transcript parsing (both shapes + partial-write truncation), override detection (including false-positive cases for "minimal"/"trivial"), fail-open wrapper, env-var bypass variants |
| 1 | Unit + integration | Hook 1: normal injection (systemMessage key), bypass, crash |
| 2 | Unit + integration | Hook 2: skill present / override present / neither (exit 2) / no user msgs (subagent) / old task window / non-mutation / bypass / crash |
| 3 | Unit + integration | Hook 3: no active feature / no Stage 5 / matching HEAD / drifted HEAD / PSR marker (valid + SHA mismatch) / short SHA / no commits / rebase / override / non-git Bash / subdirectory cwd / bypass / crash |
| 4 | n/a | Doc-only; manual review |
| 5 | E2E | Full session: prompt → hook 1 → skill (marker written) → mutation → hook 2 → Stage 5 verdict (verdict_sha) → commit → hook 3 blocks → PSR markers → hook 3 allows |

Every phase: write tests FIRST → confirm RED → implement → confirm GREEN
→ run full pre-existing suite (zero regressions).

## Verification criteria

The feature is **done** when:

- All 3 hooks ship in `hooks/`, wired in `hooks/hooks.json` at plugin root
- All hook tests pass (unit + integration + E2E)
- Pre-existing repo tests pass (zero regressions)
- Performance: Hook 2 latency <50ms p99 on a 1MB transcript
- Fresh `claude plugin add github:neuralforge-labs/tlmforge` + session restart →
  Hook 1 reminder appears on first prompt; Hook 2 blocks first
  unauthorized mutation; Hook 3 blocks `git commit` past a recorded
  Stage 5 SHA
- README install section documents the override phrases and
  `TLMFORGE_HOOKS=0`
- CHANGELOG 0.5.5 entry exists
- SKILL.md has Stage 0 + PSR (post-Stage-5 re-review) subsection + active-feature marker steps
- agents/tester.md has the LL-6 wire-test rule
- review_schema.json has `verdict_sha`
