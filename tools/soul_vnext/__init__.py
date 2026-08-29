"""Typed Research Orchestrator: frozen obligation graphs, routing, and release.

Soul owns task decomposition, route scheduling, integration, and release control. It
never emits a claim-native receipt and cannot clear a domain obligation by itself.
The planner operates only over a caller-declared frozen graph, uses one task-scoped
receipt snapshot per decision, and records deterministic selection certificates
without claiming global optimality or complete decomposition.
"""
from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from egrt_challenge import ChallengePolicy, challenge_gate
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    Obligation,
    ObligationKind,
    RuntimeEvent,
    TaskState,
    Verdict,
    digest,
    text_digest,
)
from private_io import write_private_text

SOUL_SCHEMA = "egrt.soul.routing.v1"

MODULE_FOR_KIND = {
    ObligationKind.PROOF: "mind",
    ObligationKind.DISCOVERY: "space",
    ObligationKind.SYNTHESIS: "reality",
    ObligationKind.ENGINEERING: "power",
    ObligationKind.EVALUATION: "time",
    ObligationKind.ASSURANCE: "gauntlet",
    ObligationKind.PREFLIGHT: "meditate",
    ObligationKind.REVIEW: "council",
    ObligationKind.ADAPTATION: "foil",
    ObligationKind.ADVERSARY: "blackgem",
}

_SEVERITY = {
    Verdict.CLEARED: 0,
    Verdict.UNKNOWN: 1,
    Verdict.UNAVAILABLE: 2,
    Verdict.ISSUE: 3,
}
_STATUS_PRIORITY = {
    "MISSING": 1,
    Verdict.UNKNOWN.value: 2,
    Verdict.UNAVAILABLE.value: 3,
    Verdict.ISSUE.value: 4,
}


class SoulError(ValueError):
    """Base error for invalid orchestration state."""


class ActiveTaskError(SoulError):
    """Raised when a new task would silently replace an unresolved active task."""


class SoulGraphError(SoulError):
    """Raised when the obligation graph is malformed or drifts after freeze."""


