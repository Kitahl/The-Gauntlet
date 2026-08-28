from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_smart_tool_calibration import (  # noqa: E402
    BenchmarkTarget,
    CalibrationStatus,
    HistoricalRouteEvidence,
    assess_historical_route,
    build_calibrated_runtime_policy,
    calibrate_target,
)
from foil_smart_tool_value import (  # noqa: E402
    DifficultyBand,
    PrelaunchStatus,
    RouteEvidence,
    decide_prelaunch,
)
from foil_tool_contract import ToolCost, ToolFamily  # noqa: E402
from egrt_types import digest  # noqa: E402


class SmartToolCalibrationTests(unittest.TestCase):
    def target(self, *, cap: int = 250_000) -> BenchmarkTarget:
        return BenchmarkTarget(
            benchmark_rows=60,
            baseline_correct=11,
            target_correct=22,
            maximum_total_tokens=cap,
        )

    def test_hle_target_derives_token_value_without_embedding_cap(self) -> None:
        calibrated = calibrate_target(self.target())
        self.assertEqual(calibrated.target.required_net_rescues, 11)
        self.assertEqual(calibrated.target.target_tokens_per_net_rescue, 22_727)
        self.assertEqual(calibrated.weights.rescue_value_microunits, 22_727)
        self.assertEqual(calibrated.weights.damage_loss_microunits, 45_454)
        self.assertEqual(calibrated.weights.invalid_loss_microunits, 11_364)
        self.assertEqual(calibrated.weights.token_price_microunits, 1)
        self.assertFalse(calibrated.trace()["hard_limit_embedded_in_foil"])

    def test_calibration_wires_active_fail_closed_runtime(self) -> None:
        calibrated = calibrate_target(self.target())
        runtime = build_calibrated_runtime_policy(calibrated)
        self.assertTrue(runtime.enabled)
        self.assertFalse(runtime.value_gate.benchmark_exploration)
        self.assertFalse(runtime.allow_unadmitted_benchmark_selection)
        self.assertIs(runtime.weights, calibrated.weights)

    def test_no_tools_history_stands_down_at_target_economics(self) -> None:
        decision = assess_historical_route(
            HistoricalRouteEvidence(
                route_id="RPS_NO_TOOLS_SECOND_PASS",
                attempts=30,
                rescues=2,
                damages=2,
                invalid_outcomes=1,
                total_extra_tokens=793_077,
                auditable=True,
                evidence_reason="frozen_audit",
            ),
            calibrate_target(self.target()),
        )
        self.assertEqual(decision.status, CalibrationStatus.STAND_DOWN)
        self.assertLess(decision.utility_lower_bound_microunits, 0)
        self.assertEqual(decision.observed_mean_extra_tokens, 26_436)

    def test_contaminated_retrieval_is_uncalibrated(self) -> None:
        decision = assess_historical_route(
            HistoricalRouteEvidence(
                route_id="RETRIEVAL",
                attempts=30,
                rescues=4,
                damages=0,
                invalid_outcomes=2,
                total_extra_tokens=8_943_434,
                auditable=False,
                evidence_reason="trace_attribution_failed",
            ),
            calibrate_target(self.target()),
        )
        self.assertEqual(decision.status, CalibrationStatus.UNCALIBRATED)
        self.assertIsNone(decision.utility_lower_bound_microunits)

    def test_tool_cost_changes_decision_under_same_evidence(self) -> None:
        calibrated = calibrate_target(self.target(cap=2_200_000))
        evidence = RouteEvidence(
            ToolFamily.COMPUTATION,
            DifficultyBand.HARD,
            100,
            80,
            0,
            100,
            digest("strong-hard-route"),
            True,
        )
        cheap = decide_prelaunch(
            family=ToolFamily.COMPUTATION,
            difficulty=DifficultyBand.HARD,
            cost=ToolCost(maximum_output_tokens=1_000),
            remaining_unreserved_tokens=2_200_000,
            weights=calibrated.weights,
            policy=calibrated.value_gate,
            evidence=evidence,
        )
        expensive = decide_prelaunch(
            family=ToolFamily.COMPUTATION,
            difficulty=DifficultyBand.HARD,
            cost=ToolCost(maximum_output_tokens=200_000),
            remaining_unreserved_tokens=2_200_000,
            weights=calibrated.weights,
            policy=calibrated.value_gate,
            evidence=evidence,
        )
        self.assertEqual(cheap.status, PrelaunchStatus.EXECUTE)
        self.assertEqual(expensive.status, PrelaunchStatus.DECLINE_NONPOSITIVE_VALUE)

    def test_invalid_targets_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkTarget(60, 11, 11, 250_000)
        with self.assertRaises(ValueError):
            BenchmarkTarget(60, 11, 61, 250_000)
        with self.assertRaises(ValueError):
            BenchmarkTarget(60, 11, 22, 0)


if __name__ == "__main__":
    unittest.main()
