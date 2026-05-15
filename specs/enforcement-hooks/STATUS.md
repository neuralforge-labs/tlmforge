# enforcement-hooks — Status

**TL;DR:** Three Claude Code hooks ship automatically with the plugin and enforce
the feature-development discipline end-to-end. All phases complete, 126 tests
passing, Stage 5 red-team CRITICAL findings fixed and re-verified. Shipping as v0.5.5.

## Phase status

| Phase | What | Tests added | Commit | Status |
|---|---|---|---|---|
| 0 | Scaffolding: shared lib (env, safe, overrides, transcript), hooks.json skeleton, empirical validation of hook payload schemas | +69 | def6757 | ✅ |
| 1 | Hook 1 — UserPromptSubmit reminder injector | +7 | 1991ef9 | ✅ |
| 2 | Hook 2 — PreToolUse mutation gate (skill required or override phrase) | +17 | 1991ef9 | ✅ |
| 3 | Hook 3 — post-Stage-5 commit/push gate (verdict_sha anchoring + PSR markers) | +18 | 1991ef9 | ✅ |
| 4 | SKILL.md: Stage 0 early-exit, active-feature marker (Stage 1/7), LL-6b wire-test rule | doc-only | 4620576 | ✅ |
| 5 | Integration tests (9), README hook docs, CHANGELOG 0.5.5, version bump | +9 | 4620576 | ✅ |
| S5-fix | Stage 5 red-team CRITICAL fixes (C-1 hex SHA validation, C-2 regex search, C-3 feature-name sanitization) + 6 new security tests | +6 | 280e3b8 | ✅ |

**Total new tests: 126. Passing: 126. Regressions: 0.**

## Test counts across phases

```
Pre-feature baseline:   0 (new hooks/ directory)
After Phase 0:         69 passing
After Phase 1:         76 passing
After Phase 2:         93 passing
After Phase 3:        111 passing
After Phase 5:        120 passing
After S5-fix:         126 passing
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  User prompt                                                    │
│       │                                                         │
│       ▼ UserPromptSubmit                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Hook 1: load_feature_dev_skill.py                        │   │
│  │ → systemMessage: "invoke Skill(tlmforge:feature-dev)"    │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼ Claude responds — may call Skill(tlmforge:feature-dev)  │
│       │                                                         │
│       ▼ PreToolUse (Edit|Write|Bash|MultiEdit)                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Hook 2: enforce_skill_invoked.py                         │   │
│  │ reads transcript → skill in task window?                 │   │
│  │   YES / override phrase → allow                          │   │
│  │   NO → exit(2) block                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼ PreToolUse (Bash only — git commit/push/gh pr merge)    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Hook 3: enforce_post_stage5_review.py                    │   │
│  │ reads specs/.tlmforge_active_feature                     │   │
│  │ reads final_audit_*.json → verdict_sha (hex only)        │   │
│  │ compares to git HEAD                                     │   │
│  │   HEAD == verdict_sha → allow                            │   │
│  │   HEAD != verdict_sha:                                   │   │
│  │     valid PSR marker? → allow                            │   │
│  │     override phrase?  → allow                            │   │
│  │     else → exit(2) block                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Operator runbook

**Disable for a session:** `export TLMFORGE_HOOKS=0`

**Override Hook 2 per-task:** include `be quick` / `just do it` / `trivial fix` in prompt

**Unblock Hook 3 after post-Stage-5 commits:** write a PSR marker:
```
specs/<feature>/agent_verification/final_audit_<role>_psr_<HEAD-sha>.json
```
with internal `verdict_sha` = full 40-char HEAD SHA.

**Remove all hooks:** `claude plugin remove tlmforge`

**Active-feature marker cleanup** (if feature abandoned before Stage 7):
```bash
rm specs/.tlmforge_active_feature
```

## What's NOT done

- `tlmforge:doctor` slash command (Phase 6, deferred) — diagnostic for users hitting hook issues
- Transcript-path fallback for Hook 2 (architect H-2) — fail-open already handles the absent-field case; the dependency on `transcript_path` being present in Claude Code's PreToolUse payload is undocumented but empirically confirmed
- Phase 1/2 standalone evidence files — batched with Phase 3 commit

## Honest assessment for an external reviewer

**Strengths:**
- All three hooks fail open on crash — no session-bricking failure mode
- SHA anchoring is cryptographically sound: hex-only validation blocks ref-name injection (C-1), regex search catches compound commands (C-2), feature-name sanitization blocks path traversal (C-3)
- 126 tests covering unit, integration, and security edge cases
- Stage 3 + Stage 5 both found and fixed real bugs — process paid for itself

**Weaknesses:**
- Hook 2's tool-result bypass (RT-H1) is fixed at text-extraction level but the fundamental issue — transcript is a local file the developer controls — is inherent to the single-user CLI architecture. An intentionally adversarial developer can always bypass by appending to the transcript file. This is documented and accepted.
- `TLMFORGE_HOOKS=0` is the nuclear bypass and requires no justification — intentional by design (single-user tool, no malicious threat model), but means enforcement is always opt-out.

Net: **ready to ship** as v0.5.5.
