"""Active, single-tool VERIFY runtime for FOIL benchmarks.

The route is active when explicitly enabled: it probes question-only adapters,
prices each applicable call before launch, reserves the caller's token ledger,
executes exactly one read-only tool, validates its evidence, and passes the
candidate through FOIL's existing benchmark admission finalizer.  It is not a
shadow recommendation and it has no production or promotion authority.
"""

from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Callable, Mapping, Protocol

from egrt_types import digest
from foil_adaptive_executor import (
    ActiveRouteReceipt,
    BenchmarkExecutionPolicy,
    RouteWorkResult,
    finalize_benchmark_work,
)
from foil_adaptive_route import Route
from foil_benchmark_budget import BenchmarkTokenLedger
from foil_certified_arithmetic import (
    UnsupportedExpression,
    evaluate_exact,
    normalize_expression,
)
from foil_route_opportunity import (
    OpportunityStatus,
    QuestionOnlyTask,
    discover_route_opportunity,
)
from foil_smart_tool_value import (
    DifficultyBand,
    PrelaunchDecision,
    PrelaunchStatus,
    RouteEvidence,
    UtilityWeights,
    ValueGatePolicy,
    decide_prelaunch,
)
from foil_tool_contract import (
    EvidenceAdmission,
    EvidenceEnvelope,
    ToolContract,
    ToolCost,
    ToolFamily,
    ToolOperation,
    ToolOutcome,
    ToolReceipt,
)


RUN_SCHEMA = "foil.smart-tool-active-verify-run.v1"


class ProbeStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    DECLINE = "DECLINE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ToolProbe:
    capability: str
    status: ProbeStatus
    reason: str
    family: ToolFamily
    operation: ToolOperation
    operation_input_digest: str
    difficulty: DifficultyBand
    cost: ToolCost
    timeout_ms: int
    provider_cap_enforced: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ProbeStatus(self.status))
        object.__setattr__(self, "family", ToolFamily(self.family))
        object.__setattr__(self, "operation", ToolOperation(self.operation))
        object.__setattr__(self, "difficulty", DifficultyBand(self.difficulty))
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("probe reason must be non-empty")
        if not isinstance(self.cost, ToolCost):
            raise TypeError("probe cost must be ToolCost")
        if isinstance(self.timeout_ms, bool) or not isinstance(self.timeout_ms, int) or self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")

    def trace(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "status": self.status.value,
            "reason": self.reason,
            "family": self.family.value,
            "operation": self.operation.value,
            "operation_input_digest": self.operation_input_digest,
            "difficulty": self.difficulty.value,
            "cost": self.cost.trace(),
            "timeout_ms": self.timeout_ms,
            "provider_cap_enforced": self.provider_cap_enforced,
            "question_only": True,
        }


class ToolAdapter(Protocol):
    capability: str
    tool_id: str
    tool_version: str

    def probe(self, task: QuestionOnlyTask) -> ToolProbe: ...

    def execute(self, contract: ToolContract, task: QuestionOnlyTask) -> ToolReceipt: ...


@dataclass(frozen=True)
class SmartToolRuntimePolicy:
    enabled: bool
    value_gate: ValueGatePolicy
    weights: UtilityWeights
    allow_unadmitted_benchmark_selection: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.allow_unadmitted_benchmark_selection, bool):
            raise TypeError("enabled and allow_unadmitted_benchmark_selection must be bool")
        if not isinstance(self.value_gate, ValueGatePolicy):
            raise TypeError("value_gate must be ValueGatePolicy")
        if not isinstance(self.weights, UtilityWeights):
            raise TypeError("weights must be UtilityWeights")
        if self.enabled != self.value_gate.enabled:
            raise ValueError("runtime and value gate must be enabled together")


