# check-convergence-round-aware — Master Plan

## Context

`check_convergence.py` is the mechanical convergence rule for the
tlmforge plugin's multi-agent review loop. The 0.5.0 redesign (lean review
architecture) changed the JSON artifact paths: review sidecars now live
under round-aware and stage-aware paths (`round-1-<role>.json`,
`phase-N-verification/<role>.json`, `final_audit_<role>.json`) instead of
the flat `<role>_review.json` from 0.4.0.

The script's core rule function (`evaluate_convergence`) is filename-
agnostic — it takes already-loaded dicts. The 0.5.0 changes require adding
filename-loading helpers + stage-specific orchestrators (Stage 3 round
loop, Stage 4 phase-end round loop, Stage 5 single-shot dual), and
replacing the obsolete `evaluate_stage5_two_tier` with a single-shot
`evaluate_stage5_dual`.

This work is also a **dogfood test** of the 0.5.0 SKILL.md flow itself.
Every artifact in this spec directory (this file, the phase quartets, the
agent_verification rounds, the final audit, STATUS.md) serves double duty:
documentation of the convergence-script work + proof that the redesigned
recipe works end-to-end.

## Scope

**In:**
- Add `_load_json_safely(path)` defensive loader (handles missing file,
  malformed JSON, permission errors — all collapse to `None`)
- Add `load_stage3_round_jsons(feature_dir, round_n, expected_roles)`
- Add `load_phase_end_round_jsons(feature_dir, phase_n, round_n, expected_roles)`
- Add `load_final_audit_jsons(feature_dir, expected_roles)` — calls `_load_json_safely(path, expected_iteration=1)` for each role (Stage 5 is single-shot; JSON `iteration` field is always 1 by convention). Stage 5 expected_iteration is NOT optional — `_load_json_safely` treats `None` as invalid input and raises.
- Add `evaluate_stage5_dual(red_team_json, architect_json)` — replaces
  the obsolete `evaluate_stage5_two_tier`
- Extend `evaluate_convergence` return dict with an `action` field
  (`"advance" | "retry" | "escalate"`) so callers don't have to regex
  the user_message
- **REMOVE** `evaluate_stage5_two_tier` entirely (R1-A3/T4/TH5: no
  in-tree callers per spec audit; suppressible DeprecationWarning is
  worse than cleanly absent)
- Unit tests: characterize existing behavior + cover all new helpers;
  drop the obsoleted `evaluate_stage5_two_tier` characterization tests
  in Phase 3 alongside the function removal
- Update `reviewer-convergence.md` to cite the new helpers as the canonical
  loading interface (§3 body + §4)

**Out (explicitly):**
- Marketplace publish / plugin-cache refresh (DF1 from spec audit) —
  separate operational task
- Removing the duplicate `~/.claude/skills/feature-development/check_convergence.py`
  (DF2 from spec audit) — separate cleanup
- Anthropic prompt-caching optimization for cross-round agent context —
  noted as future work in the 0.5.0 CHANGELOG
- Migrating old `<role>_review.json` files from in-flight 0.4.0 features
  to the new paths — operational, documented in 0.5.0 CHANGELOG

## Threat model / requirements / constraints

**What we're defending against** (post round-1 hardening):
- Malformed JSON files (truncated mid-write, encoding errors) → `_load_json_safely`
  catches `JSONDecodeError`, `OSError`, `UnicodeDecodeError`, `ValueError`
- A reviewer agent that writes its JSON at the wrong path (e.g., still
  using 0.4.0 conventions) — surfaces as `reviewer_json_missing`, not
  silent success
- **Gate forgery via filesystem writes** (R1-TH1): iteration cross-check
  in `_load_json_safely` rejects JSONs whose `iteration` field doesn't
  match the expected round
- **Schema-absent JSON bypass** (R1-TH2): `_validate_review_shape`
  rejects empty `{}` or missing-required-key JSONs
- **Path traversal via crafted feature_dir / role** (R1-TH3): role
  allowlist + `is_relative_to` containment
