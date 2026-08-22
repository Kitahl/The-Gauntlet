"""Optional generic evidence-ledger gate.

Enabled only when .gauntlet.json sets ledger.enabled=true and ledger.path.
The expected JSON shape is intentionally small and project-agnostic:
{"claims":[{"id":"...","status":"verified|done|...","evidence":["path", ...]}]}.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from gauntlet_config import load_config, project_root

REQUIRES_EVIDENCE = {"verified", "done", "supported", "measured", "proven"}


def check(root: Path | None = None) -> list[str]:
    root = root or project_root()
    cfg = load_config(root)
    ledger_cfg = cfg.get("ledger", {})
    if not ledger_cfg.get("enabled"):
        return []
    raw_path = ledger_cfg.get("path")
    if not raw_path:
        return ["ledger.enabled=true but ledger.path is not configured"]
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = root / path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"configured ledger missing: {path}"]
    except json.JSONDecodeError as exc:
        return [f"configured ledger is invalid JSON: {exc}"]
    claims = data.get("claims")
    if not isinstance(claims, list):
        return ["ledger must contain a claims array"]
    errors: list[str] = []
    seen: set[str] = set()
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{i}] must be an object")
            continue
        cid = str(claim.get("id") or "").strip()
        if not cid:
            errors.append(f"claims[{i}] missing id")
        elif cid in seen:
            errors.append(f"duplicate claim id: {cid}")
        seen.add(cid)
        status = str(claim.get("status") or "unknown").lower()
        evidence = claim.get("evidence") or []
        if status in REQUIRES_EVIDENCE and not evidence:
            errors.append(f"{cid or f'claims[{i}]'}: status={status} requires evidence")
        for item in evidence if isinstance(evidence, list) else []:
            p = Path(str(item))
            if not p.is_absolute():
                p = root / p
            if not p.exists():
                errors.append(f"{cid}: missing evidence path {item}")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("EVIDENCE LEDGER CHECK FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
