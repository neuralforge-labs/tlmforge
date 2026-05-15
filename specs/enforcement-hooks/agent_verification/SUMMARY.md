# Agent Verification — Stage 3 Consolidated (enforcement-hooks)

| Reviewer | R1 verdict | R2 verdict | R3 verdict | Final |
|---|---|---|---|---|
| architect-reviewer | needs_revision (4C/3H/2M/1L) | needs_revision (1C new/2W) | approve (1 nit fixed) | **APPROVE** |
| tester | needs_revision (4C/4H/4M/2L) | approve_with_warnings (2M new) | approve (2M fixed) | **APPROVE** |
| threat-modeler | needs_revision (3H/4M/1L) | approve_with_warnings (1M new) | approve (1L deferred) | **APPROVE** |

## What was actually broken (Round 1)

### Category 1: Wrong Claude Code plugin API shapes
Hook deny mechanism (`hookSpecificOutput` JSON) and context injection key (`additionalContext`) were both wrong against real installed plugins. Real plugins use `sys.exit(2)` + stderr for deny and `{"systemMessage": "..."}` for context injection. Would have shipped a no-op enforcement layer.
**Fixed:** Both corrected to match real plugin behavior.

### Category 2: Wrong file path for hooks.json
Plan specified `.claude-plugin/hooks.json` — that directory contains only `plugin.json`. Real plugins use `hooks/hooks.json` at plugin root. Would have silently ignored all hook configuration.
**Fixed:** All references updated to `hooks/hooks.json`.

### Category 3: Unverified transcript payload assumption
Hook 2's entire skill-detection mechanism depended on `transcript_path` being present in PreToolUse stdin. Real plugins read `session_id`, `tool_name`, `tool_input`, `cwd` — not a transcript path. Phase 0 now has a blocking empirical validation step that captures the real payload before any transcript parsing code is written, with a marker-file fallback path.
**Fixed:** Phase 0 gating step + fallback design added.

### Category 4: verdict_sha would never be emitted
Adding the field to the JSON schema doesn't cause Stage 5 subagents to run `git rev-parse HEAD` and record the SHA. Without the explicit SKILL.md instruction, Hook 3 would gate nothing for real features. The instruction was moved from Phase 4 to Phase 3 (ships with the schema update).
**Fixed:** Phase 3 now includes partial SKILL.md update with Stage 5 prompt instruction.

### Category 5: Multi-feature Hook 3 cross-contamination
Original design globbed all `specs/*/` and picked by mtime. Feature A's old Stage 5 verdict would block Feature B's commits. Contradicted the "independently gated" language in the risk table.
**Fixed:** Active-feature marker file `specs/.tlmforge_active_feature` scopes Hook 3 to one feature at a time.

### Category 6: Stage 5b naming collision + timing gap
"Stage 5b" in SKILL.md already means spec-drift review (LL-2). Post-commit re-review using the same name would create permanent confusion. Hook 3 also shipped before the SKILL.md definition, leaving users blocked with no actionable path.
**Fixed:** Renamed to "post-Stage-5 re-review" (PSR); PSR SKILL.md section now ships with Phase 3.

### Category 7: Override phrase false positives
Bare "minimal" and "trivial" match common technical phrases ("minimal config", "trivially false") — would bypass enforcement accidentally.
**Fixed:** Removed from override list. Retained: `["be quick", "just do it", "trivial fix"]`.

### Category 8: Subagent sessions have no user messages
Stage 3/4 reviewer subagents have zero user-message entries. Hook 2's "task window since last user message" had no anchor — could permanently block all subagent mutations, breaking the recipe's own stage execution.
**Fixed:** Hook 2 passes through immediately if no user messages in transcript.

### Category 9: git edge cases (empty repo, short SHA, rebase, subdirectory cwd)
Multiple git subprocess failure modes not handled: zero commits → exit 128; short SHA comparison always fails; verdict SHA unreachable after rebase; cwd relative glob fails from subdirectory.
**Fixed:** returncode check; SHA normalization; graceful rebase handling; `git rev-parse --show-toplevel` for repo root (covering both marker file + glob path).

### Category 10: CI=true bypass contradiction
My Round 1 review prompt accidentally introduced CI=true/GITHUB_ACTIONS as bypass signals, contradicting spec_audit F3's explicit decision not to auto-detect CI env vars. TLMFORGE_HOOKS=0 is the sole bypass.
**Fixed:** CI auto-detection removed everywhere. TLMFORGE_HOOKS now accepts multiple false-y values ("0", "false", "no", "off", "").

## Deferred (with rationale)

- **LOW (threat-modeler): fail-open warning only to stderr.** Emitting to stdout would pollute the systemMessage channel. Deferred to `tlmforge:doctor` (Phase 6). Single-user CLI; not a blocking defect.
- **EC-9 (tester): `git merge` not in Hook 3 pattern.** Local merges without push still gate before push. Acceptable.
- **EC-10 (tester): compound bash (`cd && git commit`).** Low real-world frequency; Hook 2 still gates Edit/Write independently.

## Carryover artifact

`tester_edge_cases.json` — 8 scenarios (EC-1 through EC-8) for Stage 4 TDD seed. Each maps to a Phase 2 or Phase 3 test case already reflected in the TDD plan.
