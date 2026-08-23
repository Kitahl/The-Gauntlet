"""Execution helpers for FOIL vNext7 evidence-typed decisions.

This module reuses the vNext6 admission validator rather than creating a second
truth system. vNext7 adds three things:

1. verification targets are supplied by the controller, including synthetic
   targets for regime-level obligations;
2. cached evidence can be qualified without repeating an external acquisition;
3. authority is treated as a requirement relation, not a claim that an
   independent reviewer is intrinsically "stronger" than native evidence.

The validator still requires verifier/basis matching, non-staleness, freshness
for current claims, and a receipt-backed evidence record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from experiments.foil_vnext.runtime_policy import VerifierKind
from experiments.foil_vnext6.execution_contract import (
    VERIFIER_BASES,
    EvidenceBasis,
    EvidencePacket,
    EvidenceVerdict,
    OperatorOutcome,
    OperatorRequest,
    OutcomeStatus,
    OutcomeValidation,
    ProgressStatus,
    ToolEffect,
    build_request as build_v6_request,
    validate_outcome as validate_v6_outcome,
)
from experiments.foil_vnext6.runtime_policy import EvidenceAuthority

from .runtime_policy import EvidenceTypedDecision


class QualificationKind(str, Enum):
    CLAIM_NATIVE_CHECK = "claim_native_check"
    INDEPENDENT_CHECK = "independent_check"
    MECHANICAL_CHECK = "mechanical_check"


@dataclass(frozen=True)
class CachedEvidenceRecord:
    """A content-addressed verifier result derived from already-captured data.

    A raw ReAct observation is not enough. The cached material must first be
    checked against the exact task, target and verifier, yielding a verdict and
    a qualification receipt. That local qualification can avoid a second
    network or environment call while preserving FOIL's verification boundary.
    """

    evidence_id: str
    task_instance_id: str
    target_id: str
    verifier: VerifierKind
    basis: EvidenceBasis
    reference: str
    content_sha256: str
    verdict: EvidenceVerdict
    qualification: QualificationKind
    qualification_receipt: str
    stale: bool = False
    freshness_checked: bool = False

    def __post_init__(self) -> None:
        fields = (
            self.evidence_id,
            self.task_instance_id,
            self.target_id,
            self.reference,
            self.qualification_receipt,
        )
        if any(not field.strip() for field in fields):
            raise ValueError("cached evidence identifiers and receipts are required")
        digest = self.content_sha256.lower()
        if digest.startswith("sha256:"):
            digest = digest[7:]
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("content_sha256 must contain a 64-character SHA-256")


MECHANICAL_BASES = frozenset(
    {
        EvidenceBasis.EXECUTION,
        EvidenceBasis.CALCULATION,
        EvidenceBasis.SUPPLIED_CONTEXT,
        EvidenceBasis.OUTPUT_CONTRACT,
    }
)


AUTHORITY_ACCEPTANCE = {
    EvidenceAuthority.CLAIM_NATIVE: frozenset(
        {
            EvidenceAuthority.CLAIM_NATIVE,
            EvidenceAuthority.INDEPENDENT_REVIEW,
        }
    ),
    EvidenceAuthority.INDEPENDENT_REVIEW: frozenset(
        {EvidenceAuthority.INDEPENDENT_REVIEW}
    ),
}


def _record_authority(record: CachedEvidenceRecord) -> EvidenceAuthority:
    if record.qualification is QualificationKind.INDEPENDENT_CHECK:
        return EvidenceAuthority.INDEPENDENT_REVIEW
    return EvidenceAuthority.CLAIM_NATIVE


def qualify_cached_evidence(
    decision: EvidenceTypedDecision,
    record: CachedEvidenceRecord,
) -> EvidencePacket:
    """Convert a checked cached record into the parent evidence packet.

    This function does not infer or create a verdict. It only admits a verdict
    that an executor already produced through the named qualification step.
    """

    if not decision.reuse_cached_evidence:
        raise ValueError("decision did not authorize cached evidence reuse")
    if record.task_instance_id != decision.task_instance_id:
        raise ValueError("cached evidence belongs to a different task instance")

    target = next(
        (
            item
            for item in decision.verification_targets
            if item.target_id == record.target_id
        ),
        None,
    )
    if target is None:
        raise ValueError("cached evidence does not target this decision")
    if decision.required_verifier is None:
        raise ValueError("cached evidence requires a concrete verifier")
    if record.verifier is not decision.required_verifier:
        raise ValueError("cached evidence verifier does not match the decision")
    if record.basis not in VERIFIER_BASES[record.verifier]:
        raise ValueError("cached evidence basis does not match the verifier")
    if record.stale:
        raise ValueError("stale cached evidence cannot be admitted")
    if (
        record.qualification is QualificationKind.MECHANICAL_CHECK
        and record.basis not in MECHANICAL_BASES
    ):
        raise ValueError(
            "mechanical qualification cannot certify this evidence basis"
        )
    if (
        record.verifier is VerifierKind.CURRENT_SOURCE
        and not record.freshness_checked
    ):
        raise ValueError("current-source cached evidence requires freshness checking")

    authority = _record_authority(record)
    accepted = AUTHORITY_ACCEPTANCE.get(
        decision.strategy.minimum_evidence_authority,
        frozenset(),
    )
    if authority not in accepted:
        raise ValueError("cached evidence authority does not satisfy the decision")

    return EvidencePacket(
        evidence_id=record.evidence_id,
        claim_id=record.target_id,
        authority=authority,
        verifier=record.verifier,
        basis=record.basis,
        reference=record.reference,
        verdict=record.verdict,
        stale=record.stale,
        freshness_checked=record.freshness_checked,
    )


def build_request(
    decision: EvidenceTypedDecision,
    *,
    task_instance_id: str | None = None,
    tool_effect: ToolEffect = ToolEffect.NONE,
    idempotency_key: str | None = None,
    retry_attempt: int = 0,
    prior_postcondition_checked: bool = False,
) -> OperatorRequest:
    """Build a vNext6-compatible request from explicit vNext7 targets."""

    if task_instance_id is not None and task_instance_id != decision.task_instance_id:
        raise ValueError("request task_instance_id does not match the decision")

    target_ids = (
        tuple(target.target_id for target in decision.verification_targets)
        if decision.strategy.may_discharge_load_bearing_uncertainty
        else ()
    )
    return build_v6_request(
        decision.strategy,
        task_instance_id=decision.task_instance_id,
        target_claim_ids=target_ids,
        tool_effect=tool_effect,
        idempotency_key=idempotency_key,
        retry_attempt=retry_attempt,
        prior_postcondition_checked=prior_postcondition_checked,
    )


def _invalid_validation(
    parent: OutcomeValidation,
    errors: tuple[str, ...],
    outcome: OperatorOutcome,
) -> OutcomeValidation:
    progress = (
        ProgressStatus.BLOCKED
        if outcome.status is OutcomeStatus.BLOCKED
        else ProgressStatus.STALLED
    )
    return OutcomeValidation(
        valid=False,
        progress=progress,
        errors=parent.errors + errors,
        admitted_claim_resolutions=(),
        admitted_completed_verifiers=(),
    )


def validate_outcome(
    decision: EvidenceTypedDecision,
    request: OperatorRequest,
    outcome: OperatorOutcome,
) -> OutcomeValidation:
    """Apply vNext6 admission plus the vNext7 non-ordinal authority contract."""

    parent = validate_v6_outcome(decision.strategy, request, outcome)
    extra: list[str] = []

    if request.task_instance_id != decision.task_instance_id:
        extra.append("request_task_scope_mismatch")

    accepted = AUTHORITY_ACCEPTANCE.get(
        decision.strategy.minimum_evidence_authority,
        frozenset(),
    )
    if outcome.evidence and accepted:
        if any(packet.authority not in accepted for packet in outcome.evidence):
            extra.append("evidence_authority_requirement_mismatch")

    target_ids = {target.target_id for target in decision.verification_targets}
    if outcome.evidence and target_ids:
        if any(packet.claim_id not in target_ids for packet in outcome.evidence):
            extra.append("evidence_target_outside_decision")

    if extra:
        return _invalid_validation(parent, tuple(extra), outcome)
    return parent
