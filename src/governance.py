"""
Governance rules for AI use cases
Risk tiers are inspired by EU AI Act categories and the checklist follows
the NIST AI RMF functions (Govern, Map, Measure, Manage).
This is a portfolio/educational tool - not legal advice.
"""

from datetime import date
from typing import Any, Dict, List, Optional
from src.sample_data import PROHIBITED_PRACTICES, HIGH_RISK_CATEGORIES


RISK_TIERS = ["Minimal", "Limited", "High", "Unacceptable"]
TIER_LEVEL = {tier: i for i, tier in enumerate(RISK_TIERS)}

DISCLAIMER = (
    "Risk tiers are a simplified, rule-based interpretation inspired by EU AI Act categories "
    "and the NIST AI Risk Management Framework. They are for planning purposes only and are "
    "not legal advice - confirm classification with your legal and compliance teams."
)


def classify_risk_tier(uc: Dict[str, Any]) -> Dict[str, Any]:
    """Return the risk tier and the reasons that triggered it"""
    special = uc.get("special_categories", []) or []
    reasons: List[str] = []

    prohibited = [c for c in special if c in PROHIBITED_PRACTICES]
    if prohibited:
        reasons += [f"Prohibited practice: {c}" for c in prohibited]
        return {"tier": "Unacceptable", "reasons": reasons}

    if uc.get("people_decisions"):
        reasons.append("Influences decisions about people (hiring, credit, health, performance)")
    reasons += [f"High-risk category: {c}" for c in special if c in HIGH_RISK_CATEGORIES]
    if reasons:
        return {"tier": "High", "reasons": reasons}

    if uc.get("customer_facing"):
        reasons.append("Customers interact with the AI or its output")
    if uc.get("generates_content"):
        reasons.append("Generates content that people read or act on")
    if reasons:
        return {"tier": "Limited", "reasons": reasons}

    return {"tier": "Minimal", "reasons": ["Internal, assistive use with no special risk triggers"]}


# Each item: function, control, min tier where it becomes required, optional condition
CHECKLIST_ITEMS: List[Dict[str, Any]] = [
    # GOVERN
    {"function": "Govern", "control": "Named business owner accountable for AI outcomes", "min_tier": "Minimal"},
    {"function": "Govern", "control": "AI acceptable-use policy acknowledged by users", "min_tier": "Minimal"},
    {"function": "Govern", "control": "Vendor due diligence: data use, retention, model training on your data", "min_tier": "Minimal", "when": "vendor"},
    {"function": "Govern", "control": "Risk assessment documented and approved by risk/legal", "min_tier": "Limited"},
    {"function": "Govern", "control": "Legal review against high-risk AI obligations (conformity, registration)", "min_tier": "High"},
    # MAP
    {"function": "Map", "control": "Intended use and out-of-scope uses documented", "min_tier": "Minimal"},
    {"function": "Map", "control": "Data sources, lineage and access rights documented", "min_tier": "Minimal"},
    {"function": "Map", "control": "Affected stakeholders identified and consulted", "min_tier": "Limited"},
    {"function": "Map", "control": "Data protection impact assessment (DPIA)", "min_tier": "Minimal", "when": "personal_data"},
    {"function": "Map", "control": "Impact assessment on affected people and fundamental rights", "min_tier": "High"},
    # MEASURE
    {"function": "Measure", "control": "Quality baseline and acceptance threshold defined before go-live", "min_tier": "Minimal"},
    {"function": "Measure", "control": "Error / hallucination testing on real samples", "min_tier": "Limited"},
    {"function": "Measure", "control": "Security testing: prompt injection and data leakage", "min_tier": "Limited", "when_or": "sensitive_data"},
    {"function": "Measure", "control": "Bias and fairness testing across affected groups", "min_tier": "High"},
    # MANAGE
    {"function": "Manage", "control": "Manual fallback process and ability to switch the AI off", "min_tier": "Minimal"},
    {"function": "Manage", "control": "Performance monitoring with a periodic review cadence", "min_tier": "Minimal"},
    {"function": "Manage", "control": "Transparency notice: users know they interact with AI / AI-generated content", "min_tier": "Limited"},
    {"function": "Manage", "control": "Logging and audit trail of AI outputs and decisions", "min_tier": "Limited"},
    {"function": "Manage", "control": "Incident and escalation process for AI errors", "min_tier": "Limited"},
    {"function": "Manage", "control": "Human review before any AI output affects a person", "min_tier": "High"},
]


def _condition(name: str, uc: Dict[str, Any]) -> bool:
    sensitivity = uc.get("data_sensitivity", "Internal")
    return {
        "vendor": uc.get("solution_type", "") != "Build in-house",
        "personal_data": sensitivity == "Personal data",
        "sensitive_data": sensitivity in ("Confidential", "Personal data"),
    }[name]


