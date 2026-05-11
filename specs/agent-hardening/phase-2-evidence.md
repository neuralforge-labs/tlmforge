# Phase 2 — Hard Evidence

## Verification greps

```
$ grep "^tools:" tlmforge/agents/code-reviewer.md
tools: Read, Grep, Glob, Bash, Write, Edit

$ grep "^tools:" tlmforge/agents/ux-reviewer.md
tools: Read, Grep, Glob, Bash, Write, Edit, WebSearch, WebFetch
```

Both files include `Write` and `Edit` in their tools lists.

## Reproducibility

```
cd $REPO_ROOT
grep "^tools:" agents/code-reviewer.md agents/ux-reviewer.md
# expects: both lines contain Write and Edit
```
