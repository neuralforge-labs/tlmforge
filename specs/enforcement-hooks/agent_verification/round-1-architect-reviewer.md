# enforcement-hooks — Architect Review (Round 1)

**Reviewer:** architect-reviewer
**Iteration:** 1
**Verdict:** needs_revision

---

## Summary

The plan's high-level architecture is sound — three hooks addressing the two
stated failure modes, fail-open, per-prompt override, plugin-shipped. However
several implementation-level claims are technically wrong against the real
Claude Code hook API, and two design gaps (verdict_sha reliability and
multi-feature Hook 3 logic) would cause the feature to malfunction in
predictable scenarios. Four issues require fixes before implementation begins.

---

## Instruction Compliance

The plan addresses all eight questions posed in the launch prompt. No missed
requirements. Scope matches the stated goal. Phase ordering is logical. TDD
plan is complete with per-phase test lists.

---

## Critical Issues

### C1 — Wrong PreToolUse deny output format (hallucinated API shape)

**File:** `specs/enforcement-hooks/README.md` — Phase 2 steps, deny JSON block

**What the plan says:**
```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": "<msg>"}}
```

**What the Claude Code API actually does:**
After reading the real plugin implementations (security-guidance, hookify) installed
on this machine, `PreToolUse` denial is accomplished via `sys.exit(2)` (non-zero
exit code), with the block message written to **stderr**. Claude Code reads stderr
and surfaces it to Claude as the denial reason. The `hookSpecificOutput` JSON shape
with `permissionDecision: "deny"` is documented in official docs but the actual
installed plugins use the exit-code pattern. The docs say both work, but the exit
code path (`exit(2)` + stderr) is simpler, battle-tested in production, and avoids
JSON parsing complications. More critically: the plan's Phase 2 deny implementation
would need to output this JSON to **stdout** — but the hookify PreToolUse hook
demonstrates that stdout JSON is for `systemMessage` / context injection, not
blocking. Using the wrong mechanism means Hook 2 either silently passes (if JSON
output is ignored) or surfaces a confusing error.

**Fix:** Implement the deny path using `sys.exit(2)` + block message written to
stderr. Do NOT rely on `hookSpecificOutput.permissionDecision` JSON unless you
explicitly verify that shape works for PreToolUse block in an integration test
(Phase 2 verification). Add a test case that specifically checks exit code = 2
on the deny path. Keep the JSON shape as a fallback comment with a TODO to
verify both paths.

---

### C2 — Wrong hooks.json file location

**File:** `specs/enforcement-hooks/README.md` — Phase 0 steps; Scope section

**What the plan says:** `.claude-plugin/hooks.json` (or `plugin/hooks/hooks.json`
per Claude Code convention)

