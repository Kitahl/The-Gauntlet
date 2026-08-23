"""Evidence-ledger gate with backward-compatible content-addressed receipt support.

Integrity checks prove that the referenced bytes/receipt have not changed. They do
not prove that the evidence semantically entails the claim; that remains a separate
claim-native verification obligation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from egrt_types import digest
from gauntlet_config import load_config, project_root

REQUIRES_EVIDENCE = {"verified", "done", "supported", "measured", "proven"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_integrity(path: Path) -> str | None:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"invalid runtime receipt {path}: {exc}"
    expected = body.pop("content_hash", None)
    if not expected:
        return f"runtime receipt missing content_hash: {path}"
    actual = digest(body)
    if actual != expected:
        return f"runtime receipt content hash mismatch: {path}"
    return None


def _resolve_evidence(root: Path, item: Any, *, accept_runtime_receipts: bool, receipt_dir: Path) -> tuple[Path | None, str | None, str | None]:
    """Return (path, expected_sha256, error)."""
    if isinstance(item, str):
        p = Path(item)
        if not p.is_absolute():
            p = root / p
        return p, None, None
    if not isinstance(item, dict):
        return None, None, "evidence item must be a path string or object"
    if item.get("receipt_id"):
        if not accept_runtime_receipts:
            return None, None, "runtime receipt references are disabled"
        p = receipt_dir / f"{item['receipt_id']}.json"
        return p, item.get("sha256"), None
    if item.get("path"):
        p = Path(str(item["path"]))
        if not p.is_absolute():
            p = root / p
        return p, item.get("sha256"), None
    return None, None, "evidence object requires path or receipt_id"


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

    accept_runtime = bool(ledger_cfg.get("accept_runtime_receipts", True))
    configured_state = Path(str(cfg.get("state_dir") or ".egrt/state"))
    if not configured_state.is_absolute():
        configured_state = root / configured_state
    receipt_dir = configured_state / "runtime" / "receipts"
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
        if evidence and not isinstance(evidence, list):
            errors.append(f"{cid}: evidence must be a list")
            continue
        for item in evidence:
            p, expected_sha, err = _resolve_evidence(root, item, accept_runtime_receipts=accept_runtime, receipt_dir=receipt_dir)
            if err:
                errors.append(f"{cid}: {err}")
                continue
            assert p is not None
            if not p.exists():
                errors.append(f"{cid}: missing evidence path {p}")
                continue
            if expected_sha and _sha256(p) != expected_sha:
                errors.append(f"{cid}: evidence SHA-256 mismatch for {p}")
            if accept_runtime and p.parent.name == "receipts" and p.suffix == ".json":
                integrity_error = _receipt_integrity(p)
                if integrity_error:
                    errors.append(f"{cid}: {integrity_error}")
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