@dataclass(frozen=True)
class RoutingPolicy:
    """Caller-frozen structural route budget.

    ``available_modules=None`` means availability was not constrained by the caller.
    An explicit empty tuple means no module is currently available. Cost units are
    an uncalibrated ordering proxy, not measured tokens, money, latency, or compute.
    """

    max_cost_units: int = 8
    max_obligations: int = 8
    batch_same_module: bool = True
    include_non_load_bearing: bool = False
    available_modules: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        for name in ("max_cost_units", "max_obligations"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
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
class RouteCandidate:
    obligation_id: str
    kind: str
    module: str
    dependency_ids: tuple[str, ...]
    current_state: str
    load_bearing: bool
    risk_rank: int
    information_rank: int
    cost_units: int
    shared_context_group: str | None = None


@dataclass(frozen=True)
class RouteBatch:
    batch_id: str
    module: str
    obligation_ids: tuple[str, ...]
    cost_units: int
    shared_context_group: str | None = None
    context_sharing_status: str = "ISOLATED"
    equivalence_status: str = "NOT_APPLICABLE"
    authority: str = "ROUTING_ONLY"
    execution_authorized: bool = False


@dataclass(frozen=True)
class RoutingPlan:
    plan_id: str
    task_id: str
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
    decomposition_scope: str = "CALLER_DECLARED_FROZEN_GRAPH"
    decomposition_completeness_established: bool = False
    cost_model_status: str = "UNCALIBRATED_ORDERING_PROXY"
    challenge_cost_status: str = "NOT_MEASURED"
    efficacy_status: str = "NOT_ESTABLISHED"
    authority: str = "ROUTING_ONLY"
    execution_authorized: bool = False
    schema: str = SOUL_SCHEMA


def _worse(left: Verdict, right: Verdict) -> Verdict:
    return right if _SEVERITY[right] > _SEVERITY[left] else left


def _module_for(obligation: Mapping[str, Any]) -> str | None:
    try:
        return MODULE_FOR_KIND[ObligationKind(str(obligation["kind"]))]
    except (KeyError, ValueError):
        return None


def _require_int(
    metadata: Mapping[str, Any],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = metadata.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SoulGraphError(f"{name} must be int")
    if not minimum <= value <= maximum:
        raise SoulGraphError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _dependencies(obligation: Mapping[str, Any]) -> tuple[str, ...]:
    metadata = obligation.get("metadata")
    if metadata is None:
        return ()
    if not isinstance(metadata, Mapping):
        raise SoulGraphError("obligation metadata must be an object")
    raw = metadata.get("depends_on", [])
    if not isinstance(raw, (list, tuple)):
        raise SoulGraphError("depends_on must be a list or tuple")
    values = tuple(str(item) for item in raw)
    if any(not value.strip() for value in values):
        raise SoulGraphError("depends_on values must be non-empty")
    if len(values) != len(set(values)):
        raise SoulGraphError("depends_on values must be unique")
    return values


def _shared_context_group(metadata: Mapping[str, Any]) -> str | None:
    value = metadata.get("shared_context_group")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SoulGraphError("shared_context_group must be a non-empty string")
    return value.strip()


def _required_kinds(task: Mapping[str, Any]) -> tuple[ObligationKind, ...]:
    metadata = task.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise SoulGraphError("task metadata must be an object")
    raw = metadata.get("required_obligation_kinds", [])
    if not isinstance(raw, (list, tuple)):
        raise SoulGraphError("required_obligation_kinds must be a list or tuple")
    kinds: list[ObligationKind] = []
    for value in raw:
        try:
            kind = ObligationKind(str(value))
        except ValueError as exc:
            raise SoulGraphError(f"unknown required obligation kind: {value}") from exc
        if kind in kinds:
            raise SoulGraphError("required_obligation_kinds must be unique")
        kinds.append(kind)
    return tuple(kinds)


def _normalize_obligations(
    task: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    rows = task.get("obligations", [])
    if not isinstance(rows, list):
        raise SoulGraphError("task obligations must be a list")
    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise SoulGraphError("every obligation must be an object")
        obligation_id = str(raw.get("obligation_id") or "")
        claim = str(raw.get("claim") or "")
        if not obligation_id or not claim.strip():
            raise SoulGraphError("obligation_id and claim must be non-empty")
        if obligation_id in identifiers:
            raise SoulGraphError(f"duplicate obligation_id: {obligation_id}")
        identifiers.add(obligation_id)
        try:
            kind = ObligationKind(str(raw.get("kind")))
        except ValueError as exc:
            raise SoulGraphError(
                f"unknown obligation kind for {obligation_id}"
            ) from exc
        expected_module = MODULE_FOR_KIND[kind]
        declared_module = raw.get("required_module")
        if declared_module not in (None, expected_module):
            raise SoulGraphError(
                f"{obligation_id} required_module must be {expected_module}"
            )
        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise SoulGraphError("obligation metadata must be an object")
        dependencies = _dependencies(raw)
        cost_units = _require_int(
            metadata, "cost_units", 1, minimum=1, maximum=1_000_000
        )
        risk_rank = _require_int(
            metadata, "risk_rank", 3, minimum=0, maximum=5
        )
        information_rank = _require_int(
            metadata, "information_rank", 3, minimum=0, maximum=5
        )
        load_bearing = raw.get("load_bearing", True)
        if not isinstance(load_bearing, bool):
            raise SoulGraphError("load_bearing must be bool")
        normalized.append(
            {
                "obligation_id": obligation_id,
                "kind": kind.value,
                "claim": claim,
                "load_bearing": load_bearing,
                "required_module": expected_module,
                "metadata": dict(metadata),
                "depends_on": list(dependencies),
                "cost_units": cost_units,
                "risk_rank": risk_rank,
                "information_rank": information_rank,
                "shared_context_group": _shared_context_group(metadata),
            }
        )

    by_id = {row["obligation_id"]: row for row in normalized}
    for row in normalized:
        obligation_id = row["obligation_id"]
        for dependency in row["depends_on"]:
            if dependency == obligation_id:
                raise SoulGraphError(f"{obligation_id} cannot depend on itself")
            if dependency not in by_id:
                raise SoulGraphError(
                    f"{obligation_id} depends on unknown obligation {dependency}"
                )

    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(obligation_id: str) -> None:
        if obligation_id in permanent:
            return
        if obligation_id in temporary:
            raise SoulGraphError("obligation dependency cycle detected")
        temporary.add(obligation_id)
        for dependency in by_id[obligation_id]["depends_on"]:
            visit(dependency)
        temporary.remove(obligation_id)
        permanent.add(obligation_id)

    for obligation_id in sorted(by_id):
        visit(obligation_id)

    normalized.sort(key=lambda row: row["obligation_id"])
    obligation_set_hash = digest(
        {
            "schema": SOUL_SCHEMA,
            "task_id": task.get("task_id"),
            "obligations": normalized,
        }
    )
    return normalized, obligation_set_hash


def _assert_required_kinds(
    task: Mapping[str, Any],
    normalized: Sequence[Mapping[str, Any]],
) -> None:
    required = _required_kinds(task)
    if not required:
        return
    present = {ObligationKind(str(row["kind"])) for row in normalized}
    missing = [kind.value for kind in required if kind not in present]
    if missing:
        raise SoulGraphError(f"required obligation kinds are missing: {missing}")


def _active_task_id(store: RuntimeStore) -> str | None:
    path = store.base / "active_task"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _require_open_task(task: Mapping[str, Any]) -> None:
    if task.get("released") or not task.get("active", True):
        raise SoulGraphError("task is closed")


def start_task(
    root: Path,
    goal: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> TaskState:
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be non-empty")
    store = RuntimeStore(root)
    with store.lock("active-task"):
        active_id = _active_task_id(store)
        if active_id:
            active = store.read_task(active_id)
            if active is not None and active.get("active") and not active.get("released"):
                raise ActiveTaskError(
                    f"active task {active_id} must be resolved before starting another"
                )
            active_path = store.base / "active_task"
            if active_path.exists():
                active_path.unlink()
        task = TaskState(
            task_id=new_id("task"),
            goal_hash=text_digest(goal),
            metadata=metadata or {},
        )
        store.write_task(task)
        write_private_text(store.base / "active_task", task.task_id + "\n")
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="task.started",
            component="soul",
            task_id=task.task_id,
            payload_hash=digest({"goal_hash": task.goal_hash}),
            timestamp=utcnow(),
            metadata={"active": True, "raw_goal_persisted": False},
        )
    )
    try:
        from gauntlet_monitor import snapshot as authority_snapshot

        authority_snapshot(root, task_id=task.task_id)
    except Exception:
        pass
    return task


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
    store = RuntimeStore(root)
    obligation = Obligation(
        obligation_id=new_id("obl"),
        kind=kind,
        claim=claim,
        load_bearing=load_bearing,
        required_module=MODULE_FOR_KIND[kind],
        metadata=metadata or {},
    )
    with store.lock(f"task-{task_id}"):
        raw = store.read_task(task_id)
        if raw is None:
            raise KeyError(f"unknown task {task_id}")
        _require_open_task(raw)
        if raw.get("metadata", {}).get("soul_frozen"):
            raise SoulGraphError("cannot add obligations after the graph is frozen")
        serialized = json.loads(
            json.dumps(
                obligation,
                default=lambda value: getattr(value, "value", value.__dict__),
            )
        )
        trial = dict(raw)
        trial["obligations"] = [*raw.get("obligations", []), serialized]
        _normalize_obligations(trial)
        raw.setdefault("obligations", []).append(serialized)
        store.write_task(raw)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="obligation.created",
            component="soul",
            task_id=task_id,
            payload_hash=digest(obligation),
            timestamp=utcnow(),
            metadata={
                "obligation_id": obligation.obligation_id,
                "kind": kind.value,
                "required_module": obligation.required_module,
                "load_bearing": load_bearing,
            },
        )
    )
    return obligation


