"""
Sample data and field defaults for AI Adoption Navigator
All examples are generic and do not reference any real company
"""

from typing import Dict, List, Any
import copy


SENSITIVITY_LEVELS = ["Public", "Internal", "Confidential", "Personal data"]
DECISION_TYPES = ["Assistive - human decides", "Automated - AI decides"]
OVERSIGHT_LEVELS = ["None", "Spot checks", "Review before action", "Approval of every output"]
SOLUTION_TYPES = ["Build in-house", "Buy SaaS tool", "Vendor platform + configuration"]
STATUSES = ["Idea", "Assessed", "Pilot", "Scaled", "Stopped"]

# EU AI Act-inspired special categories (simplified, not legal advice)
PROHIBITED_PRACTICES = [
    "Social scoring of people",
    "Emotion recognition in the workplace",
    "Manipulative or exploitative techniques",
]
HIGH_RISK_CATEGORIES = [
    "Biometric identification or categorisation",
    "Safety component of critical infrastructure",
    "Access to education or essential services",
]
SPECIAL_CATEGORIES = PROHIBITED_PRACTICES + HIGH_RISK_CATEGORIES


DEFAULT_USE_CASE: Dict[str, Any] = {
    "name": "",
    "business_unit": "",
    "sponsor": "",
    "status": "Idea",
    "process_description": "",
    "pain_point": "",
    # Volume and cost
    "tasks_per_month": 0,
    "minutes_per_task": 0,
    "time_reduction_pct": 30,
    "people_involved": 1,
    "hourly_cost": 50.0,
    # Strategic value (1-5)
    "strategic_alignment": 3,
    "customer_impact": 3,
    # Data and feasibility (1-5)
    "data_sources": "",
    "data_sensitivity": "Internal",
    "data_quality": 3,
    "integration_complexity": 3,
    "inhouse_skills": 3,
    "solution_type": "Buy SaaS tool",
    "solution_maturity": 3,
    # Decision and oversight
    "decision_type": "Assistive - human decides",
    "customer_facing": False,
    "generates_content": False,
    "people_decisions": False,
    "special_categories": [],
    "human_oversight": "Review before action",
    # Costs
    "license_cost_annual": 0.0,
    "implementation_cost": 0.0,
    "run_cost_annual": 0.0,
    # People and adoption
    "success_metric": "",
    "roles_affected": "",
    "sponsor_committed": False,
    "process_standardized": False,
    "has_training_plan": False,
    "has_champions": False,
    "user_involvement": 3,
}


def new_use_case(**overrides: Any) -> Dict[str, Any]:
    """Return a fresh use case dict with defaults applied"""
    uc = copy.deepcopy(DEFAULT_USE_CASE)
    uc.update(overrides)
    # Keep numeric types consistent with the defaults (Streamlit inputs reject mixed int/float)
    for key, default in DEFAULT_USE_CASE.items():
        if isinstance(default, bool):
            continue
        if isinstance(default, float):
            uc[key] = float(uc[key] or 0)
        elif isinstance(default, int):
            uc[key] = int(uc[key] or 0)
    return uc


