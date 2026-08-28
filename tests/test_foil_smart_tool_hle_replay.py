from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_smart_tool_hle_replay import build_predictions, score_predictions  # noqa: E402


class SmartToolHLEReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run = ROOT / "benchmark_runs" / "2026-08-26" / "hle_active_20"
        cls.items = json.loads((run / "items.json").read_text(encoding="utf-8"))
        cls.results = json.loads((run / "results.json").read_text(encoding="utf-8"))

    def test_prediction_is_gold_blind_and_deterministic(self) -> None:
        first = build_predictions(self.items, self.results)
        changed = copy.deepcopy(self.results)
        for row in changed["rows"]:
            row["gold"] = "hidden-changed"
            row["correct"] = not bool(row["correct"])
            row["base_correct"] = not bool(row["base_correct"])
        self.assertEqual(first, build_predictions(self.items, changed))
        self.assertEqual(first["ledger"]["spent_total_tokens"], 0)

    def test_score_conservation_and_scope(self) -> None:
        predictions = build_predictions(self.items, self.results)
        report = score_predictions(predictions, self.results)
        self.assertEqual(report["source_rows"], 60)
        self.assertEqual(report["rows"], 59)
        self.assertEqual(len(report["omitted_rows"]), 1)
        self.assertEqual(
            report["omitted_rows"][0]["reason"], "base_answer_unavailable"
        )
        self.assertEqual(report["distinct_questions"], 20)
        self.assertEqual(
            report["baseline_correct"] + (59 - report["baseline_correct"]),
            59,
        )
        self.assertEqual(report["classification"], "HISTORICAL_DEVELOPMENT_REPLAY")
        self.assertEqual(report["token_spend"], 0)


if __name__ == "__main__":
    unittest.main()
