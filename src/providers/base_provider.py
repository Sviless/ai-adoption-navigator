"""
Base provider interface for AI use case assessment
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseProvider(ABC):
    """Abstract base class for assessment providers"""

    def __init__(self):
        self.provider_name = "Base Provider"

    @abstractmethod
    def assess_use_case(self, uc: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the full assessment package for one use case"""

    @abstractmethod
    def extract_use_case(self, text: str) -> Dict[str, Any]:
        """Suggest intake fields from free text: {'fields', 'notes', 'missing'}"""

    @abstractmethod
    def diagnose_value_gap(self, uc: Dict[str, Any], summary: Dict[str, Any],
                           actuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Explain why realized value differs from plan: {'causes', 'actions', 'narrative'}"""

    def get_provider_info(self) -> Dict[str, Any]:
        return {"name": self.provider_name, "type": self.__class__.__name__}
