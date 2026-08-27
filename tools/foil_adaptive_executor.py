"""Benchmark-only execution bridge for FOIL adaptive-route decisions.

``foil_adaptive_route`` deliberately emits immutable shadow recommendations.
This module does not weaken that type.  It consumes one such recommendation at
an explicit benchmark boundary and executes exactly the named route through a
caller-supplied runner.  It never grants production or promotion authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from egrt_types import digest
from foil_adaptive_route import Route, ShadowRouteDecision


class ExecutionAction(str, Enum):
    KEEP_A0 = "KEEP_A0"
    VERIFY_STAND_DOWN = "VERIFY_STAND_DOWN"
    SELECT_VERIFIED = "SELECT_VERIFIED"
    SELECT_FULL = "SELECT_FULL"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class BenchmarkExecutionPolicy:
    enabled: bool = False
    benchmark_only: bool = True
    max_route_calls: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(
            self.benchmark_only, bool
        ):
            raise TypeError("enabled and benchmark_only must be bool")
        if self.benchmark_only is not True:
            raise ValueError("adaptive execution has no production authority")
        if self.max_route_calls != 1:
            raise ValueError("benchmark execution is frozen at one route call")


@dataclass(frozen=True)
class RouteWorkResult:
    answer: str
    verified: bool = False
    abstained: bool = False
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_event_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise ValueError("answer must be non-empty text")
        if not isinstance(self.verified, bool) or not isinstance(self.abstained, bool):
            raise TypeError("verified and abstained must be bool")
        for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.tool_event_types, tuple) or not all(
            isinstance(value, str) and value for value in self.tool_event_types
        ):
            raise TypeError("tool_event_types must be a tuple of non-empty strings")


@dataclass(frozen=True)
class ActiveRouteReceipt:
    route: Route
    action: ExecutionAction
    reason: str
    a0_digest: str
    selected_digest: str | None
    route_calls: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    tool_event_types: tuple[str, ...]
    answer_changed: bool
    benchmark_only: bool = True
    production_authorized: bool = False
    promotion_authorized: bool = False

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.adaptive-active-benchmark-receipt.v1",
            "route": self.route.value,
            "action": self.action.value,
            "reason": self.reason,
            "a0_digest": self.a0_digest,
            "selected_digest": self.selected_digest,
            "route_calls": self.route_calls,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "tool_event_types": list(self.tool_event_types),
            "answer_changed": self.answer_changed,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "raw_answer_stored": False,
        }


Runner = Callable[[], RouteWorkResult]


def execute_benchmark_route(
    decision: ShadowRouteDecision,
    a0: str,
    *,
    policy: BenchmarkExecutionPolicy = BenchmarkExecutionPolicy(),
    verify_runner: Runner | None = None,
    full_runner: Runner | None = None,
) -> tuple[str, ActiveRouteReceipt]:
    """Execute one recommendation without changing its shadow authority type."""

    if not isinstance(decision, ShadowRouteDecision):
        raise TypeError("decision must be ShadowRouteDecision")
    if not isinstance(policy, BenchmarkExecutionPolicy):
        raise TypeError("policy must be BenchmarkExecutionPolicy")
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    a0_digest = digest(a0)
    if decision.a0_digest != a0_digest:
        raise ValueError("adaptive decision does not bind A0")
    if decision.shadow_only is not True or decision.execution_authorized:
        raise ValueError("executor accepts only the original shadow recommendation")

    if not policy.enabled or decision.route is Route.DIRECT:
        if verify_runner is not None or full_runner is not None:
            raise ValueError("stand-down/DIRECT must not receive a route runner")
        reason = "executor_disabled" if not policy.enabled else "direct_route"
        receipt = ActiveRouteReceipt(
            Route.DIRECT if not policy.enabled else decision.route,
            ExecutionAction.KEEP_A0,
            reason,
            a0_digest,
            a0_digest,
            0,
            0,
            0,
            0,
            (),
            False,
        )
        return a0, receipt

    if decision.route is Route.VERIFY:
        if verify_runner is None or full_runner is not None:
            raise ValueError("VERIFY requires exactly one verify runner")
        work = verify_runner()
        if not isinstance(work, RouteWorkResult):
            raise TypeError("verify runner must return RouteWorkResult")
        if work.abstained or not work.verified:
            action = (
                ExecutionAction.ABSTAIN
                if work.abstained
                else ExecutionAction.VERIFY_STAND_DOWN
            )
            selected = None if work.abstained else a0
            reason = "verify_abstained" if work.abstained else "verify_not_confirmed"
        else:
            action = ExecutionAction.SELECT_VERIFIED
            selected = work.answer
            reason = "verified_candidate_selected"
    elif decision.route is Route.FULL:
        if full_runner is None or verify_runner is not None:
            raise ValueError("FULL requires exactly one full runner")
        work = full_runner()
        if not isinstance(work, RouteWorkResult):
            raise TypeError("full runner must return RouteWorkResult")
        if work.abstained:
            action = ExecutionAction.ABSTAIN
            selected = None
            reason = "full_route_abstained"
        else:
            action = ExecutionAction.SELECT_FULL
            selected = work.answer
            reason = "full_candidate_selected_in_benchmark"
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError("unsupported adaptive route")

    final = "ABSTAIN" if selected is None else selected
    selected_digest = None if selected is None else digest(selected)
    receipt = ActiveRouteReceipt(
        decision.route,
        action,
        reason,
        a0_digest,
        selected_digest,
        1,
        work.input_tokens,
        work.cached_input_tokens,
        work.output_tokens,
        work.tool_event_types,
        selected is not None and selected != a0,
    )
    return final, receipt
