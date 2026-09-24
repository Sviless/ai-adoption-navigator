"""
Template Provider - Rule-based assessment (no API required)
Default mode for the application
"""

from typing import Any, Dict, List
from src.providers.base_provider import BaseProvider
from src.template_engine import TemplateEngine


class TemplateProvider(BaseProvider):
    """Template-based provider using rule-based logic"""

    def __init__(self):
        super().__init__()
        self.provider_name = "Template Engine"
        self.engine = TemplateEngine()

    def assess_use_case(self, uc: Dict[str, Any]) -> Dict[str, Any]:
        package = self.engine.build_package(uc)
        package["mode"] = self.provider_name
        return package

    def extract_use_case(self, text: str) -> Dict[str, Any]:
        return self.engine.extract_use_case(text)

    def diagnose_value_gap(self, uc: Dict[str, Any], summary: Dict[str, Any],
                           actuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.engine.diagnose_value_gap(uc, summary, actuals)

    def get_provider_info(self) -> Dict[str, Any]:
        return {
            "name": self.provider_name,
            "type": "Template Engine",
            "description": "Rule-based scoring, governance rules and templates - runs fully offline",
            "requires_api": False,
        }
