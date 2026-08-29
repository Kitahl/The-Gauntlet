"""Read-only Gauntlet module adapter for the isolated runtime plugin."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Sequence

ADAPTER_SCHEMA = "gauntlet.adapter.v1"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


class AdapterError(RuntimeError):
    """Typed, fail-closed adapter error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _configure_imports(root: Path) -> None:
    tools_root = root / "tools"
    required = (
        tools_root / "__init__.py",
        tools_root / "egrt_store.py",
        tools_root / "soul_runtime.py",
    )
    if not all(path.is_file() for path in required):
        raise AdapterError(
            "GAUNTLET_REPOSITORY_INVALID",
            "Gauntlet authority files are missing from the requested repository root",
        )

    vendor_root = (root / "vendor" / "hermes-agent").resolve(strict=False)
    retained: list[str] = []
    seen: set[str] = set()
    for entry in sys.path:
        if not entry:
            continue
        resolved = Path(entry).resolve(strict=False)
        if _is_within(resolved, vendor_root):
            continue
        rendered = str(resolved)
        if rendered in seen:
            continue
        seen.add(rendered)
        retained.append(rendered)

    ordered = [str(root), str(tools_root)]
    sys.path[:] = ordered + [entry for entry in retained if entry not in ordered]
    os.environ["PYTHONPATH"] = str(root)
    os.chdir(root)


def _task_id() -> str:
    task_id = os.environ.get("GAUNTLET_TASK_ID", "").strip()
    if not task_id:
        raise AdapterError(
            "TASK_ID_MISSING",
            "GAUNTLET_TASK_ID is required; task identity is never inferred from text",
        )
    if not TASK_ID_PATTERN.fullmatch(task_id) or ".." in task_id:
        raise AdapterError(
            "TASK_ID_INVALID",
            "GAUNTLET_TASK_ID contains unsupported characters",
        )
    return task_id


def _base_document(action: str, task_id: str) -> dict[str, Any]:
    return {
        "schema": ADAPTER_SCHEMA,
        "action": action,
        "task_id": task_id,
        "canonical_source": "egrt.runtime.v1",
        "read_only": True,
        "mutation_performed": False,
        "authority": {
            "receipt_creation": False,
            "verdict_change": False,
            "obligation_clearance": False,
            "task_release": False,
        },
    }


def _release_projection(root: Path, task_id: str) -> dict[str, Any]:
    from soul_runtime import release_gate

    verdict, detail = release_gate(root, task_id)
    return {
        "verdict": verdict.value,
        "release_eligible": verdict.value == "CLEARED",
        "detail": detail,
    }


def _task_projection(task: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    states = {
        row.get("obligation_id"): row
        for row in release.get("detail", {}).get("obligations", [])
        if isinstance(row, dict) and row.get("obligation_id")
    }
    obligations: list[dict[str, Any]] = []
    for row in task.get("obligations", []):
        if not isinstance(row, dict):
            continue
        obligation_id = str(row.get("obligation_id") or "")
        projected = {
            "obligation_id": obligation_id,
            "kind": row.get("kind"),
            "claim": row.get("claim"),
            "load_bearing": bool(row.get("load_bearing", True)),
            "required_module": row.get("required_module"),
        }
        gate_state = states.get(obligation_id)
        if gate_state is not None:
            projected["release_gate"] = gate_state
        obligations.append(projected)

    return {
        "task_id": task.get("task_id"),
        "goal_hash": task.get("goal_hash"),
        "active": bool(task.get("active", False)),
        "released": bool(task.get("released", False)),
        "schema": task.get("schema"),
        "content_hash": task.get("content_hash"),
        "obligations": obligations,
    }


def _read_task(root: Path, task_id: str) -> dict[str, Any]:
    from egrt_store import RuntimeStore

    task = RuntimeStore(root).read_task(task_id, require_integrity=True)
    if task is None:
        raise AdapterError(
            "TASK_NOT_FOUND",
            f"no integrity-valid canonical task exists for {task_id}",
        )
    return task


def _execute(root: Path, action: str, task_id: str) -> dict[str, Any]:
    task = _read_task(root, task_id)
    release = _release_projection(root, task_id)
    document = _base_document(action, task_id)
    document["status"] = "OK"

    if action == "task-status":
        document["task"] = _task_projection(task, release)
        document["release"] = release
    elif action == "release-status":
        document["task_released"] = bool(task.get("released", False))
        document["release"] = release
    else:
        raise AdapterError(
            "UNSUPPORTED_ACTION",
            f"unsupported read-only adapter action: {action}",
        )
    return document


def _error_document(action: str, task_id: str, exc: AdapterError) -> dict[str, Any]:
    document = _base_document(action, task_id)
    document.update(
        {
            "status": "ERROR",
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        }
    )
    return document


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python gauntlet_host/module_cli.py",
        description="Read canonical Gauntlet task or release status without mutation.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("action", choices=("task-status", "release-status"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve(strict=False)
    task_id = os.environ.get("GAUNTLET_TASK_ID", "").strip() or "unknown"
    try:
        _configure_imports(root)
        task_id = _task_id()
        document = _execute(root, args.action, task_id)
        exit_code = 0
    except AdapterError as exc:
        document = _error_document(args.action, task_id, exc)
        exit_code = 2
    except Exception as exc:
        document = _error_document(
            args.action,
            task_id,
            AdapterError(
                "ADAPTER_INTERNAL_ERROR",
                f"unexpected read-only adapter failure: {type(exc).__name__}",
            ),
        )
        exit_code = 2

    print(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
