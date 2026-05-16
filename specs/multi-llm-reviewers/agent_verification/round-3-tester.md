# Round 3 Tester Review — multi-llm-reviewers
**Iteration:** 3
**Verdict:** needs_revision
**Date:** 2026-05-16

---

## Round-2 Finding Verdicts

### NEC-1 — Test plan contradicts `status=skipped` constraint (3 test cases)
**Verdict: FIXED**

All three Phase 1 test cases that previously specified `status=error + meta CRITICAL +
exit 0` have been corrected. Current README lines 241-243:
- "Both calls invalid JSON → status=skipped, exit 2, failure logged to `~/.cache/tlmforge/llm_reviewer.log`"
- "Auth error (mocked) → status=skipped, exit 2, failure logged"
- "Truncated response → retry → still truncated → status=skipped, exit 2, failure logged"

All three now correctly match the constraint at lines 202-207.

---

### NEC-2 — Verification criterion 1 contradicts skip-all-failures requirement
**Verdict: FIXED**

README line 379:
```
TLMFORGE_ENABLE_OPENAI=1 OPENAI_API_KEY=fake ./ai_review_openai.sh --output /tmp/t.json --iteration 1 --mode code
exits 2, JSON has `status=skipped`, `reviewer="openai"`
```

Correctly changed from the broken `exits 0, status=error` to `exits 2, status=skipped`.
Criterion 1b is present at line 380, covering the mocked happy path (exits 0, status=ok,
validates against review_schema.json).

---

### NEC-3 — `status=skipped` schema compatibility unverified, minimum fields undocumented
**Verdict: FIXED**

Phase 1 constraints (lines 211-213) now document minimum skipped-sidecar fields:
`reviewer`, `schema_version`, `iteration`, `status="skipped"`. Findings array must be
present but may be empty `[]`. Confirmed that `review_schema.json` already enumerates
`"skipped"` in the status enum.

---

## Previous Round-1 Findings — Carry-Forward Verification

| Finding | Round-2 Verdict | Round-3 Confirmation |
|---|---|---|
| EC-1 (suggested_fix missing on synthetic CRITICAL) | FIXED | CONFIRMED — error path eliminated; only status=skipped for provider failures |
| EC-2 (empty diff false approval) | FIXED | CONFIRMED — line 238: exit 2, status=skipped, OpenAI not called |
| EC-3 (truncated response accepted) | FIXED via NEC-1 | CONFIRMED — line 243 now correct |
| EC-4 (uppercase severity enum miss) | FIXED | CONFIRMED — lines 239-240 cover retry path |
| EC-5 (absent marker double-slash) | FIXED | CONFIRMED — lines 244, 276 cover both scripts |
| EC-6 (missing output parent directory) | FIXED | CONFIRMED — exit 64 in Phase 0 and Phase 2 |
| EC-7 (reviewer field not pinned) | FIXED | CONFIRMED — REVIEWER_NAME = "openai" constant |
| EC-8 (non-integer --iteration) | FIXED | CONFIRMED — lines 155, 268, exit 64 |
| EC-9 (feature name with spaces) | FIXED | CONFIRMED — regex + quoted expansion, line 263-264 |
| EC-10 (no enum mismatch test) | FIXED | CONFIRMED — lines 239-241 cover retry+mismatch |
| TM-C1 (blanket key permission) | FIXED | CONFIRMED — Bash(ai_review_openai.sh:*) used |
| TM-C2 (path traversal) | FIXED | CONFIRMED — regex validation + test at line 245 |
| TM-H2 (JSON boundary breakage) | FIXED | CONFIRMED — json.dumps() rule at line 103 |
| ARCH-C2 (wrong API used) | FIXED | CONFIRMED — Responses API specified throughout |
| ARCH-C3 (no atomic write) | FIXED | CONFIRMED — tempfile + os.replace() pattern at lines 106-110 |

---

## New Findings

### RNEC-1 [CRITICAL] — Risk audit at line 335 says `model-not-found → error JSON`

**Trigger:** An implementer reads the risk audit while implementing the model-not-found
error path.

**Exact text (README line 335):**
```
| HIGH | `gpt-5.5` model ID may require exact versioned form in some API calls
        | `TLMFORGE_OPENAI_MODEL` env override; model-not-found → error JSON, not crash |
```

**What the constraint says (lines 59-65):**
"ALL error conditions write `status=skipped` and exit 2. This includes: expired key,
free-tier quota exhausted, model not found, connection timeout..."

`model-not-found` is explicitly named in the constraint as a condition requiring
`status=skipped`. The risk audit says "error JSON" — this means `status=error`.

**Impact:** TDD discipline means an implementer reads the spec for guidance on
what each path should produce. The risk audit is part of the spec. An implementer
treating the risk audit as authoritative for the model-not-found case will write
code that produces `status=error` and exits 0 — blocking convergence exactly like
EC-1 was intended to fix. The contradiction is undetectable without cross-reading
two sections.

