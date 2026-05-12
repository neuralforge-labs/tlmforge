"""Characterization tests for check_convergence.py (Phase 0).

These tests pin the EXISTING behavior of evaluate_convergence and
evaluate_stage5_two_tier as of commit 1651332. They are GREEN by definition
against unmodified check_convergence.py.

Future phases:
- Phase 1: adds defensive loader + action enum. New tests; characterization
  tests must continue to pass (no regressions on existing behavior).
- Phase 3: removes evaluate_stage5_two_tier. The 6 characterization tests
  for that function are deleted alongside the removal in the same commit.

Each test docstring states which branch / behavior is pinned, so a future
change that breaks the test produces a meaningful failure message.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add the skill dir to sys.path so we can import check_convergence as a module
SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

from check_convergence import (  # noqa: E402
    evaluate_convergence,
    evaluate_stage5_two_tier,
)


# ============================================================================
# evaluate_convergence — happy paths
# ============================================================================

def test_evaluate_convergence_all_approve():
    """Pin: 3 reviewers all approve with no findings -> converged=True."""
    reviewer_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
        "tester": {"reviewer": "tester", "status": "ok", "verdict": "approve", "findings": []},
        "threat-modeler": {"reviewer": "threat-modeler", "status": "ok", "verdict": "approve", "findings": []},
    }
    result = evaluate_convergence(
        reviewer_jsons,
        expected_roles=["architect-reviewer", "tester", "threat-modeler"],
        iteration=1,
    )
    assert result["converged"] is True
    assert result["real_critical_count"] == 0
    assert result["meta_critical_count"] == 0


def test_evaluate_convergence_skipped_reviewer():
    """Pin: reviewer with status=skipped is excluded from critical counting."""
    reviewer_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
        "gemini": {"reviewer": "gemini", "status": "skipped", "verdict": "approve", "findings": []},
    }
    result = evaluate_convergence(
        reviewer_jsons,
        expected_roles=["architect-reviewer", "gemini"],
        iteration=1,
    )
    assert result["converged"] is True
    assert any("gemini" in w and "skipped" in w for w in result["warnings"])  # skipped warning surfaced


# ============================================================================
# evaluate_convergence — synthetic missing-JSON injection
# ============================================================================

def test_evaluate_convergence_missing_json():
    """Pin: expected reviewer absent from input -> synthetic reviewer_json_missing meta CRITICAL."""
    reviewer_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
        # tester intentionally missing
    }
    result = evaluate_convergence(
        reviewer_jsons,
        expected_roles=["architect-reviewer", "tester"],
        iteration=1,
    )
    assert result["converged"] is False
    assert result["meta_critical_count"] == 1
    assert result["real_critical_count"] == 0
    # The synthetic finding describes the missing reviewer
    findings = result["findings_by_role"]["tester"]["findings"]
    assert any("reviewer_json_missing" in f["finding"] for f in findings)


# ============================================================================
# evaluate_convergence — real vs meta CRITICAL distinction
# ============================================================================

def test_evaluate_convergence_real_critical():
    """Pin: real (non-meta) CRITICAL counted in real_critical_count, blocks convergence."""
    reviewer_jsons = {
        "architect-reviewer": {
            "reviewer": "architect-reviewer", "status": "ok", "verdict": "needs_revision",
            "findings": [
                {"severity": "critical", "category": "security", "file": "x.py", "line": 10,
                 "finding": "real critical bug", "suggested_fix": "fix it"}
            ],
        },
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["architect-reviewer"], iteration=1)
    assert result["converged"] is False
    assert result["real_critical_count"] == 1
    assert result["meta_critical_count"] == 0


def test_evaluate_convergence_meta_critical():
    """Pin: synthetic meta CRITICAL counted in meta_critical_count, blocks convergence."""
    reviewer_jsons = {
        "gemini": {
            "reviewer": "gemini", "status": "error", "verdict": "needs_revision",
            "findings": [
                {"severity": "critical", "category": "meta", "file": "architecture", "line": None,
                 "finding": "gemini_unavailable", "suggested_fix": "fix gemini wiring"}
            ],
        },
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["gemini"], iteration=1)
    assert result["converged"] is False
    assert result["real_critical_count"] == 0
    assert result["meta_critical_count"] == 1


# ============================================================================
# evaluate_convergence — lazy-empty findings (RES-1)
# ============================================================================

def test_evaluate_convergence_lazy_empty_blocking_verdict():
    """Pin: verdict=needs_revision with empty findings -> synthetic reviewer_verdict_findings_mismatch."""
    reviewer_jsons = {
        "tester": {"reviewer": "tester", "status": "ok", "verdict": "needs_revision", "findings": []},
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["tester"], iteration=1)
    assert result["converged"] is False
    assert result["meta_critical_count"] == 1
    findings = result["findings_by_role"]["tester"]["findings"]
    assert any("reviewer_verdict_findings_mismatch" in f["finding"] for f in findings)


def test_evaluate_convergence_lazy_empty_approve_verdict():
    """Pin: verdict=approve with empty findings -> warning but converges (does NOT block)."""
    reviewer_jsons = {
        "tester": {"reviewer": "tester", "status": "ok", "verdict": "approve", "findings": []},
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["tester"], iteration=1)
    assert result["converged"] is True
    assert any("possible review skip" in w for w in result["warnings"])


# ============================================================================
# evaluate_convergence — cap-hit branches
# ============================================================================

def test_evaluate_convergence_cap_hit_real_only():
    """Pin: iteration > max + real CRITICAL -> cap_hit message names persistent reals."""
    reviewer_jsons = {
        "architect-reviewer": {
            "reviewer": "architect-reviewer", "status": "ok", "verdict": "needs_revision",
            "findings": [
                {"severity": "critical", "category": "security", "file": "x.py", "line": 10,
                 "finding": "persistent real critical", "suggested_fix": "fix it"}
            ],
        },
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["architect-reviewer"], iteration=4, max_iterations=3)
    assert result["cap_hit"] is True
    assert result["converged"] is False
    assert "persistent real critical" in result["user_message"]


def test_evaluate_convergence_cap_hit_meta_only():
    """Pin: iteration > max + only meta CRITICAL -> message cites wiring/missing-reviewer concern."""
    reviewer_jsons = {
        # missing tester -> synthetic meta CRITICAL
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["tester"], iteration=4, max_iterations=3)
    assert result["cap_hit"] is True
    assert "wiring" in result["user_message"].lower() or "missing" in result["user_message"].lower()


def test_evaluate_convergence_cap_hit_both():
    """Pin: iteration > max + both real AND meta CRITICAL -> message lists both, suggests fixing real first."""
    reviewer_jsons = {
        "architect-reviewer": {
            "reviewer": "architect-reviewer", "status": "ok", "verdict": "needs_revision",
            "findings": [
                {"severity": "critical", "category": "security", "file": "x.py", "line": 10,
                 "finding": "real bug", "suggested_fix": "fix"}
            ],
        },
        # tester missing -> meta CRITICAL
    }
    result = evaluate_convergence(reviewer_jsons,
                                  expected_roles=["architect-reviewer", "tester"],
                                  iteration=4, max_iterations=3)
    assert result["cap_hit"] is True
    assert result["real_critical_count"] == 1
    assert result["meta_critical_count"] == 1


# ============================================================================
# Boundary pins for R1-A1/T2 cap-check asymmetry
# ============================================================================

def test_cap_hit_iteration_eq_max_in_evaluate_convergence():
    """Pin (R1-A1/T2 boundary): iteration=3, max=3 -> cap_hit=False ('>' semantic).

    evaluate_convergence uses `iteration > max_iterations` at line 135.
    At iteration==max, cap is NOT hit. Compare with two_tier below.
    """
    reviewer_jsons = {
        "tester": {"reviewer": "tester", "status": "ok", "verdict": "approve", "findings": []},
    }
    result = evaluate_convergence(reviewer_jsons, expected_roles=["tester"], iteration=3, max_iterations=3)
    assert result["cap_hit"] is False  # iteration > max is False since 3 > 3 is False
    assert result["converged"] is True


def test_cap_hit_iteration_eq_max_in_two_tier():
    """Pin (R1-A1/T2 boundary): iteration=3, max=3 -> cap_hit=True ('>=' semantic in two_tier).

    evaluate_stage5_two_tier uses `iteration >= max_iterations` at line 364.
    At iteration==max, cap IS hit. Asymmetry vs evaluate_convergence pinned here.
    Phase 3 resolves this by removing evaluate_stage5_two_tier entirely.
    """
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    # tier-1 converged + tier-2 CRITICAL at iteration=max -> the >= comparison triggers cap_hit
    tier2 = {
        "reviewer": "red-team-reviewer", "status": "ok", "verdict": "needs_revision",
        "findings": [{"severity": "critical", "category": "security", "file": "x.py", "line": 5,
                      "finding": "red team found bug", "suggested_fix": "fix"}],
    }
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=tier2, iteration=3, max_iterations=3)
    assert result["cap_hit"] is True  # iteration >= max is True since 3 >= 3 is True


# ============================================================================
# evaluate_stage5_two_tier — will be REMOVED in Phase 3
# ============================================================================

def test_evaluate_stage5_two_tier_tier1_not_converged():
    """Pin: tier-1 has CRITICAL -> tier-2 not processed; awaiting_tier2 False."""
    tier1_jsons = {
        "architect-reviewer": {
            "reviewer": "architect-reviewer", "status": "ok", "verdict": "needs_revision",
            "findings": [{"severity": "critical", "category": "security", "file": "x.py", "line": 5,
                          "finding": "bug", "suggested_fix": "fix"}],
        },
    }
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=None, iteration=1, max_iterations=3)
    assert result["tier1_converged"] is False
    assert result["awaiting_tier2"] is False  # not processed; awaiting flag stays False


def test_evaluate_stage5_two_tier_tier1_converged_no_tier2():
    """Pin: tier-1 OK + tier2 None -> awaiting_tier2=True."""
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=None, iteration=1, max_iterations=3)
    assert result["tier1_converged"] is True
    assert result["awaiting_tier2"] is True
    assert result["final_converged"] is False


def test_evaluate_stage5_two_tier_tier2_skipped():
    """Pin: tier-1 OK + tier2 status=skipped -> tier2_skipped=True, awaiting_tier2=True."""
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    tier2 = {"reviewer": "red-team-reviewer", "status": "skipped", "verdict": "approve", "findings": []}
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=tier2, iteration=1, max_iterations=3)
    assert result["tier2_skipped"] is True
    assert result["awaiting_tier2"] is True


def test_evaluate_stage5_two_tier_both_converged():
    """Pin: tier-1 OK + tier-2 OK -> final_converged=True."""
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    tier2 = {"reviewer": "red-team-reviewer", "status": "ok", "verdict": "approve", "findings": []}
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=tier2, iteration=1, max_iterations=3)
    assert result["final_converged"] is True


def test_evaluate_stage5_two_tier_tier2_critical_below_cap():
    """Pin: tier-1 OK + tier-2 CRITICAL + iteration < max -> restart message names remaining iterations."""
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    tier2 = {
        "reviewer": "red-team-reviewer", "status": "ok", "verdict": "needs_revision",
        "findings": [{"severity": "critical", "category": "security", "file": "x.py", "line": 5,
                      "finding": "red team found bug", "suggested_fix": "fix"}],
    }
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=tier2, iteration=1, max_iterations=3)
    assert result["final_converged"] is False
    assert result["tier2_real_critical"] == 1
    assert "iteration" in result["user_message"].lower()


def test_evaluate_stage5_two_tier_tier2_critical_at_cap():
    """Pin: tier-1 OK + tier-2 CRITICAL at iteration=max -> requires_user_override=True."""
    tier1_jsons = {
        "architect-reviewer": {"reviewer": "architect-reviewer", "status": "ok", "verdict": "approve", "findings": []},
    }
    tier2 = {
        "reviewer": "red-team-reviewer", "status": "ok", "verdict": "needs_revision",
        "findings": [{"severity": "critical", "category": "security", "file": "x.py", "line": 5,
                      "finding": "red team found bug", "suggested_fix": "fix"}],
    }
    result = evaluate_stage5_two_tier(tier1_jsons, tier2_red_team_json=tier2, iteration=3, max_iterations=3)
    assert result["requires_user_override"] is True
    assert result["cap_hit"] is True
