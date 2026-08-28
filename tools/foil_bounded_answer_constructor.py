"""One-pass, evidence-only answer construction for FOIL benchmarks.

The runner receives the question and a frozen evidence packet but never A0 and
never a tool handle.  It may return one bounded candidate or no candidate.
Schema, token, claim-count, and evidence-binding failures are typed and fail
closed without a retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from egrt_types import digest
from foil_evidence_contract import (
    AtomicClaim,
    CandidateAnswer,
    CandidateOrigin,
    ContentSafety,
    EvidencePacket,
    QuestionObligation,
)


class ConstructorOutcome(str, Enum):
    CANDIDATE = "CANDIDATE"
    NO_CANDIDATE = "NO_CANDIDATE"
    INVALID = "INVALID"
    ERROR = "ERROR"


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class ConstructorPolicy:
    enabled: bool = False
    maximum_output_tokens: int = 0
    maximum_claims: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        _count("maximum_output_tokens", self.maximum_output_tokens)
        if isinstance(self.maximum_claims, bool) or not isinstance(self.maximum_claims, int) or not 1 <= self.maximum_claims <= 8:
            raise ValueError("maximum_claims must be in [1, 8]")
        if self.enabled and self.maximum_output_tokens == 0:
            raise ValueError("enabled constructor requires a positive output cap")


@dataclass(frozen=True)
class ConstructorDraft:
    answer: str | None
    claims: tuple[AtomicClaim, ...]
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reason: str
    latency_ms: int = 0
    monetary_microunits: int = 0

    def __post_init__(self) -> None:
        if self.answer is not None and (not isinstance(self.answer, str) or not self.answer.strip()):
            raise ValueError("answer must be non-empty text or None")
        if not isinstance(self.claims, tuple) or not all(isinstance(item, AtomicClaim) for item in self.claims):
            raise TypeError("claims must be an AtomicClaim tuple")
        for name in (
            "input_tokens", "cached_input_tokens", "output_tokens",
            "latency_ms", "monetary_microunits",
        ):
            _count(name, getattr(self, name))
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("constructor draft requires a reason")
        if self.answer is None and self.claims:
            raise ValueError("no-candidate draft cannot carry claims")
        if self.answer is not None and not self.claims:
            raise ValueError("candidate draft requires claims")


ConstructorRunner = Callable[
    [str, QuestionObligation, EvidencePacket, int], ConstructorDraft
]


@dataclass(frozen=True)
class ConstructorReceipt:
    outcome: ConstructorOutcome
    candidate: CandidateAnswer | None
    reason: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    question_digest: str
    evidence_packet_digest: str
    a0_exposed: bool = False
    tools_available: bool = False
    model_passes: int = 0
    latency_ms: int = 0
    monetary_microunits: int = 0

    @property
    def actual_total_tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "foil.bounded-constructor-receipt.v1",
            "outcome": self.outcome.value,
            "candidate": None if self.candidate is None else self.candidate.trace(),
            "reason": self.reason,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "actual_total_tokens": self.actual_total_tokens,
            "question_digest": self.question_digest,
            "evidence_packet_sha256": self.evidence_packet_digest,
            "a0_exposed": False,
            "tools_available": False,
            "model_passes": self.model_passes,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "retry_count": 0,
            "raw_candidate_stored": False,
        }
        body["receipt_sha256"] = digest(body)
        return body


def run_bounded_constructor(
    question: str,
    obligation: QuestionObligation,
    packet: EvidencePacket,
    *,
    policy: ConstructorPolicy,
    runner: ConstructorRunner | None,
) -> ConstructorReceipt:
    """Run at most one blind constructor pass and validate its complete draft."""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    if not isinstance(obligation, QuestionObligation):
        raise TypeError("obligation must be QuestionObligation")
    if not isinstance(packet, EvidencePacket):
        raise TypeError("packet must be EvidencePacket")
    if not isinstance(policy, ConstructorPolicy):
        raise TypeError("policy must be ConstructorPolicy")
    question_digest = digest(question)
    if question_digest != obligation.question_digest or question_digest != packet.question_digest:
        raise ValueError("question, obligation, and evidence packet are not bound")
    if any(document.content_safety is not ContentSafety.SANITIZED_DATA_ONLY for document in packet.documents):
        raise ValueError("constructor accepts only sanitized data-only evidence")
    if not policy.enabled:
        if runner is not None:
            raise ValueError("disabled constructor must not receive runner")
        return ConstructorReceipt(
            ConstructorOutcome.NO_CANDIDATE, None, "constructor_disabled",
            0, 0, 0, question_digest, packet.packet_digest,
        )
    if runner is None:
        raise ValueError("enabled constructor requires runner")
    try:
        draft = runner(question, obligation, packet, policy.maximum_output_tokens)
        if not isinstance(draft, ConstructorDraft):
            raise TypeError("constructor runner must return ConstructorDraft")
    except Exception:
        return ConstructorReceipt(
            ConstructorOutcome.ERROR, None, "constructor_runner_exception",
            0, 0, 0, question_digest, packet.packet_digest, model_passes=1,
        )
    if draft.output_tokens > policy.maximum_output_tokens:
        return ConstructorReceipt(
            ConstructorOutcome.INVALID, None, "constructor_output_cap_exceeded",
            draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
            question_digest, packet.packet_digest, model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    if draft.answer is None:
        return ConstructorReceipt(
            ConstructorOutcome.NO_CANDIDATE, None, draft.reason,
            draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
            question_digest, packet.packet_digest, model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    if len(draft.claims) > policy.maximum_claims:
        return ConstructorReceipt(
            ConstructorOutcome.INVALID, None, "constructor_claim_cap_exceeded",
            draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
            question_digest, packet.packet_digest, model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    known_spans = {item.span_id for item in packet.spans}
    known_receipts = {item.receipt_id for item in packet.computations}
    for claim in draft.claims:
        if not (claim.evidence_span_ids or claim.computation_receipt_ids):
            return ConstructorReceipt(
                ConstructorOutcome.INVALID, None, "constructed_claim_missing_binding",
                draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
                question_digest, packet.packet_digest, model_passes=1,
                latency_ms=draft.latency_ms,
                monetary_microunits=draft.monetary_microunits,
            )
        if set(claim.evidence_span_ids) - known_spans:
            return ConstructorReceipt(
                ConstructorOutcome.INVALID, None, "constructed_claim_unknown_span",
                draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
                question_digest, packet.packet_digest, model_passes=1,
                latency_ms=draft.latency_ms,
                monetary_microunits=draft.monetary_microunits,
            )
        if set(claim.computation_receipt_ids) - known_receipts:
            return ConstructorReceipt(
                ConstructorOutcome.INVALID, None, "constructed_claim_unknown_computation",
                draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
                question_digest, packet.packet_digest, model_passes=1,
                latency_ms=draft.latency_ms,
                monetary_microunits=draft.monetary_microunits,
            )
    candidate = CandidateAnswer(
        answer_id=f"constructed-{digest({'answer': draft.answer, 'packet': packet.packet_digest})[:16]}",
        answer=draft.answer,
        answer_kind=obligation.answer_kind,
        claims=draft.claims,
        origin=CandidateOrigin.EVIDENCE_CONSTRUCTED,
    )
    return ConstructorReceipt(
        ConstructorOutcome.CANDIDATE, candidate, draft.reason,
        draft.input_tokens, draft.cached_input_tokens, draft.output_tokens,
        question_digest, packet.packet_digest, model_passes=1,
        latency_ms=draft.latency_ms,
        monetary_microunits=draft.monetary_microunits,
    )
