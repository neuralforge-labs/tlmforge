# Threat Modeler Review — enforcement-hooks
## Round 1 (Cold Review) | Iteration 1

Reviewer: threat-modeler
Date: 2026-05-15
Verdict: needs_revision

---

## Framing

The relevant threat model here is discipline integrity on a single-user CLI tool,
not adversarial security. The question is: what does this design assume that could
silently cause the enforcement to not fire when it should, or to fire incorrectly?
Every finding is calibrated to that frame, not a multi-tenant/production-service frame.

---

## Finding 1 — HIGH: README and spec_audit contradict each other on CI bypass

**Design assumption violated:** the design assumes a single consistent bypass
mechanism. The spec_audit (F3) explicitly says "Don't auto-detect CI=true (too
magical, breaks the user's mental model)" and recommends TLMFORGE_HOOKS=0 only.
But the master plan's hook architecture diagram (lines 97-98 and 163-165 of README)
lists "Honors TLMFORGE_HOOKS=0. Fails open on crash." without mentioning CI=true,
while the launch prompt for this review says "Honor CI=true and GITHUB_ACTIONS."
If the implementation team reads the launch prompt or a different section as
authoritative, they may implement CI=true auto-bypass.

**Why this matters:** A developer who sets CI=true in their shell profile (a common
pattern for testing CI behavior locally) would bypass ALL three hooks on every
session forever — silently. They would never see Hook 1 reminders, Hook 2 would not
gate mutations, and Hook 3 would not gate commits. The discipline would be completely
disabled with no warning.

**Recommendation:** The master plan must explicitly state that CI=true and
GITHUB_ACTIONS are NOT honored. Only TLMFORGE_HOOKS=0 is the bypass. This must
appear in the env.py lib (the single source of truth), not in hook-specific code.
The contradiction between spec_audit F3 and the launch prompt must be resolved
before implementation begins, or different implementers will implement it differently.

---

## Finding 2 — HIGH: Skill invocation detection pattern is under-specified and unverified

**Design assumption violated:** Hook 2 assumes it can reliably detect a Skill tool
call in the Claude Code transcript JSONL by searching for a specific JSON shape.
The spec_audit (F5) says to match `tool_name: "Skill"` + `tool_input: {"skill":
"tlmforge:feature-development"}` as a JSON pattern. But the master plan (Phase 2
steps) says "is there a tool-call entry for Skill(tlmforge:feature-development) in
the task window?" without pinning the exact field names, nesting depth, or JSONL
record structure.

**Concretely:** Claude Code's transcript JSONL schema is not publicly documented
to the level of "what does a Skill tool invocation look like at the byte level?"
The design assumes the pattern is stable and known, but no fixture showing an actual
Skill-call transcript entry appears in the spec. If the actual record uses
`tool_name: "mcp__tlmforge__feature-development"` or `type: "tool_use"` with
`name: "Skill"` as a nested field, the substring/JSON search will miss it and
Hook 2 will block every mutation even after the skill was correctly invoked.

**Impact:** False-negative detection means Hook 2 permanently blocks all mutations
after skill invocation, destroying the user experience. False-positive detection
(matching prose) means Hook 2 never blocks when it should.

**Recommendation:** Before Phase 2 implementation, produce a single real transcript
snippet of an actual Skill tool call from Claude Code and commit it as a fixture in
`hooks/tests/fixtures/`. The detection code must match that exact shape. The Phase 0
conftest.py should build synthetic transcripts from this verified fixture, not from
an assumed structure. If the real shape cannot be captured before implementation,
the transcript.py lib must treat an unknown/missing field as "skill not found" (fail
toward blocking, not toward allowing) to avoid silent bypass.

---

## Finding 3 — HIGH: Stage 5b marker check is filename-only; content not verified

**Design assumption violated:** Hook 3 assumes that the presence of a file named
`final_audit_*_5b_<sha>.json` is sufficient evidence that a Stage 5b re-review
was actually conducted for that SHA.

**Attack path (single-user robustness failure, not malicious):** A user runs
Stage 5 at SHA A. They make new commits, reaching SHA B. Hook 3 blocks. They
invoke Stage 5b review, which writes `final_audit_red-team-reviewer_5b_<B>.json`
with `verdict_sha: B`. Later they make more commits reaching SHA C, and then
run `git checkout <B>` for any reason (bisect, cherry-pick, test). The marker
file for B still exists. If they then commit back to HEAD=C, Hook 3 looks for
a marker for C and correctly blocks. BUT: if the user accidentally copies or
renames the marker file (e.g., `cp final_audit_red-team-reviewer_5b_<B>.json
final_audit_red-team-reviewer_5b_<C>.json` during a cleanup), Hook 3 will pass
through even though no actual re-review happened for C.

