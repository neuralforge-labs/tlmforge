# Round 1 Fixes — enforcement-hooks

All CRITICAL and HIGH findings from three reviewers addressed below.
Plan updated at `specs/enforcement-hooks/README.md`.

---

## CRITICAL Fixes

### C1 (architect) — Deny mechanism: exit(2) + stderr, not hookSpecificOutput JSON
**Finding:** Phase 2 planned `{"hookSpecificOutput": {"permissionDecision": "deny"}}` as stdout. Real Claude Code plugins use `sys.exit(2)` + block message to stderr.
**Fix:** Phase 2 implementation spec updated to `sys.exit(2)` + stderr text for deny path. JSON stdout path removed from deny logic. Test for `exit(2)` added to Phase 2 test list.

### C2 (architect) — hooks.json path: `hooks/hooks.json`, not `.claude-plugin/hooks.json`
**Finding:** `.claude-plugin/` contains only `plugin.json`. `hooks/hooks.json` at plugin root is the correct location per every real Claude Code plugin.
**Fix:** All references in Scope, Architecture, and Phase 0/1/2/3/5 updated to `hooks/hooks.json`. No-op `hooks/hooks.json` (`{"hooks": {}}`) is the first artifact created in Phase 0.

### C3 (architect) — transcript_path in PreToolUse stdin unverified; pivot path added
**Finding:** Real PreToolUse hooks read only `session_id`, `tool_name`, `tool_input`, `cwd`. If `transcript_path` is absent, Hook 2's skill detection silently fails (fail-open), making the gate a permanent no-op.
**Fix:** Phase 0 adds an explicit empirical validation step: deploy a 5-line diagnostic PreToolUse hook that writes full stdin JSON to a temp file, verify `transcript_path` is present and document the actual JSONL shape before `_lib/transcript.py` is written. Pivot path documented: if `transcript_path` is absent → use a marker-file approach (Hook 1 writes `~/.claude/tlmforge_skill_invoked_<session_id>` when skill fires; Hook 2 reads that file instead of transcript).

### C4 (architect) — verdict_sha needs explicit SKILL.md instruction in Stage 5 launch prompt
**Finding:** Adding the field to schema doesn't cause subagents to emit it. Stage 5 subagents won't run `git rev-parse HEAD` unless explicitly instructed.
**Fix:** Phase 3 now includes a partial SKILL.md update (the Stage 5 launch prompt template addition only): "Before writing JSON output, run `git rev-parse HEAD` and record as `verdict_sha` — required for post-Stage-5 gating." This ships with the schema update rather than waiting for Phase 4. Phase 4 retains the larger SKILL.md changes (Stage 0, post-Stage-5 re-review section, LL-6 wire-test).

---

## HIGH Fixes

### H1 (architect) — UserPromptSubmit output key: `systemMessage`, not `additionalContext`
**Finding:** Hookify (production plugin on this machine) uses `{"systemMessage": "..."}` as the stdout payload for context injection.
**Fix:** Phase 1 implementation spec updated to `{"systemMessage": "<reminder text>"}`. Test updated accordingly.

### H2 (architect) — Multi-feature Hook 3 scoping contradictory
**Finding:** Most-recent-by-mtime across all `specs/*/` picks one feature globally. Feature A's old verdict blocks Feature B's new commits incorrectly.
**Fix:** Hook 3 now uses a current-feature marker file (`specs/.tlmforge_active_feature`) written by the skill when it starts work on a feature (contains the feature directory name, e.g., `enforcement-hooks`). Hook 3 reads this marker to scope the glob to `specs/<active_feature>/agent_verification/`. If no marker → no active feature → pass-through. Phase 4 SKILL.md update adds instruction to write this marker at Stage 1 start and clear it at Stage 7 completion.

