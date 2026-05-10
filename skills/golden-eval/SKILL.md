---
name: golden-eval
description: |
  Use this skill to run a fixed corpus of reference tasks against the current Claude
  configuration and detect regression vs a baseline. Triggers on "run golden eval",
  "check for drift", "did Claude get worse", "eval drift", or via a scheduled
  invocation (cron / Anthropic Routine via the /schedule skill). Captures cost, latency,
  and per-task pass/fail; flags any regression beyond a configurable threshold.

  Output: a JSON report at `~/.claude/skills/golden-eval/reports/<timestamp>.json` and
  (if regression detected) a PushNotification with the summary.
---

# Golden eval — drift detection for Claude Code

When Anthropic ships a model change, your reviewer pipeline can silently degrade. Golden
eval catches this by running a fixed set of reference tasks weekly and comparing to a
recorded baseline. Diff in cost, latency, or pass/fail → alarm.

## When to use

**Triggers:**
- User says "run golden eval", "check for drift", "did Claude get worse"
- A scheduled run fires (Anthropic Routine via `/schedule`, or system cron)
- Before/after a model upgrade announcement (check baseline holds)

**When NOT to use:**
- Ad-hoc one-off tests — golden eval is for *fixed* corpus over time
- Replacing real tests — eval is a regression sentinel, not a substitute for unit/integration tests

## Architecture

```
tasks/                   # fixed corpus, one .yaml per task
  T01-add-constant.yaml
  T02-fix-typo.yaml
  T03-refactor-fn.yaml
                ↓
runner.py                # loads each task, executes, captures cost/latency/output
                ↓
baselines/<task>.json    # baseline metrics from a known-good run
                ↓
report.json              # current run vs baseline diffs
                ↓
notify.py                # PushNotification if any task regressed > threshold
```

## Task format

Each task is a small YAML file in `~/.claude/skills/golden-eval/tasks/`:

```yaml
# tasks/T01-add-constant.yaml
id: T01
title: Add a constant to a config file
input_prompt: >
  In the file ./test_fixture/config.py, add a constant MAX_RETRIES = 3 just below
  the existing TIMEOUT_SECONDS constant. Update the existing pytest test if needed.
expected_behavior:
  - file_modified: ./test_fixture/config.py
  - constant_added: MAX_RETRIES = 3
  - tests_pass: true
metrics:
  - cost_usd            # tracked from API response
  - duration_seconds    # tracked from wallclock
  - tools_used_count    # tracked from tool call count
success_criteria:
  - tests_pass = true
  - cost_usd <= baseline.cost_usd * 1.5     # 50% cost regression alarm
  - duration_seconds <= baseline.duration * 2.0
```

## Baseline format

A known-good run becomes the baseline:

```json
// baselines/T01.json
{
  "task_id": "T01",
  "captured_at": "2026-05-10T12:00:00Z",
  "model": "claude-sonnet-4-5",
  "cost_usd": 0.013,
  "duration_seconds": 27,
  "tools_used_count": 4,
  "tests_pass": true,
  "output_hash": "sha256:..."
}
```

Re-baseline only after intentional model upgrades — don't drift the baseline silently.

## Runner

`runner.py` is a Python script that:
1. Discovers all `tasks/*.yaml` files
2. For each task, invokes Claude Code with the input_prompt (via `claude code` CLI or via the SDK if installed) — captures cost (from JSON response), duration (wallclock), tools used (from response)
3. Validates expected_behavior (existence of file changes, test pass)
4. Compares each metric against `baselines/<task_id>.json` using `success_criteria`
5. Writes `reports/<timestamp>.json` with: per-task metrics, per-task pass/fail, overall regression count
6. Exits non-zero if any task regressed → cron sees the failure and triggers PushNotification

## Cron wiring

Use the existing `/schedule` skill to set up a weekly Anthropic Routine that invokes
`runner.py`. Recommended cadence: **Sunday 9am local** (low-traffic, before workweek).

If Anthropic Routines aren't preferred, system cron works too:

```cron
0 9 * * 0 ~/.claude/skills/golden-eval/runner.py --notify
```

## Re-baselining

When a new Claude model lands and you intentionally adopt it (e.g., Sonnet 4.6 → Sonnet 4.7):

1. Run `runner.py --record-baseline` once to capture new baselines
2. Manually inspect each task's new baseline — does the change pattern make sense?
3. Commit the new baselines
4. Continue weekly drift detection vs the new baseline

If multiple tasks regress beyond threshold but the new model is still acceptable, edit the
`success_criteria` thresholds rather than re-baselining at degraded values.

## What to put in the corpus

Pick tasks that:
- Touch a code path you care about (auth, encryption, payments, search, your specific business logic)
- Have a deterministic success criterion (test passes, file matches expected, output contains X)
- Take 30s to 5 minutes (fast enough for weekly runs; long enough that improvement/degradation shows)
- Don't depend on external state beyond the test fixture (no live API, no production data)

3-5 tasks is enough for v1. Add more as you discover blind spots.

The user's plan suggested:
- T01: small constant addition (smoke task)
- T02: fix a known bug
- T03: refactor a function
- T04: handle a security-sensitive edit (auth path; tests covering IDOR / token handling)
- T05: end-to-end memory CRUD (touches the encryption layer)

## Output: report and notification

Report (`reports/<timestamp>.json`):
```json
{
  "run_at": "2026-05-12T09:00:14Z",
  "model": "claude-sonnet-4-7",
  "task_results": [
    {"task_id": "T01", "passed": true, "cost_usd": 0.014, "duration_seconds": 28,
     "regression": false, "delta_vs_baseline": {"cost": "+8%", "duration": "+4%"}},
    {"task_id": "T03", "passed": true, "cost_usd": 0.041, "duration_seconds": 95,
     "regression": true, "delta_vs_baseline": {"cost": "+105%"},
     "alert": "cost regression — over 1.5x baseline"}
  ],
  "regression_count": 1,
  "summary": "1 of 5 tasks regressed."
}
```

Notification (only fires on regression):
```
Golden eval drift detected: 1 of 5 tasks regressed.
T03 (refactor-fn): cost is 2.05x baseline.
Full report: ~/.claude/skills/golden-eval/reports/2026-05-12T09:00:14Z.json
```

## Calibration discipline

- **Don't alarm on +5% noise.** Set thresholds at meaningful change levels (1.5x cost, 2x duration).
- **Don't auto-update baselines.** Re-baselining is a deliberate human decision.
- **Track output hash, but don't fail on it directly.** Different model wording is fine; use it as a tiebreaker if cost/duration are equal but behavior differs.
- **Run on a quiet network.** Wallclock duration is sensitive to API latency variation; pick a slot where API load is light.

## Smoke instructions

Before relying on this for drift detection, run it once manually:
```
cd ~/.claude/skills/golden-eval
python3 runner.py --record-baseline   # captures the baseline first time
python3 runner.py                     # verifies the baseline matches itself (should be near-zero diff)
```

If the second run shows large diffs, the eval itself is non-deterministic — fix the task
specs (more constraint on input, less freedom for the model) before relying on the cron.
