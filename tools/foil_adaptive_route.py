"""Default-off adaptive-compute routing over a frozen FOIL v5 answer.

The controller is deliberately advisory. ``DIRECT`` means retain immutable A0;
``VERIFY`` and ``FULL`` are host-facing shadow recommendations. This module has
no executor, provider, model, tool, network, scheduler, filesystem, authority
token, or answer-mutation surface.

Only obligations produced by the strict host-supplied declarative compiler may
create a verifier route. Free-form prose and model-generated obligations never
enter this controller.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from egrt_claims import ImmutableBindings
from egrt_types import digest
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus, VerifierResult
from foil_evidence import regularized_incomplete_beta
from foil_obligation_compiler import COMPILER_DIGEST, CompiledTaskSpec
from foil_signal_boundary import SignalAuthority

SCHEMA = "egrt.foil-adaptive-route.v1"
PPM = 1_000_000
PPM_SQUARED = PPM * PPM
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Route(str, Enum):
    DIRECT = "DIRECT"
    VERIFY = "VERIFY"
    FULL = "FULL"


class RiskClass(str, Enum):
    NONE = "NONE"
    ONE_FALSIFIABLE = "ONE_FALSIFIABLE"
    MULTIPLE_OR_CONTRADICTORY = "MULTIPLE_OR_CONTRADICTORY"
    VERIFIED_DEFECT = "VERIFIED_DEFECT"


class ObligationOrigin(str, Enum):
    HOST_DECLARED = "HOST_DECLARED"
    MODEL_GENERATED = "MODEL_GENERATED"


class DecisionReason(str, Enum):
    CONTROLLER_DISABLED = "CONTROLLER_DISABLED"
    NO_POSITIVE_VALUE_COMPLEMENT = "NO_POSITIVE_VALUE_COMPLEMENT"
    POSTERIOR_STAND_DOWN = "POSTERIOR_STAND_DOWN"
    CONDITIONAL_K2_PROBE = "CONDITIONAL_K2_PROBE"
    HOST_ROUTE_UNAVAILABLE = "HOST_ROUTE_UNAVAILABLE"
    GENERATED_OBLIGATION_INELIGIBLE = "GENERATED_OBLIGATION_INELIGIBLE"
    VERIFIER_RESULT_NOT_A_DEFECT = "VERIFIER_RESULT_NOT_A_DEFECT"
    COST_CAP_EXHAUSTED = "COST_CAP_EXHAUSTED"
    VERIFY_POSITIVE_VALUE = "VERIFY_POSITIVE_VALUE"
    FULL_POSITIVE_VALUE = "FULL_POSITIVE_VALUE"


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_ppm(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= PPM:
        raise ValueError(f"{name} must be an integer in [0, {PPM}]")
    return value


def _require_non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class FrozenEVModel:
    """Frozen, externally estimated route values in fixed-point units.

    Probabilities are parts per million. Utilities and cost penalties share one
    caller-declared micro-utility unit. The evidence digest binds the estimates;
    this class never fits them from route history.
    """

    base_correct_ppm: int
    verify_rescue_ppm: int
    verify_damage_ppm: int
    full_rescue_ppm: int
    full_damage_ppm: int
    rescue_utility_micro: int
    damage_disutility_micro: int
    cost_penalty_micro_per_unit: int
    verify_incremental_cost_units: int
    full_incremental_cost_units: int
    evidence_digest: str

    def __post_init__(self) -> None:
        for name in (
            "base_correct_ppm",
            "verify_rescue_ppm",
            "verify_damage_ppm",
            "full_rescue_ppm",
            "full_damage_ppm",
        ):
            _require_ppm(name, getattr(self, name))
        for name in (
            "rescue_utility_micro",
            "damage_disutility_micro",
            "cost_penalty_micro_per_unit",
            "verify_incremental_cost_units",
            "full_incremental_cost_units",
        ):
            _require_non_negative_int(name, getattr(self, name))
        _require_digest("evidence_digest", self.evidence_digest)

    def expected_value_numerator(self, route: Route) -> int:
        """Return exact EV numerator with denominator ``PPM_SQUARED``."""

        if route is Route.DIRECT:
            return 0
        if route is Route.VERIFY:
            rescue = self.verify_rescue_ppm
            damage = self.verify_damage_ppm
            cost = self.verify_incremental_cost_units
        elif route is Route.FULL:
            rescue = self.full_rescue_ppm
            damage = self.full_damage_ppm
            cost = self.full_incremental_cost_units
        else:  # pragma: no cover - exhaustive enum guard
            raise ValueError("unsupported route")
        q = self.base_correct_ppm
        benefit = (PPM - q) * rescue * self.rescue_utility_micro
        harm = q * damage * self.damage_disutility_micro
        cost_term = self.cost_penalty_micro_per_unit * cost * PPM_SQUARED
        return benefit - harm - cost_term

    def incremental_cost(self, route: Route) -> int:
        if route is Route.VERIFY:
            return self.verify_incremental_cost_units
        if route is Route.FULL:
            return self.full_incremental_cost_units
        return 0


@dataclass(frozen=True)
class ProbeModel:
    """Frozen value-of-information estimate for one conditional k=2 probe."""

    information_value_micro: int
    incremental_cost_units: int
    cost_penalty_micro_per_unit: int
    evidence_digest: str

    def __post_init__(self) -> None:
        for name in (
            "information_value_micro",
            "incremental_cost_units",
            "cost_penalty_micro_per_unit",
        ):
            _require_non_negative_int(name, getattr(self, name))
        _require_digest("evidence_digest", self.evidence_digest)

    @property
    def net_value_micro(self) -> int:
        return self.information_value_micro - (
            self.incremental_cost_units * self.cost_penalty_micro_per_unit
        )


@dataclass(frozen=True)
class CapabilityPosterior:
    """Count-backed route prior used only for optional stand-down.

    It is keyed to model, contract, and task regime. A contract mismatch or stale
    record has no authority. Item-specific falsifiable risks always outrank it.
    """

    correct: int
    incorrect: int
    model_fingerprint: str
    contract_fingerprint: str
    task_regime: str
    evidence_digest: str
    fresh: bool
    prior_a: float = 0.5
    prior_b: float = 0.5

    def __post_init__(self) -> None:
        _require_non_negative_int("correct", self.correct)
        _require_non_negative_int("incorrect", self.incorrect)
        for name in ("model_fingerprint", "contract_fingerprint", "evidence_digest"):
            _require_digest(name, getattr(self, name))
        if not isinstance(self.task_regime, str) or not self.task_regime.strip():
            raise ValueError("task_regime must be non-empty text")
        if not isinstance(self.fresh, bool):
            raise TypeError("fresh must be bool")
        if (
            isinstance(self.prior_a, bool)
            or isinstance(self.prior_b, bool)
            or not math.isfinite(self.prior_a)
            or not math.isfinite(self.prior_b)
            or self.prior_a <= 0
            or self.prior_b <= 0
        ):
            raise ValueError("prior parameters must be finite positive numbers")

    @property
    def observation_count(self) -> int:
        return self.correct + self.incorrect

    def mass_above(self, threshold_ppm: int) -> float:
        threshold = _require_ppm("threshold_ppm", threshold_ppm) / PPM
        if threshold <= 0.0:
            return 1.0
        if threshold >= 1.0:
            return 0.0
        return 1.0 - regularized_incomplete_beta(
            self.prior_a + self.correct,
            self.prior_b + self.incorrect,
            threshold,
        )


@dataclass(frozen=True)
class AdaptiveRoutePolicy:
    """Caller-owned rollout policy. Defaults cannot escalate or probe."""

    enabled: bool = False
    probe_enabled: bool = False
    stand_down_enabled: bool = False
    stand_down_accuracy_ppm: int | None = None
    stand_down_confidence_ppm: int | None = None
    stand_down_min_observations: int = 0

    def __post_init__(self) -> None:
        for name in ("enabled", "probe_enabled", "stand_down_enabled"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        _require_non_negative_int(
            "stand_down_min_observations", self.stand_down_min_observations
        )
        if self.stand_down_enabled:
            if self.stand_down_accuracy_ppm is None or self.stand_down_confidence_ppm is None:
                raise ValueError("stand-down thresholds must be explicit when enabled")
            _require_ppm("stand_down_accuracy_ppm", self.stand_down_accuracy_ppm)
            _require_ppm("stand_down_confidence_ppm", self.stand_down_confidence_ppm)
            if not 0 < self.stand_down_accuracy_ppm < PPM:
                raise ValueError("stand_down_accuracy_ppm must be strictly inside (0, PPM)")
            if not 0 < self.stand_down_confidence_ppm < PPM:
                raise ValueError("stand_down_confidence_ppm must be strictly inside (0, PPM)")
            if self.stand_down_min_observations <= 0:
                raise ValueError("stand_down_min_observations must be positive when enabled")


@dataclass(frozen=True)
class HostVerifierRoute:
    """Digest-only route derived from one compiler-created obligation case."""

    bindings: ImmutableBindings
    claim_id: str
    obligation_id: str
    verifier_id: str
    verifier_version: str
    verifier_input_digest: str
    compilation_digest: str
    compiler_digest: str = COMPILER_DIGEST
    origin: ObligationOrigin = ObligationOrigin.HOST_DECLARED

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        for name in ("claim_id", "obligation_id", "verifier_id", "verifier_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty text")
        for name in ("verifier_input_digest", "compilation_digest", "compiler_digest"):
            _require_digest(name, getattr(self, name))
        object.__setattr__(self, "origin", ObligationOrigin(self.origin))

    @property
    def route_digest(self) -> str:
        return digest(
            {
                "binding_digest": self.bindings.binding_digest,
                "claim_id": self.claim_id,
                "obligation_id": self.obligation_id,
                "verifier_id": self.verifier_id,
                "verifier_version": self.verifier_version,
                "verifier_input_digest": self.verifier_input_digest,
                "compilation_digest": self.compilation_digest,
                "compiler_digest": self.compiler_digest,
                "origin": self.origin.value,
            }
        )


@dataclass(frozen=True)
class ShadowRouteDecision:
    route: Route
    reason: DecisionReason
    a0_digest: str
    binding_digest: str
    expected_value_numerator: int
    verifier_route_digests: tuple[str, ...] = ()
    probe_resamples: int = 0
    final: bool = True
    shadow_only: bool = True
    execution_authorized: bool = False
    base_answer_preserved: bool = True
    host_action_required: bool = True
    routing_signal_authority: SignalAuthority = SignalAuthority.CONTROL_ONLY

    def __post_init__(self) -> None:
        object.__setattr__(self, "route", Route(self.route))
        object.__setattr__(self, "reason", DecisionReason(self.reason))
        _require_digest("a0_digest", self.a0_digest)
        _require_digest("binding_digest", self.binding_digest)
        if isinstance(self.expected_value_numerator, bool) or not isinstance(
            self.expected_value_numerator, int
        ):
            raise TypeError("expected_value_numerator must be int")
        if not isinstance(self.verifier_route_digests, tuple):
            raise TypeError("verifier_route_digests must be tuple")
        for value in self.verifier_route_digests:
            _require_digest("verifier_route_digest", value)
        if self.probe_resamples not in {0, 2}:
            raise ValueError("probe_resamples must be 0 or 2")
        if not all(
            (
                self.shadow_only,
                not self.execution_authorized,
                self.base_answer_preserved,
                self.host_action_required,
                self.routing_signal_authority is SignalAuthority.CONTROL_ONLY,
            )
        ):
            raise ValueError("adaptive route decisions must remain host-denied shadow signals")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": SCHEMA,
            "route": self.route.value,
            "reason": self.reason.value,
            "a0_digest": self.a0_digest,
            "binding_digest": self.binding_digest,
            "expected_value_numerator": self.expected_value_numerator,
            "expected_value_denominator": PPM_SQUARED,
            "verifier_route_digests": list(self.verifier_route_digests),
            "probe_resamples": self.probe_resamples,
            "final": self.final,
            "shadow_only": self.shadow_only,
            "execution_authorized": self.execution_authorized,
            "base_answer_preserved": self.base_answer_preserved,
            "host_action_required": self.host_action_required,
            "routing_signal_authority": self.routing_signal_authority.value,
            "raw_answer_stored": False,
            "raw_obligation_stored": False,
        }
        body["decision_sha256"] = digest(body)
        return body


def make_host_verifier_route(
    compiled: CompiledTaskSpec, *, claim_id: str, obligation_id: str
) -> HostVerifierRoute:
    """Select one deterministic compiler route; arbitrary verifier IDs are impossible."""

    if not isinstance(compiled, CompiledTaskSpec):
        raise TypeError("compiled must be CompiledTaskSpec")
    for claim in compiled.claims:
        if claim.claim_id != claim_id:
            continue
        for bundle in claim.obligations:
            if bundle.obligation.obligation_id != obligation_id:
                continue
            if not bundle.deterministic or bundle.case is None:
                raise ValueError("obligation has no applicable deterministic verifier route")
            verifier = DEFAULT_REGISTRY.resolve(bundle.need.verifier_id)
            if verifier.version != bundle.verifier_version:
                raise ValueError("compiler route verifier version is not current")
            return HostVerifierRoute(
                bindings=compiled.bindings,
                claim_id=claim_id,
                obligation_id=obligation_id,
                verifier_id=verifier.verifier_id,
                verifier_version=verifier.version,
                verifier_input_digest=digest(bundle.case.verifier_input),
                compilation_digest=compiled.compilation_digest,
            )
    raise KeyError("unknown compiled claim or obligation")


def host_verifier_routes(compiled: CompiledTaskSpec) -> tuple[HostVerifierRoute, ...]:
    """Return every executable host-declared route retained by the compiler."""

    if not isinstance(compiled, CompiledTaskSpec):
        raise TypeError("compiled must be CompiledTaskSpec")
    routes: list[HostVerifierRoute] = []
    for claim in compiled.claims:
        for bundle in claim.obligations:
            if bundle.deterministic and bundle.case is not None:
                routes.append(
                    make_host_verifier_route(
                        compiled,
                        claim_id=claim.claim_id,
                        obligation_id=bundle.obligation.obligation_id,
                    )
                )
    return tuple(routes)


def _direct(
    bindings: ImmutableBindings,
    reason: DecisionReason,
    *,
    expected_value_numerator: int = 0,
) -> ShadowRouteDecision:
    return ShadowRouteDecision(
        route=Route.DIRECT,
        reason=reason,
        a0_digest=bindings.a0_digest,
        binding_digest=bindings.binding_digest,
        expected_value_numerator=expected_value_numerator,
    )


def _routes_match_compiled_spec(
    bindings: ImmutableBindings,
    compiled_spec: CompiledTaskSpec | None,
    obligation_ids: Sequence[str],
    verifier_routes: Sequence[HostVerifierRoute],
) -> bool:
    if not isinstance(compiled_spec, CompiledTaskSpec):
        return False
    if compiled_spec.bindings != bindings or bindings.compiler_digest != COMPILER_DIGEST:
        return False
    if not obligation_ids or len(set(obligation_ids)) != len(obligation_ids):
        return False
    by_obligation = {route.obligation_id: route for route in verifier_routes}
    if len(by_obligation) != len(verifier_routes) or set(obligation_ids) != set(by_obligation):
        return False
    try:
        compiled_routes = {
            (route.claim_id, route.obligation_id): route
            for route in host_verifier_routes(compiled_spec)
        }
    except (KeyError, TypeError, ValueError):
        return False
    return all(
        route.origin is ObligationOrigin.HOST_DECLARED
        and compiled_routes.get((route.claim_id, route.obligation_id)) == route
        for route in verifier_routes
    )


def _matching_failed_verification(
    route: HostVerifierRoute, verification: VerifierResult | None
) -> bool:
    return bool(
        verification is not None
        and verification.verifier_id == route.verifier_id
        and verification.verifier_version == route.verifier_version
        and verification.input_digest == route.verifier_input_digest
        and verification.status is VerificationStatus.FAIL
    )


def _posterior_stands_down(
    policy: AdaptiveRoutePolicy,
    posterior: CapabilityPosterior | None,
    *,
    model_fingerprint: str,
    contract_fingerprint: str,
    task_regime: str,
) -> bool:
    if not policy.stand_down_enabled or posterior is None or not posterior.fresh:
        return False
    if (
        posterior.model_fingerprint != model_fingerprint
        or posterior.contract_fingerprint != contract_fingerprint
        or posterior.task_regime != task_regime
        or posterior.observation_count <= 0
        or posterior.observation_count < policy.stand_down_min_observations
    ):
        return False
    assert policy.stand_down_accuracy_ppm is not None
    assert policy.stand_down_confidence_ppm is not None
    return posterior.mass_above(policy.stand_down_accuracy_ppm) >= (
        policy.stand_down_confidence_ppm / PPM
    )


def decide_shadow_route(
    *,
    bindings: ImmutableBindings,
    risk: RiskClass,
    policy: AdaptiveRoutePolicy = AdaptiveRoutePolicy(),
    ev: FrozenEVModel | None = None,
    compiled_spec: CompiledTaskSpec | None = None,
    obligation_ids: tuple[str, ...] = (),
    verifier_routes: tuple[HostVerifierRoute, ...] = (),
    verification: VerifierResult | None = None,
    remaining_cost_units: int | None = None,
    borderline: bool = False,
    probe: ProbeModel | None = None,
    posterior: CapabilityPosterior | None = None,
    model_fingerprint: str | None = None,
    contract_fingerprint: str | None = None,
    task_regime: str | None = None,
) -> ShadowRouteDecision:
    """Return one deterministic, non-executing recommendation over frozen A0."""

    if not isinstance(bindings, ImmutableBindings):
        raise TypeError("bindings must be ImmutableBindings")
    risk = RiskClass(risk)
    if remaining_cost_units is not None:
        _require_non_negative_int("remaining_cost_units", remaining_cost_units)
    if not isinstance(borderline, bool):
        raise TypeError("borderline must be bool")
    if not policy.enabled:
        return _direct(bindings, DecisionReason.CONTROLLER_DISABLED)

    if risk is RiskClass.NONE:
        if posterior is not None:
            if model_fingerprint is None or contract_fingerprint is None or task_regime is None:
                return _direct(bindings, DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT)
            _require_digest("model_fingerprint", model_fingerprint)
            _require_digest("contract_fingerprint", contract_fingerprint)
            if _posterior_stands_down(
                policy,
                posterior,
                model_fingerprint=model_fingerprint,
                contract_fingerprint=contract_fingerprint,
                task_regime=task_regime,
            ):
                return _direct(bindings, DecisionReason.POSTERIOR_STAND_DOWN)
        if policy.probe_enabled and borderline and probe is not None:
            if remaining_cost_units is not None and probe.incremental_cost_units > remaining_cost_units:
                return _direct(bindings, DecisionReason.COST_CAP_EXHAUSTED)
            if probe.net_value_micro > 0:
                return ShadowRouteDecision(
                    route=Route.DIRECT,
                    reason=DecisionReason.CONDITIONAL_K2_PROBE,
                    a0_digest=bindings.a0_digest,
                    binding_digest=bindings.binding_digest,
                    expected_value_numerator=probe.net_value_micro * PPM_SQUARED,
                    probe_resamples=2,
                    final=False,
                )
        return _direct(bindings, DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT)

    if not verifier_routes or not _routes_match_compiled_spec(
        bindings, compiled_spec, obligation_ids, verifier_routes
    ):
        if any(route.origin is ObligationOrigin.MODEL_GENERATED for route in verifier_routes):
            return _direct(bindings, DecisionReason.GENERATED_OBLIGATION_INELIGIBLE)
        return _direct(bindings, DecisionReason.HOST_ROUTE_UNAVAILABLE)

    if ev is None:
        return _direct(bindings, DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT)

    if risk is RiskClass.ONE_FALSIFIABLE:
        if len(verifier_routes) != 1:
            return _direct(bindings, DecisionReason.HOST_ROUTE_UNAVAILABLE)
        candidate = Route.VERIFY
    elif risk is RiskClass.MULTIPLE_OR_CONTRADICTORY:
        if len(verifier_routes) < 2:
            return _direct(bindings, DecisionReason.HOST_ROUTE_UNAVAILABLE)
        candidate = Route.FULL
    else:
        if len(verifier_routes) != 1 or not _matching_failed_verification(
            verifier_routes[0], verification
        ):
            return _direct(bindings, DecisionReason.VERIFIER_RESULT_NOT_A_DEFECT)
        candidate = Route.FULL

    expected = ev.expected_value_numerator(candidate)
    if remaining_cost_units is not None and ev.incremental_cost(candidate) > remaining_cost_units:
        return _direct(
            bindings,
            DecisionReason.COST_CAP_EXHAUSTED,
            expected_value_numerator=expected,
        )
    if expected <= 0:
        return _direct(
            bindings,
            DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT,
            expected_value_numerator=expected,
        )
    return ShadowRouteDecision(
        route=candidate,
        reason=(
            DecisionReason.VERIFY_POSITIVE_VALUE
            if candidate is Route.VERIFY
            else DecisionReason.FULL_POSITIVE_VALUE
        ),
        a0_digest=bindings.a0_digest,
        binding_digest=bindings.binding_digest,
        expected_value_numerator=expected,
        verifier_route_digests=tuple(route.route_digest for route in verifier_routes),
    )