def build_checklist(uc: Dict[str, Any], tier: str) -> List[Dict[str, str]]:
    """Return the checklist items that apply to this use case"""
    level = TIER_LEVEL[tier]
    checklist = []
    for item in CHECKLIST_ITEMS:
        tier_applies = level >= TIER_LEVEL[item["min_tier"]]
        if item.get("when"):
            # Required from its tier, but only when the condition holds
            applies = tier_applies and _condition(item["when"], uc)
        elif item.get("when_or"):
            # Required from its tier, or earlier when the condition holds
            applies = tier_applies or _condition(item["when_or"], uc)
        else:
            applies = tier_applies
        if applies:
            checklist.append({
                "function": item["function"],
                "control": item["control"],
                "required_from": item["min_tier"],
            })
    return checklist


def review_cadence(tier: str) -> str:
    return {
        "Minimal": "Annual review",
        "Limited": "Semi-annual review",
        "High": "Quarterly review plus monitoring of every release",
        "Unacceptable": "Not applicable - do not deploy",
    }[tier]


def risk_flags(uc: Dict[str, Any], tier: str) -> List[Dict[str, str]]:
    """Specific red flags from inconsistent or risky combinations of answers"""
    flags: List[Dict[str, str]] = []
    oversight = uc.get("human_oversight", "None")
    automated = uc.get("decision_type", "").startswith("Automated")

    if tier == "Unacceptable":
        flags.append({"severity": "Critical", "flag": "Use case matches a prohibited AI practice - stop."})
    if tier == "High" and automated:
        flags.append({"severity": "Critical", "flag": "AI makes automated decisions about people. Redesign so a human decides."})
    if tier == "High" and oversight in ("None", "Spot checks"):
        flags.append({"severity": "Critical", "flag": f"High-risk use case with '{oversight}' oversight. Require human review before action."})
    if uc.get("data_sensitivity") == "Personal data" and int(uc.get("data_quality", 3)) <= 2:
        flags.append({"severity": "High", "flag": "Personal data with low data quality increases bias and error risk."})
    if uc.get("customer_facing") and oversight == "None":
        flags.append({"severity": "High", "flag": "Customer-facing output with no human oversight."})
    if automated and oversight == "None" and tier != "High":
        flags.append({"severity": "Medium", "flag": "Fully automated with no oversight - define error monitoring and a fallback."})
    if uc.get("data_sensitivity") in ("Confidential", "Personal data") and uc.get("solution_type") != "Build in-house":
        flags.append({"severity": "Medium", "flag": "Sensitive data shared with a vendor - confirm contract terms on data retention and training."})
    if not uc.get("process_standardized"):
        flags.append({"severity": "Medium", "flag": "Process is not standardized - AI will scale today's inconsistency."})
    return flags


# ------------------------------------------------------------ evidence tracking
EVIDENCE_STATUSES = ["Not started", "In progress", "Done", "Not applicable"]
NIST_FUNCTIONS = ["Govern", "Map", "Measure", "Manage"]


def evidence_readiness(checklist: List[Dict[str, str]], evidence: Dict[str, Dict[str, Any]],
                       today: Optional[date] = None) -> Dict[str, Any]:
    """
    Merge the applicable checklist with recorded evidence and measure go-live readiness.
    Readiness = Done / (applicable controls - Not applicable). Controls without a record are "Not started".
    """
    today = today or date.today()
    rows = []
    for item in checklist:
        record = evidence.get(item["control"], {})
        due = _parse_date(record.get("due_date"))
        status = record.get("status") or "Not started"
        rows.append({
            **item,
            "status": status,
            "owner": record.get("owner") or "",
            "due_date": due,
            "evidence": record.get("evidence") or "",
            "overdue": bool(due and due < today and status not in ("Done", "Not applicable")),
        })

    in_scope = [r for r in rows if r["status"] != "Not applicable"]
    done = sum(r["status"] == "Done" for r in in_scope)
    by_function = [
        {"function": f, "status": s, "count": sum(r["function"] == f and r["status"] == s for r in rows)}
        for f in NIST_FUNCTIONS for s in EVIDENCE_STATUSES
    ]
    return {
        "rows": rows,
        "total": len(in_scope),
        "done": done,
        "readiness_pct": (done / len(in_scope) * 100) if in_scope else 100.0,
        "overdue": sum(r["overdue"] for r in rows),
        "unassigned": sum(not r["owner"] and r["status"] not in ("Done", "Not applicable") for r in rows),
        "by_function": [b for b in by_function if b["count"]],
    }


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def assess_governance(uc: Dict[str, Any]) -> Dict[str, Any]:
    """Full governance assessment"""
    classification = classify_risk_tier(uc)
    tier = classification["tier"]
    return {
        "tier": tier,
        "tier_reasons": classification["reasons"],
        "checklist": build_checklist(uc, tier) if tier != "Unacceptable" else [],
        "review_cadence": review_cadence(tier),
        "flags": risk_flags(uc, tier),
        "disclaimer": DISCLAIMER,
    }