def get_sample_use_cases() -> List[Dict[str, Any]]:
    """Six generic AI use cases covering every risk tier and gate outcome"""
    return [
        new_use_case(
            name="Support Ticket Triage",
            business_unit="Customer Support",
            sponsor="Director of Support",
            status="Pilot",
            process_description="Agents read each incoming ticket, tag category and priority, and route it to the right queue.",
            pain_point="Manual triage takes 4-6 minutes per ticket and misrouted tickets add a day to resolution.",
            tasks_per_month=12000, minutes_per_task=5, time_reduction_pct=60,
            people_involved=14, hourly_cost=38,
            strategic_alignment=4, customer_impact=4,
            data_sources="Ticketing system history (2 years), product catalog",
            data_sensitivity="Confidential", data_quality=4,
            integration_complexity=2, inhouse_skills=3,
            solution_type="Vendor platform + configuration", solution_maturity=4,
            decision_type="Assistive - human decides", customer_facing=False, generates_content=False,
            human_oversight="Spot checks",
            license_cost_annual=24000, implementation_cost=30000, run_cost_annual=6000,
            success_metric="Misroute rate below 5% and triage time under 1 minute",
            roles_affected="Support Agent, Support Team Lead",
            sponsor_committed=True, process_standardized=True, has_training_plan=True,
            has_champions=True, user_involvement=4,
        ),
        new_use_case(
            name="Contract Clause Review",
            business_unit="Legal",
            sponsor="General Counsel",
            process_description="Legal reviewers compare vendor contracts against the standard clause playbook.",
            pain_point="Backlog of 3 weeks for standard NDAs and MSAs slows down sales and procurement.",
            tasks_per_month=180, minutes_per_task=90, time_reduction_pct=40,
            people_involved=4, hourly_cost=95,
            strategic_alignment=4, customer_impact=3,
            data_sources="Contract repository, clause playbook",
            data_sensitivity="Confidential", data_quality=3,
            integration_complexity=3, inhouse_skills=2,
            solution_type="Buy SaaS tool", solution_maturity=4,
            decision_type="Assistive - human decides", generates_content=True,
            human_oversight="Review before action",
            license_cost_annual=36000, implementation_cost=15000, run_cost_annual=4000,
            success_metric="Standard contract turnaround under 3 days",
            roles_affected="Legal Counsel, Contract Manager",
            sponsor_committed=True, process_standardized=True, has_training_plan=False,
            has_champions=True, user_involvement=3,
        ),
        new_use_case(
            name="Code Review Assistant",
            business_unit="Engineering",
            sponsor="VP Engineering",
            status="Scaled",
            process_description="AI suggests review comments on pull requests before a human reviewer looks at them.",
            pain_point="PRs wait 1-2 days for review; senior engineers spend 20% of their week reviewing.",
            tasks_per_month=1600, minutes_per_task=35, time_reduction_pct=25,
            people_involved=60, hourly_cost=85,
            strategic_alignment=4, customer_impact=3,
            data_sources="Source code repositories, coding standards",
            data_sensitivity="Confidential", data_quality=4,
            integration_complexity=2, inhouse_skills=4,
            solution_type="Buy SaaS tool", solution_maturity=4,
            decision_type="Assistive - human decides", generates_content=True,
            human_oversight="Review before action",
            license_cost_annual=43000, implementation_cost=8000, run_cost_annual=5000,
            success_metric="PR review wait time under 4 hours with no rise in escaped defects",
            roles_affected="Software Engineer, Tech Lead",
            sponsor_committed=True, process_standardized=True, has_training_plan=True,
            has_champions=True, user_involvement=4,
        ),
        new_use_case(
            name="Resume Screening",
            business_unit="Talent Acquisition",
            sponsor="Head of Recruiting",
            process_description="AI ranks applicants and automatically rejects candidates below a score threshold.",
            pain_point="Recruiters receive 300+ applications per role and cannot review them all.",
            tasks_per_month=4000, minutes_per_task=4, time_reduction_pct=70,
            people_involved=6, hourly_cost=45,
            strategic_alignment=3, customer_impact=2,
            data_sources="Applicant tracking system, historical hiring decisions",
            data_sensitivity="Personal data", data_quality=2,
            integration_complexity=3, inhouse_skills=2,
            solution_type="Buy SaaS tool", solution_maturity=3,
            decision_type="Automated - AI decides", people_decisions=True,
            human_oversight="None",
            license_cost_annual=30000, implementation_cost=20000, run_cost_annual=5000,
            success_metric="Time-to-shortlist under 5 days",
            roles_affected="Recruiter, Recruiting Coordinator",
            sponsor_committed=True, process_standardized=False, has_training_plan=False,
            has_champions=False, user_involvement=2,
        ),
        new_use_case(
            name="Sales Email Drafting",
            business_unit="Sales",
            sponsor="Sales Operations Manager",
            process_description="AI drafts personalised follow-up emails after discovery calls using CRM notes.",
            pain_point="Reps spend 5+ hours a week writing follow-ups; quality is inconsistent.",
            tasks_per_month=2500, minutes_per_task=12, time_reduction_pct=50,
            people_involved=25, hourly_cost=55,
            strategic_alignment=3, customer_impact=3,
            data_sources="CRM notes, email templates",
            data_sensitivity="Internal", data_quality=2,
            integration_complexity=3, inhouse_skills=3,
            solution_type="Buy SaaS tool", solution_maturity=4,
            decision_type="Assistive - human decides", customer_facing=True, generates_content=True,
            human_oversight="Review before action",
            license_cost_annual=30000, implementation_cost=5000, run_cost_annual=2000,
            success_metric="Follow-up sent within 24h for 90% of calls",
            roles_affected="Account Executive, Sales Development Rep",
            sponsor_committed=False, process_standardized=True, has_training_plan=False,
            has_champions=False, user_involvement=2,
        ),
        new_use_case(
            name="Internal Knowledge Search",
            business_unit="Operations",
            sponsor="COO Office",
            process_description="Employees ask questions and get answers sourced from internal wikis and SOPs.",
            pain_point="Employees spend 30+ minutes a day searching for information across 5 tools.",
            tasks_per_month=6000, minutes_per_task=10, time_reduction_pct=40,
            people_involved=250, hourly_cost=60,
            strategic_alignment=3, customer_impact=2,
            data_sources="Wiki, SOP library, shared drives",
            data_sensitivity="Internal", data_quality=3,
            integration_complexity=4, inhouse_skills=3,
            solution_type="Vendor platform + configuration", solution_maturity=3,
            decision_type="Assistive - human decides",
            human_oversight="Spot checks",
            license_cost_annual=60000, implementation_cost=40000, run_cost_annual=10000,
            success_metric="Search time reduced by 50% (monthly pulse survey)",
            roles_affected="All knowledge workers",
            sponsor_committed=True, process_standardized=True, has_training_plan=True,
            has_champions=False, user_involvement=3,
        ),
    ]