### H3 (architect) — Stage 5b naming collision + Phase 3→4 timing gap
**Finding:** SKILL.md already defines "Stage 5b" as spec-drift review (LL-2). Using the same label for post-commit re-review creates permanent confusion. Hook 3 (Phase 3) ships before SKILL.md defines the workflow (Phase 4), leaving users blocked with no actionable path.
**Fix:**
- Renamed throughout: "Stage 5b post-commit re-review" → "**post-Stage-5 re-review**" (abbreviated "PSR"). Marker files: `final_audit_*_psr_<sha>.json`. Block message now spells out the action inline without referencing a stage name.
- Phase ordering fix: Phase 3 ships simultaneously with the PSR workflow addition to SKILL.md (a targeted SKILL.md patch for just the PSR subsection). Phase 4 handles the remaining SKILL.md changes (Stage 0, LL-6). This closes the gap.

### EC-1 (tester) — Subagent sessions have no user messages; Hook 2 task window undefined
**Finding:** Stage 3/4 reviewer subagents have zero `type: user` messages in their transcript. Hook 2's "scan since last user message" has no anchor → either blocks all subagent mutations or crashes.
**Fix:** Phase 2 spec explicitly adds: "If transcript has no user-message entries, emit pass-through immediately." Test `test_hook2_no_user_messages.py` added to Phase 2 list.

### EC-2 (tester) — Empty repo: `git rev-parse HEAD` exits 128
**Finding:** Fresh `git init` with no commits returns exit code 128. Hook 3 gets empty string, permanent garbled block.
**Fix:** Phase 3 spec: "After running `git rev-parse HEAD`, check returncode. Non-zero → write WARNING to stderr and pass-through." Test `test_hook3_no_commits.py` added.

### EC-3 (tester) — Short SHA in verdict_sha causes permanent false block
**Finding:** Reviewer records short hash (e.g., `1424797`). `git rev-parse HEAD` returns 40-char hash. Comparison always fails. No subsequent push clears it without `TLMFORGE_HOOKS=0`.
**Fix:** Phase 3 spec: "Normalize verdict_sha to 40 chars via `git rev-parse <verdict_sha>` before comparison." SKILL.md Stage 5 prompt addition (Phase 3 partial): "Record `git rev-parse HEAD` (full 40-char hash, not `--short`)." Test `test_hook3_short_sha_verdict.py` added.

### EC-4 (tester) — Transcript partial-write race: truncated JSONL line
**Finding:** Hook fires mid-write. Last line truncated → `json.JSONDecodeError` propagates → fail-open → silent bypass of Hook 2.
**Fix:** Phase 0 `_lib/transcript.py` spec: "Wrap `json.loads(line)` in per-line `try/except JSONDecodeError`. Skip malformed lines, continue iteration." Test `test_transcript_partial_write.py` added to Phase 0.

### EC-5 / M1 / MEDIUM-2 — Override phrase false positives: "minimal", "trivial"
**Finding:** Common technical phrases ("minimal logging", "trivially false") trigger override accidentally. Confirmed by all three reviewers.
**Fix:** Override phrase list updated:
- **Removed:** `"minimal"`, `"trivial"` (too many false positives in technical prose)
- **Retained:** `"be quick"`, `"just do it"`, `"trivial fix"` (compound forms, inherently intentional)
Phase 0 `test_overrides.py` includes false-positive cases.

### EC-6 (tester) — Hook 3 cwd relative glob fails in subdirectory
**Finding:** Running `claude` from a project subdirectory → `specs/*/` glob finds nothing → Hook 3 passes through → Stage 5 verdict silently ignored.
**Fix:** Phase 3 spec: "Use `git rev-parse --show-toplevel` to find repo root; anchor glob to `<repo_root>/specs/<active_feature>/agent_verification/`. If git call fails → pass-through with WARNING." Test `test_hook3_cwd_subdirectory.py` added.

### EC-7 (tester) — TLMFORGE_HOOKS bypass too narrow: only "0" accepted
**Finding:** `TLMFORGE_HOOKS=false`, `TLMFORGE_HOOKS=`, `TLMFORGE_HOOKS=no` don't trigger bypass. Common in CI scripts.
**Fix:** Phase 0 `_lib/env.py` spec: "Accept `{'0', 'false', 'no', 'off', ''}` (case-insensitive) as bypass values." Test `test_env_bypass_variants.py` added.

