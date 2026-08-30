"""Additive symmetric comparator extensions for FOIL v2."""

from __future__ import annotations

from foil_evidence_contract import (
    AnswerKind,
    CandidateAnswer,
    CandidateOrigin,
    ClaimKind,
    EvidencePacket,
    QuestionObligation,
)
from foil_retrieval_claim_comparator import (
    PPM,
    AnswerAssessment,
    ClaimStatus,
    ClaimVerdict,
    ComparatorPolicy,
    ComparisonAuthority,
    ComparisonMethod,
    SemanticComparator,
    compare_candidate,
)
from foil_typed_formula import FormulaStatus, compare_formula, discover_formula_task, extract_target_formulas


def _normalize(value: str, kind: AnswerKind) -> str:
    from fractions import Fraction
    import re

    if kind is AnswerKind.NUMBER:
        try:
            number = Fraction(value.strip())
        except (ValueError, ZeroDivisionError):
            pass
        else:
            return str(number.numerator) if number.denominator == 1 else f"{number.numerator}/{number.denominator}"
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def compare_candidate_v2(
    candidate: CandidateAnswer,
    packet: EvidencePacket,
    *,
    obligation: QuestionObligation,
    policy: ComparatorPolicy,
    semantic_comparator: SemanticComparator | None = None,
    question: str | None = None,
) -> AnswerAssessment:
    """Apply the same independent mechanical packet check to A0 and B.

    V1 already handles explicitly bound computations and exact source spans. V2
    additionally lets a unique host computation adjudicate an unbound ANSWER
    claim. It declines when packet computations disagree or are ambiguous.
    """

    base = compare_candidate(
        candidate,
        packet,
        obligation=obligation,
        policy=policy,
        semantic_comparator=semantic_comparator,
    )
    replacements: list[ClaimVerdict] = []
    changed = False
    claims = {item.claim_id: item for item in candidate.claims}

    verification_outputs = {
        _normalize(item.candidate_answer, candidate.answer_kind)
        for item in packet.verifications
    }
    if len(verification_outputs) == 1:
        expected = next(iter(verification_outputs))
        for verdict in base.verdicts:
            claim = claims[verdict.claim_id]
            if claim.kind is ClaimKind.ANSWER and verdict.method is ComparisonMethod.NO_APPLICABLE_COMPARATOR:
                matches = _normalize(claim.normalized_value, candidate.answer_kind) == expected
                replacements.append(
                    ClaimVerdict(
                        claim.claim_id,
                        ClaimStatus.SUPPORTED if matches else ClaimStatus.CONTRADICTED,
                        ComparisonAuthority.MECHANICAL,
                        ComparisonMethod.EXACT_VERIFICATION,
                        PPM,
                        (),
                        (),
                        "unique_packet_verification_matches_answer" if matches else "unique_packet_verification_contradicts_answer",
                        verification_receipt_ids=tuple(item.receipt_id for item in packet.verifications),
                    )
                )
                changed = True
            else:
                replacements.append(verdict)
        if changed:
            base = _assessment(candidate, replacements, policy)

    formula_task = None if question is None else discover_formula_task(question)
    if formula_task is not None and packet.spans:
        document_map = {item.document_id: item for item in packet.documents}
        eligible_spans = tuple(
            span for span in packet.spans
            if document_map[span.document_id].source_class in policy.allowed_source_classes
            and (obligation.temporal_scope is None or document_map[span.document_id].temporal_scope == obligation.temporal_scope)
            and (obligation.jurisdiction is None or document_map[span.document_id].jurisdiction == obligation.jurisdiction)
        )
        formula_replacements: list[ClaimVerdict] = []
        formula_changed = False
        for verdict in base.verdicts:
            claim = claims[verdict.claim_id]
            if verdict.status is ClaimStatus.OUT_OF_SCOPE:
                formula_replacements.append(verdict)
                continue
            claim_reference_spans = (
                tuple(span for span in eligible_spans if span.span_id in claim.evidence_span_ids)
                if candidate.origin is CandidateOrigin.EVIDENCE_CONSTRUCTED
                else eligible_spans
            )
            comparison = compare_formula(
                claim.normalized_value,
                tuple(span.text for span in claim_reference_spans),
                formula_task.target,
            )
            if comparison.status in {FormulaStatus.EQUIVALENT, FormulaStatus.DIFFERENT}:
                cited = tuple(
                    span.span_id for span in claim_reference_spans
                    if extract_target_formulas(span.text, formula_task.target)
                )
                formula_replacements.append(
                    ClaimVerdict(
                        claim.claim_id,
                        ClaimStatus.SUPPORTED if comparison.status is FormulaStatus.EQUIVALENT else ClaimStatus.CONTRADICTED,
                        ComparisonAuthority.SOURCE_BOUND_MECHANICAL_UNADMITTED,
                        ComparisonMethod.TYPED_FORMULA_STRUCTURE,
                        PPM,
                        cited,
                        (),
                        comparison.reason,
                    )
                )
                formula_changed = True
            else:
                formula_replacements.append(verdict)
        if formula_changed:
            base = _assessment(candidate, formula_replacements, policy)

    if candidate.answer_kind is not AnswerKind.NUMBER:
        return base
    outputs = {_normalize(item.output, candidate.answer_kind) for item in packet.computations}
    if len(outputs) != 1:
        return base
    expected = next(iter(outputs))
    replacements = []
    changed = False
    for verdict in base.verdicts:
        claim = claims[verdict.claim_id]
        if (
            claim.kind is ClaimKind.ANSWER
            and verdict.method is ComparisonMethod.NO_APPLICABLE_COMPARATOR
        ):
            matches = _normalize(claim.normalized_value, candidate.answer_kind) == expected
            replacements.append(
                ClaimVerdict(
                    claim.claim_id,
                    ClaimStatus.SUPPORTED if matches else ClaimStatus.CONTRADICTED,
                    ComparisonAuthority.MECHANICAL,
                    ComparisonMethod.EXACT_COMPUTATION,
                    PPM,
                    (),
                    tuple(item.receipt_id for item in packet.computations),
                    (
                        "unique_packet_computation_matches_answer"
                        if matches
                        else "unique_packet_computation_contradicts_answer"
                    ),
                )
            )
            changed = True
        else:
            replacements.append(verdict)
    if not changed:
        return base
    return _assessment(candidate, replacements, policy)


