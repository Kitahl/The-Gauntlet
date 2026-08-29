"""Answer-blind claim comparison over one frozen FOIL evidence packet.

The semantic callback sees one claim plus source spans, never the surrounding
answer or whether the claim came from A0 or B.  Exact arithmetic and exact
bound-span equality are mechanical; semantic and retrieval-to-computation
results remain unadmitted unless policy explicitly records calibration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Callable

from foil_evidence_contract import (
    AnswerKind,
    AtomicClaim,
    CandidateAnswer,
    CandidateOrigin,
    ContentSafety,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
)


PPM = 1_000_000


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"
    AMBIGUOUS = "AMBIGUOUS"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ComparisonAuthority(str, Enum):
    MECHANICAL = "MECHANICAL"
    SEMANTIC_UNCALIBRATED = "SEMANTIC_UNCALIBRATED"
    SEMANTIC_CALIBRATED = "SEMANTIC_CALIBRATED"
    HYBRID_UNADMITTED = "HYBRID_UNADMITTED"


class ComparisonMethod(str, Enum):
    EXACT_BOUND_SPAN = "EXACT_BOUND_SPAN"
    EXACT_COMPUTATION = "EXACT_COMPUTATION"
    SEMANTIC_CALLBACK = "SEMANTIC_CALLBACK"
    NO_APPLICABLE_COMPARATOR = "NO_APPLICABLE_COMPARATOR"


def _ppm(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= PPM:
        raise ValueError(f"{name} must be integer ppm")
    return value


def _normalized_text(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _normalized_value(value: str, kind: AnswerKind) -> str:
    if kind is AnswerKind.NUMBER:
        try:
            fraction = Fraction(value.strip())
        except (ValueError, ZeroDivisionError):
            return _normalized_text(value)
        return str(fraction.numerator) if fraction.denominator == 1 else f"{fraction.numerator}/{fraction.denominator}"
    return _normalized_text(value)


@dataclass(frozen=True)
class SemanticComparison:
    status: ClaimStatus
    confidence_ppm: int
    evidence_span_ids: tuple[str, ...]
    reason: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    model_passes: int = 1
    latency_ms: int = 0
    monetary_microunits: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ClaimStatus(self.status))
        _ppm("confidence_ppm", self.confidence_ppm)
        if not isinstance(self.evidence_span_ids, tuple) or not all(
            isinstance(item, str) and item for item in self.evidence_span_ids
        ):
            raise TypeError("evidence_span_ids must be a string tuple")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("semantic comparison requires a reason")
        for name in (
            "input_tokens", "cached_input_tokens", "output_tokens", "model_passes",
            "latency_ms", "monetary_microunits",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.model_passes != 1:
            raise ValueError("one semantic comparison result must record one model pass")


SemanticComparator = Callable[[AtomicClaim, tuple[EvidenceSpan, ...]], SemanticComparison]


@dataclass(frozen=True)
class ComparatorPolicy:
    semantic_enabled: bool = False
    semantic_route_admitted: bool = False
    allow_unadmitted_benchmark_selection: bool = False
    minimum_semantic_confidence_ppm: int = 950_000
    maximum_claims: int = 3
    allowed_source_classes: tuple[SourceClass, ...] = tuple(SourceClass)

    def __post_init__(self) -> None:
        for name in ("semantic_enabled", "semantic_route_admitted", "allow_unadmitted_benchmark_selection"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        _ppm("minimum_semantic_confidence_ppm", self.minimum_semantic_confidence_ppm)
        if isinstance(self.maximum_claims, bool) or not isinstance(self.maximum_claims, int) or not 1 <= self.maximum_claims <= 8:
            raise ValueError("maximum_claims must be in [1, 8]")
        if not isinstance(self.allowed_source_classes, tuple) or not self.allowed_source_classes:
            raise ValueError("allowed_source_classes must be a non-empty tuple")
        object.__setattr__(
            self,
            "allowed_source_classes",
            tuple(SourceClass(item) for item in self.allowed_source_classes),
        )
        if self.semantic_route_admitted and not self.semantic_enabled:
            raise ValueError("semantic route cannot be admitted while disabled")


@dataclass(frozen=True)
class ClaimVerdict:
    claim_id: str
    status: ClaimStatus
    authority: ComparisonAuthority
    method: ComparisonMethod
    confidence_ppm: int
    evidence_span_ids: tuple[str, ...]
    computation_receipt_ids: tuple[str, ...]
    reason: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    model_passes: int = 0
    latency_ms: int = 0
    monetary_microunits: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ClaimStatus(self.status))
        object.__setattr__(self, "authority", ComparisonAuthority(self.authority))
        object.__setattr__(self, "method", ComparisonMethod(self.method))
        _ppm("confidence_ppm", self.confidence_ppm)
        for name in (
            "input_tokens", "cached_input_tokens", "output_tokens", "model_passes",
            "latency_ms", "monetary_microunits",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    def trace(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "authority": self.authority.value,
            "method": self.method.value,
            "confidence_ppm": self.confidence_ppm,
            "evidence_span_ids": list(self.evidence_span_ids),
            "computation_receipt_ids": list(self.computation_receipt_ids),
            "reason": self.reason,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "model_passes": self.model_passes,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
        }


@dataclass(frozen=True)
class AnswerAssessment:
    candidate: CandidateAnswer
    verdicts: tuple[ClaimVerdict, ...]
    supported: int
    contradicted: int
    unresolved: int
    omitted: int
    selection_eligible: bool

    def __post_init__(self) -> None:
        if len(self.verdicts) != len(self.candidate.claims):
            raise ValueError("one verdict is required for every candidate claim")
        if self.supported + self.contradicted + self.unresolved + self.omitted != len(self.candidate.claims):
            raise ValueError("claim assessment conservation failed")

    @property
    def fully_supported(self) -> bool:
        return self.supported == len(self.candidate.claims) and self.contradicted == 0 and self.unresolved == 0 and self.omitted == 0

    @property
    def has_critical_contradiction(self) -> bool:
        critical = {claim.claim_id for claim in self.candidate.claims if claim.critical}
        return any(verdict.claim_id in critical and verdict.status is ClaimStatus.CONTRADICTED for verdict in self.verdicts)

    @property
    def actual_total_tokens(self) -> int:
        return sum(item.input_tokens + item.cached_input_tokens + item.output_tokens for item in self.verdicts)

    @property
    def model_passes(self) -> int:
        return sum(item.model_passes for item in self.verdicts)

    @property
    def latency_ms(self) -> int:
        return sum(item.latency_ms for item in self.verdicts)

    @property
    def monetary_microunits(self) -> int:
        return sum(item.monetary_microunits for item in self.verdicts)

    def trace(self) -> dict[str, object]:
        return {
            "candidate": self.candidate.trace(),
            "verdicts": [item.trace() for item in self.verdicts],
            "supported": self.supported,
            "contradicted": self.contradicted,
            "unresolved": self.unresolved,
            "omitted": self.omitted,
            "claim_count": len(self.candidate.claims),
            "claim_conservation": self.supported + self.contradicted + self.unresolved + self.omitted == len(self.candidate.claims),
            "fully_supported": self.fully_supported,
            "has_critical_contradiction": self.has_critical_contradiction,
            "selection_eligible": self.selection_eligible,
            "actual_total_tokens": self.actual_total_tokens,
            "model_passes": self.model_passes,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "answer_identity_exposed_to_semantic_comparator": False,
        }


def _computation_verdict(claim: AtomicClaim, packet: EvidencePacket, answer_kind: AnswerKind) -> ClaimVerdict | None:
    if answer_kind is not AnswerKind.NUMBER or not claim.computation_receipt_ids:
        return None
    receipts = [packet.computation(receipt_id) for receipt_id in claim.computation_receipt_ids]
    outputs = {_normalized_value(item.output, answer_kind) for item in receipts}
    expected = _normalized_value(claim.normalized_value, answer_kind)
    supported = outputs == {expected}
    has_retrieved_inputs = any(
        binding.evidence_span_id is not None
        for receipt in receipts
        for binding in receipt.bindings
    )
    return ClaimVerdict(
        claim.claim_id,
        ClaimStatus.SUPPORTED if supported else ClaimStatus.CONTRADICTED,
        ComparisonAuthority.HYBRID_UNADMITTED if has_retrieved_inputs else ComparisonAuthority.MECHANICAL,
        ComparisonMethod.EXACT_COMPUTATION,
        PPM,
        tuple(
            binding.evidence_span_id
            for receipt in receipts
            for binding in receipt.bindings
            if binding.evidence_span_id is not None
        ),
        claim.computation_receipt_ids,
        "exact_computation_matches_claim" if supported else "exact_computation_contradicts_claim",
    )


def _exact_span_verdict(claim: AtomicClaim, packet: EvidencePacket, answer_kind: AnswerKind) -> ClaimVerdict | None:
    if not claim.evidence_span_ids:
        return None
    spans = tuple(packet.span(span_id) for span_id in claim.evidence_span_ids)
    expected = _normalized_value(claim.normalized_value, answer_kind)
    exact = [span for span in spans if _normalized_value(span.text, answer_kind) == expected]
    if not exact:
        return None
    return ClaimVerdict(
        claim.claim_id,
        ClaimStatus.SUPPORTED,
        ComparisonAuthority.MECHANICAL,
        ComparisonMethod.EXACT_BOUND_SPAN,
        PPM,
        tuple(span.span_id for span in exact),
        (),
        "claim_is_exact_normalized_bound_span",
    )


def compare_candidate(
    candidate: CandidateAnswer,
    packet: EvidencePacket,
    *,
    obligation: QuestionObligation,
    policy: ComparatorPolicy,
    semantic_comparator: SemanticComparator | None = None,
) -> AnswerAssessment:
    """Compare every claim, preserving omissions and unresolvable claims."""

    if not isinstance(candidate, CandidateAnswer):
        raise TypeError("candidate must be CandidateAnswer")
    if not isinstance(packet, EvidencePacket):
        raise TypeError("packet must be EvidencePacket")
    if not isinstance(obligation, QuestionObligation):
        raise TypeError("obligation must be QuestionObligation")
    if obligation.question_digest != packet.question_digest:
        raise ValueError("obligation does not bind evidence packet")
    if candidate.answer_kind is not obligation.answer_kind:
        raise ValueError("candidate answer kind does not match obligation")
    if not isinstance(policy, ComparatorPolicy):
        raise TypeError("policy must be ComparatorPolicy")
    if len(candidate.claims) > policy.maximum_claims:
        raise ValueError("candidate exceeds comparator claim bound")
    if policy.semantic_enabled and semantic_comparator is None:
        raise ValueError("semantic-enabled comparator requires callback")
    if not policy.semantic_enabled and semantic_comparator is not None:
        raise ValueError("semantic callback supplied while disabled")
    if policy.semantic_enabled and any(
        document.content_safety is not ContentSafety.SANITIZED_DATA_ONLY
        for document in packet.documents
    ):
        raise ValueError("semantic comparator accepts only sanitized data-only evidence")

    verdicts: list[ClaimVerdict] = []
    document_map = {document.document_id: document for document in packet.documents}
    packet_spans = tuple(
        span for span in packet.spans
        if (obligation.temporal_scope is None or document_map[span.document_id].temporal_scope == obligation.temporal_scope)
        and (obligation.jurisdiction is None or document_map[span.document_id].jurisdiction == obligation.jurisdiction)
        and document_map[span.document_id].source_class in policy.allowed_source_classes
    )
    for claim in candidate.claims:
        scope_mismatch = bool(
            (obligation.requested_unit is not None and claim.unit != obligation.requested_unit)
            or (obligation.temporal_scope is not None and claim.temporal_scope != obligation.temporal_scope)
            or (obligation.jurisdiction is not None and claim.jurisdiction != obligation.jurisdiction)
        )
        if scope_mismatch:
            verdicts.append(
                ClaimVerdict(
                    claim.claim_id, ClaimStatus.OUT_OF_SCOPE,
                    ComparisonAuthority.SEMANTIC_UNCALIBRATED,
                    ComparisonMethod.NO_APPLICABLE_COMPARATOR, 0, (), (),
                    "claim_scope_does_not_match_question_obligation",
                )
            )
            continue
        bound_span_ids = set(claim.evidence_span_ids)
        for receipt_id in claim.computation_receipt_ids:
            for binding in packet.computation(receipt_id).bindings:
                if binding.evidence_span_id is not None:
                    bound_span_ids.add(binding.evidence_span_id)
        bound_out_of_scope = bound_span_ids - {span.span_id for span in packet_spans}
        if bound_out_of_scope:
            verdicts.append(
                ClaimVerdict(
                    claim.claim_id, ClaimStatus.OUT_OF_SCOPE,
                    ComparisonAuthority.SEMANTIC_UNCALIBRATED,
                    ComparisonMethod.NO_APPLICABLE_COMPARATOR, 0, (), (),
                    "bound_evidence_outside_source_temporal_or_jurisdiction_scope",
                )
            )
            continue
        if candidate.origin is CandidateOrigin.EVIDENCE_CONSTRUCTED and not (
            claim.evidence_span_ids or claim.computation_receipt_ids
        ):
            verdicts.append(
                ClaimVerdict(
                    claim.claim_id, ClaimStatus.INSUFFICIENT,
                    ComparisonAuthority.SEMANTIC_UNCALIBRATED,
                    ComparisonMethod.NO_APPLICABLE_COMPARATOR, 0, (), (),
                    "constructed_claim_omits_evidence_binding",
                )
            )
            continue
        mechanical = _computation_verdict(claim, packet, candidate.answer_kind)
        if mechanical is None:
            mechanical = _exact_span_verdict(claim, packet, candidate.answer_kind)
        if mechanical is not None:
            verdicts.append(mechanical)
            continue
        if policy.semantic_enabled and semantic_comparator is not None:
            result = semantic_comparator(claim, packet_spans)
            if not isinstance(result, SemanticComparison):
                raise TypeError("semantic comparator must return SemanticComparison")
            unknown = set(result.evidence_span_ids) - {span.span_id for span in packet_spans}
            if unknown:
                raise ValueError("semantic comparator returned unknown evidence span")
            if (
                candidate.origin is CandidateOrigin.EVIDENCE_CONSTRUCTED
                and not set(result.evidence_span_ids).issubset(set(claim.evidence_span_ids))
            ):
                raise ValueError("semantic comparator cited evidence outside constructed claim binding")
            status = result.status
            if result.confidence_ppm < policy.minimum_semantic_confidence_ppm:
                status = ClaimStatus.INSUFFICIENT
            verdicts.append(
                ClaimVerdict(
                    claim.claim_id,
                    status,
                    ComparisonAuthority.SEMANTIC_CALIBRATED if policy.semantic_route_admitted else ComparisonAuthority.SEMANTIC_UNCALIBRATED,
                    ComparisonMethod.SEMANTIC_CALLBACK,
                    result.confidence_ppm,
                    result.evidence_span_ids,
                    (),
                    result.reason,
                    result.input_tokens,
                    result.cached_input_tokens,
                    result.output_tokens,
                    result.model_passes,
                    result.latency_ms,
                    result.monetary_microunits,
                )
            )
            continue
        verdicts.append(
            ClaimVerdict(
                claim.claim_id, ClaimStatus.INSUFFICIENT,
                ComparisonAuthority.SEMANTIC_UNCALIBRATED,
                ComparisonMethod.NO_APPLICABLE_COMPARATOR, 0, (), (),
                "no_applicable_claim_comparator",
            )
        )

    supported = sum(item.status is ClaimStatus.SUPPORTED for item in verdicts)
    contradicted = sum(item.status is ClaimStatus.CONTRADICTED for item in verdicts)
    unresolved = sum(item.status in {ClaimStatus.INSUFFICIENT, ClaimStatus.AMBIGUOUS, ClaimStatus.OUT_OF_SCOPE} for item in verdicts)
    omitted = sum(item.reason == "constructed_claim_omits_evidence_binding" for item in verdicts)
    unresolved -= omitted
    admissible = {ComparisonAuthority.MECHANICAL, ComparisonAuthority.SEMANTIC_CALIBRATED}
    if policy.allow_unadmitted_benchmark_selection:
        admissible |= {ComparisonAuthority.SEMANTIC_UNCALIBRATED, ComparisonAuthority.HYBRID_UNADMITTED}
    selection_eligible = bool(verdicts) and all(
        item.status is ClaimStatus.SUPPORTED and item.authority in admissible
        for item in verdicts
    )
    return AnswerAssessment(
        candidate,
        tuple(verdicts),
        supported,
        contradicted,
        unresolved,
        omitted,
        selection_eligible,
    )
