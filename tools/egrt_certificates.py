"""Claim-bound evidence certificates and safe adapters to legacy admission types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_claims import ImmutableBindings
from egrt_coverage import CoverageSummary
from egrt_types import digest
from egrt_verifiers import VerificationStatus, VerifierResult


class CertificateClass(str, Enum):
    STRUCTURAL_ONLY = "STRUCTURAL_ONLY"
    PREDICATE_SCOPED = "PREDICATE_SCOPED"
    REGRESSION_SCOPED = "REGRESSION_SCOPED"
    INDEPENDENT_SEMANTIC = "INDEPENDENT_SEMANTIC"
    INCOMPLETE_SCOPE = "INCOMPLETE_SCOPE"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a SHA-256 digest")


@dataclass(frozen=True)
class EvidenceCertificate:
    certificate_id: str
    certificate_class: CertificateClass
    claim_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    bindings: ImmutableBindings
    verifier: VerifierResult
    environment_digest: str
    evidence_digests: tuple[str, ...]
    coverage: CoverageSummary

    def __post_init__(self) -> None:
        for name in ("certificate_id", "claim_id"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.certificate_class, CertificateClass):
            raise TypeError("certificate_class must be CertificateClass")
        for name in ("base_digest", "candidate_digest", "scope_digest", "obligation_set_digest", "environment_digest"):
            _require_digest(name, getattr(self, name))
        if self.base_digest == self.candidate_digest:
            raise ValueError("certificate candidate must differ from base")
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if not isinstance(self.verifier, VerifierResult):
            raise TypeError("verifier must be VerifierResult")
        if not isinstance(self.coverage, CoverageSummary):
            raise TypeError("coverage must be CoverageSummary")
        if self.coverage.claim_id != self.claim_id:
            raise ValueError("coverage claim does not match certificate claim")
        if not isinstance(self.evidence_digests, tuple) or not self.evidence_digests:
            raise ValueError("evidence_digests must be a non-empty tuple")
        for evidence in self.evidence_digests:
            _require_digest("evidence_digest", evidence)
        if len(set(self.evidence_digests)) != len(self.evidence_digests):
            raise ValueError("certificate evidence digests must be unique")

    @property
    def certificate_digest(self) -> str:
        return digest(self)

    @property
    def status(self) -> VerificationStatus:
        if self.certificate_class is CertificateClass.INCOMPLETE_SCOPE:
            return VerificationStatus.UNKNOWN
        return self.verifier.status


def validate_certificate(certificate: EvidenceCertificate) -> tuple[bool, str]:
    if not isinstance(certificate, EvidenceCertificate):
        raise TypeError("certificate must be EvidenceCertificate")
    if certificate.certificate_class is CertificateClass.INCOMPLETE_SCOPE:
        return False, "incomplete_scope"
    if not certificate.coverage.complete:
        return False, "load_bearing_coverage_incomplete"
    if certificate.verifier.status is VerificationStatus.FAIL:
        return False, "verifier_failed"
    if certificate.verifier.status is VerificationStatus.UNKNOWN:
        return False, "verifier_unknown"
    return True, "certificate_valid_within_declared_scope"


def _legacy_status(certificate: EvidenceCertificate):
    from foil_authority import CheckStatus

    if certificate.status is VerificationStatus.PASS:
        return CheckStatus.PASS
    if certificate.status is VerificationStatus.FAIL:
        return CheckStatus.FAIL
    return CheckStatus.UNKNOWN


def to_patch_certificate(certificate: EvidenceCertificate):
    """Adapt only structural certificates; incomplete scope remains unknown."""

    from foil_authority import PatchCertificate

    if not isinstance(certificate, EvidenceCertificate):
        raise TypeError("certificate must be EvidenceCertificate")
    if certificate.certificate_class not in {
        CertificateClass.STRUCTURAL_ONLY,
        CertificateClass.PREDICATE_SCOPED,
        CertificateClass.REGRESSION_SCOPED,
    }:
        raise ValueError("certificate class cannot be adapted as structural verification")
    return PatchCertificate(
        base_digest=certificate.base_digest,
        candidate_digest=certificate.candidate_digest,
        scope_digest=certificate.scope_digest,
        obligation_set_digest=certificate.obligation_set_digest,
        verifier_id=certificate.verifier.verifier_id,
        verifier_version=certificate.verifier.verifier_version,
        environment_digest=certificate.environment_digest,
        status=_legacy_status(certificate),
    )


def to_semantic_verification(certificate: EvidenceCertificate):
    """Adapt only an independent semantic certificate; caller still proves independence."""

    from foil_authority import SemanticVerification

    if not isinstance(certificate, EvidenceCertificate):
        raise TypeError("certificate must be EvidenceCertificate")
    if certificate.certificate_class is not CertificateClass.INDEPENDENT_SEMANTIC:
        raise ValueError("certificate class cannot be adapted as semantic verification")
    return SemanticVerification(
        base_digest=certificate.base_digest,
        candidate_digest=certificate.candidate_digest,
        scope_digest=certificate.scope_digest,
        obligation_set_digest=certificate.obligation_set_digest,
        verifier_id=certificate.verifier.verifier_id,
        verifier_version=certificate.verifier.verifier_version,
        environment_digest=certificate.environment_digest,
        status=_legacy_status(certificate),
    )
