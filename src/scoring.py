"""
Deterministic scoring for AI use cases
Value, feasibility and adoption readiness scores, portfolio quadrant and decision gate
"""

from typing import Dict, List, Any
from src.roi import calculate_roi, potential_annual_hours
from src.governance import assess_governance


QUADRANT_THRESHOLD = 50
HOURS_FOR_MAX_VALUE = 4000  # ~2 FTE of potential savings earns the full hours component

SENSITIVITY_PENALTY = {"Public": 0, "Internal": 0, "Confidential": 5, "Personal data": 10}


def _scale(value: Any, max_points: float, low: int = 1, high: int = 5) -> float:
    """Map a 1-5 rating onto 0..max_points"""
    v = min(max(int(value or low), low), high)
    return (v - low) / (high - low) * max_points


def _clamp(score: float) -> int:
    return int(round(min(max(score, 0), 100)))


def value_score(uc: Dict[str, Any]) -> int:
    """Hours saved (40) + strategic alignment (30) + customer/quality impact (30)"""
    hours_points = min(potential_annual_hours(uc) / HOURS_FOR_MAX_VALUE, 1.0) * 40
    return _clamp(
        hours_points
        + _scale(uc.get("strategic_alignment"), 30)
        + _scale(uc.get("customer_impact"), 30)
    )


def feasibility_score(uc: Dict[str, Any]) -> int:
    """Data quality (30) + low integration complexity (25) + skills (25) + solution maturity (20) - sensitivity penalty"""
    integration_ease = 6 - int(uc.get("integration_complexity", 3) or 3)
    score = (
        _scale(uc.get("data_quality"), 30)
        + _scale(integration_ease, 25)
        + _scale(uc.get("inhouse_skills"), 25)
        + _scale(uc.get("solution_maturity"), 20)
        - SENSITIVITY_PENALTY.get(uc.get("data_sensitivity", "Internal"), 0)
    )
    return _clamp(score)


def adoption_readiness_score(uc: Dict[str, Any]) -> int:
    """Sponsor (25) + standardized process (25) + training (20) + champions (15) + user involvement (15)"""
    score = (
        (25 if uc.get("sponsor_committed") else 0)
        + (25 if uc.get("process_standardized") else 0)
        + (20 if uc.get("has_training_plan") else 0)
        + (15 if uc.get("has_champions") else 0)
        + _scale(uc.get("user_involvement"), 15)
    )
    return _clamp(score)


def quadrant(value: int, feasibility: int) -> str:
    high_value = value >= QUADRANT_THRESHOLD
    high_feasibility = feasibility >= QUADRANT_THRESHOLD
    if high_value and high_feasibility:
        return "Quick Win"
    if high_value:
        return "Strategic Bet"
    if high_feasibility:
        return "Fill-in"
    return "Avoid"


def decision_gate(
    uc: Dict[str, Any],
    scores: Dict[str, int],
    roi: Dict[str, Dict[str, Any]],
    governance: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Go / Pilot with conditions / Fix process first / Stop
    Rules are applied in order of severity; conditions accumulate for pilots.
    """
    tier = governance["tier"]
    conservative = roi["Conservative"]
    expected = roi["Expected"]

    if tier == "Unacceptable":
        return {"gate": "Stop", "reasons": ["Matches a prohibited AI practice."], "conditions": []}
    if expected["net_3yr"] < 0:
        return {
            "gate": "Stop",
            "reasons": ["No value case: even the Expected scenario loses money over 3 years."],
            "conditions": [],
        }
    critical_flags = [f["flag"] for f in governance["flags"] if f["severity"] == "Critical"]

    if not uc.get("process_standardized"):
        return {
            "gate": "Fix process first",
            "reasons": ["The process is not standardized. Simplify and standardize it before adding AI, "
                        "otherwise AI scales today's waste and inconsistency."],
            "conditions": ["Map and standardize the current process (see AI Workflow Waste Detector).",
                           *critical_flags,
                           "Re-assess once the standard work is in place."],
        }

    conditions: List[str] = []
    if tier == "High":
        conditions.append("Complete all High-tier governance controls before go-live.")
    conditions += critical_flags
    if scores["feasibility"] < QUADRANT_THRESHOLD:
        conditions.append("Close feasibility gaps (data quality, integration, skills) during the pilot.")
    if scores["adoption_readiness"] < 60:
        conditions.append("Secure sponsor commitment, a training plan and user champions before scaling.")
    if conservative["net_3yr"] < 0:
        conditions.append("Value is only positive in Expected/Optimistic scenarios - prove adoption in the pilot.")

    if conditions:
        return {
            "gate": "Pilot with conditions",
            "reasons": ["Value case exists, but conditions must be met before scaling."],
            "conditions": conditions,
        }
    return {
        "gate": "Go",
        "reasons": ["Positive value in the Conservative scenario, feasible, governed and ready for adoption."],
        "conditions": [],
    }


def workforce_impact(uc: Dict[str, Any], roi: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Classify the impact on affected roles based on how much task time AI removes"""
    reduction = float(uc.get("time_reduction_pct", 0) or 0)
    if reduction < 30:
        category = "Augment"
        meaning = "AI assists; the role stays largely the same with less routine work."
    elif reduction <= 60:
        category = "Redesign"
        meaning = "Tasks within the role shift toward review, exceptions and higher-value work."
    else:
        category = "Redeploy & reskill"
        meaning = ("A large share of task time is freed. Plan where the freed capacity goes "
                   "(growth work, backlog, new services) before go-live - not after.")

    roles = [r.strip() for r in str(uc.get("roles_affected", "")).split(",") if r.strip()]
    return {
        "category": category,
        "meaning": meaning,
        "roles": roles,
        "people_involved": int(uc.get("people_involved", 0) or 0),
        "capacity_freed_fte": roi["Expected"]["fte_equivalent"],
    }


def assess_use_case(uc: Dict[str, Any]) -> Dict[str, Any]:
    """Run all deterministic scoring for one use case"""
    scores = {
        "value": value_score(uc),
        "feasibility": feasibility_score(uc),
        "adoption_readiness": adoption_readiness_score(uc),
    }
    roi = calculate_roi(uc)
    governance = assess_governance(uc)
    return {
        "scores": scores,
        "quadrant": quadrant(scores["value"], scores["feasibility"]),
        "roi": roi,
        "governance": governance,
        "gate": decision_gate(uc, scores, roi, governance),
        "workforce": workforce_impact(uc, roi),
    }
