"""Default-off observational RouteVector ledger for FOIL adaptive compute.

The ledger retains exact-route observations for later analysis. It never ranks,
selects, fits, or updates a controller and never allocates causal credit among a
route's provider, compute, verifier, or retry components. Normal execution data
is observational even when its outcome was mechanically verified.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from egrt_types import digest
from egrt_verifiers import DEFAULT_REGISTRY
from foil_adaptive_route import Route

SCHEMA = "egrt.foil-shadow-route-ledger.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AssignmentDesign(str, Enum):
    OBSERVATIONAL = "OBSERVATIONAL"
    MATCHED = "MATCHED"
    RANDOMIZED = "RANDOMIZED"


class OutcomeKind(str, Enum):
    RESCUE = "RESCUE"
    NEUTRAL = "NEUTRAL"
    DAMAGE = "DAMAGE"
    UNKNOWN = "UNKNOWN"


class EligibilityReason(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    POLICY_DISABLED = "POLICY_DISABLED"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    COST_CAP_EXHAUSTED = "COST_CAP_EXHAUSTED"
    NO_POSITIVE_VALUE_COMPLEMENT = "NO_POSITIVE_VALUE_COMPLEMENT"
    UNKNOWN = "UNKNOWN"


class Attribution(str, Enum):
    OBSERVATIONAL_ONLY = "OBSERVATIONAL_ONLY"


class RouteLedgerError(ValueError):
    """A route observation or sealed receipt violates the shadow contract."""


def _require_digest(name: str, value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RouteLedgerError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RouteLedgerError(f"{name} must be non-empty text")
    return value


@dataclass(frozen=True)
class RouteVector:
    compute_mode: Route
    provider_fingerprints_sha256: tuple[str, ...]
    verifier_id: str | None
    verifier_version: str | None
    retry_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "compute_mode", Route(self.compute_mode))
        if not isinstance(self.provider_fingerprints_sha256, tuple):
            raise RouteLedgerError("provider_fingerprints_sha256 must be a tuple")
        for provider_fingerprint in self.provider_fingerprints_sha256:
            _require_digest("provider_fingerprint_sha256", provider_fingerprint)
        if len(set(self.provider_fingerprints_sha256)) != len(
            self.provider_fingerprints_sha256
        ):
            raise RouteLedgerError("provider fingerprints must not contain duplicates")
        if (self.verifier_id is None) != (self.verifier_version is None):
            raise RouteLedgerError("verifier id and version must be present together")
        if self.verifier_id is not None:
            _require_text("verifier_id", self.verifier_id)
            _require_text("verifier_version", self.verifier_version)
            try:
                verifier = DEFAULT_REGISTRY.resolve(self.verifier_id)
            except KeyError as exc:
                raise RouteLedgerError("verifier_id is not in the closed registry") from exc
            if verifier.version != self.verifier_version:
                raise RouteLedgerError("verifier_version does not match the closed registry")
        if (
            isinstance(self.retry_count, bool)
            or not isinstance(self.retry_count, int)
            or self.retry_count < 0
        ):
            raise RouteLedgerError("retry_count must be a non-negative integer")

    def body(self) -> dict[str, object]:
        return {
            "compute_mode": self.compute_mode.value,
            "provider_fingerprints_sha256": list(self.provider_fingerprints_sha256),
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "retry_count": self.retry_count,
        }

    @property
    def route_digest(self) -> str:
        return digest(self.body())


@dataclass(frozen=True)
class EligibilityTrace:
    task_signature_sha256: str
    model_fingerprint_sha256: str
    contract_fingerprint_sha256: str
    route: RouteVector
    eligible: bool
    reason_code: EligibilityReason

    def __post_init__(self) -> None:
        for name in (
            "task_signature_sha256",
            "model_fingerprint_sha256",
            "contract_fingerprint_sha256",
        ):
            _require_digest(name, getattr(self, name))
        if not isinstance(self.route, RouteVector):
            raise TypeError("route must be RouteVector")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be bool")
        object.__setattr__(self, "reason_code", EligibilityReason(self.reason_code))

    def body(self) -> dict[str, object]:
        return {
            "task_signature_sha256": self.task_signature_sha256,
            "model_fingerprint_sha256": self.model_fingerprint_sha256,
            "contract_fingerprint_sha256": self.contract_fingerprint_sha256,
            "route": self.route.body(),
            "eligible": self.eligible,
            "reason_code": self.reason_code.value,
        }

    @property
    def eligibility_digest(self) -> str:
        return digest(self.body())


@dataclass(frozen=True)
class ShadowRouteObservation:
    eligibility: EligibilityTrace
    proposed: RouteVector
    observed: RouteVector | None
    outcome_kind: OutcomeKind
    verified: bool | None
    final_success: bool | None
    source_receipt_digest: str
    cost_receipt_digest: str | None = None
    latency_ms: float | None = None
    assignment_design: AssignmentDesign = AssignmentDesign.OBSERVATIONAL
    assignment_digest: str | None = None
    attribution: Attribution = Attribution.OBSERVATIONAL_ONLY
    component_credit: int = 0
    execution_authorized: bool = False
    controller_update_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.eligibility, EligibilityTrace):
            raise TypeError("eligibility must be EligibilityTrace")
        if not isinstance(self.proposed, RouteVector):
            raise TypeError("proposed must be RouteVector")
        if self.observed is not None and not isinstance(self.observed, RouteVector):
            raise TypeError("observed must be RouteVector or None")
        object.__setattr__(self, "outcome_kind", OutcomeKind(self.outcome_kind))
        object.__setattr__(self, "assignment_design", AssignmentDesign(self.assignment_design))
        object.__setattr__(self, "attribution", Attribution(self.attribution))
        for name in ("verified", "final_success"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool or None")
        _require_digest("source_receipt_digest", self.source_receipt_digest)
        _require_digest("cost_receipt_digest", self.cost_receipt_digest, optional=True)
        _require_digest("assignment_digest", self.assignment_digest, optional=True)
        if self.assignment_design is AssignmentDesign.OBSERVATIONAL:
            if self.assignment_digest is not None:
                raise RouteLedgerError(
                    "observational records cannot claim a matched/random assignment"
                )
        elif self.assignment_digest is None:
            raise RouteLedgerError("matched/randomized records require assignment_digest")
        if self.latency_ms is not None:
            if (
                isinstance(self.latency_ms, bool)
                or not isinstance(self.latency_ms, (int, float))
                or not math.isfinite(float(self.latency_ms))
                or float(self.latency_ms) < 0
            ):
                raise RouteLedgerError("latency_ms must be finite and non-negative or None")
        if self.eligibility.route != self.proposed:
            raise RouteLedgerError("eligibility trace must bind the proposed route")
        if self.attribution is not Attribution.OBSERVATIONAL_ONLY or self.component_credit != 0:
            raise RouteLedgerError("normal route observations cannot allocate component credit")
        if self.execution_authorized or self.controller_update_authorized:
            raise RouteLedgerError("shadow route records cannot authorize execution or learning")

    def body(self) -> dict[str, object]:
        return {
            "eligibility": self.eligibility.body(),
            "eligibility_digest": self.eligibility.eligibility_digest,
            "proposed": self.proposed.body(),
            "proposed_route_digest": self.proposed.route_digest,
            "observed": self.observed.body() if self.observed is not None else None,
            "observed_route_digest": (
                self.observed.route_digest if self.observed is not None else None
            ),
            "outcome_kind": self.outcome_kind.value,
            "verified": self.verified,
            "final_success": self.final_success,
            "source_receipt_digest": self.source_receipt_digest,
            "cost_receipt_digest": self.cost_receipt_digest,
            "latency_ms": self.latency_ms,
            "assignment_design": self.assignment_design.value,
            "assignment_digest": self.assignment_digest,
            "attribution": self.attribution.value,
            "component_credit": self.component_credit,
            "execution_authorized": self.execution_authorized,
            "controller_update_authorized": self.controller_update_authorized,
            "raw_prompt_stored": False,
            "raw_answer_stored": False,
        }

    @property
    def observation_digest(self) -> str:
        return digest(self.body())


class ShadowRouteVectorLedger:
    """In-memory shadow ledger. The disabled default records nothing."""

    def __init__(self, *, enabled: bool = False) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be bool")
        self._enabled = enabled
        self._observations: list[ShadowRouteObservation] = []
        self._sealed_receipt: dict[str, object] | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def append(self, observation: ShadowRouteObservation) -> bool:
        """Append when explicitly enabled; return False without mutation otherwise."""

        if not isinstance(observation, ShadowRouteObservation):
            raise TypeError("observation must be ShadowRouteObservation")
        if self._sealed_receipt is not None:
            raise RouteLedgerError("sealed route ledger is immutable")
        if not self._enabled:
            return False
        self._observations.append(observation)
        return True

    def records_for(
        self, eligibility: EligibilityTrace, route: RouteVector
    ) -> tuple[ShadowRouteObservation, ...]:
        """Return only exact task/model/contract/route matches."""

        if not isinstance(eligibility, EligibilityTrace):
            raise TypeError("eligibility must be EligibilityTrace")
        if not isinstance(route, RouteVector):
            raise TypeError("route must be RouteVector")
        if eligibility.route != route:
            raise RouteLedgerError("eligibility trace must bind the queried route")
        return tuple(
            row
            for row in self._observations
            if row.eligibility.eligibility_digest == eligibility.eligibility_digest
            and row.proposed == route
        )

    def predictive_summary(
        self, eligibility: EligibilityTrace, route: RouteVector
    ) -> dict[str, object]:
        """Describe an exact route without treating selection-biased data as causal."""

        rows = self.records_for(eligibility, route)
        successes = sum(row.final_success is True for row in rows)
        failures = sum(row.final_success is False for row in rows)
        unknown = len(rows) - successes - failures
        return {
            "route_digest": route.route_digest,
            "observed_count": len(rows),
            "success_count": successes,
            "failure_count": failures,
            "unknown_count": unknown,
            "exact_route_only": True,
            "causal_claim_authorized": False,
            "controller_update_authorized": False,
            "component_credit_allocated": False,
        }

    def seal(self) -> dict[str, object]:
        if self._sealed_receipt is not None:
            return copy.deepcopy(self._sealed_receipt)
        records = []
        for observation in self._observations:
            body = observation.body()
            records.append({**body, "observation_digest": observation.observation_digest})
        receipt: dict[str, object] = {
            "schema": SCHEMA,
            "enabled": self._enabled,
            "record_count": len(records),
            "records": copy.deepcopy(records),
            "shadow_only": True,
            "execution_authorized": False,
            "controller_update_authorized": False,
            "component_credit_allocated": False,
        }
        receipt["receipt_sha256"] = digest(receipt)
        verify_shadow_route_receipt(receipt)
        self._sealed_receipt = copy.deepcopy(receipt)
        return copy.deepcopy(receipt)


_ROUTE_FIELDS = {
    "compute_mode",
    "provider_fingerprints_sha256",
    "verifier_id",
    "verifier_version",
    "retry_count",
}
_ELIGIBILITY_FIELDS = {
    "task_signature_sha256",
    "model_fingerprint_sha256",
    "contract_fingerprint_sha256",
    "route",
    "eligible",
    "reason_code",
}
_OBSERVATION_FIELDS = {
    "eligibility",
    "eligibility_digest",
    "proposed",
    "proposed_route_digest",
    "observed",
    "observed_route_digest",
    "outcome_kind",
    "verified",
    "final_success",
    "source_receipt_digest",
    "cost_receipt_digest",
    "latency_ms",
    "assignment_design",
    "assignment_digest",
    "attribution",
    "component_credit",
    "execution_authorized",
    "controller_update_authorized",
    "raw_prompt_stored",
    "raw_answer_stored",
}


def _route_from_body(value: object) -> RouteVector:
    if not isinstance(value, Mapping) or set(value) != _ROUTE_FIELDS:
        raise RouteLedgerError("route vector has unknown or missing fields")
    providers = value.get("provider_fingerprints_sha256")
    if not isinstance(providers, list):
        raise RouteLedgerError("route provider fingerprints must be a list")
    try:
        route = RouteVector(
            compute_mode=value["compute_mode"],
            provider_fingerprints_sha256=tuple(providers),
            verifier_id=value["verifier_id"],
            verifier_version=value["verifier_version"],
            retry_count=value["retry_count"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RouteLedgerError("route vector is invalid") from exc
    if route.body() != dict(value):
        raise RouteLedgerError("route vector is not canonical")
    return route


def _eligibility_from_body(value: object) -> EligibilityTrace:
    if not isinstance(value, Mapping) or set(value) != _ELIGIBILITY_FIELDS:
        raise RouteLedgerError("eligibility trace has unknown or missing fields")
    try:
        trace = EligibilityTrace(
            task_signature_sha256=value["task_signature_sha256"],
            model_fingerprint_sha256=value["model_fingerprint_sha256"],
            contract_fingerprint_sha256=value["contract_fingerprint_sha256"],
            route=_route_from_body(value["route"]),
            eligible=value["eligible"],
            reason_code=value["reason_code"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RouteLedgerError("eligibility trace is invalid") from exc
    if trace.body() != dict(value):
        raise RouteLedgerError("eligibility trace is not canonical")
    return trace


def _observation_from_body(value: object) -> ShadowRouteObservation:
    if not isinstance(value, Mapping) or set(value) != _OBSERVATION_FIELDS:
        raise RouteLedgerError("route observation has unknown or missing fields")
    if value.get("raw_prompt_stored") is not False or value.get("raw_answer_stored") is not False:
        raise RouteLedgerError("route observation cannot contain raw prompt or answer data")
    observed_value = value.get("observed")
    try:
        observation = ShadowRouteObservation(
            eligibility=_eligibility_from_body(value["eligibility"]),
            proposed=_route_from_body(value["proposed"]),
            observed=None if observed_value is None else _route_from_body(observed_value),
            outcome_kind=value["outcome_kind"],
            verified=value["verified"],
            final_success=value["final_success"],
            source_receipt_digest=value["source_receipt_digest"],
            cost_receipt_digest=value["cost_receipt_digest"],
            latency_ms=value["latency_ms"],
            assignment_design=value["assignment_design"],
            assignment_digest=value["assignment_digest"],
            attribution=value["attribution"],
            component_credit=value["component_credit"],
            execution_authorized=value["execution_authorized"],
            controller_update_authorized=value["controller_update_authorized"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RouteLedgerError("route observation is invalid") from exc
    if value["eligibility_digest"] != observation.eligibility.eligibility_digest:
        raise RouteLedgerError("eligibility digest mismatch")
    if value["proposed_route_digest"] != observation.proposed.route_digest:
        raise RouteLedgerError("proposed route digest mismatch")
    expected_observed_digest = (
        observation.observed.route_digest if observation.observed is not None else None
    )
    if value["observed_route_digest"] != expected_observed_digest:
        raise RouteLedgerError("observed route digest mismatch")
    if observation.body() != dict(value):
        raise RouteLedgerError("route observation is not canonical")
    return observation


def verify_shadow_route_receipt(receipt: Mapping[str, Any]) -> None:
    """Reject tampering, extra authority, and structurally incomplete seals."""

    if not isinstance(receipt, Mapping) or receipt.get("schema") != SCHEMA:
        raise RouteLedgerError("route ledger schema is invalid")
    expected_fields = {
        "schema",
        "enabled",
        "record_count",
        "records",
        "shadow_only",
        "execution_authorized",
        "controller_update_authorized",
        "component_credit_allocated",
        "receipt_sha256",
    }
    if set(receipt) != expected_fields:
        raise RouteLedgerError("route ledger has unknown or missing fields")
    expected_digest = _require_digest("receipt_sha256", receipt.get("receipt_sha256"))
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if digest(unsigned) != expected_digest:
        raise RouteLedgerError("route ledger digest mismatch")
    if receipt.get("shadow_only") is not True:
        raise RouteLedgerError("route ledger must remain shadow-only")
    if receipt.get("execution_authorized") is not False:
        raise RouteLedgerError("route ledger cannot authorize execution")
    if receipt.get("controller_update_authorized") is not False:
        raise RouteLedgerError("route ledger cannot update the controller")
    if receipt.get("component_credit_allocated") is not False:
        raise RouteLedgerError("route ledger cannot allocate component credit")
    records = receipt.get("records")
    count = receipt.get("record_count")
    if not isinstance(records, list) or isinstance(count, bool) or count != len(records):
        raise RouteLedgerError("route ledger record count is inconsistent")
    if not isinstance(receipt.get("enabled"), bool):
        raise RouteLedgerError("route ledger enabled flag must be bool")
    if receipt.get("enabled") is False and records:
        raise RouteLedgerError("disabled route ledger cannot contain records")
    expected_record_fields = _OBSERVATION_FIELDS | {"observation_digest"}
    for row in records:
        if not isinstance(row, Mapping) or set(row) != expected_record_fields:
            raise RouteLedgerError("route ledger record has unknown or missing fields")
        recorded_digest = _require_digest("observation_digest", row.get("observation_digest"))
        body = {key: value for key, value in row.items() if key != "observation_digest"}
        if digest(body) != recorded_digest:
            raise RouteLedgerError("route observation digest mismatch")
        _observation_from_body(body)
