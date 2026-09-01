"""Status/event CLI for the typed BASTION-01 evidence-control runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import RuntimeEvent, digest
from gauntlet_runtime import coverage_registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coverage")
    events = sub.add_parser("events")
    events.add_argument("--task")
    task = sub.add_parser("task")
    task.add_argument("task_id")
    emit = sub.add_parser("emit")
    emit.add_argument("event_type")
    emit.add_argument("--component", required=True)
    emit.add_argument("--task")
    emit.add_argument("--payload-hash", required=True)
    emit.add_argument("--metadata-json", default="{}")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "coverage":
        print(json.dumps({"gauntlet_operations": coverage_registry()}, indent=2))
        return 0
    store = RuntimeStore(root)
    if args.cmd == "events":
        print(json.dumps(store.iter_events(args.task), indent=2))
        return 0
    if args.cmd == "emit":
        try:
            metadata = json.loads(args.metadata_json)
        except json.JSONDecodeError as exc:
            p.error(f"--metadata-json must be valid JSON: {exc}")
        if not isinstance(metadata, dict):
            p.error("--metadata-json must be a JSON object")
        store.append_event(RuntimeEvent(
            event_id=new_id("evt"), event_type=args.event_type, component=args.component,
            task_id=args.task, payload_hash=args.payload_hash, timestamp=utcnow(), metadata=metadata,
        ))
        print(json.dumps({"status": "RECORDED", "event_type": args.event_type, "metadata_hash": digest(metadata)}, indent=2))
        return 0
    row = store.read_task(args.task_id)
    if row is None:
        print(json.dumps({"error": "task-not-found", "task_id": args.task_id}))
        return 2
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
