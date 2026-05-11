# Changelog

## 0.4.0 (2026-05-11)

### Fixes

- **Path fix (plans/ → specs/):** All agent output paths corrected to `specs/<feature>/agent_verification/`. Fixes a silent bug where threat-modeler and red-team-reviewer wrote JSON sidecars to `plans/` while the convergence script looked in `specs/` — causing convergence to always inject synthetic `reviewer_json_missing` findings for those roles.

- **Artifact writing (code-reviewer, ux-reviewer):** Added `Write` and `Edit` to both agents' tools lists. They now physically write `code_review.md` and `ux_review.md` artifacts to `specs/<feature>/agent_verification/` instead of producing prose-only output.

- **Process-compliance hook (TIER1 override):** Fixed a security hole where "be quick" / "just do it" keywords bypassed TIER1 path enforcement (auth, encryption, payments, PII, migrations) unconditionally. TIER1 detection now fires before the override check. TIER1 + override goes through LLM judgment: hard floor (>2 files or >50 LOC blocks unconditionally), LLM judgment below the floor can escalate dangerous one-line changes.

### Hardening

- **Tester agent:** Now runs the actual test suite (Python/JS/Flutter/Go runner auto-detected), reports real coverage numbers and uncovered line ranges, generates executable test stubs for CRITICAL/HIGH findings. Writes `tester_review.md` + `tester_coverage.md` artifacts. Scopes findings to phase diff when running as Stage 4.6 per-phase re-review.

- **Code-reviewer agent:** Now builds a file:line test gap table for every changed source file, writes `code_review.md` artifact. Uses `TLMFORGE_FEATURE_DIR` env var to detect feature context vs Stop-hook mode.

- **UX-reviewer agent:** Now writes a structured findings table (Component | File:line | Issue | Severity | Fix) to `ux_review.md`. Explicitly required to say "no issues found" rather than silencing — silence is treated as a missing artifact by the convergence check.

- **Per-phase re-review (Stage 4.6):** After each Phase 4 phase completes, tester + code-reviewer run against the phase diff (anchored to `phase-N-state.md git_sha`, not just `HEAD~1`). CRITICAL or HIGH findings block the next phase. Output written to `phase-N-review.md`.

- **Conditional human gates:** Stage 1→2 gate now fires only when findings are tagged `[GATE-BLOCKING]` or the feature touches TIER1 keywords. Stage 2→3 gate fires only when the plan introduces decisions not already approved. Unconditional sentinels removed — agents are the quality gate once intent is confirmed.

### Migration note

If you have in-flight features with JSON sidecars already written to `plans/<feature>/agent_verification/`, copy them before resuming:

```bash
cp -r plans/<feature>/agent_verification/ specs/<feature>/agent_verification/
```

This is a one-time migration step. New iterations will write to `specs/` automatically.
