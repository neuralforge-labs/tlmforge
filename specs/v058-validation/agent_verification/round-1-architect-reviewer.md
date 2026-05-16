# v0.5.8 Validation — Architect Review (Round 1)

**Reviewer:** architect-reviewer
**Iteration:** 1
**Verdict:** NEEDS REVISION

---

## Summary

The plan adds `test_v058_medium_path.py` with 15 content-integrity tests and 6 functional
convergence tests to guard v0.5.8's Medium-path changes. The approach is directionally correct
but has four issues that need fixing before implementation starts: one CRITICAL (the pre-fix bug
pin test is logically inverted and produces no meaningful regression value), one HIGH (on-disk
file reads couple the test suite to ephemeral developer-machine state), one HIGH (the TDD ordering
claimed in the plan is backwards for content tests), and one MEDIUM (the plan claims 151+ tests
but does not establish the baseline).

---

## CRITICAL Issues

### C1. Pre-fix bug pin test is logically wrong and adds no regression protection

**Location:** README.md — `TestConvergenceMediumPath` test 6 ("Pre-fix bug pinned")

**What the plan says:** "Pre-fix bug pinned: if threat-modeler is listed in expected_roles for
Medium Stage 3, but absent → meta CRITICAL"

**Why it's wrong:** `evaluate_convergence()` already produces a `reviewer_json_missing` meta
CRITICAL for *any* role that's listed in `expected_roles` but absent from the input dict —
regardless of whether that role is "correct" for Medium. This is a property of the function
itself, not of the v0.5.8 fix. The test as described is trivially TRUE both before and after
v0.5.8: it tests `evaluate_convergence()` doing its job, not the v0.5.8 behavioral change.

The actual v0.5.8 bug was: `reviewer-convergence.md` didn't have Medium rows in the per-stage
table, so whoever called `evaluate_convergence()` was constructing `expected_roles` with
`threat-modeler` included (because they read the Deep default). The fix was to add Medium rows
that OMIT threat-modeler. A meaningful regression test would need to verify that the *caller*
passes the right `expected_roles` for Medium — but `evaluate_convergence()` itself has no notion
of "Medium" vs "Deep." That context lives in SKILL.md and the human/LLM reading it, not in
code that can be called with an assertion.

**Impact:** The test passes identically before and after v0.5.8. It gives false confidence that
the behavioral regression is caught when it is not. Any accidental revert of the Medium row
addition to reviewer-convergence.md would NOT be caught by this test — the content integrity
tests would catch it, but this functional test would remain GREEN regardless.

**Recommended fix:** Either (a) remove the "pre-fix bug pin" functional test and document its
absence as intentional (the content integrity tests are the actual regression guard for this
bug class), or (b) replace it with a test that actually exercises the *integration* between
the table and the caller — e.g., a test that reads the Medium row from reviewer-convergence.md,
parses the expected_roles from it, and verifies threat-modeler is NOT in that list. That would
be a meaningful end-to-end regression test for the actual bug.

---

## HIGH Issues

### H1. On-disk file reads couple tests to machine state — brittle by design

**Location:** README.md and spec_audit.md — `TestSkillContentIntegrity` (all 15 tests)

**What the plan says:** Tests "read actual SKILL.md, reviewer-convergence.md, and ~/.claude/CLAUDE.md
on disk."

**Why it's a problem:**

1. **Environment coupling.** The files live at developer-machine paths (`~/.claude/CLAUDE.md`,
   `$REPO_ROOT/skills/feature-development/SKILL.md`). In a clean clone on
   another machine, `~/.claude/CLAUDE.md` may not exist or may be a different version. The
   spec_audit.md acknowledges this ("Tests skip gracefully if that file is absent") but that
   means the test suite silently degrades: the very tests guarding the ~/.claude changes become
   no-ops on machines without the file. CI systems, pair programmers, or reviewers running
   locally get a different pass/fail set than the author.

2. **Skip ≠ pass.** A test that skips because its precondition is absent is not a green test
   — it's an untested claim. The plan treats `pytest.skip()` on missing `~/.claude/CLAUDE.md`
   as acceptable, but it means the "abbreviated recipe" assertion (test 15) is never enforced
   outside the author's machine.

3. **False sense of security.** If someone reverts the ~/.claude/CLAUDE.md change (say, restoring
   a backup), the test that should catch it just skips. The regression is silent.

**Recommended fix:** For SKILL.md and reviewer-convergence.md (which ARE in the repo), on-disk
reads are acceptable — those files are part of the repo and will be present in any clone. The
fix is specific to `~/.claude/CLAUDE.md`: either (a) copy the relevant CLAUDE.md fragment into
a committed fixture file within the repo (e.g.,
`tests/fixtures/claude_medium_path_excerpt.txt`) and test against that, or (b) make the test
mandatory (no skip) and document that it must be run on the author's machine as part of the
v0.5.8 checklist. Option (a) is strongly preferred because it makes the suite
unconditionally reproducible.

### H2. TDD red phase is impossible for content integrity tests — plan is describing a fake RED

**Location:** README.md — "TDD plan" section: "Write TestSkillContentIntegrity first, verify
all 15 tests are GREEN (files already patched)"

**Why it's a problem:** The plan acknowledges that the files have already been patched as part
of v0.5.8. Writing content-integrity tests against already-patched files means the tests go
GREEN immediately — there is no RED phase. The plan does not describe how RED will be
confirmed for this class of tests. The description "Write failing tests first (pre-confirm RED
against inline fixtures that simulate v0.5.7 state)" appears in the Phase steps but
contradicts the TDD plan section which says "verify all 15 tests are GREEN."