- **OOM via large JSON** (R1-TH4): 1 MB size cap before open
- Stale callers of `evaluate_stage5_two_tier`: the function is **REMOVED**
  in Phase 3 (R1-A3/T4/TH5), so `from check_convergence import
  evaluate_stage5_two_tier` raises `ImportError` — loud failure, not
  silent drift

**What we're NOT defending against:**
- Concurrent writes to the same JSON path (writers enforce atomic
  `.tmp` + `mv` per reviewer-convergence.md §6 — loader is single reader)
- Cryptographic provenance of review JSONs (HMAC signing deferred —
  iteration cross-check + role allowlist + schema validation cover the
  highest-volume forgery paths; HMAC is appropriate for higher-trust
  environments and out of scope here)
- Filesystem permission failures beyond logging — if the spec dir is
  unreadable the convergence rule has nothing to evaluate anyway

## Architecture

```
                    Caller (main Claude orchestrating SKILL.md)
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │ Stage 3: bounded 3-round loop   │
                    │                                  │
                    │  load_stage3_round_jsons(       │
                    │     feature_dir, round_n,       │
                    │     expected_roles              │
                    │  ) -> dict[role, json|None]     │
                    │                                  │
                    │  evaluate_convergence(          │
                    │     reviewer_jsons, ...         │
                    │  ) -> {converged, action, ...}  │
                    │                                  │
                    │  action: advance | retry | escalate
                    └─────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │ Stage 4 phase-end:              │
                    │  load_phase_end_round_jsons(    │
                    │     feature_dir, phase_n,       │
                    │     round_n, expected_roles     │
                    │  )                              │
                    │  evaluate_convergence(...)      │
                    └─────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────┐
                    │ Stage 5 (single shot, dual):    │
                    │  load_final_audit_jsons(        │
                    │     feature_dir,                │
                    │     [red-team, architect]       │
                    │  )                              │
                    │  evaluate_stage5_dual(          │
                    │     red_team_json,              │
                    │     architect_json              │
                    │  ) -> {final_converged,         │
                    │        action, ...}             │
                    │                                  │
                    │  action: ship | escalate        │
                    └─────────────────────────────────┘

                    Pre-existing (unchanged):
                    - evaluate_convergence(reviewer_jsons, expected_roles, ...)
                      Core rule. Returns updated dict including new `action` key.
                    - _synthetic_meta_critical(...) — unchanged
                    - _build_synthetic_review(...) — unchanged

                    REMOVED (per round-1 review):
                    - evaluate_stage5_two_tier(...) — DELETED in Phase 3.
                      No in-tree callers; suppressible DeprecationWarning
                      was worse than cleanly absent. Loud failure
                      (ImportError) replaces silent drift.
```

**Path conventions (single source of truth — must match reviewer-convergence.md §0):**

| Stage | Round | Path pattern |
|---|---|---|
| 3 | 1 | `<feature_dir>/agent_verification/round-1-<role>.json` |
| 3 | 2 | `<feature_dir>/agent_verification/round-2-<role>.json` |
| 3 | 3 | `<feature_dir>/agent_verification/round-3-<role>.json` |
| 4 phase-end | 1 | `<feature_dir>/phase-<N>-verification/<role>.json` |
| 4 phase-end | 2 | `<feature_dir>/phase-<N>-verification/round-2-<role>.json` |
| 4 phase-end | 3 | `<feature_dir>/phase-<N>-verification/round-3-<role>.json` |
| 5 | single | `<feature_dir>/agent_verification/final_audit_<role>.json` |

## Sensitive surface inventory

