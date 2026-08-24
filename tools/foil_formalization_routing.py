"""Adaptive-route adapter for formally admitted generated obligation specs.

The core adaptive controller intentionally accepts compiler-owned host routes
only.  This adapter preserves that closed controller and adds the missing
upstream proof obligation: a generated spec must first carry a valid
``FormalizationAdmissionReceipt`` bound to the compiled spec.  The returned
wrapper keeps the generated origin visible and grants no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from egrt_types import digest
from foil_adaptive_route import (
    AdaptiveRoutePolicy,
    CapabilityPosterior,
    FrozenEVModel,
    ProbeModel,
    RiskClass,
    ShadowRouteDecision,
    decide_shadow_route,
    host_verifier_routes,
)
from foil_formalization_admission import (
    AdmittedCompiledTaskSpec,
    FormalizationAdmissionStatus,
)


@dataclass(frozen=True)
class AdmittedShadowRouteDecision:
    decision: ShadowRouteDecision
    formalization_admission_digest: str
    origin: str = field(default="ADMITTED_GENERATED", init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ShadowRouteDecision):
            raise TypeError("decision must be ShadowRouteDecision")
        if (
            not isinstance(self.formalization_admission_digest, str)
            or len(self.formalization_admission_digest) != 64
            or any(
                char not in "0123456789abcdef"
                for char in self.formalization_admission_digest
            )
        ):
            raise ValueError(
                "formalization_admission_digest must be a lowercase SHA-256 digest"
            )
        if self.execution_authorized:
            raise ValueError("admitted generated routes remain shadow-only")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "origin": self.origin,
            "formalization_admission_digest": self.formalization_admission_digest,
            "decision": self.decision.trace(),
            "execution_authorized": self.execution_authorized,
            "host_action_required": True,
        }
        body["trace_sha256"] = digest(body)
        return body


def decide_admitted_shadow_route(
    admitted: AdmittedCompiledTaskSpec,
    *,
    risk: RiskClass,
    policy: AdaptiveRoutePolicy = AdaptiveRoutePolicy(),
    ev: FrozenEVModel | None = None,
    obligation_ids: tuple[str, ...] = (),
    verification=None,
    remaining_cost_units: int | None = None,
    borderline: bool = False,
    probe: ProbeModel | None = None,
    posterior: CapabilityPosterior | None = None,
    model_fingerprint: str | None = None,
    contract_fingerprint: str | None = None,
    task_regime: str | None = None,
) -> AdmittedShadowRouteDecision:
    """Run the unchanged controller only after generated-spec admission."""

    if not isinstance(admitted, AdmittedCompiledTaskSpec):
        raise TypeError("admitted must be AdmittedCompiledTaskSpec")
    if admitted.admission.status is not FormalizationAdmissionStatus.ADMITTED:
        raise ValueError("generated obligation route is not admitted")
    compiled = admitted.compiled
    requested = set(obligation_ids)
    routes = tuple(
        route
        for route in host_verifier_routes(compiled)
        if route.obligation_id in requested
    )
    decision = decide_shadow_route(
        bindings=compiled.bindings,
        risk=risk,
        policy=policy,
        ev=ev,
        compiled_spec=compiled,
        obligation_ids=obligation_ids,
        verifier_routes=routes,
        verification=verification,
        remaining_cost_units=remaining_cost_units,
        borderline=borderline,
        probe=probe,
        posterior=posterior,
        model_fingerprint=model_fingerprint,
        contract_fingerprint=contract_fingerprint,
        task_regime=task_regime,
    )
    return AdmittedShadowRouteDecision(
        decision=decision,
        formalization_admission_digest=admitted.admission.admission_digest,
    )
