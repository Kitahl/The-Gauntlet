"""Deterministic, fail-closed compiler for the lean model-visible tool surface."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from gauntlet_host.constants import GAUNTLET_STATUS_TOOLS, GAUNTLET_TOOLSET

TOOL_SURFACE_SCHEMA = "gauntlet.tool-surface-plan.v1"
TOOL_SURFACE_REVISION = "gauntlet-tools.v1"
COMPILED_TOOLSET_NAME = "gauntlet-active-v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_CAPABILITY_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "gauntlet_task_status_compact": (
        ("CANONICAL_STATUS_REFRESH",),
        ("always", "status_refresh"),
    ),
    "gauntlet_obligation_get": (
        ("BOUNDED_PROGRESSIVE_DISCLOSURE",),
        ("always", "exact_obligation_detail"),
    ),
    "gauntlet_release_status": (
        ("CANONICAL_RELEASE_REFRESH",),
        ("always", "release_refresh"),
    ),
}


class ToolSurfaceError(RuntimeError):
    """Typed failure while planning or compiling a model-visible tool surface."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _tool_records(definitions: Any) -> list[dict[str, str]]:
    if not isinstance(definitions, (list, tuple)):
        return []
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in definitions:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name or len(name) > 256 or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "schema_hash": _canonical_hash(
                    {
                        "parameters": function.get("parameters"),
                        "strict": function.get("strict"),
                    }
                ),
            }
        )
    return sorted(records, key=lambda item: item["name"])


def manifest_hash(definitions: Any) -> str:
    """Return the same canonical schema identity used by the FOIL bridge."""

    return _canonical_hash(_tool_records(definitions))


