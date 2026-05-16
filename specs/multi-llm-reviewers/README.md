# multi-llm-reviewers — Master Plan (rev after Round 1)

## Context

The tlmforge feature-development skill currently runs only Claude subagents as reviewers.
Adding OpenAI (`gpt-5.5`, confirmed real model resolving to `gpt-5.5-2026-04-23`) and
Gemini as optional auxiliary reviewers at Stage 3 (plan review), Stage 4 (code review),
and Stage 5 (final audit) gives multi-model diversity.

Users control which LLMs participate via env vars. Claude is always on. OpenAI and
Gemini are opt-in: **both** the enable flag AND the key must be set.

Success: setting `TLMFORGE_ENABLE_OPENAI=1` + `OPENAI_API_KEY` causes the `"openai"`
reviewer to join every review round with structured JSON findings that flow through the
existing convergence engine without any changes to `check_convergence.py`.

## Scope

**In:**
- `ai_review_json_openai.py` — Python script: calls OpenAI Responses API, emits
  `review_schema.json`-compliant JSON, exits 2 gracefully when key/flag absent
- `ai_review_openai.sh` — thin shell wrapper with same exit-code contract as
  `ai_review_json.sh`
- Config: `TLMFORGE_ENABLE_OPENAI`, `TLMFORGE_ENABLE_GEMINI`,
  `TLMFORGE_OPENAI_MODEL` (default `gpt-5.5`) env vars
- SKILL.md: "Auxiliary LLM Reviewers" section with conditional `expected_roles`
  template and `reviewer` field → role name contract
- `~/.claude/settings.json`: add `Bash(ai_review_openai.sh:*)` (NOT a blanket
  `OPENAI_API_KEY=:*` entry — see security constraints)
- Tests for the Python script and shell wrapper

**Out:**
- No changes to `check_convergence.py`
- No changes to `review_schema.json`
- No changes to existing Claude subagent prompts or hooks
- No changes to the TLM server

## Threat model / constraints

- **No `Bash(OPENAI_API_KEY=:*)` permission entry.** That pattern auto-approves any
  command prefixed with that string, including injected `OPENAI_API_KEY=x rm -rf ~`.
  Use `Bash(ai_review_openai.sh:*)` instead — approves only the specific script.
- **Active-feature marker must be validated before path construction.** Regex:
  `re.fullmatch(r'[a-zA-Z0-9_-]+', feature_name)`. Reject anything with `/`, `..`,
  spaces, or special characters — exit 2 with `status=skipped`. Prevents path
  traversal exfiltration of arbitrary local files to `api.openai.com`.
- **All JSON output via `json.dumps()`, never string interpolation.** Error messages
  from OpenAI can contain quotes, newlines, and Unicode. Interpolation breaks the
  JSON boundary; `json.dumps` is safe by construction.
- **Atomic writes:** `tempfile.NamedTemporaryFile(dir=output_dir, delete=False)` +
  `os.replace(tmp, output)`. `os.replace` is POSIX-atomic on same filesystem.
  Never `shutil.move` (not atomic cross-filesystem).
- **`reviewer` field hardcoded to `"openai"`.** Must match the key used in
  `expected_roles` in SKILL.md orchestration. Never derived from `TLMFORGE_OPENAI_MODEL`.
- **OpenAI Responses API, not Chat Completions.** `gpt-5.5` requires
  `client.responses.create()`. Chat Completions is in maintenance mode for this
  model family and has worse cache utilization.
- `set -euo pipefail` in shell scripts; never `set -x`.
- **CRITICAL: All LLM provider failures must silently skip — NEVER block convergence.**
  This includes: expired key, free-tier quota exhausted, model not found, connection
  timeout, malformed response, truncated response, schema validation failure, any
  `openai.APIError`. ALL error conditions write `status=skipped` and exit 2. The
  convergence engine then excludes the reviewer as if the key was never set.
  Log the failure reason to `~/.cache/tlmforge/llm_reviewer.log` for user debugging.
  The user must be able to run the full feature-development skill with a broken or
  free-tier LLM key without any workflow interruption.

## Architecture

