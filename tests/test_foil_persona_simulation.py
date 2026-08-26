from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_persona_simulation as simulation  # noqa: E402


class PersonaSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "benchmarks" / "fixtures" / "foil_personas_v1.json"
        cls.document = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_report_is_deterministic_and_zero_cost(self) -> None:
        first = simulation.run(self.document)
        second = simulation.run(self.document)
        self.assertEqual(first, second)
        self.assertEqual(first["personas"], 6)
        self.assertEqual(first["sessions"], 90)
        self.assertTrue(all(value == 0 for value in first["cost_and_authority"].values()))
        self.assertEqual(len(first["report_sha256"]), 64)

    def test_ownership_and_claim_personas_never_fool_estimator(self) -> None:
        report = simulation.run(self.document)
        self.assertEqual(report["metrics"]["fooled_rate"], 0.0)
        by_id = {row["persona_id"]: row for row in report["persona_summaries"]}
        self.assertEqual(by_id["copy-paster"]["load_bearing_n"], 0.0)
        self.assertNotEqual(by_id["confident-wrong"]["final_classification"], "PROMISING_STRENGTH")
        self.assertNotEqual(by_id["lucky-unverified"]["final_classification"], "PROMISING_STRENGTH")

    def test_fast_learner_fades_and_plateau_stays_at_smallest_effective_rung(self) -> None:
        report = simulation.run(self.document)
        by_id = {row["persona_id"]: row for row in report["persona_summaries"]}
        self.assertEqual(by_id["fast-learner"]["final_assistance"], "A0_INDEPENDENT")
        self.assertEqual(by_id["plateau"]["final_assistance"], "A2_SCAFFOLD")
        self.assertEqual(by_id["copy-paster"]["final_assistance"], "A4_DIRECT_SOLVE")
        self.assertEqual(report["metrics"]["fade_correct_rate"], 1.0)

    def test_ladder_escalates_one_rung_and_preserves_floor_through_probe(self) -> None:
        report = simulation.run(self.document)
        copy_rows = [row for row in report["raw_rows"] if row["persona_id"] == "copy-paster"]
        self.assertEqual(
            [row["selected_assistance"] for row in copy_rows[:5]],
            ["A1_MICRO_HINT", "A2_SCAFFOLD", "A0_INDEPENDENT", "A3_PARTIAL_WORKED", "A4_DIRECT_SOLVE"],
        )
        self.assertEqual(copy_rows[2]["minimum_floor_before"], "A3_PARTIAL_WORKED")
        self.assertEqual(copy_rows[2]["minimum_floor_after"], "A3_PARTIAL_WORKED")

    def test_claimed_strength_is_not_estimator_input(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["personas"][2]["claimed_strength"] = False
        original = simulation.run(self.document)
        counterfactual = simulation.run(changed)
        self.assertEqual(original["raw_rows"], counterfactual["raw_rows"])
        original_summary = dict(original["persona_summaries"][2])
        changed_summary = dict(counterfactual["persona_summaries"][2])
        original_summary.pop("claimed_strength")
        changed_summary.pop("claimed_strength")
        self.assertEqual(original_summary, changed_summary)

    def test_unknown_fields_and_inconsistent_ground_truth_fail_closed(self) -> None:
        malformed = copy.deepcopy(self.document)
        malformed["personas"][0]["prompt"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            simulation.run(malformed)
        malformed = copy.deepcopy(self.document)
        malformed["personas"][0]["independent_outcomes"][0] = 1
        with self.assertRaisesRegex(TypeError, "boolean list"):
            simulation.run(malformed)
        malformed = copy.deepcopy(self.document)
        malformed["personas"][0]["minimum_effective_assistance"][0] = "A0_INDEPENDENT"
        with self.assertRaisesRegex(ValueError, "conflicts with minimum assistance"):
            simulation.run(malformed)

    def test_measured_over_assistance_does_not_persist_after_strength(self) -> None:
        report = simulation.run(self.document)
        self.assertGreater(report["metrics"]["over_assistance_rate"], 0.0)
        self.assertEqual(report["metrics"]["over_assistance_after_strength_rate"], 0.0)
        self.assertEqual(report["metrics"]["unplanned_under_assistance_rate"], 0.0)

    def test_all_kill_conditions_are_green(self) -> None:
        report = simulation.run(self.document)
        self.assertFalse(any(report["kill_conditions"].values()))


if __name__ == "__main__":
    unittest.main()
