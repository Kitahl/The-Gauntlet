"""One-claim v5 shadow runtime with digest-only receipts.

This is a pure orchestration boundary over the typed compiler, closed verifier
registry, residual scanner, and optional shadow-authority mapper.  It neither
creates repairs nor changes an answer, file, provider, or host state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from egrt_claims import (
    Applicability,
    ClaimKind,
    ClaimOutcome,
    Decidability,
    ImmutableBindings,
    compile_claim,
)
from egrt_coverage import ContributionOutcome, CoverageContribution
from egrt_types import EvidenceClass, digest
from foil_authority import AuthorityCeiling, AuthorityContext, EvidenceSurface, SensorRegistration
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, scan
from foil_residuals import CalibrationContext, CalibrationState, SensorCalibration, map_to_authority
from foil_v5_metrics import ResidualDiagnosticNeed, ScanStatus, summarize_metrics
from foil_v5_protocol import ProtocolValidationError, seal_protocol, validate_protocol

MANIFEST_SCHEMA = "egrt.foil-v5-shadow-runtime.v1"
RECEIPT_SCHEMA = "egrt.foil-v5-shadow-receipt.v1"
SCOPE = "ONE_CLAIM_V1"
_REQUIRED_ROOT = frozenset(
    {
        "schema",
        "g0_mode",
        "g0_protocol",
        "bindings",
        "claim",
        "observed_a0_digest",
        "diagnostic_needs",
        "cases",
    }
)
_OPTIONAL_ROOT = frozenset({"declared_coverage", "adjudicated_coverage", "authority"})


class RuntimeValidationError(ValueError):
    """A manifest cannot safely enter the shadow runtime."""


def _safe_digest(value: object) -> str:
    try:
        return digest(value)
    except (TypeError, ValueError):
        return hashlib.sha256(type(value).__name__.encode("utf-8")).hexdigest()


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeValidationError(f"{name} must be an object")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeValidationError(f"{name} must be a list")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeValidationError(f"{name} must be non-empty text")
    return value


def _enum(enum_type: type, name: str, value: object):
    if not isinstance(value, str):
        raise RuntimeValidationError(f"{name} must be an enum string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise RuntimeValidationError(f"{name} is not a supported enum value") from exc


def _strict_fields(name: str, row: Mapping[str, Any], required: set[str], optional: set[str] = set()) -> None:
    unknown = set(row) - required - optional
    missing = required - set(row)
    if unknown or missing:
        raise RuntimeValidationError(f"{name} has unknown or missing fields")


def _bindings(row: object) -> ImmutableBindings:
    data = _mapping("bindings", row)
    fields = {"a0_digest", "task_digest", "spec_digest", "compiler_digest", "config_digest"}
    _strict_fields("bindings", data, fields)
    try:
        return ImmutableBindings(**{key: data[key] for key in fields})
    except (TypeError, ValueError) as exc:
        raise RuntimeValidationError("bindings are malformed") from exc


def _protocol(mode: object, value: object) -> Mapping[str, Any]:
    if mode not in {"seal", "verify"}:
        raise RuntimeValidationError("g0_mode must be seal or verify")
    protocol = _mapping("g0_protocol", value)
    try:
        if mode == "seal":
            return seal_protocol(protocol)
        validate_protocol(protocol, require_seal=True)
        return dict(protocol)
    except ProtocolValidationError as exc:
        raise RuntimeValidationError("G0 protocol validation failed") from exc


def _claim(row: object, bindings: ImmutableBindings):
    data = _mapping("claim", row)
    required = {"statement", "kind", "decidability", "applicability", "reason"}
    _strict_fields("claim", data, required, {"required_verifiers"})
    verifiers = data.get("required_verifiers", [])
    if not isinstance(verifiers, list) or any(not isinstance(item, str) for item in verifiers):
        raise RuntimeValidationError("claim.required_verifiers must be a string list")
    try:
        return compile_claim(
            statement=_text("claim.statement", data["statement"]),
            kind=_enum(ClaimKind, "claim.kind", data["kind"]),
            decidability=_enum(Decidability, "claim.decidability", data["decidability"]),
            applicability=_enum(Applicability, "claim.applicability", data["applicability"]),
            bindings=bindings,
            required_verifiers=tuple(verifiers),
            reason=_text("claim.reason", data["reason"]),
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeValidationError("claim compilation inputs are malformed") from exc


def _needs(value: object, claim_id: str, bindings: ImmutableBindings) -> tuple[ResidualDiagnosticNeed, ...]:
    rows = _sequence("diagnostic_needs", value)
    if not rows:
        raise RuntimeValidationError("diagnostic_needs must not be empty")
    out: list[ResidualDiagnosticNeed] = []
    fields = {"need_id", "description", "verifier_id", "weight_units", "decidability", "applicability"}
    for row in rows:
        data = _mapping("diagnostic_need", row)
        _strict_fields("diagnostic_need", data, fields)
        try:
            out.append(
                ResidualDiagnosticNeed(
                    need_id=_text("need_id", data["need_id"]),
                    claim_id=claim_id,
                    description=_text("description", data["description"]),
                    verifier_id=_text("verifier_id", data["verifier_id"]),
                    weight_units=data["weight_units"],
                    decidability=_enum(Decidability, "need.decidability", data["decidability"]),
                    applicability=_enum(Applicability, "need.applicability", data["applicability"]),
                    bindings=bindings,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeValidationError("diagnostic_need is malformed or uses an unregistered verifier") from exc
    return tuple(out)


def _cases(value: object) -> tuple[DiagnosticCase, ...]:
    rows = _sequence("cases", value)
    out: list[DiagnosticCase] = []
    for row in rows:
        data = _mapping("case", row)
        _strict_fields("case", data, {"need_id", "verifier_input", "metadata"})
        try:
            out.append(DiagnosticCase(_text("case.need_id", data["need_id"]), data["verifier_input"], data["metadata"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeValidationError("diagnostic case is malformed") from exc
    return tuple(out)


def _contributions(name: str, value: object) -> tuple[CoverageContribution, ...]:
    rows = _sequence(name, value)
    out: list[CoverageContribution] = []
    for row in rows:
        data = _mapping(name, row)
        _strict_fields(name, data, {"need_id", "evidence_digest", "outcome", "reason"})
        try:
            out.append(
                CoverageContribution(
                    obligation_id=_text(f"{name}.need_id", data["need_id"]),
                    evidence_digest=_text(f"{name}.evidence_digest", data["evidence_digest"]),
                    outcome=_enum(ContributionOutcome, f"{name}.outcome", data["outcome"]),
                    reason=_text(f"{name}.reason", data["reason"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeValidationError(f"{name} contribution is malformed") from exc
    return tuple(out)


def _when(value: object) -> datetime:
    if not isinstance(value, str):
        raise RuntimeValidationError("authority.now must be ISO timestamp text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeValidationError("authority.now is malformed") from exc
    if parsed.tzinfo is None:
        raise RuntimeValidationError("authority.now must include timezone")
    return parsed


def _authority(value: object, bindings: ImmutableBindings, protocol_digest: str):
    data = _mapping("authority", value)
    _strict_fields(
        "authority",
        data,
        {"registration", "calibration", "calibration_context", "authority_context"},
    )
    registration_data = _mapping("authority.registration", data["registration"])
    _strict_fields(
        "authority.registration",
        registration_data,
        {"sensor_id", "evidence_class", "surface", "authority_ceiling", "claim_scope", "producer", "version"},
    )
    context_data = _mapping("authority.calibration_context", data["calibration_context"])
    context_fields = {"scope_digest", "model_digest", "config_digest", "protocol_digest", "evidence_digest", "thresholds_digest", "now"}
    _strict_fields("authority.calibration_context", context_data, context_fields)
    if context_data["config_digest"] != bindings.config_digest or context_data["protocol_digest"] != protocol_digest:
        raise RuntimeValidationError("authority calibration context is not bound to config/G0")
    calibration_data = _mapping("authority.calibration", data["calibration"])
    calibration_fields = {"sensor_id", "calibration_id", "scope_digest", "model_digest", "config_digest", "protocol_digest", "evidence_digest", "thresholds_digest", "correct_outputs", "false_flags", "wrong_outputs", "true_flags", "expires_at"}
    _strict_fields("authority.calibration", calibration_data, calibration_fields)
    owner = _mapping("authority.authority_context", data["authority_context"])
    _strict_fields("authority.authority_context", owner, {"repair_proposals_enabled", "calibration_current", "owner_risk_allows_repair"})
    try:
        registration = SensorRegistration(
            sensor_id=_text("sensor_id", registration_data["sensor_id"]),
            evidence_class=_enum(EvidenceClass, "evidence_class", registration_data["evidence_class"]),
            surface=_enum(EvidenceSurface, "surface", registration_data["surface"]),
            authority_ceiling=_enum(AuthorityCeiling, "authority_ceiling", registration_data["authority_ceiling"]),
            claim_scope=_text("claim_scope", registration_data["claim_scope"]),
            producer=_text("producer", registration_data["producer"]),
            version=_text("version", registration_data["version"]),
        )
        context = CalibrationContext(
            scope_digest=context_data["scope_digest"], model_digest=context_data["model_digest"], config_digest=context_data["config_digest"],
            protocol_digest=context_data["protocol_digest"], evidence_digest=context_data["evidence_digest"], thresholds_digest=context_data["thresholds_digest"], now=_when(context_data["now"]),
        )
        calibration = SensorCalibration(
            sensor_id=calibration_data["sensor_id"], calibration_id=calibration_data["calibration_id"], scope_digest=calibration_data["scope_digest"],
            model_digest=calibration_data["model_digest"], config_digest=calibration_data["config_digest"], protocol_digest=calibration_data["protocol_digest"],
            evidence_digest=calibration_data["evidence_digest"], thresholds_digest=calibration_data["thresholds_digest"], correct_outputs=calibration_data["correct_outputs"],
            false_flags=calibration_data["false_flags"], wrong_outputs=calibration_data["wrong_outputs"], true_flags=calibration_data["true_flags"], expires_at=_when(calibration_data["expires_at"]),
        )
        authority_context = AuthorityContext(**dict(owner))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError("authority inputs are malformed or not count-backed") from exc
    return registration, calibration, context, authority_context


def _metrics_public(metrics: object) -> dict[str, object]:
    if metrics is None:
        return {}
    return {
        "coverage_sha256": metrics.weighted.coverage_digest,
        "decidable_mass": metrics.weighted.decidable_mass,
        "covered_mass": metrics.weighted.covered_mass,
        "failed_mass": metrics.weighted.failed_mass,
        "unresolved_mass": metrics.weighted.unresolved_mass,
        "omitted_mass": metrics.weighted.omitted_mass,
        "undecidable_mass": metrics.weighted.undecidable_mass,
        "decidable_count": metrics.decidable_count,
        "covered_count": metrics.covered_count,
        "failed_count": metrics.failed_count,
        "unresolved_count": metrics.unresolved_count,
        "omitted_count": metrics.omitted_count,
        "undecidable_count": metrics.undecidable_count,
    }


def _receipt(body: dict[str, object]) -> dict[str, object]:
    receipt = {"schema": RECEIPT_SCHEMA, "scope": SCOPE, **body}
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def _failed_receipt(manifest: object, reason: str) -> dict[str, object]:
    return _receipt(
        {
            "status": ScanStatus.UNKNOWN.value,
            "reason": reason,
            "manifest_sha256": _safe_digest(manifest),
            "execution_authorized": False,
            "repair_generated": False,
        }
    )


def run_manifest(manifest: object) -> dict[str, object]:
    """Run a strict one-claim manifest and return only digest/enumeration receipt data."""

    try:
        data = _mapping("manifest", manifest)
        _strict_fields("manifest", data, set(_REQUIRED_ROOT), set(_OPTIONAL_ROOT))
        if data["schema"] != MANIFEST_SCHEMA:
            raise RuntimeValidationError("manifest schema is unsupported")
        protocol = _protocol(data["g0_mode"], data["g0_protocol"])
        bindings = _bindings(data["bindings"])
        compilation = _claim(data["claim"], bindings)
        common = {
            "manifest_sha256": _safe_digest(data),
            "g0_protocol_sha256": protocol["protocol_sha256"],
            "binding_sha256": bindings.binding_digest,
            "compilation_outcome": compilation.outcome.value,
            "execution_authorized": False,
            "repair_generated": False,
        }
        if compilation.outcome is not ClaimOutcome.COMPILED:
            status = ScanStatus.NOT_APPLICABLE if compilation.outcome is ClaimOutcome.NOT_APPLICABLE else ScanStatus.UNKNOWN
            return _receipt({**common, "status": status.value, "reason": compilation.reason})
        claim = compilation.claim
        assert claim is not None
        needs = _needs(data["diagnostic_needs"], claim.claim_id, bindings)
        cases = _cases(data["cases"])
        observed_a0 = _text("observed_a0_digest", data["observed_a0_digest"])
        report = scan(ResidualScanPlan(claim.claim_id, bindings.a0_digest, bindings, needs), observed_a0, cases)
        declared = summarize_metrics(needs, _contributions("declared_coverage", data["declared_coverage"])) if "declared_coverage" in data else None
        adjudicated = summarize_metrics(needs, _contributions("adjudicated_coverage", data["adjudicated_coverage"])) if "adjudicated_coverage" in data else None
        status, reason = report.status, report.reason
        authority_public: dict[str, object] | None = None
        if "authority" in data:
            registration, calibration, context, owner = _authority(data["authority"], bindings, protocol["protocol_sha256"])
            mapping = map_to_authority(report, registration, calibration, context, owner)
            authority_public = {"calibration_state": mapping.calibration.state.value, "action": mapping.decision.action.value, "shadow_mode": mapping.decision.shadow_mode, "execution_authorized": mapping.decision.execution_authorized}
            if status is ScanStatus.PASS and mapping.calibration.state is not CalibrationState.CURRENT:
                status, reason = ScanStatus.UNKNOWN, "scanner pass cannot survive stale or mismatched calibration"
        return _receipt(
            {
                **common,
                "status": status.value,
                "reason": reason,
                "claim_id": claim.claim_id,
                "scan_input_sha256": report.input_digest,
                "scan_no_answer": report.no_answer.code.value if report.no_answer else None,
                "scan_coverage": _metrics_public(report.metrics),
                "declared_coverage": _metrics_public(declared) if declared else None,
                "adjudicated_coverage": _metrics_public(adjudicated) if adjudicated else None,
                "authority": authority_public,
            }
        )
    except (RuntimeValidationError, TypeError, ValueError, KeyError):
        return _failed_receipt(manifest, "manifest validation failed closed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL v5 one-claim shadow runtime")
    parser.add_argument("manifest", nargs="?", help="JSON manifest path; omitted reads stdin")
    args = parser.parse_args(argv)
    try:
        if args.manifest:
            with open(args.manifest, encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError):
        payload = None
    print(json.dumps(run_manifest(payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