| Surface | Touched? | Notes |
|---|---|---|
| `check_convergence.py` public API | YES | Add functions; extend return dict |
| `check_convergence.py` private helpers | YES | New `_load_json_safely` |
| `reviewer-convergence.md` | YES | Cite new helpers; document paths |
| `review_schema.json` | NO | Schema unchanged |
| `ai_review_json.sh` | NO | Gemini wrapper unchanged |
| `SKILL.md` | NO | Already documents the new paths (0.5.0 rewrite) |
| Existing callers in tlmforge | NONE | No in-tree callers grep'd for `evaluate_stage5_two_tier` |
| Tests | NEW DIR | `tlmforge/skills/feature-development/tests/test_check_convergence.py` |

## Phases

### Phase 0 — Characterization tests (pin existing behavior before changing anything)

**Goal:** Write unit tests that cover ALL existing branches of
`evaluate_convergence` and `evaluate_stage5_two_tier`. This is the safety
net so Phase 1+'s additions can't silently regress current behavior.

**Test layers:** unit only. No integration (the function takes dicts, no I/O).

**Files modified:**
- `tlmforge/skills/feature-development/tests/__init__.py` (new, empty)
- `tlmforge/skills/feature-development/tests/test_check_convergence.py` (new)

**Tests to add:**
- `test_evaluate_convergence_all_approve` — 3 reviewers, all `verdict=approve`, no findings → `converged=True`
- `test_evaluate_convergence_missing_json` — one reviewer absent → synthetic meta CRITICAL → `converged=False`
- `test_evaluate_convergence_real_critical` — one reviewer has real CRITICAL → `converged=False`, count=1
- `test_evaluate_convergence_meta_critical` — one synthetic meta CRITICAL only → `converged=False`, message names the wiring concern
- `test_evaluate_convergence_lazy_empty_blocking_verdict` — reviewer emits `verdict=needs_revision` with empty findings → synthetic `reviewer_verdict_findings_mismatch`
- `test_evaluate_convergence_lazy_empty_approve_verdict` — reviewer emits `verdict=approve` with empty findings → warning but converges
- `test_evaluate_convergence_skipped_reviewer` — reviewer with `status=skipped` excluded from count
- `test_evaluate_convergence_cap_hit_real_only` — iteration > max, real CRITICALs → cap_hit message
- `test_evaluate_convergence_cap_hit_meta_only` — iteration > max, only meta CRITICALs → wiring-broken message
- `test_evaluate_convergence_cap_hit_both` — iteration > max, both → "fix real first, then re-launch"
- `test_cap_hit_iteration_eq_max_in_evaluate_convergence` — **boundary pin (R1-A1/T2)**: iteration=3, max=3 → cap_hit=False (`>` semantic)
- `test_cap_hit_iteration_eq_max_in_two_tier` — **boundary pin (R1-A1/T2)**: iteration=3, max=3 → cap_hit=True (`>=` semantic). Two pins capture the existing asymmetry; Phase 3 resolves it.
- `test_evaluate_stage5_two_tier_tier1_not_converged` — tier-1 has CRITICAL → tier-2 not processed
- `test_evaluate_stage5_two_tier_tier1_converged_no_tier2` — tier-1 OK, tier-2 absent → `awaiting_tier2=True`
- `test_evaluate_stage5_two_tier_tier2_skipped` — red-team status=skipped → `tier2_skipped=True`
- `test_evaluate_stage5_two_tier_both_converged` — tier-1 OK, tier-2 OK → `final_converged=True`
- `test_evaluate_stage5_two_tier_tier2_critical_below_cap` — restart message includes remaining iterations
- `test_evaluate_stage5_two_tier_tier2_critical_at_cap` — `requires_user_override=True`

**Verification criteria (R1-A5 fix):**
- [ ] All ~17 tests pass on initial run against unmodified `check_convergence.py` (characterization tests are GREEN by definition — they pin current behavior)
- [ ] Each test has a docstring stating which branch / behavior it pins, so a future change that breaks the test produces a meaningful failure message
- [ ] `python3 -m pytest tlmforge/skills/feature-development/tests/ -v` exits 0
- [ ] Test file has no skipped tests, no `xfail`, no `pytest.skip` calls

**Rollback:**
| Action | Time | Data risk |
|---|---|---|
| `git revert HEAD` — phase commit removes tests/ dir | 1 min | None |

