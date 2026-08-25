from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_r16_independent_audit import audit  # noqa: E402


class IndependentAuditTests(unittest.TestCase):
    def test_frozen_report_rederives_and_tampering_fails(self) -> None:
        report = json.loads(
            (ROOT / "benchmarks" / "results" / "foil_r16_no_oracle_discovery_report.json").read_text(
                encoding="utf-8"
            )
        )
        receipt = audit(report)
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["raw_rows"], 81)
        self.assertEqual(receipt["mutation_rows"], 56)
        self.assertEqual(receipt["natural_rows"], 11)
        self.assertEqual(receipt["control_rows"], 14)
        tampered = copy.deepcopy(report)
        tampered["raw_rows"][0]["detected"] = not tampered["raw_rows"][0]["detected"]
        with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
            audit(tampered)


if __name__ == "__main__":
    unittest.main()
