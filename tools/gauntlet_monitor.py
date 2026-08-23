"""Config-driven stale-authority monitor with typed runtime events."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import RuntimeEvent, digest
from gauntlet_config import load_config, project_root, state_dir
from private_io import write_private_text


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=5, shell=False)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def build_state(root: Path, governing: list[str]) -> dict:
    return {"head": git_head(root), "files": {name: file_hash(root / name) for name in governing}}


def diff_state(before: dict, after: dict, governing: list[str]) -> list[str]:
    out: list[str] = []
    if before.get("head") and after.get("head") and before["head"] != after["head"]:
        out.append(f"git HEAD changed {before['head'][:9]} -> {after['head'][:9]}")
    for name in governing:
        a = before.get("files", {}).get(name)
        b = after.get("files", {}).get(name)
        if a != b:
            if a is None and b is not None:
                out.append(f"{name}: created")
            elif a is not None and b is None:
                out.append(f"{name}: deleted")
            elif a is not None or b is not None:
                out.append(f"{name}: changed")
    return out


def _active_task(store: RuntimeStore) -> str | None:
    path = store.base / "active_task"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _emit(root: Path, event_type: str, payload: dict, metadata: dict, *, task_id: str | None = None) -> None:
    store = RuntimeStore(root)
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type=event_type, component="gauntlet",
        task_id=task_id if task_id is not None else _active_task(store),
        payload_hash=digest(payload), timestamp=utcnow(), metadata=metadata,
    ))


def snapshot(root: Path | None = None, *, task_id: str | None = None) -> int:
    root = root or project_root()
    cfg = load_config(root)
    governing = [str(x) for x in cfg.get("governing_files", [])]
    state = build_state(root, governing)
    path = state_dir(root, cfg) / "gauntlet_monitor.json"
    write_private_text(path, json.dumps(state, indent=2) + "\n")
    _emit(root, "authority.snapshot", state, {
        "governing_count": len(governing),
        "registered_authority_set_hash": digest(sorted(governing)),
    }, task_id=task_id)
    return 0


def check(root: Path | None = None, *, emit_event: bool = True) -> tuple[int, list[str]]:
    root = root or project_root()
    cfg = load_config(root)
    governing = [str(x) for x in cfg.get("governing_files", [])]
    path = state_dir(root, cfg) / "gauntlet_monitor.json"
    if not path.exists():
        return 0, []
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, []
    after = build_state(root, governing)
    drift = diff_state(before, after, governing)
    if drift and emit_event:
        _emit(root, "authority.changed", {"before": before, "after": after}, {
            "drift_count": len(drift),
            "drift_hash": digest(drift),
        })
    return (1 if drift else 0), drift


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if (argv or ["check"])[0] == "snapshot":
        return snapshot()
    code, drift = check()
    if drift:
        print(json.dumps({"systemMessage": "PROCESS ASSURANCE / refresh: governing state changed: " + "; ".join(drift) + ". Re-read the current source before relying on cached state."}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
