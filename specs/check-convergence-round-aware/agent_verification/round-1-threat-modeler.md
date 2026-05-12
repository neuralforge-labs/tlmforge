# Threat Model Review — check-convergence-round-aware (Round 1)

**Reviewer:** threat-modeler
**Iteration:** 1
**Verdict:** needs_revision

> **Note:** This .md is a faithful transcription of the threat-modeler's
> inline chat output. The agent could not write files directly in this
> running session — its tools list was cached as `Read, Grep, Glob`
> despite the main session's edit to add `Bash, Write, Edit`. Saved
> memory `feedback_subagent_files_need_session_restart` predicts this;
> the dogfood confirmed it. Captured as DF3 in Stage 7 STATUS.md.

## What I read

- `specs/check-convergence-round-aware/spec_audit.md`
- `specs/check-convergence-round-aware/README.md`
- `skills/feature-development/check_convergence.py`
- `skills/feature-development/review_schema.json`
- `skills/feature-development/reviewer-convergence.md` (§0–§1)

## Findings

### CRITICAL: Gate forgery via unauthenticated filesystem writes

**Trust assumption violated:** The design states the script runs on local
trust-zone artifacts only. It then trusts every JSON file at the
expected reviewer path as authentic.

**Attacker model:** The reviewer agents themselves are the attack
surface. A prompt-injected reviewer, a test fixture leaking into a
production run, or any process with write access to
`specs/<feature>/agent_verification/` can manufacture convergence by
writing approve-verdict, empty-findings JSON files for every expected
role. The convergence rule then computes `real_critical_count=0`,
`meta_critical_count=0`, `converged=True`, `action="advance"` — the
gate passes without any real review.

**Fix:** At a minimum, cross-check the `iteration` field inside each
loaded JSON against the `round_n` argument the loader was called for.
Mismatched iteration → treat as `reviewer_json_missing`. Stronger:
HMAC-sign each JSON with a session key.

### HIGH: Schema-absent JSON bypasses convergence silently

`_load_json_safely` accepts any syntactically valid JSON including
`{}`. `evaluate_convergence` defaults missing `verdict` to `"approve"`
and missing `findings` to `[]`, so an empty dict per role produces
`converged=True`.

**Fix:** Validate required top-level keys (`reviewer`, `schema_version`,
`iteration`, `verdict`, `findings`) at load time. On failure, return
`None`.

### HIGH: Path traversal via unsanitized feature_dir and role strings

Loaders splice `feature_dir` and role strings into filesystem paths
without normalization or containment checks. A prompt-injected
`feature_dir="../../etc"` or a role name containing path separators
escapes the `specs/` tree.

**Fix:** Assert `path.resolve().is_relative_to(Path(feature_dir).resolve())`
after construction. Validate role strings against the known reviewer
set.

### MEDIUM: Unbounded JSON file read — no size guard

`json.load` reads the entire file into memory synchronously. A 100 MB
file (anomalous reviewer or test fixture) buffered across a multi-round
loop can cause OOM and crash the orchestration.

**Fix:** `os.path.getsize(path)` check before open; threshold ~1 MB.

### LOW: DeprecationWarning is suppressible — behavioral drift is silent

`warnings.filterwarnings("ignore")` is a common pattern. Callers that
suppress warnings get the old two-tier semantics silently.

**Fix:** If there are no in-tree callers (spec audit confirms zero),
remove `evaluate_stage5_two_tier` entirely. If a grace period is
needed, also write to stderr unconditionally.

## What the design appropriately did NOT defend

- **Concurrent writes:** atomic-write on writer side is the correct
  contract. Loader doesn't need a lock.
- **External network / API surfaces:** none exist. Local filesystem only.
- **Python dict prototype pollution:** `json.load` produces plain dicts;
  no `__class__` deserialization. Safe by stdlib construction.

## Verdict: needs_revision

1 CRITICAL (gate forgery), 2 HIGH (schema bypass, path traversal), 1
MEDIUM (file-size guard), 1 LOW (deprecation strategy). All
design-level and cheap to address before implementation starts. None
require architectural rework.