### Phase 1 — `_load_json_safely` (hardened) + `_validate_review_shape` + extend `evaluate_convergence` with `action` field

**Goal:** Add the defensive JSON loader with security hardening. Extend the
existing function's return shape with `action`. Phase 1 grew from a pure
refactor into a full security-hardening pass per round-1 review (TH1, TH2,
TH3, TH4 + T1, T5). Total Phase 1 LOC: ~50 → ~120.

**Defenses landing in this phase (each maps to a round-1 finding):**

1. **R1-T1 — UnicodeDecodeError catch:** `_load_json_safely` catches
   `(json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError)`.
2. **R1-TH4 — file-size guard:** Before opening, `os.path.getsize(path)
   > 1_048_576` → return None (1 MB threshold — reviewer JSONs are
   never legitimately larger than ~100 KB).
3. **R1-TH3 — role allowlist + path containment:**
   - Validate role string against `{"architect-reviewer", "tester",
     "threat-modeler", "code-reviewer", "phase-auditor", "ux-reviewer",
     "red-team-reviewer"}`. Unknown role → return None.
   - After path construction, assert `path.resolve().is_relative_to(
     Path(feature_dir).resolve())`. Escape → return None.
4. **R1-TH2 — `_validate_review_shape`:** New private helper. After
   `json.load`, verify required keys (`reviewer`, `schema_version`,
   `iteration`, `verdict`, `findings`) are present. Missing keys →
   return None.
5. **R1-TH1 — iteration cross-check:** The loaders pass `expected_iteration`
   to `_load_json_safely`. After shape validation, assert the loaded
   `iteration` field matches `expected_iteration`. Mismatch → return None
   (treated as `reviewer_json_missing`).
6. **R1-T5 — iteration boundary check:** `evaluate_convergence` raises
   `ValueError("iteration must be >= 1")` at entry if `iteration < 1`.

**`action` enum (R1-F5 from spec audit + R1-A4 verification):**

| Stage | Possible values |
|---|---|
| Stage 3 / Stage 4 phase-end (iterative) | `"advance"` (converged) \| `"retry"` (not converged, iteration < max) \| `"escalate"` (cap_hit, not converged) |
| Stage 5 (single-shot — added in Phase 3) | `"ship"` (converged) \| `"escalate"` (any CRITICAL) |

The `action` value is computed in `evaluate_convergence` based on
`converged` + `cap_hit`. Stage 5 (Phase 3) uses a different value
mapping via its own logic.

**Files modified:**
- `tlmforge/skills/feature-development/check_convergence.py`
- `tlmforge/skills/feature-development/tests/test_check_convergence.py`

**Tests to add (≈15):**
- `test_load_json_safely_missing_file` — returns None
- `test_load_json_safely_malformed_json` — returns None
- `test_load_json_safely_permission_denied` — returns None
- `test_load_json_safely_valid_json` — returns parsed dict
- `test_load_json_safely_non_utf8` — file starting `b'\xff\xfe'` → None (R1-T1)
- `test_load_json_safely_too_large` — 2 MB file → None (R1-TH4)
- `test_load_json_safely_empty_dict` — file contains `{}` → None (R1-TH2)
- `test_load_json_safely_missing_required_key` — JSON without `verdict` → None (R1-TH2)
- `test_load_json_safely_unknown_role` — role="../etc" → None (R1-TH3)
- `test_load_json_safely_path_traversal_feature_dir` — feature_dir="../../etc" → None (R1-TH3)
- `test_load_json_safely_iteration_mismatch` — JSON says iteration=2 but loader called with expected_iteration=1 → None (R1-TH1)
- `test_iteration_zero_raises_value_error` — `evaluate_convergence(iteration=0)` raises (R1-T5)
- `test_evaluate_convergence_action_advance` — converged case → `action="advance"`
- `test_evaluate_convergence_action_retry` — not converged, iteration < max → `action="retry"`
- `test_evaluate_convergence_action_escalate` — not converged, cap hit → `action="escalate"`

