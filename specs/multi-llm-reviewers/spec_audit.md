# multi-llm-reviewers — Spec Audit

## What the user asked for

Add OpenAI (o3 model, called "Codex" colloquially) and Gemini as optional additional reviewers
in the tlmforge feature-development skill — alongside Claude — at Stage 3 (plan review),
Stage 4 phase-end (code review), and Stage 5 (final audit). Users should be able to configure
which LLMs participate: Claude always on (default), Codex opt-in, Gemini opt-in.

## Industry standard / how others do this

- **Multi-model review panels** are increasingly common in AI-assisted dev tooling (Cursor,
  Copilot Enterprise). The pattern: each model gets the same context, outputs structured JSON,
  a convergence layer aggregates findings.
- **Graceful-skip on missing key** is the gold standard for optional integrations — the feature
  degrades cleanly rather than blocking the workflow (AWS Bedrock, LangChain optional providers).
- **Config via env vars** (not config files) is the norm for secret-adjacent settings: key
  presence implies enablement; explicit feature flags avoid surprising "I set the key and now
  it's billing me" moments.
- **Schema-pinned output** (like `review_schema.json`) is how enterprise review tooling prevents
  hallucinated structures from silently corrupting downstream aggregation.

## Prior-art learning (from `learnings.md`)

- The enforcement-hooks feature showed that security-surface changes (secret/credential handling)
  must be classified Deep — this feature touches API key handling so Deep is correct.
- v058-validation showed "add X" tasks can masquerade as simpler intensity — pre-implementation
  audit discipline catches this.

---

## Findings (severity-ranked)

### CRITICAL — Decisions needed before any code

#### F1. Model naming: "Codex" is not the current OpenAI API model
- **Spec said:** "Integrate Codex"
- **Industry standard:** OpenAI Codex was deprecated in 2023. The current reasoning/code model
  is `o3` (or `o4-mini` for cost). The TLM server already uses `o3` for adversarial code review.
- **Problem:** If we ship `model="codex-002"` or similar, every call will 404. The correct
  model identifier is `o3` via the OpenAI Responses API.
- **Recommendation:** Use `o3` (full) for Stage 5 final audit and code review; `o4-mini` as
  cost-saving option for Stage 3 plan review. Make model names configurable via env.
- **Decision required:** Should Stage 3 plan review use `o3` (more expensive, same as Stage 5)
  or `o4-mini` (cheaper, slightly less capable)? [GATE-BLOCKING]

#### F2. API key exposure risk — TLM_OPENAI_API_KEY
- **Spec said:** Key is in GCP Secret Manager as `TLM_OPENAI_API_KEY` in `YOUR_GCP_PROJECT`.
- **Industry standard:** Keys must never appear in scripts, env files, or logs; always fetched
  at runtime from a secrets manager.
- **Problem:** The current Gemini pattern fetches the key inline via `gcloud secrets` inside
  `settings.local.json` (not committed). OpenAI must follow the same pattern. Additionally,
  the raw key value was exposed in this conversation — the user should rotate it.
- **Recommendation:**
  1. Rotate `TLM_OPENAI_API_KEY` in GCP Secret Manager immediately (existing value was exposed).
  2. Fetch via `gcloud secrets versions access latest --secret=TLM_OPENAI_API_KEY --project=YOUR_GCP_PROJECT --account=dev@neuralforge.co.in`.
  3. Add `"Bash(OPENAI_API_KEY=:*)"` to `~/.claude/settings.json` permissions (mirrors the
     existing `Bash(GEMINI_API_KEY=:*)` entry).
  4. Never log `OPENAI_API_KEY` value; use `set -euo pipefail` (not `set -x`) in the shell script.
- **Decision required:** Key rotation: does the user want to do this now or accept the risk
  and rotate before going to production? [GATE-BLOCKING]

#### F3. Dynamic reviewer roster — convergence logic assumes a static expected_roles list
- **Spec said:** Users configure which LLMs are enabled.
- **Industry standard:** Plugin systems expose a config surface; the aggregator inspects
  which providers are active before counting expected roles.
- **Problem:** `check_convergence.py`'s `evaluate_convergence(reviewer_jsons, expected_roles, ...)`
  requires an explicit `expected_roles` list. If a new LLM reviewer is enabled but not
  in `expected_roles`, it's silently ignored. If it's in `expected_roles` but the script
  exits 2 (key absent), a `reviewer_json_missing` synthetic CRITICAL fires — blocking
  the feature.
- **Recommendation:** The OpenAI/Gemini scripts must write a `status="skipped"` JSON sidecar
  on graceful exit (exit code 2), NOT exit silently. Then the SKILL.md orchestration
  should add them to `expected_roles` only when the feature flag is explicitly set.
  Alternatively, scripts that exit 2 write their sidecar and convergence treats them as
  skipped. `ai_review_json.sh` already writes skipped JSON on exit 2 — new scripts must
  match this pattern exactly.
