"""Small provider-neutral tool capability policy for FOIL.

FOIL does not own external providers. The host supplies a manifest describing
what is actually ready. This module chooses the first admissible provider for a
required capability and keeps write permission separate from read/use access.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from foil_capabilities import CAPABILITIES, CLAIM_ROUTES, capability_writes, validate_registry

SCHEMA = "egrt.foil-capability-manifest.v2"


class CapabilityWriteError(ValueError):
    """Raised when a write is requested through a capability that cannot write."""



def normalize_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    validate_registry()
    providers = []
    for row in raw.get("providers", []):
        capability = str(row.get("capability", "")).upper()
        name = str(row.get("name", "")).strip()
        if not capability or not name:
            continue
        providers.append(
            {
                "name": name,
                "capability": capability,
                "status": str(row.get("status", "UNKNOWN")).upper(),
                "priority": int(row.get("priority", 100)),
                "write_allowed": bool(row.get("write_allowed", False)),
                "metadata": row.get("metadata", {}),
            }
        )
    return {"schema": SCHEMA, "providers": providers}


def select_provider(
    manifest: dict[str, Any], capability: str, *, require_write: bool = False
) -> dict[str, Any] | None:
    capability = capability.upper()
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability: {capability}")
    if require_write and not capability_writes(capability):
        # The registry is authoritative over the manifest. A host that declares
        # `write_allowed` for a read-only capability is misconfigured, and
        # honouring it would let a write route through a capability whose
        # authority ceiling does not cover writes.
        raise CapabilityWriteError(
            f"{capability} is declared writes=False in the capability registry; "
            "a host manifest cannot grant it write authority"
        )
    candidates = [
        row for row in normalize_manifest(manifest)["providers"]
        if row["capability"] == capability
        and row["status"] == "READY"
        and (not require_write or row["write_allowed"])
    ]
    candidates.sort(key=lambda row: (row["priority"], row["name"]))
    return candidates[0] if candidates else None


def route_claim(
    manifest: dict[str, Any], claim_type: str, *, require_write: bool = False
) -> dict[str, Any]:
    validate_registry()
    if claim_type not in CLAIM_ROUTES:
        return {
            "status": "UNCLASSIFIED",
            "claim_type": claim_type,
            "reason": "No capability route is defined for this claim type.",
        }
    attempted = []
    refused: list[dict[str, str]] = []
    for capability in CLAIM_ROUTES[claim_type]:
        attempted.append(capability)
        try:
            provider = select_provider(manifest, capability, require_write=require_write)
        except CapabilityWriteError as exc:
            refused.append({"capability": capability, "reason": str(exc)})
            continue
        if provider:
            return {
                "status": "READY",
                "claim_type": claim_type,
                "capability": capability,
                "provider": provider,
                "authority_ceiling": CAPABILITIES[capability]["authority_ceiling"],
                "profile_rule": "Tool success is task evidence, not user competence evidence.",
            }
    return {
        "status": "REFUSED_WRITE" if refused and len(refused) == len(attempted) else "UNAVAILABLE",
        "claim_type": claim_type,
        "attempted_capabilities": attempted,
        "refused_capabilities": refused,
        "reason": (
            "Every capability on this route is read-only in the registry."
            if refused and len(refused) == len(attempted)
            else "No READY provider satisfies the minimum route."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL provider-neutral capability policy")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--claim-type", required=True, choices=sorted(CLAIM_ROUTES))
    parser.add_argument("--require-write", action="store_true")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(route_claim(manifest, args.claim_type, require_write=args.require_write), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