More importantly: a git checkout followed by file operations (the normal IDE/git
workflow) can produce marker filenames with arbitrary SHAs through copy-paste
errors. The hook does not verify the `verdict_sha` field inside the JSON matches
the filename SHA.

**Recommendation:** When Hook 3 finds a Stage 5b marker file for HEAD, it must
also parse the file and confirm that the `verdict_sha` field inside equals HEAD.
If the internal SHA doesn't match the filename SHA, treat it as absent. Two lines
of additional JSON parsing in Phase 3.

---

## Finding 4 — MEDIUM: `git rev-parse HEAD` failure in non-git directory fails open (wrong direction)

**Design assumption violated:** Hook 3 assumes it always runs inside a git
repository with git on PATH. The fail-open wrapper catches subprocess failures
and exits 0 (allow), which means if git is not installed, or cwd is not a git
repo, Hook 3 silently passes every git commit command through.

**Why this is a concern:** The design's stated goal is "discipline integrity."
Fail-open is the right choice when a hook CRASH should not brick a session —
but for Hook 3, a git rev-parse failure is not a crash in the hook logic; it is
missing information that prevents the hook from doing its job. The correct behavior
when `git rev-parse HEAD` fails (not a git repo, or git missing) is to log a
warning to stderr and pass-through — which is what fail-open does. But the design
does not distinguish between "hook crashed due to Python error" and "hook couldn't
read git state." The latter should produce a more visible warning.

**Recommendation:** Distinguish two failure modes in Hook 3: (a) Python exception
in hook logic -> fail-open silently as designed. (b) git rev-parse non-zero exit
or git not found -> fail-open but with a stderr message at WARNING level: "tlmforge
Hook 3: could not read git HEAD (git not found or not a git repo). Stage 5 SHA
check skipped." This preserves fail-open semantics while making the bypass visible.

---

## Finding 5 — MEDIUM: "minimal" as override phrase fires on natural prose

**Design assumption violated:** Hook 2's override detection assumes that the word
"minimal" in a user message always signals an intentional override of the
enforcement gate.

**Concrete false-positive scenarios:**
- "Make minimal changes to the login flow" — user wants constrained scope, NOT
  override. Hook 2 would allow all mutations without skill invocation.
- "Use a minimal dependency footprint" — same.
- "Implement a minimal viable version" — same.

The design uses "case-insensitive substring match" (Phase 0 overrides.py,
confirmed in F10 spec_audit). The phrase "minimal" is a common English modifier
that appears frequently in technical requests. Unlike "be quick" or "just do it"
(which are meta-instructions about workflow velocity), "minimal" is a content
adjective about scope. A user writing "make minimal changes" is describing the
change, not instructing the hook.

**Recommendation:** Change the override phrase to "minimal override" or "use
minimal path" — a phrase that requires the user to consciously signal intent —
rather than bare "minimal". Alternatively, require "be quick" / "trivial" / "just
do it" as the recognized overrides and remove "minimal" from the list entirely.
The CLAUDE.md global rules already list the override phrases; align this design to
that list rather than expanding it.

---

## Finding 6 — MEDIUM: mtime-based "most recent verdict" is not reliable after git operations

**Design assumption violated:** Hook 3 uses file mtime to determine which
`final_audit_*.json` is the most recent Stage 5 verdict when multiple feature
specs exist.

**mtime is reset by:**
- `git checkout` (file is touched during tree reconstruction)
- `cp` / `rsync` / `tar x` (backup restore, file copy)
- Any operation that re-writes the file without changing content

**Failure mode:** After a `git stash pop` or `git checkout <branch>`, all
files under `specs/` have their mtime reset to the checkout time. If the user
is working on Feature B (newer in wall-clock time) and they checkout a branch
that includes Feature A's final_audit, Hook 3 may pick Feature A's verdict
as "most recent" based purely on which file was touched last by git.

