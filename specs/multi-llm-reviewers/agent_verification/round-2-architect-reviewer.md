# Architect-Reviewer Round 2 — multi-llm-reviewers

## VERDICT: NEEDS REVISION

## Summary

Round 1 critical and most high findings are addressed. Two new critical issues were introduced by the round-1 fixes themselves: the Phase 1 test expectations and Verification Criterion 1 were not updated to reflect the silent-skip user requirement, creating a direct contradiction between the implementation spec and the test spec that will cause incorrect implementation.

---

## Round-1 Finding Verdicts

### C1 — `expected_roles` coupling / `REVIEWER_NAME` not pinned
**FIXED**

Evidence:
- README.md:143 — `REVIEWER_NAME = "openai"` constant specified in Phase 0 Step 2
- README.md:211 — "REVIEWER_NAME = 'openai' — always this string in the output JSON" in Phase 1
- README.md:299-304 — Phase 3 concrete Python pseudocode for conditional `expected_roles`
- README.md:306-308 — reviewer field contract documented explicitly
- README.md:242 — test asserts `reviewer="openai"` in all output paths

### C2 — Chat Completions API deprecated for `gpt-5.5`
**FIXED**

Evidence:
- README.md:55-57 — constraints section mandates `client.responses.create()`, states Chat Completions is in maintenance mode
- README.md:183-193 — Phase 1 shows full `client.responses.create()` call with `response.output_text` extraction
- README.md:337-338 — decision recorded with rationale

### C3 — No atomic-write guarantee in Python script
**FIXED**

Evidence:
- README.md:50-53 — constraints section mandates `tempfile.NamedTemporaryFile(dir=output_dir, delete=False)` + `os.replace()`, explicitly warns against `shutil.move`
- README.md:106-111 — architecture diagram shows the exact write sequence
- README.md:143 — Phase 0 Step 2 references atomic write
- README.md:160-161 — Phase 0 tests include atomic write verification scenario

### W1 — `.strip()` not applied to marker read
**PARTIALLY FIXED**

The regex guard (`[a-zA-Z0-9_-]+`) blocks the original path-corruption bug because `\n` fails the pattern. However, the effect is wrong: a marker with a trailing newline (written by `echo feature-name > marker`) will produce `status=skipped` instead of proceeding correctly. This is a silent false-skip that will confuse users.

Two gaps remain:
1. README.md:179-181 — Phase 1 pre-flight shows the `re.fullmatch` validation but does not explicitly call `.strip()` before it. The fixes doc (round-1-fixes.md:30) claimed "Phase 1 pre-flight adds `.strip()` before regex validation" but this is not reflected in the plan text.
2. The trailing-newline fixture test (also claimed in round-1-fixes.md:30) does not appear in the Phase 1 test list (README.md:231-244). The only related test (README.md:241) covers spaces, not trailing newlines. The test for "marker with trailing newline → path resolves correctly" is missing.

What to do: Add `.strip()` explicitly to the Phase 1 pre-flight pseudocode before the `re.fullmatch` call, and add a test case: "marker file containing 'my-feature\n' (trailing newline) → `mode=plan` proceeds to API call with correct README path."

### W2 — No token budget guard for plan mode
**FIXED**

README.md:326-333 risk audit row explicitly documents this as an accepted risk, notes that silent skip on quota error serves as the effective mitigation, and marks the explicit guard as a future improvement. Explicitly documented, not silently ignored.

### W3 — `gpt-5.5` unversioned alias
**FIXED**

README.md:8 confirms the resolved form `gpt-5.5-2026-04-23` is documented. README.md:291-296 shows the `TLMFORGE_OPENAI_MODEL` override in the SKILL.md config table. README.md:330 notes model-not-found as a handled risk. The pinning mechanism and risk are both acknowledged.

---

## Critical Issues (must fix before proceeding)

### NEW-C1 — Phase 1 test expectations contradict silent-skip requirement (lines 236-238)

Three test cases in the Phase 1 test additions assert `status=error` + meta CRITICAL + exit 0 for conditions that are LLM provider failures:

```
Both calls invalid JSON → status=error + meta CRITICAL with suggested_fix, exit 0
Auth error (mocked) → status=error + meta CRITICAL with suggested_fix, exit 0
Truncated response → retry → still truncated → status=error, exit 0
```

