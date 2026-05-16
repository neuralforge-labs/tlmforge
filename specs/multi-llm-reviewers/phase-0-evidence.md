# Phase 0 Evidence — multi-llm-reviewers

## Goal delivered

Shell wrapper scaffold (`ai_review_openai.sh`), Python stub
(`ai_review_json_openai.py`), Phase 0 tests, and settings.json permission entry.

## Files created

- `skills/feature-development/ai_review_openai.sh` — thin shell wrapper; arg parsing,
  ITERATION integer validation, output parent directory check, delegates to Python
- `skills/feature-development/ai_review_json_openai.py` — Python stub; full pre-flight
  logic (TLMFORGE_ENABLE_OPENAI, OPENAI_API_KEY, SDK import check); always writes
  status=skipped + exits 2 (Phase 1 replaces the stub block with the real API call)
- `skills/feature-development/tests/test_openai_wrapper.py` — 31 tests total:
  16 Phase 0 (GREEN), 15 Phase 1 (RED by design until Phase 1 impl)
- `~/.claude/settings.json` — added `Bash(ai_review_openai.sh:*)` permission

## Test run

```
python3 -m pytest skills/feature-development/tests/ \
  --ignore=skills/feature-development/tests/fixtures -v
```

**Phase 0 tests: 16 passed** (all exit-code contract + JSON shape + atomic write tests)

**Phase 1 tests: 15 failed** (expected RED — stub always exits 2, real-call tests
expect exit 0 with status=ok; these turn GREEN in Phase 1)

**Pre-existing tests: 69 passed, 0 regressions**
(test_check_convergence.py, test_checkpoint_format.py, test_v058_medium_path.py)

Total: 15 failed (Phase 1 RED), 69 passed, in 0.77s

## TDD discipline

- Tests written FIRST → confirmed RED (script didn't exist yet)
- Stub implemented → Phase 0 tests turn GREEN
- Phase 1 tests deliberately kept RED to enforce TDD at Phase 1

## Rollback

Delete `ai_review_json_openai.py`, `ai_review_openai.sh`;
remove `Bash(ai_review_openai.sh:*)` from settings.json.
