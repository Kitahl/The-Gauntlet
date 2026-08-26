"""Adversarial tests for the fail-closed RPS scorer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_rps_score as scorer  # noqa: E402


def telemetry(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "p1_outcome": "PASS",
        "p2_outcome": "N/A",
        "conflict": False,
        "repair_triggered": False,
        "answer_changed": False,
        "rollback_hinge": None,
        "tiebreak_used": False,
    }
    result.update(overrides)
    return result


def row(
    condition: str,
    *,
    correct: bool,
    input_tokens: int | None = 100,
    output_tokens: int = 100,
    item_id: str = "1",
) -> dict[str, object]:
    result: dict[str, object] = {
        "benchmark": "x",
        "item_id": item_id,
        "condition": condition,
        "correct": correct,
        "output_tokens": output_tokens,
    }
    if input_tokens is not None:
        result["input_tokens"] = input_tokens
    if condition.startswith("RPS_"):
        result["rps"] = telemetry()
    return result


class RPSScorerContractTests(unittest.TestCase):
    def load(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text(
                "\n".join(json.dumps(value) for value in rows) + "\n",
                encoding="utf-8",
            )
            return scorer.load_jsonl(path)

    def test_correct_and_valid_must_be_real_booleans(self):
        bad = row("BASE", correct=True)
        bad["correct"] = "false"
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            self.load([bad])
        bad = row("BASE", correct=True)
        bad["valid"] = 1
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            self.load([bad])

    def test_duplicate_unit_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate unit identity"):
            self.load([row("BASE", correct=False), row("BASE", correct=True)])

    def test_duplicate_json_object_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text(
                '{"benchmark":"x","item_id":"1","condition":"BASE",'
                '"correct":true,"correct":false}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                scorer.load_jsonl(path)

    def test_negative_or_boolean_token_counts_are_rejected(self):
        bad = row("BASE", correct=True, output_tokens=-1)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.load([bad])
        bad = row("BASE", correct=True)
        bad["input_tokens"] = True
        with self.assertRaisesRegex(ValueError, "integer"):
            self.load([bad])

    def test_p1_fail_requires_conflict_repair_and_rollback(self):
        bad = row("RPS_060", correct=True)
        bad["rps"] = telemetry(p1_outcome="FAIL", conflict=True)
        with self.assertRaisesRegex(ValueError, "requires conflict and repair"):
            self.load([bad])
        good = row("RPS_060", correct=True)
        good["rps"] = telemetry(
            p1_outcome="FAIL",
            conflict=True,
            repair_triggered=True,
            rollback_hinge=0,
        )
        self.assertEqual(len(self.load([good])), 1)

    def test_missing_telemetry_fails_before_majority_aggregation(self):
        bad = row("RPS_060", correct=True)
        del bad["rps"]
        with self.assertRaisesRegex(ValueError, "require telemetry"):
            self.load([bad])

    def test_mean_and_median_output_and_total_multipliers_are_reported(self):
        rows = self.load(
            [
                row("BASE", correct=False, input_tokens=100, output_tokens=100),
                row("RPS_060", correct=True, input_tokens=200, output_tokens=120),
                row(
                    "BASE",
                    correct=True,
                    input_tokens=100,
                    output_tokens=100,
                    item_id="2",
                ),
                row(
                    "RPS_060",
                    correct=True,
                    input_tokens=100,
                    output_tokens=110,
                    item_id="2",
                ),
            ]
        )
        result = scorer.paired(rows, "BASE")
        self.assertAlmostEqual(result["mean_output_token_multiplier"], 1.15)
        self.assertAlmostEqual(result["median_output_token_multiplier"], 1.15)
        self.assertAlmostEqual(result["mean_total_token_multiplier"], 1.325)
        self.assertAlmostEqual(result["median_total_token_multiplier"], 1.325)
        self.assertTrue(result["total_cost_gate_evaluable"])
        self.assertEqual(
            result["total_token_definition"], "input_tokens_plus_output_tokens"
        )

    def test_missing_input_tokens_makes_total_gate_unevaluable(self):
        rows = self.load(
            [
                row("BASE", correct=True, input_tokens=None),
                row("RPS_060", correct=True, input_tokens=None),
            ]
        )
        result = scorer.paired(rows, "BASE")
        self.assertIsNone(result["mean_total_token_multiplier"])
        self.assertFalse(result["total_cost_gate_evaluable"])

    def test_closed_schema_rejects_unknown_fields(self):
        bad = row("BASE", correct=True)
        bad["gold_answer"] = "secret"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.load([bad])


if __name__ == "__main__":
    unittest.main()