**Verification criteria:**
- [ ] All Phase 0 tests still pass (no regressions on existing behavior)
- [ ] All new tests pass
- [ ] `evaluate_convergence` return dict has new `action` key in every branch
- [ ] `_validate_review_shape` rejects ≥4 distinct malformed shapes
- [ ] Path containment + role allowlist BOTH cover the path-traversal surface (two independent defenses)
- [ ] No silent fallback — every malformed/missing/forged file returns `None`

**Rollback:**
| Action | Time | Data risk |
|---|---|---|
| `git revert HEAD` | 1 min | None — pure additions; reverting leaves Phase 0 tests in place |

### Phase 2 — Stage-specific loaders (Stage 3, Stage 4 phase-end, Stage 5)

**Goal:** Add `load_stage3_round_jsons`, `load_phase_end_round_jsons`,
`load_final_audit_jsons`. Each is a thin function that:
1. Constructs the per-role expected paths from the path patterns table
2. Calls `_load_json_safely` per role
3. Returns the dict `{role: json|None}` that `evaluate_convergence` already
   accepts

**Files modified:**
- `tlmforge/skills/feature-development/check_convergence.py`
- `tlmforge/skills/feature-development/tests/test_check_convergence.py`

**Tests to add:**
- `test_load_stage3_round_jsons_all_present` — round 1 with 3 files written → all 3 dicts loaded
- `test_load_stage3_round_jsons_missing_one` — round 2 with only architect file → `{architect: dict, tester: None, threat-modeler: None}`
- `test_load_stage3_round_jsons_round_3` — verifies path uses `round-3-` prefix
- `test_load_phase_end_round_jsons_round_1` — uses bare `<role>.json` path (round 1 in phase-N-verification/)
- `test_load_phase_end_round_jsons_round_2` — uses `round-2-<role>.json`
- `test_load_phase_end_round_jsons_ux_skipped` — ux-reviewer not in expected_roles → not in returned dict
- `test_load_final_audit_jsons_both_present` — red-team + architect files → 2-entry dict
- `test_load_final_audit_jsons_one_missing` — only red-team → `{red-team: dict, architect: None}`
- `test_load_final_audit_jsons_ignores_carryover` — `tester_edge_cases.json` present in dir is NOT loaded by this function (F6 from spec audit)

**Verification criteria:**
- [ ] Phase 0 + Phase 1 tests still pass
- [ ] New tests pass
- [ ] Tester fixtures use `tmp_path` (pytest fixture) — no test pollutes the real `specs/` directory

**Rollback:**
| Action | Time | Data risk |
|---|---|---|
| `git revert HEAD` | 1 min | None |

### Phase 3 — `evaluate_stage5_dual` + REMOVE `evaluate_stage5_two_tier`

**Goal:** Replace the obsolete two-tier convergence with the 0.5.0
single-shot dual model. **REMOVE the old function entirely** — no shim,
no DeprecationWarning. Round-1 review found the shim silently discards
CRITICALs and DeprecationWarning is suppressible (R1-A3/T4/TH5). Spec
audit confirmed zero in-tree callers; safe to remove.

**`evaluate_stage5_dual` return shape (R1-A4 fix — pinned spec):**

Internally delegates to:
```python
evaluate_convergence(
    reviewer_jsons={"red-team-reviewer": red_team_json, "architect-reviewer": architect_json},
    expected_roles=["red-team-reviewer", "architect-reviewer"],
    iteration=1,
    max_iterations=1,
)
```

At `iteration=1, max=1`:
- Zero CRITICALs → `converged=True`. Map to `action="ship"`.
- Any CRITICAL → `cap_hit=True` (since iteration==max and not converged). Map to `action="escalate"`.

Stage 5 has no `"retry"` semantic. The `evaluate_convergence` core
returns `"escalate"` for cap_hit cases; `evaluate_stage5_dual` wraps the
result and additionally promotes `"advance"` to `"ship"` (since Stage 5
is terminal — converged means ship the feature, not advance to a next
round).

