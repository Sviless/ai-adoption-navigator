"""
Markdown and CSV exports
"""

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from src.scoring import assess_use_case
from src.utils import bullet_list, hours, money, months, pct


def _strip_streamlit_markup(text: str) -> str:
    """Remove Streamlit-only markup (icons, colored text) for plain Markdown export"""
    import re
    text = re.sub(r":material/[a-z_]+:\s*", "", text)
    return re.sub(r":(?:red|orange|green|blue|violet|gray|grey|rainbow)\[(.*?)\]", r"\1", text, flags=re.S)


def roi_table(assessment: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name, s in assessment["roi"].items():
        rows.append({
            "Scenario": name,
            "Adoption": f"{s['adoption']:.0%}",
            "Realization": f"{s['realization']:.0%}",
            "Hours saved / yr": round(s["annual_hours_saved"]),
            "FTE": round(s["fte_equivalent"], 1),
            "Annual benefit": round(s["annual_benefit"]),
            "Annual running cost": round(s["annual_running_cost"]),
            "3-yr net value": round(s["net_3yr"]),
            "3-yr ROI %": None if s["roi_3yr_pct"] is None else round(s["roi_3yr_pct"]),
            "Payback (months)": None if s["payback_months"] is None else round(s["payback_months"], 1),
        })
    return pd.DataFrame(rows)


def _md_table(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, sep, *body])


def export_markdown(uc: Dict[str, Any], package: Dict[str, Any],
                    readiness: Optional[Dict[str, Any]] = None) -> str:
    a = package["assessment"]
    s = package["sections"]
    insights = package.get("ai_insights", {})
    parts = [
        f"# AI Use Case Assessment: {uc['name']}",
        f"*Generated {date.today().isoformat()} with AI Adoption Navigator - {package.get('mode', 'Template Engine')}*",
        "## Executive summary", s["executive_summary"],
        "## Decision", s["final_recommendation"],
        "## Use case canvas", s["use_case_canvas"],
        "## Scores",
        f"- Value: {a['scores']['value']}/100\n- Feasibility: {a['scores']['feasibility']}/100\n"
        f"- Adoption readiness: {a['scores']['adoption_readiness']}/100\n- Portfolio quadrant: {a['quadrant']}",
        "## ROI scenarios", _md_table(roi_table(a)),
        "### Assumptions", s["roi_assumptions"],
        "### Assumption checks",
        bullet_list([f"[{c['severity']}] {c['check']}" + (" (AI)" if c.get("source") == "AI" else "")
                     for c in package["assumption_checks"]]),
        "## Governance", s["governance_summary"],
    ]
    if insights.get("governance_rationale"):
        parts += ["### AI governance rationale", insights["governance_rationale"]]
    if insights.get("key_controls"):
        parts += ["### Key controls for this use case", bullet_list(insights["key_controls"])]
    if readiness and readiness["rows"]:
        evidence = evidence_dataframe(readiness["rows"]).drop(columns=["Overdue"])
        parts += [f"### Governance checklist and evidence - {readiness['readiness_pct']:.0f}% ready "
                  f"({readiness['done']}/{readiness['total']} controls done, {readiness['overdue']} overdue)",
                  _md_table(evidence)]
    else:
        checklist = pd.DataFrame(a["governance"]["checklist"])
        if not checklist.empty:
            checklist.columns = ["NIST AI RMF function", "Control", "Required from tier"]
            parts += ["### Governance checklist", _md_table(checklist)]
    parts += [f"*{a['governance']['disclaimer']}*",
              "## Data readiness", s["data_readiness"],
              "## Human-in-the-loop design", s["hitl_design"],
              "## Workforce impact and reskilling", s["workforce_plan"]]
    if insights.get("workforce_narrative"):
        parts += ["### AI workforce recommendations", insights["workforce_narrative"]]
    parts += ["## Change and adoption plan", s["adoption_plan"]]
    if insights.get("adoption_narrative"):
        parts += ["### AI adoption recommendations", insights["adoption_narrative"]]
    parts += ["## 30/60/90-day pilot plan", s["pilot_plan"]]
    if insights.get("pilot_adjustments"):
        parts += ["### AI pilot adjustments", bullet_list(insights["pilot_adjustments"])]
    risks = pd.DataFrame(package["risks"]).drop(columns=["source"], errors="ignore")
    parts += ["## Risk log", _md_table(risks) if not risks.empty else "- None",
              "## Stakeholder communication", s["stakeholder_comms"],
              "## Achievement statement", s["linkedin_statement"]]
    return _strip_streamlit_markup("\n\n".join(parts)) + "\n"


def evidence_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """Checklist rows merged with evidence, in audit-friendly column names"""
    return pd.DataFrame([{
        "Function": r["function"],
        "Control": r["control"],
        "Required from tier": r["required_from"],
        "Status": r["status"],
        "Owner": r["owner"],
        "Due date": r["due_date"].isoformat() if r["due_date"] else "",
        "Evidence": r["evidence"],
        "Overdue": "Yes" if r["overdue"] else "",
    } for r in rows])


def portfolio_dataframe(use_cases: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for uc in use_cases:
        a = assess_use_case(uc)
        exp = a["roi"]["Expected"]
        rows.append({
            "Use case": uc["name"],
            "Business unit": uc.get("business_unit", ""),
            "Status": uc.get("status", ""),
            "Value": a["scores"]["value"],
            "Feasibility": a["scores"]["feasibility"],
            "Adoption readiness": a["scores"]["adoption_readiness"],
            "Quadrant": a["quadrant"],
            "Risk tier": a["governance"]["tier"],
            "Decision": a["gate"]["gate"],
            "Hours saved / yr (expected)": round(exp["annual_hours_saved"]),
            "3-yr net (expected)": round(exp["net_3yr"]),
            "3-yr net (conservative)": round(a["roi"]["Conservative"]["net_3yr"]),
            "Payback months (expected)": None if exp["payback_months"] is None else round(exp["payback_months"], 1),
            "Workforce impact": a["workforce"]["category"],
        })
    return pd.DataFrame(rows)


def actuals_dataframe(uc: Dict[str, Any], actuals: List[Dict[str, Any]], promised_monthly_hours: float) -> pd.DataFrame:
    df = pd.DataFrame(actuals, columns=["month", "hours_saved", "adoption_pct", "actual_cost", "notes"])
    df["promised_hours"] = round(promised_monthly_hours)
    df["realization_pct"] = (df["hours_saved"] / promised_monthly_hours * 100).round(0) if promised_monthly_hours else 0
    df.insert(0, "use_case", uc["name"])
    return df