def _assessment(
    candidate: CandidateAnswer,
    replacements: list[ClaimVerdict],
    policy: ComparatorPolicy,
) -> AnswerAssessment:
    supported = sum(item.status is ClaimStatus.SUPPORTED for item in replacements)
    contradicted = sum(item.status is ClaimStatus.CONTRADICTED for item in replacements)
    omitted = sum(item.reason == "constructed_claim_omits_evidence_binding" for item in replacements)
    unresolved = sum(
        item.status in {ClaimStatus.INSUFFICIENT, ClaimStatus.AMBIGUOUS, ClaimStatus.OUT_OF_SCOPE}
        for item in replacements
    ) - omitted
    admissible = {ComparisonAuthority.MECHANICAL, ComparisonAuthority.SEMANTIC_CALIBRATED}
    if policy.allow_unadmitted_benchmark_selection:
        admissible |= {
            ComparisonAuthority.SOURCE_BOUND_MECHANICAL_UNADMITTED,
            ComparisonAuthority.SEMANTIC_UNCALIBRATED,
            ComparisonAuthority.HYBRID_UNADMITTED,
        }
    eligible = bool(replacements) and all(
        item.status is ClaimStatus.SUPPORTED and item.authority in admissible
        for item in replacements
    )
    return AnswerAssessment(
        candidate,
        tuple(replacements),
        supported,
        contradicted,
        unresolved,
        omitted,
        eligible,
    )
