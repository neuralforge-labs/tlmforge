"""Mechanical convergence rule for Stage 3 / Stage 5 multi-agent review.

Single source of truth for the rule described in `reviewer-convergence.md`.
SKILL.md cites this file; tests import from it.

Convergence reached when, for the current iteration:
  - real_critical_count == 0  (per-finding severity=critical with category != "meta")
  - meta_critical_count == 0  (synthetic meta criticals — gemini_unavailable, reviewer_json_missing, etc.)
  - iteration <= max_iterations (default 3)

Reviewers with status="skipped" are excluded from counting (e.g., Gemini absent).
Missing JSON files trigger a synthetic `reviewer_json_missing` meta CRITICAL.
Lazy-empty reviews (verdict=needs_revision/do_not_ship + findings=[]) trigger
`reviewer_verdict_findings_mismatch` synthetic meta CRITICAL.
"""
from __future__ import annotations

from typing import Optional


META_CATEGORY = "meta"
SKIPPED = "skipped"
ERROR = "error"
OK = "ok"

BLOCKING_VERDICTS = {"needs_revision", "do_not_ship"}


def _synthetic_meta_critical(finding: str, suggested_fix: Optional[str] = None) -> dict:
    return {
        "severity": "critical",
        "category": META_CATEGORY,
        "file": "architecture",
        "line": None,
        "finding": finding,
        "suggested_fix": suggested_fix or "Investigate and fix the meta failure mode.",
    }


def _build_synthetic_review(role: str, iteration: int, finding: str, fix: Optional[str] = None) -> dict:
    return {
        "reviewer": role,
        "schema_version": "1.0",
        "iteration": iteration,
        "status": ERROR,
        "verdict": "needs_revision",
        "findings": [_synthetic_meta_critical(finding, fix)],
    }


def evaluate_convergence(
    reviewer_jsons: dict,
    expected_roles: list,
    iteration: int,
    max_iterations: int = 3,
) -> dict:
    """Compute convergence state for a single iteration's reviewer outputs.

    Args:
        reviewer_jsons: dict mapping role name → review JSON dict (or None if missing)
        expected_roles: list of role names that should have produced reviews
        iteration: current iteration counter (1-indexed)
        max_iterations: cap (default 3)

    Returns:
        dict with:
          - converged: bool
          - real_critical_count: int
          - meta_critical_count: int
          - findings_by_role: dict[role, review-dict]  (synthetic injections included)
          - user_message: str
          - iteration: int
          - cap_hit: bool
          - warnings: list[str]
    """
    findings_by_role: dict = {}
    warnings: list = []

    for role in expected_roles:
        review = reviewer_jsons.get(role)

        if review is None:
            # Missing JSON — Cat 2: never silent fallback, inject synthetic
            findings_by_role[role] = _build_synthetic_review(
                role,
                iteration,
                f"reviewer_json_missing — no JSON sidecar for {role} at iteration {iteration}",
                f"Re-launch {role} with explicit JSON-output instructions.",
            )
            continue

        status = review.get("status", OK)
        if status == SKIPPED:
            # Excluded from counting; log to warnings
            warnings.append(f"{role}: skipped (status=skipped, e.g. Gemini key absent)")
            findings_by_role[role] = review
            continue

        # Lazy-empty handling (RES-1)
        verdict = review.get("verdict", "approve")
        findings = review.get("findings", [])
        if not findings:
            if verdict in BLOCKING_VERDICTS:
                # Verdict says block but no findings → malformed
                synthetic = _build_synthetic_review(
                    role,
                    iteration,
                    f"reviewer_verdict_findings_mismatch — {role} emitted verdict={verdict} but no findings",
                    f"Re-launch {role} and require explicit findings to back the verdict.",
                )
                findings_by_role[role] = synthetic
                continue
            else:
                # verdict=approve + empty findings → log warning but allow
                warnings.append(
                    f"{role}: verdict=approve with empty findings (possible review skip — verify human review)"
                )

        findings_by_role[role] = review

    # Count real vs meta CRITICALs across all reviewers (skipped excluded)
    real_critical_count = 0
    meta_critical_count = 0
    for role, review in findings_by_role.items():
        status = review.get("status", OK)
        if status == SKIPPED:
            continue
        for f in review.get("findings", []):
            if f.get("severity") == "critical":
                if f.get("category") == META_CATEGORY:
                    meta_critical_count += 1
                else:
                    real_critical_count += 1

    cap_hit = iteration > max_iterations
    converged = (
        real_critical_count == 0
        and meta_critical_count == 0
        and not cap_hit
    )

    user_message = _render_user_message(
        iteration=iteration,
        max_iterations=max_iterations,
        real_critical_count=real_critical_count,
        meta_critical_count=meta_critical_count,
        cap_hit=cap_hit,
        converged=converged,
        findings_by_role=findings_by_role,
        warnings=warnings,
    )

    return {
        "converged": converged,
        "real_critical_count": real_critical_count,
        "meta_critical_count": meta_critical_count,
        "findings_by_role": findings_by_role,
        "user_message": user_message,
        "iteration": iteration,
        "cap_hit": cap_hit,
        "warnings": warnings,
    }


