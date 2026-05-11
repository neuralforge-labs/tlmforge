# Phase 4 — Hard Evidence

## Step ordering verification

Process-compliance hook step order in `~/.claude/settings.json`:

```
STEP 1: LOOP PREVENTION
STEP 2: CHECK FOR CODE CHANGES
STEP 3: CLASSIFY SCOPE           ← sets TIER1 flag
STEP 4: TIER1 PATH CHECK         ← NEW: before override
STEP 4b: USER OVERRIDE CHECK     ← non-TIER1 override fast-path
STEP 4c: TIER1 + OVERRIDE LLM JUDGMENT  ← NEW: LLM judgment for TIER1+override
STEP 5: TRIVIAL FAST-PATH
STEP 6: ARTIFACT CHECK
STEP 7: DECISION
```

## Key grep assertions

```
$ grep -c "STEP 4: TIER1 PATH CHECK" ~/.claude/settings.json
1

$ grep -c "STEP 4c: TIER1 + OVERRIDE LLM JUDGMENT" ~/.claude/settings.json
1

$ grep -n "STEP 4" ~/.claude/settings.json | head -5
# STEP 4: TIER1 PATH CHECK appears before STEP 4b: USER OVERRIDE CHECK
```

## LLM judgment clause present

```
$ grep -c "read the diff" ~/.claude/settings.json || grep -c "ACTUALLY do" ~/.claude/settings.json
1
```

## Dotfiles mirror in sync

```
$ diff ~/.claude/settings.json ~/dotfiles/claude/global/settings.json
(no output — files identical)
```

## Reproducibility

```
grep -c "STEP 4: TIER1 PATH CHECK" ~/.claude/settings.json  # expects: 1
grep -c "STEP 4c:" ~/.claude/settings.json                  # expects: 1
diff ~/.claude/settings.json ~/dotfiles/claude/global/settings.json  # expects: empty
```
