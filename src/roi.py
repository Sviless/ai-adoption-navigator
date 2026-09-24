"""
ROI calculations for AI use cases
Deterministic math only - the LLM never changes these numbers
"""

from typing import Dict, List, Any, Optional


HOURS_PER_FTE_YEAR = 1800

# Adoption = share of users who actually use the tool
# Realization = share of theoretical time savings that turns into real capacity
SCENARIOS: Dict[str, Dict[str, float]] = {
    "Conservative": {"adoption": 0.50, "realization": 0.60},
    "Expected": {"adoption": 0.70, "realization": 0.80},
    "Optimistic": {"adoption": 0.90, "realization": 1.00},
}


def potential_annual_hours(uc: Dict[str, Any]) -> float:
    """Theoretical annual hours saved if every task used AI at the stated time reduction"""
    tasks_per_year = float(uc.get("tasks_per_month", 0) or 0) * 12
    hours_per_task = float(uc.get("minutes_per_task", 0) or 0) / 60
    reduction = float(uc.get("time_reduction_pct", 0) or 0) / 100
    return tasks_per_year * hours_per_task * reduction


def annual_running_cost(uc: Dict[str, Any]) -> float:
    return float(uc.get("license_cost_annual", 0) or 0) + float(uc.get("run_cost_annual", 0) or 0)


def calculate_scenario(uc: Dict[str, Any], adoption: float, realization: float) -> Dict[str, Any]:
    """Calculate one ROI scenario"""
    hours = potential_annual_hours(uc) * adoption * realization
    hourly_cost = float(uc.get("hourly_cost", 0) or 0)
    benefit = hours * hourly_cost
    running = annual_running_cost(uc)
    implementation = float(uc.get("implementation_cost", 0) or 0)

    net_year1 = benefit - running - implementation
    net_3yr = 3 * benefit - 3 * running - implementation
    total_cost_3yr = implementation + 3 * running
    roi_3yr_pct = (net_3yr / total_cost_3yr * 100) if total_cost_3yr > 0 else None

    monthly_net = (benefit - running) / 12
    payback_months: Optional[float]
    if monthly_net <= 0:
        payback_months = None
    elif implementation <= 0:
        payback_months = 0.0
    else:
        payback_months = implementation / monthly_net

    return {
        "adoption": adoption,
        "realization": realization,
        "annual_hours_saved": hours,
        "fte_equivalent": hours / HOURS_PER_FTE_YEAR,
        "annual_benefit": benefit,
        "annual_running_cost": running,
        "implementation_cost": implementation,
        "net_year1": net_year1,
        "net_3yr": net_3yr,
        "roi_3yr_pct": roi_3yr_pct,
        "payback_months": payback_months,
    }


def calculate_roi(uc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Calculate all three ROI scenarios"""
    return {
        name: calculate_scenario(uc, s["adoption"], s["realization"])
        for name, s in SCENARIOS.items()
    }


def cumulative_cash_flow(roi: Dict[str, Dict[str, Any]], months_ahead: int = 36) -> List[Dict[str, Any]]:
    """Month-by-month cumulative net value per scenario (implementation cost paid in month 0)"""
    rows = []
    for name, s in roi.items():
        monthly_net = (s["annual_benefit"] - s["annual_running_cost"]) / 12
        for month in range(months_ahead + 1):
            rows.append({"Scenario": name, "Month": month,
                         "Cumulative net value": -s["implementation_cost"] + monthly_net * month})
    return rows


def total_task_hours(uc: Dict[str, Any]) -> float:
    """Annual hours spent on the task today, before AI"""
    return float(uc.get("tasks_per_month", 0) or 0) * 12 * float(uc.get("minutes_per_task", 0) or 0) / 60


def realization_summary(uc: Dict[str, Any], actuals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare promised (Expected scenario) vs realized value from monthly actuals

    Status thresholds (share of promised hours realized):
    >= 90% On track | 70-90% Watch | 40-70% Value leakage | < 40% Critical leakage
    """
    expected = calculate_scenario(uc, **_scenario_args("Expected"))
    promised_monthly_hours = expected["annual_hours_saved"] / 12
    hourly_cost = float(uc.get("hourly_cost", 0) or 0)
    months = len(actuals)

    actual_hours = sum(float(a.get("hours_saved", 0) or 0) for a in actuals)
    actual_cost = sum(float(a.get("actual_cost", 0) or 0) for a in actuals)
    promised_hours = promised_monthly_hours * months
    realization_pct = (actual_hours / promised_hours * 100) if promised_hours > 0 else 0.0

    realized_value = actual_hours * hourly_cost - actual_cost
    promised_value = promised_hours * hourly_cost - (annual_running_cost(uc) / 12) * months

    if months < 2:
        status = "Too early"
    elif realization_pct >= 90:
        status = "On track"
    elif realization_pct >= 70:
        status = "Watch"
    elif realization_pct >= 40:
        status = "Value leakage"
    else:
        status = "Critical leakage"

    adoption_values = [float(a.get("adoption_pct", 0) or 0) for a in actuals]
    if len(adoption_values) >= 2:
        delta = adoption_values[-1] - adoption_values[0]
        adoption_trend = "Rising" if delta > 5 else "Falling" if delta < -5 else "Flat"
    else:
        adoption_trend = "Not enough data"

    return {
        "months_tracked": months,
        "promised_monthly_hours": promised_monthly_hours,
        "promised_hours": promised_hours,
        "actual_hours": actual_hours,
        "realization_pct": realization_pct,
        "actual_cost": actual_cost,
        "realized_value": realized_value,
        "promised_value": promised_value,
        "value_gap": promised_value - realized_value,
        "latest_adoption_pct": adoption_values[-1] if adoption_values else 0.0,
        "adoption_trend": adoption_trend,
        "status": status,
    }


def _scenario_args(name: str) -> Dict[str, float]:
    s = SCENARIOS[name]
    return {"adoption": s["adoption"], "realization": s["realization"]}
