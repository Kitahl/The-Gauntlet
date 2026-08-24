"""Integrated, host-safe FOIL v5 structured shadow pipeline.

This is the production seam that the earlier pilots assembled manually:
strict compilation -> deterministic scanning -> adaptive shadow routing ->
optional observational RouteVector recording.  It never creates a candidate,
calls a provider, mutates A0, or authorizes execution.  A separate helper may
pass an already authorized host request into the pure host finalizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from egrt_host_bridge import HostActionRequest
from egrt_host_finalizer import (
    HostCommitApproval,
    HostFinalizationResult,
    answer_digest,
    finalize_host_answer,
)
from egrt_types import digest
from egrt_verifiers import VerifierResult
from foil_adaptive_route import (
    AdaptiveRoutePolicy,
    DecisionReason,
    FrozenEVModel,
    HostVerifierRoute,
    RiskClass,
    Route,
    ShadowRouteDecision,
    decide_shadow_route,
    host_verifier_routes,
)
from foil_formalization_admission import AdmittedCompiledTaskSpec
from foil_formalization_routing import AdmittedShadowRouteDecision
from foil_obligation_compiler import CompiledTaskSpec, compile_task_spec
from foil_residual_scanner import ResidualScanReport, scan
from foil_shadow_route_ledger import (
    EligibilityReason,
    EligibilityTrace,
    OutcomeKind,
    RouteVector,
    ShadowRouteObservation,
    ShadowRouteVectorLedger,
)
from foil_v5_metrics import ScanStatus


class PipelineStatus(str, Enum):
    CLEARED = "CLEARED"
    DEFECT = "DEFECT"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class StructuredShadowResult:
    base_answer: str
    compiled: CompiledTaskSpec
    scans: tuple[ResidualScanReport, ...]
    status: PipelineStatus
    route: ShadowRouteDecision | AdmittedShadowRouteDecision
    route_observation_digest: str | None
    route_observation_recorded: bool
    base_answer_preserved: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    candidate_generated: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.base_answer, str):
            raise TypeError("base_answer must be str")
        if not isinstance(self.compiled, CompiledTaskSpec):
            raise TypeError("compiled must be CompiledTaskSpec")
        if not isinstance(self.scans, tuple) or any(
            not isinstance(item, ResidualScanReport) for item in self.scans
        ):
            raise TypeError("scans must contain ResidualScanReport")
        object.__setattr__(self, "status", PipelineStatus(self.status))
        if not isinstance(
            self.route,
            (ShadowRouteDecision, AdmittedShadowRouteDecision),
        ):
            raise TypeError("route must be a shadow route decision")
        if self.route_observation_digest is not None:
            _require_digest(
                "route_observation_digest",
                self.route_observation_digest,
            )
        if not isinstance(self.route_observation_recorded, bool):
            raise TypeError("route_observation_recorded must be bool")
        if not self.base_answer_preserved or self.execution_authorized:
            raise ValueError("the structured pipeline must preserve A0")

    @property
    def decision(self) -> ShadowRouteDecision:
        if isinstance(self.route, AdmittedShadowRouteDecision):
            return self.route.decision
        return self.route

    def trace(self) -> dict[str, object]:
        scan_rows = [
            {
                "status": item.status.value,
                "input_digest": item.input_digest,
                "no_answer": item.no_answer.code.value if item.no_answer else None,
                "failed_count": item.metrics.failed_count,
                "unresolved_count": item.metrics.unresolved_count,
                "omitted_count": item.metrics.omitted_count,
            }
            for item in self.scans
        ]
        body: dict[str, object] = {
            "schema": "egrt.foil-v5-integrated-shadow.v1",
            "a0_digest": self.compiled.bindings.a0_digest,
            "compilation_digest": self.compiled.compilation_digest,
            "status": self.status.value,
            "scans": scan_rows,
            "route": self.route.trace(),
            "route_observation_digest": self.route_observation_digest,
            "route_observation_recorded": self.route_observation_recorded,
            "base_answer_preserved": self.base_answer_preserved,
            "execution_authorized": self.execution_authorized,
            "candidate_generated": self.candidate_generated,
            "raw_answer_stored": False,
            "raw_spec_stored": False,
        }
        body["trace_sha256"] = digest(body)
        return body


def _require_digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _aggregate(scans: tuple[ResidualScanReport, ...]) -> PipelineStatus:
    if any(item.status is ScanStatus.FAIL for item in scans):
        return PipelineStatus.DEFECT
    if scans and all(item.status is ScanStatus.PASS for item in scans):
        return PipelineStatus.CLEARED
    return PipelineStatus.UNRESOLVED


def _failed_verifiers(
    scans: tuple[ResidualScanReport, ...],
) -> tuple[tuple[str, VerifierResult], ...]:
    rows: list[tuple[str, VerifierResult]] = []
    for report in scans:
        for result in report.results:
            if result.status is ScanStatus.FAIL and result.verifier is not None:
                rows.append((result.need_id, result.verifier))
    return tuple(rows)


def _selected_routes(
    routes: tuple[HostVerifierRoute, ...],
    risk: RiskClass,
    failures: tuple[tuple[str, VerifierResult], ...],
) -> tuple[RiskClass, tuple[HostVerifierRoute, ...], VerifierResult | None]:
    by_obligation = {route.obligation_id: route for route in routes}
    if len(failures) == 1:
        need_id, verifier = failures[0]
        route = by_obligation.get(need_id)
        return (
            RiskClass.VERIFIED_DEFECT,
            (route,) if route is not None else (),
            verifier,
        )
    if len(failures) > 1:
        failed_routes = tuple(
            by_obligation[need_id]
            for need_id, _ in failures
            if need_id in by_obligation
        )
        return RiskClass.MULTIPLE_OR_CONTRADICTORY, failed_routes, None
    if risk is RiskClass.NONE:
        return risk, (), None
    return risk, routes, None


def _eligibility_reason(decision: ShadowRouteDecision) -> EligibilityReason:
    if decision.reason is DecisionReason.CONTROLLER_DISABLED:
        return EligibilityReason.POLICY_DISABLED
    if decision.reason is DecisionReason.COST_CAP_EXHAUSTED:
        return EligibilityReason.COST_CAP_EXHAUSTED
    if decision.reason is DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT:
        return EligibilityReason.NO_POSITIVE_VALUE_COMPLEMENT
    if decision.route in {Route.VERIFY, Route.FULL}:
        return EligibilityReason.ELIGIBLE
    return EligibilityReason.UNKNOWN


def _record_route(
    *,
    ledger: ShadowRouteVectorLedger | None,
    decision: ShadowRouteDecision,
    selected_routes: tuple[HostVerifierRoute, ...],
    compiled: CompiledTaskSpec,
    model_fingerprint_sha256: str,
    contract_fingerprint_sha256: str,
    provider_fingerprints_sha256: tuple[str, ...],
    source_receipt_digest: str,
) -> tuple[str | None, bool]:
    if ledger is None:
        return None, False
    if not isinstance(ledger, ShadowRouteVectorLedger):
        raise TypeError("route_ledger must be ShadowRouteVectorLedger or None")
    _require_digest("model_fingerprint_sha256", model_fingerprint_sha256)
    _require_digest("contract_fingerprint_sha256", contract_fingerprint_sha256)
    for value in provider_fingerprints_sha256:
        _require_digest("provider_fingerprint_sha256", value)
    single = selected_routes[0] if len(selected_routes) == 1 else None
    route = RouteVector(
        compute_mode=decision.route,
        provider_fingerprints_sha256=provider_fingerprints_sha256,
        verifier_id=single.verifier_id if single else None,
        verifier_version=single.verifier_version if single else None,
        retry_count=0,
    )
    eligibility = EligibilityTrace(
        task_signature_sha256=compiled.bindings.task_digest,
        model_fingerprint_sha256=model_fingerprint_sha256,
        contract_fingerprint_sha256=contract_fingerprint_sha256,
        route=route,
        eligible=decision.route in {Route.VERIFY, Route.FULL},
        reason_code=_eligibility_reason(decision),
    )
    observation = ShadowRouteObservation(
        eligibility=eligibility,
        proposed=route,
        observed=None,
        outcome_kind=OutcomeKind.UNKNOWN,
        verified=None,
        final_success=None,
        source_receipt_digest=source_receipt_digest,
    )
    return observation.observation_digest, ledger.append(observation)


def run_structured_shadow(
    *,
    base_answer: str,
    task_spec: object | None = None,
    admitted: AdmittedCompiledTaskSpec | None = None,
    risk: RiskClass = RiskClass.NONE,
    route_policy: AdaptiveRoutePolicy = AdaptiveRoutePolicy(),
    ev: FrozenEVModel | None = None,
    remaining_cost_units: int | None = None,
    route_ledger: ShadowRouteVectorLedger | None = None,
    model_fingerprint_sha256: str,
    contract_fingerprint_sha256: str,
    provider_fingerprints_sha256: tuple[str, ...] = (),
) -> StructuredShadowResult:
    """Run the complete zero-I/O shadow path over one structured task spec."""

    if not isinstance(base_answer, str):
        raise TypeError("base_answer must be str")
    if (task_spec is None) == (admitted is None):
        raise ValueError("supply exactly one of host task_spec or admitted generated spec")
    observed_a0_digest = answer_digest(base_answer)
    compiled = (
        admitted.compiled
        if admitted is not None
        else compile_task_spec(task_spec, observed_a0_digest=observed_a0_digest)
    )
    if compiled.bindings.a0_digest != observed_a0_digest:
        raise ValueError("compiled spec is not bound to the supplied A0")
    scans = tuple(
        scan(
            plan,
            observed_a0_digest,
            compiled.deterministic_cases(plan.claim_id),
        )
        for plan in compiled.deterministic_scanner_plans()
    )
    status = _aggregate(scans)
    all_routes = host_verifier_routes(compiled)
    effective_risk, selected, verification = _selected_routes(
        all_routes,
        RiskClass(risk),
        _failed_verifiers(scans),
    )
    decision = decide_shadow_route(
        bindings=compiled.bindings,
        risk=effective_risk,
        policy=route_policy,
        ev=ev,
        compiled_spec=compiled,
        obligation_ids=tuple(route.obligation_id for route in selected),
        verifier_routes=selected,
        verification=verification,
        remaining_cost_units=remaining_cost_units,
    )
    wrapped: ShadowRouteDecision | AdmittedShadowRouteDecision
    if admitted is None:
        wrapped = decision
    else:
        wrapped = AdmittedShadowRouteDecision(
            decision=decision,
            formalization_admission_digest=admitted.admission.admission_digest,
        )
    source_digest = digest(
        {
            "compilation_digest": compiled.compilation_digest,
            "scan_input_digests": tuple(item.input_digest for item in scans),
            "route_decision": decision.trace(),
        }
    )
    observation_digest, recorded = _record_route(
        ledger=route_ledger,
        decision=decision,
        selected_routes=selected,
        compiled=compiled,
        model_fingerprint_sha256=model_fingerprint_sha256,
        contract_fingerprint_sha256=contract_fingerprint_sha256,
        provider_fingerprints_sha256=provider_fingerprints_sha256,
        source_receipt_digest=source_digest,
    )
    return StructuredShadowResult(
        base_answer=base_answer,
        compiled=compiled,
        scans=scans,
        status=status,
        route=wrapped,
        route_observation_digest=observation_digest,
        route_observation_recorded=recorded,
    )


def finalize_external_candidate(
    shadow: StructuredShadowResult,
    request: HostActionRequest,
    *,
    candidate_answer: str,
    approval: HostCommitApproval | None = None,
) -> HostFinalizationResult:
    """Bind the existing host finalizer to the exact pipeline A0."""

    if not isinstance(shadow, StructuredShadowResult):
        raise TypeError("shadow must be StructuredShadowResult")
    if not isinstance(request, HostActionRequest):
        raise TypeError("request must be HostActionRequest")
    if request.base_digest != shadow.compiled.bindings.a0_digest:
        raise ValueError("host request is not bound to the pipeline A0")
    return finalize_host_answer(
        request,
        base_answer=shadow.base_answer,
        candidate_answer=candidate_answer,
        approval=approval,
    )
