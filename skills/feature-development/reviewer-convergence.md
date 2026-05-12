# Reviewer convergence — JSON schema, prompt template, and convergence rule

> Sub-document of `feature-development` skill. Cited from SKILL.md Stage 3 and Stage 5. Purpose: keep SKILL.md under 1200 lines while making the JSON-output and convergence rule details explicit, auditable, and testable.

---

## 0. Per-stage expected reviewer roles

The convergence rule's `expected_roles` list varies BY STAGE. SKILL.md and this sub-doc must agree.

| Stage | Iteration model | Default expected reviewer roles | Conditional / optional |
|---|---|---|---|
| Stage 3 (plan review) | bounded 3-round loop, same reviewers across rounds | `architect-reviewer`, `tester`, `threat-modeler` | `ux-reviewer` (only if plan describes UI work) |
| Stage 4 phase-end (per-phase verification) | bounded 3-round loop per phase | `code-reviewer`, `tester`, `phase-auditor` | `ux-reviewer` (only if phase diff contains UI files) |
| Stage 5 (final audit) | **single shot, no iteration** | `red-team-reviewer` [opus], `architect-reviewer` [sonnet] | none |

**Stage 3 — why the trio:**
- `architect-reviewer`: would a senior L8/E8 ship this design?
- `tester`: edge cases + emits the `tester_edge_cases.json` carryover artifact at Round 1
- `threat-modeler`: design-time trust-boundary violations

**Stage 4 phase-end — why these four:**
- `code-reviewer`: TDD compliance, patterns, security on the phase diff
- `tester`: re-runs the suite and cross-checks `phase-N-evidence.md` numbers; verifies edge cases from `tester_edge_cases.json` are covered at the right layer
- `phase-auditor`: promise-vs-delivered for the phase spec (scope, tests, rollback)
- `ux-reviewer` (conditional): accessibility + platform conventions on UI files in the phase diff

**Stage 5 — why two single-shot agents:**
- `red-team-reviewer` [opus]: adversarial impl-time attack on the full diff. Single shot — the one opus invocation per feature where deep reasoning earns its keep.
- `architect-reviewer` [sonnet]: holistic + cross-phase design check. NOT a re-derivation of design from scratch — focuses on inter-phase consistency, accumulated design debt, irreversible operations that slipped through.

**Stop hooks: removed entirely.** No tester/code-reviewer/ux-reviewer/process-compliance Stop hooks fire after every save anymore. Review happens at the gates above, or via main-agent self-review in the Light path (defined in `~/.claude/CLAUDE.md`).

**Why `code-reviewer` is NOT at Stage 3 or Stage 5** — at Stage 3 there's no code; at Stage 5 every phase's code has already been reviewed by phase-end code-reviewer at Stage 4. Cross-phase code-quality concerns surface via `architect-reviewer`'s Stage 5 holistic pass.

**Why `threat-modeler` is Stage 3 only** — design-time trust assumptions are cheap to fix at design time; by impl time, red-team-reviewer takes the adversarial seat.

**Why `phase-auditor` is Stage 4-only** — its job (promise-vs-delivered) is phase-bound. At Stage 5 the equivalent role is implicitly "feature-as-a-whole vs original master plan," which architect-reviewer handles holistically.

---

## 1. JSON severity schema (single source of truth)

Schema lives in `~/.claude/skills/feature-development/review_schema.json`. The block below is an inline copy with byte-identical drift detection (`test_schema_inline_matches_file.py`).