```
User enables:
  TLMFORGE_ENABLE_OPENAI=1
  OPENAI_API_KEY=<fetched from gcloud secrets>
  TLMFORGE_OPENAI_MODEL=gpt-5.5         (optional; default gpt-5.5)
  TLMFORGE_ENABLE_GEMINI=1              (optional)
  GEMINI_API_KEY=<fetched from gcloud>  (optional)

Stage 3 plan review (parallel in SKILL.md orchestration)
  ┌────────────────────────────────────────────────────────────────┐
  │  Agent(architect-reviewer) → round-1-architect-reviewer.json  │
  │  Agent(tester)             → round-1-tester.json              │
  │  Agent(threat-modeler)     → round-1-threat-modeler.json      │
  │  Bash(ai_review_openai.sh --mode plan --output round-1-openai.json) │ ← new
  │  Bash(ai_review_json.sh   --mode plan --output round-1-gemini.json) │ ← extended
  └────────────────────────────────────────────────────────────────┘
         ↓
  SKILL.md builds expected_roles conditionally:
    base = ["architect-reviewer", "tester", "threat-modeler"]
    if TLMFORGE_ENABLE_OPENAI=1 and OPENAI_API_KEY set: append "openai"
    if TLMFORGE_ENABLE_GEMINI=1 and GEMINI_API_KEY set:  append "gemini"
  check_convergence.py(reviewer_jsons={...}, expected_roles=[...])

Stage 4 phase-end (parallel) — same conditional roster pattern
Stage 5 final audit (parallel) — same conditional roster pattern

Script exit-code contract (BOTH scripts must follow):
  0  → JSON sidecar written (status=ok); status=error reserved for script-level bugs only (disk full, etc.)
  2  → graceful skip: flag unset, key absent, SDK missing, validation failed,
       empty diff in mode=code, invalid marker; JSON written: status=skipped
 64  → usage error: missing --output, missing --iteration, non-integer --iteration,
       output parent directory does not exist

Python JSON output construction rule: ALL output via json.dumps(). Zero string
interpolation for fields that contain external data.

Atomic write sequence:
  tmp = tempfile.NamedTemporaryFile(dir=output_dir, suffix='.tmp', delete=False)
  tmp.write(json.dumps(result).encode())
  tmp.close()
  os.replace(tmp.name, output_path)
```

## Sensitive surface inventory

- `OPENAI_API_KEY` — env only; never logged, never written to disk
- `GEMINI_API_KEY` — env only (existing constraint, extended to Stage 3/4)
- `ai_review_json_openai.py` — outbound HTTPS to `api.openai.com`; sends code diffs
  and plan content (acknowledged risk: diffs may contain sensitive data)
- `ai_review_openai.sh` — thin wrapper; inherits env; `set -euo pipefail`, no `set -x`
- `.tlmforge_active_feature` — validated with `[a-zA-Z0-9_-]+` before use in path
- `--output` path — parent directory existence checked before write; no traversal check
  needed (script writes to where called from, not user-supplied arbitrary paths)

## Phases

### Phase 0 — Config layer + shell wrapper scaffold
**Goal:** Establish the env-var config surface and exit-code contract before any API
integration. All test scenarios runnable without a live key.

**Steps:**
1. Create `skills/feature-development/ai_review_openai.sh`:
   - Flags: `--output PATH --iteration N [--mode plan|code]` (default: `code`)
   - Pre-flights: check `TLMFORGE_ENABLE_OPENAI` set, `OPENAI_API_KEY` non-empty,
     output parent directory exists; exit 2 or 64 as appropriate with sidecar written
   - Validate `ITERATION` is integer (`[[ "$ITERATION" =~ ^[0-9]+$ ]]`), exit 64 if not
   - Calls: `python3 "$(dirname "$0")/ai_review_json_openai.py" --output "$OUTPUT" --iteration "$ITERATION" --mode "$MODE"`
   - Passes Python exit codes through unchanged
2. Create `skills/feature-development/ai_review_json_openai.py` (stub):
   - Parses `--output`, `--iteration` (validated as integer), `--mode` (default `code`)
   - Pre-flights: `TLMFORGE_ENABLE_OPENAI`, `OPENAI_API_KEY`, `import openai` check
   - Stub: always writes `status=skipped` JSON and exits 2 (real API call in Phase 1)
   - `REVIEWER_NAME = "openai"` constant
   - All JSON via `json.dumps()`, atomic write via tempfile + `os.replace()`
3. Add `"Bash(ai_review_openai.sh:*)"` to `~/.claude/settings.json` permissions

**Files modified:**
- `skills/feature-development/ai_review_openai.sh` (new)
- `skills/feature-development/ai_review_json_openai.py` (new, stub)
- `~/.claude/settings.json` (one permission entry)