def get_sample_evidence() -> Dict[str, List[Dict[str, Any]]]:
    """Governance evidence for the live samples (control text must match governance.CHECKLIST_ITEMS)"""
    def ev(control, status, owner="", due_date="", evidence=""):
        return {"control": control, "status": status, "owner": owner, "due_date": due_date, "evidence": evidence}

    return {
        "Support Ticket Triage": [
            ev("Named business owner accountable for AI outcomes", "Done", "Director of Support", "2026-04-15",
               "RACI in project charter v1.2"),
            ev("AI acceptable-use policy acknowledged by users", "Done", "Support Team Lead", "2026-04-30",
               "LMS completion report - 14/14 agents"),
            ev("Vendor due diligence: data use, retention, model training on your data", "Done", "Procurement",
               "2026-04-10", "DPA signed; no training on customer data (clause 7.2)"),
            ev("Intended use and out-of-scope uses documented", "Done", "Support Ops Analyst", "2026-04-20",
               "Use case card on the wiki"),
            ev("Data sources, lineage and access rights documented", "In progress", "Data Engineer", "2026-10-15"),
            ev("Quality baseline and acceptance threshold defined before go-live", "Done", "Support Ops Analyst",
               "2026-04-25", "Baseline misroute rate 14%; threshold <5%"),
            ev("Security testing: prompt injection and data leakage", "In progress", "Security Engineer",
               "2026-09-01"),
            ev("Manual fallback process and ability to switch the AI off", "Done", "Support Team Lead",
               "2026-05-01", "SOP-114 manual triage fallback"),
            ev("Performance monitoring with a periodic review cadence", "Not started", "", "2026-11-30"),
        ],
        "Code Review Assistant": [
            ev("Named business owner accountable for AI outcomes", "Done", "VP Engineering", "2026-03-01",
               "Engineering AI steering committee minutes"),
            ev("AI acceptable-use policy acknowledged by users", "In progress", "Engineering Manager", "2026-06-30",
               "38/60 engineers acknowledged"),
            ev("Vendor due diligence: data use, retention, model training on your data", "Done", "Procurement",
               "2026-03-15", "Enterprise agreement - zero data retention"),
            ev("Risk assessment documented and approved by risk/legal", "Done", "Risk Manager", "2026-04-01",
               "Risk register entry R-2026-031"),
            ev("Intended use and out-of-scope uses documented", "Done", "Tech Lead", "2026-03-20"),
            ev("Error / hallucination testing on real samples", "Not started", "Tech Lead", "2026-07-31"),
            ev("Transparency notice: users know they interact with AI / AI-generated content", "Done",
               "Engineering Manager", "2026-04-15", "AI comments labeled in the PR tool"),
            ev("Incident and escalation process for AI errors", "Not applicable", "", "",
               "Covered by existing code review process"),
        ],
    }


def get_sample_actuals() -> Dict[str, List[Dict[str, Any]]]:
    """Monthly actuals for use cases already in Pilot/Scaled (keyed by use case name)"""
    return {
        "Support Ticket Triage": [
            {"month": "2026-05", "hours_saved": 240, "adoption_pct": 45, "actual_cost": 6500, "notes": "Pilot with 6 agents"},
            {"month": "2026-06", "hours_saved": 330, "adoption_pct": 60, "actual_cost": 2500, "notes": "Rolled out to full team"},
            {"month": "2026-07", "hours_saved": 390, "adoption_pct": 75, "actual_cost": 2500, "notes": ""},
            {"month": "2026-08", "hours_saved": 410, "adoption_pct": 80, "actual_cost": 2500, "notes": ""},
        ],
        "Code Review Assistant": [
            {"month": "2026-05", "hours_saved": 70, "adoption_pct": 30, "actual_cost": 4400, "notes": "Licenses for all 60 engineers"},
            {"month": "2026-06", "hours_saved": 60, "adoption_pct": 25, "actual_cost": 4400, "notes": "Suggestions too noisy, engineers ignore them"},
            {"month": "2026-07", "hours_saved": 55, "adoption_pct": 22, "actual_cost": 4400, "notes": "No training delivered yet"},
            {"month": "2026-08", "hours_saved": 58, "adoption_pct": 24, "actual_cost": 4400, "notes": ""},
        ],
    }
