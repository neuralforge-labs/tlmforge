# Threat Modeler — Round 2 Review
# multi-llm-reviewers
# Iteration: 2

## Round-1 Finding Verdicts

### CRITICAL-1 — `Bash(OPENAI_API_KEY=:*)` blanket execution surface
**Verdict: FIXED**

Evidence: The updated plan's Scope section now reads `~/.claude/settings.json: add Bash(ai_review_openai.sh:*)` with an explicit parenthetical `(NOT a blanket OPENAI_API_KEY=:* entry — see security constraints)`. The Threat model / constraints section adds the prohibition as a named bullet. The Decisions section records the rationale. Phase 0 Step 3 says `"Bash(ai_review_openai.sh:*)"` as the specific permission entry. The old attack surface is removed by design.

---

### CRITICAL-2 — Unvalidated active-feature marker → path traversal → exfiltration
**Verdict: FIXED**

Evidence: The plan now mandates the validation in three places:
- Constraints section: "Regex: `re.fullmatch(r'[a-zA-Z0-9_-]+', feature_name)`. Reject anything with `/`, `..`, spaces, or special characters — exit 2 with `status=skipped`."
- Phase 1 pre-flight: "`mode=plan`: validate marker with `re.fullmatch(r'[a-zA-Z0-9_-]+', feature)` ... if invalid or absent → skipped"
- Phase 2 steps: "`[[ ! "$feature" =~ ^[a-zA-Z0-9_-]+$ ]]` → exit 2 skipped"
- Sensitive surface inventory: "`.tlmforge_active_feature` — validated with `[a-zA-Z0-9_-]+` before use in path"
- Tests added: marker with `../foo`, marker with spaces, absent marker — all must exit 2.

The fix is thorough and present in both the Python and shell paths.

---

### HIGH-1 — `git diff HEAD` sent to OpenAI without acknowledging the data-trust boundary
**Verdict: FIXED**

Evidence: The risk audit table now has an explicit HIGH row: "git diff HEAD and plan README content sent to api.openai.com — may include accidentally staged .env files, secrets in test fixtures, or NDA-sensitive architecture | Accepted risk — opt-in only; documented here. Future: pre-flight secret scan before send." The outbound channel to api.openai.com is now named in the sensitive surface inventory. The acknowledgment is present.

---

### HIGH-2 — API error messages interpolated into JSON → JSON boundary breakage
**Verdict: FIXED**

Evidence: The constraints section now states "All JSON output via `json.dumps()`, never string interpolation." The architecture section repeats this as a code comment. Phase 1 steps specify "ALL failure paths write `status=skipped`" (eliminating the paths that were building error-message strings). The Decisions section records "`json.dumps()` for all output: prevents JSON boundary breakage on error messages containing quotes (threat-modeler HIGH-2)." The fix directly addresses the named assumption.

---

### MEDIUM-1 — Plan README sent to OpenAI with no size guard or content filter
**Verdict: PARTIALLY**

The round-1-fixes.md defers this with the rationale that "silent skip on quota error already handles it." The operational consequence (convergence not blocked) is addressed by the new skip-on-failure policy. However, the original finding had two components:
1. Convergence block risk — now handled via silent skip.
2. Exfiltration of sensitive content in a large README to api.openai.com — still present and only covered by the general HIGH-1 risk table entry which focuses on `git diff HEAD`. The README-specific path is not separately acknowledged.

The risk is documented at a coarser granularity than the finding. The convergence-block half is resolved; the data-exfiltration half is partially absorbed into HIGH-1's rationale but not explicitly called out for plan mode.

---

### MEDIUM-2 — `TLMFORGE_OPENAI_MODEL` env var passed without validation
**Verdict: NOT_FIXED**

Not addressed in the fixes doc or updated plan. The plan still shows `os.environ.get("TLMFORGE_OPENAI_MODEL", "gpt-5.5")` passed directly to the SDK. The round-1 finding itself noted the SDK provides implicit sanitization via JSON serialization, so this remains a low-priority speculative finding. The deferral is defensible.

---

### LOW-1 — TOCTOU between key check and API call → status=error instead of status=skipped
**Verdict: PARTIALLY**

The risk audit table now has a LOW row acknowledging this: "TOCTOU between key presence check and API call | Results in status=error instead of status=skipped; correct graceful behavior."

However, this description is now inconsistent with the updated plan. The new user requirement mandates ALL LLM provider failures produce `status=skipped`, never `status=error`. The risk table says the TOCTOU "Results in status=error" — which contradicts the new policy. An AuthenticationError raised at API call time (after the key-check passed) must now produce `status=skipped` per the constraint section. The risk table description is stale. The operational behavior should be correct if Phase 1 is implemented faithfully, but the documented expectation is wrong.

