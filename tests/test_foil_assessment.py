from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_assessment as fa  # noqa: E402
import foil_profile as fp  # noqa: E402

FORBIDDEN_KEY_NAMES = {"answer", "correct", "correct_answer", "correct_index", "key"}


def _forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEY_NAMES:
                return str(key)
            found = _forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _forbidden_key(child)
            if found:
                return found
    return None


class FoilAssessmentTests(unittest.TestCase):
    def test_session_is_blank_and_has_no_answer_fields(self) -> None:
        session = fa.build(seed=42)
        responses = session["response_schema"]
        self.assertEqual(len(session["objective_items"]), 20)
        self.assertTrue(
            all(item["choice"] is None for item in responses["objective"].values())
        )
        self.assertTrue(all(value is None for value in responses["context"].values()))
        self.assertTrue(
            all(value is None for value in responses["self_estimates"].values())
        )
        for item in session["objective_items"]:
            self.assertIsNone(_forbidden_key(item))

    def test_generated_options_have_exactly_one_derived_answer(self) -> None:
        for seed in range(500):
            session = fa.build(seed=seed)
            for item in session["objective_items"]:
                expected = fa.answer(item)
                self.assertIn(expected, item["options"])
                self.assertEqual(item["options"].count(expected), 1)
                self.assertEqual(len(item["options"]), len(set(item["options"])))

    def test_unanswered_is_insufficient_not_gap(self) -> None:
        session = fa.build(seed=3)
        report = fa.score(session, session["response_schema"])
        self.assertTrue(
            all(
                row["classification"] == "INSUFFICIENT_EVIDENCE"
                for row in report["domain_evidence"].values()
            )
        )

    def test_assisted_success_does_not_become_strength(self) -> None:
        session = fa.build(seed=4)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fa.answer(item)
            responses["objective"][item["id"]]["assistance"] = "full"
        report = fa.score(session, responses)
        self.assertTrue(
            all(
                row["classification"] == "INSUFFICIENT_EVIDENCE"
                for row in report["domain_evidence"].values()
            )
        )

    def test_perfect_independent_screen_is_only_promising(self) -> None:
        session = fa.build(seed=5)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fa.answer(item)
            responses["objective"][item["id"]]["confidence"] = 100
        report = fa.score(session, responses)
        self.assertTrue(
            all(
                row["classification"] == "PROMISING_STRENGTH"
                for row in report["domain_evidence"].values()
            )
        )
        self.assertEqual(report["calibration"]["brier"], 0.0)
        self.assertIn("cannot certify OWNED", report["ownership_ceiling"])

    def test_setup_adds_optional_and_custom_domains_without_scoring_them(self) -> None:
        session = fa.build(
            seed=6,
            setup_text="I work in quantum physics, materials science, UI design, and machine learning",
            extra_domains=["theorem_proving"],
        )
        for domain in (
            "physics",
            "chemistry_materials",
            "design_ux",
            "data_ml",
            "theorem_proving",
        ):
            self.assertIn(domain, session["selected_domains"])
        report = fa.score(session, session["response_schema"])
        self.assertFalse(report["domain_evidence"]["theorem_proving"]["screened"])
        self.assertEqual(
            report["domain_evidence"]["theorem_proving"]["classification"],
            "INSUFFICIENT_EVIDENCE",
        )

    def test_apply_report_updates_saved_profile_without_raw_answers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"EGR_FOIL_PROFILE_DIR": directory},
                clear=False,
            ):
                profile = fp.new_profile("alice")
                fp.save(profile)
                session = fa.build(seed=7, extra_domains=["theorem_proving"])
                responses = session["response_schema"]
                responses["context"]["goal"] = "Improve research reasoning"
                responses["context"]["other_domains"] = "robotics, control theory"
                responses["self_estimates"]["theorem_proving"] = 4
                for item in session["objective_items"]:
                    responses["objective"][item["id"]]["choice"] = fa.answer(item)
                report = fa.score(session, responses)
                fa.apply_to_profile("alice", report)
                saved = fp.load("alice")
                self.assertIn("theorem_proving", saved["domains"])
                self.assertIn("robotics", saved["domains"])
                self.assertIn("control_theory", saved["domains"])
                serialized = json.dumps(saved)
                for item in session["objective_items"]:
                    self.assertNotIn(item["prompt"], serialized)


if __name__ == "__main__":
    unittest.main()