**Recommendation:** Use the `verdict_sha` field inside the JSON to determine
which verdict applies to the current commit, not file mtime. The correct
logic is: "find all final_audit*.json files, extract verdict_sha from each,
find the one where verdict_sha is an ancestor of HEAD (via `git merge-base
--is-ancestor <sha> HEAD`), and use that as the anchor." This is git-native
and immune to mtime manipulation. If multiple feature specs have valid anchors,
the most recent by `git log` order (not mtime) wins.

---

## Finding 7 — MEDIUM: Task window "since last user message" is undefined for headless / programmatic sessions

**Design assumption violated:** Hook 2 assumes the Claude Code transcript always
contains a clear "last user message" event that can be used as the task window
boundary. The design notes that `--continue` works fine (F7 in spec_audit) but
does not address the case where Claude Code is invoked programmatically (e.g.,
via the API in headless mode, or via `claude -p "..."` one-shot mode).

In a one-shot `claude -p "add encryption to the login flow"` invocation, there
may be no prior user message in the transcript (the transcript is fresh), or the
message format may differ from an interactive session's format. Hook 2 would scan
"since last user message" but if no prior user message exists, the window is
the entire (empty) transcript — and no skill invocation would be found, correctly
blocking. BUT: if Hook 1 fires first and the skill is invoked in the same
synthetic flow, the window boundary logic needs to find that invocation.

**The precise gap:** the design does not specify what `transcript.py`'s
"last user message" detection does when there is zero or one user message in the
transcript. "Since last user message" with zero prior messages is ambiguous (window
= infinity? window = since session start?).

**Recommendation:** The transcript.py lib must specify: if fewer than two user
messages exist, the task window is the entire transcript from session start.
Document this in Phase 0 with an explicit test case: `test_hook2_first_message_in_session`.

---

## Finding 8 — LOW: Fail-open for Hook 2 means the primary enforcement gate silently disables on Python error

**Design assumption violated:** The design says "a crashing hook must not brick
the user's session" and documents fail-open as a trade-off. The mitigation is
the deferred `tlmforge:doctor` command (Phase 6, optional). But Phase 6 is
explicitly marked "OPTIONAL — DEFERRED" and "Skipping unless user pulls in."

**The gap:** If Hook 2's Python process crashes on every invocation (e.g., due
to a bad import, a Python version mismatch, or a corrupt transcript file), the
fail-open wrapper exits 0 for every mutation. The user's entire session proceeds
without enforcement. The user has no visibility into this unless they read stderr,
which Claude Code may not surface prominently.

**This is a LOW finding** because the fail-open is intentional and the
alternative (fail-closed) would be worse UX. But the mitigation (doctor command)
being deferred to an optional phase means there is no in-band signal to the user
that enforcement is silently disabled.

**Recommendation:** Hook 2 (and Hook 3) should emit a structured warning to
stdout when they fail-open, not just stderr. Claude Code surfaces stdout from
hooks in the conversation. A message like "[tlmforge] WARNING: enforcement hook
crashed; mutation gate disabled for this call. Run `tlmforge:doctor` to
diagnose." is visible to both Claude and the user. This does not require the full
doctor command — it just surfaces the failure in the conversation thread.

---

## Summary

| # | Severity | Component | Short description |
|---|---|---|---|
| 1 | HIGH | env.py / all hooks | CI=true bypass: spec_audit and README/launch-prompt contradict each other |
| 2 | HIGH | transcript.py / Hook 2 | Skill tool-call detection pattern unverified against real transcript format |
| 3 | HIGH | Hook 3 | Stage 5b marker checked by filename only; content SHA not verified |
| 4 | MEDIUM | Hook 3 | git rev-parse failure is indistinguishable from hook crash; wrong failure path |
| 5 | MEDIUM | overrides.py | "minimal" as bare substring matches natural prose, causing silent bypass |
| 6 | MEDIUM | Hook 3 | mtime-based verdict selection is unreliable after git operations |
| 7 | MEDIUM | transcript.py | Task window boundary undefined for zero/one user message (headless/first-message) |
| 8 | LOW | safe.py / Hook 2 | Fail-open with doctor deferred; no in-band warning when hook crashes repeatedly |

**Overall verdict: needs_revision.** No finding is CRITICAL (none has a concrete
attack chain with data loss, unauthorized access, or financial impact — this is
a single-user discipline tool). Three HIGH findings should be resolved before
implementation begins, because they affect core correctness of the detection
logic. The MEDIUM findings can be addressed in implementation but should have
explicit test cases. Finding 7 (task window boundary) is a design gap that
needs to be specified in transcript.py's interface contract before Phase 0 code
is written.
