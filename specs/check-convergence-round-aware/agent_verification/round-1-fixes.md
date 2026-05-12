# Round-1 fixes — main Claude's response to Stage 3 R1 findings

Main Claude has read all three round-1 review files (architect, tester,
threat-modeler) plus the JSON sidecars. Below: per-finding response with
the specific change made to README.md (master plan) to address it.

## CRITICAL — addressed in plan

### A1/T2: `>` vs `>=` cap-check inconsistency
- **Finding:** `evaluate_convergence` uses `iteration > max_iterations`
  (line 135). `evaluate_stage5_two_tier` uses `iteration >= max_iterations`
  (line 364). At `iteration=3, max=3`, the two disagree on whether the
  cap is hit.
- **Fix in plan:**
  - Phase 0 adds two boundary tests: `test_cap_hit_iteration_eq_max`
    (asserts current `evaluate_convergence` says NOT cap_hit at
    iteration=3, max=3) and `test_two_tier_iteration_eq_max` (asserts
    current `evaluate_stage5_two_tier` DOES say cap_hit at same point).
    These tests pin the existing buggy asymmetry.
  - Phase 3 (which removes `evaluate_stage5_two_tier`, see A3 below)
    transparently resolves the asymmetry: only one rule survives, and
    it's the `>` rule from `evaluate_convergence`. Phase 3 verification
    criterion: "iteration=3, max=3 is NOT cap_hit; cap fires at
    iteration=4."

### T1: `_load_json_safely` misses `UnicodeDecodeError`
- **Finding:** `UnicodeDecodeError` is a `ValueError` subclass but NOT
  a `JSONDecodeError`. A file with non-UTF-8 bytes raises uncaught.
- **Fix in plan:**
  - Phase 1 `_load_json_safely` catches `(json.JSONDecodeError, OSError,
    UnicodeDecodeError, ValueError)` — broadened to cover the
    `UnicodeDecodeError` and any related decode failure.
  - Phase 1 test `test_load_json_safely_non_utf8` writes a file
    starting with `b'\xff\xfe garbage'` and asserts `None` is returned.

### TH1: Gate forgery — no provenance check
- **Finding:** Any process with write access to `agent_verification/`
  can manufacture convergence with fake approve+empty JSONs.
- **Fix in plan:** Phase 1 `_load_json_safely` (or a new
  `_validate_review_shape` wrapper) cross-checks the `iteration` field
  in the loaded JSON against the `round_n` argument the loader was
  called with. Mismatch → return `None` (treated as missing →
  synthetic meta CRITICAL). This is the minimum-viable defense; HMAC
  signing is OUT OF SCOPE (operational complexity not justified for
  the threat surface).

## HIGH — addressed in plan

### A2: reviewer-convergence.md §3 body still 0.4.0
- **Finding:** Plan updates §0 and §4 but leaves §3's body
  (Convergence rule walkthrough, line 175 area) citing the old
  `<role>_review.json` paths and the old "Stage 5 tier-1 default:
  architect-reviewer + code-reviewer + tester" trio.
- **Fix in plan:** Phase 3 expanded — now updates §0, §3 body, AND §4.
  Phase 3 verification criterion adds: "grep 'flat-path\\|tier-1+tier-2'
  reviewer-convergence.md → 0 matches in normative sections."

### A3 / T4 / TH5: Deprecation shim → just REMOVE the function
- **Finding:** The shim silently discards non-architect tier-1
  CRITICALs (architect: H1, tester: H2). DeprecationWarning is
  suppressible (threat-modeler: TH5). No in-tree callers (spec audit
  confirmed via grep).
- **Fix in plan:** Phase 3 REMOVES `evaluate_stage5_two_tier` entirely
  instead of deprecating. No shim, no DeprecationWarning, no behavioral
  ambiguity. Three implications updated in plan:
  1. Phase 0's characterization tests for `evaluate_stage5_two_tier`
     stay — they pin current behavior. After Phase 3 removes the
     function, those tests are DELETED (single-commit per Phase 3:
     remove function + delete its now-obsolete tests).
  2. Plan's "Decisions made" updated: "Remove, don't deprecate.
     Cleaner, no suppressible warning."
  3. Spec_audit.md F3 (back-compat) and F9 (in-flight 0.4.0 callers)
     no longer apply at the code level — operational migration only.

### A4 / T3: evaluate_stage5_dual return shape underspecified
- **Finding:** Plan said "returns same shape conventions" but didn't
  pin it. Without explicit shape, `action="retry"` could be returned
  when `action="escalate"` is correct (Stage 5 has no iteration).
