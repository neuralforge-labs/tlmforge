# Round 2 Tester Review — multi-llm-reviewers
**Iteration:** 2
**Verdict:** needs_revision
**Date:** 2026-05-16

---

## Round-1 Finding Verdicts

### EC-1 — Error handler omits `suggested_fix` on synthetic CRITICAL
**Verdict: FIXED**

The fix eliminated the entire failure class by changing the error model globally.
ALL LLM provider failure conditions now write `status=skipped` + exit 2; `status=error`
is reserved only for implementation bugs (disk full etc.). Evidence:
- Constraints section: "ALL error conditions write `status=skipped` and exit 2."
- Phase 1 steps: "ALL failure paths write `status=skipped` and exit 2 (NEVER
  `status=error` or synthetic meta CRITICAL)."
- Architecture exit-code table: exit 2 covers all graceful skips including auth
  failure, quota, truncation, enum mismatch.

---

### EC-2 — Empty diff in `mode=code` produces false approval
**Verdict: FIXED**

Phase 1 pre-flight: "`mode=code` + empty `git diff HEAD` → skipped (no empty-diff
reviews)". Phase 2 step 3 mirrors this for the Gemini shell script. Tests added to
both Phase 1 and Phase 2 test plans.

---

### EC-3 — Truncated response accepted as complete
**Verdict: PARTIALLY FIXED**

The prose constraint correctly handles truncation: retry once, still truncated →
`status=skipped` + exit 2 + log. However, the Phase 1 test plan (line 238 of README)
specifies:

  "Truncated response → retry → still truncated → **status=error, exit 0**"

This directly contradicts the constraint. An implementer following TDD red→green will
write code that produces `status=error` for truncated responses, violating the user
requirement. See NEC-1 below for full scope of this contradiction.

---

### EC-4 — Uppercase severity passes shape check, missed by convergence
**Verdict: FIXED**

Enum validation before accept is specified. On mismatch → retry. After retry →
`status=skipped` + exit 2 + log. Test added: "First call uppercase severity
('CRITICAL') → retry → second valid → exit 0."

---

### EC-5 — Absent marker + double-slash resolves to wrong `specs/README.md`
**Verdict: FIXED**

Explicit marker existence + non-emptiness check in both Python (Phase 1 pre-flight)
and shell (Phase 2 step 2). Test added to both test plans including a decoy
`specs/README.md` scenario.

---

### EC-6 — Missing output parent directory causes exit 1 with no JSON sidecar
**Verdict: FIXED**

Phase 0 step 1 and Phase 2 step 5 both specify the check. Architecture exit-code
table: exit 64 for missing output parent directory. Phase 0 tests include this
scenario.

---

### EC-7 — `reviewer` field not pinned to `"openai"`
**Verdict: FIXED**

`REVIEWER_NAME = "openai"` constant specified in Phase 0 stub. System prompt in
Phase 1 includes `reviewer ("openai")`. Phase 3 documents the reviewer-field →
role-name contract. Test: "`reviewer` field in all output paths is exactly
`"openai"`".

---

### EC-8 — Non-integer `--iteration` not validated
**Verdict: FIXED**

Shell: `[[ "$ITERATION" =~ ^[0-9]+$ ]]` → exit 64. Python: `--iteration` validated
as integer in arg parse. Phase 2 also adds integer validation for the Gemini script.
Tests cover "abc" as iteration value → exit 64.

---

### EC-9 — Feature name with spaces causes bash word-splitting
**Verdict: FIXED**

Phase 2 step 2 specifies quoted expansion: `feature_name="$(cat "$marker")"` and
`"specs/${feature_name}/README.md"`. Regex `[a-zA-Z0-9_-]+` additionally catches
spaces before path construction. Tests added in both Phase 1 and Phase 2 test plans.

---

### EC-10 — No test planned for schema enum mismatch
**Verdict: FIXED**

Phase 1 test plan now includes: "First call uppercase severity ('CRITICAL') →
retry → second valid → exit 0" and "Both calls invalid JSON → ..." exercising the
retry path triggered by enum mismatch.

---

## New Findings

### NEC-1 [CRITICAL] — Test plan contradicts `status=skipped` constraint in 4 places

**Trigger:** Phase 1 test plan (README lines 235-238) specifies outcomes that
contradict the global constraint at lines 202-207.

**Contradicting test assertions:**
1. "Both calls invalid JSON → `status=error` + meta CRITICAL with `suggested_fix`,
   exit 0"
2. "Auth error (mocked) → `status=error` + meta CRITICAL with `suggested_fix`,
   exit 0"
