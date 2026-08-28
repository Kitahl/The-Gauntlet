"""Authoritative public controller for automatic Soul orchestration.

The implementation kernel lives in :mod:`soul_vnext.controller_impl`. This surface
binds public identity allocation, concurrent graph revision freezing, and diagnostic
Process Assurance to that kernel without exposing speculative state as persisted state.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import Obligation, ObligationKind, RuntimeEvent, Verdict, digest
from soul_vnext import controller_impl as _impl
from soul_vnext.controller_impl import (
    MODULE_FOR_KIND,
    SOUL_AUTOMATIC_SCHEMA,
    SOUL_SCHEMA,
    ActiveTaskError,
    RouteBatch,
    RouteCandidate,
    RoutingPlan,
    RoutingPolicy,
    SoulError,
    SoulGraphError,
    freeze_task,
    plan_routes,
    resolve_current_task_id,
)
from soul_vnext.controller_impl import release_gate as _release_gate
from soul_vnext.controller_impl import release_task as _release_task

SOUL_CONTROL_SCHEMA = SOUL_AUTOMATIC_SCHEMA
core = _impl.core

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


def _sanitize_task_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Preserve user metadata while removing all Soul control-plane fields."""

    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping or None")
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(key, str)
        and key not in _RESERVED_TASK_METADATA
        and not key.startswith("soul_")
    }


def _has_load_bearing(task: Mapping[str, Any]) -> bool:
    return any(
        isinstance(row, Mapping) and bool(row.get("load_bearing", True))
        for row in task.get("obligations", [])
    )


def _empty_task_detail(
    *,
    requested_task_id: str,
    resolved_task_id: str,
    automatic: bool,
) -> dict[str, Any]:
    """Represent absence of domain work without inventing an assurance obligation."""

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
        "target_domain_clearance_authorized": False,
    }


def start_task(
    root: Path,
    goal: str,
    *,
    metadata: dict[str, Any] | None = None,
    supersession_reason: str | None = None,
):
    """Start a task without allowing caller metadata to predeclare control state."""

    return _impl.start_task(
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
) -> Obligation:
    """Persist and return the same obligation identity under automatic lineage.

    The low-level constructor allocates its own identifier for an unfrozen task, so
    that persisted object is returned directly. A frozen task receives one successor
    revision, and that successor is frozen before another automatic writer may extend
    the lineage.
    """

    if not isinstance(kind, ObligationKind):
        raise TypeError("kind must be ObligationKind")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be non-empty")

    store = RuntimeStore(root)
    result: Obligation
    with store.lock("active-task"):
        current_id, _ = _impl._resolve_lineage_unlocked(store, task_id)
        current = store.read_task(current_id)
        if current is None:
            raise KeyError(f"unknown task {current_id}")
        _impl.core._require_open_task(current)
        if _impl._metadata(current).get("soul_frozen"):
            if not _impl._runtime_flag(root, "automatic_graph_revision", True):
                raise SoulGraphError("cannot add obligations after the graph is frozen")
            result = Obligation(
                obligation_id=new_id("obl"),
                kind=kind,
                claim=claim,
                load_bearing=load_bearing,
                required_module=MODULE_FOR_KIND[kind],
                metadata=metadata or {},
            )
            successor_id = _impl._successor_with_obligation_locked(
                root,
                store,
                current_id,
                result,
                reason="new-obligation-after-freeze",
            )
            _impl.core.freeze_task(root, successor_id)
        else:
            result = _impl.core.add_obligation(
                root,
                current_id,
                kind,
                claim,
                load_bearing=load_bearing,
                metadata=metadata,
            )
    return result


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Evaluate release while keeping an empty task explicitly UNKNOWN."""

    current_id, _ = resolve_current_task_id(root, task_id)
    task = RuntimeStore(root).read_task(current_id)
    if task is not None and not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_task_detail(
            requested_task_id=task_id,
            resolved_task_id=current_id,
            automatic=False,
        )
    return _release_gate(root, task_id)


def release_task(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Commit release only when represented load-bearing work exists."""

    current_id, _ = resolve_current_task_id(root, task_id)
    task = RuntimeStore(root).read_task(current_id)
    if task is not None and not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_task_detail(
            requested_task_id=task_id,
            resolved_task_id=current_id,
            automatic=False,
        )
    return _release_task(root, task_id)


def automatic_release(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Run the automatic cycle and keep Process Assurance active while work is pending.

    Pending domain routes cannot release. They still receive an ``ASSURANCE_ONLY``
    diagnostic receipt for the represented state, so the watchdog remains automatic
    without substituting for missing claim-native receipts. A task with no load-bearing
    domain work remains UNKNOWN and does not receive fabricated assurance work.
    """

    current_id, _ = resolve_current_task_id(root, task_id)
    task = RuntimeStore(root).read_task(current_id)
    if task is not None and not _has_load_bearing(task):
        return Verdict.UNKNOWN, _empty_task_detail(
            requested_task_id=task_id,
            resolved_task_id=current_id,
            automatic=True,
        )

    verdict, raw_detail = _impl.automatic_release(root, task_id)
    detail = dict(raw_detail)
    if (
        detail.get("reason") != "automatic-routes-pending"
        or not _impl._automatic_assurance_enabled(root)
        or detail.get("assurance_receipt_id")
    ):
        return verdict, detail

    resolved_id = str(detail.get("resolved_task_id") or task_id)
    from gauntlet_automatic import assurance_obligation_id, run_automatic_assurance

    assurance_id = assurance_obligation_id(root, resolved_id)
    if not assurance_id:
        return verdict, detail

    store = RuntimeStore(root)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="release.attempted",
            component="soul",
            task_id=resolved_id,
            payload_hash=digest(
                {
                    "task_id": resolved_id,
                    "routing_plan_id": detail.get("routing_plan_id"),
                    "pending_domain": True,
                }
            ),
            timestamp=utcnow(),
            metadata={
                "routing_plan_id": detail.get("routing_plan_id"),
                "automatic": True,
                "pending_domain": True,
                "requested_task_id": task_id,
            },
        )
    )
    try:
        assurance = run_automatic_assurance(
            root,
            assurance_id,
            task_id=resolved_id,
            policy=_impl._assurance_policy(root),
        )
    except Exception as exc:
        detail.update(
            {
                "reason": "automatic-assurance-unavailable",
                "assurance_error_type": type(exc).__name__,
                "assurance_receipt_id": None,
            }
        )
        return Verdict.UNAVAILABLE, detail

    detail["assurance_receipt_id"] = assurance.receipt_id
    detail["assurance_verdict"] = assurance.verdict.value
    detail["assurance_phase"] = "PENDING_DOMAIN_DIAGNOSTIC"
    return verdict, detail


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
