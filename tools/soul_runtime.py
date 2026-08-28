"""Public compatibility surface for the automatic Research Orchestrator."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import soul_vnext as _core
from egrt_store import RuntimeStore
from egrt_types import ObligationKind, Verdict
from soul_automatic import (
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
    add_obligation,
    freeze_task,
    resolve_current_task_id,
    start_task,
)
from soul_automatic import automatic_release as _automatic_release
from soul_automatic import plan_routes as _plan_routes
from soul_automatic import release_gate as _release_gate
from soul_automatic import release_task as _release_task

_PUBLIC_ROUTE_INVARIANTS = {
    ObligationKind.ADVERSARY: "blackgem",
}
for _kind, _module in _PUBLIC_ROUTE_INVARIANTS.items():
    if MODULE_FOR_KIND.get(_kind) != _module:
        raise RuntimeError(f"Soul route registration drift: {_kind.value} -> {_module}")


def _current_task(
    root: Path,
    task_id: str,
) -> tuple[str, tuple[str, ...], dict | None]:
    current_id, lineage = resolve_current_task_id(root, task_id)
    return current_id, lineage, RuntimeStore(root).read_task(current_id)


def _unknown_task_detail(
    requested_task_id: str,
    current_task_id: str,
    lineage: tuple[str, ...],
    reason: str,
    detail: str | None = None,
) -> tuple[Verdict, dict]:
    payload: dict = {
        "reason": reason,
        "requested_task_id": requested_task_id,
        "resolved_task_id": current_task_id,
        "supersession_chain": lineage,
        "authority": "CONTROL_ONLY",
        "target_domain_clearance_authorized": False,
    }
    if detail:
        payload["detail"] = detail
    return Verdict.UNKNOWN, payload


def plan_routes(
    root: Path,
    task_id: str,
    *,
    policy: RoutingPolicy | None = None,
) -> RoutingPlan:
    """Plan the current task while retaining the complete requested-ID lineage."""

    plan = _plan_routes(root, task_id, policy=policy)
    _, lineage = resolve_current_task_id(root, task_id)
    if plan.requested_task_id == task_id and plan.supersession_chain == lineage:
        return plan
    return replace(
        plan,
        requested_task_id=task_id,
        supersession_chain=lineage,
    )


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict]:
    """Evaluate the current task revision and map empty/corrupt state to UNKNOWN."""

    current_id, lineage, task = _current_task(root, task_id)
    if task is None:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "task-not-found",
        )
    load_bearing = [
        row
        for row in task.get("obligations", [])
        if isinstance(row, dict) and row.get("load_bearing", True)
    ]
    if not load_bearing:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "no-load-bearing-obligations",
        )
    try:
        verdict, detail = _release_gate(root, current_id)
    except (KeyError, SoulGraphError) as exc:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "obligation-graph-invalid",
            str(exc),
        )
    result = dict(detail)
    result.update(
        {
            "requested_task_id": task_id,
            "resolved_task_id": current_id,
            "supersession_chain": lineage,
        }
    )
    return verdict, result


def release_task(root: Path, task_id: str) -> tuple[Verdict, dict]:
    """Release the current revision, including idempotent already-released calls."""

    current_id, lineage, task = _current_task(root, task_id)
    if task is None:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "task-not-found",
        )
    if task.get("released"):
        verdict, detail = _core.release_task(root, current_id)
    else:
        load_bearing = [
            row
            for row in task.get("obligations", [])
            if isinstance(row, dict) and row.get("load_bearing", True)
        ]
        if not load_bearing:
            return _unknown_task_detail(
                task_id,
                current_id,
                lineage,
                "no-load-bearing-obligations",
            )
        try:
            verdict, detail = _release_task(root, current_id)
        except (KeyError, SoulGraphError) as exc:
            return _unknown_task_detail(
                task_id,
                current_id,
                lineage,
                "obligation-graph-invalid",
                str(exc),
            )
    result = dict(detail)
    result.update(
        {
            "requested_task_id": task_id,
            "resolved_task_id": current_id,
            "supersession_chain": lineage,
        }
    )
    return verdict, result


def automatic_release(root: Path, task_id: str) -> tuple[Verdict, dict]:
    """Run the automatic route/assure/release cycle on current authority state.

    Freeze first so any automatic graph revision—particularly the assurance
    obligation—exists before the authority snapshot is bound. Detected drift remains
    an ``authority.changed`` event and is intentionally not papered over by a new
    snapshot. Monitor failure is fail-closed downstream: ``refresh`` remains UNKNOWN
    rather than being fabricated as clear.
    """

    current_id, lineage, task = _current_task(root, task_id)
    if task is None:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "task-not-found",
        )
    load_bearing = [
        row
        for row in task.get("obligations", [])
        if isinstance(row, dict) and row.get("load_bearing", True)
    ]
    if not load_bearing:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "no-load-bearing-obligations",
        )
    try:
        frozen = freeze_task(root, current_id)
    except (KeyError, SoulGraphError) as exc:
        return _unknown_task_detail(
            task_id,
            current_id,
            lineage,
            "obligation-graph-invalid",
            str(exc),
        )
    current_id = str(frozen["task_id"])
    _, lineage = resolve_current_task_id(root, task_id)
    try:
        from gauntlet_monitor import check as authority_check
        from gauntlet_monitor import snapshot as authority_snapshot

        drift_code, _ = authority_check(root, emit_event=True)
        if drift_code == 0:
            authority_snapshot(root, task_id=current_id)
    except Exception:
        # The automatic release path will still run. Without a valid snapshot the
        # Gauntlet refresh monitor cannot clear, which is the safe represented state.
        pass
    verdict, detail = _automatic_release(root, current_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": task_id,
            "resolved_task_id": current_id,
            "supersession_chain": lineage,
        }
    )
    return verdict, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--goal", required=True)
    start.add_argument("--supersession-reason")

    add = sub.add_parser("add")
    add.add_argument("task_id")
    add.add_argument("kind", choices=[kind.value for kind in ObligationKind])
    add.add_argument("--claim", required=True)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("task_id")

    plan = sub.add_parser("plan")
    plan.add_argument("task_id")
    plan.add_argument(
        "--mode",
        choices=["AUTOMATIC_ALL_READY", "BUDGETED_EXPERIMENTAL"],
        default="AUTOMATIC_ALL_READY",
    )
    plan.add_argument("--max-cost-units", type=int)
    plan.add_argument("--max-obligations", type=int)
    plan.add_argument("--no-batch", action="store_true")

    gate = sub.add_parser("gate")
    gate.add_argument("task_id")

    release = sub.add_parser("release")
    release.add_argument("task_id")

    auto_release = sub.add_parser("automatic-release")
    auto_release.add_argument("task_id")

    current = sub.add_parser("current")
    current.add_argument("task_id")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "start":
        task = start_task(
            root,
            args.goal,
            supersession_reason=args.supersession_reason,
        )
        print(
            json.dumps(
                {"task_id": task.task_id, "goal_hash": task.goal_hash},
                indent=2,
            )
        )
        return 0
    if args.cmd == "add":
        obligation = add_obligation(
            root,
            args.task_id,
            ObligationKind(args.kind),
            args.claim,
        )
        current_id, lineage = resolve_current_task_id(root, args.task_id)
        print(
            json.dumps(
                {
                    "obligation_id": obligation.obligation_id,
                    "module": obligation.required_module,
                    "current_task_id": current_id,
                    "supersession_chain": lineage,
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "freeze":
        task = freeze_task(root, args.task_id)
        print(
            json.dumps(
                {
                    "requested_task_id": args.task_id,
                    "task_id": task.get("task_id"),
                    "obligation_set_hash": task.get("metadata", {}).get(
                        "soul_obligation_set_hash"
                    ),
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "plan":
        route = plan_routes(
            root,
            args.task_id,
            policy=RoutingPolicy(
                mode=args.mode,
                max_cost_units=args.max_cost_units,
                max_obligations=args.max_obligations,
                batch_same_module=not args.no_batch,
            ),
        )
        print(json.dumps(asdict(route), indent=2))
        return 0
    if args.cmd == "current":
        current_id, lineage = resolve_current_task_id(root, args.task_id)
        print(
            json.dumps(
                {"task_id": current_id, "supersession_chain": lineage},
                indent=2,
            )
        )
        return 0
    if args.cmd == "automatic-release":
        verdict, detail = automatic_release(root, args.task_id)
    elif args.cmd == "release":
        verdict, detail = release_task(root, args.task_id)
    else:
        verdict, detail = release_gate(root, args.task_id)
    print(json.dumps({"verdict": verdict.value, **detail}, indent=2))
    return 0 if verdict == Verdict.CLEARED else 2


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
    "main",
    "plan_routes",
    "release_gate",
    "release_task",
    "resolve_current_task_id",
    "start_task",
]


if __name__ == "__main__":
    raise SystemExit(main())
