"""Private, config-aware state and content-addressed receipt storage.

Mutable task/component state is owner-private. Receipts and generic events are
integrity-protected with canonical SHA-256 content hashes. Integrity is not semantic
truth: claim-native verification remains the responsibility of the owning module.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from egrt_types import Receipt, RuntimeEvent, TaskState, canonical_json, digest
from gauntlet_config import load_config
from private_io import ensure_private_dir, write_private_text


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return json.loads(canonical_json(value))
    return value


def _integrity_body(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key != "content_hash"}


def verify_content_hash(body: dict[str, Any]) -> bool:
    expected = body.get("content_hash")
    return bool(expected) and digest(_integrity_body(body)) == expected


class RuntimeStore:
    def __init__(self, root: Path, state_dir: str | None = None) -> None:
        self.root = Path(root).resolve()
        if state_dir is None:
            cfg = load_config(self.root)
            state_dir = str(cfg.get("state_dir") or ".egrt/state")
        state_path = Path(state_dir)
        if not state_path.is_absolute():
            state_path = self.root / state_path
        self.base = ensure_private_dir(state_path / "runtime")
        self.tasks = ensure_private_dir(self.base / "tasks")
        self.receipts = ensure_private_dir(self.base / "receipts")
        self.events = ensure_private_dir(self.base / "events")
        self.councils = ensure_private_dir(self.base / "councils")
        self.meditate = ensure_private_dir(self.base / "meditate")

    def _write(self, path: Path, value: Any) -> Path:
        return write_private_text(path, json.dumps(_serialize(value), indent=2, sort_keys=True) + "\n")

    def write_task(self, task: TaskState) -> Path:
        return self._write(self.tasks / f"{task.task_id}.json", task)

    def read_task(self, task_id: str) -> dict[str, Any] | None:
        path = self.tasks / f"{task_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def task_for_obligation(self, obligation_id: str) -> str | None:
        for path in self.tasks.glob("*.json"):
            try:
                task = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if any(row.get("obligation_id") == obligation_id for row in task.get("obligations", [])):
                return str(task.get("task_id") or path.stem)
        return None

    def write_receipt(self, receipt: Receipt) -> Path:
        body = json.loads(canonical_json(receipt))
        body["stored_at"] = utcnow()
        body["content_hash"] = digest(body)
        path = self._write(self.receipts / f"{receipt.receipt_id}.json", body)
        task_id = receipt.task_id or self.task_for_obligation(receipt.obligation_id)
        # Structured events let Gauntlet monitor release/evidence state without
        # persisting raw prompts or raw tool outputs.
        self.append_event(RuntimeEvent(
            event_id=new_id("evt"), event_type="receipt.written", component=receipt.module,
            task_id=task_id, payload_hash=body["content_hash"], timestamp=utcnow(),
            metadata={"receipt_id": receipt.receipt_id, "obligation_id": receipt.obligation_id, "verdict": receipt.verdict.value, "action": receipt.action},
        ))
        self.append_event(RuntimeEvent(
            event_id=new_id("evt"), event_type="obligation.state", component=receipt.module,
            task_id=task_id, payload_hash=body["content_hash"], timestamp=utcnow(),
            metadata={"obligation_id": receipt.obligation_id, "state": receipt.verdict.value},
        ))
        for evidence in body.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
            self.append_event(RuntimeEvent(
                event_id=new_id("evt"), event_type="evidence.attached", component=receipt.module,
                task_id=task_id, payload_hash=digest(evidence), timestamp=utcnow(),
                metadata={
                    "obligation_id": receipt.obligation_id,
                    "producer": receipt.module,
                    "verifier": evidence.get("verifier") or receipt.verifier,
                    "producer_provenance": metadata.get("producer_provenance"),
                    "verifier_provenance": evidence.get("provenance_group") or metadata.get("verifier_provenance"),
                    "evidence_class": evidence.get("evidence_class"),
                },
            ))
        return path

    def read_receipt(self, receipt_id: str, *, require_integrity: bool = True) -> dict[str, Any] | None:
        path = self.receipts / f"{receipt_id}.json"
        if not path.exists():
            return None
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if require_integrity and not verify_content_hash(body):
            return None
        return body

    def receipts_for(self, obligation_id: str, *, valid_only: bool = True) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in self.receipts.glob("*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if row.get("obligation_id") != obligation_id:
                continue
            if valid_only and not verify_content_hash(row):
                continue
            out.append(row)
        out.sort(key=lambda r: str(r.get("stored_at") or r.get("finished_at") or r.get("started_at") or ""))
        return out

    def append_event(self, event: RuntimeEvent) -> Path:
        # Generic event state contains only structured metadata and hashes.
        body = json.loads(canonical_json(event))
        body["content_hash"] = digest(body)
        return self._write(self.events / f"{event.timestamp.replace(':', '-')}-{event.event_id}.json", body)

    def iter_events(self, task_id: str | None = None, *, valid_only: bool = True) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.events.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if valid_only and not verify_content_hash(row):
                continue
            if task_id is None or row.get("task_id") == task_id:
                rows.append(row)
        return rows

    def write_named_state(self, family: str, ident: str, value: Any) -> Path:
        directory = ensure_private_dir(self.base / family)
        return self._write(directory / f"{ident}.json", value)

    def read_named_state(self, family: str, ident: str) -> dict[str, Any] | None:
        path = self.base / family / f"{ident}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
