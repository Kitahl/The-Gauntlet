"""Tests for the Stage-2 blind-rival provider harness."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))
sys.path.insert(0, str(ROOT / "tools"))

import foil_rps_v063_stage2_pilot as pilot  # noqa: E402


class Stage2PilotTests(unittest.TestCase):
    def test_prepare_reads_items_only_and_request_has_no_incumbent_surface(self):
        items = {
            "items": [
                {
                    "id": "a",
                    "benchmark": "PROCESSBENCH_GSM8K",
                    "problem": "p1",
                    "steps": [r"\[2+2=4\]"],
                },
                {
                    "id": "b",
                    "benchmark": "PROCESSBENCH_GSM8K",
                    "problem": "p2",
                    "steps": [r"\[3+3=6\]"],
                },
            ]
        }
        document = pilot.build_requests_document(items)
        self.assertEqual(document["created_from"], "items_only_before_a0")
        for row in document["requests"]:
            self.assertNotIn("base", row)
            self.assertNotIn("candidate", row)
            self.assertNotIn("gold", row)
            self.assertTrue(row["incumbent_withheld"])

    def test_provider_argv_is_fresh_read_only_ephemeral_and_schema_bound(self):
        argv = pilot.build_argv("TERRA_LOW", Path("empty"), Path("last.json"))
        joined = " ".join(argv)
        for token in (
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--output-schema",
            "--json",
        ):
            self.assertIn(token, joined)

    def test_rival_answer_parser_is_closed(self):
        valid, error = pilot.parse_rival_answer(
            '{"answer":"OK","abstain":false,"method_summary":"checked"}'
        )
        self.assertIsNone(error)
        self.assertEqual(valid["answer"], "OK")
        for malformed in (
            '{"answer":"OK","abstain":"false","method_summary":"checked"}',
            '{"answer":"OK","abstain":false,"method_summary":"checked","x":1}',
            '{"answer":"OK","abstain":false}',
        ):
            value, reason = pilot.parse_rival_answer(malformed)
            self.assertIsNone(value)
            self.assertIsNotNone(reason)

    def test_score_recomputes_rescue_abstention_and_additive_cost(self):
        predictions = {
            "provider_calls": 1,
            "tool_calls": 0,
            "rows": [
                {
                    "unit_id": "u1",
                    "item_id": "i1",
                    "config_id": "TERRA_LOW",
                    "base": {"answer": "OK", "abstain": False},
                    "final": {"answer": "0", "abstain": False},
                    "stage2": None,
                    "base_input_tokens": 100,
                    "base_output_tokens": 10,
                    "added_input_tokens": 0,
                    "added_output_tokens": 0,
                },
                {
                    "unit_id": "u2",
                    "item_id": "i2",
                    "config_id": "TERRA_LOW",
                    "base": {"answer": "OK", "abstain": False},
                    "final": {"answer": "ABSTAIN", "abstain": True},
                    "stage2": {"outcome": "DISAGREE"},
                    "base_input_tokens": 100,
                    "base_output_tokens": 10,
                    "added_input_tokens": 100,
                    "added_output_tokens": 10,
                },
            ],
        }
        results = {
            "rows": [
                {"benchmark": "PROCESSBENCH_GSM8K", "unit_id": "u1", "gold": "0"},
                {"benchmark": "PROCESSBENCH_GSM8K", "unit_id": "u2", "gold": "OK"},
            ]
        }
        report = pilot.score_documents(predictions, results)
        self.assertEqual(report["summary"]["rescues"], 1)
        self.assertEqual(report["summary"]["stage2_abstentions"], 1)
        self.assertEqual(report["summary"]["damages"], 0)
        self.assertEqual(report["summary"]["accuracy_losses"], 1)
        self.assertEqual(report["summary"]["aggregate_total_token_multiplier"], 1.5)
        self.assertFalse(report["kill_conditions"]["damage"])
        self.assertTrue(report["kill_conditions"]["triggered_abstention"])
        self.assertTrue(report["kill_conditions"]["total_token_cost"])


if __name__ == "__main__":
    unittest.main()
