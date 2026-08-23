"""Typed execution and evidence-admission contract for FOIL vNext6.

The strategy controller selects one operator. This module defines the public
request/result boundary for executing that operator and deciding whether its
output changed candidate state, added usable evidence, completed a verifier, or
resolved a load-bearing claim.

It stores no private reasoning or chain-of-thought.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from experiments.foil_vnext.runtime_policy import VerifierKind

from .runtime_policy import (
    EvidenceAuthority,
    StrategyDecision,
    StrategyOperator,
)


class ToolEffect(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    SIDE_EFFECTING = "side_effecting"


class OutcomeStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ProgressStatus(str, Enum):
    PROGRESSED = "progressed"
    STALLED = "stalled"
    BLOCKED = "blocked"


class EvidenceBasis(str, Enum):
    PRIMARY_SOURCE = "primary_source"
    OFFICIAL_SOURCE = "official_source"
    OFFICIAL_GUIDELINE = "official_guideline"
    EXECUTION = "execution"
    CALCULATION = "calculation"
    PROOF_OR_COUNTEREXAMPLE = "proof_or_counterexample"
    SUPPLIED_CONTEXT = "supplied_context"
    OUTPUT_CONTRACT = "output_contract"


AUTHORITY_RANK: Mapping[EvidenceAuthority, int] = {
    EvidenceAuthority.NONE: 0,
    EvidenceAuthority.INTERNAL_HEURISTIC: 1,
    EvidenceAuthority.EXTERNAL_OBSERVATION: 2,
    EvidenceAuthority.CLAIM_NATIVE: 3,
    EvidenceAuthority.INDEPENDENT_REVIEW: 4,
}


VERIFIER_BASES: Mapping[VerifierKind, frozenset[EvidenceBasis]] = {
    VerifierKind.SOURCE_EVIDENCE: frozenset(
        {
            EvidenceBasis.PRIMARY_SOURCE,
            EvidenceBasis.OFFICIAL_SOURCE,
            EvidenceBasis.OFFICIAL_GUIDELINE,
        }
    ),
    VerifierKind.CURRENT_SOURCE: frozenset(
        {
            EvidenceBasis.OFFICIAL_SOURCE,
            EvidenceBasis.OFFICIAL_GUIDELINE,
        }
    ),
    VerifierKind.EXECUTION_TEST: frozenset({EvidenceBasis.EXECUTION}),
    VerifierKind.EXACT_CALCULATION: frozenset({EvidenceBasis.CALCULATION}),
    VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY: frozenset(
        {EvidenceBasis.SUPPLIED_CONTEXT}
    ),
    VerifierKind.CONTRADICTION_COUNTEREXAMPLE: frozenset(
        {EvidenceBasis.PROOF_OR_COUNTEREXAMPLE}
    ),
    VerifierKind.OUTPUT_CONTRACT: frozenset({EvidenceBasis.OUTPUT_CONTRACT}),
}


NON_VERIFYING_OPERATORS = frozenset(
    {
        StrategyOperator.DIRECT,
        StrategyOperator.DECOMPOSE,
        StrategyOperator.REACT,
        StrategyOperator.BOUNDED_CHALLENGER_SEARCH,
        StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION,
        StrategyOperator.MASTERMIND_CAUSAL_AUDIT,
        StrategyOperator.STOP,
        StrategyOperator.BLOCKED,
    }
)


@dataclass(frozen=True)
class OperatorRequest:
    controller_version: str
    operator: StrategyOperator
    reason_code: str
    required_verifier: VerifierKind | None
    minimum_evidence_authority: EvidenceAuthority
    target_claim_ids: tuple[str, ...] = ()
    tool_effect: ToolEffect = ToolEffect.NONE
    idempotency_key: str | None = None
    retry_attempt: int = 0
    prior_postcondition_checked: bool = False

    def __post_init__(self) -> None:
        if not self.controller_version:
            raise ValueError("controller_version is required")
        if not self.reason_code:
            raise ValueError("reason_code is required")
        if len(set(self.target_claim_ids)) != len(self.target_claim_ids):
            raise ValueError("target_claim_ids must be unique")
        if any(not claim_id.strip() for claim_id in self.target_claim_ids):
            raise ValueError("target claim IDs must be non-empty")
        if self.retry_attempt < 0:
            raise ValueError("retry_attempt must be non-negative")
        if self.tool_effect is ToolEffect.SIDE_EFFECTING:
            if not self.idempotency_key:
                raise ValueError("side-effecting tools require an idempotency key")
            if self.retry_attempt and not self.prior_postcondition_checked:
                raise ValueError(
                    "side-effecting retries require verify-before-retry evidence"
                )
        elif self.idempotency_key is not None:
            raise ValueError("idempotency keys are only valid for side effects")

    def trace(self) -> dict[str, object]:
        return {
            "trace_type": "operator_request",
            "controller_version": self.controller_version,
            "operator": self.operator.value,
            "reason_code": self.reason_code,
            "required_verifier": (
                self.required_verifier.value if self.required_verifier else None
            ),
            "minimum_evidence_authority": (
                self.minimum_evidence_authority.value
            ),
            "target_claim_count": len(self.target_claim_ids),
            "tool_effect": self.tool_effect.value,
            "retry_attempt": self.retry_attempt,
            "prior_postcondition_checked": self.prior_postcondition_checked,
        }


@dataclass(frozen=True)
class EvidencePacket:
    evidence_id: str
    claim_id: str
    authority: EvidenceAuthority
    verifier: VerifierKind
    basis: EvidenceBasis
    reference: str
    entails_claim: bool
    stale: bool = False
    freshness_checked: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")
        if not self.claim_id.strip():
            raise ValueError("claim_id is required")
        if not self.reference.strip():
            raise ValueError("evidence reference is required")
        if self.authority not in {
            EvidenceAuthority.CLAIM_NATIVE,
            EvidenceAuthority.INDEPENDENT_REVIEW,
        }:
            raise ValueError(
                "evidence packets require claim-native or independent authority"
            )


@dataclass(frozen=True)
class OperatorOutcome:
    operator: StrategyOperator
    status: OutcomeStatus
    candidate_created: bool = False
    candidate_revised: bool = False
    evidence: tuple[EvidencePacket, ...] = ()
    completed_verifiers: frozenset[VerifierKind] = frozenset()
    resolved_claim_ids: tuple[str, ...] = ()
    defect_id: str | None = None
    postcondition_verified: bool = False
    observed_state_fingerprint: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if len(set(self.resolved_claim_ids)) != len(self.resolved_claim_ids):
            raise ValueError("resolved_claim_ids must be unique")
        if any(not claim_id.strip() for claim_id in self.resolved_claim_ids):
            raise ValueError("resolved claim IDs must be non-empty")
        if self.defect_id is not None and not self.defect_id.strip():
            raise ValueError("defect_id cannot be blank")
        if self.status is OutcomeStatus.COMPLETED and self.error_code:
            raise ValueError("completed outcomes cannot carry an error code")

    def trace(self) -> dict[str, object]:
        return {
            "trace_type": "operator_outcome",
            "operator": self.operator.value,
            "status": self.status.value,
            "candidate_created": self.candidate_created,
            "candidate_revised": self.candidate_revised,
            "evidence_count": len(self.evidence),
            "completed_verifier_count": len(self.completed_verifiers),
            "resolved_claim_count": len(self.resolved_claim_ids),
            "defect_localized": self.defect_id is not None,
            "postcondition_verified": self.postcondition_verified,
            "state_fingerprint_present": (
                self.observed_state_fingerprint is not None
            ),
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class OutcomeValidation:
    valid: bool
    progress: ProgressStatus
    errors: tuple[str, ...]
    admitted_resolved_claim_ids: tuple[str, ...]
    admitted_completed_verifiers: tuple[VerifierKind, ...]

    def trace(self) -> dict[str, object]:
        return {
            "trace_type": "outcome_validation",
            "valid": self.valid,
            "progress": self.progress.value,
            "error_count": len(self.errors),
            "admitted_resolved_claim_count": len(
                self.admitted_resolved_claim_ids
            ),
            "admitted_completed_verifier_count": len(
                self.admitted_completed_verifiers
            ),
        }


def build_request(
    decision: StrategyDecision,
    *,
    target_claim_ids: tuple[str, ...] = (),
    tool_effect: ToolEffect = ToolEffect.NONE,
    idempotency_key: str | None = None,
    retry_attempt: int = 0,
    prior_postcondition_checked: bool = False,
) -> OperatorRequest:
    if decision.may_discharge_load_bearing_uncertainty and not target_claim_ids:
        raise ValueError(
            "evidence-bearing operators require explicit target claim IDs"
        )
    return OperatorRequest(
        controller_version=decision.controller_version,
        operator=decision.operator,
        reason_code=decision.reason_code,
        required_verifier=decision.required_verifier,
        minimum_evidence_authority=decision.minimum_evidence_authority,
        target_claim_ids=target_claim_ids,
        tool_effect=tool_effect,
        idempotency_key=idempotency_key,
        retry_attempt=retry_attempt,
        prior_postcondition_checked=prior_postcondition_checked,
    )


def _progress(outcome: OperatorOutcome) -> ProgressStatus:
    if outcome.status is OutcomeStatus.BLOCKED:
        return ProgressStatus.BLOCKED
    if outcome.status is OutcomeStatus.FAILED:
        return ProgressStatus.STALLED
    if (
        outcome.candidate_created
        or outcome.candidate_revised
        or outcome.evidence
        or outcome.completed_verifiers
        or outcome.resolved_claim_ids
        or outcome.defect_id
        or outcome.postcondition_verified
    ):
        return ProgressStatus.PROGRESSED
    return ProgressStatus.STALLED


def _packet_supports(
    packet: EvidencePacket,
    *,
    claim_id: str,
    required_verifier: VerifierKind,
    minimum_authority: EvidenceAuthority,
) -> bool:
    if packet.claim_id != claim_id:
        return False
    if packet.verifier is not required_verifier:
        return False
    if packet.basis not in VERIFIER_BASES[required_verifier]:
        return False
    if AUTHORITY_RANK[packet.authority] < AUTHORITY_RANK[minimum_authority]:
        return False
    if not packet.entails_claim or packet.stale:
        return False
    if (
        required_verifier is VerifierKind.CURRENT_SOURCE
        and not packet.freshness_checked
    ):
        return False
    return True


def validate_outcome(
    decision: StrategyDecision,
    request: OperatorRequest,
    outcome: OperatorOutcome,
) -> OutcomeValidation:
    errors: list[str] = []

    if request.controller_version != decision.controller_version:
        errors.append("controller_version_mismatch")
    if request.operator is not decision.operator:
        errors.append("request_operator_mismatch")
    if outcome.operator is not request.operator:
        errors.append("outcome_operator_mismatch")
    if request.required_verifier is not decision.required_verifier:
        errors.append("required_verifier_mismatch")
    if (
        request.minimum_evidence_authority
        is not decision.minimum_evidence_authority
    ):
        errors.append("minimum_authority_mismatch")

    if (
        request.tool_effect is ToolEffect.SIDE_EFFECTING
        and outcome.status is OutcomeStatus.COMPLETED
        and not outcome.postcondition_verified
    ):
        errors.append("side_effect_postcondition_unverified")

    if outcome.operator in NON_VERIFYING_OPERATORS:
        if outcome.resolved_claim_ids:
            errors.append("non_verifying_operator_resolved_claim")
        if outcome.completed_verifiers:
            errors.append("non_verifying_operator_completed_verifier")

    if outcome.operator is StrategyOperator.REACT:
        if any(
            packet.authority
            in {
                EvidenceAuthority.CLAIM_NATIVE,
                EvidenceAuthority.INDEPENDENT_REVIEW,
            }
            for packet in outcome.evidence
        ):
            errors.append("react_discovery_claimed_verifier_authority")

    if (
        outcome.operator is StrategyOperator.MASTERMIND_CAUSAL_AUDIT
        and outcome.status is OutcomeStatus.COMPLETED
        and outcome.defect_id is None
    ):
        errors.append("mastermind_completed_without_distinct_defect")

    if (
        outcome.operator is StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION
        and outcome.status is OutcomeStatus.COMPLETED
        and not (outcome.candidate_created or outcome.candidate_revised)
    ):
        errors.append("reflection_completed_without_candidate_change")

    if outcome.operator in {StrategyOperator.STOP, StrategyOperator.BLOCKED}:
        if (
            outcome.candidate_created
            or outcome.candidate_revised
            or outcome.evidence
            or outcome.completed_verifiers
            or outcome.resolved_claim_ids
            or outcome.defect_id
            or outcome.postcondition_verified
        ):
            errors.append("terminal_operator_reported_state_change")

    admitted_claims: list[str] = []
    admitted_verifiers: list[VerifierKind] = []

    if outcome.resolved_claim_ids:
        if not decision.may_discharge_load_bearing_uncertainty:
            errors.append("decision_did_not_authorize_resolution")
        if decision.required_verifier is None:
            errors.append("resolution_without_required_verifier")
        else:
            for claim_id in outcome.resolved_claim_ids:
                if claim_id not in request.target_claim_ids:
                    errors.append(f"untargeted_claim_resolution:{claim_id}")
                    continue
                supporting = any(
                    _packet_supports(
                        packet,
                        claim_id=claim_id,
                        required_verifier=decision.required_verifier,
                        minimum_authority=(
                            decision.minimum_evidence_authority
                        ),
                    )
                    for packet in outcome.evidence
                )
                if not supporting:
                    errors.append(f"unsupported_claim_resolution:{claim_id}")
                else:
                    admitted_claims.append(claim_id)

    if outcome.completed_verifiers:
        if decision.required_verifier is None:
            errors.append("verifier_completion_without_requirement")
        else:
            unexpected = set(outcome.completed_verifiers) - {
                decision.required_verifier
            }
            if unexpected:
                errors.append("unexpected_completed_verifier")
            if decision.required_verifier in outcome.completed_verifiers:
                relevant_packets = [
                    packet
                    for packet in outcome.evidence
                    if packet.verifier is decision.required_verifier
                    and packet.basis
                    in VERIFIER_BASES[decision.required_verifier]
                    and AUTHORITY_RANK[packet.authority]
                    >= AUTHORITY_RANK[
                        decision.minimum_evidence_authority
                    ]
                    and not packet.stale
                    and (
                        decision.required_verifier
                        is not VerifierKind.CURRENT_SOURCE
                        or packet.freshness_checked
                    )
                ]
                if not relevant_packets:
                    errors.append("completed_verifier_without_admissible_evidence")
                else:
                    admitted_verifiers.append(decision.required_verifier)

    return OutcomeValidation(
        valid=not errors,
        progress=_progress(outcome),
        errors=tuple(errors),
        admitted_resolved_claim_ids=tuple(admitted_claims),
        admitted_completed_verifiers=tuple(admitted_verifiers),
    )
