"""Public compatibility and CLI surface for the automatic Research Orchestrator."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from egrt_store import RuntimeStore
from egrt_types import ObligationKind, Verdict, digest
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
    plan_routes,
    release_gate,
    release_task,
    resolve_current_task_id,
    start_task,
)
from soul_automatic import automatic_release as _automatic_release

_PUBLIC_ROUTE_INVARIANTS = {
    ObligationKind.ADVERSARY: "blackgem",
}
for _kind, _module in _PUBLIC_ROUTE_INVARIANTS.items():
    if MODULE_FOR_KIND.get(_kind) != _module:
        raise RuntimeError(f"Soul route registration drift: {_kind.value} -> {_module}")


def _authority_failure(
    verdict: Verdict,
    *,
    task_id: str,
    resolved_id: str,
    lineage: tuple[str, ...],
    reason: str,
    extra: dict | None = None,
) -> tuple[Verdict, dict]:
    detail = {
        "reason": reason,
        "requested_task_id": task_id,
        "resolved_task_id": resolved_id,
        "supersession_chain": lineage,
        "automatic": True,
        "authority": "CONTROL_ONLY",
        "target_domain_clearance_authorized": False,
        "routing_plan_id": None,
        "route_manifest": [],
        "assurance_receipt_id": None,
    }
    if extra:
        detail.update(extra)
    return verdict, detail


def automatic_release(root: Path, task_id: str) -> tuple[Verdict, dict]:
    """Run one authority-bound automatic route/assure/release cycle.

    A changed governing state is recorded, then reconciled to a new snapshot, but the
    same call cannot release against that newly adopted state. The host must retry so
    the changed authority is actually reread. Monitor failure is ``UNAVAILABLE`` and
    never falls through to a stale release attempt.
    """

    resolved_id, lineage = resolve_current_task_id(root, task_id)
    store = RuntimeStore(root)
    task = store.read_task(resolved_id)
    if task is None or task.get("released"):
        return _automatic_release(root, task_id)

    load_bearing = [
        row
        for row in task.get("obligations", [])
        if isinstance(row, dict) and row.get("load_bearing", True)
    ]
    if not load_bearing:
        return _automatic_release(root, task_id)

    try:
        frozen = freeze_task(root, resolved_id)
    except (KeyError, SoulGraphError) as exc:
        return _authority_failure(
            Verdict.UNKNOWN,
            task_id=task_id,
            resolved_id=resolved_id,
            lineage=lineage,
            reason="obligation-graph-invalid",
            extra={"detail_type": type(exc).__name__},
        )
    resolved_id = str(frozen["task_id"])
    _, lineage = resolve_current_task_id(root, task_id)

    try:
        from gauntlet_monitor import check as authority_check
        from gauntlet_monitor import snapshot as authority_snapshot

        drift_code, drift = authority_check(root, emit_event=True)
    except Exception as exc:
        return _authority_failure(
            Verdict.UNAVAILABLE,
            task_id=task_id,
            resolved_id=resolved_id,
            lineage=lineage,
            reason="authority-monitor-unavailable",
            extra={"error_type": type(exc).__name__},
        )

    if drift_code:
        try:
            authority_snapshot(root, task_id=resolved_id)
        except Exception as exc:
            return _authority_failure(
                Verdict.UNAVAILABLE,
                task_id=task_id,
                resolved_id=resolved_id,
                lineage=lineage,
                reason="authority-reconciliation-unavailable",
                extra={"error_type": type(exc).__name__},
            )
        return _authority_failure(
            Verdict.UNKNOWN,
            task_id=task_id,
            resolved_id=resolved_id,
            lineage=lineage,
            reason="authority-drift-reconciled-retry-required",
            extra={
                "authority_drift_count": len(drift),
                "authority_drift_hash": digest(drift),
                "retry_required": True,
            },
        )

    try:
        authority_snapshot(root, task_id=resolved_id)
    except Exception as exc:
        return _authority_failure(
            Verdict.UNAVAILABLE,
            task_id=task_id,
            resolved_id=resolved_id,
            lineage=lineage,
            reason="authority-snapshot-unavailable",
            extra={"error_type": type(exc).__name__},
        )

    verdict, detail = _automatic_release(root, task_id)
    result = dict(detail)
    result.update(
        {
            "requested_task_id": task_id,
            "resolved_task_id": result.get("resolved_task_id", resolved_id),
            "supersession_chain": result.get("supersession_chain", lineage),
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