**Tests added:** `skills/feature-development/tests/test_openai_wrapper.py`
- exit 2 + skipped JSON when `TLMFORGE_ENABLE_OPENAI` unset
- exit 2 + skipped JSON when `OPENAI_API_KEY` unset (flag set)
- exit 2 + skipped JSON when `openai` SDK not importable (monkeypatched)
- exit 64 when `--output` missing
- exit 64 when `--iteration` missing
- exit 64 when `--iteration` is non-integer ("abc")
- exit 64 when output parent directory does not exist
- skipped JSON has `reviewer="openai"`, validates against `review_schema.json`
- atomic write: output file is valid JSON even if checked mid-write (verified via
  concurrent read during write simulation)

**Rollback:** Delete the two new files; remove the `Bash(ai_review_openai.sh:*)` settings entry.

---

### Phase 1 — OpenAI Responses API integration
**Goal:** Replace stub with a real `gpt-5.5` call using the Responses API, producing
schema-compliant JSON with all edge cases handled.

**Steps:**
1. Implement `ai_review_json_openai.py`:

   **Pre-flight (exit 2 + skipped JSON):**
   - `TLMFORGE_ENABLE_OPENAI` unset → skipped
   - `OPENAI_API_KEY` absent → skipped
   - `import openai` fails → skipped
   - `mode=code` + empty `git diff HEAD` → skipped (no empty-diff reviews)
   - `mode=plan`: read marker, apply `.strip()`, then validate with `re.fullmatch(r'[a-zA-Z0-9_-]+', feature)`;
     if invalid, absent, or empty → skipped; if README missing → skipped

   **API call via Responses API:**
   ```python
   client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
   response = client.responses.create(
       model=os.environ.get("TLMFORGE_OPENAI_MODEL", "gpt-5.5"),
       input=[
           {"role": "system", "content": SYSTEM_PROMPT},
           {"role": "user",   "content": diff_or_plan_text},
       ],
   )
   raw = response.output_text
   ```

   **Truncation check:** if response indicates incomplete output, treat as invalid,
   trigger retry.

   **Retry once on invalid JSON or schema enum mismatch.**

   **Enum validation before accept:** check `severity` in `{"critical","high","medium",
   "low","nit"}` and `category` in the schema enum. On mismatch → retry.

   **ALL failure paths write `status=skipped` and exit 2 (NEVER `status=error` or
   synthetic meta CRITICAL).** This includes API auth failure, quota exceeded, model not
   found, connection error, both retries producing invalid/truncated JSON, enum mismatch
   after retry. Log the reason to `~/.cache/tlmforge/llm_reviewer.log`.
   The `status=error` path is reserved for implementation bugs (e.g., disk full on
   atomic write) — not for LLM provider unavailability.

   **`REVIEWER_NAME = "openai"` — always this string in the output JSON.**

   **Skipped sidecar minimum fields:** `reviewer`, `schema_version`, `iteration`,
   `status="skipped"`. Findings array must be present but may be empty `[]`.
   `review_schema.json` already enumerates `"skipped"` in the status enum (confirmed).
   No schema changes needed.

2. System prompt (mirrors Gemini prompt from `ai_review_json.sh` line 81):
   ```
   Review the provided content against the feature-development discipline.
   Output ONLY a JSON object. Lowercase severity. Category from enum:
   security, auth, null_safety, bug, logic_error, race_condition, data_loss,
   missing_error_handling, test_coverage, tdd_violation, architecture,
   backwards_compat, performance, observability, documentation, style, meta.
   suggested_fix REQUIRED if severity=critical.
   Top-level fields: reviewer ("openai"), schema_version ("1.0"),
   iteration (<N>), status ("ok"), verdict
   (approve|approve_with_warnings|needs_revision|do_not_ship), findings (array).
   Output JSON only, no prose.
   ```

**Files modified:**
- `skills/feature-development/ai_review_json_openai.py` (implement)
- `skills/feature-development/ai_review_openai.sh` (pass `--mode` through)

