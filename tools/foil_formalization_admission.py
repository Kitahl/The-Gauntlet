"""Fail-closed admission for externally generated FOIL obligation specs.

The current FOIL compiler remains deterministic and never reads prose.  This
module sits in front of it when a host elects to supply a spec produced by an
external formalizer.  It does not call a model, judge semantics, or grant
execution authority.  It admits only content-addressed specs backed by a
route-scoped calibration, separately measured extraction recall, a complete
mutation receipt, and mechanical per-instance checks.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from egrt_types import digest
from foil_evidence import regularized_incomplete_beta
from foil_obligation_compiler import (
    TASK_SPEC_SCHEMA,
    CompiledTaskSpec,
    compile_task_spec,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PPM = 1_000_000


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_ppm(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= PPM:
        raise ValueError(f"{name} must be an integer in [0, 1000000]")
    return value


def _when(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class TranslationDistance(str, Enum):
    EXECUTION = "EXECUTION"
    TRANSLATION = "TRANSLATION"


class FormalizationAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    STAND_DOWN = "STAND_DOWN"


@dataclass(frozen=True)
class FormalizationRouteBinding:
    route_id: str
    route_version: str
    translation_distance: TranslationDistance
    formalizer_fingerprints_sha256: tuple[str, ...]
    task_regime_sha256: str
    target_schema: str

    def __post_init__(self) -> None:
        _require_text("route_id", self.route_id)
        _require_text("route_version", self.route_version)
        object.__setattr__(
            self,
            "translation_distance",
            TranslationDistance(self.translation_distance),
        )
        if not isinstance(self.formalizer_fingerprints_sha256, tuple):
            raise TypeError("formalizer_fingerprints_sha256 must be a tuple")
        if not self.formalizer_fingerprints_sha256:
            raise ValueError("a generated route must identify at least one formalizer")
        for value in self.formalizer_fingerprints_sha256:
            _require_digest("formalizer_fingerprint_sha256", value)
        if len(set(self.formalizer_fingerprints_sha256)) != len(
            self.formalizer_fingerprints_sha256
        ):
            raise ValueError("formalizer fingerprints must be unique")
        _require_digest("task_regime_sha256", self.task_regime_sha256)
        _require_text("target_schema", self.target_schema)

    @property
    def binding_digest(self) -> str:
        return digest(
            {
                "route_id": self.route_id,
                "route_version": self.route_version,
                "translation_distance": self.translation_distance.value,
                "formalizer_fingerprints_sha256": self.formalizer_fingerprints_sha256,
                "task_regime_sha256": self.task_regime_sha256,
                "target_schema": self.target_schema,
            }
        )


@dataclass(frozen=True)
class FormalizationCalibration:
    route_binding_digest: str
    audited_faithful: int
    audited_unfaithful: int
    extracted_load_bearing_claims: int
    source_load_bearing_claims: int
    mutation_classes_expected: tuple[str, ...]
    mutation_classes_caught: tuple[str, ...]
    error_correlation_ppm: int | None
    auditor_provenance_sha256: str
    evidence_sha256: str
    observed_at: str
    expires_at: str

    def __post_init__(self) -> None:
        _require_digest("route_binding_digest", self.route_binding_digest)
        for name in (
            "audited_faithful",
            "audited_unfaithful",
            "extracted_load_bearing_claims",
            "source_load_bearing_claims",
        ):
            _require_count(name, getattr(self, name))
        if self.audited_faithful + self.audited_unfaithful <= 0:
            raise ValueError("calibration must contain audited outcomes")
        if self.extracted_load_bearing_claims > self.source_load_bearing_claims:
            raise ValueError("extracted claims cannot exceed source claims")
        for name in ("mutation_classes_expected", "mutation_classes_caught"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValueError(f"{name} must be a tuple of non-empty names")
            if len(set(value)) != len(value):
                raise ValueError(f"{name} must not contain duplicates")
        if not set(self.mutation_classes_caught).issubset(
            self.mutation_classes_expected
        ):
            raise ValueError("caught mutation classes must belong to the frozen suite")
        if self.error_correlation_ppm is not None:
            _require_ppm("error_correlation_ppm", self.error_correlation_ppm)
        _require_digest("auditor_provenance_sha256", self.auditor_provenance_sha256)
        _require_digest("evidence_sha256", self.evidence_sha256)
        if _when("expires_at", self.expires_at) <= _when("observed_at", self.observed_at):
            raise ValueError("calibration must expire after it was observed")

    @property
    def calibration_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class FormalizationInstanceChecks:
    route_binding_digest: str
    source_text_sha256: str
    generated_spec_sha256: str
    round_trip_passed: bool
    forward_entailment_passed: bool
    reverse_entailment_passed: bool
    dual_formalization_agreed: bool
    mechanical_equivalence_sha256: str | None
    extraction_review_passed: bool
    check_evidence_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "route_binding_digest",
            "source_text_sha256",
            "generated_spec_sha256",
        ):
            _require_digest(name, getattr(self, name))
        for name in (
            "round_trip_passed",
            "forward_entailment_passed",
            "reverse_entailment_passed",
            "dual_formalization_agreed",
            "extraction_review_passed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.mechanical_equivalence_sha256 is not None:
            _require_digest(
                "mechanical_equivalence_sha256",
                self.mechanical_equivalence_sha256,
            )
        if not isinstance(self.check_evidence_sha256, tuple):
            raise TypeError("check_evidence_sha256 must be a tuple")
        if not self.check_evidence_sha256:
            raise ValueError("instance checks require content-addressed evidence")
        for value in self.check_evidence_sha256:
            _require_digest("check_evidence_sha256", value)


@dataclass(frozen=True)
class FormalizationFidelityPolicy:
    enabled: bool = False
    confidence_ppm: int = 950_000
    fidelity_floor_ppm: int = 950_000
    extraction_recall_floor_ppm: int = 900_000
    min_audited_transforms: int = 1
    max_error_correlation_ppm: int = 600_000
    require_complete_mutation_suite: bool = True
    require_dual_translation: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        for name in (
            "confidence_ppm",
            "fidelity_floor_ppm",
            "extraction_recall_floor_ppm",
            "max_error_correlation_ppm",
        ):
            _require_ppm(name, getattr(self, name))
        if not 500_000 <= self.confidence_ppm < PPM:
            raise ValueError("confidence_ppm must be in [500000, 1000000)")
        if self.min_audited_transforms <= 0:
            raise ValueError("min_audited_transforms must be positive")
        for name in ("require_complete_mutation_suite", "require_dual_translation"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")

    @property
    def policy_digest(self) -> str:
        return digest(self)


def clopper_pearson_lower_ppm(successes: int, total: int, confidence_ppm: int) -> int:
    """Return the exact one-sided binomial lower bound, floored to ppm."""

    _require_count("successes", successes)
    _require_count("total", total)
    _require_ppm("confidence_ppm", confidence_ppm)
    if total <= 0 or successes > total:
        raise ValueError("require 0 <= successes <= total and total > 0")
    if not 500_000 <= confidence_ppm < PPM:
        raise ValueError("confidence_ppm must be in [500000, 1000000)")
    if successes == 0:
        return 0
    alpha = 1.0 - confidence_ppm / PPM
    lo, hi = 0.0, 1.0
    failures = total - successes
    for _ in range(90):
        mid = (lo + hi) / 2.0
        cdf = regularized_incomplete_beta(successes, failures + 1, mid)
        if cdf < alpha:
            lo = mid
        else:
            hi = mid
    return min(PPM, max(0, math.floor(lo * PPM)))


@dataclass(frozen=True)
class FormalizationAdmissionReceipt:
    status: FormalizationAdmissionStatus
    reason_code: str
    route_binding_digest: str
    target_schema: str
    source_text_sha256: str
    generated_spec_sha256: str
    calibration_sha256: str
    policy_sha256: str
    fidelity_lower_ppm: int
    extraction_recall_lower_ppm: int
    mutation_suite_complete: bool
    instance_checks_passed: bool
    execution_authorized: bool = field(default=False, init=False)
    host_action_required: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", FormalizationAdmissionStatus(self.status))
        _require_text("reason_code", self.reason_code)
        for name in (
            "route_binding_digest",
            "source_text_sha256",
            "generated_spec_sha256",
            "calibration_sha256",
            "policy_sha256",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("target_schema", self.target_schema)
        for name in ("fidelity_lower_ppm", "extraction_recall_lower_ppm"):
            _require_ppm(name, getattr(self, name))
        for name in ("mutation_suite_complete", "instance_checks_passed"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.execution_authorized or not self.host_action_required:
            raise ValueError("formalization admission is control-only")

    @property
    def admission_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class AdmittedCompiledTaskSpec:
    compiled: CompiledTaskSpec
    admission: FormalizationAdmissionReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.compiled, CompiledTaskSpec):
            raise TypeError("compiled must be CompiledTaskSpec")
        if not isinstance(self.admission, FormalizationAdmissionReceipt):
            raise TypeError("admission must be FormalizationAdmissionReceipt")
        if self.admission.status is not FormalizationAdmissionStatus.ADMITTED:
            raise ValueError("generated compilation requires an admitted receipt")
        if self.compiled.source_spec_digest != self.admission.generated_spec_sha256:
            raise ValueError("compiled spec and admission receipt must match")


def _receipt(
    *,
    status: FormalizationAdmissionStatus,
    reason: str,
    binding: FormalizationRouteBinding,
    calibration: FormalizationCalibration,
    checks: FormalizationInstanceChecks,
    policy: FormalizationFidelityPolicy,
    fidelity_lower_ppm: int,
    extraction_lower_ppm: int,
    mutation_complete: bool,
    checks_passed: bool,
) -> FormalizationAdmissionReceipt:
    return FormalizationAdmissionReceipt(
        status=status,
        reason_code=reason,
        route_binding_digest=binding.binding_digest,
        target_schema=binding.target_schema,
        source_text_sha256=checks.source_text_sha256,
        generated_spec_sha256=checks.generated_spec_sha256,
        calibration_sha256=calibration.calibration_digest,
        policy_sha256=policy.policy_digest,
        fidelity_lower_ppm=fidelity_lower_ppm,
        extraction_recall_lower_ppm=extraction_lower_ppm,
        mutation_suite_complete=mutation_complete,
        instance_checks_passed=checks_passed,
    )


def admit_formalization(
    binding: FormalizationRouteBinding,
    calibration: FormalizationCalibration,
    checks: FormalizationInstanceChecks,
    policy: FormalizationFidelityPolicy = FormalizationFidelityPolicy(),
    *,
    now: str,
) -> FormalizationAdmissionReceipt:
    """Admit one generated spec only when route and instance gates all pass."""

    if not isinstance(binding, FormalizationRouteBinding):
        raise TypeError("binding must be FormalizationRouteBinding")
    if not isinstance(calibration, FormalizationCalibration):
        raise TypeError("calibration must be FormalizationCalibration")
    if not isinstance(checks, FormalizationInstanceChecks):
        raise TypeError("checks must be FormalizationInstanceChecks")
    if not isinstance(policy, FormalizationFidelityPolicy):
        raise TypeError("policy must be FormalizationFidelityPolicy")
    current = _when("now", now)
    audited = calibration.audited_faithful + calibration.audited_unfaithful
    fidelity_lower = clopper_pearson_lower_ppm(
        calibration.audited_faithful,
        audited,
        policy.confidence_ppm,
    )
    extraction_lower = (
        clopper_pearson_lower_ppm(
            calibration.extracted_load_bearing_claims,
            calibration.source_load_bearing_claims,
            policy.confidence_ppm,
        )
        if calibration.source_load_bearing_claims
        else 0
    )
    mutation_complete = bool(calibration.mutation_classes_expected) and (
        set(calibration.mutation_classes_caught)
        == set(calibration.mutation_classes_expected)
    )
    checks_passed = all(
        (
            checks.round_trip_passed,
            checks.forward_entailment_passed,
            checks.reverse_entailment_passed,
            checks.extraction_review_passed,
        )
    )

    reason = "all_formalization_admission_gates_passed"
    if not policy.enabled:
        reason = "formalization_route_disabled"
    elif binding.target_schema != TASK_SPEC_SCHEMA:
        reason = "unsupported_target_schema"
    elif calibration.route_binding_digest != binding.binding_digest:
        reason = "calibration_route_binding_mismatch"
    elif checks.route_binding_digest != binding.binding_digest:
        reason = "instance_route_binding_mismatch"
    elif current < _when("observed_at", calibration.observed_at):
        reason = "calibration_not_yet_current"
    elif current >= _when("expires_at", calibration.expires_at):
        reason = "calibration_expired"
    elif audited < policy.min_audited_transforms:
        reason = "insufficient_audited_transforms"
    elif fidelity_lower < policy.fidelity_floor_ppm:
        reason = "fidelity_lower_bound_below_floor"
    elif extraction_lower < policy.extraction_recall_floor_ppm:
        reason = "extraction_recall_lower_bound_below_floor"
    elif policy.require_complete_mutation_suite and not mutation_complete:
        reason = "mutation_suite_incomplete"
    elif not checks_passed:
        reason = "instance_fidelity_checks_failed"
    elif binding.translation_distance is TranslationDistance.TRANSLATION:
        if policy.require_dual_translation and len(
            binding.formalizer_fingerprints_sha256
        ) < 2:
            reason = "dual_formalization_required"
        elif policy.require_dual_translation and not checks.dual_formalization_agreed:
            reason = "dual_formalization_disagreed"
        elif checks.mechanical_equivalence_sha256 is None:
            reason = "mechanical_equivalence_missing"
        elif calibration.error_correlation_ppm is None:
            reason = "formalizer_error_correlation_unmeasured"
        elif calibration.error_correlation_ppm > policy.max_error_correlation_ppm:
            reason = "formalizer_error_correlation_above_limit"

    status = (
        FormalizationAdmissionStatus.ADMITTED
        if reason == "all_formalization_admission_gates_passed"
        else FormalizationAdmissionStatus.STAND_DOWN
    )
    return _receipt(
        status=status,
        reason=reason,
        binding=binding,
        calibration=calibration,
        checks=checks,
        policy=policy,
        fidelity_lower_ppm=fidelity_lower,
        extraction_lower_ppm=extraction_lower,
        mutation_complete=mutation_complete,
        checks_passed=checks_passed,
    )


def compile_admitted_task_spec(
    spec: object,
    *,
    observed_a0_digest: str,
    admission: FormalizationAdmissionReceipt,
) -> AdmittedCompiledTaskSpec:
    """Compile an already admitted generated spec without weakening the compiler."""

    if not isinstance(admission, FormalizationAdmissionReceipt):
        raise TypeError("admission must be FormalizationAdmissionReceipt")
    if admission.status is not FormalizationAdmissionStatus.ADMITTED:
        raise ValueError("generated obligation spec was not admitted")
    if digest(spec) != admission.generated_spec_sha256:
        raise ValueError("generated spec digest does not match its admission receipt")
    if (
        not isinstance(spec, dict)
        or spec.get("schema") != admission.target_schema
    ):
        raise ValueError("generated spec schema does not match its admission receipt")
    compiled = compile_task_spec(spec, observed_a0_digest=observed_a0_digest)
    return AdmittedCompiledTaskSpec(compiled, admission)