def _render_user_message(
    iteration: int,
    max_iterations: int,
    real_critical_count: int,
    meta_critical_count: int,
    cap_hit: bool,
    converged: bool,
    findings_by_role: dict,
    warnings: list,
) -> str:
    if converged:
        return (
            f"Convergence reached at iteration {iteration} of {max_iterations}. "
            f"0 real CRITICAL, 0 meta CRITICAL across present reviewers. "
            + (f"Warnings: {'; '.join(warnings)}." if warnings else "")
        )

    # Helper: gather persistent CRITICAL findings for the message
    persistent_real = []
    persistent_meta = []
    for role, review in findings_by_role.items():
        for f in review.get("findings", []):
            if f.get("severity") != "critical":
                continue
            entry = f"{role}: {f.get('finding', '?')}"
            if f.get("category") == META_CATEGORY:
                persistent_meta.append(entry)
            else:
                persistent_real.append(entry)

    if cap_hit:
        # Distinguish 4 cases per reviewer-convergence.md §3
        if real_critical_count > 0 and meta_critical_count == 0:
            body = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"{real_critical_count} real CRITICAL persists across all 3 iterations:\n"
                + "\n".join(f"  - {p}" for p in persistent_real)
                + f"\nNext: address the findings above and request another review iteration."
            )
        elif real_critical_count == 0 and meta_critical_count > 0:
            body = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"0 real CRITICALs in {max_iterations} iterations, but {meta_critical_count} "
                f"meta CRITICAL(s) — Gemini wiring is broken or a reviewer JSON went missing:\n"
                + "\n".join(f"  - {p}" for p in persistent_meta)
                + "\nNext: (a) fix the wiring/missing-reviewer issue, (b) accept 3-reviewer "
                "convergence (lose diversity guarantee), or (c) abort."
            )
        elif real_critical_count > 0 and meta_critical_count > 0:
            body = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"Real CRITICALs persist AND wiring is broken.\n"
                f"Real CRITICALs ({real_critical_count}):\n"
                + "\n".join(f"  - {p}" for p in persistent_real)
                + f"\nMeta CRITICALs ({meta_critical_count}):\n"
                + "\n".join(f"  - {p}" for p in persistent_meta)
                + "\nNext: address the real findings first, then re-launch with the wrapper repaired."
            )
        else:
            body = "Convergence cap hit but no CRITICAL findings — anomalous state, investigate."
        if warnings:
            body += f"\nWarnings: {'; '.join(warnings)}."
        return body

    # Not capped, not converged — mid-loop status
    return (
        f"Iteration {iteration} of {max_iterations}: not converged. "
        f"{real_critical_count} real CRITICAL, {meta_critical_count} meta CRITICAL."
    )


# ============================================================================
# Stage 5 two-tier convergence (Phase 3c, gap H follow-through)
# ============================================================================

