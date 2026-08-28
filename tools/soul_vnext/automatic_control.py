"""Authoritative automatic-control hardening for Soul.

This layer preserves the automatic mechanisms implemented by :mod:`soul_automatic`
while closing control-plane gaps that a host model, caller metadata, or stale task ID
must not be able to exploit.  The public runtime imports this module rather than the
mechanism module directly.

The controller provides:

* content-valid successor-lineage traversal;
* caller-metadata sanitization for reserved Soul control fields;
* full supersession lineage in route-plan certificates;
* fail-closed empty, released, and authority-monitor states;
* idempotent automatic release;
* bounded machine-readable route instructions for the host loop.

It still never creates a target-domain receipt or authorizes execution/adoption.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

import soul_automatic as mechanism
import soul_vnext as low_level
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import ObligationKind, RuntimeEvent, Verdict, digest
from gauntlet_config import load_config, state_dir

SOUL_CONTROL_SCHEMA = "egrt.soul.automatic-control.v2"
SOUL_AUTOMATIC_SCHEMA = SOUL_CONTROL_SCHEMA
SOUL_SCHEMA = mechanism.SOUL_SCHEMA
MODULE_FOR_KIND = mechanism.MODULE_FOR_KIND
SoulError = mechanism.SoulError
ActiveTaskError = mechanism.ActiveTaskError
SoulGraphError = mechanism.SoulGraphError
RouteCandidate = mechanism.RouteCandidate
RouteBatch = mechanism.RouteBatch
RoutingPolicy = mechanism.RoutingPolicy
RoutingPlan = mechanism.RoutingPlan

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RESERVED_TASK_METADATA = {
    "active",
    "released",
    "task_id",
    "goal_hash",
    "content_hash",
    "supersession_reason",
    "raw_goal",
    "raw_prompt",
    "raw_supersession_reason",
}


def _sanitize_task_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Remove caller-supplied control-plane fields.

    User metadata remains available, but no caller or model may predeclare lineage,
    freeze state, release state, route certificates, or Soul authority by placing a
    reserved key in the metadata envelope.
    """

    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping or None")
    return {
        str(key): value
        for key, value in metadata.items()
        if isinstance(key, str)
        and key not in _RESERVED_TASK_METADATA
        and not key.startswith("soul_")
    }


def _successor_id(task: Mapping[str, Any]) -> str | None:
    metadata = task.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise SoulGraphError("task metadata must be a mapping")
    value = metadata.get("soul_superseded_by")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SoulGraphError("invalid task successor identifier")
    return value


def resolve_current_task_id(
    root: Path,
    task_id: str,
) -> tuple[str, tuple[str, ...]]:
    """Resolve the current task through a bidirectionally bound lineage chain."""

    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task_id must be a non-empty string")
    store = RuntimeStore(root)
    current = task_id
    chain: list[str] = [current]
    seen = {current}
    for _ in range(64):
        task = store.read_task(current)
        if task is None:
            if len(chain) == 1:
                return current, tuple(chain)
            raise SoulGraphError(f"missing successor task {current}")
        successor = _successor_id(task)
        if successor is None:
            return current, tuple(chain)
        metadata = task.get("metadata") or {}
        reason_hash = metadata.get("soul_supersession_reason_hash")
        if (
            task.get("active") is not False
            or task.get("released") is not False
            or metadata.get("soul_status") != "SUPERSEDED"
            or not isinstance(reason_hash, str)
            or _SHA256.fullmatch(reason_hash) is None
        ):
            raise SoulGraphError("unbound or contradictory task supersession state")
        if successor in seen:
            raise SoulGraphError("task supersession cycle detected")
        successor_task = store.read_task(successor)
        if successor_task is None:
            raise SoulGraphError(f"missing successor task {successor}")
        successor_metadata = successor_task.get("metadata") or {}
        if (
            not isinstance(successor_metadata, Mapping)
            or successor_metadata.get("soul_supersedes") != current
        ):
            raise SoulGraphError("successor does not bind its predecessor")
        seen.add(successor)
        chain.append(successor)
        current = successor
    raise SoulGraphError("task supersession chain exceeds 64 revisions")