@dataclass(frozen=True)
class SmartToolRunReceipt:
    task_id: str
    question_digest: str
    a0_digest: str
    final_digest: str
    opportunity_status: str
    selected_capability: str | None
    active_verify_executed: bool
    reason: str
    probes: tuple[dict[str, object], ...]
    prelaunch_decisions: tuple[dict[str, object], ...]
    contract_trace: dict[str, object] | None
    tool_receipt_trace: dict[str, object] | None
    evidence_trace: dict[str, object] | None
    active_route_trace: dict[str, object] | None
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
            "selected_capability": self.selected_capability,
            "active_verify_executed": self.active_verify_executed,
            "shadow_only": False,
            "reason": self.reason,
            "probes": list(self.probes),
            "prelaunch_decisions": list(self.prelaunch_decisions),
            "contract": self.contract_trace,
            "tool_receipt": self.tool_receipt_trace,
            "evidence": self.evidence_trace,
            "active_route_receipt": self.active_route_trace,
            "ledger_before": self.ledger_before,
            "ledger_after": self.ledger_after,
            "answer_changed": self.answer_changed,
            "cost_accounting_complete": self.cost_accounting_complete,
            "single_tool_only": True,
            "generated_contract_origin": "GENERATED_UNADMITTED",
            "generated_contract_admitted": False,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "raw_question_stored": False,
            "raw_a0_stored": False,
            "raw_candidate_stored": False,
        }
        body["run_sha256"] = digest(body)
        return body


_MATH_SPAN = re.compile(r"\\\((.*?)\\\)|\$(.*?)\$", re.DOTALL)
_PLAIN_COMPUTE = re.compile(
    r"\b(?:compute|calculate|evaluate)\s+(?:the\s+value\s+of\s+)?(.+?)(?:\?|\.$|$)",
    re.IGNORECASE | re.DOTALL,
)
_PYTHON_BLOCK = re.compile(r"```python\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _difficulty(size: int) -> DifficultyBand:
    if size <= 24:
        return DifficultyBand.EASY
    if size <= 96:
        return DifficultyBand.MEDIUM
    if size <= 384:
        return DifficultyBand.HARD
    return DifficultyBand.EXPERT


def _exact_expression(question: str) -> str | None:
    candidates: list[str] = []
    for match in _MATH_SPAN.finditer(question):
        source = next(group for group in match.groups() if group is not None)
        try:
            evaluate_exact(source)
        except UnsupportedExpression:
            continue
        candidates.append(source)
    plain = _PLAIN_COMPUTE.search(question)
    if plain is not None:
        source = plain.group(1).strip()
        try:
            evaluate_exact(source)
        except UnsupportedExpression:
            pass
        else:
            candidates.append(source)
    normalized = {normalize_expression(source) for source in candidates}
    return next(iter(normalized)) if len(normalized) == 1 else None


def _restricted_python_expression(question: str) -> tuple[str, str] | None:
    blocks = _PYTHON_BLOCK.findall(question)
    if len(blocks) != 1:
        return None
    source = blocks[0].strip()
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return None
    call = tree.body[0].value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "print"
        and len(call.args) == 1
        and not call.keywords
    ):
        return None
    expression = ast.unparse(call.args[0])
    try:
        normalized = normalize_expression(expression)
        evaluate_exact(normalized)
    except UnsupportedExpression:
        return None
    return source, normalized


