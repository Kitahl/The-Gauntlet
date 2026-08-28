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
    FULL_STAND_DOWN = "FULL_STAND_DOWN"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    ROUTE_BUDGET_REJECTED = "ROUTE_BUDGET_REJECTED"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class BenchmarkExecutionPolicy:
    enabled: bool = False
    benchmark_only: bool = True
    max_route_calls: int = 1
    independent_verification_available: bool = False
    max_route_total_tokens: int | None = None
    max_cached_input_tokens: int | None = None
    max_tool_events: int | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, bool)
            for value in (
                self.enabled,
                self.benchmark_only,
                self.independent_verification_available,
            )
        ):
            raise TypeError(
                "enabled, benchmark_only, and independent_verification_available "
                "must be bool"
            )
        if self.benchmark_only is not True:
            raise ValueError("adaptive execution has no production authority")
        if self.max_route_calls != 1:
            raise ValueError("benchmark execution is frozen at one route call")
        for name in (
            "max_route_total_tokens",
            "max_cached_input_tokens",
            "max_tool_events",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")


@dataclass(frozen=True)
class RouteWorkResult:
    answer: str
    verified: bool = False
    abstained: bool = False
    contract_valid: bool = True
    failure_reasons: tuple[str, ...] = ()
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_event_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise ValueError("answer must be non-empty text")
        if not all(
            isinstance(value, bool)
            for value in (self.verified, self.abstained, self.contract_valid)
        ):
            raise TypeError("verified, abstained, and contract_valid must be bool")
        for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.tool_event_types, tuple) or not all(
            isinstance(value, str) and value for value in self.tool_event_types
        ):
            raise TypeError("tool_event_types must be a tuple of non-empty strings")
        if not isinstance(self.failure_reasons, tuple) or not all(
            isinstance(value, str) and value for value in self.failure_reasons
        ):
            raise TypeError("failure_reasons must be a tuple of non-empty strings")
        if self.contract_valid and self.failure_reasons:
            raise ValueError("valid work cannot carry failure_reasons")
        if not self.contract_valid and not self.failure_reasons:
            raise ValueError("invalid work must carry at least one failure_reason")


@dataclass(frozen=True)
class ActiveRouteReceipt:
    route: Route
    action: ExecutionAction
    reason: str
    a0_digest: str
    selected_digest: str | None
    candidate_digest: str | None
    route_calls: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    tool_event_types: tuple[str, ...]
    answer_changed: bool
    candidate_verified: bool
    contract_valid: bool
    rejection_reasons: tuple[str, ...]
    route_budget_exceeded: bool
    benchmark_only: bool = True
    production_authorized: bool = False
    promotion_authorized: bool = False

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.adaptive-active-benchmark-receipt.v2",
            "route": self.route.value,
            "action": self.action.value,
            "reason": self.reason,
            "a0_digest": self.a0_digest,
            "selected_digest": self.selected_digest,
            "candidate_digest": self.candidate_digest,
            "route_calls": self.route_calls,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "tool_event_types": list(self.tool_event_types),
            "answer_changed": self.answer_changed,
            "candidate_verified": self.candidate_verified,
            "contract_valid": self.contract_valid,
            "rejection_reasons": list(self.rejection_reasons),
            "route_budget_exceeded": self.route_budget_exceeded,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "raw_answer_stored": False,
        }


Runner = Callable[[], RouteWorkResult]


def _route_budget_failures(
    work: RouteWorkResult, policy: BenchmarkExecutionPolicy
) -> tuple[str, ...]:
    failures: list[str] = []
    total_tokens = work.input_tokens + work.cached_input_tokens + work.output_tokens
    if (
        policy.max_route_total_tokens is not None
        and total_tokens > policy.max_route_total_tokens
    ):
        failures.append("route_total_tokens_exceeded")
    if (
        policy.max_cached_input_tokens is not None
        and work.cached_input_tokens > policy.max_cached_input_tokens
    ):
        failures.append("cached_input_tokens_exceeded")
    if (
        policy.max_tool_events is not None
        and len(work.tool_event_types) > policy.max_tool_events
    ):
        failures.append("tool_events_exceeded")
    return tuple(failures)


