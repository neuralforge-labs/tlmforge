# Round 3 Tester Review — enforcement-hooks

**Iteration:** 3 (final)
**Verdict:** approve

---

## Prior Finding Resolution

### NEW-1 (Medium — reminder text contradiction)

**Status: FIXED**

**Evidence:** README.md Phase 1 Steps, reminder text block (lines 278–283):

> To bypass enforcement on this message, include `be quick`, `just do it`,
> or `trivial fix` in your prompt. (Bare "minimal" / "trivial" are NOT
> accepted — they appear too often in technical prose.)

The reminder now lists exactly the three retained override phrases. The
explicit parenthetical makes the rejection of bare "minimal"/"trivial"
discoverable to users who read the reminder. The suggested test update is
implicitly addressed: `test_hook1_normal.py` ("stdin → expected stdout JSON
shape") must assert the emitted systemMessage string, and the correct string
is now in the plan. Any implementation that produces the old text will fail
that test.

### NEW-2 (Low — marker file path not anchored)

**Status: FIXED**

**Evidence:** README.md Phase 3 Steps (lines 376–384):

> Use `git rev-parse --show-toplevel` first to find repo root (handles any
> cwd). Then read `<repo_root>/specs/.tlmforge_active_feature` to get active
> feature name... (repo root already resolved above; reuse for all
> subsequent paths)

Single `--show-toplevel` call at hook entry. Both the marker read and the
glob now explicitly reference `<repo_root>/...`. The redundant second call
is documented as removed.

`test_hook3_cwd_subdirectory.py` description (lines 427–428):

> cwd is project subdir, not repo root → uses git rev-parse --show-toplevel
> for BOTH marker file AND glob; both resolve correctly (EC-6 + NEW-2)

Both IO operations are explicitly covered in the test description.

---

## New Findings (Round 3 Only)

### LOW-1 — PSR marker with missing `verdict_sha` field: behavior unspecified

**Finding:** Phase 3 specifies that corrupt or missing-field `final_audit_*.json`
files are skipped ("skip if absent or corrupt — JSONDecodeError → continue").
For the PSR marker file, the plan specifies that filename match alone is
insufficient and the internal `verdict_sha` field must equal HEAD. However,
the plan does not specify what happens when the PSR marker file EXISTS but
the `verdict_sha` field is ABSENT (e.g., a manually written or empty-field
PSR file).

If the implementation treats absent-field as "validation passed," a user who
accidentally writes a PSR marker without the `verdict_sha` field bypasses
the gate silently. If it treats absent-field as "block," that is correct
defense-in-depth behavior.

**Affected test:** No test named `test_hook3_psr_marker_missing_verdict_sha.py`
is listed. The existing `test_hook3_psr_marker_sha_mismatch.py` covers
wrong-value but not absent-value.

**Impact:** Low. This is a plan ambiguity, not a confirmed bug. The
implementation team should clarify: absent `verdict_sha` in a PSR marker
file → treat as no valid PSR → block. A one-line test stub covering this
case should be added during Phase 3 TDD.

**Suggested test:**
```python
def test_hook3_psr_marker_missing_verdict_sha(tmp_path, monkeypatch):
    # PSR marker file exists but has no verdict_sha field
    # Hook 3 should treat this as no valid PSR → block
    psr_marker = tmp_path / "final_audit_red-team-reviewer_psr_BBBB.json"
    psr_marker.write_text('{"role": "red-team-reviewer"}')  # no verdict_sha
    # ... set up active feature, HEAD=BBBB, verdict_sha=AAAA ...
    result = run_hook3(command="git commit -m test", head="BBBB", ...)
    assert result.returncode == 2  # currently: may return 0 (bypass) if absent field treated as match
```

**This finding does NOT block approval.** It is a plan-level ambiguity that
implementation-time TDD should resolve. The correct behavior is clear from
intent (block); the plan should simply be more explicit.

---

## Edge Cases Properly Handled (Carried Forward)

Confirming the following remain correctly addressed in the final plan:

- EC-1: Subagent sessions (no user messages) → Hook 2 pass-through
- EC-2: Empty repo / no commits → Hook 3 WARNING + pass-through
- EC-3: Short SHA in verdict_sha → normalized to 40 chars before compare
- EC-5: Override phrases "minimal"/"trivial" removed from override library
- EC-6: Glob anchored to git rev-parse --show-toplevel
- EC-8: verdict_sha unreachable after rebase → still block, "?" for commit count
- HIGH-3: PSR marker internal SHA mismatch → block (filename alone insufficient)
- Fail-open on hook crash → exit(0) + stderr (all three hooks)
- TLMFORGE_HOOKS=0 multi-value bypass honored by all three hooks
- Subagent pass-through (Hook 2) prevents blocking Stage 3/4 reviewer agents
- Override phrase scoped to LAST user message only (not anywhere in transcript)

---

## Summary

Both round-2 findings (NEW-1, NEW-2) are fully resolved in the updated plan.
One new LOW finding (LOW-1) identifies a plan ambiguity around PSR marker
files with absent `verdict_sha` fields. This should be addressed during
Phase 3 TDD by clarifying the behavior and adding one test stub. It does not
warrant blocking the plan.

**Verdict: approve**
