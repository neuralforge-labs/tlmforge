# Phase 6 — Hard Evidence

## Version assertion

```
$ python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert d['version']=='0.4.0'; print('version:', d['version'])"
version: 0.4.0
```

## Files

- `.claude-plugin/plugin.json` — version bumped 0.3.0 → 0.4.0
- `CHANGELOG.md` — created with migration note for plans/ → specs/ path change
