"""Authoritative public controller for automatic Soul orchestration.

The implementation kernel lives in :mod:`soul_vnext.controller_impl`. This surface
binds public identity allocation, concurrent graph revision freezing, and diagnostic
Process Assurance to that kernel without exposing speculative state as persisted state.
"""
from __future__ import annotations

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
    release_gate,
    release_task,
    resolve_current_task_id,
    start_task,
)

core = _impl.core


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


def automatic_release(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Run the automatic cycle and keep Process Assurance active while work is pending.

    Pending domain routes cannot release. They still receive an ``ASSURANCE_ONLY``
    diagnostic receipt for the represented state, so the watchdog remains automatic
    without substituting for missing claim-native receipts.
    """

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