**Tests added** (extend `test_openai_wrapper.py`):
- `mode=code` mocked diff → valid schema JSON, `reviewer="openai"`, exit 0
- `mode=plan` mocked README → valid schema JSON, exit 0
- `mode=code` empty diff → exit 2, status=skipped, OpenAI not called
- First call invalid JSON → retry → second valid → exit 0, status=ok
- First call uppercase severity ("CRITICAL") → retry → second valid → exit 0
- Both calls invalid JSON → status=skipped, exit 2, failure logged to `~/.cache/tlmforge/llm_reviewer.log`
- Auth error (mocked) → status=skipped, exit 2, failure logged
- Truncated response → retry → still truncated → status=skipped, exit 2, failure logged
- `mode=plan` + absent marker → exit 2, status=skipped
- `mode=plan` + marker with path traversal ("../foo") → exit 2, status=skipped
- `mode=plan` + marker with spaces ("my feature") → Python strips and validates, exit 2 (invalid chars)
- `reviewer` field in all output paths is exactly `"openai"`
- All output JSON validates against `review_schema.json`
- All critical findings in `status=ok` output have `suggested_fix` (string, len >= 8); `status=skipped` output has empty findings array

**Rollback:** Revert `ai_review_json_openai.py` to Phase 0 stub.

---

### Phase 2 — Extend Gemini script to Stage 3 plan mode
**Goal:** Add `--mode plan` to `ai_review_json.sh` with the same safety constraints
as the Python script.

**Steps:**
1. Add `--mode` flag (default `code`) to `ai_review_json.sh`
2. When `mode=plan`:
   - Check marker exists and is non-empty (`[[ ! -f "$marker" ]] || [[ -z "$(cat "$marker")" ]]`)
   - Validate feature name: `[[ ! "$feature" =~ ^[a-zA-Z0-9_-]+$ ]]` → exit 2 skipped
   - Quote the expansion: `feature_name="$(cat "$marker")"` and `"specs/${feature_name}/README.md"`
   - If README missing → exit 2 skipped
   - Pipe README content to gemini instead of `git diff HEAD`
3. When `mode=code`: if `git diff HEAD` is empty, write_skipped + exit 2 (mirrors Python)
4. Validate `ITERATION` is integer: `[[ ! "$ITERATION" =~ ^[0-9]+$ ]]` → exit 64
5. Check output parent directory exists before write → exit 64 if not

**Files modified:**
- `skills/feature-development/ai_review_json.sh`

**Tests added:** extend `skills/feature-development/tests/test_ai_review_json.sh`
- `--mode plan` with `GEMINI_API_KEY_ABSENT=1` → exit 2, skipped JSON
- `--mode plan` + absent marker → exit 2, skipped (not decoy `specs/README.md`)
- `--mode plan` + marker with path traversal → exit 2, skipped
- `--mode plan` + marker with spaces → exit 2, skipped (invalid chars)
- `--mode code` + empty diff → exit 2, skipped
- `--mode code` (existing) → all existing tests still pass
- Non-integer `--iteration` → exit 64
- Missing output parent directory → exit 64

**Rollback:** Revert `ai_review_json.sh` changes.

---

### Phase 3 — SKILL.md orchestration documentation
**Goal:** Document conditional roster construction and reviewer field contract so any
engineer can wire the new reviewers correctly.

**Steps:**
Add "Auxiliary LLM Reviewers" section to SKILL.md covering:

1. **Config table:**
   | Env var | Purpose | Default |
   |---|---|---|
   | `TLMFORGE_ENABLE_OPENAI` | Enable OpenAI reviewer | off |
   | `TLMFORGE_ENABLE_GEMINI` | Enable Gemini reviewer | off |
   | `TLMFORGE_OPENAI_MODEL` | OpenAI model name | `gpt-5.5` |

2. **Conditional `expected_roles` construction template:**
   ```python
   expected_roles = ["architect-reviewer", "tester", "threat-modeler"]
   if os.environ.get("TLMFORGE_ENABLE_OPENAI") == "1" and os.environ.get("OPENAI_API_KEY"):
       expected_roles.append("openai")
   if os.environ.get("TLMFORGE_ENABLE_GEMINI") == "1" and os.environ.get("GEMINI_API_KEY"):
       expected_roles.append("gemini")
   ```

3. **Reviewer field contract:** the `reviewer` field in `round-1-openai.json` must
   be `"openai"` (not the model name). The `reviewer` field in `round-1-gemini.json`
   must be `"gemini"`. These strings must match the keys in `expected_roles` exactly.

4. **Where to launch:** Stage 3 parallel block, Stage 4 phase-end, Stage 5 final audit.

5. **Skipped reviewer handling:** if a reviewer writes `status=skipped`, convergence
   excludes it from CRITICAL counts. The SKILL.md orchestrator should NOT add it to
   `expected_roles` if the flag isn't set — but if it is added and the script exits 2
   writing a skipped sidecar, that's also clean.

