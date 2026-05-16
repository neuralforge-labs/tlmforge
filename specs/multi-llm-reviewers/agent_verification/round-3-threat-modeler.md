# Round 3 Threat-Modeler Review — multi-llm-reviewers

**Reviewer:** threat-modeler
**Iteration:** 3
**Date:** 2026-05-16

---

## Prior-Finding Verification

### CRITICAL-1: Blanket `OPENAI_API_KEY=:*` permission entry
**Status: FIXED**

README.md line 29 now specifies `Bash(ai_review_openai.sh:*)`. The blanket
prefix-wildcard pattern that would auto-approve arbitrary commands prefixed with the
key assignment is gone. The permission is scoped to the specific script path. Fix is
correct and sufficient.

### CRITICAL-2: Unvalidated marker content → path traversal → exfiltration to api.openai.com
**Status: FIXED**

README.md lines 44-46 document the Python validation:
`re.fullmatch(r'[a-zA-Z0-9_-]+', feature_name)` with reject-on-failure → exit 2,
status=skipped.

README.md lines 262-263 document the shell validation:
`[[ ! "$feature" =~ ^[a-zA-Z0-9_-]+$ ]] → exit 2 skipped`.

Verification criterion 4 (README.md line 383) explicitly tests the `../etc/passwd`
injection case. The test plan at Phase 1 line 245 tests `mode=plan + marker with path
traversal → exit 2, status=skipped`. Both paths (Python and shell) independently
enforce the regex. Fix is correct and sufficient.

### HIGH-1: `git diff HEAD` sent to api.openai.com without acknowledged risk
**Status: FIXED (accepted risk)**

Risk audit table (README.md line 333) now has an explicit row: diff and plan content
may include accidentally staged `.env` files, secrets, or NDA-sensitive architecture.
The row names this as accepted risk for the opt-in feature. The acknowledgment is
sufficient.

### HIGH-2: API error messages interpolated into JSON string construction
**Status: FIXED**

README.md lines 49, 104, and the architecture section explicitly state: "ALL output
via json.dumps(), zero string interpolation for fields that contain external data."
The skipped sidecar minimum fields are documented. fix is correct and sufficient.

---

### Round 2 MEDIUM: Silent-skip stealthy reviewer-suppression window
**Status: ACCEPTED (not fixed by design)**

The round-2-fixes document confirms this is accepted risk on the grounds that the same
risk exists for the Gemini reviewer today. The risk remains in the profile but is not
blocking.

### Round 2 NIT-1: Stale risk audit table LOW row still says `status=error`
**Status: NOT FIXED**

README.md line 337 still reads:
`Results in status=error instead of status=skipped; correct graceful behavior`

The round-2-fixes doc says the exit-code contract *comment* at line 97 was updated,
but the risk audit *table* row retains the stale language. The Phase 1 constraint
section (line 207) correctly says ALL failures → status=skipped; the table contradicts
it. An implementer reading the table in isolation gets the wrong behavior spec. This
remains a nit.

### Round 2 NIT-2: False assertion about `--output` path in sensitive surface inventory
**Status: NOT FIXED**

README.md line 122 still reads:
`--output path — parent directory existence checked before write; no traversal check
needed (script writes to where called from, not user-supplied arbitrary paths)`

The `--output` argument IS user-supplied via CLI. The rationale ("writes to where called
from") is false — the caller controls where that is. The assertion is inaccurate. The
actual mitigation is that the `Bash(ai_review_openai.sh:*)` permission narrows which
script can be invoked, and the output path must be under a directory that exists
(parent-dir check exits 64 if not). That is a partial mitigation, not the claimed one.
The severity is low (requires compromised orchestrator), but the documentation should
not state a false justification.

---

## New Findings (Round 2 → Round 3 changes only)

### Finding N-1: Log write to `~/.cache/tlmforge/llm_reviewer.log` uses raw exception text
**Severity: nit**

The plan says all JSON *output* uses `json.dumps()`, but the log write (raw exception
text to the log file) is not constrained. An `openai.APIError` whose message contains
newlines could produce multi-line log entries that break naive log parsers or grep-based
debugging. This is not a security threat (the log is local; only an attacker who can
control the API error message could exploit it, and the impact is only log readability).
Worth noting for implementers: write a single-line entry (e.g., replace newlines with
`\n` literal or use `repr()`). Not a convergence blocker.

---

## Round 3 Summary

| Finding | Round | Status | Severity |
|---|---|---|---|
| CRITICAL-1: blanket key-prefix permission | 1 | FIXED | — |
| CRITICAL-2: path traversal via marker | 1 | FIXED | — |
| HIGH-1: diff sent outbound (acknowledged risk) | 1 | ACCEPTED | — |
| HIGH-2: API error messages in JSON | 1 | FIXED | — |
| MEDIUM-1: README size guard absent | 1 | UNADDRESSED | medium |
| MEDIUM-2: model name unvalidated | 1 | UNADDRESSED | medium |
| MEDIUM: silent-skip suppression window | 2 | ACCEPTED | — |
| NIT-1: stale status=error in risk table | 2 | NOT FIXED | nit |
| NIT-2: false --output assertion | 2 | NOT FIXED | nit |
| N-1: log write raw exception text | NEW | open | nit |

**All CRITICALs from Round 1 are FIXED. All HIGHs are resolved or documented as
accepted risk. No new critical or high surfaces introduced by the Round 2 → Round 3
design changes.**

**Verdict: approve_with_warnings**

The two unresolved mediums (size guard, model name) and three nits are not convergence
blockers. The design is safe to implement provided the Phase 1 implementer follows the
documented constraints: `re.fullmatch` validation on marker, `json.dumps()` for all
output fields, `set -euo pipefail` without `set -x` in shell, and atomic writes.