def start_task(
    root: Path,
    goal: str,
    *,
    metadata: dict[str, Any] | None = None,
    supersession_reason: str | None = None,
):
    return mechanism.start_task(
        root,
        goal,
        metadata=_sanitize_task_metadata(metadata),
        supersession_reason=supersession_reason,
    )


def add_obligation(
    root: Path,
    task_id: str,
    kind: ObligationKind,
    claim: str,
    *,
    load_bearing: bool = True,
    metadata: dict[str, Any] | None = None,
):
    current_id, _ = resolve_current_task_id(root, task_id)
    return mechanism.add_obligation(
        root,
        current_id,
        kind,
        claim,
        load_bearing=load_bearing,
        metadata=metadata,
    )


def freeze_task(root: Path, task_id: str) -> dict[str, Any]:
    current_id, _ = resolve_current_task_id(root, task_id)
    return mechanism.freeze_task(root, current_id)


def _load_task(root: Path, task_id: str) -> tuple[RuntimeStore, dict[str, Any]]:
    store = RuntimeStore(root)
    task = store.read_task(task_id)
    if task is None:
        raise KeyError(f"unknown task {task_id}")
    return store, task


def _has_load_bearing(task: Mapping[str, Any]) -> bool:
    return any(
        isinstance(row, Mapping) and bool(row.get("load_bearing", True))
        for row in task.get("obligations", [])
    )


def _empty_detail(
    *,
    requested_task_id: str,
    resolved_task_id: str,
    automatic: bool,
) -> dict[str, Any]:
    return {
        "reason": "no-load-bearing-obligations",
        "task_id": resolved_task_id,
        "requested_task_id": requested_task_id,
        "resolved_task_id": resolved_task_id,
        "obligations": [],
        "automatic": automatic,
        "routing_plan_id": None,
        "routing_liveness_status": "STALLED_NO_EXECUTABLE_ROUTE",
        "routing_batches": [],
        "selected_obligations": [],
        "assurance_receipt_id": None,
        "authority": "CONTROL_ONLY",
    }


def _wrap_plan_lineage(
    root: Path,
    requested_task_id: str,
    plan: RoutingPlan,
    chain: tuple[str, ...],
) -> RoutingPlan:
    input_hash = digest(
        {
            "base_input_hash": plan.input_hash,
            "requested_task_id": requested_task_id,
            "resolved_task_id": plan.task_id,
            "supersession_chain": chain,
            "schema": SOUL_CONTROL_SCHEMA,
        }
    )
    coverage_hash = digest(
        {
            "base_coverage_certificate_hash": plan.coverage_certificate_hash,
            "requested_task_id": requested_task_id,
            "resolved_task_id": plan.task_id,
            "supersession_chain": chain,
            "decomposition_completeness_established": False,
        }
    )
    selection_hash = digest(
        {
            "base_selection_certificate_hash": plan.selection_certificate_hash,
            "input_hash": input_hash,
            "selected": plan.selected_obligations,
            "excluded": plan.excluded_obligations,
            "dependency_blocked": plan.dependency_blocked,
            "policy": asdict(plan.policy),
            "optimality_claimed": False,
        }
    )
    plan_payload = {
        "base_plan_hash": plan.plan_hash,
        "requested_task_id": requested_task_id,
        "resolved_task_id": plan.task_id,
        "input_hash": input_hash,
        "obligation_set_hash": plan.obligation_set_hash,
        "selected": plan.selected_obligations,
        "excluded": plan.excluded_obligations,
        "dependency_blocked": plan.dependency_blocked,
        "batches": [asdict(batch) for batch in plan.batches],
        "coverage_certificate_hash": coverage_hash,
        "selection_certificate_hash": selection_hash,
        "supersession_chain": chain,
        "liveness_status": plan.liveness_status,
        "schema": SOUL_CONTROL_SCHEMA,
    }
    plan_hash = digest(plan_payload)
    wrapped = replace(
        plan,
        plan_id=f"route-{plan_hash[:16]}",
        requested_task_id=requested_task_id,
        input_hash=input_hash,
        coverage_certificate_hash=coverage_hash,
        selection_certificate_hash=selection_hash,
        plan_hash=plan_hash,
        supersession_chain=chain,
        schema=SOUL_CONTROL_SCHEMA,
    )
    store = RuntimeStore(root)
    state = asdict(wrapped)
    state["content_hash"] = digest(state)
    store.write_named_state("soul_routes", wrapped.plan_id, state)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="route.plan.automatic.control",
            component="soul",
            task_id=wrapped.task_id,
            payload_hash=wrapped.plan_hash,
            timestamp=utcnow(),
            metadata={
                "plan_id": wrapped.plan_id,
                "requested_task_id": requested_task_id,
                "supersession_chain_hash": digest(chain),
                "selected_count": len(wrapped.selected_obligations),
                "batch_count": len(wrapped.batches),
                "liveness_status": wrapped.liveness_status,
                "authority": "ROUTING_ONLY",
                "execution_authorized": False,
                "automatic": True,
            },
        )
    )
    return wrapped


