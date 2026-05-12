# Stage 3 Round 1 — Tester Review
# check-convergence-round-aware

## Summary verdict

`needs_revision` — 2 CRITICAL, 3 HIGH, 2 MEDIUM identified. Several edge
cases in the design either produce silent failure or crash in ways the plan
doesn't fully account for. Phase 0's characterization-test list is solid;
the gaps are in Phase 1–3 design specifics.

---

## CRITICAL findings

### C1. `_load_json_safely` non-UTF-8 bytes: `json.load` raises `UnicodeDecodeError`, NOT `JSONDecodeError`

**Surface:** Phase 1, `_load_json_safely` in `check_convergence.py`

**Trigger:** A reviewer agent writes a JSON file and the OS or network
filesystem introduces non-UTF-8 bytes (e.g., a BOM, a null byte, or a
partial multibyte sequence from a truncated write). Python's `json.load`
first calls `fp.read()`, which raises `UnicodeDecodeError` (a subclass of
`ValueError`, NOT of `json.JSONDecodeError`) before the JSON parser even
runs.

**What the plan says:** The plan says catch `JSONDecodeError` and `OSError`.
`UnicodeDecodeError` is neither. It will propagate uncaught, crash the
convergence loop, and produce a Python traceback instead of a synthetic
`reviewer_json_missing`.

**What the test must verify:** Write a tmpfile with `b'\xff\xfe invalid'`
bytes, open it in text mode with default encoding, call `_load_json_safely`,
assert the return value is `None` — NOT an exception.

**Fix:** Catch `(json.JSONDecodeError, OSError, UnicodeDecodeError)` or
catch the broader `(json.JSONDecodeError, OSError, ValueError)` since
`UnicodeDecodeError` is a `ValueError` subclass. The latter is cleaner
because it also catches numeric-string overflow in the JSON parser.

---

### C2. `cap_hit` semantics: `iteration > max_iterations` means cap is already EXCEEDED — iteration=3/max=3 never triggers cap

**Surface:** Phase 0 characterization tests, then Phase 1 `action` field

**Trigger:** The existing code computes `cap_hit = iteration > max_iterations`.
With `max_iterations=3`, the cap is NOT triggered at `iteration=3` — only at
`iteration=4`. This means:
- `iteration=3` → `cap_hit=False`, `converged=False` (if criticals present)
  → the `action` field would be `"retry"` not `"escalate"`
- `iteration=4` → `cap_hit=True` → `action="escalate"`

The plan's Phase 0 characterization test `test_evaluate_convergence_cap_hit_real_only`
passes `iteration > max_iterations` without specifying the exact input values.
If the test writes `iteration=3, max=3`, it will FAIL to trigger cap_hit and
the test will produce a false GREEN.

Furthermore, `evaluate_stage5_two_tier` uses `iteration >= max_iterations`
(line 364) for cap detection in tier-2, but the outer function uses
`iteration > max_iterations` (line 135). This asymmetry is a pre-existing
bug that Phase 0 characterization tests must PIN, and Phase 3's shim must
decide which semantics to preserve.

**What the test must verify:**
- `evaluate_convergence(jsons, roles, iteration=3, max_iterations=3)` with
  real CRITICALs → `cap_hit=False` (this is the CURRENT behavior; test must
  pin it, not silently fix it)
- `evaluate_convergence(jsons, roles, iteration=4, max_iterations=3)` with
  real CRITICALs → `cap_hit=True`
- Separate test pinning the `evaluate_stage5_two_tier` uses `>=` at line 364

**Fix in plan:** The Phase 0 test descriptions must specify exact `iteration`
and `max_iterations` values, not just describe the intent. The Phase 1 `action`
field logic must explicitly state which threshold defines cap — and document
the `>` vs `>=` discrepancy so Phase 3 resolves it intentionally.

---

## HIGH findings

### H1. `evaluate_stage5_dual` semantics for missing JSON: `None` argument is not the same as `missing key` in `reviewer_jsons`

**Surface:** Phase 3, `evaluate_stage5_dual`

**Trigger:** The plan says `evaluate_stage5_dual(red_team_json, architect_json)`
takes two positional arguments. When one is `None` (missing file), it must
produce the same synthetic `reviewer_json_missing` behavior that
`evaluate_convergence` produces for `None`-valued dict entries. But
`evaluate_stage5_dual` is a NEW function — it can't just call
`evaluate_convergence({"red-team": red_team_json, "architect": architect_json}, ...)`
without also passing `expected_roles` AND an `iteration` value.

