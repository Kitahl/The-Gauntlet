"""Additive symmetric comparator extensions for FOIL v2."""

from __future__ import annotations

from foil_evidence_contract import (
    AnswerKind,
    CandidateAnswer,
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
    if candidate.answer_kind is not AnswerKind.NUMBER:
        return base
    outputs = {_normalize(item.output, candidate.answer_kind) for item in packet.computations}
    if len(outputs) != 1:
        return base
    expected = next(iter(outputs))
    replacements: list[ClaimVerdict] = []
    changed = False
    claims = {item.claim_id: item for item in candidate.claims}
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
    supported = sum(item.status is ClaimStatus.SUPPORTED for item in replacements)
    contradicted = sum(item.status is ClaimStatus.CONTRADICTED for item in replacements)
    omitted = sum(item.reason == "constructed_claim_omits_evidence_binding" for item in replacements)
    unresolved = sum(
        item.status in {ClaimStatus.INSUFFICIENT, ClaimStatus.AMBIGUOUS, ClaimStatus.OUT_OF_SCOPE}
        for item in replacements
    ) - omitted
    admissible = {ComparisonAuthority.MECHANICAL, ComparisonAuthority.SEMANTIC_CALIBRATED}
    if policy.allow_unadmitted_benchmark_selection:
        admissible |= {ComparisonAuthority.SEMANTIC_UNCALIBRATED, ComparisonAuthority.HYBRID_UNADMITTED}
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
