# Phase 0 Evidence — enforcement-hooks

## What was built

Scaffolding: hook directory structure, shared `_lib/` modules, test harness.
No enforcement behavior yet — all hooks are empty / no-op.

## Empirical validation results

**PreToolUse stdin payload (from security-guidance plugin source):**
`{"session_id": "...", "tool_name": "...", "tool_input": {...}, "cwd": "..."}`

**Skill invocation shape in transcript JSONL:**
```json
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "tlmforge:feature-development"}}]}}
```
Verified from live session transcript at:
`~/.claude/projects/-home-user-tlmforge/b76a3588-b0a4-42b3-aa39-62df34e713ea.jsonl`

**PreToolUse deny mechanism:** `sys.exit(2)` + message to stderr.
Verified from `security_reminder_hook.py` line 273: `sys.exit(2)  # Block tool execution`.

**UserPromptSubmit context injection:** `{"systemMessage": "..."}`
Verified from hookify `userpromptsubmit.py`.

**hooks.json location:** `hooks/hooks.json` at plugin root (not `.claude-plugin/`).
Verified from security-guidance, hookify, and superpowers plugin structures.

**`transcript_path` in PreToolUse stdin:** confirmed present via existing
`ExitPlanMode` hook in `~/.claude/settings.json` which reads `transcript_path`
from the PreToolUse stdin payload. The marker-file fallback remains available
but primary path is transcript-based.

## Artifacts delivered

- `hooks/hooks.json` — no-op manifest (`{"hooks": {}}`)
- `hooks/tests/fixtures/skill_invocation_sample.jsonl` — verified Skill call shape
- `hooks/_lib/__init__.py`
- `hooks/_lib/env.py` — `is_hooks_disabled()` accepts {"0","false","no","off",""}
- `hooks/_lib/safe.py` — `@fail_open` decorator: catches Exception, warns stderr, exits 0; lets SystemExit propagate
- `hooks/_lib/overrides.py` — `has_override()`: case-insensitive substring match on `["be quick", "just do it", "trivial fix"]`
- `hooks/_lib/transcript.py` — `load_transcript_entries()`, `find_last_user_index()`, `skill_invoked_since()`
- `hooks/tests/conftest.py` — fixtures + 1MB performance transcript fixtures (two shapes)
- `hooks/tests/test_env.py`
- `hooks/tests/test_safe.py`
- `hooks/tests/test_overrides.py`
- `hooks/tests/test_transcript.py`

## Test run output

```
Command: python3 -m pytest tests/test_env.py tests/test_safe.py tests/test_overrides.py tests/test_transcript.py -v
69 passed in 0.16s

Command: python3 -m pytest skills/feature-development/tests/ -q
18 passed in 0.03s (pre-existing, zero regressions)
```

Unit: 69 tests
Regression: 18 pre-existing tests, all passing

## Performance verification (from test run)

- `test_perf_many_short_lines`: PASSED (<50ms on ~1MB many-short-lines)
- `test_perf_few_long_lines`: PASSED (<50ms on ~1MB few-long-lines)
