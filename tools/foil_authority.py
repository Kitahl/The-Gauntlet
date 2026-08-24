"""Shadow-only action-authority and candidate-admission contracts for FOIL.

This module is deliberately separate from :mod:`foil_policy`. The existing V2
policy decides task/complement routing; this module decides what a registered
evidence producer may *recommend* after it reports an outcome. It never calls a
tool, mutates an answer, commits a candidate, or changes a capability's write
permission.

Status: VALID_IMPLEMENTATION / BEHAVIORAL_EFFICACY_NOT_MEASURED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from egrt_types import EvidenceClass


class EvidenceSurface(str, Enum):
    PROMPT = "PROMPT"
    ANSWER = "ANSWER"
    PERSON = "PERSON"


class Applicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class SensorOutcome(str, Enum):
    CLEAR = "CLEAR"
    DEFECT = "DEFECT"
    UNKNOWN = "UNKNOWN"


class AuthorityCeiling(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    FLAG_ONLY = "FLAG_ONLY"
    ASK_OR_ABSTAIN = "ASK_OR_ABSTAIN"
    ESCALATION_RECOMMENDED = "ESCALATION_RECOMMENDED"
    REPAIR_PROPOSAL_ALLOWED = "REPAIR_PROPOSAL_ALLOWED"


class AuthorityAction(str, Enum):
    STAND_DOWN = "STAND_DOWN"
    RECORD_OBSERVATION = "RECORD_OBSERVATION"
    FLAG = "FLAG"
    ASK_OR_ABSTAIN = "ASK_OR_ABSTAIN"
    RECOMMEND_ESCALATION = "RECOMMEND_ESCALATION"
    PROPOSE_REPAIR_SHADOW = "PROPOSE_REPAIR_SHADOW"


_SURFACE_CEILINGS: dict[EvidenceSurface, frozenset[AuthorityCeiling]] = {
    EvidenceSurface.PROMPT: frozenset(
        {
            AuthorityCeiling.OBSERVE_ONLY,
            AuthorityCeiling.FLAG_ONLY,
            AuthorityCeiling.ASK_OR_ABSTAIN,
        }
    ),
    EvidenceSurface.ANSWER: frozenset(AuthorityCeiling),
    EvidenceSurface.PERSON: frozenset(
        {
            AuthorityCeiling.OBSERVE_ONLY,
            AuthorityCeiling.FLAG_ONLY,
            AuthorityCeiling.ASK_OR_ABSTAIN,
        }
    ),
}


def _require_instance(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be {expected.__name__}")


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool")


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")


@dataclass(frozen=True)
class SensorRegistration:
    """Trusted registration; a sensor report cannot alter these fields."""

    sensor_id: str
    evidence_class: EvidenceClass
    surface: EvidenceSurface
    authority_ceiling: AuthorityCeiling
    claim_scope: str
    producer: str
    version: str

    def __post_init__(self) -> None:
        _require_instance("evidence_class", self.evidence_class, EvidenceClass)
        _require_instance("surface", self.surface, EvidenceSurface)
        _require_instance("authority_ceiling", self.authority_ceiling, AuthorityCeiling)
        for name in ("sensor_id", "claim_scope", "producer", "version"):
            _require_text(name, getattr(self, name))
        if self.authority_ceiling not in _SURFACE_CEILINGS[self.surface]:
            raise ValueError(
                f"{self.surface.value} evidence cannot have "
                f"{self.authority_ceiling.value} authority"
            )


@dataclass(frozen=True)
class SensorReport:
    """One sensor result. Authority is intentionally absent from this type."""

    sensor_id: str
    input_digest: str
    applicability: Applicability
    outcome: SensorOutcome
    target_scope: str

    def __post_init__(self) -> None:
        _require_instance("applicability", self.applicability, Applicability)
        _require_instance("outcome", self.outcome, SensorOutcome)
        _require_text("sensor_id", self.sensor_id)
        _require_sha256("input_digest", self.input_digest)
        _require_text("target_scope", self.target_scope)


@dataclass(frozen=True)
class AuthorityContext:
    """Explicit prerequisites; no hidden thresholds or inferred owner consent."""

    repair_proposals_enabled: bool = False
    calibration_current: bool = False
    owner_risk_allows_repair: bool = False

    def __post_init__(self) -> None:
        for name in (
            "repair_proposals_enabled",
            "calibration_current",
            "owner_risk_allows_repair",
        ):
            _require_bool(name, getattr(self, name))


@dataclass(frozen=True)
class AuthorityDecision:
    action: AuthorityAction
    reason: str
    sensor_id: str
    evidence_class: EvidenceClass
    authority_ceiling: AuthorityCeiling
    shadow_mode: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    base_answer_preserved: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        _require_instance("action", self.action, AuthorityAction)
        _require_instance("evidence_class", self.evidence_class, EvidenceClass)
        _require_instance("authority_ceiling", self.authority_ceiling, AuthorityCeiling)
        _require_text("reason", self.reason)
        _require_text("sensor_id", self.sensor_id)

    def trace(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "sensor_id": self.sensor_id,
            "evidence_class": self.evidence_class.value,
            "authority_ceiling": self.authority_ceiling.value,
            "shadow_mode": self.shadow_mode,
            "execution_authorized": self.execution_authorized,
            "base_answer_preserved": self.base_answer_preserved,
        }


def decide_authority(
    registration: SensorRegistration,
    report: SensorReport,
    context: AuthorityContext = AuthorityContext(),
) -> AuthorityDecision:
    """Return exactly one shadow action without granting execution authority."""

    _require_instance("registration", registration, SensorRegistration)
    _require_instance("report", report, SensorReport)
    _require_instance("context", context, AuthorityContext)

    def decision(action: AuthorityAction, reason: str) -> AuthorityDecision:
        return AuthorityDecision(
            action=action,
            reason=reason,
            sensor_id=registration.sensor_id,
            evidence_class=registration.evidence_class,
            authority_ceiling=registration.authority_ceiling,
        )

    if report.sensor_id != registration.sensor_id:
        return decision(AuthorityAction.STAND_DOWN, "sensor_registration_mismatch")
    if report.target_scope != registration.claim_scope:
        return decision(AuthorityAction.STAND_DOWN, "target_scope_mismatch")
    if report.applicability is Applicability.UNKNOWN:
        return decision(AuthorityAction.STAND_DOWN, "applicability_unknown")
    if report.applicability is Applicability.NOT_APPLICABLE:
        return decision(AuthorityAction.STAND_DOWN, "sensor_not_applicable")
    if report.outcome is SensorOutcome.UNKNOWN:
        return decision(AuthorityAction.STAND_DOWN, "sensor_outcome_unknown")
    if report.outcome is SensorOutcome.CLEAR:
        return decision(AuthorityAction.STAND_DOWN, "no_defect_reported")

    ceiling = registration.authority_ceiling
    if ceiling is AuthorityCeiling.OBSERVE_ONLY:
        return decision(AuthorityAction.RECORD_OBSERVATION, "observe_only_ceiling")
    if ceiling is AuthorityCeiling.FLAG_ONLY:
        return decision(AuthorityAction.FLAG, "flag_only_ceiling")
    if ceiling is AuthorityCeiling.ASK_OR_ABSTAIN:
        return decision(AuthorityAction.ASK_OR_ABSTAIN, "ask_or_abstain_ceiling")
    if ceiling is AuthorityCeiling.ESCALATION_RECOMMENDED:
        return decision(
            AuthorityAction.RECOMMEND_ESCALATION,
            "escalation_recommendation_only",
        )

    missing: list[str] = []
    if not context.repair_proposals_enabled:
        missing.append("repair_proposals_disabled")
    if not context.calibration_current:
        missing.append("calibration_not_current")
    if not context.owner_risk_allows_repair:
        missing.append("owner_risk_not_authorized")
    if missing:
        return decision(AuthorityAction.STAND_DOWN, "+".join(missing))
    return decision(
        AuthorityAction.PROPOSE_REPAIR_SHADOW,
        "registered_answer_sensor_met_explicit_proposal_prerequisites",
    )


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


@dataclass(frozen=True)
class CandidateRepair:
    candidate_id: str
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    repair_producer: str
    repair_producer_version: str

    def __post_init__(self) -> None:
        _require_text("candidate_id", self.candidate_id)
        _require_text("repair_producer", self.repair_producer)
        _require_text("repair_producer_version", self.repair_producer_version)
        for name in (
            "base_digest",
            "candidate_digest",
            "scope_digest",
            "obligation_set_digest",
        ):
            _require_sha256(name, getattr(self, name))
        if self.base_digest == self.candidate_digest:
            raise ValueError("candidate repair must differ from the base answer")


@dataclass(frozen=True)
class PatchCertificate:
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    verifier_id: str
    verifier_version: str
    provenance_group: str
    environment_digest: str
    status: CheckStatus

    def __post_init__(self) -> None:
        _require_instance("status", self.status, CheckStatus)
        _require_text("verifier_id", self.verifier_id)
        _require_text("verifier_version", self.verifier_version)
        _require_text("provenance_group", self.provenance_group)
        for name in (
            "base_digest",
            "candidate_digest",
            "scope_digest",
            "obligation_set_digest",
            "environment_digest",
        ):
            _require_sha256(name, getattr(self, name))


@dataclass(frozen=True)
class SemanticVerification:
    base_digest: str
    candidate_digest: str
    scope_digest: str
    obligation_set_digest: str
    verifier_id: str
    verifier_version: str
    provenance_group: str
    environment_digest: str
    status: CheckStatus

    def __post_init__(self) -> None:
        _require_instance("status", self.status, CheckStatus)
        _require_text("verifier_id", self.verifier_id)
        _require_text("verifier_version", self.verifier_version)
        _require_text("provenance_group", self.provenance_group)
        for name in (
            "base_digest",
            "candidate_digest",
            "scope_digest",
            "obligation_set_digest",
            "environment_digest",
        ):
            _require_sha256(name, getattr(self, name))


@dataclass(frozen=True)
class AdmissionDecision:
    state: AdmissionState
    reason: str
    candidate_id: str
    base_answer_preserved: bool = field(default=True, init=False)
    host_commit_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _require_instance("state", self.state, AdmissionState)
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


def decide_admission(
    candidate: CandidateRepair,
    certificate: PatchCertificate | None = None,
    semantic: SemanticVerification | None = None,
) -> AdmissionDecision:
    """Gate a candidate without applying it; COMMITTABLE still requires a host."""

    _require_instance("candidate", candidate, CandidateRepair)
    if certificate is not None:
        _require_instance("certificate", certificate, PatchCertificate)
    if semantic is not None:
        _require_instance("semantic", semantic, SemanticVerification)

    def decision(state: AdmissionState, reason: str) -> AdmissionDecision:
        return AdmissionDecision(
            state=state,
            reason=reason,
            candidate_id=candidate.candidate_id,
        )

    if certificate is None:
        return decision(AdmissionState.CERTIFICATE_REQUIRED, "certificate_missing")
    expected = (
        candidate.base_digest,
        candidate.candidate_digest,
        candidate.scope_digest,
        candidate.obligation_set_digest,
    )
    certificate_binding = (
        certificate.base_digest,
        certificate.candidate_digest,
        certificate.scope_digest,
        certificate.obligation_set_digest,
    )
    if certificate_binding != expected:
        return decision(AdmissionState.REJECTED, "certificate_binding_mismatch")
    if certificate.verifier_id == candidate.repair_producer:
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
    semantic_binding = (
        semantic.base_digest,
        semantic.candidate_digest,
        semantic.scope_digest,
        semantic.obligation_set_digest,
    )
    if semantic_binding != expected:
        return decision(AdmissionState.REJECTED, "semantic_binding_mismatch")
    if semantic.verifier_id == certificate.verifier_id:
        return decision(
            AdmissionState.REJECTED,
            "structural_verifier_reused_for_semantics",
        )
    if semantic.provenance_group == certificate.provenance_group:
        return decision(
            AdmissionState.REJECTED,
            "structural_semantic_provenance_overlap",
        )
    if semantic.verifier_id == candidate.repair_producer:
        return decision(AdmissionState.REJECTED, "repair_producer_self_verified_semantics")
    if semantic.status is CheckStatus.FAIL:
        return decision(AdmissionState.REJECTED, "semantic_verification_failed")
    if semantic.status is CheckStatus.UNKNOWN:
        return decision(AdmissionState.UNKNOWN, "semantic_verification_unknown")
    return decision(
        AdmissionState.COMMITTABLE,
        "certificate_and_independent_semantic_verification_passed",
    )
