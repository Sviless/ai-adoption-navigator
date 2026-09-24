"""
Template Engine - rule-based generation of the AI adoption package (no API required)
Every section here is produced locally; LLM Enhanced Mode only adds to it.
"""

from typing import Any, Dict, List
import re

from src.roi import SCENARIOS
from src.sample_data import OVERSIGHT_LEVELS
from src.scoring import assess_use_case
from src.utils import bullet_list, hours, money, months, pct, yes_no


GATE_ICONS = {
    "Go": ":material/check_circle:",
    "Pilot with conditions": ":material/science:",
    "Fix process first": ":material/build:",
    "Stop": ":material/block:",
}

# Plain-language "what to do next" for each decision
GATE_NEXT_STEP = {
    "Go": "Proceed: run a short pilot to confirm quality, then scale with the standard controls.",
    "Pilot with conditions": "Run a time-boxed pilot, and scale only if the listed conditions are met.",
    "Fix process first": "Don't buy or build AI yet. Standardize the process first, then re-assess.",
    "Stop": "Don't proceed. The value or risk profile doesn't justify the investment.",
}

# Bump when the package structure changes so older saved assessments are rebuilt
PACKAGE_VERSION = 2


class TemplateEngine:
    """Generates every output section from the deterministic assessment"""

    # ------------------------------------------------------------------ package
    def build_package(self, uc: Dict[str, Any]) -> Dict[str, Any]:
        a = assess_use_case(uc)
        sections = {
            "executive_summary": self.executive_summary(uc, a),
            "use_case_canvas": self.use_case_canvas(uc, a),
            "roi_assumptions": self.roi_assumptions(uc),
            "governance_summary": self.governance_summary(uc, a),
            "data_readiness": self.data_readiness(uc),
            "hitl_design": self.hitl_design(uc, a),
            "workforce_plan": self.workforce_plan(uc, a),
            "adoption_plan": self.adoption_plan(uc, a),
            "pilot_plan": self.pilot_plan(uc, a),
            "stakeholder_comms": self.stakeholder_comms(uc, a),
            "linkedin_statement": self.linkedin_statement(uc, a),
            "final_recommendation": self.final_recommendation(uc, a),
        }
        return {
            "assessment": a,
            "sections": sections,
            "assumption_checks": self.assumption_checks(uc),
            "risks": self.risk_log(uc, a),
            "ai_insights": {},
            "llm_enhanced": False,
            "version": PACKAGE_VERSION,
        }

    # ----------------------------------------------------------------- sections
    def executive_summary(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        exp = a["roi"]["Expected"]
        cons = a["roi"]["Conservative"]
        gate = a["gate"]["gate"]
        article = "an" if a["quadrant"][0] in "AEIOU" else "a"
        return (
            f"**{uc['name']}** ({uc.get('business_unit') or 'business unit not set'}) is assessed as {article} "
            f"**{a['quadrant']}** with a **{a['governance']['tier']}** risk tier. "
            f"The recommended decision is **{gate}**.\n\n"
            f"In the Expected scenario the use case saves about **{hours(exp['annual_hours_saved'])} per year** "
            f"({exp['fte_equivalent']:.1f} FTE of capacity) and returns **{money(exp['net_3yr'])} net over 3 years** "
            f"(payback: {months(exp['payback_months'])}). The Conservative scenario returns "
            f"{money(cons['net_3yr'])}, which is the figure to commit to in a business case.\n\n"
            f"Scores - value {a['scores']['value']}/100, feasibility {a['scores']['feasibility']}/100, "
            f"adoption readiness {a['scores']['adoption_readiness']}/100. "
            f"Workforce impact is classified as **{a['workforce']['category']}**."
        )

    def use_case_canvas(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        return "\n".join([
            f"| Element | Detail |",
            f"|---|---|",
            f"| Problem | {uc.get('pain_point') or '-'} |",
            f"| Current process | {uc.get('process_description') or '-'} |",
            f"| AI solution | {uc.get('solution_type')}, {uc.get('decision_type').lower()} |",
            f"| Users / roles | {uc.get('roles_affected') or '-'} ({uc.get('people_involved')} people) |",
            f"| Data | {uc.get('data_sources') or '-'} ({uc.get('data_sensitivity')}) |",
            f"| Success metric | {uc.get('success_metric') or 'Not defined'} |",
            f"| Sponsor | {uc.get('sponsor') or 'Not assigned'} |",
            f"| Human oversight | {uc.get('human_oversight')} |",
        ])

    def roi_assumptions(self, uc: Dict[str, Any]) -> str:
        scen = ", ".join(
            f"{name}: {s['adoption']:.0%} adoption x {s['realization']:.0%} realization"
            for name, s in SCENARIOS.items()
        )
        return (
            f"- Volume: {uc.get('tasks_per_month'):,} tasks/month x {uc.get('minutes_per_task')} min/task\n"
            f"- AI reduces task time by {uc.get('time_reduction_pct')}%\n"
            f"- Loaded hourly cost: {money(uc.get('hourly_cost'))}\n"
            f"- Costs: implementation {money(uc.get('implementation_cost'))}, "
            f"license {money(uc.get('license_cost_annual'))}/yr, run/support {money(uc.get('run_cost_annual'))}/yr\n"
            f"- Scenarios - {scen}\n"
            f"- *Realization* is the share of saved time that turns into real capacity. Saved minutes "
            f"only become value if the freed time is redirected deliberately."
        )

    def governance_summary(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        g = a["governance"]
        text = f"**Risk tier: {g['tier']}**\n\nWhy:\n{bullet_list(g['tier_reasons'])}\n\n"
        if g["tier"] == "Unacceptable":
            return text + "This is a prohibited practice. No set of controls makes it deployable."
        return text + (f"Review cadence: {g['review_cadence']}. "
                       f"{len(g['checklist'])} governance controls apply to this use case.")

    def data_readiness(self, uc: Dict[str, Any]) -> str:
        quality = int(uc.get("data_quality", 3))
        verdict = {1: "Not ready", 2: "Significant gaps", 3: "Usable with cleanup", 4: "Ready", 5: "Ready"}[quality]
        actions = []
        if quality <= 3:
            actions.append("Profile the data: completeness, duplicates, outdated records, labeling consistency.")
            actions.append("Assign a data owner and fix the top quality issues before the pilot starts.")
        if uc.get("data_sensitivity") in ("Confidential", "Personal data"):
            actions.append("Confirm access rights and minimize the data sent to the AI (only fields needed).")
        if uc.get("data_sensitivity") == "Personal data":
            actions.append("Run a data protection impact assessment (DPIA) with the privacy team.")
        actions.append("Build a labeled test set of 50-100 real examples to measure AI quality.")
        return (
            f"**Data readiness: {verdict}** (quality {quality}/5, sensitivity: {uc.get('data_sensitivity')})\n\n"
            f"Sources: {uc.get('data_sources') or 'not documented'}\n\n{bullet_list(actions)}"
        )

    def hitl_design(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        tier = a["governance"]["tier"]
        recommended = {
            "Minimal": "Spot checks",
            "Limited": "Review before action",
            "High": "Approval of every output",
            "Unacceptable": "Not applicable",
        }[tier]
        current = uc.get("human_oversight")
        below_minimum = (
            recommended in OVERSIGHT_LEVELS and current in OVERSIGHT_LEVELS
            and OVERSIGHT_LEVELS.index(current) < OVERSIGHT_LEVELS.index(recommended)
        )
        gap = (
            f"\n\n:orange[Current plan is '{current}'. For a {tier} tier use case the recommended minimum is '{recommended}'.]"
            if below_minimum else ""
        )
        return (
            f"**Recommended oversight: {recommended}** (planned: {current}){gap}\n\n"
            "- Define which outputs a human must review, and what they check against\n"
            "- Make overriding the AI easy and log every override - overrides are the best improvement signal\n"
            "- Set a confidence or risk threshold above which cases go to a human automatically\n"
            "- Keep the manual process documented so it can take over if the AI is switched off"
        )

    def workforce_plan(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        w = a["workforce"]
        roles = ", ".join(w["roles"]) or "roles not specified"
        skills = ["AI output review and quality validation", "Exception and edge-case handling",
                  "Prompt and workflow design", "Process improvement (Lean) to capture freed time"]
        if uc.get("data_sensitivity") != "Public":
            skills.append("Data stewardship and responsible data handling")
        return (
            f"**Impact category: {w['category']}** - {w['meaning']}\n\n"
            f"- Roles affected: {roles}\n"
            f"- People involved: {w['people_involved']}\n"
            f"- Capacity freed (Expected): {w['capacity_freed_fte']:.1f} FTE\n\n"
            f"**Skills to build**\n{bullet_list(skills)}\n\n"
            "**Capacity plan** - decide *before go-live* where freed capacity goes: backlog reduction, "
            "customer-facing work, quality improvement, or growth initiatives. Unplanned freed time "
            "evaporates, and unplanned headcount cuts destroy the trust that adoption depends on.\n\n"
            "**Transition timeline**\n"
            "- Days 0-30: involve affected employees in the pilot design; communicate intent openly\n"
            "- Days 31-60: role-based training; redefine tasks and success measures for each role\n"
            "- Days 61-90: update job descriptions and career paths; confirm redeployment plans"
        )

    def adoption_plan(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        gaps = []
        if not uc.get("sponsor_committed"):
            gaps.append("No committed sponsor - adoption will stall at the first obstacle.")
        if not uc.get("has_training_plan"):
            gaps.append("No training plan - users will try the tool once and go back to the old way.")
        if not uc.get("has_champions"):
            gaps.append("No champions - nominate 1 champion per 8-10 users.")
        if int(uc.get("user_involvement", 3)) <= 2:
            gaps.append("Low user involvement - co-design the workflow with the people who will use it.")
        return (
            f"**Adoption readiness: {a['scores']['adoption_readiness']}/100**\n\n"
            f"Gaps:\n{bullet_list(gaps)}\n\n"
            "| ADKAR stage | Action |\n|---|---|\n"
            "| Awareness | Explain the problem being solved and what will *not* change |\n"
            "| Desire | Show what users gain (less rework, fewer manual steps); address job-security concerns directly |\n"
            "| Knowledge | Role-based training using real examples from their own work |\n"
            "| Ability | Champions and office hours during the first 4 weeks; quick-reference guide |\n"
            "| Reinforcement | Share adoption and value metrics monthly; recognize teams that improve the workflow |"
        )

    def pilot_plan(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        exp = a["roi"]["Expected"]
        target_hours = exp["annual_hours_saved"] / 12
        metric = uc.get("success_metric") or "Define a measurable success metric"
        return (
            f"**Pilot scope:** one team, real work, {max(3, min(int(uc.get('people_involved', 5)), 10))} users\n\n"
            "| Phase | Focus | Exit criteria |\n|---|---|---|\n"
            "| Days 1-30 | Baseline current process, configure tool, train pilot users | Baseline measured; quality threshold agreed |\n"
            "| Days 31-60 | Run on real work with human review; log errors and overrides | Quality at or above threshold; adoption > 60% of pilot users |\n"
            f"| Days 61-90 | Measure value and decide | Hours saved at least {target_hours * 0.7:,.0f} h/month at full scale (70% of plan) |\n\n"
            f"**Success metric:** {metric}\n\n"
            "**Stop criteria (end the pilot if any is true at day 90)**\n"
            "- Quality stays below the agreed threshold after two improvement cycles\n"
            "- Adoption below 40% of pilot users despite training\n"
            "- Realized hours below 40% of plan\n"
            "- A governance control cannot be met\n\n"
            "Stopping a pilot on evidence is a success of the process, not a failure."
        )

    def stakeholder_comms(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        return (
            "| Audience | Message | Channel | When |\n|---|---|---|---|\n"
            f"| Sponsor ({uc.get('sponsor') or 'TBD'}) | Decision, value case, conditions | 1:1 briefing | Before kickoff |\n"
            f"| Affected employees ({uc.get('roles_affected') or 'TBD'}) | Why, what changes, what does not, how they are involved | Team meeting + Q&A | Kickoff |\n"
            "| Risk / legal / privacy | Risk tier and controls | Review meeting | Before pilot |\n"
            "| IT / data owners | Integration, access, data quality actions | Working session | Week 1 |\n"
            "| Leadership | Adoption and realized value vs plan | Monthly dashboard | Monthly |"
        )

    def linkedin_statement(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        exp = a["roi"]["Expected"]
        return (
            f"Assessed the \"{uc['name']}\" AI use case end-to-end: {hours(exp['annual_hours_saved'])}/year of "
            f"expected capacity ({exp['fte_equivalent']:.1f} FTE), {money(exp['net_3yr'])} 3-year net value, "
            f"{a['governance']['tier'].lower()}-risk governance with {len(a['governance']['checklist'])} controls, "
            f"and a people-first adoption plan - leading to a '{a['gate']['gate']}' decision backed by data."
        )

    def final_recommendation(self, uc: Dict[str, Any], a: Dict[str, Any]) -> str:
        gate = a["gate"]
        text = f"### {GATE_ICONS[gate['gate']]} {gate['gate']}\n\n{bullet_list(gate['reasons'])}"
        if gate["conditions"]:
            text += f"\n\n**Conditions**\n{bullet_list(gate['conditions'])}"
        return text

    # --------------------------------------------------------- checks and risks
    def assumption_checks(self, uc: Dict[str, Any]) -> List[Dict[str, str]]:
        """Deterministic sanity checks on the ROI inputs"""
        checks = []
        reduction = float(uc.get("time_reduction_pct", 0) or 0)
        if reduction > 60:
            checks.append({"severity": "High", "check": f"{reduction:.0f}% time reduction is aggressive. Validate it on real samples during the pilot."})
        if not uc.get("implementation_cost"):
            checks.append({"severity": "High", "check": "Implementation cost is zero. Include integration, configuration, testing, training and change management."})
        if not uc.get("run_cost_annual"):
            checks.append({"severity": "Medium", "check": "No run cost. Include support, monitoring, model/API usage and periodic re-validation."})
        if not uc.get("has_training_plan"):
            checks.append({"severity": "Medium", "check": "No training plan - Expected-scenario adoption (70%) is unlikely without one."})
        if int(uc.get("data_quality", 3)) <= 2:
            checks.append({"severity": "Medium", "check": "Low data quality usually cuts early accuracy - budget time for data cleanup."})
        if not uc.get("success_metric"):
            checks.append({"severity": "Medium", "check": "No success metric defined - value cannot be verified later."})
        if float(uc.get("hourly_cost", 0) or 0) < 20:
            checks.append({"severity": "Low", "check": "Hourly cost looks low for a loaded rate (salary + benefits + overhead)."})
        return checks

    def risk_log(self, uc: Dict[str, Any], a: Dict[str, Any]) -> List[Dict[str, str]]:
        risks = [
            {"risk": f["flag"], "category": "Governance", "severity": f["severity"],
             "mitigation": "Resolve before pilot" if f["severity"] == "Critical" else "Address in pilot plan"}
            for f in a["governance"]["flags"]
        ]
        if a["scores"]["adoption_readiness"] < 60:
            risks.append({"risk": "Low adoption - users revert to the old process", "category": "Adoption",
                          "severity": "High", "mitigation": "Sponsor, champions and role-based training"})
        if a["scores"]["feasibility"] < 50:
            risks.append({"risk": "Technical or data issues delay the pilot", "category": "Delivery",
                          "severity": "Medium", "mitigation": "Timebox data cleanup and integration spikes"})
        if a["workforce"]["category"] == "Redeploy & reskill":
            risks.append({"risk": "Employee anxiety about job security reduces adoption", "category": "People",
                          "severity": "High", "mitigation": "Communicate the capacity plan openly and early"})
        risks.append({"risk": "Freed capacity is not redirected, so savings stay on paper", "category": "Value",
                      "severity": "Medium", "mitigation": "Track realized value monthly in the Value Tracker"})
        if uc.get("solution_type") != "Build in-house":
            risks.append({"risk": "Vendor lock-in or price increases", "category": "Commercial",
                          "severity": "Low", "mitigation": "Exit clause, data export rights, annual price review"})
        return risks

    # ------------------------------------------------------------ smart intake
    def extract_use_case(self, text: str) -> Dict[str, Any]:
        """Keyword-based extraction (Template mode). LLM mode does this with real understanding."""
        t = text.lower()
        fields: Dict[str, Any] = {}
        notes: List[str] = []

        def has(*words):
            return any(w in t for w in words)

        if has("hire", "hiring", "candidate", "resume", "cv ", "applicant", "credit", "loan",
               "performance review", "promotion", "insurance claim", "patient"):
            fields["people_decisions"] = True
            notes.append("Mentions decisions about people - flagged as potentially High risk.")
        if has("customer", "client", "chatbot", "external", "public website"):
            fields["customer_facing"] = True
        if has("draft", "write", "generate", "summar", "respond", "reply"):
            fields["generates_content"] = True
        if has("personal data", "pii", "employee record", "candidate", "patient", "social security"):
            fields["data_sensitivity"] = "Personal data"
        elif has("confidential", "contract", "financial", "source code"):
            fields["data_sensitivity"] = "Confidential"
        if has("automatically", "auto-reject", "without review", "no human", "fully automated"):
            fields["decision_type"] = "Automated - AI decides"
        if has("emotion", "sentiment of employees", "mood"):
            notes.append("Mentions emotion analysis - emotion recognition in the workplace is a prohibited practice under the EU AI Act.")

        volume = re.search(r"(\d[\d,]*)\s*(?:\w+\s){0,2}(?:per|a|each|/)\s*(day|week|month)", t)
        if volume:
            n = int(volume.group(1).replace(",", ""))
            factor = {"day": 21, "week": 4.33, "month": 1}[volume.group(2)]
            fields["tasks_per_month"] = int(n * factor)
        minutes = re.search(r"(\d+)\s*(?:-\s*\d+\s*)?(minutes|min|hours|hrs?)\b", t)
        if minutes:
            m = int(minutes.group(1))
            fields["minutes_per_task"] = m * 60 if minutes.group(2).startswith("h") else m

        missing = [label for key, label in [
            ("tasks_per_month", "task volume"), ("minutes_per_task", "time per task"),
        ] if key not in fields]
        missing += ["costs (license, implementation, run)", "sponsor", "success metric", "data quality"]
        return {"fields": fields, "notes": notes, "missing": missing}

    # ------------------------------------------------------- value gap diagnosis
    def diagnose_value_gap(self, uc: Dict[str, Any], summary: Dict[str, Any],
                           actuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        causes, actions = [], []
        adoption = summary["latest_adoption_pct"]
        if adoption < 50:
            causes.append(f"Low adoption ({adoption:.0f}%) - most users are not using the tool.")
            actions.append("Interview non-users; fix the top 3 usability or trust issues.")
            if not uc.get("has_training_plan"):
                actions.append("Deliver role-based training with real examples.")
            if not uc.get("has_champions"):
                actions.append("Nominate champions and run weekly office hours.")
        elif summary["realization_pct"] < 70:
            causes.append("Adoption is reasonable but hours saved are low - the workflow around the tool was not redesigned, so saved minutes are not captured.")
            actions.append("Map the new workflow and remove steps the AI made redundant (Workflow Waste Detector).")
        if summary["adoption_trend"] == "Falling":
            causes.append("Adoption is falling - an early warning of quality or trust issues.")
            actions.append("Review AI output quality and override logs; publish fixes to users.")
        promised_cost = (float(uc.get("license_cost_annual", 0)) + float(uc.get("run_cost_annual", 0))) / 12 * summary["months_tracked"]
        if summary["actual_cost"] > promised_cost * 1.2 and summary["months_tracked"] > 0:
            causes.append("Costs are running above plan.")
            actions.append("Right-size licenses to active users and review usage-based charges.")
        notes = [a.get("notes") for a in actuals if a.get("notes")]
        if notes:
            causes.append("Team notes: " + "; ".join(notes))
        if not causes:
            causes.append("No leakage detected - value is tracking to plan.")
            actions.append("Keep monthly tracking and look for similar processes to scale to.")
        actions.append("Run a structured root cause analysis if the gap persists (AI Root Cause Coach).")
        return {"causes": causes, "actions": actions, "narrative": ""}
