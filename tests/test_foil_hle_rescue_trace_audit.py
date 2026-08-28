from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))
import foil_hle_rescue_trace_audit as MODULE  # noqa: E402


class HLERescueTraceAuditTests(unittest.TestCase):
    def test_frozen_trace_conservation_and_gate(self) -> None:
        report = MODULE.build_report(ROOT)
        self.assertEqual(report["reported_rescue_rows"], 4)
        self.assertEqual(report["distinct_questions"], 2)
        self.assertEqual(report["tool_calls"], 29)
        self.assertEqual(report["web_search_calls"], 20)
        self.assertEqual(report["command_calls"], 9)
        self.assertEqual(report["admissible_rescue_rows"], 0)
        self.assertEqual(report["calibration_gate"], "FAIL")
        self.assertFalse(report["single_target_retrieval_supported"])

    def test_artin_is_leakage_and_fermi_execution_is_unverified(self) -> None:
        report = MODULE.build_report(ROOT)
        by_item: dict[str, set[str]] = {}
        for row in report["routes"]:
            by_item.setdefault(row["item_id"], set()).add(row["classification"])
        self.assertEqual(
            by_item["hle-66ea7d2cc321286a5288ef06"],
            {"LEAKAGE_CONTAMINATED"},
        )
        self.assertEqual(
            by_item["hle-672a80a432cd57d8762583e9"],
            {"UNVERIFIED_COMPUTATION"},
        )

    def test_report_is_deterministic(self) -> None:
        first = MODULE.build_report(ROOT)
        second = MODULE.build_report(ROOT)
        self.assertEqual(first["report_sha256"], second["report_sha256"])


if __name__ == "__main__":
    unittest.main()
