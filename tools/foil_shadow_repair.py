"""Pure admission seam for externally produced shadow repair candidates.

This module accepts only a digest and locator supplied by an external producer.
It neither creates candidate content nor changes A0.  Its sole result is an
authority admission decision that remains subject to an explicit host action.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from egrt_certificates import (
    CertificateClass,
    EvidenceCertificate,
    to_patch_certificate,
    to_semantic_verification,
    validate_certificate,
)
from egrt_types import ArtifactRef, digest
from foil_authority import (
    AdmissionDecision,
    AuthorityAction,
    AuthorityDecision,
    CandidateRepair,
    CheckStatus,
    PatchCertificate,
    SemanticVerification,
    decide_admission,
)


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class ExternalRepairCandidate:
    """A content-addressed candidate reference supplied outside this module."""

    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    producer_id: str
    producer_version: str
    artifact: ArtifactRef

    def __post_init__(self) -> None:
        for name in ("candidate_id", "producer_id", "producer_version"):
            _require_text(name, getattr(self, name))
        for name in ("base_digest", "candidate_digest", "scope_digest", "obligation_set_digest"):
            _require_digest(name, getattr(self, name))
        if self.base_digest == self.candidate_digest:
            raise ValueError("candidate digest must differ from A0")
        if not isinstance(self.artifact, ArtifactRef):
            raise TypeError("artifact must be ArtifactRef")
        _require_text("artifact.locator", self.artifact.locator)
        _require_digest("artifact.sha256", self.artifact.sha256)


@dataclass(frozen=True)
class ShadowRepairProposal:
    """A proposal is a reference only; it contains no candidate payload."""

    candidate: CandidateRepair
    artifact: ArtifactRef
    proposal_digest: str
    base_answer_preserved: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CandidateRepair):
            raise TypeError("candidate must be CandidateRepair")
        if not isinstance(self.artifact, ArtifactRef):
            raise TypeError("artifact must be ArtifactRef")
        _require_text("artifact.locator", self.artifact.locator)
        _require_digest("artifact.sha256", self.artifact.sha256)
        _require_digest("proposal_digest", self.proposal_digest)
        if self.artifact.sha256 != self.candidate.candidate_digest:
            raise ValueError("artifact digest must bind the candidate digest")
        if self.base_answer_preserved is not True or self.execution_authorized is not False:
            raise ValueError("shadow proposals preserve A0 and grant no execution authority")


def propose_shadow_repair(
    authority: AuthorityDecision, external: ExternalRepairCandidate
) -> ShadowRepairProposal:
    """Create a reference-only proposal after the exact shadow authority action."""

    if not isinstance(authority, AuthorityDecision):
        raise TypeError("authority must be AuthorityDecision")
    if authority.action is not AuthorityAction.PROPOSE_REPAIR_SHADOW:
        raise ValueError("shadow repair proposal requires PROPOSE_REPAIR_SHADOW")
    if not isinstance(external, ExternalRepairCandidate):
        raise TypeError("external must be ExternalRepairCandidate")
    candidate = CandidateRepair(
        candidate_id=external.candidate_id,
        base_digest=external.base_digest,
        candidate_digest=external.candidate_digest,
        scope_digest=external.scope_digest,
        obligation_set_digest=external.obligation_set_digest,
        repair_producer=external.producer_id,
        repair_producer_version=external.producer_version,
    )
    proposal_digest = digest(
        {
            "candidate_id": candidate.candidate_id,
            "base_digest": candidate.base_digest,
            "candidate_digest": candidate.candidate_digest,
            "scope_digest": candidate.scope_digest,
            "obligation_set_digest": candidate.obligation_set_digest,
            "artifact_locator": external.artifact.locator,
            "artifact_sha256": external.artifact.sha256,
        }
    )
    return ShadowRepairProposal(candidate, external.artifact, proposal_digest)


def _structural_certificate(
    certificate: EvidenceCertificate | None,
) -> PatchCertificate | None:
    if certificate is None:
        return None
    if not isinstance(certificate, EvidenceCertificate):
        raise TypeError("structural certificate must be EvidenceCertificate")
    if certificate.certificate_class not in {
        CertificateClass.STRUCTURAL_ONLY,
        CertificateClass.PREDICATE_SCOPED,
        CertificateClass.REGRESSION_SCOPED,
    }:
        raise ValueError("structural certificate must have a structural or predicate class")
    adapted = to_patch_certificate(certificate)
    valid, _ = validate_certificate(certificate)
    return adapted if valid else replace(adapted, status=CheckStatus.UNKNOWN)


def _semantic_certificate(
    certificate: EvidenceCertificate | None,
) -> SemanticVerification | None:
    if certificate is None:
        return None
    if not isinstance(certificate, EvidenceCertificate):
        raise TypeError("semantic certificate must be EvidenceCertificate")
    if certificate.certificate_class is not CertificateClass.INDEPENDENT_SEMANTIC:
        raise ValueError("semantic certificate must be INDEPENDENT_SEMANTIC")
    adapted = to_semantic_verification(certificate)
    valid, _ = validate_certificate(certificate)
    return adapted if valid else replace(adapted, status=CheckStatus.UNKNOWN)


@dataclass(frozen=True)
class ShadowRepairAdmission:
    """Receipt-safe result of certificate checks delegated to FOIL admission."""

    proposal: ShadowRepairProposal
    structural_certificate_digest: str | None
    semantic_certificate_digest: str | None
    decision: AdmissionDecision
    base_answer_preserved: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, ShadowRepairProposal):
            raise TypeError("proposal must be ShadowRepairProposal")
        for name in ("structural_certificate_digest", "semantic_certificate_digest"):
            value = getattr(self, name)
            if value is not None:
                _require_digest(name, value)
        if not isinstance(self.decision, AdmissionDecision):
            raise TypeError("decision must be AdmissionDecision")
        if self.decision.candidate_id != self.proposal.candidate.candidate_id:
            raise ValueError("admission decision must bind the proposed candidate")
        if self.base_answer_preserved is not True or self.execution_authorized is not False:
            raise ValueError("shadow admission preserves A0 and grants no execution authority")


def admit_shadow_repair(
    proposal: ShadowRepairProposal,
    *,
    structural_certificate: EvidenceCertificate | None = None,
    semantic_certificate: EvidenceCertificate | None = None,
) -> ShadowRepairAdmission:
    """Validate separate certificates and delegate the binding checks to FOIL."""

    if not isinstance(proposal, ShadowRepairProposal):
        raise TypeError("proposal must be ShadowRepairProposal")
    structural = _structural_certificate(structural_certificate)
    semantic = _semantic_certificate(semantic_certificate)
    decision = decide_admission(proposal.candidate, structural, semantic)
    return ShadowRepairAdmission(
        proposal=proposal,
        structural_certificate_digest=(
            structural_certificate.certificate_digest
            if structural_certificate is not None
            else None
        ),
        semantic_certificate_digest=(
            semantic_certificate.certificate_digest if semantic_certificate is not None else None
        ),
        decision=decision,
    )