def freeze_task(root: Path, task_id: str) -> dict[str, Any]:
    """Validate and freeze a caller-declared graph; idempotent if unchanged."""
    store = RuntimeStore(root)
    with store.lock(f"task-{task_id}"):
        task = store.read_task(task_id)
        if task is None:
            raise KeyError(f"unknown task {task_id}")
        _require_open_task(task)
        normalized, obligation_set_hash = _normalize_obligations(task)
        if not any(row["load_bearing"] for row in normalized):
            raise SoulGraphError("task requires at least one load-bearing obligation")
        _assert_required_kinds(task, normalized)
        metadata = task.setdefault("metadata", {})
        previous = metadata.get("soul_obligation_set_hash")
        if metadata.get("soul_frozen"):
            if previous != obligation_set_hash:
                raise SoulGraphError("frozen obligation graph drift detected")
            return task
        metadata.update(
            {
                "soul_frozen": True,
                "soul_schema": SOUL_SCHEMA,
                "soul_obligation_set_hash": obligation_set_hash,
                "soul_frozen_at": utcnow(),
                "soul_decomposition_scope": "CALLER_DECLARED_FROZEN_GRAPH",
                "soul_decomposition_completeness_established": False,
            }
        )
        store.write_task(task)
        frozen = store.read_task(task_id)
    if frozen is None:
        raise SoulGraphError("frozen task could not be reread")
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="task.frozen",
            component="soul",
            task_id=task_id,
            payload_hash=obligation_set_hash,
            timestamp=utcnow(),
            metadata={
                "obligation_set_hash": obligation_set_hash,
                "load_bearing_count": sum(
                    1 for row in normalized if row["load_bearing"]
                ),
                "decomposition_completeness_established": False,
                "authority": "CONTROL_ONLY",
            },
        )
    )
    return frozen


def _receipt_order(row: Mapping[str, Any]) -> tuple[int, int, str]:
    """Prefer monotonic store sequence; timestamps are legacy fallback only."""
    sequence = row.get("seq")
    stamp = str(
        row.get("stored_at")
        or row.get("finished_at")
        or row.get("started_at")
        or ""
    )
    if isinstance(sequence, int) and not isinstance(sequence, bool):
        return 1, sequence, stamp
    return 0, 0, stamp