---

### LOW-2 — `--output` path accepted without traversal constraint
**Verdict: NOT_FIXED**

The sensitive surface inventory now says: "`--output` path — parent directory existence checked before write; no traversal check needed (script writes to where called from, not user-supplied arbitrary paths)."

This assertion is incorrect. The `--output` path IS a user-supplied CLI argument — the orchestrator (SKILL.md) constructs and passes it. The argument "writes to where called from" is true only if the caller passes a relative path; nothing in the design prevents passing an absolute path like `--output /etc/cron.d/openai_review`. The traversal check was acknowledged as low-severity (requires compromised orchestrator), and that assessment stands — but the fix doc claims no traversal check is needed, which is a false assertion, not a genuine mitigation.

This remains low-severity because exploitation requires compromising the SKILL.md orchestrator or a prompt injection that reshapes the tool call. It is not a convergence blocker.

---

## New Findings

### NEW-1 — Silent-skip failure mode enables stealthy reviewer-suppression
**Severity: medium**
**Category: security**

The new user requirement — "ALL LLM provider failures → status=skipped" — creates a new threat assumption: the design assumes that LLM provider failures are non-adversarial (network glitches, key expiry, quota exhaustion). An attacker who can cause targeted API failures can silently eliminate the OpenAI and/or Gemini reviewers from every review round without any in-workflow signal.

Concrete suppression vectors:
1. Inject `TLMFORGE_ENABLE_OPENAI=0` or unset `OPENAI_API_KEY` into the process environment via a compromised CI step or a crafted `.env` file loaded before the skill runs.
2. Craft a diff containing a content-moderation trigger. OpenAI's content policy rejection returns an API error → status=skipped → reviewer silently absent.
3. In an org with shared key quota, deliberately exhaust the key with spurious requests before a targeted review round.

The design assumes that the operator reads `~/.cache/tlmforge/llm_reviewer.log`. There is no in-workflow notification: nothing causes the SKILL.md orchestrator to surface "OpenAI reviewer was skipped — check the log" to the running agent or user. A developer running a Deep-path feature review may not notice that multi-model diversity silently collapsed to Claude-only for all three stages.

This is distinct from the general "opt-in is acceptable" design decision. The design accepts that users without a key get no OpenAI review. The new threat is that a user who expects OpenAI review (key is set, flag is set) cannot distinguish "reviewer skipped due to broken key" from "reviewer skipped due to flag unset" from "reviewer silently suppressed by attacker." The log is the only signal and the design does not mandate its inspection.

**Impact:** Reduced multi-model review coverage without operator awareness. In a high-stakes feature deployment, this could mean an adversarial diff passes review with fewer independent eyes.

**Suggested fix:** When a reviewer was expected (both flag and key were set) but produced status=skipped, the SKILL.md orchestrator should emit a warning to the active conversation: "Warning: openai reviewer was expected but returned status=skipped. Check ~/.cache/tlmforge/llm_reviewer.log." This surfaces the skip as a visible anomaly rather than silent absence. The distinction between "never configured" and "configured but failed" is the key signal to preserve.

---

### NEW-2 — Risk table LOW-1 row documents wrong behavior post-user-requirement
**Severity: nit**
**Category: architecture**

The risk audit table LOW row says: "Results in status=error instead of status=skipped; correct graceful behavior." After the user requirement change, status=error from a TOCTOU auth failure is NOT the correct graceful behavior — it is a policy violation. The table entry creates a false expectation for implementers.

**Suggested fix:** Update the LOW row to: "Results in status=skipped (per new all-failures-skip policy); failure reason logged. Correct graceful behavior."

---

## Summary

| Finding | Round-1 Severity | Verdict |
|---|---|---|
| CRITICAL-1 | critical | FIXED |
| CRITICAL-2 | critical | FIXED |
| HIGH-1 | high | FIXED |
| HIGH-2 | high | FIXED |
| MEDIUM-1 | medium | PARTIALLY |
| MEDIUM-2 | medium | NOT_FIXED (deferred, defensible) |
| LOW-1 | low | PARTIALLY (stale doc) |
| LOW-2 | low | NOT_FIXED (false rationale added) |

New findings: 1 × medium (NEW-1), 1 × nit (NEW-2).

No CRITICAL findings remain. The plan may proceed. The medium (NEW-1) is a design-time fix opportunity — adding one warning emission line to the SKILL.md orchestration template costs nothing at implementation time and should be added to Phase 3.