- **Fix in plan:** Phase 3 explicitly defines `evaluate_stage5_dual`:
  - Internally delegates to `evaluate_convergence(reviewer_jsons={...},
    expected_roles=[red-team-reviewer, architect-reviewer], iteration=1,
    max_iterations=1)`. This is the "single shot, no iteration"
    semantic — at iteration=1 with max=1, any CRITICAL → cap_hit →
    action="escalate". Zero CRITICAL → converged → action="ship"
    (overrides "advance" since Stage 5 is terminal).
  - Return dict adds `action: "ship" | "escalate"` (Stage 5 has its
    own enum subset — "retry" and "advance" don't apply at Stage 5).

### T5: iteration=0 produces schema-invalid output
- **Finding:** `_build_synthetic_review` accepts iteration=0 and emits
  it. Schema requires `iteration >= 1`.
- **Fix in plan:** Phase 1 adds `if iteration < 1: raise ValueError`
  guard at the top of `evaluate_convergence`. Phase 1 test:
  `test_iteration_zero_raises_value_error`.

### TH2: Schema-absent JSON ({}) bypasses convergence
- **Finding:** Empty dict per role → defaults to verdict=approve,
  findings=[] → converged=True.
- **Fix in plan:** Phase 1 adds `_validate_review_shape(data)` that
  checks for required top-level keys (`reviewer`, `schema_version`,
  `iteration`, `verdict`, `findings`). Called from `_load_json_safely`
  AFTER `json.load` succeeds. Missing keys → return None.
- Test: `test_load_json_safely_empty_dict` — file contains `{}` →
  loader returns `None`.

### TH3: Path traversal via unsanitized feature_dir / role
- **Finding:** Crafted `feature_dir="../etc"` or role string with
  separators escapes the spec dir.
- **Fix in plan:** Phase 1 `_load_json_safely` does:
  1. Validate `role` against the known reviewer set
     (`{architect-reviewer, tester, threat-modeler, code-reviewer,
     phase-auditor, ux-reviewer, red-team-reviewer}`). Unknown role →
     return None.
  2. After constructing the path, assert
     `path.resolve().is_relative_to(Path(feature_dir).resolve())`.
     Escape → return None.
- Test: `test_load_json_safely_path_traversal_role` — role like
  `"../../etc/passwd"` → None.

## MEDIUM — addressed in plan

### A5: Phase 0 TDD wording (characterization tests can't be RED)
- **Finding:** Plan's Phase 0 verification said "Tests RED before
  existing code is touched (sanity check that they actually test
  something)." But characterization tests against UNCHANGED code are
  GREEN by definition — they pin current behavior.
- **Fix in plan:** Phase 0 verification criterion rewritten: "Tests
  pass on initial run (characterizing current behavior — GREEN by
  definition). Each test must include a docstring stating which
  branch / behavior it pins, so a future change that breaks the test
  produces a meaningful failure message."

### TH4: No file-size guard
- **Finding:** `json.load` on a 100 MB file → OOM.
- **Fix in plan:** Phase 1 `_load_json_safely` checks
  `os.path.getsize(path)` first; >1 MB → return None.
- Test: `test_load_json_safely_too_large` — 2 MB file → None.

## Scope decisions in this round

- **Plan was a pure refactor; round-1 expanded it into a security
  hardening.** Five new defenses (UTF-8 decode catch, iteration cross-
  check, schema-key validation, path containment, file-size guard) all
  land in Phase 1's `_load_json_safely` rewrite. This grows Phase 1
  from ~50 LOC to ~120 LOC. Still small.
- **`evaluate_stage5_two_tier` REMOVED, not deprecated.** Per
  threat-modeler TH5 — suppressible warnings hide drift. The
  characterization tests for it (Phase 0) get deleted alongside the
  function in Phase 3.
- **`_validate_review_shape` is a new private helper** — Phase 1 adds
  it. Both `_load_json_safely` and (defensively) `evaluate_convergence`
  call it. Two places means two test surfaces.
- **HMAC signing of review JSONs is OUT OF SCOPE.** Defers to operational
  decisions (session-key storage, rotation, etc.). The iteration cross-
  check closes the highest-volume forgery path (wrong-round artifacts);
  HMAC is appropriate for higher-trust environments.

## Updated phase counts

- Phase 0: ~15 → ~17 tests (added two `>` vs `>=` boundary pins per A1/T2)
- Phase 1: ~7 → ~15 tests (added defensive checks per T1, TH1, TH2, TH3, TH4, T5)
- Phase 2: ~9 tests (unchanged)
- Phase 3: ~8 → ~6 tests (removed shim → fewer shim-related tests; added
  removal-verification test; added §3-body grep test)
- Phase 4: ~5 tests (unchanged)
- **Total: ~52 tests** (was ~44).

All other plan elements (architecture, threat model, scope-in/out,
rollback) stand.

## Open items deferred to Round 2

None — all CRITICAL and HIGH findings have a concrete plan response above.
Round 2 reviewers will verify each fix maps onto the updated README.md.
