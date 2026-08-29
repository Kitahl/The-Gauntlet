"""Shadow-only action-authority contracts for FOIL.

The generic candidate-admission gate now lives in :mod:`egrt_candidate_gate`.
Compatibility imports below preserve the existing FOIL public API. This module never
calls a tool, mutates an answer, commits a candidate, or changes write permission.

Status: VALID_IMPLEMENTATION / BEHAVIORAL_EFFICACY_NOT_MEASURED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from egrt_candidate_gate import (
    AdmissionDecision,
    AdmissionState,
    CandidateBinding,
    CandidateRepair,
    CheckStatus,
    PatchCertificate,
    SemanticVerification,
    StructuralCertificate,
    decide_admission,
)
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
    EvidenceSurface.PROMPT: frozenset({
        AuthorityCeiling.OBSERVE_ONLY,
        AuthorityCeiling.FLAG_ONLY,
        AuthorityCeiling.ASK_OR_ABSTAIN,
    }),
    EvidenceSurface.ANSWER: frozenset(AuthorityCeiling),
    EvidenceSurface.PERSON: frozenset({
        AuthorityCeiling.OBSERVE_ONLY,
        AuthorityCeiling.FLAG_ONLY,
        AuthorityCeiling.ASK_OR_ABSTAIN,
    }),
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
        return decision(AuthorityAction.RECOMMEND_ESCALATION, "escalation_recommendation_only")

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


__all__ = [
    "AdmissionDecision",
    "AdmissionState",
    "Applicability",
    "AuthorityAction",
    "AuthorityCeiling",
    "AuthorityContext",
    "AuthorityDecision",
    "CandidateBinding",
    "CandidateRepair",
    "CheckStatus",
    "EvidenceSurface",
    "PatchCertificate",
    "SemanticVerification",
    "SensorOutcome",
    "SensorRegistration",
    "SensorReport",
    "StructuralCertificate",
    "decide_admission",
    "decide_authority",
]