- **Decision required:** None — this is a design constraint, not a product decision.
  [INFORMATIONAL]

---

### HIGH — Should fix before launch

#### F4. `ai_review_json.sh` uses `git diff HEAD` — this may be empty at Stage 3 (plan review)
- **Spec said:** New reviewers used at Stage 3 (plan review), Stage 4 (code review), Stage 5.
- **Problem:** `git diff HEAD` is empty before any code is written (Stage 3). The Gemini
  script would send an empty diff to the model, getting a vacuous "no findings" response.
  Stage 3 reviews are of the plan document (README.md), not the diff.
- **Recommendation:** The new orchestration must pass different context per stage:
  - Stage 3: pipe `specs/<feature>/README.md` content as input
  - Stage 4/5: pipe `git diff HEAD` (or diff against phase base commit)
  - The OpenAI script needs `--mode plan|code|diff` to know what to send.
- **Decision required:** None — design constraint. [INFORMATIONAL]

#### F5. Cost exposure with no guard
- **Spec said:** User can enable Codex=yes/no.
- **Problem:** o3 pricing is ~$2/1M input + $8/1M output tokens (estimate; mark as guess).
  A 20K-token diff review costs ~$0.04 per call. A full Deep feature with 3 phases × 3
  rounds × Stage 5 = ~12 review calls × $0.04 = ~$0.50 in OpenAI costs per feature.
  Gemini Pro 2.5 pricing is similar. Without a circuit breaker, an infinite retry loop
  or a malformed prompt amplifier could rack up unexpected charges.
- **Recommendation:** Honor the existing `max_iterations=3` cap in convergence. The scripts
  themselves don't need a rate limiter — the skill orchestration already caps iterations.
  No additional cost guard needed beyond existing convergence cap.
- **Decision required:** None — existing cap is sufficient. [INFORMATIONAL]

#### F6. No fallback if both Claude AND LLM reviewer have a CRITICAL
- **Spec said:** Multi-model for multiple opinions.
- **Problem:** If the new LLM reviewer (e.g., OpenAI) flags a CRITICAL and Claude doesn't,
  the feature stays in revision loop. This is the desired behavior. But if the LLM is
  hallucinating a false CRITICAL (LLMs can), the loop could get stuck.
- **Recommendation:** Keep the existing `max_iterations=3` cap and `requires_user_override`
  path — they already handle persistent unresolvable CRITICALs. No new mechanism needed.
  [INFORMATIONAL]

---

### MEDIUM

#### F7. settings.json sync script may miss the new `Bash(OPENAI_API_KEY=:*)` permission
- A prior observation (3430) noted that the worktree was missing from the settings sync
  script. The new OPENAI permission entry in `~/.claude/settings.json` must also be
  reflected in the plugin's documented setup steps.
- [INFORMATIONAL]

#### F8. OpenAI Responses API vs Chat Completions API
- o3 is available via the Responses API (`client.responses.create`) AND Chat Completions
  (`client.chat.completions.create`). The TLM server uses Responses API.
  The shell script approach (like `ai_review_json.sh`) would call the OpenAI CLI or
  a small Python wrapper. We need to decide: shell script (like Gemini) or Python module.
- **Recommendation:** Python script (`ai_review_json_openai.py`) for OpenAI since there's
  no official OpenAI CLI binary (unlike the `gemini` CLI). Shell thin-wrapper that calls
  the Python script — same exit-code contract as the Gemini script.
- [INFORMATIONAL]

---

### LOW

#### F9. SKILL.md documentation will need updating
- The reviewer roster tables in SKILL.md currently list Claude agent types only (architect-reviewer,
  tester, etc.). Adding LLM reviewers as "auxiliary" participants needs a clear documentation
  section so future engineers know the roster is dynamic.
- [INFORMATIONAL]

---

## Open questions for the user

1. **[GATE-BLOCKING] Model for Stage 3:** Should Stage 3 plan review use `o3` (expensive,
   full reasoning) or `o4-mini` (cheaper, faster)? Recommended: `o4-mini` for plan review,
   `o3` for Stage 5 final audit and Stage 4 code review.

2. **[GATE-BLOCKING] Key rotation:** The OpenAI API key value was exposed in plaintext in
   this conversation session. Recommend rotating `TLM_OPENAI_API_KEY` in GCP Secret Manager
   before wiring it in. Do you want to rotate it now or proceed with current key?

3. **[INFORMATIONAL] Gemini at Stage 4/5:** The existing `ai_review_json.sh` already handles
   the Gemini-as-reviewer pattern for Stage 5. This feature will extend it to Stage 3 and
   Stage 4 as well. No decision needed — the extension is in scope.
