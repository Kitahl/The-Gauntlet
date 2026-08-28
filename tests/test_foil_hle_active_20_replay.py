from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_hle_active_20_replay import build_replay  # noqa: E402


class HLEActiveReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = (
            ROOT
            / "benchmark_runs"
            / "2026-08-26"
            / "hle_active_20"
            / "independent_audit.json"
        )
        cls.replay = build_replay(json.loads(path.read_text(encoding="utf-8")))

    def test_sealed_counts_reproduce(self) -> None:
        facts = self.replay["audited_facts"]
        self.assertEqual(
            (
                facts["rows"],
                facts["base_correct"],
                facts["historical_final_correct"],
                facts["historical_rescues"],
                facts["historical_published_damages"],
                facts["historical_invalid_rows"],
            ),
            (60, 11, 14, 6, 2, 3),
        )
        self.assertEqual(
            (facts["tool_calls"], facts["web_search_calls"], facts["command_calls"]),
            (151, 97, 54),
        )

    def test_fallback_restores_invalid_correct_a0(self) -> None:
        fallback = self.replay["scenarios"]["contract_fallback_only"]
        self.assertEqual(fallback["correct"], 15)
        self.assertEqual(fallback["correct_a0_withheld"], 0)

    def test_safe_admission_eliminates_observed_damage(self) -> None:
        safe = self.replay["scenarios"]["safe_admission_after_route"]
        direct = self.replay["scenarios"]["direct_preflight"]
        self.assertEqual((safe["correct"], safe["published_damages"]), (11, 0))
        self.assertEqual(safe["total_provider_tokens"], 10_913_975)
        self.assertEqual(direct["total_provider_tokens"], 1_177_464)
        self.assertEqual(direct["aggregate_token_multiplier_vs_a0"], 1.0)

    def test_oracle_scenarios_are_explicit_and_expensive(self) -> None:
        all_rescues = self.replay["scenarios"]["oracle_all_tool_rescues"]
        terra = self.replay["scenarios"]["oracle_terra_tool_rescues"]
        self.assertEqual((all_rescues["correct"], terra["correct"]), (15, 13))
        self.assertGreater(all_rescues["aggregate_token_multiplier_vs_a0"], 2.5)
        self.assertAlmostEqual(
            terra["aggregate_token_multiplier_vs_a0"],
            1.2927877200491904,
        )
        self.assertIn("ORACLE", terra["classification"])


if __name__ == "__main__":
    unittest.main()
