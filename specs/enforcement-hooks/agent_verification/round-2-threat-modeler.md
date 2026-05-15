# Round 2 Threat Modeler Review — enforcement-hooks

**Reviewer:** threat-modeler
**Iteration:** 2
**Date:** 2026-05-15

---

## Prior findings — disposition

### HIGH-1 (CI=true contradiction) — FIXED

The architecture diagram now explicitly states "Honors TLMFORGE_HOOKS=0 (sole bypass; no CI
auto-detect)." The Decisions section reads: "`TLMFORGE_HOOKS=0` is the ONLY bypass. Confirmed
(F3). CI=true and GITHUB_ACTIONS are NOT honored." The risk table entry confirms "CI=true NOT
auto-detected." All references to CI=true and GITHUB_ACTIONS are gone from the bypass logic.

Evidence: README.md Architecture box for Hook 1; Decisions section; Risk audit table.

---

### HIGH-2 (Skill-call detection pattern unverified) — FIXED

Phase 0 now has a hard-blocking empirical validation step: deploy a diagnostic PreToolUse hook,
capture full stdin JSON to a temp file, verify transcript_path is present, and capture one real
Skill tool-call JSONL record committed as `hooks/tests/fixtures/skill_invocation_sample.jsonl`.
The sensitive surface inventory lists the fixture as a required deliverable. Hook 2's detection
logic is blocked on this verified shape.

Evidence: README.md Phase 0 "Empirical validation (blocks all further Phase 0 work)" paragraph;
Sensitive surface inventory entry.

---

### HIGH-3 (PSR marker filename-only check) — FIXED

Hook 3's Phase 3 implementation spec now says: "open and verify `verdict_sha` field inside ==
HEAD (filename match alone is not sufficient — prevents accidental cp/rename bypasses)." The
architecture box shows "(SHA validated internally)." A dedicated test
`test_hook3_psr_marker_sha_mismatch.py` is listed in the Phase 3 test suite.

Evidence: README.md Phase 3 Steps, Hook 3 architecture box, Phase 3 test list.

---

### MEDIUM-1 (git subprocess failure visibility) — FIXED

Phase 3 now distinguishes returncode categories: exit 128 (no commits) → WARNING + pass-through;
other non-zero → WARNING to stderr (explicitly noted as "differentiate from generic crash") +
pass-through. The architecture box confirms "git errors: WARNING + pass-through."

Evidence: README.md Phase 3 Steps, Hook 3 architecture box.

---

### MEDIUM-2 (minimal substring override) — FIXED

Override phrase list is now `["be quick", "just do it", "trivial fix"]`. Bare "minimal" and
"trivial" are explicitly removed. Phase 0 tests include false-positive cases: "minimal config"
does NOT trigger; "trivially false" does NOT trigger.

Evidence: README.md Phase 0 overrides.py spec; Phase 2 architecture box; TDD plan Phase 0 row.

---

### MEDIUM-3 (mtime ordering for multi-verdict) — FIXED (structurally moot)

The active-feature marker approach adopted for H2 (architect) scopes Hook 3's glob to a single
feature's audit directory, where only one final_audit file per role is expected. Mtime-based
selection across multiple features is no longer in the design.

Evidence: README.md Hook 3 architecture box; Phase 3 Steps (active-feature marker read).

---

### MEDIUM-4 (zero user messages) — FIXED

Phase 2 implementation spec now explicitly says: "If transcript has NO user-message entries
(subagent session): pass-through immediately (subagents run at Stage 3/4; they must not be
blocked)." The dedicated test `test_hook2_no_user_messages.py` is listed.

Evidence: README.md Phase 2 Steps; Phase 2 test list.

---

### LOW (fail-open stderr vs stdout warning) — NOT FIXED

The plan still specifies that `safe.py` "catches exceptions, writes warning to stderr, exits 0 =
allow." No stdout JSON emission is planned. The Architecture box for Hook 2 says "Fails open on
crash" with no additional visibility mechanism. This matches an intentional deferral — no fixes
doc entry addresses it. The finding remains open.

This is a low finding. In practice, Claude Code may not surface stderr from a hook that has
already exited 0. If Hook 2 crashes silently on every invocation, the user has no in-band
signal. The deferred `tlmforge:doctor` (Phase 6, optional) is the only planned remedy. For a
single-user tool the severity remains low — the failure mode is reduced enforcement, not data
loss or unauthorized access.

---

## New findings

### NEW-1 (medium) — Hook 1 reminder text advertises bypass phrases that Hook 2 no longer accepts

The Hook 1 reminder text in Phase 1 reads:

> "To bypass enforcement on this message, include `be quick`, `minimal`, `trivial`, or `just do
> it` in your prompt."

However, the override phrase list was updated (EC-5/MEDIUM-2 fix) to remove bare "minimal" and
"trivial" as false-positive-prone. Hook 2's `overrides.py` only accepts
`["be quick", "just do it", "trivial fix"]`.

This is an internal contradiction: Hook 1 tells users that typing "minimal" or "trivial" will
bypass Hook 2, but they won't. A user following Hook 1's own guidance will be blocked by Hook 2
with no explanation of why the advertised phrase failed. They may then try compound forms
("trivial fix"), accidentally stumble on a working phrase, or give up and use `TLMFORGE_HOOKS=0`.

This is not a silent enforcement failure — the enforcement still fires correctly. The discipline
integrity assumption is not violated. The problem is discoverability: the design assumes that
Hook 1's advertised bypass phrases match Hook 2's actual bypass phrases, and it violates that
assumption.

**Impact:** User confusion; may cause unnecessary friction that pushes users toward
TLMFORGE_HOOKS=0 (the nuclear option) when a lighter override would have sufficed.

**Fix:** Update the Hook 1 reminder text to match the actual phrase list: "To bypass
enforcement on this message, include `be quick`, `trivial fix`, or `just do it` in your
prompt." Remove "minimal" and "trivial" from the reminder. Also update the block message in
Hook 2 and Hook 3 to list only the three compound phrases.

---

## Summary

All 7 prior findings disposed: 6 FIXED, 1 NOT_FIXED (LOW — fail-open stderr visibility,
intentionally deferred). One new MEDIUM finding: Hook 1 reminder text lists bypass phrases that
Hook 2 no longer accepts, creating a user-facing discoverability contradiction.

**Verdict:** approve_with_warnings

The NOT_FIXED LOW and the new MEDIUM do not block convergence. No critical or high findings
remain open.
