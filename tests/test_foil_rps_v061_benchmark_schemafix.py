"""Contract tests for the stopped-at-control schema-fixed benchmark revision."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "benchmarks"
    / "harness"
    / "foil_rps_v061_hle_shadow_small_schemafix.py"
)
SPEC = importlib.util.spec_from_file_location("rps_v061_schemafix", RUNNER)
assert SPEC is not None and SPEC.loader is not None
protocol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(protocol)


class RPSV061SchemaFixTests(unittest.TestCase):
    def test_live_unsupported_keyword_is_removed(self):
        hinges = protocol.schema_fixed()["properties"]["hinges"]
        self.assertNotIn("uniqueItems", hinges)

    def test_parser_still_rejects_duplicate_hinges(self):
        value = protocol.BASE.expected_control()
        value["hinges"] = ["same", "same"]
        self.assertIn("hinges are invalid", protocol.BASE.parse_answer(json.dumps(value))[1])

    def test_failed_attempt_is_preserved(self):
        self.assertTrue(protocol.FAILED_RECEIPT.is_file())
        receipt = protocol.BASE.read_json(protocol.FAILED_RECEIPT)
        self.assertFalse(receipt["valid"])
        self.assertIsNone(receipt["answer"])
        self.assertEqual(receipt["usage"], {})


if __name__ == "__main__":
    unittest.main()
