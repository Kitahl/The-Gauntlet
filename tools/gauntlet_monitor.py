"""Config-driven stale-authority monitor for the Process Assurance Framework."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from gauntlet_config import load_config, project_root, state_dir


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
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


def snapshot(root: Path | None = None) -> int:
    root = root or project_root()
    cfg = load_config(root)
    governing = [str(x) for x in cfg.get("governing_files", [])]
    path = state_dir(root, cfg) / "gauntlet_monitor.json"
    path.write_text(json.dumps(build_state(root, governing), indent=2) + "\n", encoding="utf-8")
    return 0


def check(root: Path | None = None) -> tuple[int, list[str]]:
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
    drift = diff_state(before, build_state(root, governing), governing)
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
