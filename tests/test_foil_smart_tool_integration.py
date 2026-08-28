from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_smart_tool_integration import run_predictions, score_predictions  # noqa: E402


class SmartToolIntegrationTests(unittest.TestCase):
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

    def test_prediction_is_deterministic_and_gold_is_not_an_input(self) -> None:
        first = run_predictions(self.items, self.retrieval, maximum_total_tokens=60)
        second = run_predictions(self.items, self.retrieval, maximum_total_tokens=60)
        self.assertEqual(first, second)
        self.assertNotIn("gold", first)
        self.assertEqual(first["ledger"]["spent_total_tokens"], 60)

    def test_scoring_conserves_and_labels_synthetic_scope(self) -> None:
        predictions = run_predictions(self.items, self.retrieval, maximum_total_tokens=60)
        report = score_predictions(predictions, self.gold)
        self.assertEqual(report["classification"], "SYNTHETIC_INTEGRATION_ONLY")
        self.assertEqual(report["items"], 12)
        self.assertEqual(report["baseline_correct"], 3)
        self.assertEqual(report["final_correct"], 9)
        self.assertEqual((report["rescues"], report["damages"]), (6, 0))
        self.assertEqual(report["active_verify_calls"], 12)
        self.assertEqual(report["tool_calls"], 12)
        self.assertEqual(report["total_tool_provider_tokens"], 60)

    def test_prediction_tampering_fails_closed(self) -> None:
        predictions = run_predictions(self.items, self.retrieval, maximum_total_tokens=60)
        predictions = copy.deepcopy(predictions)
        predictions["predictions"][0]["final"] = "tampered"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            score_predictions(predictions, self.gold)

    def test_caller_budget_is_not_a_product_constant(self) -> None:
        limited = run_predictions(self.items, self.retrieval, maximum_total_tokens=59)
        self.assertEqual(limited["ledger"]["maximum_total_tokens"], 59)
        self.assertLessEqual(limited["ledger"]["spent_total_tokens"], 59)
        active = sum(
            int(row["run"]["active_verify_executed"]) for row in limited["predictions"]
        )
        self.assertLess(active, 12)


if __name__ == "__main__":
    unittest.main()
