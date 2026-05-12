# Stage 5 Final Audit — red-team-reviewer

**Feature:** check-convergence-round-aware
**Reviewer:** red-team-reviewer (single-shot, Stage 5)
**Diff scope:** `git diff edfa9f4..HEAD` (3 commits: pre-impl spec, Phase 0 tests, Phase 0 verify)
**Verdict:** `do_not_ship` (for the post-Phase-0 *state*, not for the Phase 0 *increment*)

---

## TL;DR

The Phase 0 increment that landed is a clean characterization-tests-only
addition with **no production code changes**. The 321-line test file is
not itself exploitable. **However**, the spec explicitly defers the
security hardenings (R1-TH1/2/3/4) to Phases 1–4, and Phases 1–4 have
NOT shipped. The threat-modeler's CRITICAL gate-forgery finding and two
HIGH findings (schema-absent bypass, path traversal) are STILL OPEN in
`check_convergence.py` at HEAD.

The Phase 0 tests in fact *pin the exploitable behavior as expected*
(see test_evaluate_convergence_lazy_empty_approve_verdict and
test_evaluate_convergence_all_approve). This is fine as a
characterization step (Phase 1 is supposed to *change* this behavior),
but it means anyone who consumes the repo at this commit and starts
using `check_convergence.py` as a convergence gate is exposed.

Empirical confirmation (run against tlmforge/skills/feature-development/check_convergence.py at HEAD):

```
FORGED 3-reviewer approve+empty → CONVERGES: True       (gate forgery)
EMPTY {} dicts per reviewer    → CONVERGES: True       (schema-absent bypass)
iteration: 99 mismatch         → CONVERGES: True       (no iteration cross-check)
ALL-SKIPPED reviewers           → CONVERGES: True       (gate passes with zero reviews performed)
```

All four attacks pass. None of the defenses in the spec's "what we're
defending against" section actually exist in shipped code yet.

---

## Findings

### CRITICAL — Convergence gate is forgeable by anyone with write access to `specs/<feature>/agent_verification/`

**Status of fix in this diff:** NOT SHIPPED. Mitigation deferred to
Phases 1–2 (`_load_json_safely` defensive loader + iteration
cross-check + schema validation + path containment + role allowlist).

**File:** `tlmforge/skills/feature-development/check_convergence.py` line 100–119

**Attack chain (input → exploit → impact):**

1. An attacker (or a prompt-injected reviewer agent, or a stale test
   fixture, or any process with write access to the spec directory)
   writes three trivial JSONs:
   ```json
   {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []}
   {"reviewer": "tester",             "status": "ok", "verdict": "approve", "findings": []}
   {"reviewer": "threat-modeler",     "status": "ok", "verdict": "approve", "findings": []}
   ```
2. Per the planned `load_stage3_round_jsons` (and any current ad-hoc
   loader that simply `json.load`s the round files), these three dicts
   reach `evaluate_convergence`.
3. The lazy-empty branch at line 113–117 of `check_convergence.py`
   converts each `verdict=approve, findings=[]` into a *warning*, not a
   block. `real_critical_count == 0 == meta_critical_count`, `cap_hit
   == False`, so `converged=True`.
4. The orchestrator advances to the next stage / ships the feature
   without any real review having occurred.

**Impact:** Bypass of the multi-agent review gate. Any code change can
ship with zero genuine adversarial scrutiny. This defeats the entire
purpose of the Stage 3 / Stage 5 review loops.

**Why CRITICAL:** the attack chain has no preconditions beyond
"writable spec directory". The Phase 0 characterization tests
explicitly pin this exact behavior at
`test_evaluate_convergence_lazy_empty_approve_verdict` (line 144)
and `test_evaluate_convergence_all_approve` (line 35) as the *expected*
post-conditions. Anyone reading the tests sees the forge path as
documented behavior.

**Suggested fix (per the master plan, defer no further than Phase 1):**

- Add `_load_json_safely` with required-key shape validation
  (`reviewer`, `schema_version`, `iteration`, `verdict`, `findings`).
- Add iteration cross-check: loader passes `expected_iteration`;
  mismatch → return `None` (collapses to synthetic
  `reviewer_json_missing` meta CRITICAL).
- Add role allowlist + path containment in the per-stage loaders.
- *Stronger* defense the plan does NOT require but threat-modeler
  named in round 1: HMAC-sign the JSONs with a per-session key, so
  arbitrary filesystem writes cannot forge them. Plan explicitly
  defers HMAC; that's defensible *only if* Phases 1–4 ship and HMAC
  is reserved for higher-trust environments.

### HIGH — Empty `{}` JSON bypasses convergence silently

**Status of fix in this diff:** NOT SHIPPED. Mitigation deferred to
Phase 1 (`_validate_review_shape`).

**File:** `tlmforge/skills/feature-development/check_convergence.py` line 100–119