<!-- BEGIN SCHEMA -->
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "review_schema.json",
  "title": "Reviewer output for feature-development Stage 3 / Stage 5",
  "description": "Locked at version 1.0 by phase-1 of gold-standard-pickup. The convergence rule is driven exclusively by per-finding severity. The top-level verdict is decorative and does not gate convergence.",
  "type": "object",
  "required": ["reviewer", "schema_version", "iteration", "verdict", "findings"],
  "additionalProperties": false,
  "properties": {
    "reviewer": {
      "type": "string",
      "description": "Role identifier, e.g. architect, tester, code-reviewer, gemini."
    },
    "schema_version": {
      "const": "1.0"
    },
    "iteration": {
      "type": "integer",
      "minimum": 1
    },
    "status": {
      "enum": ["ok", "skipped", "error"],
      "default": "ok",
      "description": "ok = real review; skipped = reviewer absent (e.g. Gemini key missing); error = reviewer attempted but failed (synthetic CRITICAL injected)."
    },
    "verdict": {
      "enum": ["approve", "approve_with_warnings", "needs_revision", "do_not_ship"]
    },
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["severity", "category", "file", "finding"],
        "additionalProperties": false,
        "properties": {
          "severity": {
            "enum": ["critical", "high", "medium", "low", "nit"]
          },
          "category": {
            "enum": [
              "security",
              "auth",
              "null_safety",
              "bug",
              "logic_error",
              "race_condition",
              "data_loss",
              "missing_error_handling",
              "test_coverage",
              "tdd_violation",
              "architecture",
              "backwards_compat",
              "performance",
              "observability",
              "documentation",
              "style",
              "meta"
            ]
          },
          "file": {
            "type": "string",
            "description": "Path or 'architecture' for cross-cutting findings."
          },
          "line": {
            "type": ["integer", "null"]
          },
          "finding": {
            "type": "string",
            "minLength": 8
          },
          "suggested_fix": {
            "type": ["string", "null"]
          },
          "notes": {
            "type": "string"
          }
        },
        "allOf": [
          {
            "if": {
              "required": ["severity"],
              "properties": {"severity": {"const": "critical"}}
            },
            "then": {
              "required": ["suggested_fix"],
              "properties": {"suggested_fix": {"type": "string", "minLength": 8}}
            }
          }
        ]
      }
    }
  }
}
```
<!-- END SCHEMA -->

### Field guidance for reviewers

- `severity`: lowercase only. Use `critical` for "blocks shipping," `high` for "must fix before launch," `medium` for "should fix," `low` for "nice to fix," `nit` for stylistic.
- `category`: pick from the enum above. If nothing fits, use `meta` (typically reserved for synthetic findings the orchestrator injects).
- `file`: an exact repo-relative path. For cross-cutting design findings without a single file home, use the literal string `"architecture"`.
- `line`: integer if known, `null` if not (e.g. for architecture findings). Do NOT use a string.
- `finding`: short, declarative description. Minimum 8 characters. Examples: "Token check happens after route dispatch — IDOR vector for /v1/memos/:id."
- `suggested_fix`: required when `severity == "critical"`. Optional otherwise. Concrete enough that a developer can act on it without re-asking.
- `verdict` (top-level): for human readers. The convergence rule does NOT use this field.

---

## 2. Prompt template addition (all stages)

Every reviewer launch prompt — Stage 3, Stage 4 phase-end, Stage 5 — must include the structured-output block. Place it **immediately after** the role-introduction line and **before** the role-specific checks. The output path differs per stage; the JSON shape doesn't.

```
=== STRUCTURED OUTPUT — REQUIRED ===

In addition to your prose markdown report, you MUST use the Write tool to
create a second file at the path specified by your stage:

  Stage 3 Round 1:          specs/<feature>/agent_verification/round-1-<your_role>.json
  Stage 3 Round 2/3:        specs/<feature>/agent_verification/round-N-<your_role>.json
  Stage 4 phase-end R1:     specs/<feature>/phase-N-verification/<your_role>.json
  Stage 4 phase-end R2/3:   specs/<feature>/phase-N-verification/round-N-<your_role>.json
  Stage 5 (single shot):    specs/<feature>/agent_verification/final_audit_<your_role>.json

This JSON file must validate against the schema below (copy exactly):

[paste the contents of <!-- BEGIN SCHEMA --> ... <!-- END SCHEMA --> here at
launch time, OR cite the file path:
  ~/.claude/skills/feature-development/review_schema.json]