**Fix:**
Change line 335 mitigation column from:
`model-not-found → error JSON, not crash`
to:
`model-not-found → status=skipped + exit 2 (treated identically to auth failure);
TLMFORGE_OPENAI_MODEL env override available for model ID flexibility`

---

### RNEC-2 [CRITICAL] — Risk audit at line 337 says TOCTOU produces `status=error` and calls it "correct graceful behavior"

**Trigger:** An implementer reads the risk audit while handling the TOCTOU race between
`os.environ.get("OPENAI_API_KEY")` presence check and `client = openai.OpenAI(api_key=...)`.

**Exact text (README line 337):**
```
| LOW | TOCTOU between key presence check and API call
      | Results in status=error instead of status=skipped; correct graceful behavior |
```

**What the constraint says (lines 59-65):**
"ALL error conditions write `status=skipped` and exit 2... The user must be able to
run the full feature-development skill with a broken or free-tier LLM key without any
workflow interruption."

The risk audit explicitly labels `status=error` for TOCTOU as "correct graceful
behavior." This is wrong — `status=error` is NOT correct graceful behavior for any
LLM provider failure. It is the incorrect outcome. The constraint is unambiguous.

**Impact:** Two consequences:
1. An implementer may deliberately implement the TOCTOU path to produce `status=error`
   because the risk audit says that is acceptable.
2. A phase-end auditor or code reviewer reading the risk audit may incorrectly accept
   `status=error` output from the TOCTOU path as "by design."

Either way, this is a spec-level authorization of the wrong behavior for a real edge
case.

**Fix:**
Change line 337 to:
```
| LOW | TOCTOU between key presence check and API call | The API call itself is wrapped
in the global openai.APIError handler; auth failure during the call → status=skipped +
exit 2 (same as pre-flight key check). No special handling needed. |
```

---

### RNEC-3 [MEDIUM] — Phase 1 test at line 249 references "error output" with `suggested_fix` assertion, but `status=error` only applies to disk-full bugs

**Trigger:** An implementer writes the test at line 249:
"All critical findings in error output have `suggested_fix` (string, len >= 8)"

**Problem:** After the NEC-1 fix, `status=skipped` JSON carries no findings array
(or an empty one). `status=error` only occurs for disk-full / implementation bugs —
in which case a critical finding with `suggested_fix` may or may not be written
depending on whether the error is in the write path itself. The test scenario is
ambiguous: "error output" could mean `status=error` JSON (disk bug) or the skipped
JSON for provider failures. If it means the former, it's untestable in unit tests.
If it means the latter, the assertion should fail because skipped JSON has empty findings.

The test is not harmful on its own (a vacuously passing assertion harms nothing), but
it creates confusion and could mask a real regression if the implementer writes
`status=error` output with findings in the wrong path to satisfy this test.

**Fix:**
Replace line 249 with a precise assertion:
"`status=skipped` JSON has `findings=[]`; `status=ok` JSON with critical findings all
have `suggested_fix` non-empty (string, len >= 8)"

---

## Retry policy — verified

The retry-once policy correctly routes to `status=skipped` on second failure in all cases:
- Line 198: "Retry once on invalid JSON or schema enum mismatch."
- Lines 202-207: "ALL failure paths write `status=skipped` and exit 2... both retries
  producing invalid/truncated JSON, enum mismatch after retry."
- Tests at lines 241, 243 cover retry exhaustion → skipped.

The retry path to `status=skipped` is internally consistent between constraints and
test plan.

---

## Schema consistency — verified

- `review_schema.json` accepts "skipped" — confirmed in Phase 1 constraints.
- Minimum skipped-sidecar fields documented: reviewer, schema_version, iteration,
  status="skipped", findings=[].
- Exit-code contract at lines 96-101 is internally consistent with Phase 0 and Phase 1
  steps.
- No schema changes planned (confirmed out-of-scope).

---

## Criterion 1b — verified

Line 380 is present and correctly specifies:
"With a valid mocked OpenAI response: exits 0, JSON has `status=ok`, `reviewer="openai"`,
validates against `review_schema.json`"

---

## Summary

| Finding | Round-3 Verdict |
|---|---|
| NEC-1 (test plan contradicts constraint) | FIXED |
| NEC-2 (criterion 1 status=error) | FIXED |
| NEC-3 (schema/minimum fields undocumented) | FIXED |
| RNEC-1 (risk audit line 335: model-not-found → error JSON) | CRITICAL — must fix |
| RNEC-2 (risk audit line 337: TOCTOU → status=error called "correct") | CRITICAL — must fix |
| RNEC-3 (line 249: "error output" test assertion ambiguous) | MEDIUM — should fix |

**Two residual CRITICAL contradictions exist in the Risk Audit section that were not
touched by the round-2 fix pass. Both authorize `status=error` for provider-failure
conditions explicitly covered by the silent-skip constraint. They will guide an
implementer toward the wrong behavior.**

**Fix required before implementation starts:** Update lines 335 and 337 of README.md
to align with the `status=skipped` constraint. These are two-line edits.
