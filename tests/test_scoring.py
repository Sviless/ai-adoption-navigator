import unittest

from src.sample_data import get_sample_use_cases, new_use_case
from src.scoring import (
    adoption_readiness_score, assess_use_case, feasibility_score, quadrant, value_score,
)


def sample(name):
    return next(uc for uc in get_sample_use_cases() if uc["name"] == name)


class TestScores(unittest.TestCase):
    def test_scores_stay_in_range(self):
        extremes = [
            new_use_case(tasks_per_month=10**6, minutes_per_task=600, time_reduction_pct=100,
                         strategic_alignment=5, customer_impact=5, data_quality=5,
                         integration_complexity=1, inhouse_skills=5, solution_maturity=5),
            new_use_case(strategic_alignment=1, customer_impact=1, data_quality=1,
                         integration_complexity=5, inhouse_skills=1, solution_maturity=1,
                         data_sensitivity="Personal data"),
        ]
        for uc in extremes:
            for score in (value_score(uc), feasibility_score(uc), adoption_readiness_score(uc)):
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 100)

    def test_max_readiness(self):
        uc = new_use_case(sponsor_committed=True, process_standardized=True, has_training_plan=True,
                          has_champions=True, user_involvement=5)
        self.assertEqual(adoption_readiness_score(uc), 100)

    def test_quadrants(self):
        self.assertEqual(quadrant(80, 80), "Quick Win")
        self.assertEqual(quadrant(80, 20), "Strategic Bet")
        self.assertEqual(quadrant(20, 80), "Fill-in")
        self.assertEqual(quadrant(20, 20), "Avoid")


class TestGate(unittest.TestCase):
    def test_ticket_triage_is_go(self):
        self.assertEqual(assess_use_case(sample("Support Ticket Triage"))["gate"]["gate"], "Go")

    def test_unstandardized_process_must_be_fixed_first(self):
        gate = assess_use_case(sample("Resume Screening"))["gate"]
        self.assertEqual(gate["gate"], "Fix process first")
        # Critical governance flags are still surfaced
        self.assertTrue(any("human decides" in c for c in gate["conditions"]))

    def test_prohibited_practice_stops(self):
        uc = sample("Support Ticket Triage")
        uc["special_categories"] = ["Social scoring of people"]
        self.assertEqual(assess_use_case(uc)["gate"]["gate"], "Stop")

    def test_no_value_case_stops(self):
        uc = sample("Support Ticket Triage")
        uc["license_cost_annual"] = 10**7
        self.assertEqual(assess_use_case(uc)["gate"]["gate"], "Stop")

    def test_low_readiness_needs_conditions(self):
        self.assertEqual(assess_use_case(sample("Sales Email Drafting"))["gate"]["gate"], "Pilot with conditions")


if __name__ == "__main__":
    unittest.main()
