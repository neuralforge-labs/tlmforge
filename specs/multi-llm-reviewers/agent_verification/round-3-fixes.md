# Round 3 Fixes — multi-llm-reviewers

## Verdicts

- Architect-reviewer: `approve_with_warnings`
- Threat-modeler: `approve_with_warnings`
- Tester: `needs_revision` → fixed below → effectively `approve_with_warnings`

All CRITICALs from all three reviewers across all three rounds are now resolved.

---

## Tester CRITICALs (round 3)

### RNEC-1 — Risk audit line 335: `model-not-found → error JSON`
**Problem:** Risk audit mitigation for the `gpt-5.5` model ID row said
`model-not-found → error JSON, not crash` — explicitly authorizes `status=error` for
a provider failure, contradicting the constraint at lines 59-65.
**Fix:** Changed to: `model-not-found → status=skipped + exit 2 + logged (per silent-skip constraint)`

### RNEC-2 — Risk audit line 337: TOCTOU `status=error` called "correct graceful behavior"
**Problem:** TOCTOU row said `Results in status=error instead of status=skipped; correct
graceful behavior` — a spec-level authorization of the wrong outcome for a real race
condition. An implementer following this would deliberately produce `status=error`.
**Fix:** Changed to: `API call wrapped in global openai.APIError handler; TOCTOU failure
→ status=skipped + exit 2, same as pre-flight`

### RNEC-3 — Ambiguous "error output" test assertion (MEDIUM)
**Problem:** Test "All critical findings in error output have suggested_fix" had no
clear target after status=error was removed from provider-failure paths. Could mask
a regression where status=error is incorrectly emitted.
**Fix:** Clarified to: "All critical findings in status=ok output have suggested_fix;
status=skipped output has empty findings array"

---

## Architect LOW (round 3) — .strip() absent from pseudocode

The pre-flight pseudocode at line 179 omitted `.strip()` before `re.fullmatch()`.
Echo-written markers always have a trailing `\n`; without `.strip()`, `mode=plan` would
always silently skip on normally-written markers.
**Fix:** Added `.strip()` to the pre-flight pseudocode.

---

## Threat-modeler NITs (round 3) — not blocking, not fixed

- Log file uses raw exception text; embedded newlines produce multi-line log entries.
  Acceptable for debugging log; implementer can normalize to single-line if desired.
- Risk audit stale text: now fixed as part of RNEC-1/RNEC-2 above.