**Return dict (concrete):**
```python
{
    "final_converged": bool,            # True iff both agents approve and no CRITICALs
    "real_critical_count": int,         # from underlying evaluate_convergence
    "meta_critical_count": int,
    "action": "ship" | "escalate",
    "findings_by_role": {...},          # same as evaluate_convergence
    "user_message": str,                # tuned for Stage 5 (mentions FINAL_ESCALATION.md if cap_hit)
}
```

**Files modified:**
- `tlmforge/skills/feature-development/check_convergence.py` — add
  `evaluate_stage5_dual`; **delete** `evaluate_stage5_two_tier`
- `tlmforge/skills/feature-development/tests/test_check_convergence.py`
  — add new tests; **delete** the 6 Phase 0 characterization tests for
  the removed function (single commit)
- `tlmforge/skills/feature-development/reviewer-convergence.md` —
  rewrite §3 body + §4 (per R1-A2). §3 currently cites old flat-path
  reviewer JSON; replace with round-aware path examples. §0 + §4
  already updated in the 0.5.0 rewrite.

**Tests to add (≈6 — was 8 before removal cleanup):**
- `test_evaluate_stage5_dual_both_approve` → `final_converged=True`, `action="ship"`
- `test_evaluate_stage5_dual_red_team_critical` → `final_converged=False`, `action="escalate"`
- `test_evaluate_stage5_dual_architect_critical` — symmetric
- `test_evaluate_stage5_dual_both_critical` — both have CRITICALs
- `test_evaluate_stage5_dual_red_team_missing` — `red_team_json=None` → synthetic meta CRITICAL → escalate
- `test_evaluate_stage5_two_tier_removed` — `from check_convergence import evaluate_stage5_two_tier` raises `ImportError` (pin the removal)