What should `iteration` be for a single-shot function? The plan doesn't say.
If the implementation passes `iteration=1, max_iterations=1`, then
`cap_hit = (1 > 1) = False`, which is correct — a single-shot never caps.
But if the implementation defaults `iteration=1, max_iterations=3` and a
reviewer has CRITICAL, it returns `action="retry"` instead of `action="escalate"`.
Stage 5 is NOT supposed to retry — it's a final gate.

**What the test must verify:**
- `evaluate_stage5_dual(None, valid_architect_json)` → `final_converged=False`,
  `action="escalate"` (not "retry")
- `evaluate_stage5_dual(valid_red_team_json, valid_architect_json_with_critical)`
  → `final_converged=False`, `action="escalate"` (not "retry", since Stage 5
  has no retry concept)

**Fix:** `evaluate_stage5_dual` must pass `max_iterations=1` internally
(single-shot has no retry budget), OR handle the action translation itself:
map any non-converged result to `"escalate"` regardless of the underlying
`evaluate_convergence` action output.

---

### H2. `evaluate_stage5_two_tier` deprecation shim must NOT silently suppress real CRITICALs from tier-1

**Surface:** Phase 3, deprecation wrapper for `evaluate_stage5_two_tier`

**Trigger:** The plan says the wrapper delegates to `evaluate_stage5_dual`
by "collapsing tier-1 trio to architect-reviewer + tier-2 to red-team."
But `evaluate_stage5_two_tier` receives a full `tier1_jsons` dict (multiple
roles). If the shim just picks one role from `tier1_jsons` (say the
`architect-reviewer` key) and discards the others, any CRITICAL findings in
the discarded tier-1 roles are silently dropped. The deprecated caller would
get `final_converged=True` when the original function would have returned
`final_converged=False`.

The plan notes this is "imperfect but back-compatible enough for the no-op
grace period." That's insufficient — silent suppression of real CRITICALs
in a security-gating function is not "imperfect," it's incorrect.

**What the test must verify:**
- `evaluate_stage5_two_tier({"code-reviewer": {critical_finding}, "architect-reviewer": clean_json}, None, 1)`
  → `tier1_converged=False` (the code-reviewer CRITICAL must not be dropped)
- The plan's own test `test_evaluate_stage5_two_tier_delegates_to_dual` must
  assert this explicitly, not just assert the same `final_converged` for a
  trivial case where both inputs are clean.

**Fix:** The shim must aggregate all tier-1 findings (e.g., by calling
`evaluate_convergence` on the full `tier1_jsons` dict first, then passing
the merged result to `evaluate_stage5_dual`), OR it must refuse to collapse
and instead just call the NEW function path directly. The "collapse to one
role" approach is not safe.

---

### H3. `iteration=0` passed to `evaluate_convergence` is schema-invalid but not defensively rejected

**Surface:** Phase 1, `evaluate_convergence` and `_load_json_safely`

**Trigger:** The JSON schema (`review_schema.json`) has `"minimum": 1` on
the `iteration` field, meaning iteration is 1-indexed. But `evaluate_convergence`
does not validate its own `iteration` argument. If a caller passes
`iteration=0`:
- `cap_hit = (0 > 3) = False` — correct-ish
- `user_message` says "Convergence reached at iteration 0 of 3" — confusing
- The synthetic review dict produced by `_build_synthetic_review` would
  write `"iteration": 0` into a dict that purports to follow the schema,
  then that dict would fail schema validation if ever re-validated