**Attack:**
- A reviewer agent that crashes and emits `{}` (or any process that
  writes `{}` to the expected path) yields a dict that, in the
  current code, has `.get("status", OK) == OK`,
  `.get("verdict", "approve") == "approve"`, `.get("findings", []) ==
  []`. The reviewer is silently counted as "approved with no
  findings."
- Empirically confirmed: feeding `{"architect-reviewer": {}, "tester":
  {}, "threat-modeler": {}}` to `evaluate_convergence` returns
  `converged=True`.

**Why HIGH not CRITICAL:** requires a write-access foothold or an
agent that emits literally `{}`, which is less likely than the
deliberate-forgery scenario above.

**Fix:** `_validate_review_shape` per Phase 1, R1-TH2.

### HIGH — Iteration cross-check absent; stale-round JSONs are accepted

**Status of fix in this diff:** NOT SHIPPED. Mitigation deferred to
Phase 1 (loaders pass `expected_iteration` to `_load_json_safely`).

**File:** `tlmforge/skills/feature-development/check_convergence.py` (whole file — there's no iteration check anywhere on the consumed JSON)

**Attack:**
- An attacker copies a converged round-1 JSON from a *different
  feature* (or the same feature's earlier round) into the current
  round's path. The JSON's internal `iteration` field is `1`, but
  the loader is fetching round 3. The current source never compares
  the two — round-3 just trusts the round-1 dict.
- Empirically confirmed: a JSON with `"iteration": 99` passed to
  `evaluate_convergence(..., iteration=1)` converges normally.

**Why HIGH:** requires a write foothold *and* an existing approve
JSON to copy, but both are realistic in CI / shared-dev-machine
attacker models.

**Fix:** Phase 1 R1-TH1 — `_load_json_safely(path,
expected_iteration)` rejects mismatch as `reviewer_json_missing`.

### HIGH — Path traversal in feature_dir / role names

**Status of fix in this diff:** NOT SHIPPED. Mitigation deferred to
Phase 1 (role allowlist + `is_relative_to` containment).

**File:** N/A in current shipped code (no loaders exist yet), but the
*planned* loaders (`load_stage3_round_jsons`,
`load_phase_end_round_jsons`, `load_final_audit_jsons`) splice
user-controlled `feature_dir` and role strings into filesystem paths.

**Attack:**
- A prompt-injected orchestrator passes `feature_dir="../../etc"` or
  `role="../../etc/passwd"`. Without containment, the loader reads
  whatever JSON-shaped file it can find — could include
  attacker-staged content on disk.
- The plan addresses this; today's code has no loaders to attack —
  but as soon as Phase 2 lands without the Phase 1 hardening, this
  surface opens.

**Why HIGH not CRITICAL:** today there are no loaders, so the
surface is purely future. Calling this out NOW per the "medium-when-
risk-depends-on-future-code" calibration.

**Fix:** Phase 1 R1-TH3 — role allowlist + `path.resolve().is_relative_to(
Path(feature_dir).resolve())`.

### MEDIUM — All-skipped reviewer set converges with zero real review

**Status of fix in this diff:** Behavior is PINNED AS CORRECT by
test_evaluate_convergence_skipped_reviewer (test 2 in the test file)
in a 1-of-2 case. Empirically, 3-of-3 all-skipped also converges —
no test pins this and the plan does not call it out.

**File:** `tlmforge/skills/feature-development/check_convergence.py` line 93–97

**Attack:**
- If every reviewer reports `status=skipped` (e.g., all three agents
  fail to launch for transient infra reasons), the code emits three
  warnings and converges with `real_critical_count = meta_critical_count = 0`.
- A malicious orchestrator that wants to bypass review can force
  every reviewer into `skipped` (kill the API key, exceed rate
  limit, etc.) and the gate opens.

**Why MEDIUM not HIGH:** requires denial-of-service on the reviewer
agents, which the same attacker would also have to weaponize.
Likeliest in CI when Gemini is offline AND the trio agents 500.

**Fix:** require at least one *non-skipped* reviewer with a non-empty
findings list OR an `approve` verdict with positive findings count.
Not currently in the master plan. Recommend adding to Phase 1
verification criteria or a Phase 5b.

### MEDIUM — `sys.path` injection in the test file is a footgun for parallel test runs

**Status:** SHIPPED in this diff.

**File:** `tlmforge/skills/feature-development/tests/test_check_convergence.py` line 22–23

```python
SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))
from check_convergence import (...)
```

**Issue:**
- Mutates global `sys.path` at import time. In a pytest session that
  also imports `~/.claude/skills/feature-development/check_convergence.py`
  (the *duplicate* DF2 from spec_audit), Python's import cache will
  serve whichever copy is imported first and silently use it for
  every subsequent reference. The two copies are byte-identical TODAY
  (md5 check via stat-size match) but the plan explicitly defers
  DF2 cleanup — they will diverge as soon as Phase 1 lands in only
  one of them.
- An attacker who can write to *either* skill dir (and Claude itself
  can write to both as the user) can swap behavior across the import
  boundary depending on which test file runs first.

**Why MEDIUM not LOW:** the attack requires write access to one of
the two skill dirs, but a single misplaced `Edit` call by the same
agent already toggles which copy `from check_convergence import` resolves
to. This is exactly the kind of bug that surfaces a year later as
"why does CI behave differently from local."

**Fix:** Replace `sys.path.insert` with a proper package layout —
`tests/conftest.py` setting `pytest_plugins` and a `pyproject.toml`
with `[tool.pytest.ini_options] pythonpath = ["..."]`. OR remove the
duplicate file per DF2 *in this commit*, not deferred.

### LOW — `evaluate_stage5_two_tier` still present in shipped source, still callable

**Status:** removal deferred to Phase 3, which has NOT shipped.

**File:** `tlmforge/skills/feature-development/check_convergence.py` line 240–403

**Issue:**
- The function is still importable and still has its old semantic
  ("iteration >= max_iterations" cap-check vs evaluate_convergence's
  "iteration > max_iterations"). The Phase 0 tests in fact PIN both
  semantics simultaneously at test line 209 vs line 223. A caller who
  imports `evaluate_stage5_two_tier` today gets the off-by-one cap
  behavior the round-1 review identified as a real defect.
- Phase 0 evidence claims "Phase 3 can safely remove ... without
  ambiguity" but the function is removable today, not "after Phase 3"
  — and *not removing it* keeps the off-by-one alive in code that
  any external caller might import.

**Why LOW:** the master plan's spec_audit confirms zero in-tree
callers, so practical exposure is near-zero. Just feels wrong to
have shipped tests that pin a known-buggy behavior as "correct".

**Fix:** if there's a 0.5.0 release planned before Phase 3 lands,
do the Phase 3 removal now (it's a 1-line `del` plus 6 test
deletions). Otherwise, this is purely cosmetic until Phase 3.

### NIT — Phase 0 test directory ships with `__init__.py` but no `conftest.py`

**File:** `tlmforge/skills/feature-development/tests/__init__.py` (empty)

The empty `__init__.py` triggers a known pytest gotcha: with an
`__init__.py` present, pytest uses *package* import mode, which interacts
oddly with the `sys.path.insert` hack above. Removing `__init__.py` and
using rootdir-based `conftest.py` is the cleaner pattern. Not a security
issue; just hygiene.

---

## Distinction: shipped vs deferred

| Concern | Status |
|---|---|
| Gate forgery (verdict=approve + findings=[]) | **OPEN in shipped code.** Plan defers to Phase 1. Phase 0 tests pin it as "expected." |
| Empty `{}` bypass | **OPEN in shipped code.** Plan defers to Phase 1. |
| Iteration cross-check | **OPEN in shipped code.** Plan defers to Phase 1. |
| Path traversal in loaders | **Surface doesn't exist yet** (loaders not shipped). Will become OPEN as soon as Phase 2 lands without Phase 1. |
| All-skipped converges | **OPEN in shipped code.** Not addressed in the master plan. |
| sys.path injection in tests | **SHIPPED.** No fix planned. |
| Off-by-one cap in `evaluate_stage5_two_tier` | **OPEN in shipped code.** Plan defers to Phase 3. |

---

## Verdict: `do_not_ship`

**Caveat:** This verdict applies to the *post-Phase-0 state of the
codebase*, not to the Phase 0 *increment*. The Phase 0 increment is
clean: tests-only, no production behavior change. From a pure
"increment safety" perspective, Phase 0 would be `approve`.

But the user-facing question Stage 5 asks is "should this feature
be considered done?", and the answer is unambiguously NO until at
least Phase 1 ships:

- The convergence script is *load-bearing* for the entire review
  architecture. The gate-forgery CRITICAL means anyone using this
  script *today* has a forgeable review gate.
- The Phase 0 tests document the exploitable behavior as expected.
  Anyone reading the test suite as "this is what convergence
  should do" walks away believing approve+empty is fine.
- The duplicate-script footgun (DF2) is a 2-line cleanup the plan
  defers; the longer it's deferred the more likely silent drift
  bites.

**Recommended path:**
1. Add a prominent README warning that the script is mid-hardening
   and not yet production-safe — until Phase 1 ships, callers MUST
   NOT rely on `evaluate_convergence` as a security gate.
2. Ship Phase 1 (loader + shape validation + iteration cross-check
   + path containment) **before** any 0.5.0 marketplace release.
3. Resolve DF2 (duplicate script) *in this commit or before Phase 1*,
   not after.
4. Re-run this red-team review at end-of-Phase-3 (or end-of-Phase-4)
   to confirm the listed CRITICAL/HIGH findings are actually closed.

