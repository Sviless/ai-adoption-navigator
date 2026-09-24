"""LLM Enhanced provider with a fake LLM client - no network or API key needed"""

import json
import unittest
from unittest import mock

from src.providers import EnhancedLLMProvider, TemplateProvider
from src.sample_data import get_sample_use_cases


def sample(name):
    return next(uc for uc in get_sample_use_cases() if uc["name"] == name)


FAKE_INSIGHTS = {
    "executive_summary": "AI summary.",
    "assumption_challenges": [{"severity": "High", "check": "Adoption of 70% is optimistic for recruiters."}],
    "governance_rationale": "Hiring decisions are high risk.",
    "key_controls": ["Human review of every rejection"],
    "workforce_narrative": "Recruiters shift to candidate engagement.",
    "adoption_narrative": "Co-design with recruiters.",
    "pilot_adjustments": ["Measure false rejection rate by group"],
    "additional_risks": [{"risk": "Candidate complaints", "category": "Reputation", "severity": "Medium", "mitigation": "Appeal process"}],
    "linkedin_statement": "AI statement.",
}


def make_provider(response=None, error=None):
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        provider = EnhancedLLMProvider(provider="claude", model="claude-opus-5")
    fake = mock.Mock(side_effect=error) if error else mock.Mock(return_value=response)
    provider.llm_client.generate = fake
    return provider


class TestEnhancedProvider(unittest.TestCase):
    def test_llm_insights_merge_without_changing_numbers(self):
        uc = sample("Resume Screening")
        template = TemplateProvider().assess_use_case(uc)
        enhanced = make_provider(json.dumps(FAKE_INSIGHTS)).assess_use_case(uc)

        self.assertTrue(enhanced["llm_enhanced"])
        self.assertEqual(enhanced["assessment"], template["assessment"])  # numbers untouched
        self.assertEqual(enhanced["sections"]["executive_summary"], "AI summary.")
        self.assertTrue(any(c.get("source") == "AI" for c in enhanced["assumption_checks"]))
        self.assertTrue(any(r.get("source") == "AI" for r in enhanced["risks"]))
        self.assertEqual(enhanced["ai_insights"]["key_controls"], ["Human review of every rejection"])

    def test_falls_back_to_template_on_llm_error(self):
        uc = sample("Resume Screening")
        result = make_provider(error=Exception("rate limited")).assess_use_case(uc)
        self.assertFalse(result["llm_enhanced"])
        self.assertIn("rate limited", result["llm_error"])
        self.assertEqual(result["sections"]["executive_summary"],
                         TemplateProvider().assess_use_case(uc)["sections"]["executive_summary"])

    def test_falls_back_on_invalid_json(self):
        result = make_provider("not json at all").assess_use_case(sample("Code Review Assistant"))
        self.assertFalse(result["llm_enhanced"])

    def test_no_api_key_means_template_output(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            provider = EnhancedLLMProvider(provider="openai")
        self.assertFalse(provider.llm_available)
        self.assertFalse(provider.assess_use_case(sample("Code Review Assistant"))["llm_enhanced"])

    def test_extracted_fields_are_sanitized(self):
        response = json.dumps({"fields": {
            "tasks_per_month": "1200.0", "data_sensitivity": "Top secret", "people_decisions": "yes",
            "strategic_alignment": 9, "unknown_field": "x"}, "notes": [], "missing": []})
        fields = make_provider(response).extract_use_case("some text")["fields"]
        self.assertEqual(fields["tasks_per_month"], 1200)
        self.assertIsInstance(fields["tasks_per_month"], int)
        self.assertNotIn("data_sensitivity", fields)  # invalid choice dropped
        self.assertTrue(fields["people_decisions"])
        self.assertEqual(fields["strategic_alignment"], 5)  # clamped
        self.assertNotIn("unknown_field", fields)


class TestTemplateExtraction(unittest.TestCase):
    def test_keyword_extraction(self):
        result = TemplateProvider().extract_use_case(
            "Recruiters get 300 applications per week and spend 4 minutes on each resume. "
            "The vendor tool would automatically reject weak candidates.")
        fields = result["fields"]
        self.assertTrue(fields["people_decisions"])
        self.assertEqual(fields["decision_type"], "Automated - AI decides")
        self.assertEqual(fields["minutes_per_task"], 4)
        self.assertEqual(fields["tasks_per_month"], 1299)


if __name__ == "__main__":
    unittest.main()