Severity ladder (lowercase, pinned): critical | high | medium | low | nit
Category enum: see schema. Pick from list. Use "meta" for synthetic findings.
Suggested_fix is REQUIRED when severity == "critical".
Top-level verdict is decorative — convergence is driven by per-finding severity.

If you do not emit this JSON file, the orchestrator will inject a synthetic
finding `severity=critical, category=meta, finding=reviewer_json_missing` for
your slot. At Stages 3 and 4 (iterative), this triggers a re-launch in the
next round. At Stage 5 (single-shot), this blocks the final audit until you
emit a valid JSON.

=== END STRUCTURED OUTPUT REQUIREMENT ===
```

### Round-2/3 prompt addition (Stage 3 and Stage 4 phase-end iteration)

When iteration > 1, the launch prompt MUST also include this block to enforce verify-your-findings framing:

```
=== ITERATION FRAMING (round N > 1) — REQUIRED ===

Your prior-round findings: <prior_round_findings_path>
The fixes Claude made:     <fixes_path>
Updated plan / diff:       <plan-or-diff-path>

For each of YOUR prior findings: verdict FIXED / PARTIALLY / NOT_FIXED
with file:line evidence in the updated artifact.

Add NEW findings only if you genuinely missed something in the prior round
— NEW signal, not re-derivation of the same finding from a different angle.