This isn't a theoretical concern — TDD rules (`~/.claude/rules/tdd.md`) are explicit:
"Run new tests → confirm RED. A test that passes before impl is worthless." If the impl is
already done (files already patched), the only honest path to RED is:

- Test against inline fixtures that hold v0.5.7 content (not the live files), confirm RED
- Then switch to the live file reads, confirm GREEN

The plan mentions fixtures in Phase steps but doesn't commit to this approach in the TDD plan
section. The two sections are inconsistent, and the likely implementation path (write tests
against live already-patched files, observe GREEN, claim done) skips RED entirely.

**Recommended fix:** The TDD plan section must explicitly state: "Content integrity tests are
written against inline v0.5.7 fixture strings first (no on-disk file reads in the RED phase).
Confirm RED against the fixture. Then switch the parameterization to read from live disk files
and confirm GREEN." The implementation must execute this sequence and capture RED output as
evidence.

---

## MEDIUM Issues

### M1. The "151+ tests" verification criterion is unanchored — baseline is unknown

**Location:** README.md — "Verification criteria": "python3 -m pytest hooks/tests/
skills/feature-development/tests/ -v → 151+ passed, 0 failed"

**Why it's a problem:** The plan claims the combined suite should reach 151+. The existing
test files contain 22 + 11 = 33 tests under `skills/feature-development/tests/`. Adding 21
new tests gives 54 there. The "151+" number includes `hooks/tests/` — but the plan never
establishes the current hooks test count. If the hooks suite currently has 120 tests, 151+
is achievable. If it has 90, the math doesn't work. This is an unverified claim.

More importantly, the `hooks/tests/` suite is not read by the plan at all — it's just
referenced in the combined count. If `hooks/tests/` currently fails for unrelated reasons,
the verification criterion silently blocks the plan's success check.

**Recommended fix:** Before implementation, run the full suite and capture the current baseline
count. Replace "151+" with the concrete expected count: "current_baseline + 21 = N; expect N
passed." This is a one-command check that should be done at plan time, not left ambiguous.

### M2. No test for the "superset" behavior in Stage 3 Medium (test 4 of convergence class)

**Location:** README.md — test 4: "Medium Stage 4 with all 3 Deep agents → still converges
(superset of expected)"

**Why it's worth flagging:** This test passes `code-reviewer + tester + phase-auditor` to
a Medium Stage 4 convergence call where `expected_roles = ["code-reviewer", "phase-auditor"]`.
The behavior being tested is that extra roles in `reviewer_jsons` (beyond `expected_roles`)
do not cause synthetic CRITICALs. Reading `check_convergence.py` at lines 79-119, the
function iterates `expected_roles`, not `reviewer_jsons.keys()` — extra keys are simply
ignored. This is already pinned by the existing test suite implicitly. The test adds no new
signal and exercises a trivially obvious code path.

**Recommended fix:** Replace this slot with a more discriminating scenario: what happens when
the Medium Stage 4 `phase-auditor` returns `verdict=needs_revision` with a real CRITICAL?
This exercises the full happy-path→blocking path transition that the Medium phase-end actually
needs to handle. It also pairs with test 3 (converges) to give you a symmetric pair.

---

## LOW Issues

### L1. Plan does not specify test isolation between TestSkillContentIntegrity tests

**Location:** README.md / implied implementation

The 15 content tests all read the same on-disk files. If the test class uses `setUpClass`
or module-level caching (likely, for performance), a test that mutates a shared string
could contaminate subsequent tests. The plan is silent on this. Since the tests read but
don't write, the risk is low — but the plan should explicitly state that each test re-reads
(or that the fixture is module-level read-once, with explicit rationale).

### L2. Convergence test 5 (Stage 5 Medium with phase-auditor only) is under-specified

**Location:** README.md — test 5: "Medium Stage 5 with phase-auditor only → converges
(no synthetic for red-team)"

The test verifies that passing `expected_roles=["phase-auditor"]` with a phase-auditor
approval doesn't trigger a synthetic for red-team-reviewer. This is correct. But it should
also verify that the result keys match what the caller expects (e.g., `converged=True`,
`real_critical_count=0`, `meta_critical_count=0`). The plan description doesn't state which
assertions will be made. A test that calls `evaluate_convergence()` and just doesn't crash is
not a test.

---

## What's Good

1. **The core insight is correct.** Content integrity tests for SKILL.md and
   reviewer-convergence.md against in-repo files is a sound pattern for guarding against
   accidental reverts. The `test_check_convergence.py` precedent (characterization tests
   against an already-correct function) shows this repo is comfortable with this pattern.

2. **Scope is tight.** One new file, zero changes to existing tests, clear rollback. Exactly
   right for a Medium task.

3. **The split between content tests and functional tests is architecturally sound.** Content
   tests catch "did someone revert the file change." Functional tests catch "does the function
   behave correctly given correct inputs." These are orthogonal failure modes and both deserve
   coverage.

4. **Functional convergence tests are correctly scoped.** Tests 1-5 call `evaluate_convergence()`
   directly with Medium-specific `expected_roles` — this is the right level of abstraction.
   No mocking of the function, no patching — just the real function with controlled inputs.

5. **Graceful skip for ~/.claude/CLAUDE.md is acknowledged upfront** in spec_audit.md rather
   than buried in implementation. Even though I'm recommending fixing it (H1), the fact that it
   was surfaced as a known tradeoff is better than discovering it in a CI failure.

---

## Instruction Compliance

The plan addresses the original mandate (add regression tests for v0.5.8 changes, both content
and functional). No scope creep. Files in scope are exactly what was described. The Medium path
process (spec_audit → README → single-round review) is being followed. Compliant on scope.

Non-compliant on TDD discipline: the plan does not cleanly establish how RED will be achieved
for content integrity tests (H2). This must be resolved before implementation.