class ExactArithmeticAdapter:
    capability = "SYMBOLIC_COMPUTATION"
    tool_id = "foil.exact-arithmetic"
    tool_version = "1"

    def probe(self, task: QuestionOnlyTask) -> ToolProbe:
        expression = _exact_expression(task.question)
        applicable = expression is not None
        material = expression if expression is not None else task.question_digest
        return ToolProbe(
            self.capability,
            ProbeStatus.APPLICABLE if applicable else ProbeStatus.DECLINE,
            "single_closed_expression" if applicable else "no_unique_closed_expression",
            ToolFamily.COMPUTATION,
            ToolOperation.EXACT_ARITHMETIC,
            digest(material),
            _difficulty(len(expression or task.question)),
            ToolCost(maximum_tool_calls=1, maximum_latency_ms=500),
            500,
            True,
        )

    def execute(self, contract: ToolContract, task: QuestionOnlyTask) -> ToolReceipt:
        started = time.perf_counter()
        expression = _exact_expression(task.question)
        if expression is None or digest(expression) != contract.operation_input_digest:
            return ToolReceipt(
                call_id=f"call-{contract.contract_digest[:16]}",
                contract_digest=contract.contract_digest,
                outcome=ToolOutcome.NOT_APPLICABLE,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        value = _fraction_text(evaluate_exact(expression))
        return ToolReceipt(
            call_id=f"call-{contract.contract_digest[:16]}",
            contract_digest=contract.contract_digest,
            outcome=ToolOutcome.VERIFIED,
            candidate_answer=value,
            evidence_digest=digest({"expression": expression, "value": value}),
            mechanically_verified=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class RestrictedPythonOutputAdapter:
    capability = "CODE_EXECUTION"
    tool_id = "foil.restricted-python-output"
    tool_version = "1"

    def probe(self, task: QuestionOnlyTask) -> ToolProbe:
        extracted = _restricted_python_expression(task.question)
        applicable = extracted is not None
        material = extracted[0] if extracted is not None else task.question_digest
        return ToolProbe(
            self.capability,
            ProbeStatus.APPLICABLE if applicable else ProbeStatus.DECLINE,
            "single_numeric_print" if applicable else "outside_restricted_python_language",
            ToolFamily.EXECUTION,
            ToolOperation.RESTRICTED_PYTHON_OUTPUT,
            digest(material),
            _difficulty(len(material)),
            ToolCost(maximum_tool_calls=1, maximum_latency_ms=500),
            500,
            True,
        )

    def execute(self, contract: ToolContract, task: QuestionOnlyTask) -> ToolReceipt:
        started = time.perf_counter()
        extracted = _restricted_python_expression(task.question)
        if extracted is None or digest(extracted[0]) != contract.operation_input_digest:
            return ToolReceipt(
                call_id=f"call-{contract.contract_digest[:16]}",
                contract_digest=contract.contract_digest,
                outcome=ToolOutcome.NOT_APPLICABLE,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        source, expression = extracted
        value = _fraction_text(evaluate_exact(expression))
        return ToolReceipt(
            call_id=f"call-{contract.contract_digest[:16]}",
            contract_digest=contract.contract_digest,
            outcome=ToolOutcome.VERIFIED,
            candidate_answer=value,
            evidence_digest=digest({"source": source, "value": value}),
            mechanically_verified=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


@dataclass(frozen=True)
class RetrievalResult:
    candidate_answer: str | None
    evidence_text: str
    source_urls: tuple[str, ...]
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: int
    monetary_microunits: int = 0


RetrievalRunner = Callable[[str, int], RetrievalResult]


class CallbackRetrievalAdapter:
    """Bound a host retrieval implementation to FOIL's supporting-only contract."""

    def __init__(
        self,
        *,
        capability: str,
        runner: RetrievalRunner,
        maximum_cost: ToolCost,
        difficulty: DifficultyBand,
        provider_cap_enforced: bool,
        tool_id: str,
        tool_version: str,
    ) -> None:
        if capability not in {"WEB_SEARCH", "SCHOLARLY_SEARCH"}:
            raise ValueError("retrieval capability must be WEB_SEARCH or SCHOLARLY_SEARCH")
        self.capability = capability
        self.runner = runner
        self.maximum_cost = maximum_cost
        self.difficulty = DifficultyBand(difficulty)
        self.provider_cap_enforced = provider_cap_enforced
        self.tool_id = tool_id
        self.tool_version = tool_version

    @property
    def operation(self) -> ToolOperation:
        return (
            ToolOperation.WEB_RETRIEVAL
            if self.capability == "WEB_SEARCH"
            else ToolOperation.SCHOLARLY_RETRIEVAL
        )

    def probe(self, task: QuestionOnlyTask) -> ToolProbe:
        return ToolProbe(
            self.capability,
            ProbeStatus.APPLICABLE,
            "bounded_retrieval_provider_available",
            ToolFamily.RETRIEVAL,
            self.operation,
            task.question_digest,
            self.difficulty,
            self.maximum_cost,
            self.maximum_cost.maximum_latency_ms,
            self.provider_cap_enforced,
        )

    def execute(self, contract: ToolContract, task: QuestionOnlyTask) -> ToolReceipt:
        result = self.runner(task.question, contract.cost.maximum_total_tokens)
        if not isinstance(result, RetrievalResult):
            raise TypeError("retrieval runner must return RetrievalResult")
        return ToolReceipt(
            call_id=f"call-{contract.contract_digest[:16]}",
            contract_digest=contract.contract_digest,
            outcome=ToolOutcome.SUPPORTING,
            candidate_answer=result.candidate_answer,
            evidence_digest=digest(result.evidence_text),
            source_urls=result.source_urls,
            input_tokens=result.input_tokens,
            cached_input_tokens=result.cached_input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            monetary_microunits=result.monetary_microunits,
        )


def _stand_down_receipt(
    *,
    task: QuestionOnlyTask,
    a0: str,
    opportunity_status: str,
    reason: str,
    probes: tuple[dict[str, object], ...],
    prelaunch: tuple[dict[str, object], ...],
    ledger_before: dict[str, object],
    ledger_after: dict[str, object],
) -> SmartToolRunReceipt:
    return SmartToolRunReceipt(
        task.task_id,
        task.question_digest,
        digest(a0),
        digest(a0),
        opportunity_status,
        None,
        False,
        reason,
        probes,
        prelaunch,
        None,
        None,
        None,
        None,
        ledger_before,
        ledger_after,
        False,
        True,
    )


def run_smart_verify(
    raw_task: Mapping[str, object],
    a0: str,
    *,
    adapters: Mapping[str, ToolAdapter],
    evidence: Mapping[tuple[ToolFamily, DifficultyBand], RouteEvidence],
    ledger: BenchmarkTokenLedger,
    policy: SmartToolRuntimePolicy,
) -> tuple[str, SmartToolRunReceipt]:
    """Actively execute at most one pre-priced tool and preserve A0 on failure."""

    task = QuestionOnlyTask.from_mapping(raw_task)
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(ledger, BenchmarkTokenLedger):
        raise TypeError("ledger must be BenchmarkTokenLedger")
    if not isinstance(policy, SmartToolRuntimePolicy):
        raise TypeError("policy must be SmartToolRuntimePolicy")
    for capability, adapter in adapters.items():
        if capability != adapter.capability:
            raise ValueError("adapter registry key must match adapter capability")
    before = ledger.trace()
    opportunity = discover_route_opportunity(raw_task)
    if not policy.enabled:
        receipt = _stand_down_receipt(
            task=task,
            a0=a0,
            opportunity_status=opportunity.status.value,
            reason="smart_tool_runtime_disabled",
            probes=(),
            prelaunch=(),
            ledger_before=before,
            ledger_after=ledger.trace(),
        )
        return a0, receipt
    if opportunity.status is OpportunityStatus.UNSUPPORTED:
        receipt = _stand_down_receipt(
            task=task,
            a0=a0,
            opportunity_status=opportunity.status.value,
            reason="no_question_only_tool_opportunity",
            probes=(),
            prelaunch=(),
            ledger_before=before,
            ledger_after=ledger.trace(),
        )
        return a0, receipt

    considered: list[tuple[int, ToolAdapter, ToolProbe, PrelaunchDecision]] = []
    probe_traces: list[dict[str, object]] = []
    decision_traces: list[dict[str, object]] = []
    for index, candidate in enumerate(opportunity.candidates):
        adapter = adapters.get(candidate.capability)
        if adapter is None:
            continue
        probe = adapter.probe(task)
        if probe.capability != candidate.capability:
            raise ValueError("adapter probe capability drift")
        probe_traces.append(probe.trace())
        if probe.status is not ProbeStatus.APPLICABLE:
            continue
        route_evidence = evidence.get((probe.family, probe.difficulty))
        prelaunch = decide_prelaunch(
            family=probe.family,
            difficulty=probe.difficulty,
            cost=probe.cost,
            remaining_unreserved_tokens=ledger.remaining_unreserved_tokens,
            weights=policy.weights,
            policy=policy.value_gate,
            evidence=route_evidence,
        )
        decision_traces.append(prelaunch.trace() | {"capability": probe.capability})
        if prelaunch.executes:
            considered.append((index, adapter, probe, prelaunch))
    if not considered:
        receipt = _stand_down_receipt(
            task=task,
            a0=a0,
            opportunity_status=opportunity.status.value,
            reason="no_applicable_positive_or_exploration_route",
            probes=tuple(probe_traces),
            prelaunch=tuple(decision_traces),
            ledger_before=before,
            ledger_after=ledger.trace(),
        )
        return a0, receipt

    def rank(row: tuple[int, ToolAdapter, ToolProbe, PrelaunchDecision]) -> tuple[int, int, int]:
        index, _, probe, decision = row
        calibrated = int(decision.status is PrelaunchStatus.EXECUTE)
        utility = decision.utility_lower_bound_microunits or 0
        return (-calibrated, -utility, probe.cost.maximum_total_tokens * 1_000 + index)

    _, adapter, probe, prelaunch = min(considered, key=rank)
    contract = ToolContract(
        task_id=task.task_id,
        question_digest=task.question_digest,
        a0_digest=digest(a0),
        tool_id=adapter.tool_id,
        tool_version=adapter.tool_version,
        capability=probe.capability,
        family=probe.family,
        operation=probe.operation,
        operation_input_digest=probe.operation_input_digest,
        cost=probe.cost,
        timeout_ms=probe.timeout_ms,
        provider_cap_enforced=probe.provider_cap_enforced,
    )
    call_id = f"call-{contract.contract_digest[:16]}"
    ledger.reserve(
        call_id,
        contract.cost.maximum_total_tokens,
        provider_cap_enforced=contract.provider_cap_enforced,
    )
    try:
        tool_receipt = adapter.execute(contract, task)
        tool_receipt.validate_against(contract)
        ledger.settle(call_id, tool_receipt.actual_total_tokens)
    except Exception:
        if call_id in ledger.trace()["active_call_ids"]:
            ledger.cancel(call_id)
        receipt = SmartToolRunReceipt(
            task.task_id,
            task.question_digest,
            digest(a0),
            digest(a0),
            opportunity.status.value,
            probe.capability,
            True,
            "tool_contract_or_accounting_exception_preserve_a0",
            tuple(probe_traces),
            tuple(decision_traces),
            contract.trace(),
            None,
            None,
            None,
            before,
            ledger.trace(),
            False,
            False,
        )
        return a0, receipt

    envelope = EvidenceEnvelope.from_receipt(contract, tool_receipt)
    candidate = tool_receipt.candidate_answer or a0
    invalid = tool_receipt.outcome in {
        ToolOutcome.INVALID,
        ToolOutcome.ERROR,
        ToolOutcome.TIMEOUT,
    }
    work = RouteWorkResult(
        answer=candidate,
        verified=(
            envelope.admission is EvidenceAdmission.BENCHMARK_CORRECTIVE_UNADMITTED
            and policy.allow_unadmitted_benchmark_selection
        ),
        contract_valid=not invalid,
        failure_reasons=(tool_receipt.error_code,) if invalid and tool_receipt.error_code else (),
        input_tokens=tool_receipt.input_tokens,
        cached_input_tokens=tool_receipt.cached_input_tokens,
        output_tokens=tool_receipt.output_tokens,
        tool_event_types=(probe.capability.lower(),),
    )
    executor_policy = BenchmarkExecutionPolicy(
        enabled=True,
        max_route_total_tokens=contract.cost.maximum_total_tokens,
        max_tool_events=1,
    )
    final, active_receipt = finalize_benchmark_work(
        Route.VERIFY,
        a0,
        work,
        policy=executor_policy,
    )
    run_receipt = SmartToolRunReceipt(
        task.task_id,
        task.question_digest,
        digest(a0),
        digest(final),
        opportunity.status.value,
        probe.capability,
        True,
        active_receipt.reason,
        tuple(probe_traces),
        tuple(decision_traces),
        contract.trace(),
        tool_receipt.trace(),
        envelope.trace(),
        active_receipt.trace(),
        before,
        ledger.trace(),
        final != a0,
        True,
    )
    return final, run_receipt
