# Threat Modeler Review — Round 3 (final)

**Feature:** enforcement-hooks
**Iteration:** 3
**Reviewer:** threat-modeler
**Verdict:** approve

---

## Round-2 finding disposition

### NEW-1 (MEDIUM) — Hook 1 reminder text contradicts Hook 2 override phrase list

**Verdict: FIXED**

The round-2 finding was: Hook 1's systemMessage advertised "minimal" and "trivial"
as bypass phrases, but Hook 2's overrides.py only accepted ["be quick", "just do it",
"trivial fix"]. A user following Hook 1's own instructions would be silently blocked.

**Evidence:** Phase 1 reminder text in the updated plan (README.md lines 280-283) now reads:

> To bypass enforcement on this message, include `be quick`, `just do it`, or
> `trivial fix` in your prompt. (Bare "minimal" / "trivial" are NOT accepted —
> they appear too often in technical prose.)

The three compound phrases in the systemMessage now exactly match the three phrases
in Hook 2's override list. The parenthetical explicitly calls out the removed phrases
and explains why. Block message in Hook 2 (Phase 2 steps) and Hook 3 (Phase 3 steps)
both list the same three phrases. The contradiction is resolved.

---

### LOW — Fail-open crash warning to stderr only; silent enforcement failure on persistent hook crash

**Verdict: NOT_FIXED (intentional deferral — accepted)**

The round-2 finding was: if safe.py's fail-open wrapper catches an exception on
every invocation, enforcement is silently disabled with no in-band signal visible
to the user (stderr from an exit-0 hook may not surface in Claude Code's UI).

**Evidence from round-2-fixes.md:**

> NOT fixed: Hook 1 emits to stdout (systemMessage); Hook 2/3 deny via exit(2) to
> stderr; crash-path warning to stderr only. Emitting warning to stdout would pollute
> the systemMessage channel and could confuse Claude. Deferred to tlmforge:doctor (Phase 6).

**Assessment:** The deferral rationale is sound. For Hook 1, stdout is the
systemMessage channel — writing a crash warning there would inject garbled text into
Claude's reasoning context. For Hooks 2/3, exit(2) is the deny path; exit(0) is the
fail-open path; there is no clean in-band channel available at exit(0). The tlmforge:doctor
plan (Phase 6) would provide an out-of-band diagnostic command to surface this state.

For a single-user CLI tool with no adversarial threat model (per feedback-threat-model-calibration),
the failure mode is reduced enforcement discipline, not data loss or unauthorized access.
The user can observe missing enforcement and run tlmforge:doctor to diagnose. Severity
remains low. The deferral is proportionate.

---

## New findings

None. No new trust assumptions were introduced by the round-2 fixes. The Phase 1
reminder text fix is purely additive text clarification; the CWD anchoring fix (NF2,
from tester) is an implementation correctness fix with no new security surface.