**Verification criteria:**
- [ ] All Phase 0 + Phase 1 + Phase 2 tests still pass (Phase 0's 6 `evaluate_stage5_two_tier` tests are now deleted — count drops by 6)
- [ ] New tests pass
- [ ] `grep -n "evaluate_stage5_two_tier" check_convergence.py` returns 0 (function gone)
- [ ] `grep -n "evaluate_stage5_two_tier" tests/test_check_convergence.py` returns 0 except for the removal test
- [ ] `reviewer-convergence.md` §3 body cites `round-1-<role>.json` / `final_audit_<role>.json` (NOT `<role>_review.json` flat path)
- [ ] `grep -E "tier-1.*trio\|tier-2" reviewer-convergence.md` returns 0 matches in normative sections (R1-A2)
- [ ] `iteration=3, max=3` is NOT cap_hit (resolves R1-A1/T2 asymmetry; `>` semantic survives)

**Rollback:**
| Action | Time | Data risk |
|---|---|---|
| `git revert HEAD` | 1 min | None (no external callers to break) |

### Phase 4 — Integration test against real spec-dir fixture

**Goal:** Run the loaders against a realistic on-disk fixture mimicking
the 0.5.0 artifact layout. This is the Stage 6 live verification proxy:
proves the full path-loader→evaluate pipeline works end-to-end without
mocks.

**Files modified:**
- `tlmforge/skills/feature-development/tests/test_check_convergence.py` —
  add integration test class

**Tests to add:**
- `test_integration_stage3_round_1_converged` — write 3 reviewer JSONs (all `verdict=approve`, empty findings) to a `tmp_path`-based `specs/test-feature/agent_verification/round-1-*.json` layout; load via `load_stage3_round_jsons`; evaluate; assert `action="advance"`
- `test_integration_stage3_round_2_with_carryover_retry` — round-1 files + `tester_edge_cases.json` + `round-1-fixes.md` present; load round-2 files (none yet) at `iteration=2, max_iterations=3` → all 3 missing → 3 synthetic meta CRITICALs → `action="retry"` (cap not hit)
- `test_integration_stage3_round_2_with_carryover_escalate` — `iteration=4, max_iterations=3` → all 3 missing → `cap_hit=True` (because 4>3) → `action="escalate"`. Under the `>` semantic adopted in Phase 3, the cap fires AT iteration>max. iteration=3 is at-cap-boundary (no escalate); iteration=4 is past-cap (escalate). This is the canonical escalate-fixture pair tied to the round-1 cap-asymmetry resolution.
- `test_integration_phase_end_with_ui` — write code-reviewer/tester/phase-auditor/ux-reviewer JSONs to `phase-1-verification/`; load with `expected_roles=[code-reviewer, tester, phase-auditor, ux-reviewer]`; evaluate; assert converged
- `test_integration_phase_end_without_ui` — same but only 3 files (no ux); `expected_roles` excludes ux; assert converged (NOT a missing-file error)
- `test_integration_stage5_final_audit_ship` — write red-team + architect final-audit JSONs (both approve); evaluate; `action="ship"`

**Verification criteria:**
- [ ] All previous tests still pass
- [ ] Integration tests pass
- [ ] `phase-4-evidence.md` contains the actual pytest output (per-layer counts, elapsed) — this is the no-regression evidence

**Rollback:**
| Action | Time | Data risk |
|---|---|---|
| `git revert HEAD` | 1 min | None |

## Risk audit

(severity-tagged, carried forward from spec_audit + anything new)

| Risk | Severity | Mitigation |
|---|---|---|
| F1: No existing tests → unknown regressions when changing | CRITICAL | Phase 0 pins behavior BEFORE Phase 1+ touches code |
| F2: Plugin cache on 0.3.0 → user-facing flow still old | HIGH | OUT OF SCOPE — flagged in STATUS.md; separate marketplace-publish task |
| F3: `evaluate_stage5_two_tier` obsolete | HIGH | Phase 3 — REMOVE function entirely. No shim (round-1 R1-A3/T4/TH5: shim silently discards CRITICALs + suppressible warning). |
| F4: Malformed JSON crashes loader | HIGH | `_load_json_safely` catches `json.JSONDecodeError` + `OSError` |
| F5: Caller has to regex user_message to decide action | HIGH | Phase 1 adds `action` field to return dict |
| F6: tester_edge_cases.json (carryover) could be confused with a review | MEDIUM | Loaders glob explicit `round-*-<role>.json` patterns; integration test pins behavior |
| F7: Phase-end paths nested under `phase-N-verification/`, not `agent_verification/` | MEDIUM | Distinct helper per stage |
| F8: Conditional reviewers (ux at Stage 3/4) — caller responsibility | MEDIUM | Documented; integration test covers both cases |
| F9: In-flight 0.4.0 features have old `<role>_review.json` paths | LOW | Operational — documented in 0.5.0 CHANGELOG; no code change |
| DF1: Plugin cache hasn't refreshed to 0.5.0 | HIGH | OUT OF SCOPE — flagged in STATUS.md |
| DF2: Duplicate `~/.claude/skills/feature-development/check_convergence.py` | LOW | OUT OF SCOPE — clarify mirror behavior separately |

## Decisions made

- **`action` field uses bounded enum** (`advance | retry | escalate | ship`)
  — not free-text — so callers can switch on it without parsing.
- **Stage 5 dual function returns same shape conventions as the iterative
  ones** (`final_converged`, `user_message`, etc.) — minimizes caller
  divergence between Stage 3/4 and Stage 5.
- **`load_*_jsons` helpers do NOT inject synthetic missing-file findings.**
  They return `None` for absent files. The synthetic injection lives in
  `evaluate_convergence` where it already does, preserving single
  responsibility. Otherwise loaders would have to know about the
  convergence schema.
- **`evaluate_stage5_two_tier` is REMOVED, not deprecated** (R1
  decision). Spec audit confirmed zero in-tree callers, so no
  back-compat shim is needed. A suppressible DeprecationWarning would
  be worse than a clean removal: callers that suppress warnings would
  silently get the old (incorrect) tier-1+tier-2 semantics. `ImportError`
  on import is a loud failure mode that surfaces the migration need.
- **Tests live in `tlmforge/skills/feature-development/tests/`** — colocated
  with the script, not in a separate top-level `tests/` directory. The
  plugin distribution bundles them so users can run the test suite
  locally to verify their install. (Pytest discovers via convention.)

## Cost analysis

- **Implementation cost:** entirely token-cost on this session — no API
  calls beyond Claude itself. Phase 0 ~150 LOC of tests; Phase 1 ~50 LOC
  code + ~80 LOC tests; Phase 2 ~80 LOC code + ~120 LOC tests; Phase 3
  ~70 LOC code + ~80 LOC tests; Phase 4 ~150 LOC of integration tests.
  Total: ~200 LOC code, ~580 LOC tests.
- **Runtime cost (when used in production):** zero — pure Python with file
  I/O. The script's effect is to REDUCE multi-agent review costs by
  enforcing convergence caps. Net cost impact for users: large reduction.
- **Operational cost:** zero — no infra, no API keys, no external services.

## Open questions for the user

(None — explicitly resolved within the plan per "no clarifying questions"
directive.)

## TDD plan

Test layers identified:
- **Unit** — every function in `check_convergence.py` (Phase 0, 1, 2, 3
  tests are all unit). The function signatures take dicts; no I/O at this
  layer.
- **Integration** — Phase 4 tests use real `tmp_path` + real files
  exercising the full pipeline (write JSONs → load via helpers → evaluate
  via core rule).
- **E2E** — N/A. There's no user-facing flow here — the script is internal
  tooling. Live verification (Stage 6) IS the integration tests against
  realistic fixtures.

| Phase | Test files | What they verify | Expected RED → GREEN |
|---|---|---|---|
| 0 | `tests/test_check_convergence.py` | Characterizes existing behavior of `evaluate_convergence` + `evaluate_stage5_two_tier` | All RED against `_load_json_safely`-using rewrite would fail; against original, all GREEN |
| 1 | (extends above) | `_load_json_safely` defensive paths; `action` field added | RED before impl; GREEN after |
| 2 | (extends above) | Stage 3/4/5 path loaders; correct path patterns | RED before impl |
| 3 | (extends above) | `evaluate_stage5_dual` single-shot semantics; removal of `evaluate_stage5_two_tier` (ImportError test) | RED before impl |
| 4 | (extends above) | End-to-end integration: real files on disk through full pipeline | RED before impl |

Sub-phases (5b, 5c, etc.) are NOT pre-allocated. They get added LATER if a
post-rollout review surfaces gaps.

## Verification criteria (becomes phase-N-verify.md targets)

The feature is "done" when:

1. `python3 -m pytest tlmforge/skills/feature-development/tests/ -v` exits 0
2. Test count >= 45 (Phase 0: ~17, Phase 1: ~15, Phase 2: ~9, Phase 3: ~6, Phase 4: ~5 — post round-1 expansion; total ~52)
3. Coverage of `check_convergence.py` >= 95% (measured via `pytest --cov`)
4. `evaluate_convergence` return dict includes `action` in every branch
5. `evaluate_stage5_two_tier` does NOT exist — `from check_convergence import evaluate_stage5_two_tier` raises `ImportError` (function removed in Phase 3 per round-1 fixes)
6. `evaluate_stage5_dual` exists and is documented in `reviewer-convergence.md`
7. `reviewer-convergence.md` §0 and §4 cite the new helpers
8. Integration test demonstrates: write JSONs at the new paths → load via
   helpers → `evaluate_convergence` returns `action="advance"` when all
   converge, `action="escalate"` at iteration 4
9. No regressions in pre-existing tests (zero; the project had none, so
   this is trivially satisfied — but Phase 0's characterization tests
   become the pre-existing baseline for Phase 1+)
