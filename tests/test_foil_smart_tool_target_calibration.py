from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))
sys.path.insert(0, str(ROOT / "tools"))

from foil_smart_tool_calibration import BenchmarkTarget  # noqa: E402
import foil_smart_tool_target_calibration as HARNESS  # noqa: E402


class SmartToolTargetCalibrationReportTests(unittest.TestCase):
    @staticmethod
    def read(relative: str) -> dict[str, object]:
        value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert isinstance(value, dict)
        return value

    def build(self) -> dict[str, object]:
        return HARNESS.build_report(
            self.read("benchmark_runs/2026-08-26/hle_active_20/independent_audit.json"),
            self.read("benchmark_runs/2026-08-28/hle_rescue_trace_audit/report.json"),
            self.read("benchmark_runs/2026-08-28/smart_tool_hle_replay/report.json"),
            target=BenchmarkTarget(60, 11, 22, 250_000),
        )

    def test_policy_decisions_match_frozen_evidence(self) -> None:
        report = self.build()
        decisions = {row["route_id"]: row for row in report["route_decisions"]}
        self.assertEqual(decisions["RPS_NO_TOOLS_SECOND_PASS"]["status"], "STAND_DOWN")
        self.assertEqual(
            decisions["UNRESTRICTED_RETRIEVAL_SECOND_PASS"]["status"],
            "UNCALIBRATED",
        )
        self.assertEqual(
            decisions["DETERMINISTIC_HLE_ACTIVE_VERIFY"]["status"],
            "UNCALIBRATED",
        )
        self.assertFalse(report["promotion_authorized"])

    def test_report_hash_is_deterministic(self) -> None:
        self.assertEqual(self.build()["report_sha256"], self.build()["report_sha256"])


if __name__ == "__main__":
    unittest.main()
