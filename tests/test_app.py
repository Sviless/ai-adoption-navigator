"""Headless UI smoke tests with Streamlit's AppTest (Template mode, temporary data folder)"""

import os
import tempfile
import unittest
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def click(at: AppTest, label_contains: str) -> AppTest:
    return next(b for b in at.button if label_contains in b.label).click().run()


class TestAppSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NAVIGATOR_DATA_DIR"] = self.tmp.name
        st.cache_resource.clear()  # get_db() is cached across AppTest runs in this process
        self.at = AppTest.from_file(APP, default_timeout=60)
        self.at.run()
        self.assertFalse(self.at.exception)

    def tearDown(self):
        st.cache_resource.clear()
        os.environ.pop("NAVIGATOR_DATA_DIR", None)
        self.tmp.cleanup()

    def test_load_samples_and_render_every_use_case(self):
        at = click(self.at, "Load sample portfolio")
        self.assertFalse(at.exception)
        self.assertTrue(any("Loaded 6 sample use cases" in s.value for s in at.success))

        self.assertEqual(len(at.selectbox(key="selected_id").options), 7)  # "New" + 6 samples
        for use_case_id in range(1, 7):
            at.selectbox(key="selected_id").set_value(use_case_id).run()
            self.assertFalse(at.exception, f"Exception for use case {use_case_id}")
            self.assertEqual(at.text_input(key="f_name").value, at.header[0].value)

    def test_welcome_screen_then_portfolio_and_tracker_views(self):
        self.assertTrue(any("Welcome" in h.value for h in self.at.header))
        at = click(self.at, "Load sample portfolio")
        self.assertEqual(at.segmented_control(key="view").value, "Portfolio")
        self.assertEqual(at.header[0].value, "AI portfolio overview")
        at.segmented_control(key="view").set_value("Value tracker").run()
        self.assertFalse(at.exception)
        # Default tracked use case is the first sample (Support Ticket Triage, on track)
        at = click(at, "Diagnose")
        self.assertFalse(at.exception)

    def test_save_governance_evidence_and_render_brief(self):
        at = click(self.at, "Load sample portfolio")
        at.selectbox(key="selected_id").set_value(1).run()  # Support Ticket Triage (has sample evidence)
        self.assertTrue(any("Governance 67% ready" in m.value for m in at.markdown))
        at = click(at, "Save evidence")
        self.assertFalse(at.exception)
        self.assertTrue(any("Governance evidence saved" in s.value for s in at.success))
        # Saving without edits must not change readiness (dates and blanks round-trip cleanly)
        self.assertTrue(any("Governance 67% ready" in m.value for m in at.markdown))
        self.assertTrue(at.get("html"))  # executive brief preview rendered

    def test_new_use_case_validation(self):
        self.at = click(self.at, "Start a new use case")
        self.at.text_input(key="f_name").set_value("Invoice matching")
        at = click(self.at, "Save and assess")
        self.assertFalse(at.exception)
        self.assertTrue(at.error)  # process description and volume are missing

    def test_save_new_use_case(self):
        self.at = click(self.at, "Start a new use case")
        self.at.text_input(key="f_name").set_value("Invoice matching")
        self.at.text_area(key="f_process_description").set_value("AP clerks match invoices to purchase orders")
        self.at.number_input(key="f_tasks_per_month").set_value(2000)
        self.at.number_input(key="f_minutes_per_task").set_value(6)
        at = click(self.at, "Save and assess")
        self.assertFalse(at.exception)
        self.assertEqual(at.header[0].value, "Invoice matching")
        self.assertTrue(any("Saved and assessed" in s.value for s in at.success))


if __name__ == "__main__":
    unittest.main()