3. "Truncated response → retry → still truncated → `status=error`, exit 0"

**What the constraint says (lines 202-207):**
"ALL failure paths write `status=skipped` and exit 2 (NEVER `status=error` or
synthetic meta CRITICAL). This includes API auth failure, quota exceeded, model not
found, connection error, both retries producing invalid/truncated JSON, enum mismatch
after retry."

**Impact:** TDD discipline means the tests are written first. Tests written from
the Phase 1 test list will assert `status=error`; implementation will be written to
pass those tests; the result is a reviewer that blocks convergence on auth failure
— the exact opposite of the user requirement. This is a production-blocking
contradiction in the spec.

**Fix:**
Change all three test assertions to:
- "Both calls invalid JSON → `status=skipped`, exit 2, logged"
- "Auth error (mocked) → `status=skipped`, exit 2, logged"
- "Truncated response → retry → still truncated → `status=skipped`, exit 2, logged"
Remove the `suggested_fix` assertion from these test cases — `status=skipped`
JSON does not carry findings arrays.

---

### NEC-2 [CRITICAL] — Verification criterion 1 contradicts the skip-all-failures requirement

**Trigger:** Running verification criterion 1 after implementation.

**Text of criterion 1 (README line 374):**
```
TLMFORGE_ENABLE_OPENAI=1 OPENAI_API_KEY=fake ./ai_review_openai.sh
  --output /tmp/t.json --iteration 1 --mode code
exits 0, JSON has status=error, reviewer="openai", meta CRITICAL has suggested_fix
```

**What a fake/invalid key means:** auth failure → LLM provider failure. Per the
constraint, this must produce `status=skipped` + exit 2. The verification criterion
says exit 0 + `status=error`.

**Impact:** Phase-end verification at Stage 4 will run this exact command. If the
implementation correctly follows the constraint (exit 2, skipped), the phase-end
auditor will mark it as failing verification criterion 1. If the implementation is
changed to pass this criterion, it violates the user requirement. Either way, one
gate fails.

**Fix:**
Change verification criterion 1 to:
```
TLMFORGE_ENABLE_OPENAI=1 OPENAI_API_KEY=fake ./ai_review_openai.sh
  --output /tmp/t.json --iteration 1 --mode code
exits 2, JSON has status=skipped, reviewer="openai"
```

---

### NEC-3 [HIGH] — `status=skipped` JSON structure not defined; schema compatibility unverified

**Trigger:** Convergence engine receiving a `status=skipped` JSON sidecar from the
OpenAI reviewer.

**Problem:** The plan states `review_schema.json` is out-of-scope for changes, but
never specifies:
1. What fields a `status=skipped` JSON must contain (only `status`? also `reviewer`,
   `schema_version`, `iteration`? what about `findings`?).
2. Whether `review_schema.json` accepts `"skipped"` as a valid value for the `status`
   field (it may only enumerate `"ok"` and `"error"`).

If `review_schema.json` does not include `"skipped"` as a valid status enum value,
the convergence engine's schema validator would reject the skipped JSON — potentially
treating it as a missing reviewer and injecting a `reviewer_json_missing` CRITICAL.
This is the failure mode the skip design is supposed to prevent.

**Impact:** Silent convergence block on any LLM provider failure, contradicting the
entire user requirement.

**Fix:** Add to the plan (probably Phase 0 or the Architecture section):
- State the minimum required fields for `status=skipped` output:
  `{reviewer, schema_version, iteration, status: "skipped"}` — no `findings` array
  required.
- Verify `review_schema.json` already accepts `"skipped"` as a valid status value,
  OR note that the convergence engine checks `status` by string value before schema
  validation and the skipped path bypasses full schema validation.
- Add a test: convergence engine given a `status=skipped` sidecar from "openai"
  does not inject `reviewer_json_missing` CRITICAL.

---

## Summary

| Finding | Verdict |
|---|---|
| EC-1 | FIXED |
| EC-2 | FIXED |
| EC-3 | PARTIALLY FIXED (prose correct; test plan contradicts) |
| EC-4 | FIXED |
| EC-5 | FIXED |
| EC-6 | FIXED |
| EC-7 | FIXED |
| EC-8 | FIXED |
| EC-9 | FIXED |
| EC-10 | FIXED |
| NEC-1 (new) | CRITICAL — test plan contradicts constraint in 3 test cases |
| NEC-2 (new) | CRITICAL — verification criterion 1 contradicts skip requirement |
| NEC-3 (new) | HIGH — `status=skipped` schema compatibility unverified |

**Two issues remain that will cause production bugs if not fixed before implementation starts.**
