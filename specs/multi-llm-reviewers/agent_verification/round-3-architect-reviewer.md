# Round 3 Architect Review — multi-llm-reviewers

## VERDICT: APPROVE_WITH_WARNINGS

## Summary

All Round 1 CRITICALs (C1, C2, C3) and all Round 2 CRITICALs (NEW-C1, NEW-C2) are correctly
resolved in the current README.md. Two residual items remain: W1 (`.strip()` before marker
regex) is still only implied by a test comment rather than stated in implementation pseudocode,
and two stale `status=error` references in the risk audit table contradict the now-canonical
silent-skip policy. Neither blocks shipping but both should be corrected before the plan is
handed to implementation.

---

## Findings carry-forward from Round 1

### C1 — expected_roles coupling / reviewer field not pinned
**VERDICT: FIXED**
Evidence:
- README.md:54 — `"reviewer" field hardcoded to "openai"` in constraints
- README.md:143 — `REVIEWER_NAME = "openai"` constant in Phase 0 Step 2
- README.md:210 — `REVIEWER_NAME = "openai" — always this string in the output JSON` in Phase 1
- README.md:302-308 — Phase 3 concrete Python pseudocode for conditional `expected_roles` with both flag and key gating
- README.md:247 — Phase 1 test asserts `reviewer` field is exactly `"openai"` in all output paths

### C2 — Chat Completions API deprecated for gpt-5.5
**VERDICT: FIXED**
Evidence:
- README.md:55-57 — constraints mandate `client.responses.create()`, explain Chat Completions maintenance-mode status
- README.md:183-193 — Phase 1 implementation block shows full `client.responses.create()` + `response.output_text`
- README.md:341-342 — decision recorded in Decisions Made section

### C3 — No atomic-write guarantee
**VERDICT: FIXED**
Evidence:
- README.md:50-53 — constraints mandate `tempfile.NamedTemporaryFile(dir=output_dir, delete=False)` + `os.replace()`; `shutil.move` explicitly prohibited
- README.md:106-111 — architecture block shows exact four-line atomic write sequence

### W1 — .strip() not applied to marker read before regex validation
**VERDICT: PARTIALLY FIXED**

The fix was documented in round-1-fixes.md (noting that `.strip()` must be applied before
regex validation). The test at README.md:246 implies it: `"my feature" → Python strips and
validates, exit 2`. However, the canonical implementation pseudocode at README.md:179-180
still reads:

```
mode=plan: validate marker with re.fullmatch(r'[a-zA-Z0-9_-]+', feature);
if invalid or absent → skipped
```

There is no `.strip()` call shown. The regex `[a-zA-Z0-9_-]+` does NOT match a string
containing `\n`, so any marker file written with `echo` (the standard shell tool, which
appends a newline) will produce a string that fails the regex and causes `mode=plan` to
always exit 2 with `status=skipped`. This is a spec bug: the implementation pseudocode is
the authoritative reference for the implementer, and it is missing the strip.

**What's needed:** Add `.strip()` explicitly to the pre-flight pseudocode:
`feature = open(marker_path).read().strip()` then apply `re.fullmatch(...)`. Also add an
explicit test case: "marker file containing trailing newline → strips correctly, proceeds
to README lookup."

### W2 — Token budget guard
**VERDICT: FIXED (deferred/accepted)**
Risk audit line 334 documents the accepted risk of sending full README content to the API
without a token guard. The deferred state is explicitly noted. No action required.

---

## Findings carry-forward from Round 2

### NEW-C1 — Phase 1 tests: status=error + exit 0 for provider failures
**VERDICT: FIXED**
Evidence:
- README.md:241 — `Both calls invalid JSON → status=skipped, exit 2, failure logged`
- README.md:242 — `Auth error (mocked) → status=skipped, exit 2, failure logged`
- README.md:243 — `Truncated response → retry → still truncated → status=skipped, exit 2, failure logged`
All three previously broken test expectations now correctly specify the silent-skip contract.

### NEW-C2 — Verification criterion 1 expects status=error on fake API key
**VERDICT: FIXED**
Evidence:
- README.md:379 — Criterion 1 now: `exits 2, JSON has status=skipped, reviewer="openai"`
- README.md:380 — Criterion 1b added: mocked valid response exits 0, status=ok, validates against schema

### NEW-H1 — Echo trailing newline in marker
**VERDICT: SUBSUMED BY W1 (still partially open)**
The round-2-fixes correctly notes this was already handled by W1. However as documented
above under W1, the `.strip()` is still absent from the implementation pseudocode. The
core problem is unresolved at the spec level even though the test at line 246 implies it.

---

## New Findings (Round 3 only)

### MEDIUM — Risk audit table still references status=error for LLM provider failures

**Location:** README.md:335, README.md:337

The risk audit table was partially updated (line 97 exit-code contract was fixed) but two
rows still carry stale `status=error` language:

- Line 335: `gpt-5.5 model ID... model-not-found → error JSON, not crash`
- Line 337: `TOCTOU between key presence check and API call → Results in status=error instead of status=skipped`

Both of these describe LLM provider failure conditions. Per the now-canonical constraint at
README.md:59-66 and Phase 1 lines 203-208, ALL LLM provider failures must produce
`status=skipped + exit 2`, never `status=error`. The line 337 description is factually
wrong about what the correctly implemented script will do. An implementer reading the risk
audit after reading the constraint section will find a contradiction.

**Fix:** 
- Line 335: Change to `model-not-found → status=skipped, exit 2, failure logged; not crash`
- Line 337: Change to `Results in status=skipped (key absent at call time → openai.AuthenticationError → silent skip)`

---

## What's Good

- The overall architecture is sound: opt-in env-var gates, hardcoded reviewer name constant,
  Responses API (not Chat Completions), atomic writes, and the silent-skip policy are all
  correctly specified.
- The `expected_roles` conditional roster template in Phase 3 is concrete and unambiguous —
  it shows real Python code, not vague prose.
- The exit-code contract table at README.md:96-101 is now internally consistent and clear
  about the separation between `status=ok` (exit 0), `status=skipped` (exit 2, ALL provider
  failures), and usage errors (exit 64).
- Verification criteria 1 and 1b together cover both the skip path and the happy path, which
  is the right two-sided check.
- The security constraints section is thorough: no blanket key-prefix shell permission, path
  traversal regex, json.dumps for all output, no `set -x`.
- Phase 1 test list at lines 235-249 is now comprehensive and internally consistent with
  the silent-skip policy.