def _task_receipts(store: RuntimeStore, task_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in store.receipts.glob("*.json"):
        receipt = store.read_receipt(path.stem)
        if receipt is not None and receipt.get("task_id") == task_id:
            rows.append(receipt)
    rows.sort(key=_receipt_order)
    return rows


def _receipt_index(
    task: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    expected = {
        str(row.get("obligation_id")): row.get("required_module") or _module_for(row)
        for row in task.get("obligations", [])
        if isinstance(row, Mapping)
    }
    index: dict[str, Mapping[str, Any]] = {}
    for receipt in receipts:
        obligation_id = str(receipt.get("obligation_id") or "")
        if obligation_id and receipt.get("module") == expected.get(obligation_id):
            index[obligation_id] = receipt
    return index


def _receipt_verdict(receipt: Mapping[str, Any] | None) -> Verdict:
    if receipt is None:
        return Verdict.UNKNOWN
    try:
        return Verdict(str(receipt.get("verdict", Verdict.UNKNOWN.value)))
    except ValueError:
        return Verdict.UNKNOWN


def _challenge_snapshot(store: RuntimeStore, task_id: str) -> tuple[str, int, int]:
    challenges = store.challenges_for(task_id)
    challenge_ids = {str(row.get("challenge_id")) for row in challenges}
    resolutions: list[dict[str, Any]] = []
    for path in store.challenge_resolutions.glob("*.json"):
        row = store.read_challenge_resolution(path.stem)
        if row is not None and str(row.get("challenge_id")) in challenge_ids:
            resolutions.append(row)
    resolutions.sort(key=_receipt_order)
    snapshot_hash = digest(
        {
            "challenge_hashes": [row.get("content_hash") for row in challenges],
            "resolution_hashes": [row.get("content_hash") for row in resolutions],
        }
    )
    return snapshot_hash, len(challenges), len(resolutions)


def _challenge_binding_errors(
    store: RuntimeStore,
    task_id: str,
    obligation: Mapping[str, Any],
    obligation_set_hash: str,
) -> list[str]:
    obligation_id = str(obligation["obligation_id"])
    expected_module = str(obligation["required_module"])
    metadata = obligation.get("metadata") or {}
    expected_candidate = metadata.get("candidate_hash") if isinstance(metadata, Mapping) else None
    expected_scope = metadata.get("scope_hash") if isinstance(metadata, Mapping) else None
    errors: list[str] = []
    for challenge in store.challenges_for(task_id, obligation_id):
        if not challenge.get("load_bearing", True):
            continue
        challenge_id = str(challenge.get("challenge_id") or "unknown")
        if challenge.get("obligation_set_hash") != obligation_set_hash:
            errors.append(f"{challenge_id}:obligation-set")
        if challenge.get("target_module") != expected_module:
            errors.append(f"{challenge_id}:target-module")
        if expected_candidate is not None and challenge.get("candidate_hash") != expected_candidate:
            errors.append(f"{challenge_id}:candidate")
        if expected_scope is not None and challenge.get("scope_hash") != expected_scope:
            errors.append(f"{challenge_id}:scope")
    return errors


def _challenge_effect(
    root: Path,
    store: RuntimeStore,
    task_id: str,
    obligation: Mapping[str, Any],
    obligation_set_hash: str,
    mode: str,
) -> tuple[Verdict, dict[str, Any]]:
    binding_errors = _challenge_binding_errors(
        store,
        task_id,
        obligation,
        obligation_set_hash,
    )
    if binding_errors:
        return Verdict.ISSUE, {
            "mode": mode,
            "applied": mode == "enforced",
            "binding_valid": False,
            "binding_errors": binding_errors,
            "counterfactual_verdict": Verdict.ISSUE.value,
        }
    try:
        verdict, detail = challenge_gate(
            root,
            task_id,
            str(obligation["obligation_id"]),
            mode=mode,
        )
    except (RuntimeError, ValueError) as exc:
        return Verdict.UNAVAILABLE, {
            "mode": mode,
            "applied": mode == "enforced",
            "binding_valid": True,
            "reason": f"challenge-gate-unavailable:{type(exc).__name__}",
        }
    detail = dict(detail)
    detail["binding_valid"] = True
    return verdict, detail


def _relevant_obligation_ids(
    normalized: Sequence[Mapping[str, Any]],
    include_non_load_bearing: bool,
) -> set[str]:
    by_id = {str(row["obligation_id"]): row for row in normalized}
    if include_non_load_bearing:
        relevant = set(by_id)
    else:
        relevant = {
            obligation_id
            for obligation_id, row in by_id.items()
            if bool(row.get("load_bearing"))
        }
    stack = list(relevant)
    while stack:
        current = stack.pop()
        for dependency in by_id[current].get("depends_on", []):
            dependency = str(dependency)
            if dependency not in relevant:
                relevant.add(dependency)
                stack.append(dependency)
    return relevant


def _build_batches(
    task_id: str,
    selected: Sequence[RouteCandidate],
    *,
    batch_same_module: bool,
) -> tuple[RouteBatch, ...]:
    groups: list[tuple[str, str | None, list[RouteCandidate]]] = []
    positions: dict[tuple[str, str], int] = {}
    for candidate in selected:
        group = candidate.shared_context_group
        if not batch_same_module or group is None:
            groups.append((candidate.module, None, [candidate]))
            continue
        key = (candidate.module, group)
        if key not in positions:
            positions[key] = len(groups)
            groups.append((candidate.module, group, []))
        groups[positions[key]][2].append(candidate)

    batches: list[RouteBatch] = []
    for module, group, candidates in groups:
        obligation_ids = tuple(candidate.obligation_id for candidate in candidates)
        shared = group is not None and len(candidates) > 1
        payload = {
            "task_id": task_id,
            "module": module,
            "shared_context_group": group,
            "obligations": obligation_ids,
        }
        batches.append(
            RouteBatch(
                batch_id=f"batch-{digest(payload)[:16]}",
                module=module,
                obligation_ids=obligation_ids,
                cost_units=sum(candidate.cost_units for candidate in candidates),
                shared_context_group=group,
                context_sharing_status=(
                    "CALLER_OPT_IN_SHARED_CONTEXT" if shared else "ISOLATED"
                ),
                equivalence_status=(
                    "NOT_ESTABLISHED" if shared else "NOT_APPLICABLE"
                ),
            )
        )
    return tuple(batches)


def _liveness(
    unresolved: set[str],
    selected: Sequence[RouteCandidate],
    excluded: Sequence[tuple[str, str]],
    blocked: Sequence[tuple[str, tuple[str, ...]]],
) -> tuple[str, tuple[str, ...]]:
    if not unresolved:
        return "CLEARED", ()
    if selected:
        return "RUNNABLE", ()
    unavailable = [item for item, reason in excluded if reason == "MODULE_UNAVAILABLE"]
    if unavailable:
        return "STALLED_MODULE_UNAVAILABLE", tuple(sorted(unavailable))
    budgeted = [
        item
        for item, reason in excluded
        if reason in {"MAX_COST_UNITS", "MAX_OBLIGATIONS"}
    ]
    if budgeted:
        return "STALLED_BUDGET", tuple(budgeted)
    if blocked:
        frontier = sorted({dep for _, dependencies in blocked for dep in dependencies})
        return "STALLED_DEPENDENCY_FRONTIER", tuple(frontier)
    return "STALLED_NO_EXECUTABLE_ROUTE", tuple(sorted(unresolved))


def plan_routes(
    root: Path,
    task_id: str,
    *,
    policy: RoutingPolicy | None = None,
) -> RoutingPlan:
    """Create a deterministic, dependency-aware, non-executing routing plan."""
    policy = policy or RoutingPolicy()
    freeze_task(root, task_id)
    store = RuntimeStore(root)
    task = store.read_task(task_id)
    if task is None:
        raise KeyError(f"unknown task {task_id}")
    _require_open_task(task)
    normalized, obligation_set_hash = _normalize_obligations(task)
    if task.get("metadata", {}).get("soul_obligation_set_hash") != obligation_set_hash:
        raise SoulGraphError("frozen obligation graph drift detected")

    with store.evidence_lock(task_id):
        evidence_version = store.evidence_version(task_id, assume_locked=True)
        receipts = _task_receipts(store, task_id)
        index = _receipt_index(task, receipts)
        challenge_policy = ChallengePolicy.from_root(root)
        challenge_hash, challenge_count, resolution_count = _challenge_snapshot(
            store,
            task_id,
        )

        composite: dict[str, Verdict] = {}
        current_state: dict[str, str] = {}
        for row in normalized:
            obligation_id = str(row["obligation_id"])
            receipt = index.get(obligation_id)
            base = _receipt_verdict(receipt)
            challenge_verdict, _ = _challenge_effect(
                root,
                store,
                task_id,
                row,
                obligation_set_hash,
                challenge_policy.mode,
            )
            combined = (
                _worse(base, challenge_verdict)
                if challenge_policy.mode == "enforced"
                else base
            )
            composite[obligation_id] = combined
            current_state[obligation_id] = (
                "MISSING"
                if receipt is None and combined == Verdict.UNKNOWN
                else combined.value
            )

        relevant = _relevant_obligation_ids(
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
                -_STATUS_PRIORITY.get(candidate.current_state, 0),
                -candidate.risk_rank,
                -candidate.information_rank,
                candidate.cost_units,
                candidate.module,
                candidate.obligation_id,
            )
        )
        selected: list[RouteCandidate] = []
        used_cost = 0
        stop_reason: str | None = None
        stop_index = len(candidates)
        for index_position, candidate in enumerate(candidates):
            if len(selected) >= policy.max_obligations:
                stop_reason = "MAX_OBLIGATIONS"
                stop_index = index_position
                break
            if used_cost + candidate.cost_units > policy.max_cost_units:
                stop_reason = "MAX_COST_UNITS"
                stop_index = index_position
                break
            selected.append(candidate)
            used_cost += candidate.cost_units
        if stop_reason is not None:
            excluded.extend(
                (candidate.obligation_id, stop_reason)
                for candidate in candidates[stop_index:]
            )

        unresolved = {
            obligation_id
            for obligation_id in relevant
            if composite.get(obligation_id) != Verdict.CLEARED
        }
        liveness_status, stall_frontier = _liveness(
            unresolved,
            selected,
            excluded,
            blocked,
        )
        batches = _build_batches(
            task_id,
            selected,
            batch_same_module=policy.batch_same_module,
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
            }
        )

    coverage_certificate_hash = digest(
        {
            "scope": "FROZEN_DECLARED_OBLIGATION_GRAPH_ONLY",
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
                "state_desc_risk_desc_information_desc_cost_asc_module_asc_"
                "obligation_id_asc_strict_prefix_under_budget"
            ),
            "candidate_order": [candidate.obligation_id for candidate in candidates],
            "selected": [candidate.obligation_id for candidate in selected],
            "excluded": excluded,
            "policy": asdict(policy),
            "budget_monotonicity_scope": "FIXED_CANDIDATE_ORDER_AND_AVAILABILITY",
            "optimality_claimed": False,
        }
    )
    payload = {
        "task_id": task_id,
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
        "cost_model_status": "UNCALIBRATED_ORDERING_PROXY",
        "challenge_cost_status": challenge_cost_status,
        "efficacy_status": "NOT_ESTABLISHED",
        "challenge_count": challenge_count,
        "challenge_resolution_count": resolution_count,
        "schema": SOUL_SCHEMA,
    }
    plan_hash = digest(payload)
    plan = RoutingPlan(
        plan_id=f"route-{plan_hash[:16]}",
        task_id=task_id,
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
        challenge_cost_status=challenge_cost_status,
    )
    state = asdict(plan)
    state["content_hash"] = digest(state)
    store.write_named_state("soul_routes", plan.plan_id, state)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="route.plan.frozen",
            component="soul",
            task_id=task_id,
            payload_hash=plan.plan_hash,
            timestamp=utcnow(),
            metadata={
                "plan_id": plan.plan_id,
                "selected_count": len(plan.selected_obligations),
                "batch_count": len(plan.batches),
                "planned_cost_units": plan.planned_cost_units,
                "liveness_status": plan.liveness_status,
                "cost_model_status": plan.cost_model_status,
                "authority": plan.authority,
                "execution_authorized": False,
            },
        )
    )
    return plan


