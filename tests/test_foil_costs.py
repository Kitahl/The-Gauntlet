from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_costs as costs  # noqa: E402


def receipt(**overrides):
    values = {
        "task_id": "task-1",
        "condition": "CORRECT_PROFILE",
        "prompt_sha256": "a" * 64,
        "profile_payload_sha256": "b" * 64,
        "profile_lookup_count": 1,
        "routing_decision_count": 1,
        "model_calls": 1,
        "tool_calls": 2,
        "verification_calls": 1,
        "retry_count": 0,
        "branch_count": 1,
        "revision_count": 0,
        "tokens_in": 100,
        "tokens_out": 40,
        "wall_time_ms": 25.5,
    }
    values.update(overrides)
    return costs.RunCostReceipt(**values)


class RunCostReceiptTests(unittest.TestCase):
    def test_receipt_contains_every_addendum_field_and_no_raw_prompt(self):
        trace = receipt().trace()
        self.assertEqual(set(costs.COST_FIELDS) - set(trace), set())
        self.assertFalse(trace["raw_prompt_stored"])
        self.assertEqual(len(trace["receipt_sha256"]), 64)
        self.assertNotIn("secret prompt", json.dumps(trace))

    def test_unavailable_values_remain_none(self):
        row = receipt(tokens_in=None, tokens_out=None)
        trace = row.trace()
        self.assertIsNone(trace["tokens_in"])
        self.assertIsNone(trace["tokens_out"])

    def test_invalid_or_fabricated_numeric_values_fail_closed(self):
        for field, value in (
            ("model_calls", True),
            ("tool_calls", -1),
            ("tokens_in", 1.5),
            ("wall_time_ms", float("nan")),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                receipt(**{field: value})

    def test_trace_round_trip_and_digest_tampering(self):
        trace = receipt().trace()
        self.assertEqual(costs.RunCostReceipt.from_mapping(trace), receipt())
        trace["tool_calls"] = 99
        with self.assertRaises(ValueError):
            costs.RunCostReceipt.from_mapping(trace)

    def test_condition_total_is_the_sum_of_recorded_costs(self):
        rows = [receipt(), receipt(task_id="task-2")]
        totals = costs.aggregate_costs(rows)
        self.assertEqual(totals["profile_lookup_count"], 2)
        self.assertEqual(totals["tool_calls"], 4)
        self.assertEqual(totals["tokens_in"], 200)
        self.assertEqual(totals["wall_time_ms"], 51.0)

    def test_one_missing_component_keeps_that_aggregate_unknown(self):
        totals = costs.aggregate_costs([receipt(), receipt(tokens_in=None)])
        self.assertIsNone(totals["tokens_in"])
        self.assertEqual(totals["tokens_out"], 80)

    def test_cost_per_correct_preserves_units(self):
        result = costs.cost_per_correct([receipt(), receipt(task_id="task-2")], 1)
        self.assertEqual(result["model_calls"], 2.0)
        self.assertEqual(result["tokens_out"], 80.0)
        self.assertIsNone(costs.cost_per_correct([receipt()], 0)["model_calls"])

    def test_matched_total_cost_requires_complete_exact_vectors(self):
        self.assertTrue(costs.matched_total_cost([receipt(), receipt(task_id="task-2")]))
        self.assertFalse(
            costs.matched_total_cost([receipt(), receipt(task_id="task-2", tool_calls=3)])
        )
        self.assertFalse(costs.matched_total_cost([receipt(tokens_in=None)]))


if __name__ == "__main__":
    unittest.main()