def evaluate_stage5_two_tier(
    tier1_jsons: dict,
    tier2_red_team_json: Optional[dict],
    iteration: int,
    max_iterations: int = 3,
) -> dict:
    """Two-tier Stage 5 convergence.

    Tier-1: existing trio (architect-reviewer + code-reviewer + tester) plus
    optional Gemini wrapper output. Iterates up to `max_iterations` rounds.

    Tier-2: red-team-reviewer fires once per feature, only AFTER tier-1
    converges (real_critical_count == 0 AND meta_critical_count == 0). If
    tier-2 finds CRITICAL, tier-1 must restart with the new findings folded
    in — but red-team calls do NOT consume the iteration counter (cap remains
    `max_iterations` tier-1 iterations total).

    The "iteration 3.5" case (tier-1 converged at iteration == max_iterations,
    tier-2 found CRITICAL): cap is hit; `requires_user_override` is True.
    The user must explicitly accept the gap or restart with iteration counter
    reset.

    Tier-2 status handling:
        - status="ok" with 0 critical → final_converged
        - status="ok" with 1+ real critical → restart tier-1
        - status="error" with synthetic meta critical → restart tier-1
        - status="skipped" → awaiting tier-2 (red-team agent declined; not
          a clean tier-2 — caller should decide whether to re-launch or
          accept the diversity gap)
        - tier2 is None → tier-2 not yet launched

    Returns:
        {
            'tier1_converged': bool,
            'final_converged': bool,
            'tier1_real_critical': int,
            'tier1_meta_critical': int,
            'tier2_real_critical': int,
            'tier2_meta_critical': int,
            'awaiting_tier2': bool,         # True if tier-2 not yet launched
            'tier2_skipped': bool,          # True if tier-2 status='skipped'
            'cap_hit': bool,
            'requires_user_override': bool, # True iff cap_hit AND tier-2 has unresolved CRITICAL
            'iteration': int,
            'user_message': str,
        }
    """
    expected_tier1_roles = list(tier1_jsons.keys())
    tier1_result = evaluate_convergence(
        reviewer_jsons=tier1_jsons,
        expected_roles=expected_tier1_roles,
        iteration=iteration,
        max_iterations=max_iterations,
    )

    out = {
        "tier1_converged": tier1_result["converged"],
        "final_converged": False,
        "tier1_real_critical": tier1_result["real_critical_count"],
        "tier1_meta_critical": tier1_result["meta_critical_count"],
        "tier2_real_critical": 0,
        "tier2_meta_critical": 0,
        "awaiting_tier2": False,
        "tier2_skipped": False,
        "cap_hit": tier1_result["cap_hit"],
        "requires_user_override": False,
        "iteration": iteration,
        "user_message": "",
    }

    if not tier1_result["converged"]:
        # Don't process tier-2 until tier-1 settles.
        out["user_message"] = (
            f"Tier-1 not converged at iteration {iteration}: "
            f"{tier1_result['real_critical_count']} real CRITICAL, "
            f"{tier1_result['meta_critical_count']} meta CRITICAL. "
            f"Tier-2 (red-team) will not fire until tier-1 reaches 0 CRITICAL."
        )
        return out

    # Tier-1 converged. Process tier-2.
    if tier2_red_team_json is None:
        out["awaiting_tier2"] = True
        out["user_message"] = (
            "Tier-1 converged. Awaiting tier-2 launch (red-team-reviewer)."
        )
        return out

    tier2_status = tier2_red_team_json.get("status", OK)

    if tier2_status == SKIPPED:
        out["tier2_skipped"] = True
        out["awaiting_tier2"] = True  # caller should decide
        out["user_message"] = (
            "Tier-1 converged but red-team-reviewer status='skipped' — "
            "adversarial gate not validated. Re-launch red-team OR accept "
            "diversity gap with explicit user override."
        )
        return out

    # tier-2 status is "ok" or "error" — count its CRITICALs.
    tier2_real = 0
    tier2_meta = 0
    for f in tier2_red_team_json.get("findings", []):
        if f.get("severity") == "critical":
            if f.get("category") == META_CATEGORY:
                tier2_meta += 1
            else:
                tier2_real += 1

    out["tier2_real_critical"] = tier2_real
    out["tier2_meta_critical"] = tier2_meta

    # Decide convergence.
    if tier2_real == 0 and tier2_meta == 0:
        out["final_converged"] = True
        out["user_message"] = (
            f"Tier-1 + tier-2 converged at iteration {iteration}. "
            f"0 real CRITICAL, 0 meta CRITICAL across all reviewers including "
            f"red-team-reviewer."
        )
        return out

    # Tier-2 found CRITICAL — tier-1 must restart unless cap reached.
    if iteration >= max_iterations:
        # Cap-hit branch: tier-1 already used max_iterations. Red-team's
        # finding can't be folded back without exceeding the cap budget.
        # Per Phase 2 Cat 1: requires explicit user override.
        out["cap_hit"] = True
        out["requires_user_override"] = True
        if tier2_real > 0 and tier2_meta == 0:
            out["user_message"] = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"Tier-1 trio converged, but red-team-reviewer found "
                f"{tier2_real} real CRITICAL on the converged diff. "
                f"User override required to ship — accept the gap, or "
                f"reset the iteration counter and restart tier-1 with "
                f"red-team's findings folded in."
            )
        elif tier2_meta > 0 and tier2_real == 0:
            out["user_message"] = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"Tier-1 converged but red-team-reviewer is unavailable "
                f"({tier2_meta} meta CRITICAL). Adversarial review wasn't "
                f"performed. User override: ship without adversarial gate, "
                f"or fix red-team wiring and re-launch."
            )
        else:
            out["user_message"] = (
                f"Convergence cap hit at iteration {max_iterations}. "
                f"Tier-1 converged but red-team has {tier2_real} real + "
                f"{tier2_meta} meta CRITICAL. User override required."
            )
        return out

    # Tier-2 found CRITICAL, iteration not yet at cap → restart tier-1.
    out["user_message"] = (
        f"Tier-1 converged at iteration {iteration}, but red-team-reviewer "
        f"found {tier2_real} real + {tier2_meta} meta CRITICAL. Restart "
        f"tier-1 with red-team's findings folded in (red-team calls do not "
        f"consume the iteration counter; tier-1 has "
        f"{max_iterations - iteration} iteration(s) remaining)."
    )
    return out