def _route_missing_capabilities(route: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for row in route.get("missing_capabilities", []):
        if not isinstance(row, dict):
            continue
        for capability in row.get("acceptable_capabilities", []):
            if isinstance(capability, str) and capability and capability not in missing:
                missing.append(capability)
    return missing


def build_tool_surface_plan(
    definitions: Sequence[dict[str, Any]],
    route: dict[str, Any],
) -> dict[str, Any]:
    """Freeze the authorized catalog and proposed active manifest."""

    records = _tool_records(definitions)
    expected_names = set(GAUNTLET_STATUS_TOOLS)
    actual_names = {record["name"] for record in records}
    if actual_names != expected_names:
        raise ToolSurfaceError(
            "AUTHORIZED_CATALOG_MISMATCH",
            "authorized Gauntlet catalog did not match the frozen lean status tools",
        )
    route_hash = route.get("content_hash") if isinstance(route, dict) else None
    if not isinstance(route_hash, str) or not _SHA256_PATTERN.fullmatch(route_hash):
        raise ToolSurfaceError(
            "TOOL_SURFACE_ROUTE_INVALID",
            "tool-surface planning requires a content-addressed FOIL proposal",
        )
    specs: list[dict[str, Any]] = []
    record_by_name = {record["name"]: record for record in records}
    for name in sorted(expected_names):
        capability_ids, required_for = _CAPABILITY_SPECS[name]
        specs.append(
            {
                "name": name,
                "authorized_toolset": GAUNTLET_TOOLSET,
                "schema_hash": record_by_name[name]["schema_hash"],
                "capability_ids": list(capability_ids),
                "required_for": list(required_for),
                "required": True,
                "availability": "AUTHORIZED_PENDING_FRESH_PROBE",
            }
        )
    payload = {
        "schema": TOOL_SURFACE_SCHEMA,
        "revision": TOOL_SURFACE_REVISION,
        "compiled_toolset": COMPILED_TOOLSET_NAME,
        "authorized_toolsets": [GAUNTLET_TOOLSET],
        "capability_specs": specs,
        "required_in_flight_tools": [],
        "required_retry_tools": [],
        "foil_proposal_hash": route_hash,
        "foil_selected_capability_ids": list(route.get("minimum_capability_bundle", [])),
        "foil_missing_capability_ids": _route_missing_capabilities(route),
        "planned_manifest_hash": _canonical_hash(records),
        "authorized_catalog_hash": _canonical_hash(specs),
        "silent_widening_allowed": False,
    }
    payload["content_hash"] = _canonical_hash(payload)
    return payload


def validate_tool_surface_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != TOOL_SURFACE_SCHEMA:
        raise ToolSurfaceError(
            "TOOL_SURFACE_PLAN_MISSING",
            "worker request omitted the frozen tool-surface plan",
        )
    if value.get("revision") != TOOL_SURFACE_REVISION:
        raise ToolSurfaceError(
            "TOOL_SURFACE_REVISION_MISMATCH",
            "tool-surface plan revision is not supported",
        )
    supplied_hash = value.get("content_hash")
    if not isinstance(supplied_hash, str) or not _SHA256_PATTERN.fullmatch(supplied_hash):
        raise ToolSurfaceError(
            "TOOL_SURFACE_CONTENT_HASH_INVALID",
            "tool-surface plan omitted a valid content hash",
        )
    payload = dict(value)
    payload.pop("content_hash", None)
    if _canonical_hash(payload) != supplied_hash:
        raise ToolSurfaceError(
            "TOOL_SURFACE_CONTENT_HASH_MISMATCH",
            "tool-surface plan content hash did not match its payload",
        )
    if value.get("compiled_toolset") != COMPILED_TOOLSET_NAME:
        raise ToolSurfaceError(
            "TOOL_SURFACE_NAME_INVALID",
            "tool-surface plan named an unsupported compiled toolset",
        )
    if value.get("authorized_toolsets") != [GAUNTLET_TOOLSET]:
        raise ToolSurfaceError(
            "TOOL_SURFACE_AUTHORIZATION_INVALID",
            "tool-surface plan did not freeze the Gauntlet-only authorization",
        )
    if value.get("silent_widening_allowed") is not False:
        raise ToolSurfaceError(
            "TOOL_SURFACE_WIDENING_INVALID",
            "tool-surface plan permitted silent widening",
        )
    specs = value.get("capability_specs")
    if not isinstance(specs, list) or len(specs) != len(GAUNTLET_STATUS_TOOLS):
        raise ToolSurfaceError(
            "CAPABILITY_SPECS_INVALID",
            "tool-surface plan capability specifications are incomplete",
        )
    expected_names = set(GAUNTLET_STATUS_TOOLS)
    seen: set[str] = set()
    for spec in specs:
        if not isinstance(spec, dict):
            raise ToolSurfaceError("CAPABILITY_SPEC_INVALID", "capability spec is malformed")
        name = spec.get("name")
        if name not in expected_names or name in seen:
            raise ToolSurfaceError(
                "CAPABILITY_SPEC_INVALID",
                "capability spec names are unknown or duplicated",
            )
        seen.add(name)
        expected_caps, expected_reasons = _CAPABILITY_SPECS[name]
        if (
            spec.get("authorized_toolset") != GAUNTLET_TOOLSET
            or spec.get("schema_hash") is None
            or spec.get("capability_ids") != list(expected_caps)
            or spec.get("required_for") != list(expected_reasons)
            or spec.get("required") is not True
            or spec.get("availability") != "AUTHORIZED_PENDING_FRESH_PROBE"
        ):
            raise ToolSurfaceError(
                "CAPABILITY_SPEC_INVALID",
                f"capability spec for {name} did not match the frozen contract",
            )
    if seen != expected_names or value.get("authorized_catalog_hash") != _canonical_hash(specs):
        raise ToolSurfaceError(
            "AUTHORIZED_CATALOG_HASH_MISMATCH",
            "authorized catalog identity did not match its capability specs",
        )
    planned_hash = value.get("planned_manifest_hash")
    if not isinstance(planned_hash, str) or not _SHA256_PATTERN.fullmatch(planned_hash):
        raise ToolSurfaceError(
            "PLANNED_MANIFEST_HASH_INVALID",
            "tool-surface plan omitted its planned manifest identity",
        )
    return value


@dataclass(frozen=True, slots=True)
class CompiledToolSurface:
    toolset_name: str
    tool_names: tuple[str, ...]
    planned_manifest_hash: str
    active_manifest_hash: str
    fresh_available_names: tuple[str, ...]
    ignored_available_names: tuple[str, ...]
    missing_required_names: tuple[str, ...]
    capability_bundle_complete: bool
    foil_missing_capability_ids: tuple[str, ...]
    silent_widening_performed: bool

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def compile_live_tool_surface(
    plan: Any,
    live_definitions: Any,
    *,
    requested_toolsets: Sequence[str],
) -> CompiledToolSurface:
    """Compile a fresh availability snapshot without ever widening authority."""

    plan = validate_tool_surface_plan(plan)
    requested = tuple(dict.fromkeys(requested_toolsets))
    if set(requested) != {GAUNTLET_TOOLSET}:
        raise ToolSurfaceError(
            "UNCOMPILED_AUTHORIZED_TOOLSET",
            "requested toolsets exceeded the frozen Gauntlet-only catalog",
        )
    records = _tool_records(live_definitions)
    live_by_name = {record["name"]: record for record in records}
    required_names = tuple(spec["name"] for spec in plan["capability_specs"])
    missing = tuple(sorted(name for name in required_names if name not in live_by_name))
    if missing:
        raise ToolSurfaceError(
            "REQUIRED_TOOL_UNAVAILABLE",
            "fresh availability omitted required tools: " + ", ".join(missing),
        )
    schema_drift = sorted(
        spec["name"]
        for spec in plan["capability_specs"]
        if live_by_name[spec["name"]]["schema_hash"] != spec["schema_hash"]
    )
    if schema_drift:
        raise ToolSurfaceError(
            "REQUIRED_TOOL_SCHEMA_DRIFT",
            "fresh tool schemas drifted from the frozen catalog: " + ", ".join(schema_drift),
        )
    active_records = sorted(
        (live_by_name[name] for name in required_names), key=lambda item: item["name"]
    )
    active_hash = _canonical_hash(active_records)
    if active_hash != plan["planned_manifest_hash"]:
        raise ToolSurfaceError(
            "ACTIVE_MANIFEST_HASH_MISMATCH",
            "compiled active manifest did not match the parent-frozen identity",
        )
    ignored = tuple(sorted(set(live_by_name).difference(required_names)))
    return CompiledToolSurface(
        toolset_name=COMPILED_TOOLSET_NAME,
        tool_names=tuple(sorted(required_names)),
        planned_manifest_hash=plan["planned_manifest_hash"],
        active_manifest_hash=active_hash,
        fresh_available_names=tuple(sorted(live_by_name)),
        ignored_available_names=ignored,
        missing_required_names=(),
        capability_bundle_complete=not plan["foil_missing_capability_ids"],
        foil_missing_capability_ids=tuple(plan["foil_missing_capability_ids"]),
        silent_widening_performed=False,
    )


def install_compiled_toolset(compiled: CompiledToolSurface) -> None:
    """Install the exact compiled name list into pinned Hermes before AIAgent init."""

    if compiled.toolset_name != COMPILED_TOOLSET_NAME or not compiled.tool_names:
        raise ToolSurfaceError(
            "COMPILED_TOOLSET_INVALID",
            "compiled toolset is empty or named incorrectly",
        )
    from toolsets import create_custom_toolset

    create_custom_toolset(
        name=compiled.toolset_name,
        description="Gauntlet request-scoped, availability-probed active manifest",
        tools=list(compiled.tool_names),
        includes=[],
    )
