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
                verified=True,
                input_tokens=20,
                cached_input_tokens=5,
                output_tokens=4,
                tool_event_types=("web_search",),
            )

        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(
                enabled=True, independent_verification_available=True
            ),
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

    def test_unverified_full_candidate_cannot_replace_a0(self) -> None:
        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(
                enabled=True, independent_verification_available=True
            ),
            full_runner=lambda: RouteWorkResult("B"),
        )
        self.assertEqual(final, "A")
        self.assertEqual(receipt.action, ExecutionAction.FULL_STAND_DOWN)
        self.assertFalse(receipt.answer_changed)
        self.assertEqual(receipt.candidate_digest, digest("B"))

    def test_invalid_contract_falls_back_to_a0(self) -> None:
        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(
                enabled=True, independent_verification_available=True
            ),
            full_runner=lambda: RouteWorkResult(
                "B",
                verified=True,
                contract_valid=False,
                failure_reasons=("web_search_without_evidence_url",),
            ),
        )
        self.assertEqual(final, "A")
        self.assertEqual(receipt.action, ExecutionAction.CANDIDATE_REJECTED)
        self.assertEqual(
            receipt.rejection_reasons, ("web_search_without_evidence_url",)
        )

    def test_abstaining_candidate_preserves_a0(self) -> None:
        for route in (Route.VERIFY, Route.FULL):
            with self.subTest(route=route.value):
                runner = lambda: RouteWorkResult("B", abstained=True)
                kwargs = (
                    {"verify_runner": runner}
                    if route is Route.VERIFY
                    else {"full_runner": runner}
                )
                final, receipt = execute_benchmark_route(
                    decision(route),
                    "A",
                    policy=BenchmarkExecutionPolicy(
                        enabled=True,
                        independent_verification_available=True,
                    ),
                    **kwargs,
                )
                self.assertEqual(final, "A")
                self.assertEqual(receipt.selected_digest, digest("A"))
                self.assertEqual(receipt.candidate_digest, digest("B"))
                self.assertEqual(
                    receipt.action, ExecutionAction.CANDIDATE_REJECTED
                )
                self.assertFalse(receipt.answer_changed)
                self.assertIn("preserve_a0", receipt.reason)

    def test_route_budget_rejection_preserves_a0(self) -> None:
        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(
                enabled=True,
                independent_verification_available=True,
                max_route_total_tokens=100,
                max_cached_input_tokens=60,
                max_tool_events=1,
            ),
            full_runner=lambda: RouteWorkResult(
                "B",
                verified=True,
                input_tokens=50,
                cached_input_tokens=70,
                output_tokens=1,
                tool_event_types=("web_search", "command"),
            ),
        )
        self.assertEqual(final, "A")
        self.assertEqual(receipt.action, ExecutionAction.ROUTE_BUDGET_REJECTED)
        self.assertTrue(receipt.route_budget_exceeded)
        self.assertEqual(
            receipt.rejection_reasons,
            (
                "route_total_tokens_exceeded",
                "cached_input_tokens_exceeded",
                "tool_events_exceeded",
            ),
        )
        self.assertEqual(
            receipt.trace()["schema"],
            "foil.adaptive-active-benchmark-receipt.v2",
        )

    def test_full_preflight_stands_down_without_calling_runner(self) -> None:
        called = False

        def run() -> RouteWorkResult:
            nonlocal called
            called = True
            return RouteWorkResult("B", verified=True)

        final, receipt = execute_benchmark_route(
            decision(Route.FULL),
            "A",
            policy=BenchmarkExecutionPolicy(enabled=True),
            full_runner=run,
        )
        self.assertEqual(final, "A")
        self.assertFalse(called)
        self.assertEqual(receipt.route_calls, 0)
        self.assertEqual(receipt.action, ExecutionAction.FULL_STAND_DOWN)

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
