"""Calibration-bound residual reports mapped to FOIL's existing shadow authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from egrt_types import digest
from foil_authority import Applicability as AuthorityApplicability
from foil_authority import (
    AuthorityContext,
    SensorOutcome,
    SensorRegistration,
    SensorReport,
    decide_authority,
)
from foil_residual_scanner import ResidualScanReport
from foil_v5_metrics import ScanStatus


class CalibrationState(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    MISMATCH = "MISMATCH"


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
class CalibrationContext:
    scope_digest: str
    model_digest: str
    config_digest: str
    protocol_digest: str
    evidence_digest: str
    thresholds_digest: str
    now: datetime

    def __post_init__(self) -> None:
        for name in (
            "scope_digest",
            "model_digest",
            "config_digest",
            "protocol_digest",
            "evidence_digest",
            "thresholds_digest",
        ):
            _require_digest(name, getattr(self, name))
        if not isinstance(self.now, datetime) or self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware datetime")


@dataclass(frozen=True)
class SensorCalibration:
    sensor_id: str
    calibration_id: str
    scope_digest: str
    model_digest: str
    config_digest: str
    protocol_digest: str
    evidence_digest: str
    thresholds_digest: str
    correct_outputs: int
    false_flags: int
    wrong_outputs: int
    true_flags: int
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("sensor_id", "calibration_id"):
            _require_text(name, getattr(self, name))
        for name in (
            "scope_digest",
            "model_digest",
            "config_digest",
            "protocol_digest",
            "evidence_digest",
            "thresholds_digest",
        ):
            _require_digest(name, getattr(self, name))
        if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware datetime")
        for name in ("correct_outputs", "false_flags", "wrong_outputs", "true_flags"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.correct_outputs <= 0 or self.wrong_outputs <= 0:
            raise ValueError("calibration requires observed correct and wrong outputs")
        if self.false_flags > self.correct_outputs or self.true_flags > self.wrong_outputs:
            raise ValueError("calibration event counts cannot exceed class totals")

    @property
    def false_flag_rate(self) -> float:
        return self.false_flags / self.correct_outputs

    @property
    def residual_recall(self) -> float:
        return self.true_flags / self.wrong_outputs


@dataclass(frozen=True)
class CalibrationCheck:
    state: CalibrationState
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.state, CalibrationState):
            raise TypeError("state must be CalibrationState")
        _require_text("reason", self.reason)

    @property
    def current(self) -> bool:
        return self.state is CalibrationState.CURRENT


@dataclass(frozen=True)
class ResidualAuthorityMapping:
    report: SensorReport
    calibration: CalibrationCheck
    decision: object


def check_calibration(
    registration: SensorRegistration, calibration: SensorCalibration, context: CalibrationContext
) -> CalibrationCheck:
    if not isinstance(registration, SensorRegistration):
        raise TypeError("registration must be SensorRegistration")
    if not isinstance(calibration, SensorCalibration):
        raise TypeError("calibration must be SensorCalibration")
    if not isinstance(context, CalibrationContext):
        raise TypeError("context must be CalibrationContext")
    if calibration.sensor_id != registration.sensor_id:
        return CalibrationCheck(
            CalibrationState.MISMATCH, "calibration sensor identity does not match registration"
        )
    if context.now >= calibration.expires_at:
        return CalibrationCheck(CalibrationState.STALE, "calibration has expired")
    expected = (
        context.scope_digest,
        context.model_digest,
        context.config_digest,
        context.protocol_digest,
        context.evidence_digest,
        context.thresholds_digest,
    )
    actual = (
        calibration.scope_digest,
        calibration.model_digest,
        calibration.config_digest,
        calibration.protocol_digest,
        calibration.evidence_digest,
        calibration.thresholds_digest,
    )
    if actual != expected:
        return CalibrationCheck(
            CalibrationState.MISMATCH,
            "calibration scope/model/config/protocol/evidence/threshold binding mismatch",
        )
    return CalibrationCheck(CalibrationState.CURRENT, "calibration is current and exactly bound")


def map_to_authority(
    scan: ResidualScanReport,
    registration: SensorRegistration,
    calibration: SensorCalibration,
    context: CalibrationContext,
    authority_context: AuthorityContext = AuthorityContext(),
) -> ResidualAuthorityMapping:
    """Create an unprivileged report; only trusted registration supplies authority."""

    if not isinstance(scan, ResidualScanReport):
        raise TypeError("scan must be ResidualScanReport")
    checked = check_calibration(registration, calibration, context)
    if not checked.current:
        applicability, outcome = AuthorityApplicability.UNKNOWN, SensorOutcome.UNKNOWN
    elif scan.status is ScanStatus.NOT_APPLICABLE:
        applicability, outcome = AuthorityApplicability.NOT_APPLICABLE, SensorOutcome.UNKNOWN
    elif scan.status is ScanStatus.UNKNOWN:
        applicability, outcome = AuthorityApplicability.UNKNOWN, SensorOutcome.UNKNOWN
    elif scan.status is ScanStatus.FAIL:
        applicability, outcome = AuthorityApplicability.APPLICABLE, SensorOutcome.DEFECT
    else:
        applicability, outcome = AuthorityApplicability.APPLICABLE, SensorOutcome.CLEAR
    report = SensorReport(
        sensor_id=registration.sensor_id,
        input_digest=digest({"scan": scan.input_digest, "calibration": calibration.calibration_id}),
        applicability=applicability,
        outcome=outcome,
        target_scope=registration.claim_scope,
    )
    safe_context = AuthorityContext(
        repair_proposals_enabled=authority_context.repair_proposals_enabled,
        calibration_current=authority_context.calibration_current and checked.current,
        owner_risk_allows_repair=authority_context.owner_risk_allows_repair,
    )
    return ResidualAuthorityMapping(
        report=report,
        calibration=checked,
        decision=decide_authority(registration, report, safe_context),
    )
