"""Reusable, active DIRECT/VERIFY/FULL orchestration for FOIL v2.

The runtime is provider-neutral and profile-blind.  It freezes the task-only
frontier before A0 is used, executes one cheapest positive-value route, archives
raw boundary evidence before reporting success, compares A0 and B symmetrically,
and preserves A0 on every unresolved or typed external-boundary failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from egrt_types import digest
from foil_answer_selector_v2 import (
    SelectionReceiptV2,
    SelectorPolicyV2,
    select_answer_v2,
)
from foil_bounded_answer_constructor_v2 import (
    ConstructorOutcomeV2,
    ConstructorPolicyV2,
    ConstructorReceiptV2,
    ConstructorRequestV2,
    ConstructorRunnerV2,
    run_bounded_constructor_v2,
)
from foil_evidence_archive import EvidenceArchiveReceipt, RawEvidenceArchive
from foil_evidence_contract import (
    AnswerKind,
    CandidateAnswer,
    CandidateOrigin,
    ComputationReceipt,
    ContentSafety,
    EvidenceDocument,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
    single_answer_candidate,
)
from foil_retrieval_claim_comparator import (
    AnswerAssessment,
    ComparatorPolicy,
    SemanticComparator,
)
from foil_retrieval_claim_comparator_v2 import compare_candidate_v2
from foil_route_opportunity_v2 import (
    OpportunityStatusV2,
    QuestionOnlyTaskV2,
    RouteOpportunityV2,
    RuntimeToolFamily,
    discover_route_opportunity_v2,
)
from foil_runtime_token_ledger import RuntimeLedgerError, RuntimeTokenLedger
from foil_runtime_tools_v2 import (
    ProbeStatusV2,
    RuntimeToolAdapterV2,
    ToolBoundaryFailure,
    ToolProbeV2,
)
from foil_tool_contract_v2 import (
    BoundaryFailureCode,
    OperationSpecOrigin,
    ToolContractV2,
    ToolOutcomeV2,
    ToolReceiptV2,
    TokenUsageV2,
)


class RuntimeOutcomeV2(str, Enum):
    DIRECT = "DIRECT"
    COVERAGE_GAP = "COVERAGE_GAP"
    VERIFY_RESOLVED = "VERIFY_RESOLVED"
    FULL_RESOLVED = "FULL_RESOLVED"
    PRESERVED_A0 = "PRESERVED_A0"
    TOOL_ERROR = "TOOL_ERROR"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    CONSTRUCTOR_ERROR = "CONSTRUCTOR_ERROR"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"


_NUMERIC_RESULT_FAMILIES = frozenset(
    {
        RuntimeToolFamily.EXACT_ARITHMETIC,
        RuntimeToolFamily.RESTRICTED_PYTHON,
        RuntimeToolFamily.SYMBOLIC_COMPUTATION,
    }
)


@dataclass(frozen=True)
class FoilRuntimePolicyV2:
    enabled: bool
    answer_change_enabled: bool
    comparator: ComparatorPolicy
    constructor: ConstructorPolicyV2
    require_raw_archive: bool = True
    production_authorized: bool = False

    def __post_init__(self) -> None:
        for name in (
            "enabled", "answer_change_enabled", "require_raw_archive",
            "production_authorized",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.comparator, ComparatorPolicy):
            raise TypeError("comparator must be ComparatorPolicy")
        if not isinstance(self.constructor, ConstructorPolicyV2):
            raise TypeError("constructor must be ConstructorPolicyV2")
        if self.production_authorized:
            raise ValueError("FOIL v2 runtime is unadmitted and cannot claim production authority")


@dataclass(frozen=True)
class FoilRuntimeReceiptV2:
    task_id: str
    question_digest: str
    a0_digest: str
    final_digest: str
    outcome: RuntimeOutcomeV2
    reason: str
    opportunity: dict[str, object]
    probes: tuple[dict[str, object], ...]
    selected_family: RuntimeToolFamily | None
    contract: dict[str, object] | None
    tool_receipt: dict[str, object] | None
    archive_receipt: dict[str, object] | None
    evidence_packet: dict[str, object] | None
    a0_assessment: dict[str, object] | None
    constructor: dict[str, object] | None
    b_assessment: dict[str, object] | None
    selection: dict[str, object] | None
    ledger_before: dict[str, object]
    ledger_after: dict[str, object]
    answer_changed: bool
    cost_accounting_complete: bool

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "foil.active-runtime.v2",
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "a0_sha256": self.a0_digest,
            "final_sha256": self.final_digest,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "opportunity": self.opportunity,
            "probes": list(self.probes),
            "selected_family": None if self.selected_family is None else self.selected_family.value,
            "contract": self.contract,
            "tool_receipt": self.tool_receipt,
            "archive_receipt": self.archive_receipt,
            "evidence_packet": self.evidence_packet,
            "a0_assessment": self.a0_assessment,
            "constructor": self.constructor,
            "b_assessment": self.b_assessment,
            "selection": self.selection,
            "ledger_before": self.ledger_before,
            "ledger_after": self.ledger_after,
            "answer_changed": self.answer_changed,
            "cost_accounting_complete": self.cost_accounting_complete,
            "shadow_only": False,
            "question_only_frontier": True,
            "profile_read": False,
            "profile_written": False,
            "raw_question_stored": False,
            "raw_a0_stored": False,
            "raw_candidate_stored": False,
            "production_authorized": False,
            "promotion_authorized": False,
        }
        body["run_sha256"] = digest(body)
        return body


def _receipt(
    task: QuestionOnlyTaskV2,
    a0: str,
    opportunity: RouteOpportunityV2,
    ledger_before: dict[str, object],
    ledger: RuntimeTokenLedger,
    *,
    outcome: RuntimeOutcomeV2,
    reason: str,
    final: str | None = None,
    probes: tuple[dict[str, object], ...] = (),
    family: RuntimeToolFamily | None = None,
    contract: ToolContractV2 | None = None,
    tool_receipt: ToolReceiptV2 | None = None,
    archive_receipt: EvidenceArchiveReceipt | None = None,
    packet: EvidencePacket | None = None,
    a0_assessment: AnswerAssessment | None = None,
    constructor: ConstructorReceiptV2 | None = None,
    b_assessment: AnswerAssessment | None = None,
    selection: SelectionReceiptV2 | None = None,
    cost_accounting_complete: bool = True,
) -> FoilRuntimeReceiptV2:
    selected = a0 if final is None else final
    return FoilRuntimeReceiptV2(
        task.task_id,
        task.question_digest,
        digest(a0),
        digest(selected),
        outcome,
        reason,
        opportunity.trace(),
        probes,
        family,
        None if contract is None else contract.trace(),
        None if tool_receipt is None else tool_receipt.trace(),
        None if archive_receipt is None else archive_receipt.trace(),
        None if packet is None else packet.trace(),
        None if a0_assessment is None else a0_assessment.trace(),
        None if constructor is None else constructor.trace(),
        None if b_assessment is None else b_assessment.trace(),
        None if selection is None else selection.trace(),
        ledger_before,
        ledger.trace(),
        selected != a0,
        cost_accounting_complete,
    )


def _source_class(value: str) -> SourceClass:
    try:
        return SourceClass(value)
    except ValueError:
        return SourceClass.UNKNOWN


def _packet_from_receipt(
    task: QuestionOnlyTaskV2, receipt: ToolReceiptV2
) -> EvidencePacket:
    documents: list[EvidenceDocument] = []
    spans: list[EvidenceSpan] = []
    computations: list[ComputationReceipt] = []
    for index, passage in enumerate(receipt.passages):
        document_id = passage.document_id
        documents.append(
            EvidenceDocument(
                document_id,
                passage.source_url,
                passage.title,
                passage.content,
                passage.retrieved_at,
                _source_class(passage.source_class),
                passage.independent_group,
                ContentSafety.SANITIZED_DATA_ONLY,
            )
        )
        spans.append(
            EvidenceSpan(
                f"span-{index}-{passage.passage_digest[:12]}",
                document_id,
                passage.start_offset,
                passage.end_offset,
                passage.passage,
            )
        )
    if receipt.outcome is ToolOutcomeV2.RESOLVED:
        if receipt.verification_expression is None or receipt.candidate_answer is None:
            raise ValueError("resolved receipt lacks mechanical verification material")
        computations.append(
            ComputationReceipt(
                f"computation-{receipt.contract_digest[:16]}",
                receipt.verification_expression,
                (),
                receipt.candidate_answer,
            )
        )
    return EvidencePacket(
        task.question_digest,
        tuple(documents),
        tuple(spans),
        tuple(computations),
        receipt.usage.input_tokens,
        receipt.usage.cached_input_tokens,
        receipt.usage.output_tokens,
        receipt.tool_calls,
        int(receipt.family is RuntimeToolFamily.PASSAGE_RETRIEVAL),
        int(receipt.family is RuntimeToolFamily.PASSAGE_RETRIEVAL),
        receipt.latency_ms,
        receipt.monetary_microunits,
    )


def _total_usage(
    tool: ToolReceiptV2,
    constructor: ConstructorReceiptV2 | None,
    a0: AnswerAssessment | None,
    b: AnswerAssessment | None,
) -> TokenUsageV2:
    verdicts = () if a0 is None else a0.verdicts
    if b is not None:
        verdicts = verdicts + b.verdicts
    return TokenUsageV2(
        tool.usage.input_tokens
        + (0 if constructor is None else constructor.usage.input_tokens)
        + sum(item.input_tokens for item in verdicts),
        tool.usage.cached_input_tokens
        + (0 if constructor is None else constructor.usage.cached_input_tokens)
        + sum(item.cached_input_tokens for item in verdicts),
        tool.usage.output_tokens
        + (0 if constructor is None else constructor.usage.output_tokens)
        + sum(item.output_tokens for item in verdicts),
    )


def run_foil_v2(
    raw_task: Mapping[str, object],
    a0: str,
    obligation: QuestionObligation,
    *,
    adapters: Mapping[RuntimeToolFamily, RuntimeToolAdapterV2],
    ledger: RuntimeTokenLedger,
    policy: FoilRuntimePolicyV2,
    archive: RawEvidenceArchive | None,
    constructor_runner: ConstructorRunnerV2 | None = None,
    semantic_comparator: SemanticComparator | None = None,
) -> tuple[str, FoilRuntimeReceiptV2]:
    """Execute one active v2 route and return A0 or an admitted candidate."""

    task = QuestionOnlyTaskV2.from_mapping(raw_task)
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(obligation, QuestionObligation):
        raise TypeError("obligation must be QuestionObligation")
    if obligation.task_id != task.task_id or obligation.question_digest != task.question_digest:
        raise ValueError("obligation does not bind task")
    if not isinstance(ledger, RuntimeTokenLedger):
        raise TypeError("ledger must be RuntimeTokenLedger")
    if not isinstance(policy, FoilRuntimePolicyV2):
        raise TypeError("policy must be FoilRuntimePolicyV2")
    for family, adapter in adapters.items():
        if RuntimeToolFamily(family) is not adapter.family:
            raise ValueError("adapter registry key does not match adapter family")
    if policy.require_raw_archive and policy.enabled and archive is None:
        raise ValueError("enabled runtime requires raw evidence archive")
    if not policy.comparator.semantic_enabled and semantic_comparator is not None:
        raise ValueError("semantic callback supplied while comparator is disabled")
    if policy.comparator.semantic_enabled and semantic_comparator is None:
        raise ValueError("semantic comparator enabled without callback")
    opportunity = discover_route_opportunity_v2(raw_task)
    before = ledger.trace()
    if not policy.enabled:
        if constructor_runner is not None or semantic_comparator is not None:
            raise ValueError("disabled runtime must not receive model callbacks")
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=RuntimeOutcomeV2.DIRECT, reason="runtime_disabled_direct",
        )
    if opportunity.status is OpportunityStatusV2.COVERAGE_GAP:
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=RuntimeOutcomeV2.COVERAGE_GAP,
            reason="no_implemented_question_only_capability",
        )

    considered: list[tuple[int, RuntimeToolAdapterV2, ToolProbeV2]] = []
    probe_traces: list[dict[str, object]] = []
    incompatible_families: list[str] = []
    for candidate in opportunity.candidates:
        if (
            candidate.family in _NUMERIC_RESULT_FAMILIES
            and obligation.answer_kind is not AnswerKind.NUMBER
        ):
            incompatible_families.append(candidate.family.value)
            continue
        adapter = adapters.get(candidate.family)
        if adapter is None:
            continue
        probe = adapter.probe(task)
        if probe.family is not candidate.family:
            raise ValueError("adapter probe family drift")
        probe_traces.append(probe.trace())
        if probe.status == ProbeStatusV2.APPLICABLE and probe.value.executes:
            considered.append((candidate.cost_rank, adapter, probe))
    if not considered:
        reason = "no_applicable_positive_value_route"
        if incompatible_families:
            reason += ":answer_kind_mismatch=" + ",".join(incompatible_families)
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=RuntimeOutcomeV2.PRESERVED_A0,
            reason=reason,
            probes=tuple(probe_traces),
        )
    _, adapter, probe = min(
        considered,
        key=lambda item: (item[0], -item[2].value.expected_gain_microunits),
    )
    contract = ToolContractV2(
        task.task_id,
        task.question_digest,
        digest(a0),
        probe.family,
        adapter.tool_id,
        adapter.tool_version,
        probe.operation_input_digest,
        probe.spec_origin,
        probe.envelope,
        probe.value,
        probe.timeout_ms,
        probe.formalization_admission_digest,
    )
    call_id = f"call-{contract.contract_digest[:16]}"
    try:
        ledger.reserve(
            call_id=call_id,
            contract_digest=contract.contract_digest,
            envelope=contract.envelope,
            value=contract.value,
            provider_cap_enforced=probe.provider_cap_enforced,
        )
    except RuntimeLedgerError as exc:
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=RuntimeOutcomeV2.PRESERVED_A0,
            reason=f"prelaunch_declined:{exc}", probes=tuple(probe_traces),
            family=probe.family, contract=contract,
        )
    try:
        tool_receipt = adapter.execute(contract, task, probe)
    except ToolBoundaryFailure as exc:
        outcome = RuntimeOutcomeV2.TOOL_TIMEOUT if exc.code is BoundaryFailureCode.TIMEOUT else RuntimeOutcomeV2.TOOL_ERROR
        try:
            ledger.settle(
                call_id,
                usage=exc.usage,
                tool_calls=exc.tool_calls,
                latency_ms=exc.latency_ms,
                monetary_microunits=exc.monetary_microunits,
            )
            complete = True
        except RuntimeLedgerError:
            if call_id in ledger.active_call_ids:
                ledger.cancel(call_id, "boundary_failure_accounting_invalid")
            complete = False
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=outcome, reason=f"{exc.code.value}:{exc.detail}",
            probes=tuple(probe_traces), family=probe.family, contract=contract,
            cost_accounting_complete=complete,
        )
    tool_receipt.validate_against(contract)
    archive_receipt: EvidenceArchiveReceipt | None = None
    if archive is not None:
        try:
            archive_receipt = archive.store(contract, tool_receipt)
        except OSError as exc:
            ledger.cancel(call_id, "raw_evidence_persistence_failed")
            return a0, _receipt(
                task, a0, opportunity, before, ledger,
                outcome=RuntimeOutcomeV2.PERSISTENCE_ERROR,
                reason=f"raw_evidence_persistence_failed:{type(exc).__name__}",
                probes=tuple(probe_traces), family=probe.family,
                contract=contract, tool_receipt=tool_receipt,
                cost_accounting_complete=False,
            )
    if tool_receipt.outcome not in {ToolOutcomeV2.RESOLVED, ToolOutcomeV2.SUPPORTING}:
        ledger.settle(
            call_id, usage=tool_receipt.usage, tool_calls=tool_receipt.tool_calls,
            latency_ms=tool_receipt.latency_ms,
            monetary_microunits=tool_receipt.monetary_microunits,
        )
        return a0, _receipt(
            task, a0, opportunity, before, ledger,
            outcome=RuntimeOutcomeV2.PRESERVED_A0,
            reason=f"tool_{tool_receipt.outcome.value.lower()}",
            probes=tuple(probe_traces), family=probe.family,
            contract=contract, tool_receipt=tool_receipt,
            archive_receipt=archive_receipt,
        )

    packet = _packet_from_receipt(task, tool_receipt)
    a0_candidate = single_answer_candidate(
        a0,
        answer_kind=obligation.answer_kind,
        origin=CandidateOrigin.BASE,
        unit=obligation.requested_unit,
        temporal_scope=obligation.temporal_scope,
        jurisdiction=obligation.jurisdiction,
    )
    a0_assessment = compare_candidate_v2(
        a0_candidate,
        packet,
        obligation=obligation,
        policy=policy.comparator,
        semantic_comparator=semantic_comparator,
    )
    constructor: ConstructorReceiptV2 | None = None
    b_candidate: CandidateAnswer | None = None
    if tool_receipt.outcome is ToolOutcomeV2.RESOLVED:
        assert tool_receipt.candidate_answer is not None
        b_candidate = single_answer_candidate(
            tool_receipt.candidate_answer,
            answer_kind=obligation.answer_kind,
            origin=CandidateOrigin.EVIDENCE_CONSTRUCTED,
            computation_receipt_ids=(packet.computations[0].receipt_id,),
            unit=obligation.requested_unit,
            temporal_scope=obligation.temporal_scope,
            jurisdiction=obligation.jurisdiction,
        )
    else:
        request = ConstructorRequestV2(
            task.question,
            obligation,
            packet,
            policy.constructor.maximum_output_tokens,
        )
        constructor = run_bounded_constructor_v2(
            request, policy=policy.constructor, runner=constructor_runner
        )
        if constructor.outcome in {ConstructorOutcomeV2.PROVIDER_ERROR, ConstructorOutcomeV2.TIMEOUT}:
            total = _total_usage(tool_receipt, constructor, a0_assessment, None)
            try:
                ledger.settle(
                    call_id, usage=total, tool_calls=tool_receipt.tool_calls,
                    latency_ms=tool_receipt.latency_ms + constructor.latency_ms,
                    monetary_microunits=(tool_receipt.monetary_microunits + constructor.monetary_microunits),
                )
                complete = True
            except RuntimeLedgerError:
                if call_id in ledger.active_call_ids:
                    ledger.cancel(call_id, "constructor_failure_accounting_invalid")
                complete = False
            return a0, _receipt(
                task, a0, opportunity, before, ledger,
                outcome=RuntimeOutcomeV2.CONSTRUCTOR_ERROR,
                reason=constructor.reason, probes=tuple(probe_traces),
                family=probe.family, contract=contract, tool_receipt=tool_receipt,
                archive_receipt=archive_receipt, packet=packet,
                a0_assessment=a0_assessment, constructor=constructor,
                cost_accounting_complete=complete,
            )
        b_candidate = constructor.candidate

    b_assessment = None
    if b_candidate is not None:
        b_assessment = compare_candidate_v2(
            b_candidate,
            packet,
            obligation=obligation,
            policy=policy.comparator,
            semantic_comparator=semantic_comparator,
        )
    final, selection = select_answer_v2(
        a0,
        a0_assessment,
        b_assessment,
        evidence_packet_digest=packet.packet_digest,
        policy=SelectorPolicyV2(answer_change_enabled=policy.answer_change_enabled),
    )
    total = _total_usage(tool_receipt, constructor, a0_assessment, b_assessment)
    ledger.settle(
        call_id,
        usage=total,
        tool_calls=tool_receipt.tool_calls,
        latency_ms=(
            tool_receipt.latency_ms
            + (0 if constructor is None else constructor.latency_ms)
            + a0_assessment.latency_ms
            + (0 if b_assessment is None else b_assessment.latency_ms)
        ),
        monetary_microunits=(
            tool_receipt.monetary_microunits
            + (0 if constructor is None else constructor.monetary_microunits)
            + a0_assessment.monetary_microunits
            + (0 if b_assessment is None else b_assessment.monetary_microunits)
        ),
    )
    route_outcome = (
        RuntimeOutcomeV2.VERIFY_RESOLVED
        if probe.family is not RuntimeToolFamily.PASSAGE_RETRIEVAL
        and (a0_assessment.fully_supported or (b_assessment is not None and b_assessment.fully_supported))
        else RuntimeOutcomeV2.FULL_RESOLVED
        if probe.family is RuntimeToolFamily.PASSAGE_RETRIEVAL
        and (a0_assessment.fully_supported or (b_assessment is not None and b_assessment.fully_supported))
        else RuntimeOutcomeV2.PRESERVED_A0
    )
    return final, _receipt(
        task, a0, opportunity, before, ledger,
        outcome=route_outcome, reason=selection.reason, final=final,
        probes=tuple(probe_traces), family=probe.family, contract=contract,
        tool_receipt=tool_receipt, archive_receipt=archive_receipt,
        packet=packet, a0_assessment=a0_assessment, constructor=constructor,
        b_assessment=b_assessment, selection=selection,
    )
