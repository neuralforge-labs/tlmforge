# enforcement-hooks — Spec Audit

## What the user asked for

Build the structural enforcement layer for tlmforge so the discipline runs
*regardless* of whether Claude (or the user) remembers to invoke the
feature-development skill. Three hooks plus a SKILL.md tightening:

1. `UserPromptSubmit` hook — always inject a system-reminder telling Claude
   to invoke `Skill(tlmforge:feature-development)`. Pure injection, no
   classification logic in the hook.
2. `PreToolUse[Edit, Write, Bash]` hook — block mutation if the skill was
   not invoked for the current task and no override phrase was given.
3. `PreToolUse[Bash]` on `git commit` / `git push` / `gh pr merge` — block
   if HEAD has advanced past the Stage 5 verdict SHA without a Stage 5b
   re-review marker.
4. SKILL.md update: extend Stage 5b to cover post-Stage-5 commit re-review
   explicitly; tighten tester agent's wire-test requirement to address LL-6.

The triggering observation: in another session, Claude declared "Stage 5
GATE_OPEN_FOR_STAGE_6" at one SHA and then shipped 4 more substantive
commits against new SHAs that no auditor saw. The skill prose said this
was a violation (LL-1, LL-8) but nothing structural prevented it.

## Industry standard / how others do this

- **Anthropic Code Review plugin**: PreToolUse hooks gate sensitive
  mutations. No multi-stage workflow enforcement.
- **claude-mem (thedotmack)**: ships UserPromptSubmit + PostToolUse hooks
  for memory injection. Same delivery mechanism we'll use. Hooks declared
  in `plugin/hooks/hooks.json`, bash commands, `CLAUDE_PLUGIN_ROOT` resolves
  the install path.
- **superpowers**: prose discipline only; no programmatic enforcement.
- **husky / lefthook / pre-commit**: standard pattern in non-AI tooling — a
  pre-commit gate that blocks mutations until quality criteria pass. The
  closest analog. We're applying the same pattern at the AI workflow layer.

The closest prior art for "pre-mutation gate that consults a workflow state"
is the husky+commitlint pattern. None of the AI plugins surveyed do this
because none of them have a multi-stage workflow to gate against.

## Findings (severity-ranked)

### CRITICAL — Decisions needed before any code

#### F1. Override scope semantics — per-prompt vs sticky-session
- **Spec said:** "phrases 'be quick' / 'minimal' / 'trivial' / 'just do it'
  in any user message bypass hooks 2 and 3."
- **Industry standard:** husky/lefthook overrides are per-invocation only
  (`HUSKY=0 git commit`). git's own `--no-verify` flag is per-command.
- **Problem:** "Any user message" is ambiguous. If user says "be quick" in
  message N, does that override stay in effect for messages N+1 through
  end-of-session? Or only for the next mutation?
  - **Sticky-session semantics:** user has to remember to "re-arm" the gate
    for the next task — which is *exactly the failure mode we're trying to
    fix*. They will forget.
  - **Per-prompt semantics:** override applies to the immediately-following
    work cycle, then resets. Aligned with husky pattern. But "task boundary"
    is fuzzy — when does the cycle end?
- **Recommendation:** Per-prompt override that resets at the next user
  message. The override applies to all mutations between user message N
  (which contained the override phrase) and user message N+1. After N+1,
  the gate re-arms unless N+1 also contains an override phrase.
- **Decision required:** [GATE-BLOCKING] Confirm per-prompt-with-reset
  semantics, or specify alternative.

#### F2. Distribution mechanism — plugin-shipped vs slash-command-installed
- **Spec said:** "plugin wiring so they auto-install."
- **Industry standard:** Claude Code plugins ship hooks via
  `plugin/hooks/hooks.json` and they activate on `claude plugin add`
  (verified against thedotmack/claude-mem). No user action beyond install.
- **Problem:** Two paths with different tradeoffs:
  - **Plugin-shipped (auto):** hooks activate immediately on `claude
    plugin add github:neuralforge-labs/tlmforge`. Better UX, no manual step.
    Risk: a user installing tlmforge to *try it out* gets aggressive
    PreToolUse blocks on their first mutation, which may feel hostile.
    Mitigation: Hook 2 only blocks when prompt was actually a work
    request (skill must have been needed) — for "show me X" prompts the
    skill itself will exit without doing anything, so no block fires.
  - **Slash-command installed (`/tlmforge:install-hooks`):** explicit
    user opt-in writes hooks to `~/.claude/settings.json`. Higher trust
    threshold; user knows what they're getting. But adds a manual step
    that 50% of installers will skip — which is exactly the "nobody uses
    it" problem we're solving.
- **Recommendation:** Plugin-shipped (auto). Pair with a single
  `<system-reminder>` injected at SessionStart explaining "tlmforge hooks
  are active; override with 'be quick' or uninstall via `claude plugin
  remove tlmforge`." Lowers the surprise factor without sacrificing the
  default-on enforcement.