def finalize_benchmark_work(
    route: Route,
    a0: str,
    work: RouteWorkResult,
    *,
    policy: BenchmarkExecutionPolicy,
) -> tuple[str, ActiveRouteReceipt]:
    """Apply the shared benchmark admission boundary to completed route work.

    This function does not launch work or authorize a route. It lets the legacy
    shadow bridge and smart-tool controller share identical A0-preservation,
    verification, contract, and route-budget rules.
    """

    route = Route(route)
    if route is Route.DIRECT:
        raise ValueError("DIRECT has no completed route work to finalize")
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(work, RouteWorkResult):
        raise TypeError("work must be RouteWorkResult")
    if not isinstance(policy, BenchmarkExecutionPolicy):
        raise TypeError("policy must be BenchmarkExecutionPolicy")
    if not policy.enabled:
        raise ValueError("completed work cannot be finalized by a disabled executor")
    if route is Route.FULL and not policy.independent_verification_available:
        raise ValueError("FULL work requires independent verification availability")

    budget_failures = _route_budget_failures(work, policy)
    if budget_failures:
        action = ExecutionAction.ROUTE_BUDGET_REJECTED
        selected = a0
        reason = f"{route.value.lower()}_route_budget_exceeded"
    elif not work.contract_valid:
        action = ExecutionAction.CANDIDATE_REJECTED
        selected = a0
        reason = f"{route.value.lower()}_candidate_contract_invalid"
    elif work.abstained:
        action = ExecutionAction.CANDIDATE_REJECTED
        selected = a0
        reason = f"{route.value.lower()}_candidate_abstained_preserve_a0"
    elif route is Route.VERIFY and not work.verified:
        action = ExecutionAction.VERIFY_STAND_DOWN
        selected = a0
        reason = "verify_not_confirmed"
    elif route is Route.FULL and not work.verified:
        action = ExecutionAction.FULL_STAND_DOWN
        selected = a0
        reason = "full_candidate_not_independently_verified"
    elif route is Route.VERIFY:
        action = ExecutionAction.SELECT_VERIFIED
        selected = work.answer
        reason = "verified_candidate_selected"
    else:
        action = ExecutionAction.SELECT_FULL
        selected = work.answer
        reason = "verified_full_candidate_selected_in_benchmark"

    a0_digest = digest(a0)
    receipt = ActiveRouteReceipt(
        route=route,
        action=action,
        reason=reason,
        a0_digest=a0_digest,
        selected_digest=digest(selected),
        candidate_digest=digest(work.answer),
        route_calls=1,
        input_tokens=work.input_tokens,
        cached_input_tokens=work.cached_input_tokens,
        output_tokens=work.output_tokens,
        tool_event_types=work.tool_event_types,
        answer_changed=selected != a0,
        candidate_verified=work.verified,
        contract_valid=work.contract_valid,
        rejection_reasons=work.failure_reasons + budget_failures,
        route_budget_exceeded=bool(budget_failures),
    )
    return selected, receipt


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
            route=Route.DIRECT if not policy.enabled else decision.route,
            action=ExecutionAction.KEEP_A0,
            reason=reason,
            a0_digest=a0_digest,
            selected_digest=a0_digest,
            candidate_digest=None,
            route_calls=0,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            tool_event_types=(),
            answer_changed=False,
            candidate_verified=False,
            contract_valid=True,
            rejection_reasons=(),
            route_budget_exceeded=False,
        )
        return a0, receipt

    if (
        decision.route is Route.FULL
        and not policy.independent_verification_available
    ):
        if verify_runner is not None:
            raise ValueError("FULL must not receive a verify runner")
        receipt = ActiveRouteReceipt(
            route=decision.route,
            action=ExecutionAction.FULL_STAND_DOWN,
            reason="no_independent_verification_available",
            a0_digest=a0_digest,
            selected_digest=a0_digest,
            candidate_digest=None,
            route_calls=0,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            tool_event_types=(),
            answer_changed=False,
            candidate_verified=False,
            contract_valid=True,
            rejection_reasons=(),
            route_budget_exceeded=False,
        )
        return a0, receipt

    if decision.route is Route.VERIFY:
        if verify_runner is None or full_runner is not None:
            raise ValueError("VERIFY requires exactly one verify runner")
        work = verify_runner()
        if not isinstance(work, RouteWorkResult):
            raise TypeError("verify runner must return RouteWorkResult")
    elif decision.route is Route.FULL:
        if full_runner is None or verify_runner is not None:
            raise ValueError("FULL requires exactly one full runner")
        work = full_runner()
        if not isinstance(work, RouteWorkResult):
            raise TypeError("full runner must return RouteWorkResult")
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError("unsupported adaptive route")
    return finalize_benchmark_work(decision.route, a0, work, policy=policy)
