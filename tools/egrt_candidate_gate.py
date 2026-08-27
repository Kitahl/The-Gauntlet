"""Neutral candidate-binding and dual-verifier admission gate.

The gate can make a candidate ``COMMITTABLE`` but never applies it. Exact base,
candidate, scope, obligation-set, and environment bindings are required, and the
producer, structural verifier, and semantic verifier must be distinct identities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_sha256(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class AdmissionState(str, Enum):
    CERTIFICATE_REQUIRED = "CERTIFICATE_REQUIRED"
    SEMANTIC_VERIFICATION_REQUIRED = "SEMANTIC_VERIFICATION_REQUIRED"
    COMMITTABLE = "COMMITTABLE"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@runtime_checkable
class _CandidateLike(Protocol):
    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str


@dataclass(frozen=True)
class CandidateBinding:
    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    producer: str
    producer_version: str

    def __post_init__(self) -> None:
        _validate_candidate(
            self.candidate_id,
            self.base_digest,
            self.candidate_digest,
            self.scope_digest,
            self.obligation_set_digest,
            self.producer,
            self.producer_version,
        )


@dataclass(frozen=True)
class CandidateRepair:
    """Compatibility shape retained for the existing FOIL authority API."""

    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    repair_producer: str
    repair_producer_version: str

    def __post_init__(self) -> None:
        _validate_candidate(
            self.candidate_id,
            self.base_digest,
            self.candidate_digest,
            self.scope_digest,
            self.obligation_set_digest,
            self.repair_producer,
            self.repair_producer_version,
        )

    @property
    def producer(self) -> str:
        return self.repair_producer

    @property
    def producer_version(self) -> str:
        return self.repair_producer_version


def _validate_candidate(
    candidate_id: str,
    base_digest: str,
    candidate_digest: str,
    scope_digest: str,
    obligation_set_digest: str,
    producer: str,
    producer_version: str,
) -> None:
    for name, value in (
        ("candidate_id", candidate_id),
        ("producer", producer),
        ("producer_version", producer_version),
    ):
        _require_text(name, value)
    for name, value in (
        ("base_digest", base_digest),
        ("candidate_digest", candidate_digest),
        ("scope_digest", scope_digest),
        ("obligation_set_digest", obligation_set_digest),
    ):
        _require_sha256(name, value)
    if base_digest == candidate_digest:
        raise ValueError("candidate must differ from the base")


@dataclass(frozen=True)
class StructuralCertificate:
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    verifier_id: str
    verifier_version: str
    environment_digest: str
    status: CheckStatus

    def __post_init__(self) -> None:
        _validate_verification(self)


# Existing FOIL callers use this public name.
PatchCertificate = StructuralCertificate


@dataclass(frozen=True)
class SemanticVerification:
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    verifier_id: str
    verifier_version: str
    environment_digest: str
    status: CheckStatus

    def __post_init__(self) -> None:
        _validate_verification(self)


def _validate_verification(value: StructuralCertificate | SemanticVerification) -> None:
    if not isinstance(value.status, CheckStatus):
        raise TypeError("status must be CheckStatus")
    _require_text("verifier_id", value.verifier_id)
    _require_text("verifier_version", value.verifier_version)
    for name in (
        "base_digest",
        "candidate_digest",
        "scope_digest",
        "obligation_set_digest",
        "environment_digest",
    ):
        _require_sha256(name, getattr(value, name))


@dataclass(frozen=True)
class AdmissionDecision:
    state: AdmissionState
    reason: str
    candidate_id: str
    base_answer_preserved: bool = field(default=True, init=False)
    host_commit_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.state, AdmissionState):
            raise TypeError("state must be AdmissionState")
        _require_text("reason", self.reason)
        _require_text("candidate_id", self.candidate_id)

    @property
    def candidate_committable(self) -> bool:
        return self.state is AdmissionState.COMMITTABLE

    def trace(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "reason": self.reason,
            "candidate_id": self.candidate_id,
            "candidate_committable": self.candidate_committable,
            "base_answer_preserved": self.base_answer_preserved,
            "host_commit_required": self.host_commit_required,
            "execution_authorized": self.execution_authorized,
        }


def _producer(candidate: CandidateBinding | CandidateRepair) -> str:
    return candidate.producer


def _binding(candidate: _CandidateLike) -> tuple[str, str, str, str]:
    return (
        candidate.base_digest,
        candidate.candidate_digest,
        candidate.scope_digest,
        candidate.obligation_set_digest,
    )


def _verification_binding(
    verification: StructuralCertificate | SemanticVerification,
) -> tuple[str, str, str, str]:
    return (
        verification.base_digest,
        verification.candidate_digest,
        verification.scope_digest,
        verification.obligation_set_digest,
    )


def decide_admission(
    candidate: CandidateBinding | CandidateRepair,
    certificate: StructuralCertificate | None = None,
    semantic: SemanticVerification | None = None,
) -> AdmissionDecision:
    """Gate a bound candidate without granting execution or commit authority."""
    if not isinstance(candidate, (CandidateBinding, CandidateRepair)):
        raise TypeError("candidate must be CandidateBinding or CandidateRepair")
    if certificate is not None and not isinstance(certificate, StructuralCertificate):
        raise TypeError("certificate must be StructuralCertificate")
    if semantic is not None and not isinstance(semantic, SemanticVerification):
        raise TypeError("semantic must be SemanticVerification")

    def decision(state: AdmissionState, reason: str) -> AdmissionDecision:
        return AdmissionDecision(state=state, reason=reason, candidate_id=candidate.candidate_id)

    if certificate is None:
        return decision(AdmissionState.CERTIFICATE_REQUIRED, "certificate_missing")
    expected = _binding(candidate)
    if _verification_binding(certificate) != expected:
        return decision(AdmissionState.REJECTED, "certificate_binding_mismatch")
    producer = _producer(candidate)
    if certificate.verifier_id == producer:
        return decision(AdmissionState.REJECTED, "repair_producer_self_certified")
    if certificate.status is CheckStatus.FAIL:
        return decision(AdmissionState.REJECTED, "certificate_failed")
    if certificate.status is CheckStatus.UNKNOWN:
        return decision(AdmissionState.UNKNOWN, "certificate_unknown")

    if semantic is None:
        return decision(
            AdmissionState.SEMANTIC_VERIFICATION_REQUIRED,
            "structural_certificate_passed_semantics_missing",
        )
    if _verification_binding(semantic) != expected:
        return decision(AdmissionState.REJECTED, "semantic_binding_mismatch")
    if semantic.environment_digest != certificate.environment_digest:
        return decision(AdmissionState.REJECTED, "verification_environment_mismatch")
    if semantic.verifier_id == certificate.verifier_id:
        return decision(AdmissionState.REJECTED, "structural_verifier_reused_for_semantics")
    if semantic.verifier_id == producer:
        return decision(AdmissionState.REJECTED, "repair_producer_self_verified_semantics")
    if semantic.status is CheckStatus.FAIL:
        return decision(AdmissionState.REJECTED, "semantic_verification_failed")
    if semantic.status is CheckStatus.UNKNOWN:
        return decision(AdmissionState.UNKNOWN, "semantic_verification_unknown")
    return decision(
        AdmissionState.COMMITTABLE,
        "certificate_and_independent_semantic_verification_passed",
    )


__all__ = [
    "AdmissionDecision",
    "AdmissionState",
    "CandidateBinding",
    "CandidateRepair",
    "CheckStatus",
    "PatchCertificate",
    "SemanticVerification",
    "StructuralCertificate",
    "decide_admission",
]
