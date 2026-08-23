"""Typed Research Orchestrator runtime: obligations, routing and release gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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


# Release severity, worst first. UNAVAILABLE must outrank CLEARED: a module that
# could not run has not cleared anything.
_SEVERITY = {
    Verdict.CLEARED: 0,
    Verdict.UNKNOWN: 1,
    Verdict.UNAVAILABLE: 2,
    Verdict.ISSUE: 3,
}


def _worse(left: Verdict, right: Verdict) -> Verdict:
    return right if _SEVERITY[right] > _SEVERITY[left] else left


def _module_for(obligation: dict) -> str | None:
    try:
        return MODULE_FOR_KIND[ObligationKind(obligation["kind"])]
    except (KeyError, ValueError):
        return None


def start_task(root: Path, goal: str, *, metadata: dict | None = None) -> TaskState:
    store = RuntimeStore(root)
    task = TaskState(task_id=new_id("task"), goal_hash=text_digest(goal), metadata=metadata or {})
    store.write_task(task)
    write_private_text(store.base / "active_task", task.task_id + "\n")
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type="task.started", component="soul",
        task_id=task.task_id, payload_hash=digest({"goal_hash": task.goal_hash}),
        timestamp=utcnow(), metadata={"active": True},
    ))
    # A task gets its own registered-authority baseline so refresh monitoring is
    # meaningful even when SessionStart happened before the typed task began.
    try:
        from gauntlet_monitor import snapshot as authority_snapshot
        authority_snapshot(root, task_id=task.task_id)
    except Exception:
        # Failure to snapshot cannot be silently converted into CLEARED later:
        # gauntlet.refresh will return UNKNOWN when no authority.snapshot exists.
        pass
    return task


def add_obligation(root: Path, task_id: str, kind: ObligationKind, claim: str, *, load_bearing: bool = True, metadata: dict | None = None) -> Obligation:
    store = RuntimeStore(root)
    obligation = Obligation(
        obligation_id=new_id("obl"),
        kind=kind,
        claim=claim,
        load_bearing=load_bearing,
        required_module=MODULE_FOR_KIND[kind],
        metadata=metadata or {},
    )
    # Read-modify-write under an advisory lock: concurrent hook processes otherwise
    # each append to a stale copy and all but the last obligation is lost.
    with store.lock(f"task-{task_id}"):
        raw = store.read_task(task_id)
        if raw is None:
            raise KeyError(f"unknown task {task_id}")
        raw.setdefault("obligations", []).append(json.loads(json.dumps(obligation, default=lambda o: getattr(o, "value", o.__dict__))))
        store.write_task(raw)
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type="obligation.created", component="soul",
        task_id=task_id, payload_hash=digest(obligation), timestamp=utcnow(),
        metadata={"obligation_id": obligation.obligation_id, "kind": kind.value, "required_module": obligation.required_module, "load_bearing": load_bearing},
    ))
    return obligation


def release_gate(root: Path, task_id: str) -> tuple[Verdict, dict]:
    store = RuntimeStore(root)
    task = store.read_task(task_id)
    if task is None:
        return Verdict.UNKNOWN, {"reason": "task-not-found"}
    details = []
    overall = Verdict.CLEARED
    for obligation in task.get("obligations", []):
        if not obligation.get("load_bearing", True):
            continue
        receipts = store.receipts_for(obligation["obligation_id"])
        # An obligation with no explicit required_module still has one implied by its
        # kind; falling back to "accept any module" would let an unrelated module
        # clear it.
        expected = obligation.get("required_module") or _module_for(obligation)
        receipts = [
            r for r in receipts
            if r.get("module") == expected and r.get("task_id") == task_id
        ]
        if not receipts:
            details.append({"obligation_id": obligation["obligation_id"], "verdict": Verdict.UNKNOWN.value, "reason": "missing-receipt"})
            overall = _worse(overall, Verdict.UNKNOWN)
            continue
        # Each module owns the aggregate current state of its obligation. Historical
        # receipts remain auditable, but the most recently stored valid receipt is
        # authoritative for release; an old green result cannot mask a newer issue.
        current = receipts[-1]
        try:
            verdict = Verdict(current.get("verdict", Verdict.UNKNOWN.value))
        except ValueError:
            verdict = Verdict.UNKNOWN
        details.append({
            "obligation_id": obligation["obligation_id"],
            "verdict": verdict.value,
            "receipt_id": current.get("receipt_id"),
            "historical_receipt_ids": [r.get("receipt_id") for r in receipts[:-1]],
        })
        overall = _worse(overall, verdict)
    return overall, {"task_id": task_id, "obligations": details}



def release_task(root: Path, task_id: str) -> tuple[Verdict, dict]:
    verdict, detail = release_gate(root, task_id)
    if verdict != Verdict.CLEARED:
        return verdict, detail
    store = RuntimeStore(root)
    task = store.read_task(task_id)
    if task is None:
        return Verdict.UNKNOWN, {"reason": "task-not-found", "task_id": task_id}
    task["active"] = False
    task["released"] = True
    store.write_task(task)
    active = store.base / "active_task"
    if active.exists() and active.read_text(encoding="utf-8").strip() == task_id:
        active.unlink()
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type="release.completed", component="soul",
        task_id=task_id, payload_hash=digest(detail), timestamp=utcnow(),
        metadata={"verdict": verdict.value},
    ))
    return verdict, detail

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--goal", required=True)
    a = sub.add_parser("add")
    a.add_argument("task_id")
    a.add_argument("kind", choices=[k.value for k in ObligationKind])
    a.add_argument("--claim", required=True)
    g = sub.add_parser("gate")
    g.add_argument("task_id")
    r = sub.add_parser("release")
    r.add_argument("task_id")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "start":
        task = start_task(root, args.goal)
        print(json.dumps({"task_id": task.task_id, "goal_hash": task.goal_hash}, indent=2))
        return 0
    if args.cmd == "add":
        obligation = add_obligation(root, args.task_id, ObligationKind(args.kind), args.claim)
        print(json.dumps({"obligation_id": obligation.obligation_id, "module": obligation.required_module}, indent=2))
        return 0
    if args.cmd == "release":
        verdict, detail = release_task(root, args.task_id)
    else:
        verdict, detail = release_gate(root, args.task_id)
    print(json.dumps({"verdict": verdict.value, **detail}, indent=2))
    return 0 if verdict == Verdict.CLEARED else 2


if __name__ == "__main__":
    raise SystemExit(main())