def _evaluate_release_locked(
    root: Path,
    store: RuntimeStore,
    task_id: str,
) -> tuple[Verdict, dict[str, Any]]:
    task = store.read_task(task_id)
    if task is None:
        return Verdict.UNKNOWN, {"reason": "task-not-found", "task_id": task_id}
    try:
        normalized, obligation_set_hash = _normalize_obligations(task)
        _assert_required_kinds(task, normalized)
    except SoulGraphError as exc:
        return Verdict.UNKNOWN, {
            "reason": "obligation-graph-invalid",
            "task_id": task_id,
            "detail": str(exc),
        }
    frozen_hash = task.get("metadata", {}).get("soul_obligation_set_hash")
    if frozen_hash != obligation_set_hash:
        return Verdict.UNKNOWN, {
            "reason": "frozen-obligation-graph-drift",
            "task_id": task_id,
            "expected_obligation_set_hash": frozen_hash,
            "observed_obligation_set_hash": obligation_set_hash,
        }
    load_bearing = [row for row in normalized if row["load_bearing"]]
    if not load_bearing:
        return Verdict.UNKNOWN, {
            "reason": "no-load-bearing-obligations",
            "task_id": task_id,
            "decomposition_scope": "CALLER_DECLARED_FROZEN_GRAPH",
        }
    effective_ids = _relevant_obligation_ids(normalized, False)
    release_obligations = [
        row for row in normalized if str(row["obligation_id"]) in effective_ids
    ]

    evidence_version = store.evidence_version(task_id, assume_locked=True)
    receipts = _task_receipts(store, task_id)
    index = _receipt_index(task, receipts)
    challenge_policy = ChallengePolicy.from_root(root)
    challenge_snapshot_hash, challenge_count, resolution_count = _challenge_snapshot(
        store,
        task_id,
    )
    details: list[dict[str, Any]] = []
    overall = Verdict.CLEARED
    for obligation in release_obligations:
        obligation_id = str(obligation["obligation_id"])
        current = index.get(obligation_id)
        domain_verdict = _receipt_verdict(current)
        challenge_verdict, challenge_detail = _challenge_effect(
            root,
            store,
            task_id,
            obligation,
            obligation_set_hash,
            challenge_policy.mode,
        )
        applied_challenge = (
            challenge_verdict
            if challenge_policy.mode == "enforced"
            else Verdict.CLEARED
        )
        verdict = _worse(domain_verdict, applied_challenge)
        row: dict[str, Any] = {
            "obligation_id": obligation_id,
            "kind": obligation["kind"],
            "required_module": obligation["required_module"],
            "verdict": verdict.value,
            "domain_verdict": domain_verdict.value,
            "challenge_mode": challenge_policy.mode,
            "challenge_verdict": challenge_verdict.value,
            "challenge": challenge_detail,
            "effective_load_bearing": obligation_id in effective_ids,
            "declared_load_bearing": bool(obligation["load_bearing"]),
        }
        if current is None:
            row["reason"] = "missing-receipt"
        else:
            row.update(
                {
                    "receipt_id": current.get("receipt_id"),
                    "receipt_content_hash": current.get("content_hash"),
                    "receipt_seq": current.get("seq"),
                    "historical_receipt_ids": [
                        receipt.get("receipt_id")
                        for receipt in receipts
                        if receipt.get("obligation_id") == obligation_id
                        and receipt.get("module") == obligation["required_module"]
                        and receipt.get("receipt_id") != current.get("receipt_id")
                    ],
                }
            )
        details.append(row)
        overall = _worse(overall, verdict)

    challenge_cost_status = (
        "INCLUDED_NOT_MEASURED"
        if challenge_policy.mode == "shadow" and challenge_count
        else "NOT_APPLICABLE"
    )
    snapshot_payload = {
        "task_hash": task.get("content_hash"),
        "obligation_set_hash": obligation_set_hash,
        "evidence_version": evidence_version,
        "receipt_hashes": [row.get("content_hash") for row in receipts],
        "challenge_snapshot_hash": challenge_snapshot_hash,
        "challenge_mode": challenge_policy.mode,
        "obligation_verdicts": [
            (row["obligation_id"], row["verdict"]) for row in details
        ],
    }
    snapshot_hash = digest(snapshot_payload)
    release_token = digest(
        {
            "task_id": task_id,
            "obligation_set_hash": obligation_set_hash,
            "evidence_version": evidence_version,
            "snapshot_hash": snapshot_hash,
        }
    )
    return overall, {
        "task_id": task_id,
        "obligations": details,
        "obligation_set_hash": obligation_set_hash,
        "snapshot_hash": snapshot_hash,
        "release_token": release_token,
        "evidence_version": evidence_version,
        "challenge_snapshot_hash": challenge_snapshot_hash,
        "challenge_count": challenge_count,
        "challenge_resolution_count": resolution_count,
        "challenge_cost_status": challenge_cost_status,
        "receipt_scan_passes": 1,
        "receipt_count": len(receipts),
        "decomposition_scope": "CALLER_DECLARED_FROZEN_GRAPH",
        "decomposition_completeness_established": False,
        "release_consistency": "COOPERATIVE_TASK_EVIDENCE_COMPARE_AND_SWAP",
        "release_consistency_scope": "RUNTIME_STORE_WRITERS_ONLY",
        "authority": "CONTROL_ONLY",
        "target_domain_clearance_authorized": False,
        "efficacy_status": "NOT_ESTABLISHED",
    }


