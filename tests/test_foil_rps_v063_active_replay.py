"""Tests for the frozen-output active RPS replay."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_rps_v063_active_replay import build_report  # noqa: E402


def item(item_id: str, steps: list[str]) -> dict[str, object]:
    return {
        "benchmark": "PROCESSBENCH_GSM8K",
        "id": item_id,
        "problem": "Find the first error.",
        "steps": steps,
    }


def row(unit_id: str, item_id: str, answer: str, gold: str) -> dict[str, object]:
    candidate = {"answer": answer, "abstain": False}
    correct = answer == gold
    return {
        "benchmark": "PROCESSBENCH_GSM8K",
        "unit_id": unit_id,
        "item_id": item_id,
        "config_id": "TEST",
        "gold": gold,
        "base": candidate,
        "base_correct": correct,
        "final": candidate,
        "final_correct": correct,
    }


class ActiveReplayTests(unittest.TestCase):
    def test_rescues_wrong_a_and_preserves_confirmed_a(self):
        items = {
            "items": [
                item("error", [r"\[2+2=4\]", r"\[3+3=7\]"]),
                item("clean", [r"\[2+2=4\]"]),
            ]
        }
        results = {
            "rows": [
                row("wrong", "error", "OK", "1"),
                row("right", "error", "1", "1"),
                row("clean", "clean", "OK", "OK"),
            ]
        }
        report = build_report(items, results, source_hashes={"fixture": "x"})
        summary = report["summary"]
        self.assertEqual(summary["base_correct"], 2)
        self.assertEqual(summary["active_final_correct"], 3)
        self.assertEqual(summary["rescues"], 1)
        self.assertEqual(summary["damages"], 0)
        self.assertEqual(summary["stage2_not_run"], 1)
        self.assertEqual(summary["total_token_multiplier"], 1.0)

    def test_duplicate_units_and_tampered_scores_fail_closed(self):
        items = {"items": [item("error", [r"\[2+2=5\]"])]}
        duplicate = row("u", "error", "OK", "0")
        with self.assertRaisesRegex(ValueError, "duplicate unit"):
            build_report(
                items,
                {"rows": [duplicate, duplicate]},
                source_hashes={"fixture": "x"},
            )
        tampered = dict(duplicate)
        tampered["base_correct"] = True
        with self.assertRaisesRegex(ValueError, "correctness mismatch"):
            build_report(
                items, {"rows": [tampered]}, source_hashes={"fixture": "x"}
            )


if __name__ == "__main__":
    unittest.main()
