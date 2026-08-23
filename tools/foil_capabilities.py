"""Authoritative FOIL capability and claim-routing registry.

This is intentionally small. Provider names belong in host manifests; this file
only defines semantic capabilities and which claim types require them. Keeping
one runtime registry prevents the skill, router, and tests from silently drifting.
"""
from __future__ import annotations

from typing import Any

CAPABILITIES: dict[str, dict[str, Any]] = {
    "TEXT_GENERATION": {
        "authority_ceiling": "model output; carries no evidential authority of its own",
        "writes": False,
    },
    "REASONING": {
        "authority_ceiling": "model reasoning; a claim still needs a claim-native verifier",
        "writes": False,
    },
    "WEB_SEARCH": {
        "authority_ceiling": "source discovery/evidence; authority depends on retrieved source",
        "writes": False,
    },
    "DEEP_RESEARCH": {
        "authority_ceiling": "synthesis/discovery; underlying sources retain authority",
        "writes": False,
    },
    "SCHOLARLY_SEARCH": {
        "authority_ceiling": "literature discovery/evidence; paper scope controls claim",
        "writes": False,
    },
    "FILES_LIBRARY": {
        "authority_ceiling": "source evidence within supplied/connected files",
        "writes": False,
    },
    "REPOSITORY": {
        "authority_ceiling": "repository/source evidence",
        "writes": False,
    },
    "CODE_EXECUTION": {
        "authority_ceiling": "executable evidence for the executed environment",
        "writes": False,
    },
    "SYMBOLIC_COMPUTATION": {
        "authority_ceiling": "computational evidence within tool assumptions",
        "writes": False,
    },
    "FORMAL_PROOF": {
        "authority_ceiling": "formal evidence within checker/axiom/version boundary",
        "writes": False,
    },
    "DATABASE": {
        "authority_ceiling": "project/data evidence within queried state",
        "writes": False,
    },
    "VISION": {
        "authority_ceiling": "visual observation; may require source/native verification",
        "writes": False,
    },
}

# Ordered by minimum-sufficient preference. A later capability is a fallback,
# not an instruction to invoke every provider.
CLAIM_ROUTES: dict[str, tuple[str, ...]] = {
    "model_generation": ("TEXT_GENERATION",),
    "model_reasoning": ("REASONING", "TEXT_GENERATION"),
    "independent_review": ("REASONING", "TEXT_GENERATION"),
    "current_fact": ("WEB_SEARCH",),
    "prior_art": ("SCHOLARLY_SEARCH", "WEB_SEARCH"),
    "scholarly_claim": ("SCHOLARLY_SEARCH",),
    "broad_research": ("DEEP_RESEARCH", "SCHOLARLY_SEARCH", "WEB_SEARCH"),
    "user_file": ("FILES_LIBRARY",),
    "repository_state": ("REPOSITORY",),
    "software_behavior": ("CODE_EXECUTION",),
    "numeric_computation": ("CODE_EXECUTION", "SYMBOLIC_COMPUTATION"),
    "symbolic_computation": ("SYMBOLIC_COMPUTATION", "CODE_EXECUTION"),
    "formal_theorem": ("FORMAL_PROOF",),
    "database_state": ("DATABASE",),
    "visual_evidence": ("VISION",),
}


#: Attributes every capability record must declare. A capability may not be
#: routed unless every one of these is present, and every one of them is read
#: somewhere in the router. v1 declared `writes` and never consulted it, so a
#: read-only capability could be selected to satisfy a write request.
REQUIRED_ATTRIBUTES: frozenset[str] = frozenset({"authority_ceiling", "writes"})


def capability_writes(capability: str) -> bool:
    """Can this capability semantically perform an external write?"""
    capability = capability.upper()
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability: {capability}")
    return bool(CAPABILITIES[capability]["writes"])


def validate_registry() -> None:
    unknown = {
        cap
        for route in CLAIM_ROUTES.values()
        for cap in route
        if cap not in CAPABILITIES
    }
    if unknown:
        raise ValueError(f"claim routes reference unknown capabilities: {sorted(unknown)}")
    incomplete = {
        name: sorted(REQUIRED_ATTRIBUTES - set(meta))
        for name, meta in CAPABILITIES.items()
        if not REQUIRED_ATTRIBUTES <= set(meta)
    }
    if incomplete:
        raise ValueError(f"capabilities missing required attributes: {incomplete}")


def capability_names() -> tuple[str, ...]:
    validate_registry()
    return tuple(CAPABILITIES)