def _evaluate_release(
    root: Path,
    task_id: str,
    *,
    ensure_frozen: bool,
    assume_evidence_locked: bool = False,
) -> tuple[Verdict, dict[str, Any]]:
    if ensure_frozen:
        try:
            freeze_task(root, task_id)
        except KeyError:
            return Verdict.UNKNOWN, {"reason": "task-not-found", "task_id": task_id}
        except SoulGraphError as exc:
            return Verdict.UNKNOWN, {
                "reason": "obligation-graph-invalid",
                "task_id": task_id,
                "detail": str(exc),
            }
    store = RuntimeStore(root)
    context = nullcontext() if assume_evidence_locked else store.evidence_lock(task_id)
    with context:
        return _evaluate_release_locked(root, store, task_id)


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Evaluate one frozen release snapshot without granting domain authority."""
    return _evaluate_release(root, task_id, ensure_frozen=True)


def _release_control_seal(metadata: Mapping[str, Any], task_id: str) -> str:
    return digest(
        {
            "task_id": task_id,
            "release_token": metadata.get("soul_release_token"),
            "snapshot_hash": metadata.get("soul_release_snapshot_hash"),
            "obligation_set_hash": metadata.get("soul_release_obligation_set_hash"),
            "evidence_version": metadata.get("soul_release_evidence_version"),
            "authority": metadata.get("soul_release_authority"),
            "consistency": metadata.get("soul_release_consistency"),
        }
    )


def _released_result(task: Mapping[str, Any], task_id: str) -> tuple[Verdict, dict[str, Any]]:
    metadata = task.get("metadata") or {}
    stored = metadata.get("soul_release_control_seal")
    expected = _release_control_seal(metadata, task_id)
    if not stored or stored != expected:
        return Verdict.UNKNOWN, {
            "reason": "release-control-seal-invalid",
            "task_id": task_id,
        }
    return Verdict.CLEARED, {
        "task_id": task_id,
        "already_released": True,
        "snapshot_hash": metadata.get("soul_release_snapshot_hash"),
        "release_token": metadata.get("soul_release_token"),
        "release_consistency": metadata.get("soul_release_consistency"),
        "release_consistency_scope": "RUNTIME_STORE_WRITERS_ONLY",
    }


def release_task(root: Path, task_id: str) -> tuple[Verdict, dict[str, Any]]:
    """Commit release with a cooperative task/evidence compare-and-swap token."""
    store = RuntimeStore(root)
    existing = store.read_task(task_id)
    if existing is None:
        return Verdict.UNKNOWN, {"reason": "task-not-found", "task_id": task_id}
    if existing.get("released"):
        return _released_result(existing, task_id)

    verdict, detail = _evaluate_release(root, task_id, ensure_frozen=True)
    if verdict != Verdict.CLEARED:
        return verdict, detail
    expected_token = detail["release_token"]

    with store.lock(f"task-{task_id}"):
        with store.evidence_lock(task_id):
            current = store.read_task(task_id)
            if current is None:
                return Verdict.UNKNOWN, {"reason": "task-not-found", "task_id": task_id}
            if current.get("released"):
                return _released_result(current, task_id)
            current_verdict, current_detail = _evaluate_release(
                root,
                task_id,
                ensure_frozen=False,
                assume_evidence_locked=True,
            )
            if (
                current_verdict != Verdict.CLEARED
                or current_detail.get("release_token") != expected_token
            ):
                return Verdict.UNKNOWN, {
                    "reason": "release-input-drift",
                    "task_id": task_id,
                    "expected_release_token": expected_token,
                    "observed_release_token": current_detail.get("release_token"),
                    "observed_verdict": current_verdict.value,
                }
            released_at = utcnow()
            metadata = current.setdefault("metadata", {})
            metadata.update(
                {
                    "soul_release_token": expected_token,
                    "soul_release_snapshot_hash": current_detail["snapshot_hash"],
                    "soul_release_obligation_set_hash": current_detail[
                        "obligation_set_hash"
                    ],
                    "soul_release_evidence_version": current_detail["evidence_version"],
                    "soul_released_at": released_at,
                    "soul_release_authority": "CONTROL_ONLY",
                    "soul_release_consistency": (
                        "COOPERATIVE_TASK_EVIDENCE_COMPARE_AND_SWAP"
                    ),
                }
            )
            metadata["soul_release_control_seal"] = _release_control_seal(
                metadata,
                task_id,
            )
            current["active"] = False
            current["released"] = True
            store.write_task(current)

    active = store.base / "active_task"
    if active.exists() and active.read_text(encoding="utf-8").strip() == task_id:
        active.unlink()
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="release.completed",
            component="soul",
            task_id=task_id,
            payload_hash=expected_token,
            timestamp=utcnow(),
            metadata={
                "verdict": Verdict.CLEARED.value,
                "snapshot_hash": detail["snapshot_hash"],
                "release_token": expected_token,
                "release_consistency": (
                    "COOPERATIVE_TASK_EVIDENCE_COMPARE_AND_SWAP"
                ),
                "authority": "CONTROL_ONLY",
                "target_domain_clearance_authorized": False,
            },
        )
    )
    return Verdict.CLEARED, detail


__all__ = [
    "ActiveTaskError",
    "MODULE_FOR_KIND",
    "RouteBatch",
    "RouteCandidate",
    "RoutingPlan",
    "RoutingPolicy",
    "SOUL_SCHEMA",
    "SoulError",
    "SoulGraphError",
    "add_obligation",
    "freeze_task",
    "plan_routes",
    "release_gate",
    "release_task",
    "start_task",
]
