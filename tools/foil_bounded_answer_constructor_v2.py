"""One-pass evidence-conditioned candidate construction for FOIL v2.

The request type has no A0 field and no tool handle.  A provider output limit is
optional; when present it must be enforced by the provider.  Declared provider
boundary failures carry their real accounting instead of becoming a fabricated
zero-token generic error.
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
from foil_tool_contract_v2 import TokenUsageV2


class ConstructorOutcomeV2(str, Enum):
    CANDIDATE = "CANDIDATE"
    NO_CANDIDATE = "NO_CANDIDATE"
    INVALID = "INVALID"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class ConstructorPolicyV2:
    enabled: bool = False
    maximum_claims: int = 3
    maximum_output_tokens: int | None = None
    provider_cap_enforced: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("enabled and provider_cap_enforced must be bool")
        if isinstance(self.maximum_claims, bool) or not isinstance(self.maximum_claims, int) or not 1 <= self.maximum_claims <= 8:
            raise ValueError("maximum_claims must be in [1, 8]")
        if self.maximum_output_tokens is not None:
            if (
                isinstance(self.maximum_output_tokens, bool)
                or not isinstance(self.maximum_output_tokens, int)
                or self.maximum_output_tokens <= 0
            ):
                raise ValueError("maximum_output_tokens must be positive or None")
            if not self.provider_cap_enforced:
                raise ValueError("an output cap must be provider-enforced")
        elif self.provider_cap_enforced:
            raise ValueError("provider_cap_enforced requires a configured output cap")


@dataclass(frozen=True)
class ConstructorRequestV2:
    question: str
    obligation: QuestionObligation
    evidence_packet: EvidencePacket
    maximum_output_tokens: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("question must be non-empty text")
        if digest(self.question) != self.obligation.question_digest:
            raise ValueError("constructor request question does not bind obligation")
        if self.evidence_packet.question_digest != self.obligation.question_digest:
            raise ValueError("constructor request evidence does not bind obligation")

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.constructor-request.v2",
            "question_sha256": digest(self.question),
            "obligation_sha256": self.obligation.trace()["obligation_sha256"],
            "evidence_packet_sha256": self.evidence_packet.packet_digest,
            "maximum_output_tokens": self.maximum_output_tokens,
            "a0_exposed": False,
            "tools_available": False,
        }


@dataclass(frozen=True)
class ConstructorDraftV2:
    answer: str | None
    claims: tuple[AtomicClaim, ...]
    usage: TokenUsageV2
    reason: str
    prompt_digest: str
    latency_ms: int = 0
    monetary_microunits: int = 0

    def __post_init__(self) -> None:
        if self.answer is not None and (not isinstance(self.answer, str) or not self.answer.strip()):
            raise ValueError("answer must be non-empty text or None")
        if not isinstance(self.claims, tuple) or not all(isinstance(item, AtomicClaim) for item in self.claims):
            raise TypeError("claims must be an AtomicClaim tuple")
        if not isinstance(self.usage, TokenUsageV2):
            raise TypeError("usage must be TokenUsageV2")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("draft requires a reason")
        if not isinstance(self.prompt_digest, str) or len(self.prompt_digest) != 64:
            raise ValueError("prompt_digest must be SHA-256 hex")
        for name in ("latency_ms", "monetary_microunits"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.answer is None and self.claims:
            raise ValueError("no-candidate draft cannot carry claims")
        if self.answer is not None and not self.claims:
            raise ValueError("candidate draft requires claims")


class ConstructorBoundaryFailure(RuntimeError):
    outcome = ConstructorOutcomeV2.PROVIDER_ERROR

    def __init__(
        self,
        reason: str,
        *,
        usage: TokenUsageV2 | None = None,
        latency_ms: int = 0,
        monetary_microunits: int = 0,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.usage = TokenUsageV2() if usage is None else usage
        self.latency_ms = latency_ms
        self.monetary_microunits = monetary_microunits


class ConstructorTimeout(ConstructorBoundaryFailure):
    outcome = ConstructorOutcomeV2.TIMEOUT


ConstructorRunnerV2 = Callable[[ConstructorRequestV2], ConstructorDraftV2]


@dataclass(frozen=True)
class ConstructorReceiptV2:
    outcome: ConstructorOutcomeV2
    candidate: CandidateAnswer | None
    reason: str
    usage: TokenUsageV2
    question_digest: str
    evidence_packet_digest: str
    prompt_digest: str | None
    model_passes: int
    latency_ms: int
    monetary_microunits: int

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "foil.bounded-constructor-receipt.v2",
            "outcome": self.outcome.value,
            "candidate": None if self.candidate is None else self.candidate.trace(),
            "reason": self.reason,
            "usage": self.usage.trace(),
            "question_digest": self.question_digest,
            "evidence_packet_sha256": self.evidence_packet_digest,
            "prompt_sha256": self.prompt_digest,
            "model_passes": self.model_passes,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "a0_exposed": False,
            "tools_available": False,
            "raw_candidate_stored": False,
        }
        body["receipt_sha256"] = digest(body)
        return body


def _receipt(
    request: ConstructorRequestV2,
    outcome: ConstructorOutcomeV2,
    reason: str,
    *,
    candidate: CandidateAnswer | None = None,
    usage: TokenUsageV2 | None = None,
    prompt_digest: str | None = None,
    model_passes: int = 0,
    latency_ms: int = 0,
    monetary_microunits: int = 0,
) -> ConstructorReceiptV2:
    return ConstructorReceiptV2(
        outcome,
        candidate,
        reason,
        TokenUsageV2() if usage is None else usage,
        request.obligation.question_digest,
        request.evidence_packet.packet_digest,
        prompt_digest,
        model_passes,
        latency_ms,
        monetary_microunits,
    )


def run_bounded_constructor_v2(
    request: ConstructorRequestV2,
    *,
    policy: ConstructorPolicyV2,
    runner: ConstructorRunnerV2 | None,
) -> ConstructorReceiptV2:
    if not isinstance(request, ConstructorRequestV2):
        raise TypeError("request must be ConstructorRequestV2")
    if not isinstance(policy, ConstructorPolicyV2):
        raise TypeError("policy must be ConstructorPolicyV2")
    if any(
        item.content_safety is not ContentSafety.SANITIZED_DATA_ONLY
        for item in request.evidence_packet.documents
    ):
        raise ValueError("constructor accepts sanitized data-only evidence")
    if not policy.enabled:
        if runner is not None:
            raise ValueError("disabled constructor must not receive runner")
        return _receipt(request, ConstructorOutcomeV2.NO_CANDIDATE, "constructor_disabled")
    if runner is None:
        raise ValueError("enabled constructor requires runner")
    try:
        draft = runner(request)
    except ConstructorBoundaryFailure as exc:
        return _receipt(
            request,
            exc.outcome,
            exc.reason,
            usage=exc.usage,
            model_passes=1,
            latency_ms=exc.latency_ms,
            monetary_microunits=exc.monetary_microunits,
        )
    if not isinstance(draft, ConstructorDraftV2):
        raise TypeError("constructor runner must return ConstructorDraftV2")
    if policy.maximum_output_tokens is not None and draft.usage.output_tokens > policy.maximum_output_tokens:
        return _receipt(
            request,
            ConstructorOutcomeV2.INVALID,
            "constructor_output_cap_exceeded",
            usage=draft.usage,
            prompt_digest=draft.prompt_digest,
            model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    if draft.answer is None:
        return _receipt(
            request,
            ConstructorOutcomeV2.NO_CANDIDATE,
            draft.reason,
            usage=draft.usage,
            prompt_digest=draft.prompt_digest,
            model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    if len(draft.claims) > policy.maximum_claims:
        return _receipt(
            request,
            ConstructorOutcomeV2.INVALID,
            "constructor_claim_cap_exceeded",
            usage=draft.usage,
            prompt_digest=draft.prompt_digest,
            model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    spans = {item.span_id for item in request.evidence_packet.spans}
    computations = {item.receipt_id for item in request.evidence_packet.computations}
    verifications = {item.receipt_id for item in request.evidence_packet.verifications}
    for claim in draft.claims:
        if not (
            claim.evidence_span_ids
            or claim.computation_receipt_ids
            or claim.verification_receipt_ids
        ):
            reason = "constructed_claim_missing_binding"
        elif set(claim.evidence_span_ids) - spans:
            reason = "constructed_claim_unknown_span"
        elif set(claim.computation_receipt_ids) - computations:
            reason = "constructed_claim_unknown_computation"
        elif set(claim.verification_receipt_ids) - verifications:
            reason = "constructed_claim_unknown_verification"
        else:
            continue
        return _receipt(
            request,
            ConstructorOutcomeV2.INVALID,
            reason,
            usage=draft.usage,
            prompt_digest=draft.prompt_digest,
            model_passes=1,
            latency_ms=draft.latency_ms,
            monetary_microunits=draft.monetary_microunits,
        )
    candidate = CandidateAnswer(
        answer_id=f"constructed-{digest({'answer': draft.answer, 'packet': request.evidence_packet.packet_digest})[:16]}",
        answer=draft.answer,
        answer_kind=request.obligation.answer_kind,
        claims=draft.claims,
        origin=CandidateOrigin.EVIDENCE_CONSTRUCTED,
    )
    return _receipt(
        request,
        ConstructorOutcomeV2.CANDIDATE,
        draft.reason,
        candidate=candidate,
        usage=draft.usage,
        prompt_digest=draft.prompt_digest,
        model_passes=1,
        latency_ms=draft.latency_ms,
        monetary_microunits=draft.monetary_microunits,
    )