**Files modified:** `skills/feature-development/SKILL.md`

**Tests:** None (documentation-only); phase-auditor verifies content at phase-end.

**Rollback:** Revert SKILL.md section.

---

## Risk audit

| Severity | Risk | Mitigation |
|---|---|---|
| HIGH | `git diff HEAD` and plan README content sent to `api.openai.com` — may include accidentally staged `.env` files, secrets in test fixtures, or NDA-sensitive architecture | Accepted risk — opt-in only; documented here. Future: pre-flight secret scan before send. |
| HIGH | `gpt-5.5` model ID may require exact versioned form in some API calls | `TLMFORGE_OPENAI_MODEL` env override; model-not-found → `status=skipped + exit 2 + logged` (per silent-skip constraint) |
| MEDIUM | OpenAI key exposed in this conversation's context | User accepted risk; key not committed to git |
| LOW | TOCTOU between key presence check and API call | API call wrapped in global `openai.APIError` handler; TOCTOU failure → `status=skipped + exit 2`, same as pre-flight |

## Decisions made

- **OpenAI Responses API, not Chat Completions**: architect-reviewer confirmed Chat
  Completions is in maintenance mode for `gpt-5.5`; Responses API is required.
- **`Bash(ai_review_openai.sh:*)` permission, not `Bash(OPENAI_API_KEY=:*)`**: threat-modeler
  confirmed the blanket key-prefix permission is a command-execution surface.
- **`reviewer="openai"` hardcoded**: architect-reviewer confirmed that deriving the
  reviewer name from the model name causes `expected_roles` key mismatch in convergence.
- **Marker validation regex `[a-zA-Z0-9_-]+`**: prevents path traversal exfiltration.
- **`json.dumps()` for all output**: prevents JSON boundary breakage on error messages
  containing quotes (threat-modeler HIGH-2).
- **Empty diff → exit 2 skipped**: prevents false approvals at Stage 3 (tester EC-2).
- **Enum validation before accepting response**: prevents silent false convergence on
  uppercase severity values (tester EC-4).
- **`os.replace()` atomic write**: prevents false `reviewer_json_missing` CRITICALs
  from interrupted writes (architect-reviewer C3).

## Cost analysis

- `gpt-5.5`: ~$5/1M input, ~$30/1M output (GUESS — architect confirmed pricing direction
  but exact values may differ; the model is `gpt-5.5-2026-04-23`)
- Typical review (20K input, 2K output): ~$0.16 per call (GUESS)
- Full Deep feature (~12 review calls): ~$1.92 (GUESS)
- No circuit breaker needed beyond existing `max_iterations=3` cap

## Open questions for the user

None — all decisions resolved.

## TDD plan

| Phase | Test file | Key scenarios | RED state |
|---|---|---|---|
| 0 | `tests/test_openai_wrapper.py` | Exit-code contract, missing args, skipped JSON validity, atomic write | Stub always skips → real-call tests RED |
| 1 | `tests/test_openai_wrapper.py` (extended) | All EC-1..EC-7 + API error paths + enum validation | All RED until full Python impl |
| 2 | `tests/test_ai_review_json.sh` (extended) | Plan mode, absent marker, path traversal, empty diff | RED until `--mode` added |
| 3 | — | Documentation only | n/a |

## Verification criteria

1. `TLMFORGE_ENABLE_OPENAI=1 OPENAI_API_KEY=fake ./ai_review_openai.sh --output /tmp/t.json --iteration 1 --mode code` exits 2, JSON has `status=skipped`, `reviewer="openai"`
1b. With a valid mocked OpenAI response: exits 0, JSON has `status=ok`, `reviewer="openai"`, validates against `review_schema.json`
2. Without `TLMFORGE_ENABLE_OPENAI`, same command exits 2, JSON has `status=skipped`
3. `GEMINI_API_KEY_ABSENT=1 ./ai_review_json.sh --output /tmp/g.json --iteration 1 --mode plan` exits 2, JSON has `status=skipped`
4. `echo '../etc/passwd' > specs/.tlmforge_active_feature && ./ai_review_openai.sh --output /tmp/t.json --iteration 1 --mode plan` exits 2, status=skipped (path traversal blocked)
5. All pre-existing 23 tests: `python3 -m pytest skills/feature-development/tests/ -v` exits 0
6. New tests: `python3 -m pytest skills/feature-development/tests/test_openai_wrapper.py -v` exits 0