### EC-8 (tester) — Rebase: verdict_sha not in history, git rev-list fails
**Finding:** After rebase, `git rev-list <verdict_sha>..<HEAD> --count` exits non-zero → hook crashes → fail-open → post-rebase commits bypass PSR gate silently.
**Fix:** Phase 3 spec: "Wrap `git rev-list` in try/except. On failure, log WARNING and still block (HEAD != verdict_sha is still true); display '?' for commit count in block message." Test `test_hook3_verdict_sha_not_in_history.py` added.

### HIGH-1 (threat-modeler) — CI=true contradicts spec_audit F3 decision
**Finding:** My launch prompt for Round 1 introduced CI=true/GITHUB_ACTIONS as bypass signals, contradicting spec_audit F3 which explicitly rejected auto-detecting CI env vars ("too magical"). Spec_audit F3 decision stands: TLMFORGE_HOOKS=0 is the ONLY bypass.
**Fix:** Removed CI=true and GITHUB_ACTIONS from Architecture diagram and all bypass logic. TLMFORGE_HOOKS=0 is sole bypass. README install docs instruct CI pipelines to set this env var explicitly.

### HIGH-2 (threat-modeler) — Skill-call detection pattern unverified against real transcript
**Finding:** If real Claude Code transcript uses a different JSON shape for Skill invocations than assumed (e.g., MCP-style tool name), Hook 2 will never detect skill as invoked.
**Fix:** Phase 0 adds: "Capture one real Skill tool-call JSONL record from a live session and commit as `hooks/tests/fixtures/skill_invocation_sample.jsonl`. Detection logic in `_lib/transcript.py` is written against this verified shape." This is blocked by C3's empirical validation step (both happen in Phase 0).

### HIGH-3 (threat-modeler) — PSR marker validated by filename only, not internal SHA
**Finding:** File named `*_psr_<sha>.json` with wrong or missing internal `verdict_sha` passes the filename check, unblocking commits with no real re-review.
**Fix:** Phase 3 spec: "After finding a PSR marker by filename, parse it and assert `internal verdict_sha == HEAD`. Mismatch or missing field → treat file as absent." Test `test_hook3_psr_marker_sha_mismatch.py` added.

---

## MEDIUM Fixes (selected)

### MEDIUM-1 (threat-modeler) — git subprocess failure visibility
**Fix:** Phase 3: differentiate `subprocess.CalledProcessError` / `FileNotFoundError` from generic exceptions. Specific git failures write visible WARNING to stderr before pass-through.

### MEDIUM-3 (threat-modeler) — mtime for multi-verdict ordering
**Fix:** (Moot given H2 fix: active-feature marker scopes glob to one feature dir. Only one final_audit per feature is expected.)

### MEDIUM-4 (threat-modeler) / EC-1 (tester) — Task window with zero/one user messages
**Fix:** Covered by EC-1 fix: "no user messages → pass-through immediately." First user message as anchor works correctly per the tester's analysis.

---

## NOT Fixed (intentional deferrals)

- **EC-9** (git merge): Local `git merge` not in pattern — scoped to `git push` as the true "ship" gate; local merges without push can be Stage 5b'd before push.
- **EC-10** (compound bash): `cd && git commit` bypass — low real-world frequency; Hook 2 still gates Edit/Write independently.
- **EC-11** (benchmark fixtures): Both transcript shapes added to conftest. Minor.
- **EC-12** (5b naming): Resolved by H3 fix (renamed to PSR with explicit spec).
- **M3** (architecture, no-op hooks.json): Added to Phase 0.
- **L1** (CI=true in diagram): Resolved by HIGH-1 fix.
- **L2** (atomic write): Added to Phase 3 explicitly.
