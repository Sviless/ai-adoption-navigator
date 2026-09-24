import base64
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from src.brief import build_brief_html
from src.db import Database
from src.governance import CHECKLIST_ITEMS, assess_governance, evidence_readiness
from src.providers import TemplateProvider
from src.sample_data import get_sample_evidence, get_sample_use_cases


def sample(name):
    return next(uc for uc in get_sample_use_cases() if uc["name"] == name)


class TestEvidenceReadiness(unittest.TestCase):
    def setUp(self):
        self.checklist = assess_governance(sample("Support Ticket Triage"))["checklist"]

    def test_no_evidence_means_zero_readiness(self):
        r = evidence_readiness(self.checklist, {})
        self.assertEqual(r["readiness_pct"], 0)
        self.assertEqual(r["total"], len(self.checklist))
        self.assertTrue(all(row["status"] == "Not started" for row in r["rows"]))

    def test_not_applicable_is_excluded_and_overdue_detected(self):
        c = [item["control"] for item in self.checklist]
        evidence = {
            c[0]: {"status": "Done"},
            c[1]: {"status": "Not applicable"},
            c[2]: {"status": "In progress", "owner": "Ana", "due_date": "2026-01-31"},
        }
        r = evidence_readiness(self.checklist, evidence, today=date(2026, 9, 1))
        self.assertEqual(r["total"], len(self.checklist) - 1)
        self.assertEqual(r["done"], 1)
        self.assertAlmostEqual(r["readiness_pct"], 100 / (len(self.checklist) - 1))
        self.assertEqual(r["overdue"], 1)

    def test_all_done_is_ready(self):
        evidence = {item["control"]: {"status": "Done"} for item in self.checklist}
        self.assertEqual(evidence_readiness(self.checklist, evidence)["readiness_pct"], 100)

    def test_sample_evidence_matches_real_controls(self):
        known = {item["control"] for item in CHECKLIST_ITEMS}
        for rows in get_sample_evidence().values():
            for row in rows:
                self.assertIn(row["control"], known)


class TestEvidenceStorage(unittest.TestCase):
    def test_round_trip_and_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "t.db")
            uc_id = db.save_use_case(sample("Support Ticket Triage"))
            db.save_evidence(uc_id, [{"control": "X", "status": "In progress", "owner": "Ana",
                                      "due_date": date(2026, 10, 1), "evidence": ""}])
            db.save_evidence(uc_id, [{"control": "X", "status": "Done", "owner": "Ana",
                                      "due_date": None, "evidence": "doc.pdf"}])
            record = db.get_evidence(uc_id)["X"]
            self.assertEqual(record["status"], "Done")
            self.assertEqual(record["evidence"], "doc.pdf")
            self.assertEqual(record["due_date"], "")
            db.delete_use_case(uc_id)
            self.assertEqual(db.get_evidence(uc_id), {})

    def test_load_samples_adds_evidence_to_existing_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "t.db")
            db.load_samples(get_sample_use_cases(), {}, {})  # older version: no evidence
            db.load_samples(get_sample_use_cases(), {}, get_sample_evidence())
            triage_id = next(uc["id"] for uc in db.list_use_cases() if uc["name"] == "Support Ticket Triage")
            self.assertTrue(db.get_evidence(triage_id))


class TestBrief(unittest.TestCase):
    def test_brief_contains_decision_and_charts(self):
        uc = sample("Resume Screening")
        package = TemplateProvider().assess_use_case(uc)
        html = build_brief_html(uc, package)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("Decision: Fix process first", html)

    def test_charts_are_data_uri_images_with_valid_svg(self):
        # st.html strips inline <svg>, so every chart must be an <img> data URI (regression: blank charts)
        uc = sample("Support Ticket Triage")
        package = TemplateProvider().assess_use_case(uc)
        evidence = {row["control"]: row for row in get_sample_evidence()["Support Ticket Triage"]}
        readiness = evidence_readiness(package["assessment"]["governance"]["checklist"], evidence)
        html = build_brief_html(uc, package, readiness, standalone=False)
        self.assertNotIn("<svg", html)
        images = re.findall(r'src="data:image/svg\+xml;base64,([^"]+)"', html)
        self.assertEqual(len(images), 5)  # scores, payback, tier, readiness, time freed
        for encoded in images:
            root = ET.fromstring(base64.b64decode(encoded))  # raises if not well-formed XML
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_brief_escapes_user_and_llm_text(self):
        uc = sample("Code Review Assistant")
        uc["name"] = "<script>alert(1)</script>"
        package = TemplateProvider().assess_use_case(uc)
        package["sections"]["executive_summary"] = "**Bold** <img src=x onerror=alert(1)>"
        html = build_brief_html(uc, package)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)  # injected tag must not survive (chart <img>s are expected)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("<strong>Bold</strong>", html)

    def test_brief_shows_governance_readiness(self):
        uc = sample("Support Ticket Triage")
        package = TemplateProvider().assess_use_case(uc)
        evidence = {row["control"]: row for row in get_sample_evidence()["Support Ticket Triage"]}
        readiness = evidence_readiness(package["assessment"]["governance"]["checklist"], evidence)
        html = build_brief_html(uc, package, readiness)
        self.assertIn(f"{readiness['readiness_pct']:.0f}%", html)


if __name__ == "__main__":
    unittest.main()
