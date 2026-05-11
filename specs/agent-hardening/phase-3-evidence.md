# Phase 3 — Hard Evidence

## Prompt grep assertions

```
$ grep -c "tester_coverage.md" agents/tester.md
1

$ grep -c "pytest --cov" agents/tester.md
1

$ grep -c "code_review.md" agents/code-reviewer.md
1

$ grep -c "file:line" agents/code-reviewer.md
2

$ grep -c "ux_review.md" agents/ux-reviewer.md
1

$ grep -c "File:line" agents/ux-reviewer.md
1
```

## What was added

| Agent | New section | Key additions |
|---|---|---|
| `tester.md` | `## Artifact Output` | test runner detection (Python/JS/Flutter/Go), graceful degrade, tester_coverage.md + tester_review.md artifacts, TLMFORGE_FEATURE_DIR context detection, per-phase scoping for Stage 4.6 |
| `code-reviewer.md` | `## Artifact Output` | test gap table with file:line refs, code_review.md artifact, TLMFORGE_FEATURE_DIR context detection |
| `ux-reviewer.md` | `## Artifact Output` | structured findings table with File:line refs, ux_review.md artifact, explicit no-findings requirement, TLMFORGE_FEATURE_DIR context detection |

## Reproducibility

```
cd $REPO_ROOT
grep -c "tester_coverage.md" agents/tester.md       # expects: 1
grep -c "pytest --cov" agents/tester.md             # expects: 1
grep -c "code_review.md" agents/code-reviewer.md    # expects: 1
grep -c "ux_review.md" agents/ux-reviewer.md        # expects: 1
```
