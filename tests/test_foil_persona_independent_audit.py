from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_persona_independent_audit as independent_audit  # noqa: E402
import foil_persona_simulation as simulation  # noqa: E402


class PersonaIndependentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        document = json.loads(
            (ROOT / "benchmarks" / "fixtures" / "foil_personas_v1.json").read_text(encoding="utf-8")
        )
        cls.report = simulation.run(document)

    def test_recomputes_raw_rows_and_conservation(self) -> None:
        receipt = independent_audit.audit(self.report)
        self.assertTrue(receipt["metrics_recomputed"])
        self.assertTrue(receipt["kill_conditions_recomputed"])
        self.assertTrue(receipt["row_conservation_passed"])
        self.assertEqual(receipt["sessions"], 90)

    def test_metric_tamper_fails_digest_first(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["metrics"]["over_assistance_rate"] = 0.0
        with self.assertRaisesRegex(ValueError, "report_sha256 mismatch"):
            independent_audit.audit(changed)

    def test_rehashed_metric_tamper_fails_recomputation(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["metrics"]["over_assistance_rate"] = 0.0
        unsigned = copy.deepcopy(changed)
        unsigned.pop("report_sha256")
        changed["report_sha256"] = independent_audit._digest(unsigned)
        with self.assertRaisesRegex(ValueError, "metrics mismatch"):
            independent_audit.audit(changed)


if __name__ == "__main__":
    unittest.main()
