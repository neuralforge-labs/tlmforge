#!/usr/bin/env python3
"""Golden eval runner — discovers tasks, executes via Claude Code, compares to baselines.

Skeleton implementation: defines the framework + comparison logic. The actual Claude Code
invocation (CLI/SDK) is left as a TODO marker since it depends on which integration the
user wires up.

Usage:
    runner.py                    # run all tasks, write report, exit non-zero on regression
    runner.py --record-baseline  # capture current run as the baseline (deliberate)
    runner.py --task T03         # run only task T03
    runner.py --notify           # also send PushNotification on regression (cron mode)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sys
from typing import Optional

try:
    import yaml  # PyYAML
except ImportError:
    print("ERROR: PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(2)


SKILL_DIR = pathlib.Path(__file__).resolve().parent
TASKS_DIR = SKILL_DIR / "tasks"
BASELINES_DIR = SKILL_DIR / "baselines"
REPORTS_DIR = SKILL_DIR / "reports"


def load_tasks(filter_id: Optional[str] = None) -> list[dict]:
    """Load all .yaml task files from tasks/."""
    tasks = []
    if not TASKS_DIR.exists():
        return []
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        with open(path) as f:
            t = yaml.safe_load(f)
        if filter_id and t.get("id") != filter_id:
            continue
        tasks.append(t)
    return tasks


def load_baseline(task_id: str) -> Optional[dict]:
    path = BASELINES_DIR / f"{task_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_baseline(task_id: str, metrics: dict) -> None:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINES_DIR / f"{task_id}.json"
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
    tmp.rename(path)


def execute_task(task: dict) -> dict:
    """Execute a single task via Claude Code and capture metrics.

    THIS IS THE INTEGRATION POINT. The skeleton returns synthetic metrics so the
    framework is testable without a live Claude Code invocation. Replace with:
      - subprocess `claude code -p '<input_prompt>'` and parse the JSON response
      - OR the Anthropic SDK with a tool-use loop matching the user's setup

    Returns: dict with metrics matching the task's `metrics` list.
    """
    # SKELETON: replace with real Claude Code call.
    return {
        "task_id": task["id"],
        "passed": True,
        "cost_usd": 0.0,
        "duration_seconds": 0,
        "tools_used_count": 0,
        "output_hash": "sha256:skeleton",
        "captured_at": datetime.datetime.utcnow().isoformat() + "Z",
        "model": "skeleton",
        "_note": (
            "This is the skeleton runner. To wire up real Claude Code execution, "
            "replace `execute_task()` with a subprocess call to `claude code -p ...` "
            "or an Anthropic SDK tool-use loop. See SKILL.md for guidance."
        ),
    }


def evaluate_success_criteria(task: dict, metrics: dict, baseline: Optional[dict]) -> dict:
    """Apply task.success_criteria to metrics+baseline, return pass/fail per criterion."""
    results = []
    criteria = task.get("success_criteria", [])
    for c in criteria:
        passed = _eval_criterion(c, metrics, baseline)
        results.append({"criterion": c, "passed": passed})
    return {
        "all_passed": all(r["passed"] for r in results),
        "criteria_results": results,
    }


def _eval_criterion(criterion: str, metrics: dict, baseline: Optional[dict]) -> bool:
    """Tiny DSL: 'tests_pass = true', 'cost_usd <= baseline.cost_usd * 1.5'."""
    text = criterion.strip()
    # boolean
    if "=" in text and "<=" not in text and ">=" not in text:
        key, expected = [s.strip() for s in text.split("=", 1)]
        if expected.lower() == "true":
            return bool(metrics.get(key))
        if expected.lower() == "false":
            return not metrics.get(key)
        return str(metrics.get(key)) == expected
    # comparison vs baseline
    for op_str, op in [("<=", "<="), (">=", ">="), ("<", "<"), (">", ">")]:
        if op_str in text:
            left, right = [s.strip() for s in text.split(op_str, 1)]
            left_val = metrics.get(left)
            right_val = _resolve_value(right, baseline)
            if left_val is None or right_val is None:
                return False
            if op == "<=": return left_val <= right_val
            if op == ">=": return left_val >= right_val
            if op == "<": return left_val < right_val
            if op == ">": return left_val > right_val
    return False


def _resolve_value(expr: str, baseline: Optional[dict]) -> Optional[float]:
    """Resolve 'baseline.cost_usd * 1.5' or '5.0'."""
    expr = expr.strip()
    try:
        return float(expr)
    except ValueError:
        pass
    if expr.startswith("baseline."):
        if baseline is None:
            return None
        # baseline.cost_usd * 1.5
        rest = expr[len("baseline."):]
        if "*" in rest:
            key, mult = [s.strip() for s in rest.split("*", 1)]
            return float(baseline.get(key, 0)) * float(mult)
        return float(baseline.get(rest, 0))
    return None


def compute_deltas(metrics: dict, baseline: Optional[dict]) -> dict:
    if baseline is None:
        return {"baseline": "absent"}
    deltas = {}
    for key in ("cost_usd", "duration_seconds", "tools_used_count"):
        if key in metrics and key in baseline:
            base = baseline[key]
            curr = metrics[key]
            if base == 0:
                deltas[key] = "(baseline 0)"
            else:
                pct = ((curr - base) / base) * 100
                deltas[key] = f"{pct:+.1f}%"
    return deltas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record-baseline", action="store_true")
    ap.add_argument("--task", type=str, default=None)
    ap.add_argument("--notify", action="store_true")
    args = ap.parse_args()

    tasks = load_tasks(filter_id=args.task)
    if not tasks:
        print("No tasks found in", TASKS_DIR, file=sys.stderr)
        return 0

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    task_results = []
    regressions = []
    for t in tasks:
        metrics = execute_task(t)
        if args.record_baseline:
            save_baseline(t["id"], metrics)
            task_results.append({"task_id": t["id"], "recorded_baseline": True})
            continue

        baseline = load_baseline(t["id"])
        criteria = evaluate_success_criteria(t, metrics, baseline)
        deltas = compute_deltas(metrics, baseline)
        regression = not criteria["all_passed"]
        result = {
            "task_id": t["id"],
            "passed": metrics.get("passed"),
            "cost_usd": metrics.get("cost_usd"),
            "duration_seconds": metrics.get("duration_seconds"),
            "delta_vs_baseline": deltas,
            "criteria": criteria,
            "regression": regression,
        }
        task_results.append(result)
        if regression:
            regressions.append(result)

    if args.record_baseline:
        print(f"Baselines recorded for {len(tasks)} tasks.")
        return 0

    report = {
        "run_at": datetime.datetime.utcnow().isoformat() + "Z",
        "task_results": task_results,
        "regression_count": len(regressions),
        "summary": f"{len(regressions)} of {len(tasks)} tasks regressed.",
    }
    report_path = REPORTS_DIR / f"{report['run_at'].replace(':', '-')}.json"
    with open(report_path.with_suffix(".json.tmp"), "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    report_path.with_suffix(".json.tmp").rename(report_path)
    print(json.dumps(report, indent=2))

    if regressions and args.notify:
        # Hook for PushNotification — actual implementation depends on user's setup.
        print(
            f"\nNOTIFY: golden eval drift detected — {len(regressions)} task(s) regressed.\n"
            f"  Report: {report_path}",
            file=sys.stderr,
        )

    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
