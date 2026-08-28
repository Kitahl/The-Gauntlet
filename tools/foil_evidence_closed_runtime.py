"""Benchmark-only retrieval/computation -> compare -> construct -> select runtime.

This module is an additive v2 path.  It does not alter the frozen smart-tool v1
runtime.  One caller-budgeted plan is reserved atomically; every failure keeps
A0.  The constructor never sees A0, the semantic comparator never sees answer
identity, and production/promotion authority is always false.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from egrt_types import digest
from foil_adaptive_executor import (
    BenchmarkExecutionPolicy,
    RouteWorkResult,
    finalize_benchmark_work,
)
from foil_adaptive_route import Route
from foil_answer_selector import (
    SelectionOutcome,
    SelectionReceipt,
    SelectorPolicy,
    select_answer,
)
from foil_benchmark_budget import BenchmarkTokenLedger
from foil_bounded_answer_constructor import (
    ConstructorOutcome,
    ConstructorPolicy,
    ConstructorReceipt,
    ConstructorRunner,
    run_bounded_constructor,
)
from foil_evidence_contract import (
    CandidateOrigin,
    EvidencePacket,
    QuestionObligation,
    single_answer_candidate,
)
from foil_retrieval_claim_comparator import (
    AnswerAssessment,
    ComparatorPolicy,
    SemanticComparator,
    compare_candidate,
)
from foil_route_opportunity import (
    OpportunityStatus,
    QuestionOnlyTask,
    discover_route_opportunity,
)
from foil_smart_tool_value import UtilityWeights
from foil_tool_contract import ToolOperation
from foil_tool_plan_v2 import (
    PlanDecision,
    PlanEvidence,
    PlanValuePolicy,
    ToolPlanContractV2,
    choose_plan,
    decide_plan_prelaunch,
)


RUN_SCHEMA = "foil.evidence-closed-benchmark-run.v1"


_OPERATION_CAPABILITY = {
    ToolOperation.EXACT_ARITHMETIC: "SYMBOLIC_COMPUTATION",
    ToolOperation.RESTRICTED_PYTHON_OUTPUT: "CODE_EXECUTION",
    ToolOperation.WEB_RETRIEVAL: "WEB_SEARCH",
    ToolOperation.SCHOLARLY_RETRIEVAL: "SCHOLARLY_SEARCH",
}


EvidencePlanRunner = Callable[[ToolPlanContractV2, QuestionOnlyTask], EvidencePacket]


@dataclass(frozen=True)
class EvidenceClosedRuntimePolicy:
    enabled: bool
    plan_value: PlanValuePolicy
    weights: UtilityWeights
    comparator: ComparatorPolicy
    constructor: ConstructorPolicy
    selector: SelectorPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        if not isinstance(self.plan_value, PlanValuePolicy):
            raise TypeError("plan_value must be PlanValuePolicy")
        if not isinstance(self.weights, UtilityWeights):
            raise TypeError("weights must be UtilityWeights")
        if not isinstance(self.comparator, ComparatorPolicy):
            raise TypeError("comparator must be ComparatorPolicy")
        if not isinstance(self.constructor, ConstructorPolicy):
            raise TypeError("constructor must be ConstructorPolicy")
        if not isinstance(self.selector, SelectorPolicy):
            raise TypeError("selector must be SelectorPolicy")
        if self.enabled != self.plan_value.enabled:
            raise ValueError("runtime and plan-value gate must be enabled together")


@dataclass(frozen=True)
class EvidenceClosedRunReceipt:
    task_id: str
    question_digest: str
    a0_digest: str
    final_digest: str
    opportunity_status: str
    reason: str
    plan_decisions: tuple[dict[str, object], ...]
    selected_plan: dict[str, object] | None
    evidence_packet: dict[str, object] | None
    a0_assessment: dict[str, object] | None
    constructor: dict[str, object] | None
    b_assessment: dict[str, object] | None
    selection: dict[str, object] | None
    active_route: dict[str, object] | None
    ledger_before: dict[str, object]
    ledger_after: dict[str, object]
    answer_changed: bool
    cost_accounting_complete: bool
    benchmark_only: bool = True
    production_authorized: bool = False
    promotion_authorized: bool = False

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": RUN_SCHEMA,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "a0_digest": self.a0_digest,
            "final_digest": self.final_digest,
            "opportunity_status": self.opportunity_status,
            "reason": self.reason,
            "plan_decisions": list(self.plan_decisions),
            "selected_plan": self.selected_plan,
            "evidence_packet": self.evidence_packet,
            "a0_assessment": self.a0_assessment,
            "constructor": self.constructor,
            "b_assessment": self.b_assessment,
            "selection": self.selection,
            "active_route": self.active_route,
            "ledger_before": self.ledger_before,
            "ledger_after": self.ledger_after,
            "answer_changed": self.answer_changed,
            "cost_accounting_complete": self.cost_accounting_complete,
            "a0_fallback": True,
            "question_only_plan_selection": True,
            "constructor_a0_exposed": False,
            "comparator_answer_identity_exposed": False,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "raw_question_stored": False,
            "raw_a0_stored": False,
            "raw_candidate_stored": False,
            "raw_evidence_stored": False,
        }
        body["run_sha256"] = digest(body)
        return body


def _receipt(
    task: QuestionOnlyTask,
    a0: str,
    *,
    final: str | None = None,
    opportunity_status: str,
    reason: str,
    plan_decisions: tuple[dict[str, object], ...],
    selected_plan: dict[str, object] | None,
    packet: EvidencePacket | None,
    a0_assessment: AnswerAssessment | None,
    constructor: ConstructorReceipt | None,
    b_assessment: AnswerAssessment | None,
    selection: SelectionReceipt | None,
    active_route: dict[str, object] | None,
    ledger_before: dict[str, object],
    ledger: BenchmarkTokenLedger,
    cost_accounting_complete: bool,
) -> EvidenceClosedRunReceipt:
    selected = a0 if final is None else final
    return EvidenceClosedRunReceipt(
        task.task_id,
        task.question_digest,
        digest(a0),
        digest(selected),
        opportunity_status,
        reason,
        plan_decisions,
        selected_plan,
        None if packet is None else packet.trace(),
        None if a0_assessment is None else a0_assessment.trace(),
        None if constructor is None else constructor.trace(),
        None if b_assessment is None else b_assessment.trace(),
        None if selection is None else selection.trace(),
        active_route,
        ledger_before,
        ledger.trace(),
        selected != a0,
        cost_accounting_complete,
    )


def _validate_packet(packet: EvidencePacket, plan: ToolPlanContractV2) -> None:
    cost = plan.cost
    total_chars = sum(len(document.content) for document in packet.documents)
    failures: list[str] = []
    if packet.actual_total_tokens > cost.maximum_total_tokens:
        failures.append("retrieval_tokens_exceeded")
    if packet.tool_calls > cost.maximum_tool_calls:
        failures.append("tool_calls_exceeded")
    if packet.search_calls > cost.maximum_search_calls:
        failures.append("search_calls_exceeded")
    if packet.fetch_calls > cost.maximum_fetch_calls:
        failures.append("fetch_calls_exceeded")
    if len(packet.documents) > cost.maximum_sources:
        failures.append("sources_exceeded")
    if total_chars > cost.maximum_evidence_characters:
        failures.append("evidence_characters_exceeded")
    if packet.latency_ms > cost.maximum_latency_ms:
        failures.append("latency_exceeded")
    if packet.monetary_microunits > cost.maximum_monetary_microunits:
        failures.append("monetary_cost_exceeded")
    if failures:
        raise ValueError("evidence packet exceeds plan: " + ",".join(failures))


def _validate_total_use(
    plan: ToolPlanContractV2,
    packet: EvidencePacket,
    a0_assessment: AnswerAssessment,
    constructor: ConstructorReceipt,
    b_assessment: AnswerAssessment | None,
) -> tuple[int, int, int, int, int, int]:
    verdicts = a0_assessment.verdicts + (() if b_assessment is None else b_assessment.verdicts)
    input_tokens = packet.input_tokens + constructor.input_tokens + sum(item.input_tokens for item in verdicts)
    cached_tokens = packet.cached_input_tokens + constructor.cached_input_tokens + sum(item.cached_input_tokens for item in verdicts)
    output_tokens = packet.output_tokens + constructor.output_tokens + sum(item.output_tokens for item in verdicts)
    model_passes = constructor.model_passes + a0_assessment.model_passes + (0 if b_assessment is None else b_assessment.model_passes)
    latency_ms = (
        packet.latency_ms + constructor.latency_ms
        + a0_assessment.latency_ms
        + (0 if b_assessment is None else b_assessment.latency_ms)
    )
    monetary_microunits = (
        packet.monetary_microunits + constructor.monetary_microunits
        + a0_assessment.monetary_microunits
        + (0 if b_assessment is None else b_assessment.monetary_microunits)
    )
    cost = plan.cost
    if input_tokens > cost.maximum_input_tokens:
        raise ValueError("plan input-token envelope exceeded")
    if cached_tokens > cost.maximum_cached_input_tokens:
        raise ValueError("plan cached-input envelope exceeded")
    if output_tokens > cost.maximum_output_tokens:
        raise ValueError("plan output-token envelope exceeded")
    if model_passes > cost.maximum_model_passes:
        raise ValueError("plan model-pass envelope exceeded")
    if latency_ms > cost.maximum_latency_ms:
        raise ValueError("plan end-to-end latency envelope exceeded")
    if monetary_microunits > cost.maximum_monetary_microunits:
        raise ValueError("plan monetary envelope exceeded")
    return (
        input_tokens, cached_tokens, output_tokens, model_passes,
        latency_ms, monetary_microunits,
    )


def run_evidence_closed_benchmark(
    raw_task: Mapping[str, object],
    a0: str,
    obligation: QuestionObligation,
    *,
    plans: Sequence[ToolPlanContractV2],
    plan_evidence: Mapping[tuple[str, str], PlanEvidence],
    ledger: BenchmarkTokenLedger,
    policy: EvidenceClosedRuntimePolicy,
    plan_runner: EvidencePlanRunner | None,
    constructor_runner: ConstructorRunner | None,
    semantic_comparator: SemanticComparator | None,
) -> tuple[str, EvidenceClosedRunReceipt]:
    """Execute at most one evidence-closed plan; preserve A0 on every failure."""

    task = QuestionOnlyTask.from_mapping(raw_task)
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(obligation, QuestionObligation):
        raise TypeError("obligation must be QuestionObligation")
    if obligation.task_id != task.task_id or obligation.question_digest != task.question_digest:
        raise ValueError("obligation does not bind task")
    if not isinstance(ledger, BenchmarkTokenLedger):
        raise TypeError("ledger must be BenchmarkTokenLedger")
    if not isinstance(policy, EvidenceClosedRuntimePolicy):
        raise TypeError("policy must be EvidenceClosedRuntimePolicy")
    before = ledger.trace()
    opportunity = discover_route_opportunity(raw_task)
    if not policy.enabled:
        if any(item is not None for item in (plan_runner, constructor_runner, semantic_comparator)):
            raise ValueError("disabled runtime must not receive executable callbacks")
        receipt = _receipt(
            task, a0, opportunity_status=opportunity.status.value,
            reason="evidence_closed_runtime_disabled", plan_decisions=(),
            selected_plan=None, packet=None, a0_assessment=None, constructor=None,
            b_assessment=None, selection=None, active_route=None,
            ledger_before=before, ledger=ledger, cost_accounting_complete=True,
        )
        return a0, receipt
    if plan_runner is None:
        raise ValueError("enabled runtime requires plan runner")
    if opportunity.status is OpportunityStatus.UNSUPPORTED:
        receipt = _receipt(
            task, a0, opportunity_status=opportunity.status.value,
            reason="no_question_only_tool_opportunity", plan_decisions=(),
            selected_plan=None, packet=None, a0_assessment=None, constructor=None,
            b_assessment=None, selection=None, active_route=None,
            ledger_before=before, ledger=ledger, cost_accounting_complete=True,
        )
        return a0, receipt

    allowed = {item.capability for item in opportunity.candidates}
    decisions: list[tuple[ToolPlanContractV2, PlanDecision]] = []
    traces: list[dict[str, object]] = []
    seen_plan_ids: set[str] = set()
    for plan in plans:
        if not isinstance(plan, ToolPlanContractV2):
            raise TypeError("plans must contain ToolPlanContractV2")
        if plan.plan_id in seen_plan_ids:
            raise ValueError("plan ids must be unique")
        seen_plan_ids.add(plan.plan_id)
        if plan.task_id != task.task_id or plan.question_digest != task.question_digest or plan.a0_digest != digest(a0):
            raise ValueError("plan does not bind task and A0")
        required = {_OPERATION_CAPABILITY[step.operation] for step in plan.steps}
        if not required.issubset(allowed):
            continue
        route_evidence = plan_evidence.get((plan.route_key, plan.plan_version))
        decision = decide_plan_prelaunch(
            plan,
            remaining_unreserved_tokens=ledger.remaining_unreserved_tokens,
            weights=policy.weights,
            policy=policy.plan_value,
            evidence=route_evidence,
        )
        decisions.append((plan, decision))
        traces.append(decision.trace() | {"plan_id": plan.plan_id})
    selected = choose_plan(decisions)
    if selected is None:
        receipt = _receipt(
            task, a0, opportunity_status=opportunity.status.value,
            reason="no_applicable_positive_or_exploration_plan",
            plan_decisions=tuple(traces), selected_plan=None, packet=None,
            a0_assessment=None, constructor=None, b_assessment=None,
            selection=None, active_route=None, ledger_before=before,
            ledger=ledger, cost_accounting_complete=True,
        )
        return a0, receipt

    plan, _ = selected
    call_id = f"plan-{plan.contract_digest[:16]}"
    ledger.reserve(call_id, plan.cost.maximum_total_tokens, provider_cap_enforced=plan.provider_cap_enforced)
    packet: EvidencePacket | None = None
    a0_assessment: AnswerAssessment | None = None
    constructor: ConstructorReceipt | None = None
    b_assessment: AnswerAssessment | None = None
    selection: SelectionReceipt | None = None
    try:
        packet = plan_runner(plan, task)
        if not isinstance(packet, EvidencePacket):
            raise TypeError("plan runner must return EvidencePacket")
        if packet.question_digest != task.question_digest:
            raise ValueError("evidence packet does not bind question")
        _validate_packet(packet, plan)
        a0_candidate = single_answer_candidate(
            a0,
            answer_kind=obligation.answer_kind,
            origin=CandidateOrigin.BASE,
            unit=obligation.requested_unit,
            temporal_scope=obligation.temporal_scope,
            jurisdiction=obligation.jurisdiction,
        )
        a0_assessment = compare_candidate(
            a0_candidate,
            packet,
            obligation=obligation,
            policy=policy.comparator,
            semantic_comparator=semantic_comparator,
        )
        if a0_assessment.fully_supported and a0_assessment.selection_eligible:
            constructor = ConstructorReceipt(
                ConstructorOutcome.NO_CANDIDATE, None, "a0_supported_skip_constructor",
                0, 0, 0, task.question_digest, packet.packet_digest,
            )
        else:
            constructor = run_bounded_constructor(
                task.question,
                obligation,
                packet,
                policy=policy.constructor,
                runner=constructor_runner,
            )
        if constructor.outcome is ConstructorOutcome.ERROR:
            raise RuntimeError("constructor provider failure has incomplete cost accounting")
        if constructor.candidate is not None:
            b_assessment = compare_candidate(
                constructor.candidate,
                packet,
                obligation=obligation,
                policy=policy.comparator,
                semantic_comparator=semantic_comparator,
            )
        selected_answer, selection = select_answer(
            a0,
            a0_assessment,
            b_assessment,
            policy=policy.selector,
        )
        input_tokens, cached_tokens, output_tokens, _, _, _ = _validate_total_use(
            plan, packet, a0_assessment, constructor, b_assessment
        )
        ledger.settle(call_id, input_tokens + cached_tokens + output_tokens)
        tool_events = (
            ("search",) * packet.search_calls
            + ("fetch",) * packet.fetch_calls
            + ("tool",) * (packet.tool_calls - packet.search_calls - packet.fetch_calls)
        )
        work = RouteWorkResult(
            answer=selected_answer,
            verified=selection.outcome is SelectionOutcome.SELECT_B_BENCHMARK_UNADMITTED,
            contract_valid=True,
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            output_tokens=output_tokens,
            tool_event_types=tool_events,
        )
        final, active = finalize_benchmark_work(
            Route.VERIFY,
            a0,
            work,
            policy=BenchmarkExecutionPolicy(
                enabled=True,
                max_route_total_tokens=plan.cost.maximum_total_tokens,
                max_cached_input_tokens=plan.cost.maximum_cached_input_tokens,
                max_tool_events=plan.cost.maximum_tool_calls,
            ),
        )
        receipt = _receipt(
            task, a0, final=final, opportunity_status=opportunity.status.value,
            reason=selection.reason, plan_decisions=tuple(traces),
            selected_plan=plan.trace(), packet=packet,
            a0_assessment=a0_assessment, constructor=constructor,
            b_assessment=b_assessment, selection=selection,
            active_route=active.trace(), ledger_before=before, ledger=ledger,
            cost_accounting_complete=True,
        )
        return final, receipt
    except Exception:
        if call_id in ledger.trace()["active_call_ids"]:
            ledger.cancel(call_id)
        receipt = _receipt(
            task, a0, opportunity_status=opportunity.status.value,
            reason="evidence_closed_contract_or_accounting_exception_preserve_a0",
            plan_decisions=tuple(traces), selected_plan=plan.trace(), packet=packet,
            a0_assessment=a0_assessment, constructor=constructor,
            b_assessment=b_assessment, selection=selection, active_route=None,
            ledger_before=before, ledger=ledger, cost_accounting_complete=False,
        )
        return a0, receipt
