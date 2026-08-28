"""Compatibility surface for the authoritative automatic Soul controller."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import soul_vnext.controller as _controller
from egrt_store import RuntimeStore, new_id
from egrt_types import Obligation, ObligationKind
from soul_vnext.controller import (
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
    automatic_release,
    freeze_task,
    plan_routes,
    release_gate,
    release_task,
    resolve_current_task_id,
    start_task,
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

    The lower-level constructor allocates its own identifier for an unfrozen task.
    Automatic Soul therefore returns that persisted object directly instead of a
    speculative pre-allocation. A frozen task still receives one content-bound
    successor revision containing the pre-allocated obligation.
    """

    if not isinstance(kind, ObligationKind):
        raise TypeError("kind must be ObligationKind")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be non-empty")

    store = RuntimeStore(root)
    successor_id: str | None = None
    result: Obligation
    with store.lock("active-task"):
        current_id, _ = _controller._resolve_lineage_unlocked(store, task_id)
        current = store.read_task(current_id)
        if current is None:
            raise KeyError(f"unknown task {current_id}")
        _controller.core._require_open_task(current)
        if _controller._metadata(current).get("soul_frozen"):
            if not _controller._runtime_flag(root, "automatic_graph_revision", True):
                raise SoulGraphError("cannot add obligations after the graph is frozen")
            result = Obligation(
                obligation_id=new_id("obl"),
                kind=kind,
                claim=claim,
                load_bearing=load_bearing,
                required_module=MODULE_FOR_KIND[kind],
                metadata=metadata or {},
            )
            successor_id = _controller._successor_with_obligation_locked(
                root,
                store,
                current_id,
                result,
                reason="new-obligation-after-freeze",
            )
        else:
            result = _controller.core.add_obligation(
                root,
                current_id,
                kind,
                claim,
                load_bearing=load_bearing,
                metadata=metadata,
            )
    if successor_id is not None:
        _controller.core.freeze_task(root, successor_id)
    return result


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
