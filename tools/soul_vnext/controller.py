"""Authoritative automatic Research Orchestrator controller.

This module composes the typed ``soul_vnext`` graph, receipt, challenge, and release
mechanisms while preserving automatic reframing and routing. The controller never
manufactures a claim-native receipt. It schedules every dependency-ready obligation,
preserves immutable task revisions, invokes Process Assurance only after domain work is
complete, and commits release only through the low-level evidence-bound CAS.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import soul_vnext as core
from egrt_challenge import ChallengePolicy
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    Obligation,
    ObligationKind,
    RuntimeEvent,
    TaskState,
    Verdict,
    canonical_json,
    digest,
    text_digest,
)
from gauntlet_config import load_config
from private_io import write_private_text

SOUL_AUTOMATIC_SCHEMA = "egrt.soul.automatic.v2"
SOUL_SCHEMA = core.SOUL_SCHEMA
MODULE_FOR_KIND = core.MODULE_FOR_KIND
SoulError = core.SoulError
ActiveTaskError = core.ActiveTaskError
SoulGraphError = core.SoulGraphError
RouteCandidate = core.RouteCandidate
RouteBatch = core.RouteBatch

_ROUTING_MODES = {"AUTOMATIC_ALL_READY", "BUDGETED_EXPERIMENTAL"}
_RESERVED_CALLER_METADATA = {
    "raw_goal_persisted",
    "raw_supersession_reason_persisted",
}


@dataclass(frozen=True)
class RoutingPolicy:
    """Automatic routing policy.

    Production mode selects every dependency-ready unresolved obligation. Structural
    ceilings are available only in the explicitly experimental budgeted mode.
    """

    mode: str = "AUTOMATIC_ALL_READY"
    max_cost_units: int | None = None
    max_obligations: int | None = None
    batch_same_module: bool = True
    include_non_load_bearing: bool = False
    available_modules: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.mode not in _ROUTING_MODES:
            raise ValueError(f"mode must be one of {sorted(_ROUTING_MODES)}")
        for name in ("max_cost_units", "max_obligations"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative int or None")
        if (
            self.mode == "BUDGETED_EXPERIMENTAL"
            and self.max_cost_units is None
            and self.max_obligations is None
        ):
            raise ValueError("budgeted experimental mode requires at least one ceiling")
        for name in ("batch_same_module", "include_non_load_bearing"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.available_modules is not None:
            if not isinstance(self.available_modules, tuple):
                raise TypeError("available_modules must be tuple or None")
            if any(
                not isinstance(item, str) or not item.strip()
                for item in self.available_modules
            ):
                raise ValueError("available_modules must contain non-empty strings")
            if len(set(self.available_modules)) != len(self.available_modules):
                raise ValueError("available_modules must be unique")


@dataclass(frozen=True)
class RoutingPlan:
    plan_id: str
    task_id: str
    requested_task_id: str
    input_hash: str
    obligation_set_hash: str
    policy: RoutingPolicy
    selected_obligations: tuple[str, ...]
    excluded_obligations: tuple[tuple[str, str], ...]
    dependency_blocked: tuple[tuple[str, tuple[str, ...]], ...]
    batches: tuple[RouteBatch, ...]
    planned_cost_units: int
    unresolved_cost_units: int
    coverage_certificate_hash: str
    selection_certificate_hash: str
    plan_hash: str
    liveness_status: str
    stall_frontier: tuple[str, ...]
    supersession_chain: tuple[str, ...]
    decomposition_scope: str = "AUTOMATIC_REVISIONED_DECLARED_GRAPH"
    decomposition_completeness_established: bool = False
    cost_model_status: str = "UNCALIBRATED_ORDERING_PROXY"
    challenge_cost_status: str = "NOT_MEASURED"
    efficacy_status: str = "NOT_ESTABLISHED"
    authority: str = "ROUTING_ONLY"
    execution_authorized: bool = False
    automatic: bool = True
    schema: str = SOUL_AUTOMATIC_SCHEMA


def _runtime_config(root: Path) -> Mapping[str, Any]:
    raw = load_config(root).get("runtime") or {}
    return raw if isinstance(raw, Mapping) else {}


def _runtime_flag(root: Path, name: str, default: bool) -> bool:
    value = _runtime_config(root).get(name, default)
    return value if isinstance(value, bool) else default


def _active_task_id(store: RuntimeStore) -> str | None:
    path = store.base / "active_task"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _metadata(task: Mapping[str, Any]) -> Mapping[str, Any]:
    value = task.get("metadata") or {}
    if not isinstance(value, Mapping):
        raise SoulGraphError("task metadata must be an object")
    return value


def _predecessor_id(task: Mapping[str, Any]) -> str | None:
    value = _metadata(task).get("soul_supersedes")
    return str(value) if isinstance(value, str) and value else None


def _successor_id(task: Mapping[str, Any]) -> str | None:
    value = _metadata(task).get("soul_superseded_by")
    return str(value) if isinstance(value, str) and value else None


def _assert_superseded(task: Mapping[str, Any], expected_successor: str) -> None:
    metadata = _metadata(task)
    if metadata.get("soul_status") != "SUPERSEDED":
        raise SoulGraphError("lineage predecessor is not marked SUPERSEDED")
    if task.get("active") or task.get("released"):
        raise SoulGraphError("lineage predecessor must be inactive and unreleased")
    if metadata.get("soul_superseded_by") != expected_successor:
        raise SoulGraphError("lineage predecessor successor binding mismatch")


def _resolve_lineage_unlocked(
    store: RuntimeStore,
    task_id: str,
) -> tuple[str, tuple[str, ...]]:
    """Resolve a task from any revision and validate both directions of lineage."""

    initial = store.read_task(task_id)
    if initial is None:
        return task_id, (task_id,)

    ancestors: list[str] = []
    current_id = task_id
    current = initial
    seen = {current_id}
    for _ in range(64):
        predecessor_id = _predecessor_id(current)
        if predecessor_id is None:
            break
        if predecessor_id in seen:
            raise SoulGraphError("task supersession cycle detected")
        predecessor = store.read_task(predecessor_id)
        if predecessor is None:
            raise SoulGraphError("task supersession predecessor is missing or corrupt")
        _assert_superseded(predecessor, current_id)
        ancestors.append(predecessor_id)
        seen.add(predecessor_id)
        current_id = predecessor_id
        current = predecessor
    else:
        raise SoulGraphError("task supersession ancestry exceeds 64 revisions")

    chain = list(reversed(ancestors)) + [task_id]
    current_id = task_id
    current = initial
    seen = set(chain)
    for _ in range(64):
        successor_id = _successor_id(current)
        if successor_id is None:
            if not current.get("active", True) and not current.get("released", False):
                raise SoulGraphError("terminal task revision is inactive without a successor")
            return current_id, tuple(chain)
        _assert_superseded(current, successor_id)
        if successor_id in seen:
            raise SoulGraphError("task supersession cycle detected")
        successor = store.read_task(successor_id)
        if successor is None:
            raise SoulGraphError("task supersession successor is missing or corrupt")
        if _predecessor_id(successor) != current_id:
            raise SoulGraphError("task supersession reverse binding mismatch")
        chain.append(successor_id)
        seen.add(successor_id)
        current_id = successor_id
        current = successor
    raise SoulGraphError("task supersession chain exceeds 64 revisions")


def resolve_current_task_id(root: Path, task_id: str) -> tuple[str, tuple[str, ...]]:
    store = RuntimeStore(root)
    with store.lock("active-task"):
        return _resolve_lineage_unlocked(store, task_id)


def _validated_caller_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(metadata or {})
    forbidden = sorted(
        key
        for key in result
        if key.startswith("soul_") or key in _RESERVED_CALLER_METADATA
    )
    if forbidden:
        raise ValueError(f"caller metadata uses reserved Soul control keys: {forbidden}")
    return result


def _reason_hash(reason: str | None) -> str:
    return text_digest(reason or "automatic-new-frame")


def _active_metadata(
    base: Mapping[str, Any] | None,
    *,
    predecessor_id: str | None,
    reason_hash: str,
    kind: str,
    graph_revision: int = 0,
) -> dict[str, Any]:
    result = {
        key: value
        for key, value in dict(base or {}).items()
        if not key.startswith("soul_") and key not in _RESERVED_CALLER_METADATA
    }
    result.update(
        {
            "soul_status": "ACTIVE",
            "soul_supersedes": predecessor_id,
            "soul_supersession_reason_hash": reason_hash,
            "soul_supersession_kind": kind,
            "soul_graph_revision": graph_revision,
            "raw_supersession_reason_persisted": False,
        }
    )
    return result


def _mark_superseded(
    task: dict[str, Any],
    successor_id: str,
    *,
    reason_hash: str,
    kind: str,
) -> None:
    task["active"] = False
    task["released"] = False
    metadata = task.setdefault("metadata", {})
    metadata.update(
        {
            "soul_status": "SUPERSEDED",
            "soul_superseded_by": successor_id,
            "soul_superseded_at": utcnow(),
            "soul_supersession_reason_hash": reason_hash,
            "soul_supersession_kind": kind,
        }
    )


def _emit_task_started(
    store: RuntimeStore,
    task: TaskState,
    predecessor_id: str | None,
) -> None:
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="task.started",
            component="soul",
            task_id=task.task_id,
            payload_hash=digest(
                {
                    "goal_hash": task.goal_hash,
                    "predecessor_task_id": predecessor_id,
                }
            ),
            timestamp=utcnow(),
            metadata={
                "active": True,
                "automatic": True,
                "predecessor_task_id": predecessor_id,
                "raw_goal_persisted": False,
            },
        )
    )


def _emit_supersession(
    store: RuntimeStore,
    predecessor_id: str,
    successor_id: str,
    *,
    reason_hash: str,
    kind: str,
    predecessor_hash: str | None,
    new_obligation_id: str | None = None,
) -> None:
    payload = {
        "predecessor_hash": predecessor_hash,
        "successor_task_id": successor_id,
        "reason_hash": reason_hash,
        "new_obligation_id": new_obligation_id,
    }
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="task.superseded",
            component="soul",
            task_id=predecessor_id,
            payload_hash=digest(payload),
            timestamp=utcnow(),
            metadata={
                "successor_task_id": successor_id,
                "reason_hash": reason_hash,
                "kind": kind,
                "new_obligation_id": new_obligation_id,
                "raw_reason_persisted": False,
            },
        )
    )


def start_task(
    root: Path,
    goal: str,
    *,
    metadata: dict[str, Any] | None = None,
    supersession_reason: str | None = None,
) -> TaskState:
    """Start a task and preserve any replaced active frame as immutable lineage."""

    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be non-empty")
    caller_metadata = _validated_caller_metadata(metadata)
    store = RuntimeStore(root)
    strict = _runtime_flag(root, "strict_active_task", False)
    automatic_supersession = _runtime_flag(root, "automatic_task_supersession", True)
    reason_hash = _reason_hash(supersession_reason)
    predecessor_id: str | None = None
    predecessor_hash: str | None = None
    task_id = new_id("task")

    with store.lock("active-task"):
        active_id = _active_task_id(store)
        if active_id:
            active = store.read_task(active_id)
            if active is None:
                raise ActiveTaskError("active task pointer targets missing or corrupt state")
            if active.get("active") and not active.get("released"):
                if strict or not automatic_supersession:
                    raise ActiveTaskError(
                        f"active task {active_id} must be resolved before starting another"
                    )
                predecessor_id = active_id
                predecessor_hash = str(active.get("content_hash") or "")
                _mark_superseded(
                    active,
                    task_id,
                    reason_hash=reason_hash,
                    kind="AUTOMATIC_REFRAME",
                )
                store.write_task(active)
            else:
                active_path = store.base / "active_task"
                if active_path.exists():
                    active_path.unlink()

        task = TaskState(
            task_id=task_id,
            goal_hash=text_digest(goal),
            metadata=_active_metadata(
                caller_metadata,
                predecessor_id=predecessor_id,
                reason_hash=reason_hash,
                kind="AUTOMATIC_REFRAME",
            ),
        )
        store.write_task(task)
        write_private_text(store.base / "active_task", task.task_id + "\n")

    if predecessor_id:
        _emit_supersession(
            store,
            predecessor_id,
            task.task_id,
            reason_hash=reason_hash,
            kind="AUTOMATIC_REFRAME",
            predecessor_hash=predecessor_hash,
        )
    _emit_task_started(store, task, predecessor_id)
    try:
        from gauntlet_monitor import snapshot as authority_snapshot

        authority_snapshot(root, task_id=task.task_id)
    except Exception:
        pass
    return task


def _serialize_obligation(obligation: Obligation) -> dict[str, Any]:
    return json.loads(canonical_json(obligation))


def _successor_with_obligation_locked(
    root: Path,
    store: RuntimeStore,
    task_id: str,
    obligation: Obligation,
    *,
    reason: str,
) -> str:
    """Create one successor revision while the caller holds ``active-task``."""

    current_id, _ = _resolve_lineage_unlocked(store, task_id)
    reason_hash = _reason_hash(reason)
    successor_id = new_id("task")
    with store.lock(f"task-{current_id}"):
        current = store.read_task(current_id)
        if current is None:
            raise KeyError(f"unknown task {current_id}")
        core._require_open_task(current)
        predecessor_hash = str(current.get("content_hash") or "")
        successor = json.loads(json.dumps(current))
        successor.pop("content_hash", None)
        successor["task_id"] = successor_id
        successor["active"] = True
        successor["released"] = False
        successor["obligations"] = [
            *successor.get("obligations", []),
            _serialize_obligation(obligation),
        ]
        revision = int(_metadata(current).get("soul_graph_revision", 0)) + 1
        successor["metadata"] = _active_metadata(
            _metadata(current),
            predecessor_id=current_id,
            reason_hash=reason_hash,
            kind="AUTOMATIC_GRAPH_REVISION",
            graph_revision=revision,
        )
        core._normalize_obligations(successor)
        _mark_superseded(
            current,
            successor_id,
            reason_hash=reason_hash,
            kind="AUTOMATIC_GRAPH_REVISION",
        )
        store.write_task(current)
        store.write_task(successor)
        write_private_text(store.base / "active_task", successor_id + "\n")

    _emit_supersession(
        store,
        current_id,
        successor_id,
        reason_hash=reason_hash,
        kind="AUTOMATIC_GRAPH_REVISION",
        predecessor_hash=predecessor_hash,
        new_obligation_id=obligation.obligation_id,
    )
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="task.graph.revised",
            component="soul",
            task_id=successor_id,
            payload_hash=digest(
                {
                    "predecessor_task_id": current_id,
                    "new_obligation_id": obligation.obligation_id,
                }
            ),
            timestamp=utcnow(),
            metadata={
                "predecessor_task_id": current_id,
                "new_obligation_id": obligation.obligation_id,
                "automatic": True,
            },
        )
    )
    return successor_id


def add_obligation(
    root: Path,
    task_id: str,
    kind: ObligationKind,
    claim: str,
    *,
    load_bearing: bool = True,
    metadata: dict[str, Any] | None = None,
) -> Obligation:
    if not isinstance(kind, ObligationKind):
        raise TypeError("kind must be ObligationKind")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be non-empty")
    obligation = Obligation(
        obligation_id=new_id("obl"),
        kind=kind,
        claim=claim,
        load_bearing=load_bearing,
        required_module=MODULE_FOR_KIND[kind],
        metadata=metadata or {},
    )
    store = RuntimeStore(root)
    successor_id: str | None = None
    with store.lock("active-task"):
        current_id, _ = _resolve_lineage_unlocked(store, task_id)
        current = store.read_task(current_id)
        if current is None:
            raise KeyError(f"unknown task {current_id}")
        core._require_open_task(current)
        if _metadata(current).get("soul_frozen"):
            if not _runtime_flag(root, "automatic_graph_revision", True):
                raise SoulGraphError("cannot add obligations after the graph is frozen")
            successor_id = _successor_with_obligation_locked(
                root,
                store,
                current_id,
                obligation,
                reason="new-obligation-after-freeze",
            )
        else:
            core.add_obligation(
                root,
                current_id,
                kind,
                claim,
                load_bearing=load_bearing,
                metadata=metadata,
            )
    if successor_id is not None:
        core.freeze_task(root, successor_id)
    return obligation


def _automatic_assurance_enabled(root: Path) -> bool:
    return _runtime_flag(root, "automatic_assurance", False)


def _ensure_automatic_assurance(root: Path, task_id: str) -> str:
    if not _automatic_assurance_enabled(root):
        return resolve_current_task_id(root, task_id)[0]

    store = RuntimeStore(root)
    successor_id: str | None = None
    with store.lock("active-task"):
        current_id, _ = _resolve_lineage_unlocked(store, task_id)
        task = store.read_task(current_id)
        if task is None or task.get("released"):
            return current_id
        obligations = [
            row for row in task.get("obligations", []) if isinstance(row, Mapping)
        ]
        if any(
            row.get("kind") == ObligationKind.ASSURANCE.value
            and row.get("required_module") in (None, "gauntlet")
            and row.get("load_bearing", True)
            for row in obligations
        ):
            return current_id
        domain_ids = [
            str(row.get("obligation_id"))
            for row in obligations
            if row.get("load_bearing", True)
            and row.get("kind") != ObligationKind.ASSURANCE.value
            and row.get("obligation_id")
        ]
        if not domain_ids:
            return current_id
        assurance = Obligation(
            obligation_id=new_id("obl"),
            kind=ObligationKind.ASSURANCE,
            claim="Run automatic Process Assurance before release",
            load_bearing=True,
            required_module="gauntlet",
            metadata={
                "depends_on": domain_ids,
                "cost_units": 1,
                "risk_rank": 5,
                "information_rank": 5,
                "automatic_control": True,
            },
        )
        if _metadata(task).get("soul_frozen"):
            successor_id = _successor_with_obligation_locked(
                root,
                store,
                current_id,
                assurance,
                reason="automatic-assurance-obligation",
            )
        else:
            core.add_obligation(
                root,
                current_id,
                ObligationKind.ASSURANCE,
                assurance.claim,
                load_bearing=True,
                metadata=dict(assurance.metadata),
            )
    return successor_id or current_id


def freeze_task(root: Path, task_id: str) -> dict[str, Any]:
    current_id = _ensure_automatic_assurance(root, task_id)
    return core.freeze_task(root, current_id)


def _shadow_counterfactual(
    challenge_verdict: Verdict,
    detail: Mapping[str, Any],
    mode: str,
) -> Verdict:
    if mode != "shadow":
        return challenge_verdict
    raw = detail.get("counterfactual_verdict")
    try:
        return Verdict(str(raw))
    except ValueError:
        return challenge_verdict


def _build_batches(
    task_id: str,
    selected: Sequence[RouteCandidate],
    *,
    enabled: bool,
) -> tuple[RouteBatch, ...]:
    if not enabled:
        return core._build_batches(task_id, selected, batch_same_module=False)

    by_module: dict[str, list[RouteCandidate]] = {}
    module_order: list[str] = []
    for candidate in selected:
        if candidate.module not in by_module:
            by_module[candidate.module] = []
            module_order.append(candidate.module)
        by_module[candidate.module].append(candidate)

    batches: list[RouteBatch] = []
    for module in module_order:
        rows = by_module[module]
        shared_groups: dict[str, list[RouteCandidate]] = {}
        isolated: list[RouteCandidate] = []
        for row in rows:
            if row.shared_context_group:
                shared_groups.setdefault(row.shared_context_group, []).append(row)
            else:
                isolated.append(row)
        if isolated:
            obligation_ids = tuple(row.obligation_id for row in isolated)
            batches.append(
                RouteBatch(
                    batch_id=f"batch-{digest({'task': task_id, 'module': module, 'ids': obligation_ids, 'mode': 'isolated-envelope'})[:16]}",
                    module=module,
                    obligation_ids=obligation_ids,
                    cost_units=sum(row.cost_units for row in isolated),
                    shared_context_group=None,
                    context_sharing_status="AUTOMATIC_ISOLATED_SUBREQUESTS_REQUIRED",
                    equivalence_status="PARTITION_REQUIRED_NOT_EMPIRICALLY_CLAIMED",
                )
            )
        for group, grouped in shared_groups.items():
            obligation_ids = tuple(row.obligation_id for row in grouped)
            batches.append(
                RouteBatch(
                    batch_id=f"batch-{digest({'task': task_id, 'module': module, 'ids': obligation_ids, 'group': group})[:16]}",
                    module=module,
                    obligation_ids=obligation_ids,
                    cost_units=sum(row.cost_units for row in grouped),
                    shared_context_group=group,
                    context_sharing_status="CALLER_OPT_IN_SHARED_CONTEXT",
                    equivalence_status="NOT_ESTABLISHED",
                )
            )
    return tuple(batches)


def _select_candidates(
    candidates: Sequence[RouteCandidate],
    policy: RoutingPolicy,
) -> tuple[list[RouteCandidate], list[tuple[str, str]]]:
    if policy.mode == "AUTOMATIC_ALL_READY":
        return list(candidates), []
    selected: list[RouteCandidate] = []
    excluded: list[tuple[str, str]] = []
    used_cost = 0
    for candidate in candidates:
        if (
            policy.max_obligations is not None
            and len(selected) >= policy.max_obligations
        ):
            excluded.append((candidate.obligation_id, "MAX_OBLIGATIONS_EXPERIMENTAL"))
            continue
        if (
            policy.max_cost_units is not None
            and used_cost + candidate.cost_units > policy.max_cost_units
        ):
            excluded.append((candidate.obligation_id, "MAX_COST_UNITS_EXPERIMENTAL"))
            continue
        selected.append(candidate)
        used_cost += candidate.cost_units
    return selected, excluded


def plan_routes(
    root: Path,
    task_id: str,
    *,
    policy: RoutingPolicy | None = None,
) -> RoutingPlan:
    """Create a deterministic plan containing every dependency-ready route by default."""

    policy = policy or RoutingPolicy()
    requested_task_id = task_id
    current_id, _ = resolve_current_task_id(root, requested_task_id)
    frozen = freeze_task(root, current_id)
    resolved_id = str(frozen["task_id"])
    final_id, supersession_chain = resolve_current_task_id(root, requested_task_id)
    if final_id != resolved_id:
        raise SoulGraphError("task lineage changed while the route graph was frozen")

    store = RuntimeStore(root)
    task = store.read_task(resolved_id)
    if task is None:
        raise KeyError(f"unknown task {resolved_id}")
    core._require_open_task(task)
    normalized, obligation_set_hash = core._normalize_obligations(task)
    if _metadata(task).get("soul_obligation_set_hash") != obligation_set_hash:
        raise SoulGraphError("frozen obligation graph drift detected")

    with store.evidence_lock(resolved_id):
        evidence_version = store.evidence_version(resolved_id, assume_locked=True)
        receipts = core._task_receipts(store, resolved_id)
        index = core._receipt_index(task, receipts)
        challenge_policy = ChallengePolicy.from_root(root)
        challenge_hash, challenge_count, resolution_count = core._challenge_snapshot(
            store,
            resolved_id,
        )

        composite: dict[str, Verdict] = {}
        current_state: dict[str, str] = {}
        for row in normalized:
            obligation_id = str(row["obligation_id"])
            receipt = index.get(obligation_id)
            base = core._receipt_verdict(receipt)
            challenge_verdict, detail = core._challenge_effect(
                root,
                store,
                resolved_id,
                row,
                obligation_set_hash,
                challenge_policy.mode,
            )
            routing_challenge = _shadow_counterfactual(
                challenge_verdict,
                detail,
                challenge_policy.mode,
            )
            combined = (
                core._worse(base, routing_challenge)
                if challenge_policy.mode in {"shadow", "enforced"}
                else base
            )
            composite[obligation_id] = combined
            current_state[obligation_id] = (
                "MISSING"
                if receipt is None and combined == Verdict.UNKNOWN
                else combined.value
            )

        relevant = core._relevant_obligation_ids(
            normalized,
            policy.include_non_load_bearing,
        )
        candidates: list[RouteCandidate] = []
        blocked: list[tuple[str, tuple[str, ...]]] = []
        excluded: list[tuple[str, str]] = []
        availability_constrained = policy.available_modules is not None
        available = set(policy.available_modules or ())
        for row in normalized:
            obligation_id = str(row["obligation_id"])
            if obligation_id not in relevant or composite[obligation_id] == Verdict.CLEARED:
                continue
            dependencies = tuple(str(item) for item in row.get("depends_on", []))
            unresolved_dependencies = tuple(
                dependency
                for dependency in dependencies
                if composite.get(dependency) != Verdict.CLEARED
            )
            if unresolved_dependencies:
                blocked.append((obligation_id, unresolved_dependencies))
                continue
            module = str(row["required_module"])
            if availability_constrained and module not in available:
                excluded.append((obligation_id, "MODULE_UNAVAILABLE"))
                continue
            candidates.append(
                RouteCandidate(
                    obligation_id=obligation_id,
                    kind=str(row["kind"]),
                    module=module,
                    dependency_ids=dependencies,
                    current_state=current_state[obligation_id],
                    load_bearing=bool(row["load_bearing"]),
                    risk_rank=int(row["risk_rank"]),
                    information_rank=int(row["information_rank"]),
                    cost_units=int(row["cost_units"]),
                    shared_context_group=row.get("shared_context_group"),
                )
            )

        candidates.sort(
            key=lambda candidate: (
                -core._STATUS_PRIORITY.get(candidate.current_state, 0),
                -candidate.risk_rank,
                -candidate.information_rank,
                candidate.cost_units,
                candidate.module,
                candidate.obligation_id,
            )
        )
        selected, budget_excluded = _select_candidates(candidates, policy)
        excluded.extend(budget_excluded)
        used_cost = sum(candidate.cost_units for candidate in selected)
        unresolved = {
            obligation_id
            for obligation_id in relevant
            if composite.get(obligation_id) != Verdict.CLEARED
        }
        liveness_status, stall_frontier = core._liveness(
            unresolved,
            selected,
            [
                (obligation_id, reason.replace("_EXPERIMENTAL", ""))
                for obligation_id, reason in excluded
            ],
            blocked,
        )
        batches = _build_batches(
            resolved_id,
            selected,
            enabled=policy.batch_same_module,
        )
        challenge_cost_status = (
            "INCLUDED_NOT_MEASURED"
            if challenge_policy.mode == "shadow" and challenge_count
            else "NOT_APPLICABLE"
        )
        input_hash = digest(
            {
                "task_hash": task.get("content_hash"),
                "obligation_set_hash": obligation_set_hash,
                "evidence_version": evidence_version,
                "receipt_hashes": [row.get("content_hash") for row in receipts],
                "challenge_snapshot_hash": challenge_hash,
                "challenge_mode": challenge_policy.mode,
                "policy": asdict(policy),
                "supersession_chain": supersession_chain,
            }
        )

    coverage_certificate_hash = digest(
        {
            "scope": "AUTOMATIC_REVISIONED_DECLARED_GRAPH_ONLY",
            "decomposition_completeness_established": False,
            "relevant_obligations": sorted(relevant),
            "already_cleared": sorted(
                obligation_id
                for obligation_id in relevant
                if composite.get(obligation_id) == Verdict.CLEARED
            ),
            "selected": [candidate.obligation_id for candidate in selected],
            "excluded": sorted(excluded),
            "dependency_blocked": sorted(blocked),
            "liveness_status": liveness_status,
            "stall_frontier": list(stall_frontier),
            "supersession_chain": supersession_chain,
        }
    )
    unresolved_cost_units = sum(
        int(row["cost_units"])
        for row in normalized
        if str(row["obligation_id"]) in relevant
        and composite.get(str(row["obligation_id"])) != Verdict.CLEARED
    )
    selection_certificate_hash = digest(
        {
            "rule": (
                "all_dependency_ready_candidates"
                if policy.mode == "AUTOMATIC_ALL_READY"
                else "priority_order_budget_fill_with_skip_ahead_experimental"
            ),
            "candidate_order": [candidate.obligation_id for candidate in candidates],
            "selected": [candidate.obligation_id for candidate in selected],
            "excluded": excluded,
            "policy": asdict(policy),
            "optimality_claimed": False,
            "coverage_reduction_authorized": policy.mode == "BUDGETED_EXPERIMENTAL",
        }
    )
    payload = {
        "requested_task_id": requested_task_id,
        "task_id": resolved_id,
        "input_hash": input_hash,
        "obligation_set_hash": obligation_set_hash,
        "policy": asdict(policy),
        "selected": [candidate.obligation_id for candidate in selected],
        "excluded": excluded,
        "dependency_blocked": blocked,
        "batches": [asdict(batch) for batch in batches],
        "planned_cost_units": used_cost,
        "unresolved_cost_units": unresolved_cost_units,
        "coverage_certificate_hash": coverage_certificate_hash,
        "selection_certificate_hash": selection_certificate_hash,
        "liveness_status": liveness_status,
        "stall_frontier": list(stall_frontier),
        "supersession_chain": supersession_chain,
        "challenge_count": challenge_count,
        "challenge_resolution_count": resolution_count,
        "schema": SOUL_AUTOMATIC_SCHEMA,
    }
    plan_hash = digest(payload)
    plan = RoutingPlan(
        plan_id=f"route-{plan_hash[:16]}",
        task_id=resolved_id,
        requested_task_id=requested_task_id,
        input_hash=input_hash,
        obligation_set_hash=obligation_set_hash,
        policy=policy,
        selected_obligations=tuple(
            candidate.obligation_id for candidate in selected
        ),
        excluded_obligations=tuple(excluded),
        dependency_blocked=tuple(blocked),
        batches=batches,
        planned_cost_units=used_cost,
        unresolved_cost_units=unresolved_cost_units,
        coverage_certificate_hash=coverage_certificate_hash,
        selection_certificate_hash=selection_certificate_hash,
        plan_hash=plan_hash,
        liveness_status=liveness_status,
        stall_frontier=stall_frontier,
        supersession_chain=supersession_chain,
        challenge_cost_status=challenge_cost_status,
    )
    state = asdict(plan)
    state["content_hash"] = digest(state)
    store.write_named_state("soul_routes", plan.plan_id, state)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="route.plan.automatic",
            component="soul",
            task_id=resolved_id,
            payload_hash=plan.plan_hash,
            timestamp=utcnow(),
            metadata={
                "plan_id": plan.plan_id,
                "routing_mode": policy.mode,
                "selected_count": len(plan.selected_obligations),
                "batch_count": len(plan.batches),
                "liveness_status": plan.liveness_status,
                "authority": plan.authority,
                "execution_authorized": False,
            },
        )
    )
    return plan


def _prepare_release_task_id(root: Path, task_id: str) -> str:
    current_id, _ = resolve_current_task_id(root, task_id)
    task = RuntimeStore(root).read_task(current_id)
    if task is None or task.get("released"):
        return current_id
    return _ensure_automatic_assurance(root, current_id)


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    resolved_id = _prepare_release_task_id(root, task_id)
    verdict, detail = core.release_gate(root, resolved_id)
    detail = dict(detail)
    detail["requested_task_id"] = task_id
    detail["resolved_task_id"] = resolved_id
    return verdict, detail


def release_task(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    resolved_id = _prepare_release_task_id(root, task_id)
    verdict, detail = core.release_task(root, resolved_id)
    detail = dict(detail)
    detail["requested_task_id"] = task_id
    detail["resolved_task_id"] = resolved_id
    return verdict, detail


def _route_manifest(plan: RoutingPlan) -> list[dict[str, Any]]:
    return [
        {
            "batch_id": batch.batch_id,
            "module": batch.module,
            "obligation_ids": list(batch.obligation_ids),
            "context_sharing_status": batch.context_sharing_status,
            "equivalence_status": batch.equivalence_status,
        }
        for batch in plan.batches
    ]


def _assurance_policy(root: Path):
    from gauntlet_automatic import AutomaticAssurancePolicy

    runtime = _runtime_config(root)
    mode = str(runtime.get("automatic_assurance_mode") or "AUTOMATIC_FULL")
    max_cost = runtime.get("automatic_assurance_max_cost_units")
    max_operations = runtime.get("automatic_assurance_max_operations")
    stop_on_issue = runtime.get("automatic_assurance_stop_on_issue", False)
    return AutomaticAssurancePolicy(
        mode=mode,
        max_cost_units=(
            max_cost
            if isinstance(max_cost, int) and not isinstance(max_cost, bool)
            else None
        ),
        max_operations=(
            max_operations
            if isinstance(max_operations, int) and not isinstance(max_operations, bool)
            else None
        ),
        stop_on_issue=stop_on_issue if isinstance(stop_on_issue, bool) else False,
    )


def automatic_release(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Route pending domain work, then run Gauntlet and attempt release."""

    store = RuntimeStore(root)
    current_id, lineage = resolve_current_task_id(root, task_id)
    task = store.read_task(current_id)
    if task is None:
        return Verdict.UNKNOWN, {
            "reason": "task-not-found",
            "requested_task_id": task_id,
            "resolved_task_id": current_id,
            "supersession_chain": lineage,
            "automatic": True,
        }
    if task.get("released"):
        verdict, detail = core.release_task(root, current_id)
        detail = dict(detail)
        detail.update(
            {
                "requested_task_id": task_id,
                "resolved_task_id": current_id,
                "supersession_chain": lineage,
                "automatic": True,
                "routing_plan_id": None,
                "route_manifest": [],
                "assurance_receipt_id": None,
            }
        )
        return verdict, detail

    try:
        normalized, _ = core._normalize_obligations(task)
    except SoulGraphError as exc:
        return Verdict.UNKNOWN, {
            "reason": "obligation-graph-invalid",
            "detail": str(exc),
            "requested_task_id": task_id,
            "resolved_task_id": current_id,
            "supersession_chain": lineage,
            "automatic": True,
        }
    if not any(row["load_bearing"] for row in normalized):
        verdict, detail = core.release_gate(root, current_id)
        detail = dict(detail)
        detail.update(
            {
                "requested_task_id": task_id,
                "resolved_task_id": current_id,
                "supersession_chain": lineage,
                "automatic": True,
                "routing_plan_id": None,
                "routing_liveness_status": "STALLED_NO_LOAD_BEARING_OBLIGATION",
                "route_manifest": [],
                "assurance_receipt_id": None,
            }
        )
        return verdict, detail

    plan = plan_routes(root, task_id)
    resolved_id = plan.task_id
    task = store.read_task(resolved_id)
    if task is None:
        return Verdict.UNKNOWN, {
            "reason": "task-not-found-after-routing",
            "requested_task_id": task_id,
            "resolved_task_id": resolved_id,
            "automatic": True,
        }
    kind_by_id = {
        str(row.get("obligation_id")): str(row.get("kind"))
        for row in task.get("obligations", [])
        if isinstance(row, Mapping)
    }
    pending_domain = [
        obligation_id
        for obligation_id in plan.selected_obligations
        if kind_by_id.get(obligation_id) != ObligationKind.ASSURANCE.value
    ]
    manifest = _route_manifest(plan)
    if pending_domain:
        return Verdict.UNKNOWN, {
            "reason": "automatic-routes-pending",
            "requested_task_id": task_id,
            "resolved_task_id": resolved_id,
            "supersession_chain": plan.supersession_chain,
            "routing_plan_id": plan.plan_id,
            "routing_plan_hash": plan.plan_hash,
            "routing_liveness_status": plan.liveness_status,
            "pending_domain_obligations": pending_domain,
            "route_manifest": manifest,
            "assurance_receipt_id": None,
            "automatic": True,
            "authority": "ROUTING_ONLY",
            "execution_authorized": False,
        }
    if plan.liveness_status.startswith("STALLED"):
        return Verdict.UNKNOWN, {
            "reason": "automatic-routing-stalled",
            "requested_task_id": task_id,
            "resolved_task_id": resolved_id,
            "supersession_chain": plan.supersession_chain,
            "routing_plan_id": plan.plan_id,
            "routing_plan_hash": plan.plan_hash,
            "routing_liveness_status": plan.liveness_status,
            "stall_frontier": list(plan.stall_frontier),
            "route_manifest": manifest,
            "assurance_receipt_id": None,
            "automatic": True,
        }

    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="release.attempted",
            component="soul",
            task_id=resolved_id,
            payload_hash=digest(
                {"task_id": resolved_id, "routing_plan_id": plan.plan_id}
            ),
            timestamp=utcnow(),
            metadata={
                "routing_plan_id": plan.plan_id,
                "automatic": True,
                "requested_task_id": task_id,
            },
        )
    )

    assurance_receipt_id: str | None = None
    if _automatic_assurance_enabled(root):
        from gauntlet_automatic import assurance_obligation_id, run_automatic_assurance

        assurance_id = assurance_obligation_id(root, resolved_id)
        if assurance_id:
            assurance = run_automatic_assurance(
                root,
                assurance_id,
                task_id=resolved_id,
                policy=_assurance_policy(root),
            )
            assurance_receipt_id = assurance.receipt_id

    verdict, detail = core.release_task(root, resolved_id)
    detail = dict(detail)
    detail.update(
        {
            "requested_task_id": task_id,
            "resolved_task_id": resolved_id,
            "supersession_chain": plan.supersession_chain,
            "routing_plan_id": plan.plan_id,
            "routing_plan_hash": plan.plan_hash,
            "routing_liveness_status": plan.liveness_status,
            "route_manifest": manifest,
            "assurance_receipt_id": assurance_receipt_id,
            "automatic": True,
        }
    )
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
