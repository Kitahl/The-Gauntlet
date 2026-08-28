"""Atomic, caller-budgeted multi-tool plans for FOIL evidence-closed runs.

The v1 single-call contract remains unchanged.  A v2 plan binds up to three
ordered tool-family steps inside one reservation.  Limits are supplied by the
caller per run; FOIL contains no product-wide token ceiling.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from egrt_types import digest
from foil_smart_tool_value import PPM, UtilityWeights, jeffreys_bound_ppm
from foil_route_opportunity import QuestionOnlyTask, discover_route_opportunity
from foil_tool_contract import ToolFamily, ToolOperation


PLAN_SCHEMA = "foil.tool-plan-contract.v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_FAMILY = {
    ToolOperation.EXACT_ARITHMETIC: ToolFamily.COMPUTATION,
    ToolOperation.RESTRICTED_PYTHON_OUTPUT: ToolFamily.EXECUTION,
    ToolOperation.WEB_RETRIEVAL: ToolFamily.RETRIEVAL,
    ToolOperation.SCHOLARLY_RETRIEVAL: ToolFamily.RETRIEVAL,
}


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive(name: str, value: object) -> int:
    result = _count(name, value)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value


def _strict(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise ValueError(
            f"closed {label} schema mismatch: missing={sorted(expected - set(raw))}, "
            f"unknown={sorted(set(raw) - expected)}"
        )


@dataclass(frozen=True)
class ToolPlanCost:
    maximum_input_tokens: int = 0
    maximum_cached_input_tokens: int = 0
    maximum_output_tokens: int = 0
    maximum_tool_calls: int = 1
    maximum_search_calls: int = 0
    maximum_fetch_calls: int = 0
    maximum_sources: int = 0
    maximum_evidence_characters: int = 0
    maximum_model_passes: int = 0
    maximum_latency_ms: int = 1_000
    maximum_monetary_microunits: int = 0
    privacy_cost_microunits: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "maximum_input_tokens", "maximum_cached_input_tokens",
            "maximum_output_tokens", "maximum_search_calls",
            "maximum_fetch_calls", "maximum_sources",
            "maximum_evidence_characters", "maximum_model_passes",
            "maximum_latency_ms", "maximum_monetary_microunits",
            "privacy_cost_microunits", "retry_count",
        ):
            _count(name, getattr(self, name))
        if not 1 <= self.maximum_tool_calls <= 8:
            raise ValueError("v2 maximum_tool_calls must be in [1, 8]")
        if self.maximum_search_calls + self.maximum_fetch_calls > self.maximum_tool_calls:
            raise ValueError("search and fetch calls exceed tool-call envelope")
        if self.maximum_sources > self.maximum_fetch_calls and self.maximum_fetch_calls:
            raise ValueError("maximum_sources cannot exceed fetch-call envelope")
        if self.maximum_model_passes > 8:
            raise ValueError("evidence-closed v2 allows at most eight bounded model passes")
        if self.retry_count != 0:
            raise ValueError("evidence-closed v2 does not retry")

    @property
    def maximum_total_tokens(self) -> int:
        return self.maximum_input_tokens + self.maximum_cached_input_tokens + self.maximum_output_tokens

    def trace(self) -> dict[str, int]:
        return {
            "maximum_input_tokens": self.maximum_input_tokens,
            "maximum_cached_input_tokens": self.maximum_cached_input_tokens,
            "maximum_output_tokens": self.maximum_output_tokens,
            "maximum_total_tokens": self.maximum_total_tokens,
            "maximum_tool_calls": self.maximum_tool_calls,
            "maximum_search_calls": self.maximum_search_calls,
            "maximum_fetch_calls": self.maximum_fetch_calls,
            "maximum_sources": self.maximum_sources,
            "maximum_evidence_characters": self.maximum_evidence_characters,
            "maximum_model_passes": self.maximum_model_passes,
            "maximum_latency_ms": self.maximum_latency_ms,
            "maximum_monetary_microunits": self.maximum_monetary_microunits,
            "privacy_cost_microunits": self.privacy_cost_microunits,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ToolPlanCost":
        expected = {
            "maximum_input_tokens", "maximum_cached_input_tokens",
            "maximum_output_tokens", "maximum_total_tokens",
            "maximum_tool_calls", "maximum_search_calls",
            "maximum_fetch_calls", "maximum_sources",
            "maximum_evidence_characters", "maximum_model_passes",
            "maximum_latency_ms", "maximum_monetary_microunits",
            "privacy_cost_microunits", "retry_count",
        }
        _strict(raw, expected, "tool-plan-cost")
        item = cls(**{
            name: raw[name]
            for name in expected
            if name != "maximum_total_tokens"
        })  # type: ignore[arg-type]
        if raw["maximum_total_tokens"] != item.maximum_total_tokens:
            raise ValueError("tool-plan total-token envelope mismatch")
        return item


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    family: ToolFamily
    operation: ToolOperation
    operation_input_digest: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text("step_id", self.step_id)
        object.__setattr__(self, "family", ToolFamily(self.family))
        object.__setattr__(self, "operation", ToolOperation(self.operation))
        if _OPERATION_FAMILY[self.operation] is not self.family:
            raise ValueError("plan operation does not match tool family")
        _sha256("operation_input_digest", self.operation_input_digest)
        if not isinstance(self.depends_on, tuple) or not all(
            isinstance(item, str) and item for item in self.depends_on
        ):
            raise TypeError("depends_on must be a tuple of step ids")

    def trace(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "family": self.family.value,
            "operation": self.operation.value,
            "operation_input_digest": self.operation_input_digest,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "PlanStep":
        expected = {
            "step_id", "family", "operation", "operation_input_digest",
            "depends_on",
        }
        _strict(raw, expected, "tool-plan-step")
        depends_on = raw["depends_on"]
        if not isinstance(depends_on, list):
            raise TypeError("serialized depends_on must be a list")
        return cls(
            step_id=raw["step_id"],  # type: ignore[arg-type]
            family=raw["family"],  # type: ignore[arg-type]
            operation=raw["operation"],  # type: ignore[arg-type]
            operation_input_digest=raw["operation_input_digest"],  # type: ignore[arg-type]
            depends_on=tuple(depends_on),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class ToolPlanContractV2:
    task_id: str
    question_digest: str
    a0_digest: str
    plan_id: str
    plan_version: str
    steps: tuple[PlanStep, ...]
    cost: ToolPlanCost
    provider_cap_enforced: bool
    schema: str = PLAN_SCHEMA
    read_only: bool = True
    benchmark_only: bool = True
    answer_change_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema != PLAN_SCHEMA:
            raise ValueError("unsupported tool-plan schema")
        for name in ("task_id", "plan_id", "plan_version"):
            _text(name, getattr(self, name))
        _sha256("question_digest", self.question_digest)
        _sha256("a0_digest", self.a0_digest)
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= 3 or not all(
            isinstance(item, PlanStep) for item in self.steps
        ):
            raise ValueError("steps must contain one to three PlanStep values")
        ids: set[str] = set()
        for step in self.steps:
            if step.step_id in ids:
                raise ValueError("plan step ids must be unique")
            if any(parent not in ids for parent in step.depends_on):
                raise ValueError("plan dependencies must reference earlier steps")
            ids.add(step.step_id)
        if not isinstance(self.cost, ToolPlanCost):
            raise TypeError("cost must be ToolPlanCost")
        if not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")
        if self.cost.maximum_total_tokens and not self.provider_cap_enforced:
            raise ValueError("token-consuming plan requires provider-enforced cap")
        if self.read_only is not True or self.benchmark_only is not True or self.answer_change_authority is not False:
            raise ValueError("v2 plans are read-only, benchmark-only, and non-authoritative")

    @property
    def route_key(self) -> str:
        return ">".join(step.operation.value for step in self.steps)

    def body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "a0_digest": self.a0_digest,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "route_key": self.route_key,
            "steps": [item.trace() for item in self.steps],
            "cost": self.cost.trace(),
            "provider_cap_enforced": self.provider_cap_enforced,
            "read_only": True,
            "benchmark_only": True,
            "answer_change_authority": False,
            "raw_question_stored": False,
            "raw_a0_stored": False,
        }

    @property
    def contract_digest(self) -> str:
        return digest(self.body())

    def trace(self) -> dict[str, object]:
        body = self.body()
        body["contract_sha256"] = self.contract_digest
        return body

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ToolPlanContractV2":
        expected = {
            "schema", "task_id", "question_digest", "a0_digest", "plan_id",
            "plan_version", "route_key", "steps", "cost",
            "provider_cap_enforced", "read_only", "benchmark_only",
            "answer_change_authority", "raw_question_stored", "raw_a0_stored",
            "contract_sha256",
        }
        _strict(raw, expected, "tool-plan-contract")
        if raw["raw_question_stored"] is not False or raw["raw_a0_stored"] is not False:
            raise ValueError("tool plan cannot persist raw question or A0")
        steps = raw["steps"]
        cost = raw["cost"]
        if not isinstance(steps, list) or not isinstance(cost, Mapping):
            raise TypeError("serialized tool plan requires steps list and cost mapping")
        item = cls(
            task_id=raw["task_id"],  # type: ignore[arg-type]
            question_digest=raw["question_digest"],  # type: ignore[arg-type]
            a0_digest=raw["a0_digest"],  # type: ignore[arg-type]
            plan_id=raw["plan_id"],  # type: ignore[arg-type]
            plan_version=raw["plan_version"],  # type: ignore[arg-type]
            steps=tuple(PlanStep.from_mapping(step) for step in steps),  # type: ignore[arg-type]
            cost=ToolPlanCost.from_mapping(cost),
            provider_cap_enforced=raw["provider_cap_enforced"],  # type: ignore[arg-type]
            schema=raw["schema"],  # type: ignore[arg-type]
            read_only=raw["read_only"],  # type: ignore[arg-type]
            benchmark_only=raw["benchmark_only"],  # type: ignore[arg-type]
            answer_change_authority=raw["answer_change_authority"],  # type: ignore[arg-type]
        )
        if raw["route_key"] != item.route_key:
            raise ValueError("tool-plan route key mismatch")
        if raw["contract_sha256"] != item.contract_digest:
            raise ValueError("tool-plan contract digest mismatch")
        return item


@dataclass(frozen=True)
class PlanEvidence:
    route_key: str
    plan_version: str
    attempts: int
    rescues: int
    damages: int
    invalids: int
    evidence_digest: str
    fresh: bool

    def __post_init__(self) -> None:
        _text("route_key", self.route_key)
        _text("plan_version", self.plan_version)
        for name in ("attempts", "rescues", "damages", "invalids"):
            _count(name, getattr(self, name))
        if any(getattr(self, name) > self.attempts for name in ("rescues", "damages", "invalids")):
            raise ValueError("plan outcome counts cannot exceed attempts")
        if self.rescues + self.damages > self.attempts:
            raise ValueError("one attempt cannot be both rescue and damage")
        _sha256("evidence_digest", self.evidence_digest)
        if not isinstance(self.fresh, bool):
            raise TypeError("fresh must be bool")


class PlanDecisionStatus(str, Enum):
    EXECUTE = "EXECUTE"
    EXECUTE_EXPLORATION = "EXECUTE_EXPLORATION"
    DECLINE_DISABLED = "DECLINE_DISABLED"
    DECLINE_BUDGET = "DECLINE_BUDGET"
    DECLINE_UNCALIBRATED = "DECLINE_UNCALIBRATED"
    DECLINE_STALE = "DECLINE_STALE"
    DECLINE_NONPOSITIVE_VALUE = "DECLINE_NONPOSITIVE_VALUE"


@dataclass(frozen=True)
class PlanValuePolicy:
    enabled: bool = False
    benchmark_exploration: bool = False
    minimum_observations: int = 20
    interval_mass_ppm: int = 950_000
    minimum_utility_microunits: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.benchmark_exploration, bool):
            raise TypeError("enabled and benchmark_exploration must be bool")
        _count("minimum_observations", self.minimum_observations)
        if not 0 < self.interval_mass_ppm < PPM:
            raise ValueError("interval_mass_ppm must be strictly inside (0, PPM)")
        _count("minimum_utility_microunits", self.minimum_utility_microunits)


@dataclass(frozen=True)
class PlanDecision:
    status: PlanDecisionStatus
    reason: str
    utility_lower_bound_microunits: int | None
    rescue_lcb_ppm: int | None
    damage_ucb_ppm: int | None
    invalid_ucb_ppm: int | None
    maximum_total_tokens: int
    observations: int
    route_key: str

    @property
    def executes(self) -> bool:
        return self.status in {PlanDecisionStatus.EXECUTE, PlanDecisionStatus.EXECUTE_EXPLORATION}

    def trace(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "utility_lower_bound_microunits": self.utility_lower_bound_microunits,
            "rescue_lcb_ppm": self.rescue_lcb_ppm,
            "damage_ucb_ppm": self.damage_ucb_ppm,
            "invalid_ucb_ppm": self.invalid_ucb_ppm,
            "maximum_total_tokens": self.maximum_total_tokens,
            "observations": self.observations,
            "route_key": self.route_key,
            "probabilities_from_model_self_report": False,
        }


def decide_plan_prelaunch(
    plan: ToolPlanContractV2,
    *,
    remaining_unreserved_tokens: int,
    weights: UtilityWeights,
    policy: PlanValuePolicy,
    evidence: PlanEvidence | None,
) -> PlanDecision:
    """Price one complete plan using counted route outcomes, never self-confidence."""

    if not isinstance(plan, ToolPlanContractV2):
        raise TypeError("plan must be ToolPlanContractV2")
    _count("remaining_unreserved_tokens", remaining_unreserved_tokens)
    if not isinstance(weights, UtilityWeights):
        raise TypeError("weights must be UtilityWeights")
    if not isinstance(policy, PlanValuePolicy):
        raise TypeError("policy must be PlanValuePolicy")
    base = {
        "maximum_total_tokens": plan.cost.maximum_total_tokens,
        "observations": 0 if evidence is None else evidence.attempts,
        "route_key": plan.route_key,
    }
    if not policy.enabled:
        return PlanDecision(PlanDecisionStatus.DECLINE_DISABLED, "plan_value_gate_disabled", None, None, None, None, **base)
    if plan.cost.maximum_total_tokens > remaining_unreserved_tokens:
        return PlanDecision(PlanDecisionStatus.DECLINE_BUDGET, "caller_token_budget_insufficient", None, None, None, None, **base)
    matches = bool(
        evidence is not None
        and evidence.route_key == plan.route_key
        and evidence.plan_version == plan.plan_version
    )
    if not matches or evidence is None or evidence.attempts < policy.minimum_observations:
        if policy.benchmark_exploration:
            return PlanDecision(PlanDecisionStatus.EXECUTE_EXPLORATION, "explicit_bounded_plan_exploration", None, None, None, None, **base)
        return PlanDecision(PlanDecisionStatus.DECLINE_UNCALIBRATED, "no_matching_minimum_plan_evidence", None, None, None, None, **base)
    if not evidence.fresh:
        return PlanDecision(PlanDecisionStatus.DECLINE_STALE, "plan_evidence_stale", None, None, None, None, **base)

    tail_ppm = (PPM - policy.interval_mass_ppm) // 2
    rescue_lcb = jeffreys_bound_ppm(successes=evidence.rescues, attempts=evidence.attempts, quantile_ppm=tail_ppm)
    damage_ucb = jeffreys_bound_ppm(successes=evidence.damages, attempts=evidence.attempts, quantile_ppm=PPM - tail_ppm)
    invalid_ucb = jeffreys_bound_ppm(successes=evidence.invalids, attempts=evidence.attempts, quantile_ppm=PPM - tail_ppm)
    cost = (
        plan.cost.maximum_total_tokens * weights.token_price_microunits
        + plan.cost.maximum_latency_ms * weights.latency_price_microunits_per_ms
        + plan.cost.maximum_monetary_microunits
        + plan.cost.privacy_cost_microunits
    )
    numerator = (
        rescue_lcb * weights.rescue_value_microunits
        - damage_ucb * weights.damage_loss_microunits
        - invalid_ucb * weights.invalid_loss_microunits
    )
    utility = math.floor(numerator / PPM) - cost
    if utility <= policy.minimum_utility_microunits:
        status = PlanDecisionStatus.DECLINE_NONPOSITIVE_VALUE
        reason = "conservative_plan_utility_not_above_margin"
    else:
        status = PlanDecisionStatus.EXECUTE
        reason = "conservative_plan_utility_positive"
    return PlanDecision(status, reason, utility, rescue_lcb, damage_ucb, invalid_ucb, **base)


def choose_plan(
    plans: Sequence[tuple[ToolPlanContractV2, PlanDecision]],
) -> tuple[ToolPlanContractV2, PlanDecision] | None:
    """Select maximum lower-bound utility, then least tokens and fewest calls."""

    executable = [(plan, decision) for plan, decision in plans if decision.executes]
    if not executable:
        return None
    return min(
        executable,
        key=lambda row: (
            -(row[1].utility_lower_bound_microunits or 0),
            row[0].cost.maximum_total_tokens,
            row[0].cost.maximum_tool_calls,
            row[0].route_key,
        ),
    )


_CAPABILITY_STEP = {
    "SYMBOLIC_COMPUTATION": (ToolFamily.COMPUTATION, ToolOperation.EXACT_ARITHMETIC),
    "CODE_EXECUTION": (ToolFamily.EXECUTION, ToolOperation.RESTRICTED_PYTHON_OUTPUT),
    "WEB_SEARCH": (ToolFamily.RETRIEVAL, ToolOperation.WEB_RETRIEVAL),
    "SCHOLARLY_SEARCH": (ToolFamily.RETRIEVAL, ToolOperation.SCHOLARLY_RETRIEVAL),
}


def build_plan_catalog(
    raw_task: Mapping[str, object],
    a0: str,
    *,
    costs_by_route_key: Mapping[str, ToolPlanCost],
    provider_cap_enforced: bool,
    plan_version: str,
) -> tuple[ToolPlanContractV2, ...]:
    """Build deterministic single and retrieve-then-execute plan variants.

    Costs are caller-supplied.  Missing cost profiles simply omit that variant;
    no product-wide token or call limit is hidden here.
    """

    task = QuestionOnlyTask.from_mapping(raw_task)
    _text("a0", a0)
    _text("plan_version", plan_version)
    if not isinstance(provider_cap_enforced, bool):
        raise TypeError("provider_cap_enforced must be bool")
    opportunity = discover_route_opportunity(raw_task)
    capabilities = [item.capability for item in opportunity.candidates if item.capability in _CAPABILITY_STEP]
    variants: list[tuple[str, ...]] = [(capability,) for capability in capabilities]
    retrieval = [item for item in capabilities if _CAPABILITY_STEP[item][0] is ToolFamily.RETRIEVAL]
    executable = [item for item in capabilities if _CAPABILITY_STEP[item][0] is not ToolFamily.RETRIEVAL]
    variants.extend((source, target) for source in retrieval for target in executable)
    plans: list[ToolPlanContractV2] = []
    for variant in variants:
        route_key = ">".join(_CAPABILITY_STEP[item][1].value for item in variant)
        cost = costs_by_route_key.get(route_key)
        if cost is None:
            continue
        steps: list[PlanStep] = []
        for index, capability in enumerate(variant):
            family, operation = _CAPABILITY_STEP[capability]
            step_id = f"step-{index + 1}-{operation.value.lower()}"
            steps.append(
                PlanStep(
                    step_id,
                    family,
                    operation,
                    task.question_digest,
                    () if index == 0 else (steps[index - 1].step_id,),
                )
            )
        plans.append(
            ToolPlanContractV2(
                task.task_id,
                task.question_digest,
                digest(a0),
                f"plan-{digest({'task': task.task_id, 'route': route_key, 'version': plan_version})[:16]}",
                plan_version,
                tuple(steps),
                cost,
                provider_cap_enforced,
            )
        )
    return tuple(plans)


@dataclass(frozen=True)
class ContinuationEvidence:
    attempts: int
    helpful_decision_changes: int
    harmful_decision_changes: int
    evidence_digest: str
    fresh: bool

    def __post_init__(self) -> None:
        for name in ("attempts", "helpful_decision_changes", "harmful_decision_changes"):
            _count(name, getattr(self, name))
        if self.helpful_decision_changes + self.harmful_decision_changes > self.attempts:
            raise ValueError("continuation outcomes exceed attempts")
        _sha256("evidence_digest", self.evidence_digest)
        if not isinstance(self.fresh, bool):
            raise TypeError("fresh must be bool")


@dataclass(frozen=True)
class ContinuationDecision:
    execute: bool
    reason: str
    utility_lower_bound_microunits: int | None
    helpful_lcb_ppm: int | None
    harmful_ucb_ppm: int | None

    def trace(self) -> dict[str, object]:
        return {
            "execute": self.execute,
            "reason": self.reason,
            "utility_lower_bound_microunits": self.utility_lower_bound_microunits,
            "helpful_lcb_ppm": self.helpful_lcb_ppm,
            "harmful_ucb_ppm": self.harmful_ucb_ppm,
            "probabilities_from_model_self_report": False,
        }


def decide_incremental_query(
    *,
    incremental_cost_microunits: int,
    weights: UtilityWeights,
    evidence: ContinuationEvidence | None,
    minimum_observations: int,
    interval_mass_ppm: int = 950_000,
    benchmark_exploration: bool = False,
) -> ContinuationDecision:
    """Run another query only when conservative marginal value is positive."""

    _count("incremental_cost_microunits", incremental_cost_microunits)
    _count("minimum_observations", minimum_observations)
    if not 0 < interval_mass_ppm < PPM:
        raise ValueError("interval_mass_ppm must be strictly inside (0, PPM)")
    if evidence is None or evidence.attempts < minimum_observations:
        return ContinuationDecision(
            benchmark_exploration,
            "explicit_continuation_exploration" if benchmark_exploration else "continuation_uncalibrated",
            None, None, None,
        )
    if not evidence.fresh:
        return ContinuationDecision(False, "continuation_evidence_stale", None, None, None)
    tail = (PPM - interval_mass_ppm) // 2
    helpful = jeffreys_bound_ppm(
        successes=evidence.helpful_decision_changes,
        attempts=evidence.attempts,
        quantile_ppm=tail,
    )
    harmful = jeffreys_bound_ppm(
        successes=evidence.harmful_decision_changes,
        attempts=evidence.attempts,
        quantile_ppm=PPM - tail,
    )
    utility = math.floor(
        (
            helpful * weights.rescue_value_microunits
            - harmful * weights.damage_loss_microunits
        ) / PPM
    ) - incremental_cost_microunits
    return ContinuationDecision(
        utility > 0,
        "positive_marginal_query_value" if utility > 0 else "nonpositive_marginal_query_value",
        utility,
        helpful,
        harmful,
    )