This directly contradicts:
- Architecture constraint at lines 59-66: "ALL LLM provider failures must silently skip — NEVER block convergence... ALL error conditions write `status=skipped` and exit 2"
- Phase 1 implementation spec at lines 200-208: "ALL failure paths write `status=skipped` and exit 2 (NEVER `status=error` or synthetic meta CRITICAL). This includes... both retries producing invalid/truncated JSON, enum mismatch after retry."

Auth error, double-retry-invalid-JSON, and truncation after retry are all LLM provider failures. A developer writing code to pass these test expectations will produce `status=error` behavior that breaks the silent-skip contract and will block convergence on a bad key.

Fix: Change those three test expectations to:
- "Both calls invalid JSON → status=skipped, exit 2, reason logged to ~/.cache/tlmforge/llm_reviewer.log"
- "Auth error (mocked) → status=skipped, exit 2, reason logged"
- "Truncated response → retry → still truncated → status=skipped, exit 2, reason logged"

### NEW-C2 — Verification Criterion 1 contradicts silent-skip requirement (line 374)

Criterion 1 asserts:

```
TLMFORGE_ENABLE_OPENAI=1 OPENAI_API_KEY=fake ./ai_review_openai.sh --output /tmp/t.json --iteration 1 --mode code
exits 0, JSON has status=error, reviewer="openai", meta CRITICAL has suggested_fix
```

A fake API key will cause an OpenAI auth error (`openai.AuthenticationError`), which is an LLM provider failure. Per the silent-skip requirement it must produce `status=skipped` + exit 2. A developer verifying against this criterion will either (a) implement the wrong `status=error` behavior to satisfy it, or (b) correctly implement `status=skipped` and then incorrectly conclude their implementation is broken because it fails criterion 1.

Fix: Change Criterion 1 to assert exit 2 + `status=skipped` + reason logged. Add a separate Criterion 1b that mocks the OpenAI call successfully (or uses a valid key in CI) to verify the exit 0 + `status=ok` happy path.

---

## Warnings (should fix)

### NEW-W1 — Exit-code contract comment still mentions `status=error` for normal operation (line 97)

The architecture block comment reads:
```
0  → JSON sidecar written (status=ok or status=error with synthetic CRITICAL)
```

After the silent-skip requirement, `status=error` with synthetic CRITICAL should never appear under normal LLM provider failures. The comment is technically true for disk-full edge cases but will mislead implementers about expected behavior. The contrast with the `status=skipped` path (exit 2) is no longer clear from this comment alone.

Fix: Update to "exit 0 → status=ok (successful review) or status=error (implementation-level bug only, e.g. disk full — NOT for LLM provider failures). LLM provider failures always use exit 2 + status=skipped."

---

## Suggestions (nice to have)

- The system prompt at Phase 1 Step 2 (lines 214-223) mentions `suggested_fix REQUIRED if severity=critical`. With all critical findings now coming only from successful reviews, this is consistent. No issue — just confirming it's coherent after the silent-skip change.
- Phase 2 Gemini extension tests (lines 270-278) do not include a test for empty diff in `mode=code`. The plan mentions this in the steps (line 263) but the test list at line 274 only covers `mode=plan` scenarios and references the existing tests. Worth adding explicitly: "`--mode code` + empty diff → exit 2, skipped JSON" to the Phase 2 test list to match Phase 1.

---

## What's Good

- The silent-skip requirement is correctly reflected in the Phase 1 implementation spec (lines 200-208) — the implementation description is right. Only the test spec and verification criteria were missed.
- The atomic-write constraint (C3) is now thoroughly specified: in constraints, in the architecture diagram, in Phase 0 steps, and in Phase 0 tests. This is the right level of specification for a concurrency-sensitive operation.
- `REVIEWER_NAME = "openai"` as a hardcoded constant (C1) is the correct pattern — not derived from the model name, not from an env var. Prevents the convergence key-mismatch class of bugs entirely.
- The `Bash(ai_review_openai.sh:*)` permission entry (vs. the rejected `Bash(OPENAI_API_KEY=:*)`) is correctly specified and the rationale is documented.
- Marker validation regex (`[a-zA-Z0-9_-]+`) is specified in both Python (re.fullmatch) and shell (`=~` pattern), covering both scripts consistently.
- The `json.dumps()` for all output constraint is well-specified in the constraints section and in the decisions log.
