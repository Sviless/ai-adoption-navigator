"""
Input validation: required fields, and sanitizing AI-suggested intake fields
"""

from typing import Any, Dict, List
from src.sample_data import (
    DECISION_TYPES, DEFAULT_USE_CASE, OVERSIGHT_LEVELS, SENSITIVITY_LEVELS,
    SOLUTION_TYPES, SPECIAL_CATEGORIES,
)


def validate_use_case(uc: Dict[str, Any]) -> List[str]:
    """Return blocking errors (empty list = valid)"""
    errors = []
    if not str(uc.get("name", "")).strip():
        errors.append("Use case name is required.")
    if not str(uc.get("process_description", "")).strip():
        errors.append("Describe the current process.")
    if float(uc.get("tasks_per_month", 0) or 0) <= 0:
        errors.append("Tasks per month must be greater than 0.")
    if float(uc.get("minutes_per_task", 0) or 0) <= 0:
        errors.append("Minutes per task must be greater than 0.")
    if float(uc.get("hourly_cost", 0) or 0) <= 0:
        errors.append("Loaded hourly cost must be greater than 0.")
    return errors


RATING_FIELDS = ["strategic_alignment", "customer_impact", "data_quality", "integration_complexity",
                 "inhouse_skills", "solution_maturity", "user_involvement"]
# Integer fields must stay int - Streamlit number inputs reject mixed int/float values
INTEGER_FIELDS = ["tasks_per_month", "minutes_per_task", "time_reduction_pct", "people_involved"]
NUMBER_FIELDS = ["hourly_cost", "license_cost_annual", "implementation_cost", "run_cost_annual"]
BOOL_FIELDS = ["customer_facing", "generates_content", "people_decisions", "sponsor_committed",
               "process_standardized", "has_training_plan", "has_champions"]
TEXT_FIELDS = ["name", "business_unit", "sponsor", "process_description", "pain_point",
               "data_sources", "success_metric", "roles_affected"]
CHOICE_FIELDS = {
    "data_sensitivity": SENSITIVITY_LEVELS,
    "decision_type": DECISION_TYPES,
    "human_oversight": OVERSIGHT_LEVELS,
    "solution_type": SOLUTION_TYPES,
}


def sanitize_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only known fields with valid types/values (LLM output is untrusted)"""
    clean: Dict[str, Any] = {}
    for key, value in (fields or {}).items():
        if key not in DEFAULT_USE_CASE or value is None:
            continue
        try:
            if key in RATING_FIELDS:
                clean[key] = min(max(int(value), 1), 5)
            elif key in INTEGER_FIELDS:
                number = int(round(float(value)))
                if number >= 0:
                    clean[key] = min(number, 100) if key == "time_reduction_pct" else number
            elif key in NUMBER_FIELDS:
                number = float(value)
                if number >= 0:
                    clean[key] = number
            elif key in BOOL_FIELDS:
                clean[key] = value if isinstance(value, bool) else str(value).lower() in ("true", "yes", "1")
            elif key in TEXT_FIELDS:
                clean[key] = str(value)[:1000]
            elif key in CHOICE_FIELDS and value in CHOICE_FIELDS[key]:
                clean[key] = value
            elif key == "special_categories" and isinstance(value, list):
                clean[key] = [v for v in value if v in SPECIAL_CATEGORIES]
        except (TypeError, ValueError):
            continue
    return clean
