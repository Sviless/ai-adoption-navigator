import unittest

from src.governance import assess_governance, classify_risk_tier
from src.sample_data import get_sample_use_cases, new_use_case


def sample(name):
    return next(uc for uc in get_sample_use_cases() if uc["name"] == name)


class TestRiskTier(unittest.TestCase):
    def test_resume_screening_is_high_risk(self):
        self.assertEqual(classify_risk_tier(sample("Resume Screening"))["tier"], "High")

    def test_internal_knowledge_search_is_minimal(self):
        self.assertEqual(classify_risk_tier(sample("Internal Knowledge Search"))["tier"], "Minimal")

    def test_customer_facing_is_limited(self):
        self.assertEqual(classify_risk_tier(sample("Sales Email Drafting"))["tier"], "Limited")

    def test_prohibited_practice_is_unacceptable(self):
        uc = new_use_case(special_categories=["Emotion recognition in the workplace"])
        self.assertEqual(classify_risk_tier(uc)["tier"], "Unacceptable")


class TestChecklist(unittest.TestCase):
    def test_high_tier_requires_bias_testing(self):
        controls = [c["control"] for c in assess_governance(sample("Resume Screening"))["checklist"]]
        self.assertTrue(any("Bias" in c for c in controls))
        self.assertTrue(any("DPIA" in c for c in controls))

    def test_minimal_tier_has_no_bias_testing(self):
        controls = [c["control"] for c in assess_governance(sample("Internal Knowledge Search"))["checklist"]]
        self.assertFalse(any("Bias" in c for c in controls))

    def test_sensitive_data_triggers_security_testing_below_limited(self):
        uc = new_use_case(data_sensitivity="Confidential")
        controls = [c["control"] for c in assess_governance(uc)["checklist"]]
        self.assertTrue(any("prompt injection" in c for c in controls))

    def test_automated_people_decisions_flagged_critical(self):
        flags = assess_governance(sample("Resume Screening"))["flags"]
        self.assertTrue(any(f["severity"] == "Critical" for f in flags))


if __name__ == "__main__":
    unittest.main()
