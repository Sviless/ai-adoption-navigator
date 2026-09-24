"""
Enhanced LLM Provider - AI judgment and narrative on top of the Template Engine
Scores, ROI numbers, risk tier and gate always come from the deterministic engine;
the LLM adds context-aware insights and never overrides the numbers.
"""

from typing import Any, Dict, List, Optional
import json

from src.llm_client import UniversalLLMClient
from src.providers.base_provider import BaseProvider
from src.sample_data import (
    DECISION_TYPES, OVERSIGHT_LEVELS, SENSITIVITY_LEVELS, SOLUTION_TYPES, SPECIAL_CATEGORIES,
)
from src.template_engine import TemplateEngine
from src.validators import sanitize_fields


class EnhancedLLMProvider(BaseProvider):
    """LLM-enhanced provider with fallback to Template Engine output"""

    def __init__(self, provider: str = "claude", model: Optional[str] = None,
                 api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__()
        self.provider_name = "LLM Enhanced"
        self.llm_provider = provider
        self.template_engine = TemplateEngine()
        self.init_error = ""
        try:
            self.llm_client = UniversalLLMClient(provider=provider, model=model, api_key=api_key, base_url=base_url)
            self.llm_available = True
        except Exception as e:
            self.init_error = str(e)
            self.llm_available = False

    # ---------------------------------------------------------------- assess
    def assess_use_case(self, uc: Dict[str, Any]) -> Dict[str, Any]:
        """Template package first, then LLM enhancement; falls back on any error"""
        package = self.template_engine.build_package(uc)
        package["mode"] = "Template Engine"
        if not self.llm_available:
            package["llm_error"] = self.init_error
            return package
        try:
            insights = self.llm_client.generate_json(self._assessment_prompt(uc, package), max_tokens=6000)
            self._merge_insights(package, insights)
            package["llm_enhanced"] = True
            package["mode"] = f"LLM Enhanced ({self.llm_provider}: {self.llm_client.model})"
        except Exception as e:
            package["llm_error"] = str(e)
        return package

    def _assessment_prompt(self, uc: Dict[str, Any], package: Dict[str, Any]) -> str:
        a = package["assessment"]
        facts = {
            "scores": a["scores"],
            "quadrant": a["quadrant"],
            "roi": {name: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in s.items()}
                    for name, s in a["roi"].items()},
            "risk_tier": a["governance"]["tier"],
            "tier_reasons": a["governance"]["tier_reasons"],
            "governance_flags": a["governance"]["flags"],
            "decision_gate": a["gate"],
            "workforce_impact": {k: v for k, v in a["workforce"].items() if k != "roles"},
            "rule_based_assumption_checks": package["assumption_checks"],
        }
        return f"""Review this AI use case proposal and its rule-based assessment.

USE CASE INPUTS:
{json.dumps(uc, indent=2, default=str)}

CALCULATED ASSESSMENT (authoritative - do not change or recompute these numbers):
{json.dumps(facts, indent=2, default=str)}

Return a JSON object with these keys:
- "executive_summary": 2 short paragraphs of markdown for an executive. Use only the numbers above.
- "assumption_challenges": list of {{"severity": "High|Medium|Low", "check": "..."}} - challenge the ROI inputs like a skeptical CFO: optimistic time savings or adoption, hidden costs (integration, change management, monitoring, error handling, API usage growth), vendor lock-in. Do not repeat the rule-based checks.
- "governance_rationale": markdown paragraph explaining why this risk tier fits this specific use case and what could push it into a higher tier.
- "key_controls": list of the 3-5 governance controls that matter most for THIS use case, each with one sentence on how to implement it.
- "workforce_narrative": markdown paragraph with a specific, people-centered plan for the affected roles: which tasks change, which skills to build, and where freed capacity should go.
- "adoption_narrative": markdown paragraph with the 3 most important change management actions for this context.
- "pilot_adjustments": list of specific changes to a standard 30/60/90-day pilot for this use case (test cases, metrics, stop criteria).
- "additional_risks": list of {{"risk": "...", "category": "...", "severity": "High|Medium|Low", "mitigation": "..."}} not already covered by the governance flags.
- "linkedin_statement": one sentence achievement statement for a professional profile, using the Expected scenario numbers."""

    def _merge_insights(self, package: Dict[str, Any], insights: Dict[str, Any]):
        sections = package["sections"]
        if isinstance(insights.get("executive_summary"), str) and insights["executive_summary"].strip():
            sections["executive_summary_template"] = sections["executive_summary"]
            sections["executive_summary"] = insights["executive_summary"].strip()
        if isinstance(insights.get("linkedin_statement"), str) and insights["linkedin_statement"].strip():
            sections["linkedin_statement"] = insights["linkedin_statement"].strip()

        package["assumption_checks"] += [
            {"severity": str(c.get("severity", "Medium")), "check": str(c.get("check", "")), "source": "AI"}
            for c in _as_list(insights.get("assumption_challenges")) if isinstance(c, dict) and c.get("check")
        ]
        package["risks"] += [
            {"risk": str(r.get("risk", "")), "category": str(r.get("category", "Other")),
             "severity": str(r.get("severity", "Medium")), "mitigation": str(r.get("mitigation", "")), "source": "AI"}
            for r in _as_list(insights.get("additional_risks")) if isinstance(r, dict) and r.get("risk")
        ]
        package["ai_insights"] = {
            "governance_rationale": str(insights.get("governance_rationale", "") or ""),
            "key_controls": [str(c) for c in _as_list(insights.get("key_controls"))],
            "workforce_narrative": str(insights.get("workforce_narrative", "") or ""),
            "adoption_narrative": str(insights.get("adoption_narrative", "") or ""),
            "pilot_adjustments": [str(p) for p in _as_list(insights.get("pilot_adjustments"))],
        }

    # ----------------------------------------------------------- smart intake
    def extract_use_case(self, text: str) -> Dict[str, Any]:
        fallback = self.template_engine.extract_use_case(text)
        if not self.llm_available:
            return fallback
        prompt = f"""Extract AI use case intake fields from the text below. Only include fields the text supports - do not guess.

Allowed fields and values:
- name, business_unit, sponsor, process_description, pain_point, data_sources, success_metric, roles_affected (strings)
- tasks_per_month, minutes_per_task, people_involved, hourly_cost, license_cost_annual, implementation_cost, run_cost_annual (numbers; convert per day/week to per month)
- time_reduction_pct (0-100)
- strategic_alignment, customer_impact, data_quality, integration_complexity, inhouse_skills, solution_maturity, user_involvement (1-5)
- customer_facing, generates_content, people_decisions, sponsor_committed, process_standardized, has_training_plan, has_champions (booleans)
- data_sensitivity: one of {SENSITIVITY_LEVELS}
- decision_type: one of {DECISION_TYPES}
- human_oversight: one of {OVERSIGHT_LEVELS}
- solution_type: one of {SOLUTION_TYPES}
- special_categories: list from {SPECIAL_CATEGORIES}

TEXT:
\"\"\"{text}\"\"\"

Return JSON: {{"fields": {{...}}, "notes": ["risks or red flags you noticed, e.g. vendor claims that need validation"], "missing": ["important information not in the text"]}}"""
        try:
            result = self.llm_client.generate_json(prompt, max_tokens=3000)
            return {
                "fields": sanitize_fields(result.get("fields", {})),
                "notes": [str(n) for n in _as_list(result.get("notes"))],
                "missing": [str(m) for m in _as_list(result.get("missing"))],
                "source": "AI",
            }
        except Exception as e:
            fallback["notes"].append(f"LLM extraction failed, used keyword extraction instead: {e}")
            return fallback

    # ------------------------------------------------------ value gap diagnosis
    def diagnose_value_gap(self, uc: Dict[str, Any], summary: Dict[str, Any],
                           actuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        base = self.template_engine.diagnose_value_gap(uc, summary, actuals)
        if not self.llm_available:
            return base
        prompt = f"""An approved AI use case is being tracked against its business case.

USE CASE: {json.dumps(uc, default=str)}
REALIZATION SUMMARY (authoritative numbers): {json.dumps(summary, default=str)}
MONTHLY ACTUALS: {json.dumps(actuals, default=str)}
RULE-BASED FINDINGS: {json.dumps(base)}

Diagnose why realized value differs from plan, using Lean and change management thinking.
Return JSON: {{"causes": ["likely root causes, most likely first"], "actions": ["specific corrective actions with an owner role"], "narrative": "short markdown paragraph for the sponsor"}}"""
        try:
            result = self.llm_client.generate_json(prompt, max_tokens=3000)
            return {
                "causes": [str(c) for c in _as_list(result.get("causes"))] or base["causes"],
                "actions": [str(a) for a in _as_list(result.get("actions"))] or base["actions"],
                "narrative": str(result.get("narrative", "") or ""),
                "source": "AI",
            }
        except Exception as e:
            base["narrative"] = f"LLM diagnosis failed, showing rule-based findings: {e}"
            return base

    def get_provider_info(self) -> Dict[str, Any]:
        return {
            "name": self.provider_name,
            "type": "LLM Enhanced",
            "provider": self.llm_provider,
            "available": self.llm_available,
            "description": "Rule-based assessment plus AI judgment, challenges and tailored narratives",
        }


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []
