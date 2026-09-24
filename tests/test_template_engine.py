import unittest

from src.roi import calculate_roi, cumulative_cash_flow
from src.sample_data import get_sample_use_cases, new_use_case
from src.scoring import assess_use_case
from src.template_engine import TemplateEngine


def sample(name):
    return next(uc for uc in get_sample_use_cases() if uc["name"] == name)


class TestTemplateFixes(unittest.TestCase):
    def setUp(self):
        self.engine = TemplateEngine()

    def test_article_before_vowel_quadrant(self):
        uc = sample("Resume Screening")  # quadrant "Avoid"
        text = self.engine.executive_summary(uc, assess_use_case(uc))
        self.assertIn("assessed as an **Avoid**", text)

    def test_oversight_gap_shown_for_minimal_tier(self):
        uc = sample("Internal Knowledge Search")
        uc["human_oversight"] = "None"
        self.assertIn("recommended minimum", self.engine.hitl_design(uc, assess_use_case(uc)))

    def test_no_oversight_gap_when_above_minimum(self):
        uc = sample("Code Review Assistant")  # Limited tier, Review before action
        self.assertNotIn("recommended minimum", self.engine.hitl_design(uc, assess_use_case(uc)))

    def test_unacceptable_tier_summary(self):
        uc = new_use_case(name="X", special_categories=["Social scoring of people"])
        text = self.engine.governance_summary(uc, assess_use_case(uc))
        self.assertIn("prohibited practice", text)


class TestCashFlow(unittest.TestCase):
    def test_cash_flow_crosses_zero_at_payback_month(self):
        roi = calculate_roi(sample("Support Ticket Triage"))
        rows = [r for r in cumulative_cash_flow(roi) if r["Scenario"] == "Expected"]
        payback = roi["Expected"]["payback_months"]
        self.assertLess(rows[int(payback)]["Cumulative net value"], 0)
        self.assertGreaterEqual(rows[int(payback) + 1]["Cumulative net value"], 0)
        self.assertAlmostEqual(rows[36]["Cumulative net value"], roi["Expected"]["net_3yr"], places=6)


if __name__ == "__main__":
    unittest.main()