- **Decision required:** [GATE-BLOCKING] Confirm plugin-shipped, or
  prefer manual-install.

#### F3. CI / automated `git commit` / agentic workflows
- **Spec said:** nothing.
- **Industry standard:** husky honors `HUSKY=0` env var. lefthook honors
  `LEFTHOOK=0`. CI runners commonly set `CI=true`.
- **Problem:** If a CI pipeline (or a release script, or a bot) runs
  `git commit` inside a tlmforge-installed environment, Hook 3 will
  block it because there's no Stage 5 verdict in the transcript at all.
  This breaks `gh pr merge` automation, `npm version`, release tooling.
  Even local `git commit` inside a non-Claude shell won't trigger the
  hook (Claude Code is the host) — but anything Claude itself runs in a
  Bash subagent will.
- **Recommendation:** Honor `TLMFORGE_HOOKS=0` environment variable as a
  full-bypass. Don't auto-detect `CI=true` (too magical, breaks the
  user's mental model). Document the env var in README. Hook scripts
  check the env var as the FIRST line and exit pass-through if set.
- **Decision required:** [GATE-BLOCKING] Confirm `TLMFORGE_HOOKS=0` as
  the bypass mechanism, or specify alternative.

### HIGH — Should fix before launch

#### F4. Hook performance budget
- **Problem:** PreToolUse[Edit, Write, Bash] fires on EVERY mutation. If
  the hook takes 200ms, a 50-edit phase adds 10 seconds of wall time. The
  transcript scan must be sub-50ms even on a 100K-token transcript file.
- **Recommendation:** Hook reads the transcript file path from the JSON
  Claude Code passes on stdin, performs ONLY substring search (no full
  parse), exits in <50ms. Benchmark in Phase 0 with a synthetic 1MB
  transcript. If we can't hit the budget, fall back to a marker-file
  cache: hook writes `~/.claude/state/tlmforge/<session-id>.passed` on
  first allow, subsequent calls just `stat` the file.

#### F5. Skill-invocation detection — false positives and negatives
- **Problem:** "Skill was invoked" detection is a substring search for
  `Skill(tlmforge:feature-development)` in the transcript. False positives:
  user prose like `"don't invoke Skill(tlmforge:feature-development) on
  this"` matches. False negatives: skill invoked under an alias or namespace
  variant.
- **Recommendation:** Match the structured tool-call shape, not the prose
  shape. Claude Code's transcript stores tool calls as JSON entries with
  `tool_name: "Skill"` + `tool_input: {"skill": "tlmforge:feature-development"}`.
  Search for that JSON pattern, not free text. False-positive rate → near
  zero.

#### F6. Stage 5 SHA detection — what gets recorded and where
- **Problem:** The post-Stage-5 hook needs to know:
  (a) was a Stage 5 verdict produced in this conversation, and
  (b) what SHA was HEAD when that verdict was produced.
  Today the skill writes `final_audit_*.{md,json}` files but doesn't
  record the SHA. Without an explicit anchor, the hook has no way to
  detect "HEAD has moved past it."
- **Recommendation:** Stage 5 final_audit_*.json schema gains a required
  `verdict_sha:` field. Skill prompt template updated to instruct reviewers
  to record `git rev-parse HEAD` at verdict time. Hook 3 reads
  `specs/*/agent_verification/final_audit_*.json`, extracts the highest
  `verdict_sha`, compares to current HEAD. Stage 5b re-review writes
  `final_audit_*_5b_<new_sha>.json` to bump the anchor.

#### F7. Cross-session continuity (`claude --continue` / resumed sessions)
- **Problem:** A user runs `claude` in session A, gets through Stage 5,
  closes the terminal. Next day runs `claude --continue` — same session
  ID, same transcript. They make a small fix and commit. Hook 3 sees the
  Stage 5 verdict in the transcript and the SHA mismatch, blocks. This is
  the CORRECT behavior. But: the user might have intended the fix as a
  trivial follow-up (typo, comment). The override path ("be quick") in
  the new prompt handles this — confirms the design works across sessions
  *if* the override mechanism is robust.
