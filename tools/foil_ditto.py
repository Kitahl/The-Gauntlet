"""Bounded, host-denied Ditto resolver for post-solve diagnostic needs.

This module selects only among the closed capability manifest and a small,
reviewed method-recipe registry. It never invokes a provider, tool, model,
network, subprocess, Gauntlet, or Mastermind runtime. A successful resolution
is an advisory host request, never execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from foil_candidate_state import (
    AuthorityIssuer,
    CandidateBinding,
    CandidateDecision,
    CandidateState,
)
from foil_capabilities import CAPABILITIES
from foil_tool_policy import route_claim
from foil_v5_metrics import DiagnosticCapabilityRequirement


class DittoDisposition(str, Enum):
    """Closed outcomes for diagnostic capability resolution."""

    USE = "USE"
    METHOD_ONLY = "METHOD_ONLY"
    SUGGEST = "SUGGEST"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MethodRecipe:
    """A static, reviewed method reference; never executable caller input."""

    recipe_id: str
    version: str
    required_capability: str
    summary: str

    def __post_init__(self) -> None:
        for name in ("recipe_id", "version", "required_capability", "summary"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if self.required_capability not in CAPABILITIES:
            raise ValueError("recipe required_capability must be a closed capability")


# This tuple is the only registry accepted by resolve_diagnostic_requirement.
# Entries describe host-reviewed methods, never executable code.
REVIEWED_METHOD_RECIPES: tuple[MethodRecipe, ...] = (
    MethodRecipe(
        recipe_id="deterministic-code-check-v1",
        version="1",
        required_capability="CODE_EXECUTION",
        summary="Run one host-reviewed deterministic, non-writing code check.",
    ),
)

_RECIPES_BY_ID = {recipe.recipe_id: recipe for recipe in REVIEWED_METHOD_RECIPES}
if len(_RECIPES_BY_ID) != len(REVIEWED_METHOD_RECIPES):
    raise RuntimeError("reviewed method recipe ids must be unique")


@dataclass(frozen=True)
class DittoResolution:
    """An advisory resolution that always leaves provider execution to the host."""

    disposition: DittoDisposition
    reason_code: str
    requirement_id: str
    required_capability: str
    candidate_state: CandidateState
    route_status: str | None = None
    provider_name: str | None = None
    recipe_id: str | None = None
    execution_authorized: bool = False
    host_action_required: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, DittoDisposition):
            raise TypeError("disposition must be DittoDisposition")
        if not isinstance(self.candidate_state, CandidateState):
            raise TypeError("candidate_state must be CandidateState")
        for name in ("reason_code", "requirement_id", "required_capability"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if self.route_status is not None and not isinstance(self.route_status, str):
            raise TypeError("route_status must be text or None")
        if self.provider_name is not None and not isinstance(self.provider_name, str):
            raise TypeError("provider_name must be text or None")
        if self.recipe_id is not None and self.recipe_id not in _RECIPES_BY_ID:
            raise ValueError("recipe_id must name a closed reviewed recipe")
        if self.execution_authorized is not False or self.host_action_required is not True:
            raise ValueError("Ditto resolution grants no execution authority")
        if self.disposition is DittoDisposition.USE:
            if self.candidate_state is not CandidateState.ACTIVE:
                raise ValueError("USE requires ACTIVE candidate state")
            if self.route_status != "READY" or not self.provider_name:
                raise ValueError("USE requires one READY exact route")
            if self.recipe_id is not None:
                raise ValueError("USE cannot carry a method recipe")
        if self.disposition is DittoDisposition.METHOD_ONLY:
            if self.candidate_state is not CandidateState.ACTIVE:
                raise ValueError("METHOD_ONLY requires ACTIVE candidate state")
            if self.route_status != "READY" or self.recipe_id is None:
                raise ValueError("METHOD_ONLY requires a READY route and closed recipe")
        if self.disposition is DittoDisposition.SUGGEST:
            if self.provider_name is not None or self.recipe_id is not None:
                raise ValueError("SUGGEST is display-only and names no provider or recipe")


def _candidate_state(value: CandidateDecision | CandidateState) -> CandidateState:
    if isinstance(value, CandidateDecision):
        if not isinstance(value.state, CandidateState):
            raise TypeError("candidate decision state must be CandidateState")
        return value.state
    if isinstance(value, CandidateState):
        return value
    raise TypeError("candidate must be CandidateDecision or CandidateState")


def _has_verified_active_authority(
    candidate: CandidateDecision | CandidateState,
    binding: CandidateBinding | None,
    issuer: AuthorityIssuer | None,
    now: str | None,
) -> bool:
    """Require host-issued, current authority for ACTIVE-only outcomes."""

    if not isinstance(candidate, CandidateDecision):
        return False
    if not isinstance(binding, CandidateBinding) or not isinstance(issuer, AuthorityIssuer):
        return False
    if not isinstance(now, str) or not now.strip() or candidate.token is None:
        return False
    try:
        return issuer.verify(
            candidate.token,
            binding,
            now=now,
            expected_state=CandidateState.ACTIVE,
        )
    except (TypeError, ValueError):
        return False


def _resolution(
    disposition: DittoDisposition,
    reason_code: str,
    requirement: DiagnosticCapabilityRequirement,
    state: CandidateState,
    *,
    route_status: str | None = None,
    provider_name: str | None = None,
    recipe_id: str | None = None,
) -> DittoResolution:
    return DittoResolution(
        disposition=disposition,
        reason_code=reason_code,
        requirement_id=requirement.requirement_id,
        required_capability=requirement.capability,
        candidate_state=state,
        route_status=route_status,
        provider_name=provider_name,
        recipe_id=recipe_id,
    )


def resolve_diagnostic_requirement(
    requirement: DiagnosticCapabilityRequirement,
    manifest: dict[str, Any],
    *,
    claim_type: str,
    candidate: CandidateDecision | CandidateState,
    binding: CandidateBinding | None = None,
    issuer: AuthorityIssuer | None = None,
    now: str | None = None,
    recipe_id: str | None = None,
) -> DittoResolution:
    """Resolve one exact diagnostic need without invoking the selected provider.

    ACTIVE-only results require an issuer-verified token bound to ``binding`` at
    ``now``. Raw states remain useful only for non-active display outcomes.
    The caller supplies the claim-route key because requirements record a
    capability, not a claim taxonomy; a different-capability fallback is no
    match.
    """

    if not isinstance(requirement, DiagnosticCapabilityRequirement):
        raise TypeError("requirement must be DiagnosticCapabilityRequirement")
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a dict")
    if not isinstance(claim_type, str) or not claim_type.strip():
        raise ValueError("claim_type must be non-empty text")
    if recipe_id is not None and (not isinstance(recipe_id, str) or not recipe_id.strip()):
        raise ValueError("recipe_id must be non-empty text or None")

    state = _candidate_state(candidate)
    required_capability = requirement.capability
    if required_capability not in CAPABILITIES:
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            "unknown_required_capability",
            requirement,
            state,
        )

    route = route_claim(manifest, claim_type, require_write=False)
    route_status = str(route.get("status") or "UNKNOWN")
    if route_status != "READY":
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            f"route_{route_status.lower()}",
            requirement,
            state,
            route_status=route_status,
        )

    routed_capability = route.get("capability")
    provider = route.get("provider")
    provider_name = provider.get("name") if isinstance(provider, Mapping) else None
    if (
        routed_capability != required_capability
        or not isinstance(provider_name, str)
        or not provider_name
    ):
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            "route_capability_mismatch",
            requirement,
            state,
            route_status=route_status,
        )

    if state is not CandidateState.ACTIVE:
        return _resolution(
            DittoDisposition.SUGGEST,
            "candidate_not_active",
            requirement,
            state,
            route_status=route_status,
        )

    if not _has_verified_active_authority(candidate, binding, issuer, now):
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            "active_authority_missing_or_invalid",
            requirement,
            state,
            route_status=route_status,
        )

    if recipe_id is None:
        return _resolution(
            DittoDisposition.USE,
            "ready_exact_capability",
            requirement,
            state,
            route_status=route_status,
            provider_name=provider_name,
        )

    recipe = _RECIPES_BY_ID.get(recipe_id)
    if recipe is None:
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            "recipe_not_reviewed",
            requirement,
            state,
            route_status=route_status,
        )
    if recipe.required_capability != required_capability:
        return _resolution(
            DittoDisposition.UNAVAILABLE,
            "recipe_capability_mismatch",
            requirement,
            state,
            route_status=route_status,
        )
    return _resolution(
        DittoDisposition.METHOD_ONLY,
        "ready_reviewed_recipe",
        requirement,
        state,
        route_status=route_status,
        provider_name=provider_name,
        recipe_id=recipe.recipe_id,
    )
