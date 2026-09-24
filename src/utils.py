"""
Formatting helpers
"""

from typing import Any, Optional


def money(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def hours(value: float) -> str:
    return f"{value:,.0f} h"


def pct(value: Optional[float], decimals: int = 0) -> str:
    return "n/a" if value is None else f"{value:.{decimals}f}%"


def months(value: Optional[float]) -> str:
    if value is None:
        return "No payback"
    return f"{value:.1f} months"


def yes_no(value: Any) -> str:
    return "Yes" if value else "No"


def bullet_list(items) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"
