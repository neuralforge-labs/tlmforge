# Round 1 Fixes — multi-llm-reviewers

## Summary

Round 1 produced 3 × CRITICAL (architect), 2 × CRITICAL (threat-modeler), 7 × CRITICAL
(tester), 2 × HIGH (threat-modeler), 2 × HIGH (tester), plus a user-supplied requirement
after round 1 review. All CRITICALs and HIGHs addressed below.

---

## Architect-reviewer findings

### C1 — `expected_roles` coupling unresolved; `reviewer` field not pinned
**Fix:** Phase 3 now specifies a concrete SKILL.md template showing conditional
`expected_roles` construction (Python pseudocode with the exact env-var checks).
Phase 1 spec now explicitly requires `REVIEWER_NAME = "openai"` hardcoded constant,
with a test: `assert data["reviewer"] == "openai"`. The SKILL.md section documents
the reviewer-field → role-name contract.

### C2 — Chat Completions API deprecated for `gpt-5.5`
**Fix:** Phase 1 spec now uses `client.responses.create()` with `response.output_text`
extraction. Test mocks patched accordingly (`openai.OpenAI().responses.create`).

### C3 — No atomic-write guarantee in Python script
**Fix:** Phase 0 spec now mandates `tempfile.NamedTemporaryFile(dir=output_dir,
delete=False)` + `os.replace(tmp.name, output_path)`. Phase 0 tests include an
atomic-write verification scenario. The architecture diagram documents the write sequence.

### W1 — `.strip()` not applied to active-feature marker read
**Fix:** Phase 1 pre-flight adds `.strip()` before regex validation. Test: fixture
with trailing newline produces correct path.

### W2 — No token budget guard for plan mode
**Fix:** Added to risk audit as an accepted risk with a deferred note. The user
requirement (all LLM failures → skip) means an oversized plan → quota error → status=skipped,
not a convergence block. A `TLMFORGE_MAX_PLAN_TOKENS` guard is noted as a future improvement.

---

## Threat-modeler findings

### CRITICAL-1 — `Bash(OPENAI_API_KEY=:*)` blanket execution surface
**Fix:** Settings.json entry changed to `Bash(ai_review_openai.sh:*)`. The README scope
section, constraints section, and Phase 0 steps all updated to reflect this. The old
`Bash(OPENAI_API_KEY=:*)` entry is not added.

### CRITICAL-2 — Unvalidated active-feature marker → path traversal → exfiltration
**Fix:** Both Python script (Phase 1) and Gemini extension (Phase 2) now require
`re.fullmatch(r'[a-zA-Z0-9_-]+', feature_name)` before path construction. On validation
failure → `status=skipped`, exit 2. Tests added: marker with `../etc/passwd`, marker with
spaces, marker empty — all must exit 2 with status=skipped.

### HIGH-1 — `git diff HEAD` sent to OpenAI without acknowledging the data-trust boundary
**Fix:** Added to risk audit section: "Accepted risk — opt-in only; documented here.
Future: pre-flight secret scan before send." The sensitive surface inventory now explicitly
names the data sent outbound.

### HIGH-2 — API error messages interpolated into shell JSON string → JSON breakage
**Fix:** Phase 1 mandates `json.dumps()` for ALL output. The Python script never uses
string interpolation for fields containing external data. The constraint is in the
architecture section and repeated in Phase 1 steps.

---

## Tester findings

### EC-1 — Error handler omits `suggested_fix` on synthetic CRITICAL
**Fix:** All failure paths now write `status=skipped` (not `status=error` with synthetic
CRITICAL) per the user's "silent skip" requirement. This eliminates the class of bugs
where a malformed synthetic finding blocks convergence. The only `status=error` path
remaining is for implementation bugs (disk full etc.).

### EC-2 — Empty diff in `mode=code` produces false approval
**Fix:** Both Python and Gemini extension: after getting diff content, check `strip() ==
""`. If empty → write_skipped + exit 2. Test added.

### EC-3 — Truncated response (`finish_reason` equivalent) accepted as complete
**Fix:** Check for truncation before accepting. Truncated → retry once. Still truncated
after retry → write_skipped + exit 2 (per silent-skip requirement) + log to
`~/.cache/tlmforge/llm_reviewer.log`.

### EC-4 — Uppercase severity passes shape check, missed by convergence
**Fix:** Validate enum values after parsing OpenAI response. On mismatch → retry. After
retry still invalid → write_skipped + exit 2 + log. Test added (highest-value test).

### EC-5 — Absent marker + double-slash resolves to wrong `specs/README.md`
**Fix:** Explicit marker existence + non-emptiness check in both Python and shell before
path construction. If absent or empty → write_skipped + exit 2. Test: decoy
`specs/README.md` present, marker absent → exit 2.

### EC-6 — Missing output parent directory → exit 1 (undefined)
**Fix:** Both shell wrapper and Python check `dirname(OUTPUT)` exists. If not → exit 64
with stderr message. Test added.

### EC-7 — `reviewer` field not pinned to `"openai"`
**Fix:** `REVIEWER_NAME = "openai"` hardcoded constant. Test: assert `data["reviewer"] ==
"openai"`. See also architect C1 fix.

### EC-8 — Non-integer `--iteration` → undefined exit code
**Fix:** Shell validates `[[ "$ITERATION" =~ ^[0-9]+$ ]]` → exit 64. Python wraps
`int(args.iteration)` in `try/except ValueError` → exit 64. Tests added.

### EC-9 — Feature name with spaces → bash word-splitting
**Fix:** All subshell expansions quoted: `feature_name="$(cat "$marker")"`. Marker
validation regex `[a-zA-Z0-9_-]+` also catches spaces before they reach path
construction. Tests added.

### EC-10 — No test planned for schema enum mismatch
**Fix:** Explicit test added to Phase 1 test plan: "mocked OpenAI returns uppercase
severity CRITICAL → retry → still invalid → write_skipped + exit 2".

---

## User requirement (post-round-1)

**"If any LLM provider doesn't work, simply ignore them and skip their feedback.
Log to a file for debugging. Specially required for expired keys, free-tier limits,
any other problems."**

**Fix:** This changes the error model globally. Previously: API failures → `status=error`
with synthetic meta CRITICAL → blocks convergence. New design:
- ALL LLM provider failure conditions → `status=skipped` + exit 2
- Log failure reason to `~/.cache/tlmforge/llm_reviewer.log` (append mode, timestamped)
- `status=error` reserved only for script-level bugs (disk full, etc.)
- Convergence engine already excludes `status=skipped` reviewers from CRITICAL counts
  (existing behavior in `check_convergence.py` — no code change needed there)

This simplifies EC-1 handling (no synthetic CRITICAL to get wrong), EC-3, EC-4 error
paths. The plan, constraints, and Phase 1 steps all updated.

---

## What was NOT fixed (deferred)

- **Architect W2** (token budget guard): deferred — silent skip on quota error already
  handles it; explicit guard is a future nicety
- **Architect W3** (`gpt-5.5` unversioned alias): noted in decisions; `TLMFORGE_OPENAI_MODEL`
  override handles it; pinning recommendation added to SKILL.md section
- **Threat-modeler MEDIUM-1** (plan size limit): same as W2 — silent skip on quota error
- **Threat-modeler LOW-1/LOW-2**: cosmetic / requires compromised orchestrator; deferred