The plan adds an `action` field but doesn't specify behavior for
`iteration=0` or `iteration` being non-integer (e.g., a string "1" from
JSON deserialization that wasn't explicitly cast).

**What the test must verify:**
- `evaluate_convergence({}, [], iteration=0)` → either raises `ValueError`
  with a clear message, or is documented to return `action="advance"` with
  a warning. Either is acceptable but must be explicit and tested.
- `evaluate_convergence({}, [], iteration="1")` (string, not int) → test
  documents the current crash behavior so it's pinned.

---

## MEDIUM findings

### M1. Phase 4 integration test `test_integration_stage3_round_2_with_carryover` has a broken assertion

**Surface:** Phase 4, integration test description

**Trigger:** The test description says: load round-2 files (which don't exist
yet) → all 3 missing → 3 synthetic meta CRITICALs → `action="retry"` (or
`escalate` if iteration counter says cap). The parenthetical "or escalate"
is ambiguous — the test can't assert two different actions with an "or."

The correct answer: `iteration=2, max_iterations=3` → `cap_hit = (2 > 3) = False`
→ `action="retry"`. At `iteration=4` it would be `escalate`. The test must
commit to ONE set of inputs and ONE expected output.

If the test uses `iteration=2` it will assert `action="retry"`. But this
test is also supposed to verify the carryover file (`tester_edge_cases.json`)
is NOT loaded — and that assertion is orthogonal to the action. The test
should be split: one test for carryover exclusion (using round-1 context,
asserting 3 roles loaded and carryover not present in dict), and one test
for cap behavior (using iteration=4, asserting `action="escalate"`).

**What the test must verify:** The test plan must be split into deterministic
single-assertion tests, not "or" conditionals.

---

### M2. Role names with hyphens in path construction: `round-1-code-reviewer.json` is ambiguous to a glob splitter

**Surface:** Phase 2, `load_stage3_round_jsons` path construction

**Trigger:** The path pattern is `round-{N}-{role}.json`. If a role name
contains a hyphen (e.g., `code-reviewer`, `red-team`), the resulting filename
`round-1-code-reviewer.json` has THREE hyphen-delimited segments. If anyone
tries to PARSE the filename back into `(round, role)` by splitting on `-`
and taking `parts[1]` as the round number and `parts[2:]` as the role, they
get `code` + `reviewer` instead of `code-reviewer`.

The loaders are not supposed to parse filenames — they construct paths from
known inputs — so this isn't a runtime bug in the loader itself. However,
the test suite should prove that the loaders work correctly WITH hyphenated
role names, since all three canonical roles (`code-reviewer`, `red-team`,
`phase-auditor`) contain hyphens. If a future loader refactor uses filename
parsing, the tests will catch the regression.

**What the test must verify:**
- All Phase 2 loader tests must use the real role names (`code-reviewer`,
  `red-team`, `architect`) — not synthetic single-word names — to exercise
  the actual path construction with embedded hyphens.

---

## Edge cases the plan handles correctly

- F4 (malformed JSON): `_load_json_safely` catches `JSONDecodeError` + `OSError`.
  Good. The gap is only `UnicodeDecodeError` (C1 above).
- F6 (carryover artifact not loaded): glob pattern `round-{N}-{role}.json`
  excludes `tester_edge_cases.json` by construction. The integration test
  confirms it. Good.
- F7 (distinct helpers per stage): two separate helpers for Stage 3 vs
  Stage 4. Good.
- F8 (conditional ux-reviewer): caller passes explicit `expected_roles`.
  Good.
- Lazy-empty `verdict=approve` + empty findings: DOES NOT trigger blocking
  synthetic. Logs a warning. This is intentional and correct.
- `status=skipped` exclusion from CRITICAL counting: correct in current code,
  Phase 0 tests pin it.
- `tmp_path` for integration tests: plan explicitly calls this out. No real
  spec-dir pollution.

---

## Tests missing from the plan

1. **`test_load_json_safely_non_utf8_bytes`** — tmpfile with `b'\xff\xfe'`,
   assert returns `None` not exception. Add to Phase 1.

2. **`test_evaluate_convergence_cap_hit_exact_boundary`** — `iteration=3,
   max=3` with real CRITICALs → `cap_hit=False`. Pins the `>` semantics.
   Add to Phase 0.

3. **`test_evaluate_stage5_two_tier_cap_asymmetry`** — calls
   `evaluate_stage5_two_tier` with `iteration=3, max=3`, tier-1 converged,
   tier-2 has CRITICAL. Asserts that `requires_user_override=True` (because
   tier-2 uses `>=`). This pins the asymmetric cap semantics as intentional
   before they are altered in Phase 3.

4. **`test_evaluate_stage5_dual_no_retry_on_critical`** — CRITICAL in one
   agent → `action="escalate"` (not "retry"). Proves Stage 5 has no retry
   path. Add to Phase 3.

5. **`test_evaluate_stage5_two_tier_shim_preserves_tier1_criticals`** —
   tier-1 dict has a role with CRITICAL; the shim must NOT collapse it away.
   Add to Phase 3.

6. **`test_evaluate_convergence_iteration_zero`** — documents behavior for
   `iteration=0`. Add to Phase 1.

7. **`test_integration_stage3_round_2_all_missing_retry`** (deterministic
   split from the ambiguous Phase 4 test) — `iteration=2, max=3`, all round-2
   files absent → `action="retry"`.

8. **`test_integration_stage3_round_4_all_missing_escalate`** (second split)
   — `iteration=4, max=3`, all files absent → `action="escalate"`.
