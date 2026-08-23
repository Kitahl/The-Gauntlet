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

import foil_calibration as fc  # noqa: E402
import foil_layer2 as fl2  # noqa: E402
import foil_profile as fp  # noqa: E402

FORBIDDEN = {"answer", "correct", "correct_answer", "correct_index", "key"}


def forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN:
                return str(key)
            found = forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = forbidden_key(child)
            if found:
                return found
    return None


class FoilLayer2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EGR_FOIL_PROFILE_DIR": self.temp.name}, clear=False)
        self.env.start()
        profile = fp.new_profile("stranger")
        fp.save(profile)
        fp.activate("stranger")

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_standard_session_is_blank_and_answer_free(self) -> None:
        session = fl2.build(fp.load(), seed=42, mode="standard")
        self.assertEqual(len(session["objective_items"]), 24)
        self.assertEqual(len(session["open_probes"]), 3)
        self.assertEqual(len(session["self_estimate_facets"]), 12)
        self.assertTrue(
            all(
                row["choice"] is None
                for row in session["response_schema"]["objective"].values()
            )
        )
        self.assertIsNone(forbidden_key(session["objective_items"]))

    def test_every_generated_item_has_exactly_one_derived_answer(self) -> None:
        for seed in range(100):
            session = fl2.build(fp.load(), seed=seed)
            for item in session["objective_items"]:
                expected = fl2.answer(item)
                self.assertIn(expected, item["options"])
                self.assertEqual(item["options"].count(expected), 1)
                self.assertEqual(len(item["options"]), len(set(item["options"])))

    def test_short_mode_is_screen_not_classification(self) -> None:
        session = fl2.build(fp.load(), seed=2, mode="short")
        self.assertEqual(len(session["objective_items"]), 12)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fl2.answer(item)
        report = fl2.score(session, responses)
        self.assertTrue(
            all(
                row["classification"] == "INSUFFICIENT_EVIDENCE"
                for row in report["facet_evidence"].values()
            )
        )

    def test_standard_perfect_independent_is_not_load_bearing(self) -> None:
        """Previously asserted PROMISING_STRENGTH for a two-item-per-facet screen."""
        session = fl2.build(fp.load(), seed=3)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fl2.answer(item)
            responses["objective"][item["id"]]["confidence"] = 100
        report = fl2.score(session, responses)
        for row in report["facet_evidence"].values():
            self.assertEqual(row["classification"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(row["screen_signal"], "ALL_CORRECT")
        self.assertTrue(
            all(
                entry["action"].startswith("confirm with harder")
                for entry in report["follow_up"]
            )
        )
        self.assertEqual(report["calibration"]["brier"], 0.0)
        self.assertIn("cannot certify OWNED", report["ownership_ceiling"])

    def test_assisted_success_does_not_create_promising_strength(self) -> None:
        session = fl2.build(fp.load(), seed=4)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fl2.answer(item)
            responses["objective"][item["id"]]["assistance"] = "full"
        report = fl2.score(session, responses)
        self.assertTrue(
            all(
                row["classification"] == "INSUFFICIENT_EVIDENCE"
                for row in report["facet_evidence"].values()
            )
        )

    def test_apply_to_profile_records_verified_microprobes_without_open_text(self) -> None:
        profile = fp.load()
        session = fl2.build(profile, seed=5)
        responses = session["response_schema"]
        responses["open"]["design-open"]["response"] = (
            "PRIVATE OPEN RESPONSE SHOULD NOT BE STORED"
        )
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fl2.answer(item)
        report = fl2.score(session, responses)
        fl2.apply_to_profile(profile, report)
        fp.save(profile)
        saved = fp.load()
        serialized = json.dumps(saved)
        self.assertNotIn("PRIVATE OPEN RESPONSE SHOULD NOT BE STORED", serialized)
        deep = saved["deep_calibration"]
        self.assertEqual(len(deep["probe_history"]), 24)
        for facet in session["self_estimate_facets"]:
            # Two screen items per facet are recorded in full but, as with
            # Layer 1, cannot reach a load-bearing verdict. This previously
            # asserted PROMISING_STRENGTH.
            self.assertEqual(
                deep["facet_evidence"][facet]["classification"],
                "INSUFFICIENT_EVIDENCE",
            )
            self.assertEqual(
                deep["facet_evidence"][facet]["independent_verified_pass"], 2
            )

    def test_layer2_screen_alone_cannot_satisfy_deep_profile_gate(self) -> None:
        profile = fp.load()
        session = fl2.build(profile, seed=6)
        responses = session["response_schema"]
        for item in session["objective_items"]:
            responses["objective"][item["id"]]["choice"] = fl2.answer(item)
            responses["objective"][item["id"]]["confidence"] = 80
        report = fl2.score(session, responses)
        fl2.apply_to_profile(profile, report)
        state = fc.maturity(profile)
        self.assertNotEqual(state["status"], "DEEP_PROFILE_READY")
        self.assertIn("distinct_domains", state["missing"])
        self.assertIn("real_work_samples", state["missing"])

    def test_prompt_facet_relevance_does_not_change_competence(self) -> None:
        profile = fp.load()
        facets = fl2.infer_facets(
            "Please formalize this proof claim and red team the evidence before we run tests"
        )
        self.assertIn("formalization_precision", facets)
        self.assertIn("error_detection", facets)
        self.assertIn("evidence_discipline", facets)
        self.assertIn("implementation_execution", facets)
        fl2.mark_facet_relevance(profile, facets)
        deep = profile["deep_calibration"]
        for facet in facets:
            self.assertNotIn(facet, deep.get("facet_evidence", {}))
            self.assertGreaterEqual(deep["facet_relevance"][facet]["mentions"], 1)


if __name__ == "__main__":
    unittest.main()