def plan_routes(
    root: Path,
    task_id: str,
    *,
    policy: RoutingPolicy | None = None,
) -> RoutingPlan:
    requested_task_id = task_id
    current_id, _ = resolve_current_task_id(root, requested_task_id)
    _, task = _load_task(root, current_id)
    if not _has_load_bearing(task):
        raise SoulGraphError("task requires at least one load-bearing obligation")
    mechanism.freeze_task(root, current_id)
    resolved_id, chain = resolve_current_task_id(root, requested_task_id)
    plan = mechanism.plan_routes(root, resolved_id, policy=policy)
    final_id, final_chain = resolve_current_task_id(root, requested_task_id)
    if final_id != plan.task_id:
        raise SoulGraphError("route plan targeted a stale task revision")
    return _wrap_plan_lineage(root, requested_task_id, plan, final_chain)


def _released_result(
    root: Path,
    requested_task_id: str,
    resolved_task_id: str,
) -> tuple[Verdict, dict[str, Any]]:
    verdict, detail = low_level.release_task(root, resolved_task_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": requested_task_id,
            "resolved_task_id": resolved_task_id,
            "automatic": True,
            "routing_plan_id": None,
            "routing_liveness_status": "CLEARED",
            "routing_batches": [],
            "selected_obligations": [],
            "assurance_receipt_id": None,
        }
    )
    return verdict, result


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    requested_task_id = task_id
    current_id, _ = resolve_current_task_id(root, requested_task_id)
    _, task = _load_task(root, current_id)
    if not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_detail(
            requested_task_id=requested_task_id,
            resolved_task_id=current_id,
            automatic=False,
        )
    if task.get("released"):
        verdict, detail = low_level.release_gate(root, current_id)
    else:
        mechanism.freeze_task(root, current_id)
        current_id, _ = resolve_current_task_id(root, requested_task_id)
        verdict, detail = low_level.release_gate(root, current_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": requested_task_id,
            "resolved_task_id": current_id,
        }
    )
    return verdict, result


def release_task(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    requested_task_id = task_id
    current_id, _ = resolve_current_task_id(root, requested_task_id)
    _, task = _load_task(root, current_id)
    if not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_detail(
            requested_task_id=requested_task_id,
            resolved_task_id=current_id,
            automatic=False,
        )
    if task.get("released"):
        verdict, detail = low_level.release_task(root, current_id)
    else:
        mechanism.freeze_task(root, current_id)
        current_id, _ = resolve_current_task_id(root, requested_task_id)
        verdict, detail = low_level.release_task(root, current_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": requested_task_id,
            "resolved_task_id": current_id,
        }
    )
    return verdict, result


def _runtime_flag(root: Path, name: str, default: bool) -> bool:
    runtime = load_config(root).get("runtime") or {}
    if not isinstance(runtime, Mapping):
        return default
    value = runtime.get(name, default)
    return value if isinstance(value, bool) else default


def _emit_authority_unavailable(
    root: Path,
    task_id: str,
    error_type: str,
) -> None:
    RuntimeStore(root).append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="authority.changed",
            component="soul",
            task_id=task_id,
            payload_hash=digest(
                {"monitor": "gauntlet-authority", "error_type": error_type}
            ),
            timestamp=utcnow(),
            metadata={
                "drift_count": 1,
                "monitor_unavailable": True,
                "error_type": error_type,
                "automatic": True,
            },
        )
    )


