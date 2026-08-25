from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "benchmarks" / "harness" / "foil_adaptive_two_benchmark_pilot.py"
SPEC = importlib.util.spec_from_file_location("foil_adaptive_two_benchmark_pilot", PATH)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class AdaptivePilotTests(unittest.TestCase):
    def test_certified_pass_stands_down_and_failure_routes_full(self) -> None:
        item = {
            "id": "x",
            "benchmark": "PROCESSBENCH_GSM8K",
            "problem": "x",
            "steps": ["$2+2=4$"],
            "item_sha256": "x",
        }
        a0 = {"answer": "OK", "abstain": False}
        direct = pilot.route_item(item, a0, "TERRA_LOW")
        item["steps"] = ["$2+2=5$"]
        full = pilot.route_item(item, a0, "TERRA_LOW")
        self.assertEqual((direct["route"], direct["failed_equalities"]), ("DIRECT", 0))
        self.assertEqual((full["route"], full["failed_equalities"]), ("FULL", 1))

    def test_no_oracle_route_and_direct_identity_contract(self) -> None:
        item = {"id": "s", "benchmark": "SIMPLEQA_NO_BROWSE", "problem": "Who?", "item_sha256": "x"}
        a0 = {"answer": "A", "abstain": False}
        route = pilot.route_item(item, a0, "SOL_LOW")
        self.assertEqual(route["route"], "DIRECT")
        self.assertNotIn("gold", pilot.item_prompt(item).lower())

    def test_closed_answer_and_tool_event_contracts(self) -> None:
        value, error = pilot.parse_answer('{"answer":"A","abstain":false}')
        self.assertIsNone(error)
        self.assertEqual(value, {"answer": "A", "abstain": False})
        self.assertIsNotNone(pilot.parse_answer('{"answer":"A","extra":1}')[1])
        stream = pilot.parse_stream('{"type":"item.completed","item":{"type":"tool_call"}}')
        self.assertTrue(stream["tool_events"])


if __name__ == "__main__":
    unittest.main()