=== END ITERATION FRAMING ===
```

---

## 3. Convergence rule

Implemented in `~/.claude/skills/feature-development/check_convergence.py` (delivered in phase-1b of gold-standard-pickup). The rule, in plain language:

1. Collect all `<role>_review.json` files in `specs/<feature>/agent_verification/` for the current iteration.
2. For each role expected by the current stage (see §0 for the per-stage table — Stage 3 default: architect-reviewer + tester + threat-modeler; Stage 5 tier-1 default: architect-reviewer + code-reviewer + tester + gemini-if-present; Stage 5 tier-2: red-team-reviewer): if the JSON file is missing, inject a synthetic finding `severity=critical, category=meta, finding=reviewer_json_missing` for that role.
3. For each reviewer with `status: "ok"` or `status: "error"`: count `severity=="critical"` findings.
4. **Real CRITICAL count** = sum of `critical` findings with `category != "meta"`.
5. **Meta CRITICAL count** = sum of `critical` findings with `category == "meta"` (these are synthetic / orchestrator-injected: `gemini_unavailable`, `gemini_wiring_broken`, `reviewer_json_missing`, `reviewer_timeout`, `reviewer_verdict_findings_mismatch`).
6. **Reviewers with `status: "skipped"`** are excluded from convergence counting; they are logged in SUMMARY.md as "<role> skipped — <reason>" so the absence is visible.
7. **Convergence reached** when: `Real CRITICAL == 0 AND Meta CRITICAL == 0 AND iteration <= 3`.
8. **Lazy-empty-findings rule** (RES-1): if a reviewer emits `findings: []` AND `verdict in ["needs_revision", "do_not_ship"]`, inject `severity=critical, category=meta, finding=reviewer_verdict_findings_mismatch`. If `findings: []` AND `verdict == "approve"`: log a WARNING (visible in SUMMARY.md) but do not block convergence — the warning lets a human notice if a reviewer skipped substantive review.

### Iteration cap & user-facing message

If iteration > 3 and not converged, surface to user a structured message that distinguishes the four cases:

| Case | User-visible message |
|---|---|
| Real CRITICAL > 0, Meta CRITICAL == 0 | "Convergence cap hit at iteration 3. Real CRITICALs persist:\n  - <reviewer>: <finding>\n  - ...\nNext: address the findings above and request another review iteration." |
| Real CRITICAL == 0, Meta CRITICAL > 0 (typically `gemini_unavailable`) | "Convergence cap hit. No real CRITICALs in 3 iterations, but Gemini wiring is broken (<count> meta findings).\nNext: (a) fix Gemini wiring, (b) accept 3-reviewer convergence (lose diversity guarantee), or (c) abort." |
| Real CRITICAL > 0 AND Meta CRITICAL > 0 | "Convergence cap hit. Real CRITICALs persist AND Gemini is unavailable. Recommend fixing the real findings first, then re-launching with Gemini once wiring is resolved." |
| All `skipped` (no real reviewers ran) | "All reviewers skipped — convergence cannot be evaluated. Check launch configuration." |

### Per-reviewer wall-clock timeout (Cat 6)

- Claude reviewers (`Agent` calls): 60 seconds per reviewer per iteration.
- `ai_review_json.sh` Bash call: 30 seconds per invocation per iteration.
- A reviewer's JSON file missing at the deadline → synthetic `severity=critical, category=meta, finding=reviewer_timeout`.

### Atomic write contract

`ai_review_json.sh` and any reviewer-JSON-writing path must:
1. Write to `<final-path>.tmp`
2. `mv` to `<final-path>` only after writing is complete

### Carryover artifacts (Stage 3 → Stage 4)

These are NOT review JSON sidecars — they're inputs the next stage reads to avoid re-derivation:

| Artifact | Produced by | Consumed by | Purpose |
|---|---|---|---|
| `agent_verification/tester_edge_cases.json` | tester at Stage 3 Round 1 | main Claude at Stage 4 (scenario seed for TDD); tester at Stage 4 phase-end (coverage validation) | Avoid re-enumerating edge cases 3× across stages |
| `agent_verification/round-N-fixes.md` | main Claude after each Stage 3 round | reviewers at Stage 3 round N+1 (verify-your-findings) | Tells round N+1 reviewers what changed and why |
| `phase-N-verification/round-N-fixes.md` | main Claude after each phase-end round | reviewers at phase-end round N+1 | Same pattern as Stage 3 fixes |
| `phase-N-state.md` (existing) | main Claude at phase start | Stage 4.6 phase-end agents (anchors the diff baseline) | Records `git_sha:` so reviewers diff from the right commit |

**Schema for tester_edge_cases.json:**
```json
{
  "schema_version": "1.0",
  "feature": "<feature-slug>",
  "produced_by": "tester-stage-3-round-1",
  "edge_cases": [
    {
      "id": "EC1",
      "title": "<short>",
      "surface": "<file or area>",
      "expected": "<expected behavior>",
      "test_stub": "<runnable code or pseudocode>",
      "source": "design" | "impl"   // "design" set by Stage 3 tester; "impl" set by main Claude if scenario surfaced during impl
    }
  ]
}
```

Main Claude UPDATES this file in place during Stage 4 — when implementation surfaces a scenario Stage 3 missed, append with `source: "impl"`. Phase-end tester reads the full set (design + impl).

This prevents the convergence script from reading a half-written JSON.

---

## 4. Stage 5 — always single-shot, no skip rule

Stage 5 in the lean architecture is **always two single-shot agents** (red-team-reviewer + architect-reviewer), no iteration, no skip rule. Cost is bounded by design:
- 1 opus invocation (red-team) + 1 sonnet invocation (architect) per feature
- No retry/convergence loop at this stage — the iterative loops already ran at Stage 3 and Stage 4 phase-end

If either Stage 5 agent finds CRITICALs, the user is escalated via `agent_verification/FINAL_ESCALATION.md` and decides next steps (fix and re-run Stage 5 as a fresh single-shot, accept residual risk, or abandon). There is no automatic re-launch.

The previous skip-rule logic (Stage 5 fires only if Stage 3 was needs_revision or had CRITICALs) is obsolete — Stage 5 now does work that no earlier stage covers (cross-phase holistic + adversarial impl), so it always fires.

---

## 5. Backwards compatibility

- **No silent prose-grep fallback** (per SUMMARY.md Cat 2). For any new feature run with this skill, missing JSON triggers `reviewer_json_missing`.
- Legacy `agent_verification/` directories from before this change (e.g., `plans/encryption/`) are read-only historical artifacts. The skill does NOT consume them at runtime.
- A future `--legacy-tolerant` mode for migrations is out of scope here.

---

## 6. Atomic-write and Bash invocation guidance

When invoking `ai_review_json.sh` from Stage 5, use:
```
Bash(
  command="bash ~/.claude/skills/feature-development/ai_review_json.sh \
    --output specs/<feature>/agent_verification/gemini_review.json \
    --iteration <N> > .tmp/gemini_review/<timestamp>.log 2>&1",
  run_in_background=true,
  timeout=35000
)
```

Followed by a `Monitor` or polling step to wait for the JSON file to land, with a 30-second per-invocation deadline.

---

## 8. Compressed sub-agent returns (gap F)

Sub-agent JSON sidecars are the exhaustive output. Their **chat reply** to the
orchestrator must be a compressed summary — no raw file dumps, no copy-pasted
code, no full markdown reports. Cap: **≤ 5 sentences AND ≤ 1000 characters**.

The launch prompt template (§2 above) closes with this addendum on every Stage
3 / Stage 5 reviewer launch:

```
Your chat reply to the orchestrator must be ≤ 5 sentences and ≤ 1000
characters. Treat your JSON sidecar (and markdown report) as the exhaustive
output — they're written to files where I can read them. Do NOT repeat the
JSON contents or paste file fragments into your chat reply. Anything longer
in this reply is wasted orchestrator context and weakens convergence.
```

This is advisory (not validator-enforced); a noncompliant agent doesn't break
the system, it just wastes context. Convergence reads from the JSON sidecars
regardless of chat-reply size.

---

## 9. State.md handoff between Stage 4 and Stage 5 (gap E)

Stage 4 phases are long; by phase N's end, the implementer's context is full
of impl narrative that biases the Stage 5 reviewer. To enable a cold-start
Stage 5, each Stage 4 phase writes `specs/<feature>/phase-N-state.md`.

**Format (atomic-write per §6 — write to `phase-N-state.md.tmp`, then `mv`):**

```markdown
---
git_sha: <abbrev SHA from `git rev-parse --short HEAD` at write time>
phase: N
written_at: <ISO 8601 timestamp>
---

