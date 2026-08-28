from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_smart_tool_value import (  # noqa: E402
    DifficultyBand,
    PrelaunchStatus,
    RouteEvidence,
    UtilityWeights,
    ValueGatePolicy,
    decide_prelaunch,
)
from foil_tool_contract import ToolCost, ToolFamily  # noqa: E402


WEIGHTS = UtilityWeights(
    rescue_value_microunits=1_000_000,
    damage_loss_microunits=2_000_000,
    invalid_loss_microunits=500_000,
    token_price_microunits=1,
)


def evidence(*, attempts: int, rescues: int, damages: int, valid: int, fresh: bool = True):
    return RouteEvidence(
        ToolFamily.COMPUTATION,
        DifficultyBand.EASY,
        attempts,
        rescues,
        damages,
        valid,
        digest(f"{attempts}:{rescues}:{damages}:{valid}:{fresh}"),
        fresh,
    )


class SmartToolValueTests(unittest.TestCase):
    def decide(self, rows, *, cap: int = 100, exploration: bool = False):
        return decide_prelaunch(
            family=ToolFamily.COMPUTATION,
            difficulty=DifficultyBand.EASY,
            cost=ToolCost(maximum_output_tokens=10),
            remaining_unreserved_tokens=cap,
            weights=WEIGHTS,
            policy=ValueGatePolicy(
                enabled=True,
                benchmark_exploration=exploration,
                minimum_observations=20,
            ),
            evidence=rows,
        )

    def test_sparse_evidence_declines_or_explicitly_explores(self) -> None:
        sparse = evidence(attempts=5, rescues=5, damages=0, valid=5)
        self.assertEqual(self.decide(sparse).status, PrelaunchStatus.DECLINE_UNCALIBRATED)
        explored = self.decide(sparse, exploration=True)
        self.assertEqual(explored.status, PrelaunchStatus.EXECUTE_EXPLORATION)
        self.assertIsNone(explored.utility_lower_bound_microunits)

    def test_strong_route_executes_and_damage_route_declines(self) -> None:
        strong = self.decide(evidence(attempts=100, rescues=80, damages=0, valid=100))
        self.assertEqual(strong.status, PrelaunchStatus.EXECUTE)
        self.assertGreater(strong.rescue_lcb_ppm, 600_000)
        dangerous = self.decide(
            evidence(attempts=100, rescues=20, damages=40, valid=100)
        )
        self.assertEqual(dangerous.status, PrelaunchStatus.DECLINE_NONPOSITIVE_VALUE)

    def test_budget_and_freshness_fail_closed(self) -> None:
        rows = evidence(attempts=100, rescues=80, damages=0, valid=100)
        self.assertEqual(self.decide(rows, cap=9).status, PrelaunchStatus.DECLINE_BUDGET)
        stale = self.decide(
            evidence(attempts=100, rescues=80, damages=0, valid=100, fresh=False)
        )
        self.assertEqual(stale.status, PrelaunchStatus.DECLINE_STALE)

    def test_more_rescues_raise_lower_bound_with_fixed_denominator(self) -> None:
        low = self.decide(evidence(attempts=100, rescues=50, damages=0, valid=100))
        high = self.decide(evidence(attempts=100, rescues=80, damages=0, valid=100))
        self.assertGreater(high.rescue_lcb_ppm, low.rescue_lcb_ppm)


if __name__ == "__main__":
    unittest.main()
