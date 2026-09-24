import unittest

from src.roi import calculate_roi, potential_annual_hours, realization_summary
from src.sample_data import new_use_case


def simple_case(**overrides):
    # 100 tasks/month x 60 min x 50% reduction = 600 potential hours/year
    base = dict(
        tasks_per_month=100, minutes_per_task=60, time_reduction_pct=50, hourly_cost=100,
        license_cost_annual=10000, run_cost_annual=2000, implementation_cost=12000,
    )
    base.update(overrides)
    return new_use_case(**base)


class TestRoi(unittest.TestCase):
    def test_potential_hours(self):
        self.assertAlmostEqual(potential_annual_hours(simple_case()), 600)

    def test_expected_scenario_matches_hand_calculation(self):
        expected = calculate_roi(simple_case())["Expected"]
        # 600 h x 0.7 adoption x 0.8 realization = 336 h -> $33,600
        self.assertAlmostEqual(expected["annual_hours_saved"], 336)
        self.assertAlmostEqual(expected["annual_benefit"], 33600)
        # 3 x 33,600 - 3 x 12,000 - 12,000
        self.assertAlmostEqual(expected["net_3yr"], 52800)
        # 12,000 / ((33,600 - 12,000) / 12) = 6.67 months
        self.assertAlmostEqual(expected["payback_months"], 6.6667, places=3)

    def test_no_payback_when_running_cost_exceeds_benefit(self):
        roi = calculate_roi(simple_case(license_cost_annual=100000))
        self.assertIsNone(roi["Conservative"]["payback_months"])
        self.assertLess(roi["Conservative"]["net_3yr"], 0)

    def test_scenarios_are_ordered(self):
        roi = calculate_roi(simple_case())
        self.assertLess(roi["Conservative"]["annual_benefit"], roi["Expected"]["annual_benefit"])
        self.assertLess(roi["Expected"]["annual_benefit"], roi["Optimistic"]["annual_benefit"])


class TestRealization(unittest.TestCase):
    def test_value_leakage_flag(self):
        # Promised = 336 h / 12 = 28 h per month; actual 14 h = 50%
        actuals = [{"month": "2026-01", "hours_saved": 14, "adoption_pct": 40, "actual_cost": 1000},
                   {"month": "2026-02", "hours_saved": 14, "adoption_pct": 30, "actual_cost": 1000}]
        summary = realization_summary(simple_case(), actuals)
        self.assertAlmostEqual(summary["realization_pct"], 50)
        self.assertEqual(summary["status"], "Value leakage")
        self.assertEqual(summary["adoption_trend"], "Falling")

    def test_on_track(self):
        actuals = [{"month": "2026-01", "hours_saved": 30, "adoption_pct": 70, "actual_cost": 1000},
                   {"month": "2026-02", "hours_saved": 28, "adoption_pct": 80, "actual_cost": 1000}]
        self.assertEqual(realization_summary(simple_case(), actuals)["status"], "On track")

    def test_too_early_with_one_month(self):
        actuals = [{"month": "2026-01", "hours_saved": 1, "adoption_pct": 5, "actual_cost": 0}]
        self.assertEqual(realization_summary(simple_case(), actuals)["status"], "Too early")


if __name__ == "__main__":
    unittest.main()
