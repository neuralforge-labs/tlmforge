# Round 2 Architect Review — enforcement-hooks

## VERDICT: NEEDS REVISION

## Summary

Round-1 findings were almost entirely addressed in the updated plan. Nine of eleven
architect findings are fully fixed. Two issues survive: one is a genuine regression
introduced by the fix itself (reminder text in Phase 1 re-introduces "minimal" and
"trivial" as override phrases after they were explicitly removed from the override
library), and one is a stale path reference in the Verification Criteria section.
Both are low-effort fixes.

---

## Prior Finding Status

### C1 — Deny via exit(2) + stderr: FIXED

Evidence: Architecture diagram (lines 146, 168), Phase 2 implementation spec
("write 3-line block message to stderr, `sys.exit(2)`", line 317), Phase 3
implementation spec ("DENY via `sys.exit(2)` + stderr block message", line 397),
Decisions section ("Deny via `sys.exit(2)` + stderr. Verified against real installed
Claude Code plugins", line 558-559). All deny paths now consistently specify the
correct mechanism. Phase 2 test `test_hook2_neither.py` explicitly tests exit 2.

### C2 — hooks.json path at plugin root: FIXED

Evidence: Scope section ("hooks/hooks.json at plugin root", line 31), Sensitive
surface inventory ("hooks/hooks.json — NEW (at plugin root, alongside
`.claude-plugin/`)", line 195), Phase 0 first-commit step (line 221), Phase 1 wire
step (line 276), Phase 2 wire step (line 318), Phase 3 wire step (line 399),
Decisions section (line 553). All in-plan references correctly use `hooks/hooks.json`.

One residual issue exists in the Verification Criteria section (line 623):
"All 3 hooks ship in `hooks/`, wired in `.claude-plugin/hooks.json`" — this
is a stale copy of the pre-fix wording. The implementation path is correct
everywhere else; only this checklist item is stale. Classified as WARNING,
not critical — the implementation guidance is clear.

### C3 — transcript_path empirical validation + marker-file fallback: FIXED

Evidence: Phase 0 "Empirical validation (blocks all further Phase 0 work)" section
(lines 224-231). The diagnostic hook step is explicitly gating: "Deploy a 5-line
diagnostic PreToolUse hook that writes full stdin JSON to /tmp/... Run a live Claude
session, trigger a Bash tool call, capture the file." The marker-file pivot path is
documented (line 229-230). The `skill_invocation_sample.jsonl` fixture requirement is
added (line 231, confirmed in Sensitive surface inventory line 193). Phase 0 must
complete empirical validation before `_lib/transcript.py` is written.

### C4 — verdict_sha SKILL.md instruction ships with Phase 3: FIXED

Evidence: Phase 3 "Partial SKILL.md update" section (lines 355-368). The Stage 5
launch prompt template addition ("Before writing JSON output, run `git rev-parse HEAD`
(full 40-char hash, not `--short`) and record as `verdict_sha`") is explicitly placed
in Phase 3, not Phase 4. Phase 4 retains the Stage 0 and LL-6 changes only (lines
444-467). The schema update and the SKILL.md instruction now ship together.

### H1 — systemMessage key: FIXED

Evidence: Phase 1 implementation ("emit `{"systemMessage": "<reminder text>"}` to
stdout (verified against hookify production plugin — `systemMessage` is the correct
key; `additionalContext` is ignored)", lines 273-275). Architecture diagram (line
100: "systemMessage"). Phase 5 integration test (line 492: "Hook 1 reminder injected
(`systemMessage`)"). Decisions section (line 560). Consistent throughout.

HOWEVER: The Phase 1 reminder text itself (lines 281-282) tells users that "minimal"
and "trivial" are override phrases, which contradicts the fix for M1 (see new finding
NF1 below).

### H2 — Multi-feature scoping via active-feature marker: FIXED

Evidence: Scope section includes `specs/.tlmforge_active_feature` marker (lines 35-36).
Hook 3 architecture diagram (lines 160-161: "Reads specs/.tlmforge_active_feature →
scopes glob to specs/<feature>/agent_verification/final_audit_*.json"). Phase 3
implementation (lines 376-379). Phase 4 SKILL.md update adds marker write/delete
instructions at Stage 1 and Stage 7 (lines 452-457). If no marker is present → pass-
through (line 378). Contradiction resolved.

### H3 — Stage 5b naming collision + Phase 3-4 timing gap: FIXED

Evidence: Phase 3 explicitly says "PSR subsection to SKILL.md Stage 5 area (using
distinct name 'post-Stage-5 re-review' / abbreviation PSR, NOT 'Stage 5b' which
already means spec-drift review per LL-2)" (lines 362-364). Block message (lines
402-405) spells out the action inline without referencing any stage name. PSR marker
file pattern `final_audit_*_psr_<sha>.json` is consistent throughout. Phase 3 ships
both Hook 3 and the PSR SKILL.md subsection concurrently — timing gap closed.

Two residual "Stage 5b" mentions at lines 197 and 634 are in notes/verification text,
not prescriptive implementation text. Line 197 ("Stage 5b extended") is describing
what the SKILL.md section is called in existing code; line 634 ("Stage 5b post-commit
subsection") is a stale checklist item. Neither creates implementation ambiguity given
the Decisions section is unambiguous. Classified as WARNING.

### M1 — Override phrase false positives ("minimal", "trivial"): PARTIALLY FIXED

The override *library* (`_lib/overrides.py`) correctly removes bare "minimal" and
"trivial" — the override list is `["be quick", "just do it", "trivial fix"]` in the
implementation spec (Phase 0 line 237-238, Phase 2 line 315, Phase 3 line 173,
Decisions line 565-566).

BUT: The Phase 1 user-facing reminder text (lines 281-282) tells users to include
`be quick`, `minimal`, `trivial`, or `just do it` to bypass. This is now factually
wrong — Hook 2 and Hook 3 will NOT honor bare "minimal" or "trivial". A user who
reads the reminder and types "minimal" in their prompt will be blocked despite the
reminder's promise. This is a new regression introduced by the fix. See NF1 below.

### M2 — CI=true in architecture diagram: FIXED

Evidence: Architecture diagram (lines 82-179) contains no mention of CI=true or
GITHUB_ACTIONS. Risk audit table (line 533) explicitly states "CI=true NOT auto-
detected." Decisions section (lines 554-557) explicitly states CI=true and
GITHUB_ACTIONS are NOT honored. `TLMFORGE_HOOKS=0` is the sole bypass everywhere.

---

## New Findings (genuine misses from round 1)

### NF1 — Hook 1 reminder text contradicts the override phrase list (HIGH)

The Phase 1 reminder text injected via `systemMessage` (lines 281-282) tells users:

> To bypass enforcement on this message, include `be quick`, `minimal`, `trivial`,
> or `just do it` in your prompt.

But the implemented override library explicitly removes bare "minimal" and "trivial"
(lines 237-238, 565-566). Hook 2 and Hook 3 will not honor these phrases. A user
who reads the in-context reminder and responds with "minimal" or "trivial" will be
blocked — the hook tells them one thing and does another.

This is not a round-1 re-derivation: M1 was about the library behavior. This is
about the user-visible text that ships as the hook's primary communication channel,
which was updated inconsistently. The reminder is the user's first point of contact
with the enforcement system; misinformation here causes frustrated confusion
immediately on first use.

Fix: Update reminder text to `be quick`, `just do it`, or `trivial fix` (not bare
"minimal" or "trivial"). The reminder is the single source of truth a user will
consult when blocked.

### NF2 — Stale path in Verification Criteria (WARNING)

Line 623: "All 3 hooks ship in `hooks/`, wired in `.claude-plugin/hooks.json`"

The second half is wrong — hooks are wired in `hooks/hooks.json`, not
`.claude-plugin/hooks.json`. C2 fixed this everywhere in the implementation
guidance but missed the Verification Criteria checklist. An implementer
running through this checklist would pass it even if the wrong path were used.

Fix: Change to "All 3 hooks ship in `hooks/`, wired in `hooks/hooks.json`".

---

## Critical Issues (must fix before proceeding)

- **NF1**: The Phase 1 `systemMessage` reminder text tells users that "minimal" and
  "trivial" are valid overrides, but the override library explicitly does not honor
  them. First-time users will be confused and blocked. Fix: update the reminder text
  (lines 281-282) to list the actual override phrases: `be quick`, `just do it`,
  `trivial fix`.

## Warnings (should fix)

- **NF2**: Line 623 Verification Criteria checklist still says `.claude-plugin/hooks.json`
  — stale from pre-fix. An implementer checking completion against this line would be
  misled. Fix: change to `hooks/hooks.json`.

- **H3 residual**: Line 634 ("SKILL.md has Stage 0 + Stage 5b post-commit subsection")
  uses "Stage 5b" for the PSR concept — contradicts the renaming decision. Minor,
  but a stale checklist item in a verification document. Fix: change to "Stage 0 +
  PSR (post-Stage-5 re-review) subsection".

## Suggestions

- The integration test in Phase 5 (lines 495-500) only tests the Hook 3 allow path
  with a single PSR file (`final_audit_red-team_psr_B.json`). The block description in
  Phase 3 implies BOTH red-team and architect PSR files are needed. The integration
  test should add a step that verifies Hook 3 remains blocked when only ONE of the two
  PSR files exists, then unblocks when both are present. This is a gap in test coverage,
  not a plan defect.

## What's Good

- C1, C2, C3, C4, H1, H2, H3 are all solidly fixed with explicit, specific language.
  The empirical validation gating in Phase 0 is a significant improvement — it correctly
  treats `transcript_path` presence as an assumption to be verified before implementation
  begins, not after.
- The active-feature marker approach for H2 is the right scoping mechanism. The pass-
  through when the marker is absent is the correct default.
- The PSR rename is clean and consistent throughout the implementation sections. The
  block message in Phase 3 is self-contained (spells out the action without referencing
  a stage name) as recommended.
- EC-1 through EC-8 fixes from the tester are well-integrated. The edge cases
  (subagent pass-through, empty repo, short SHA normalization, rebase after SHA,
  subdirectory cwd) are all accounted for with explicit test cases.
- TLMFORGE_HOOKS multi-value acceptance (`{"0","false","no","off",""}`) is a practical
  improvement over single-value matching.
- The Phase 0 → Phase 5 ordering is correct: each phase is independently shippable,
  the no-op manifest commits first, empirical validation gates Phase 0 completion.