def _refresh_authority_state(root: Path, task_id: str) -> None:
    """Refresh authority only after a valid, drift-free monitor read."""

    try:
        cfg = load_config(root)
        monitor_path = state_dir(root, cfg) / "gauntlet_monitor.json"
        if monitor_path.exists():
            raw = json.loads(monitor_path.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping):
                raise ValueError("authority state is not an object")
        from gauntlet_monitor import check as authority_check
        from gauntlet_monitor import snapshot as authority_snapshot

        drift_code, _ = authority_check(root, emit_event=True)
        if drift_code == 0:
            authority_snapshot(root, task_id=task_id)
    except Exception as exc:  # fail closed without persisting exception text
        _emit_authority_unavailable(root, task_id, type(exc).__name__)


def _bounded_route_summary(plan: RoutingPlan) -> list[dict[str, Any]]:
    return [
        {
            "module": batch.module,
            "obligation_ids": list(batch.obligation_ids[:16]),
            "context_sharing_status": batch.context_sharing_status,
            "execution_authorized": False,
        }
        for batch in plan.batches[:16]
    ]


def automatic_release(
    root: Path,
    task_id: str,
) -> tuple[Verdict, dict[str, Any]]:
    """Run the automatic route→assure→release cycle, fail closed and idempotently."""

    requested_task_id = task_id
    current_id, chain = resolve_current_task_id(root, requested_task_id)
    store, task = _load_task(root, current_id)
    if not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_detail(
            requested_task_id=requested_task_id,
            resolved_task_id=current_id,
            automatic=True,
        )
    if task.get("released"):
        return _released_result(root, requested_task_id, current_id)

    _refresh_authority_state(root, current_id)
    plan = plan_routes(root, requested_task_id)
    current_id = plan.task_id
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="release.attempted",
            component="soul",
            task_id=current_id,
            payload_hash=digest(
                {
                    "task_id": current_id,
                    "routing_plan_id": plan.plan_id,
                    "supersession_chain": plan.supersession_chain,
                }
            ),
            timestamp=utcnow(),
            metadata={
                "routing_plan_id": plan.plan_id,
                "automatic": True,
                "requested_task_id": requested_task_id,
                "selected_count": len(plan.selected_obligations),
            },
        )
    )

    assurance_receipt_id: str | None = None
    if _runtime_flag(root, "automatic_assurance", False):
        from gauntlet_automatic import assurance_obligation_id
        from gauntlet_automatic import run_automatic_assurance

        assurance_id = assurance_obligation_id(root, current_id)
        if assurance_id:
            assurance = run_automatic_assurance(
                root,
                assurance_id,
                task_id=current_id,
            )
            assurance_receipt_id = assurance.receipt_id

    verdict, detail = low_level.release_task(root, current_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": requested_task_id,
            "resolved_task_id": current_id,
            "supersession_chain": list(plan.supersession_chain),
            "routing_plan_id": plan.plan_id,
            "routing_liveness_status": plan.liveness_status,
            "routing_batches": _bounded_route_summary(plan),
            "selected_obligations": list(plan.selected_obligations),
            "excluded_obligations": [list(row) for row in plan.excluded_obligations],
            "dependency_blocked": [
                [obligation_id, list(dependencies)]
                for obligation_id, dependencies in plan.dependency_blocked
            ],
            "assurance_receipt_id": assurance_receipt_id,
            "automatic": True,
            "authority": "CONTROL_ONLY",
            "target_domain_clearance_authorized": False,
        }
    )
    return verdict, result


__all__ = [
    "ActiveTaskError",
    "MODULE_FOR_KIND",
    "RouteBatch",
    "RouteCandidate",
    "RoutingPlan",
    "RoutingPolicy",
    "SOUL_AUTOMATIC_SCHEMA",
    "SOUL_CONTROL_SCHEMA",
    "SOUL_SCHEMA",
    "SoulError",
    "SoulGraphError",
    "add_obligation",
    "automatic_release",
    "freeze_task",
    "plan_routes",
    "release_gate",
    "release_task",
    "resolve_current_task_id",
    "start_task",
]
