from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_adaptive_executor import (  # noqa: E402
    BenchmarkExecutionPolicy,
    ExecutionAction,
    RouteWorkResult,
    execute_benchmark_route,
)
from foil_adaptive_route import (  # noqa: E402
    DecisionReason,
    Route,
    ShadowRouteDecision,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def decision(route: Route, answer: str = "A") -> ShadowRouteDecision:
    return ShadowRouteDecision(
        route=route,
        reason=(
            DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT
            if route is Route.DIRECT
            else DecisionReason.VERIFY_POSITIVE_VALUE
            if route is Route.VERIFY
            else DecisionReason.FULL_POSITIVE_VALUE
        ),
        a0_digest=digest(answer),
        binding_digest=d("binding"),
        expected_value_numerator=0 if route is Route.DIRECT else 1,
    )


class AdaptiveExecutorTests(unittest.TestCase):
    def test_disabled_and_direct_never_call_a_runner(self) -> None:
        final, receipt = execute_benchmark_route(decision(Route.FULL), "A")
        self.assertEqual(final, "A")
        self.assertEqual(receipt.action, ExecutionAction.KEEP_A0)
        self.assertEqual(receipt.route_calls, 0)
        final, receipt = execute_benchmark_route(
            decision(Route.DIRECT),
            "A",
            policy=BenchmarkExecutionPolicy(enabled=True),
        )
        self.assertEqual((final, receipt.route_calls), ("A", 0))

    def test_verify_changes_only_after_confirmation(self) -> None:
        final, receipt = execute_benchmark_route(
            decision(Route.VERIFY),
            "A",
            policy=BenchmarkExecutionPolicy(enabled=True),
            verify_runner=lambda: RouteWorkResult("B", verified=False),
        )
        self.assertEqual(final, "A")
        self.assertEqual(receipt.action, ExecutionAction.VERIFY_STAND_DOWN)
        final, receipt = execute_benchmark_route(
            decision(Route.VERIFY),
            "A",
            policy=BenchmarkExecutionPolicy(enabled=True),
            verify_runner=lambda: RouteWorkResult(
                "B", verified=True, input_tokens=11, output_tokens=3
            ),
        )
        self.assertEqual(final, "B")
        self.assertEqual(receipt.action, ExecutionAction.SELECT_VERIFIED)
        self.assertTrue(receipt.answer_changed)

    def test_full_executes_once_and_records_tokens_and_tools(self) -> None:
        calls = 0

        def run() -> RouteWorkResult:
            nonlocal calls
            calls += 1
            return RouteWorkResult(
                "B",
                input_tokens=20,
                cached_input_tokens=5,
                output_tokens=4,
                tool_event_types=("web_search",),
            )

        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(enabled=True),
            full_runner=run,
        )
        self.assertEqual((calls, final), (1, "B"))
        self.assertEqual(receipt.action, ExecutionAction.SELECT_FULL)
        self.assertEqual(
            (receipt.input_tokens, receipt.cached_input_tokens, receipt.output_tokens),
            (20, 5, 4),
        )
        self.assertEqual(receipt.tool_event_types, ("web_search",))
        self.assertFalse(receipt.production_authorized)

    def test_binding_runner_and_policy_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "bind A0"):
            execute_benchmark_route(decision(Route.FULL), "different")
        with self.assertRaisesRegex(ValueError, "exactly one verify"):
            execute_benchmark_route(
                decision(Route.VERIFY),
                "A",
                policy=BenchmarkExecutionPolicy(enabled=True),
            )
        with self.assertRaisesRegex(ValueError, "production authority"):
            BenchmarkExecutionPolicy(enabled=True, benchmark_only=False)


if __name__ == "__main__":
    unittest.main()
