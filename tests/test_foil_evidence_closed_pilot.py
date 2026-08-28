from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_evidence_closed_pilot import run_predictions, score_predictions  # noqa: E402


class EvidenceClosedPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = ROOT / "benchmarks" / "data"
        cls.items = json.loads(
            (data / "foil_smart_tool_integration_v1_items.json").read_text(encoding="utf-8")
        )
        cls.retrieval = json.loads(
            (data / "foil_smart_tool_integration_v1_retrieval.json").read_text(encoding="utf-8")
        )
        cls.gold = json.loads(
            (data / "foil_smart_tool_integration_v1_gold.json").read_text(encoding="utf-8")
        )

    def test_prediction_is_deterministic_gold_blind_and_non_authoritative(self) -> None:
        first = run_predictions(self.items, self.retrieval, maximum_total_tokens=1)
        second = run_predictions(self.items, self.retrieval, maximum_total_tokens=1)
        self.assertEqual(first, second)
        self.assertNotIn("gold", first)
        self.assertFalse(first["promotion_authorized"])
        self.assertEqual(first["ledger"]["spent_total_tokens"], 0)
        self.assertTrue(
            all(not row["run"]["production_authorized"] for row in first["predictions"])
        )

    def test_scoring_conserves_and_labels_synthetic_scope(self) -> None:
        predictions = run_predictions(self.items, self.retrieval, maximum_total_tokens=1)
        report = score_predictions(predictions, self.gold)
        self.assertEqual(report["classification"], "SYNTHETIC_INTEGRATION_ONLY")
        self.assertEqual(report["items"], 4)
        self.assertEqual(report["baseline_correct"], 1)
        self.assertEqual(report["final_correct"], 4)
        self.assertEqual((report["rescues"], report["damages"]), (3, 0))
        self.assertEqual(report["tool_calls"], 8)
        self.assertEqual(report["actual_provider_tokens"], 0)

    def test_prediction_tampering_fails_closed(self) -> None:
        predictions = run_predictions(self.items, self.retrieval, maximum_total_tokens=1)
        predictions = copy.deepcopy(predictions)
        predictions["predictions"][0]["final"] = "tampered"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            score_predictions(predictions, self.gold)

    def test_zero_caller_budget_preserves_every_a0(self) -> None:
        predictions = run_predictions(self.items, self.retrieval, maximum_total_tokens=0)
        self.assertTrue(
            all(row["a0"] == row["final"] for row in predictions["predictions"])
        )


if __name__ == "__main__":
    unittest.main()