- **Recommendation:** No additional logic needed — F1's per-prompt
  override semantics resolve this naturally. Document the pattern in
  README ("if you resume a session and need to ship a follow-up, prefix
  your prompt with 'be quick' to bypass the post-Stage-5 gate").

### MEDIUM

#### F8. Hook timeout discipline
- **Problem:** Claude Code hooks have a default timeout (60s seen in
  thedotmack). If our hook hangs, it blocks the user.
- **Recommendation:** Set explicit `timeout: 5` (5 seconds, generous for
  what should be sub-50ms work). Hook script wraps logic in
  `signal.alarm(3)` defensively.

#### F9. Hook failure mode — fail-open vs fail-closed
- **Problem:** If the hook script crashes (Python missing, permission
  denied, file IO error), what happens?
- **Recommendation:** **Fail-open with stderr warning.** A bug in tlmforge
  must not brick the user's Claude Code session. Hook script wraps the
  entire body in `try/except`, on exception writes a warning to stderr
  and exits 0 (allow). User sees the warning but their work proceeds.
  Trade-off: a crashing hook silently disables enforcement. Mitigated by
  `tlmforge:doctor` (Stage 6 of this plan) which runs the hooks
  end-to-end and reports failures.

#### F10. Override phrase normalization
- **Problem:** "Be quick" vs "be quick" vs "Be Quick!" — case, punctuation,
  whitespace.
- **Recommendation:** Lowercase + strip + substring match. Override
  phrases: `["be quick", "minimal", "trivial", "just do it", "trivial fix"]`.
  Match against any user message in the current task window.

#### F11. First-run experience
- **Problem:** A user who installs tlmforge to evaluate it gets an
  immediate `<system-reminder>` injected into their first prompt. Without
  context, this looks like spam.
- **Recommendation:** SessionStart hook (one-time per session) injects a
  brief "tlmforge is active — type 'be quick' to bypass" reminder. The
  per-prompt UserPromptSubmit reminder is shorter (just the skill
  invocation instruction).

### LOW

#### F12. Block message clarity
- **Problem:** When Hook 2 or 3 blocks a mutation, the user sees a wall of
  text. They need to understand WHY and HOW to proceed.
- **Recommendation:** Block messages are 3 lines max: what was blocked,
  why, how to proceed (skill invocation OR override phrase).

#### F13. Diagnostics / `tlmforge:doctor`
- **Problem:** When something goes wrong, debugging is hard.
- **Recommendation:** Phase 6 (optional, can defer): `tlmforge:doctor`
  slash command that prints hook installation status, runs each hook with
  a synthetic transcript, reports pass/fail.

#### F14. Documentation accuracy
- **Problem:** README, CHANGELOG, and SKILL.md must all reflect the new
  enforcement layer consistently.
- **Recommendation:** Phase 5 covers all docs in lockstep with code.

#### F15. Test scaffolding
- **Problem:** Hook scripts need tests. Pattern not yet established in this
  repo.
- **Recommendation:** `hooks/tests/` with pytest, fixtures for synthetic
  transcripts representing every state machine path (no skill invoked,
  skill invoked, override given, post-stage5 SHA mismatch, etc.).

## Coverage of mandatory surfaces

(a) **Security surface** — Per `feedback-threat-model-calibration`, this is
single-user CLI; no external attackers. The relevant "security" framing is
**discipline integrity**: F4, F5, F6, F9 cover the cases where the hook
might silently fail to gate when it should. Not a hostile-attacker model.

(b) **Concurrency / races / idempotency** — Hooks are invoked
synchronously by Claude Code per tool call; no concurrency within a
single session. Cross-session state (the marker file in F4 fallback) needs
atomic write (`*.tmp` → `mv`) — addressed in implementation. No findings
beyond F4.

(c) **Failure modes under partial failure** — F8 (timeout), F9 (crash),
F4 (slow transcript). All covered. Network-down: hooks are local-only,
no network deps.

(d) **Cost impact** — Hook 1 injects ~50 tokens per prompt. At 50 prompts/
day per user that's ~2.5K tokens of overhead per user-day. Negligible.
SKILL.md load (~6-8K tokens) is one-time per task and benefits from
Anthropic's prompt cache. No new findings.

(e) **Rollback safety** — User can `claude plugin remove tlmforge` to
fully disable. Or `TLMFORGE_HOOKS=0` env var to bypass. Or per-prompt
override. Three escape hatches.

(f) **Downstream consumers / background subsystems (per LL-4)** — Hooks
modify the prompt context Claude sees and gate Bash/Edit/Write tool
calls. Downstream: every Claude Code session that has tlmforge installed.
A bug in the hook silently breaks every user's Claude Code experience.
Mitigations: F9 fail-open, F13 doctor command.

## Open questions for the user

1. **[GATE-BLOCKING]** F1 — Override scope: confirm **per-prompt with
   reset on next user message**, or specify sticky-session / per-task /
   other?
2. **[GATE-BLOCKING]** F2 — Distribution: confirm **plugin-shipped
   (auto-active on `claude plugin add`)**, or prefer
   slash-command-installed?
3. **[GATE-BLOCKING]** F3 — CI/automation bypass: confirm
   **`TLMFORGE_HOOKS=0` env var as the only bypass**, or add auto-detect
   for `CI=true` / other?
4. **[INFORMATIONAL]** Should Hook 3 also gate `gh pr create`? Risk: PR
   creation happens after commit/push, so blocking commit/push already
   prevents the workflow from reaching PR creation. Adding `gh pr create`
   is belt-and-suspenders. Default: no.
5. **[INFORMATIONAL]** Should we ship `tlmforge:doctor` (F13) in this
   release or defer? Default: defer to a follow-up.
6. **[INFORMATIONAL]** SKILL.md gets a new **Stage 0** ("is this even a
   work request?") to handle the case where the always-load skill fires
   on a conversational prompt like "what does this file do?" Default:
   include in Phase 4 of the plan.
