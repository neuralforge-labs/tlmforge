---
name: test-impact-graph
description: |
  Use this skill to identify which tests are impacted by a code change — the diff-to-tests
  reverse dependency graph (TDAD pattern). Triggers on phrases like "which tests should I run",
  "test impact for this diff", "skip tests that don't matter", or after a refactor when the
  user wants to skip running the full suite. Reads a Python codebase and computes the
  transitive set of test files that import (directly or via intermediate modules) the
  changed source files.

  Output: a list of test files (paths) to run, with the import chain that connects each test
  to a changed file. Reduces typical CI loops 5-10x for diff-scoped changes.
---

# Test impact graph (TDAD)

When you change `backend/auth/token.py`, you don't need to run the entire 500-test suite to
know whether the change broke something — you need to run exactly the tests that import
`token.py` (directly or transitively). This skill builds that import graph and returns the
impacted set.

## When to use

**Triggers:**
- "Which tests should I run after this diff?"
- "Test impact for these files."
- "Skip tests that aren't affected."
- After a refactor, when the user wants to confirm nothing broke without paying for the full suite

**When NOT to use:**
- Pure UI changes (Playwright/E2E tests don't follow Python imports — fall back to running the relevant E2E suite manually)
- Changes to test infrastructure (conftest.py, fixtures) — these affect EVERY test by definition; run the full suite
- Diff includes config/yaml/json files that are loaded at test runtime — the analyzer can't see runtime loads, so be conservative

## How it works

1. **Parse all `.py` files in the project** with Python's `ast` module
2. **For each file, extract its `import X`, `from X import Y`** statements as edges in a graph
3. **Resolve module paths to file paths** using the project's package layout
4. **Reverse the graph**: for each module, list the test files that depend on it (transitively)
5. **Given a list of changed files**, return the union of impacted test files

The skill ships with `analyzer.py` — a self-contained Python script that takes `--src-root`
and `--changed-files` and emits the impacted test list.

## Usage

```bash
$ python3 ~/.claude/skills/test-impact-graph/analyzer.py \
    --src-root ~/memx/c1/memx/backend \
    --tests-root ~/memx/c1/memx/backend/tests \
    --changed-files backend/auth/token.py backend/encryption/crypto.py

backend/tests/test_auth_token.py
backend/tests/test_login_flow.py
backend/tests/test_encryption_lifecycle.py
# 3 tests impacted (vs 487 in full suite — 162x reduction)
```

Wire into the user's CI / dev loop:

```bash
# In a pre-push hook or local script
changed=$(git diff --name-only HEAD)
impacted=$(python3 ~/.claude/skills/test-impact-graph/analyzer.py \
    --src-root . --tests-root ./tests --changed-files $changed)
pytest $impacted
```

## Limitations (acknowledge upfront)

- **Static analysis only.** Dynamic imports (`importlib.import_module(name)`, `__import__`)
  are invisible. If your code does runtime metaprogramming, the impact graph misses tests
  that exercise that code path. Workaround: maintain an explicit "always-run-these" list.
- **Python only.** Flutter/Dart, JavaScript, etc. need their own analyzer. Not in scope here.
- **conftest.py and fixture changes.** Pytest fixtures cross test files via shared discovery.
  Treat any change to `conftest.py` or `tests/fixtures/*` as "run the full suite."
- **External imports.** Changes in third-party packages aren't in your repo, so the analyzer
  doesn't see them. Use `pip install -U` + full-suite-run for dependency upgrades.

## When the analyzer's output looks wrong

- Test you expected to be impacted is missing → check whether your code uses a dynamic import
- Test you didn't expect → check whether a transitive dependency exists you forgot about (often signals coupling worth refactoring)
- Empty result on a real diff → the changed file probably isn't imported anywhere; either it's dead code or the analyzer's source-root config is wrong

## Calibration discipline

- Always run the impacted tests; don't skip them.
- If the impacted set is small (1-3 tests) on a non-trivial diff, double-check by running the full suite once before merging — a too-small impacted set is a signal of a bug in the analyzer or unusual import patterns.
- For security-touching diffs (auth, encryption, payments), run the full suite regardless. The cost saving isn't worth the risk.