**What the Claude Code API actually requires:**
After examining every installed plugin on this machine, the canonical path is
`hooks/hooks.json` at the **plugin root** — NOT inside `.claude-plugin/`. The
`.claude-plugin/` directory contains ONLY `plugin.json` (metadata). All functional
components (hooks, agents, skills, commands) live at the plugin root. The tlmforge
repo currently has `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
but no hooks directory. Placing hooks.json inside `.claude-plugin/` would cause
Claude Code to ignore it entirely on `claude plugin add`.

The `CLAUDE_PLUGIN_ROOT` env var that hooks use to self-locate also resolves to
the plugin root, not to `.claude-plugin/`. The hooks.json `command` fields reference
`${CLAUDE_PLUGIN_ROOT}/hooks/...` scripts — which only works if hooks.json is at
`hooks/hooks.json` relative to the plugin root.

**Fix:** Hooks manifest path = `hooks/hooks.json` (plugin root level, not inside
`.claude-plugin/`). Hook scripts = `hooks/load_feature_dev_skill.py`,
`hooks/enforce_skill_invoked.py`, `hooks/enforce_post_stage5_review.py`. Shared
lib = `hooks/_lib/`. Update the Scope section's bullet accordingly.

---

### C3 — transcript_path in PreToolUse stdin is unverified / likely absent

**File:** `specs/enforcement-hooks/README.md` — Phase 2 steps (Hook 2 implementation)

**What the plan says:** "Read JSON from stdin (`tool_name`, `tool_input`,
`transcript_path`). Read transcript via `_lib/transcript.py`, scoped to current
task (since last user message). Check (A): is there a tool-call entry for
`Skill(tlmforge:feature-development)` in the task window?"

**The problem:** The PreToolUse stdin payload contains `session_id`, `tool_name`,
`tool_input`, and `cwd`. Whether `transcript_path` is consistently present is
unverified. The real security-guidance plugin reads only `session_id`, `tool_name`,
`tool_input` from stdin — no transcript access. The hookify PreToolUse hook does
the same. Neither hooks implementation reads a transcript file. The Claude Code
hooks spec (code.claude.com/docs/en/hooks) shows `transcript_path` in the common
fields list, but its availability in PreToolUse payloads specifically — and the
JSONL format of the transcript — must be empirically verified. If `transcript_path`
is absent or the transcript format differs from JSONL-with-tool-call entries, Hook 2's
entire skill-detection logic silently fails (and since it fails open, it silently
allows all mutations, defeating its purpose).

**Fix:** Phase 0 must include an empirical validation step: add a diagnostic hook
that logs the full stdin JSON of a PreToolUse event to a temp file, verify
`transcript_path` is present, open the file, and document the JSONL entry shape for
tool calls. Make this a required Phase 0 deliverable before `_lib/transcript.py`
is implemented. If `transcript_path` is absent, the skill-detection strategy must
pivot to an alternative (e.g., a marker file written when skill is invoked, which
Hook 2 checks via `stat`).

---

### C4 — verdict_sha reliability: reviewers won't emit it without SKILL.md instruction

**File:** `specs/enforcement-hooks/README.md` — Phase 3 steps; Phase 4 SKILL.md updates

**The problem:** Hook 3 depends on `verdict_sha` being present in
`final_audit_*.json` files. The plan adds `verdict_sha` to `review_schema.json`
(Phase 3) and adds the Stage 5 launch prompt instruction in SKILL.md (Phase 4).
But the plan notes (correctly) that Phase 4 is doc-only. Here is the gap: Phase 3
ships Hook 3 (which reads `verdict_sha`) BEFORE Phase 4 ships the SKILL.md update
that tells Stage 5 reviewers to record `verdict_sha`. During the interval between
Phase 3 and Phase 4 going live, any Stage 5 audit run will produce final_audit JSON
files WITHOUT `verdict_sha`, and Hook 3 will treat them as "no Stage 5 yet" —
passing through silently. This is documented as acceptable in the risk table, but
there's a worse problem: even after Phase 4 ships, the Stage 5 launch prompt template
in SKILL.md must EXPLICITLY instruct reviewer subagents to (1) run `git rev-parse HEAD`
and (2) write the result as `verdict_sha` in their JSON. Subagents do not have
standing access to git state; they need explicit instruction to acquire it.
Currently SKILL.md's Stage 5 launch prompt template (line ~869 of SKILL.md) says:
"Output: agent_verification/final_audit_<your-role>.json (per JSON schema)" —
it does NOT mention running git or recording a SHA. Without this explicit step,
reviewers won't do it and Hook 3 will never gate anything for real features.

**Fix:** Phase 4 SKILL.md update must include the explicit Stage 5 launch prompt
addition: "Before writing your JSON output, run `git rev-parse HEAD` and record the
result as `verdict_sha` in your JSON. This is required — Hook 3 reads this field to
gate subsequent commits." Add a test in Phase 3 that validates: if a final_audit JSON
has a `verdict_sha` field, Hook 3 uses it; if the field is absent, Hook 3 passes
through. Also consider making Phase 4 a prerequisite of Phase 3 (swap order) so
SKILL.md changes ship before the hook that depends on them.

---

## High Severity

### H1 — UserPromptSubmit output format: `additionalContext` vs `systemMessage`

**File:** `specs/enforcement-hooks/README.md` — Phase 1 steps

**What the plan says:** emit `hookSpecificOutput.additionalContext` JSON with the
reminder text.

**What real plugins do:** The hookify `userpromptsubmit.py` (installed, production)
uses a JSON object with a `systemMessage` key for context injection:
`{"systemMessage": "..."}`. The `additionalContext` field is referenced in docs but
the key actually used in working plugins is `systemMessage`. This is a lower
criticality than C1 because Hook 1's function is additive (injection, not blocking),
so a wrong field name degrades to silence rather than catastrophic failure — but
silence is the exact failure mode we're trying to prevent: the reminder simply won't
appear in Claude's context.

**Fix:** Implement using `systemMessage` key in the JSON output. Add an integration
test in Phase 1 that verifies the reminder text actually appears in Claude's visible
context (not just that the hook exits 0). The Phase 1 manual verification step
should be made more specific: "observe the reminder text in Claude's system context,
not just that a prompt was submitted."

---

### H2 — Hook 3 multi-feature logic is inconsistent between plan body and risk table

**File:** `specs/enforcement-hooks/README.md` — Phase 3 implementation vs Risk audit

**The problem:** The Phase 3 implementation says "find the most recent (by file
mtime) Stage 5 verdict" across ALL features. The risk table says "use most-recent
by mtime within the same feature dir; if user is working across two features
simultaneously, both get gated independently." These are contradictory. The
implementation globbing `specs/*/agent_verification/final_audit_*.json` and picking
the single most-recent file treats ALL features as one pool. If Feature A has a
Stage 5 verdict at SHA 100, and Feature B is in development at SHA 110, Hook 3
will block Feature B's commits because Feature A's verdict_sha (100) != HEAD (110)
— even though Feature B has never had a Stage 5. The risk table's "gated
independently" semantics requires per-feature verdict tracking, but the
implementation is global.

**Fix:** Hook 3 must resolve the active feature from context (e.g., the `specs/`
directory whose files have been most recently modified, or the directory containing
the most recent final_audit file). Alternatively, track verdict_sha per
feature-directory and only gate if the active feature has a Stage 5 verdict. The
simplest safe heuristic: if ANY `final_audit_*.json` in `specs/*/` has
`verdict_sha` set, gate commits where HEAD != any recorded verdict_sha AND no 5b
marker exists for HEAD. But document that two simultaneous active features with
different Stage 5 SHAs will always trigger the gate — which may be the intended
conservative behavior. Pick one semantics, document it, and make the implementation
match.

---

### H3 — Stage 5b re-review workflow is not discoverable by the main Claude agent during Phase 3

**File:** `specs/enforcement-hooks/README.md` — Phase 3 block message; Phase 4 SKILL.md

**The problem:** Hook 3 ships in Phase 3. Its block message says "Run Stage 5b
re-review." But Stage 5b is defined in SKILL.md, which is updated in Phase 4. During
the Phase 3 → Phase 4 gap, Hook 3 will block commits and tell Claude to "run Stage
5b re-review" — but neither the running SKILL.md nor any other document explains
what Stage 5b is or how to run it. Claude will be blocked with no actionable path.
Even after Phase 4 ships, SKILL.md's current Stage 5b section (lines ~1304-1310 in
the existing SKILL.md — the spec-drift subsection) documents Stage 5b as a
spec-drift review, not a post-commit re-review. The plan adds a new meaning to
"Stage 5b" that conflicts with the existing one.

**Fix:** Phase 4 must land BEFORE or concurrently with Phase 3 (or Phase 3 must
ship after Phase 4). Alternatively, Phase 3's block message should be
self-contained: instead of "run Stage 5b re-review," spell out the action inline:
"Re-launch red-team-reviewer + architect-reviewer against `git diff <verdict_sha>..HEAD`
and write `final_audit_<role>_5b_<HEAD-sha>.json`." Additionally, the plan must
address the naming collision: "Stage 5b" currently means spec-drift review in
SKILL.md (LL-2). Reusing the name for post-commit re-review will create confusion.
Consider a distinct label: "Stage 5-post" or "Stage 5c."

---

## Medium Severity

### M1 — Override substring matching on "minimal" is too broad

**File:** `specs/enforcement-hooks/README.md` — Phase 0 `_lib/overrides.py`

The override phrase list includes "minimal." This word appears in natural task
descriptions: "add minimal logging," "use a minimal config," "keep it minimal."
The plan says substring match, case-insensitive. Any prompt containing "minimal"
anywhere would disable Hook 2 for that entire task window — including non-override
uses. The user's CLAUDE.md specifies "minimal" as an override trigger, but the
implementation risk of substring matching makes it too easy to accidentally trigger.

**Fix:** Match "minimal" only when it appears as a standalone token adjacent to
boundaries (word-boundary regex), not as a substring of other words. Or treat it as
requires the full phrase "be minimal" / "keep it minimal" to avoid false triggers
on "minimal change," "minimal footprint," etc.

---

### M2 — Phase ordering: review_schema.json update (Phase 3) should logically precede Hook 3

**File:** `specs/enforcement-hooks/README.md` — Phase 3 steps ordering

Phase 3 opens with "Update `skills/feature-development/review_schema.json`" then
implements Hook 3. This is correct ordering within the phase. However, given that
Hook 3 depends on `verdict_sha` which is DEFINED by the schema update and
EMITTED by the SKILL.md change (Phase 4), implementing Hook 3 before the SKILL.md
update (Phase 4) creates a permanent dead-on-arrival gate: hook deployed but nothing
ever writes the field it reads. The schema update alone does not cause reviewers to
emit the field — only the SKILL.md launch prompt change does that.

**Fix:** Either (a) merge the SKILL.md `verdict_sha` emission instruction into
Phase 3 (alongside the schema update, before Hook 3 ships), or (b) move Phase 4
to before Phase 3. Option (a) is cleaner: Phase 3 ships schema + SKILL.md prompt
instruction + Hook 3 as a coherent unit. Phase 4 then covers the remaining SKILL.md
updates (Stage 0 non-work early exit, LL-6 wire-test rule).

---

### M3 — `hooks.json` doesn't exist on first install — no validation of empty manifest

**File:** `specs/enforcement-hooks/README.md` — Phase 0 verification

The plan correctly notes wiring `.claude-plugin/hooks.json` with empty hook arrays
as a Phase 0 step (now corrected to `hooks/hooks.json` per C2). The Phase 0
verification step says "load the manifest without errors." But the plan doesn't
address what happens during Phase 0 if `hooks/hooks.json` doesn't exist yet in
the installed plugin (because Phase 0 is creating it). A user who already has
tlmforge installed and does `claude plugin update` will go through a state where
the plugin exists but `hooks/hooks.json` may not yet (depending on commit timing).
Claude Code's behavior when `hooks/hooks.json` is missing vs empty is not
documented — if it treats missing as "no hooks" that's fine; if it errors, it
could break sessions for existing users during the upgrade window.

**Fix:** Include in Phase 0 an explicit check that `hooks/hooks.json` absent is
handled gracefully by Claude Code. If uncertain, ship a no-op `hooks/hooks.json`
(empty `{"hooks": {}}`) in Phase 0 as the very first commit, before any hook
script is written. This ensures the manifest always exists at the plugin root after
Phase 0 lands.

---

### M4 — No `recommendation` field in the schema; plan's `suggested_fix` is correct but JSON output needs to match schema

**File:** `specs/enforcement-hooks/README.md` — instruction to save JSON

The launch prompt for this review asks for a `recommendation` field per finding.
The actual `review_schema.json` uses `suggested_fix`. The plan correctly says the
JSON must validate against `review_schema.json`. Confirming: my JSON output below
uses `suggested_fix` per the schema. (Non-blocking process note only.)

---

## Low Severity

### L1 — CI env var bypass: plan explicitly rejects `CI=true` but risk table documents it

**File:** `specs/enforcement-hooks/README.md` — Risk audit table

The risk audit table lists "`TLMFORGE_HOOKS=0` env var bypass" as the mitigation
for CI blocking. The spec_audit (F3) correctly recommends NOT auto-detecting
`CI=true`. The plan is internally consistent. However, the README's "Bypass:
`TLMFORGE_HOOKS=0` env var, plus CI env vars (`CI=true`, `GITHUB_ACTIONS`)" in
the architecture ASCII diagram contradicts this — the diagram text includes
`CI=true` and `GITHUB_ACTIONS` as bypass conditions. If implemented literally,
this re-introduces the auto-detect that F3 rejected.

**Fix:** Remove `CI=true` and `GITHUB_ACTIONS` from the architecture diagram's bypass
list. `TLMFORGE_HOOKS=0` is the only bypass. Clarify in the README install section
that CI users should set `TLMFORGE_HOOKS=0` in their pipeline env.

---

### L2 — No handling of concurrent Claude sessions writing to the same marker files

**File:** `specs/enforcement-hooks/README.md` — Phase 3 implementation

The spec_audit addresses concurrency briefly ("Hooks are invoked synchronously by
Claude Code per tool call; no concurrency within a single session"). However, a user
running two Claude Code sessions simultaneously on the same repo (not uncommon during
incident response) would have two Hook 3 processes reading and potentially writing the
same `final_audit_*_5b_<sha>.json` marker file concurrently. The plan's recommended
atomic write pattern (`*.tmp` → `mv`) is noted in the risk table for the marker
file but not specified in the Phase 3 implementation steps.

**Fix:** Phase 3 implementation must explicitly use atomic write for the Stage 5b
marker file. Add a test case for the race condition: two processes writing the same
marker file simultaneously should result in a valid file (not corruption).

---

## What's Good

- The fail-open architecture is correct and non-negotiable. A hook bug must not
  brick sessions. The `_lib/safe.py` wrapper approach handles this cleanly.
- The three-phase rollback structure is sound. Each phase leaves a working system;
  reverting any single phase leaves the system in the prior state.
- Per-prompt override reset semantics (F1 resolution) is the right call. Sticky
  overrides defeat the purpose of the gate.
- The TDD plan is specific — named test files, described behaviors, RED/GREEN
  expectations per phase. Not hand-waved.
- The cost analysis is concrete and shows non-trivial thought (prompt cache hit
  rate, 50ms budget for transcript scan).
- Phase 0 scaffolding before any behavior is correct engineering discipline.
- Using `CLAUDE_PLUGIN_ROOT` for self-location in hook commands is the right
  pattern — verified against real plugin implementations.

---

## Answers to the 8 Specific Questions

1. **Hidden irreversible step?** No phase has an irreversible operation. Each phase's
   rollback is "remove the hook wiring entry." Clean.

2. **Plugin hook wiring architecture correct?** Partially. The hooks.json path is
   wrong (C2). The deny output format for PreToolUse is wrong (C1). The
   UserPromptSubmit output key may be wrong (H1). The hook command structure
   (`${CLAUDE_PLUGIN_ROOT}/hooks/...`) is correct per real plugin examples.

3. **Hook 2 task window detection across multi-turn?** The design (since last user
   message) is conceptually correct. The execution risk is that transcript_path may
   not be in the PreToolUse stdin payload (C3). If it IS present and the transcript
   is JSONL with typed entries, the "since last user message" scoping is achievable.
   The boundary detection logic (find the most recent user message entry, only scan
   entries after it) is sound in concept.

4. **Stage 5b discoverability?** Not discoverable during Phase 3-to-Phase-4 window
   (H3). After Phase 4, discoverable IF SKILL.md's Stage 5b section describes the
   post-commit re-review workflow clearly. The current SKILL.md "Stage 5b"
   (spec-drift review) is a different concept — naming collision must be resolved.

5. **verdict_sha reliability?** No — subagent reviewers will not run `git rev-parse
   HEAD` without explicit instruction in the launch prompt. The schema update alone
   does not cause them to emit the field (C4). The fix requires an explicit
   instruction in the Stage 5 launch prompt template in SKILL.md.

6. **Multi-feature Hook 3 logic?** Plan body and risk table are contradictory (H2).
   The implementation as written (glob all features, pick most-recent by mtime) does
   NOT achieve "each feature gated independently." Must be resolved before Phase 3.

7. **Phase ordering — schema before SKILL.md?** The schema update (Phase 3) precedes
   the SKILL.md instruction (Phase 4), but this creates a gap: the hook is live
   but nothing writes the field it reads. Addressed in C4 and M2. The fix is to
   merge the SKILL.md `verdict_sha` emission instruction into Phase 3.

8. **What if hooks.json doesn't exist yet?** Addressed in Phase 0 (ship empty
   manifest first). M3 raises a nuance about upgrade paths for existing users.
   Ship the empty `hooks/hooks.json` as the first commit in Phase 0 to avoid
   any window where the file is absent.