## Commits landed
- <sha>: <one-line>
- ...

## Tests now passing
- <count> new tests; <count> total in feature
- baseline regression: zero broken

## Anything that surprised me
- <terse honest list — used to feed learnings.md at Stage 7>
```

**Stage 5 reads it cold.** Compare `git_sha:` to `git rev-parse --short HEAD`:

- equal → safe to use as-is
- HEAD ahead of state.md → emit warning ("state.md is from <sha>, HEAD is at
  <sha>; reviewing against current HEAD"), proceed
- state.md missing → graceful absence, proceed without narrative

The Stage 5 launch prompt explicitly frames state.md as DATA (context the
reviewer reads), NOT as INSTRUCTIONS — the implementer's narrative is
informational, not authoritative. Reviewers must adversarially scrutinize the
diff, not be biased by what the implementer claims to have surprised them.

---

## 7. Testing this sub-document

Tests live in `~/dotfiles/claude/plans/gold-standard-pickup/phase-1/tests/`:
- `test_review_schema*.py` — schema validity, enums, additionalProperties, suggested_fix-required-for-critical
- `test_schema_inline_matches_file.py` — drift detection between this document and `review_schema.json`
- `test_skill_md_references_subdocument.py` — SKILL.md cites this file in Stage 3 and Stage 5
- `test_mirror_byte_identical.sh` — active and dotfiles paths match

Run from the tests directory:
```
.venv/bin/python -m pytest -v
bash test_mirror_byte_identical.sh
```

(The `.venv` is created with `python3 -m venv .venv && .venv/bin/pip install pytest jsonschema`.)
