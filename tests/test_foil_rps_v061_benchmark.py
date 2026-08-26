"""Pre-call contract tests for the sealed RPS v0.6.1 small benchmark."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "harness" / "foil_rps_v061_hle_shadow_small.py"
SPEC = importlib.util.spec_from_file_location("rps_v061_small", RUNNER)
assert SPEC is not None and SPEC.loader is not None
protocol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(protocol)


class RPSV061SmallBenchmarkTests(unittest.TestCase):
    def test_parser_is_closed_and_never_accepts_gold(self):
        valid = protocol.expected_control()
        self.assertIsNone(protocol.parse_answer(json.dumps(valid))[1])
        valid["gold"] = "A"
        self.assertIsNotNone(protocol.parse_answer(json.dumps(valid))[1])

    def test_inapplicable_check_cannot_carry_outcomes(self):
        check = {
            "kind": "INVARIANT",
            "hinge_index": 0,
            "applicable": False,
            "candidate_prediction": "HOLDS",
            "challenger_prediction": None,
            "observed": None,
        }
        self.assertIn("inapplicable", protocol._valid_check(check))

    def test_structural_benchmark_covers_all_six_expected_transitions(self):
        rows = protocol.structural_microbenchmark()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["pass"] for row in rows))

    def test_prompts_contain_no_serialized_gold_or_correctness_label(self):
        items, units = protocol.source_units()
        by_id = {item["id"]: item for item in items}
        for unit in units:
            prompt = protocol.observer_prompt(
                by_id[unit["item_id"]], unit["candidate"]
            ).lower()
            self.assertNotIn('"gold"', prompt)
            self.assertNotIn('"correct"', prompt)

    def test_four_units_reuse_only_frozen_base_candidates(self):
        _items, units = protocol.source_units()
        self.assertEqual(len(units), 4)
        self.assertEqual(
            {row["config_id"] for row in units}, {"TERRA_LOW", "TERRA_HIGH"}
        )
        self.assertTrue(all(row["candidate"] in "ABCDE" for row in units))


if __name__ == "__main__":
    unittest.main()
