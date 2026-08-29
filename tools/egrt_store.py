"""Private, config-aware state and content-addressed runtime storage.

Mutable task/component state is owner-private. Receipts, challenges, resolutions, and
generic events are integrity-protected with canonical SHA-256 content hashes. Integrity
is not semantic truth: claim-native verification remains the responsibility of the
owning module.

Task-scoped receipt and challenge mutations also advance a content-protected evidence
version under one cooperative cross-process lock. Soul uses that token together with
the task content hash for an atomic compare-and-swap release commit.
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
from private_io import ensure_private_dir, file_lock, write_private_text


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


def _receipt_order(row: dict[str, Any]) -> tuple[str, int, int]:
    stamp = str(
        row.get("stored_at")
        or row.get("finished_at")
        or row.get("started_at")
        or ""
    )
    raw = row.get("seq")
    if isinstance(raw, int):
        return (stamp, 1, raw)
    return (stamp, 0, 0)


def verify_content_hash(body: dict[str, Any]) -> bool:
    expected = body.get("content_hash")
    return bool(expected) and digest(_integrity_body(body)) == expected


_ALLOWED_CHALLENGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "PROPOSED": frozenset(
        {
            "SELECTED",
            "UNRESOLVED",
            "UNAVAILABLE",
            "RESOLVED",
            "DISMISSED_NOT_APPLICABLE",
        }
    ),
    "SELECTED": frozenset(
        {
            "RUNNING",
            "UNRESOLVED",
            "UNAVAILABLE",
            "RESOLVED",
            "DISMISSED_NOT_APPLICABLE",
        }
    ),
    "RUNNING": frozenset({"UNRESOLVED", "UNAVAILABLE", "RESOLVED"}),
    "UNRESOLVED": frozenset(
        {
            "SELECTED",
            "RUNNING",
            "UNAVAILABLE",
            "RESOLVED",
            "DISMISSED_NOT_APPLICABLE",
        }
    ),
    "UNAVAILABLE": frozenset(
        {
            "SELECTED",
            "RUNNING",
            "UNRESOLVED",
            "RESOLVED",
            "DISMISSED_NOT_APPLICABLE",
        }
    ),
    "RESOLVED": frozenset(),
    "DISMISSED_NOT_APPLICABLE": frozenset(),
}


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
        self.challenges = ensure_private_dir(self.base / "challenges")
        self.challenge_resolutions = ensure_private_dir(
            self.base / "challenge_resolutions"
        )
        self.councils = ensure_private_dir(self.base / "councils")
        self.meditate = ensure_private_dir(self.base / "meditate")
        self.evidence_versions = ensure_private_dir(self.base / "evidence_versions")
        self.locks = ensure_private_dir(self.base / "locks")

    def _write(self, path: Path, value: Any) -> Path:
        return write_private_text(
            path,
            json.dumps(_serialize(value), indent=2, sort_keys=True) + "\n",
        )

    @staticmethod
    def _read(path: Path, *, require_integrity: bool = True) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(body, dict):
            return None
        if require_integrity and not verify_content_hash(body):
            return None
        return body

    def lock(self, name: str):
        """Advisory lock scoped to this store, for read-modify-write cycles."""
        return file_lock(self.locks / f"{name}.lock")

    def evidence_lock(self, task_id: str):
        """Cooperative lock for task-scoped receipt/challenge mutations."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be non-empty")
        return self.lock(f"evidence-{task_id}")

    def _evidence_version_path(self, task_id: str) -> Path:
        return self.evidence_versions / f"{task_id}.json"

    def _read_evidence_version_unlocked(self, task_id: str) -> int:
        path = self._evidence_version_path(task_id)
        if not path.exists():
            return 0
        body = self._read(path)
        if body is None or body.get("task_id") != task_id:
            raise RuntimeError(f"evidence version is missing or corrupt for {task_id}")
        version = body.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise RuntimeError(f"invalid evidence version for {task_id}")
        return version

    def evidence_version(self, task_id: str, *, assume_locked: bool = False) -> int:
        """Return the task evidence version.

        ``assume_locked`` is for callers already holding ``evidence_lock(task_id)``;
        taking the same advisory lock recursively would deadlock on some platforms.
        """
        if assume_locked:
            return self._read_evidence_version_unlocked(task_id)
        with self.evidence_lock(task_id):
            return self._read_evidence_version_unlocked(task_id)

    def _bump_evidence_version_unlocked(
        self,
        task_id: str,
        *,
        reason: str,
        payload_hash: str,
    ) -> int:
        current = self._read_evidence_version_unlocked(task_id)
        body: dict[str, Any] = {
            "task_id": task_id,
            "version": current + 1,
            "reason": reason,
            "payload_hash": payload_hash,
            "updated_at": utcnow(),
        }
        body["content_hash"] = digest(body)
        self._write(self._evidence_version_path(task_id), body)
        return current + 1

    def _ensure_task_accepts_evidence(self, task_id: str) -> None:
        task = self.read_task(task_id)
        if task is not None and task.get("released"):
            raise ValueError(f"task {task_id} is released; new evidence is not accepted")

    def next_seq(self) -> int:
        """Monotonic per-store sequence number, used to break timestamp ties."""
        with self.lock("seq"):
            path = self.base / "seq_counter.json"
            current = 0
            if path.exists():
                try:
                    current = int(
                        json.loads(path.read_text(encoding="utf-8")).get("seq", 0)
                    )
                except (OSError, ValueError, AttributeError, json.JSONDecodeError):
                    current = 0
            nxt = current + 1
            write_private_text(path, json.dumps({"seq": nxt}) + "\n")
            return nxt

    def _task_body(self, task: TaskState | dict[str, Any]) -> dict[str, Any]:
        body = _serialize(task) if is_dataclass(task) else dict(task)
        body.pop("content_hash", None)
        body["content_hash"] = digest(body)
        return body

    def write_task(self, task: TaskState | dict[str, Any]) -> Path:
        body = self._task_body(task)
        task_id = str(body.get("task_id"))
        return self._write(self.tasks / f"{task_id}.json", body)

    def read_task(
        self,
        task_id: str,
        *,
        require_integrity: bool = True,
    ) -> dict[str, Any] | None:
        return self._read(
            self.tasks / f"{task_id}.json",
            require_integrity=require_integrity,
        )

    def task_for_obligation(self, obligation_id: str) -> str | None:
        for path in self.tasks.glob("*.json"):
            task = self._read(path)
            if task is None:
                continue
            if any(
                row.get("obligation_id") == obligation_id
                for row in task.get("obligations", [])
            ):
                return str(task.get("task_id") or path.stem)
        return None

    def _write_receipt_unlocked(self, receipt: Receipt, task_id: str | None) -> Path:
        path = self.receipts / f"{receipt.receipt_id}.json"
        if path.exists():
            raise ValueError(f"duplicate receipt_id: {receipt.receipt_id}")
        body = json.loads(canonical_json(receipt))
        body["task_id"] = task_id
        body["stored_at"] = utcnow()
        body["seq"] = self.next_seq()
        body["content_hash"] = digest(body)
        path = self._write(path, body)
        self.append_event(
            RuntimeEvent(
                event_id=new_id("evt"),
                event_type="receipt.written",
                component=receipt.module,
                task_id=task_id,
                payload_hash=body["content_hash"],
                timestamp=utcnow(),
                metadata={
                    "receipt_id": receipt.receipt_id,
                    "obligation_id": receipt.obligation_id,
                    "verdict": receipt.verdict.value,
                    "action": receipt.action,
                },
            )
        )
        self.append_event(
            RuntimeEvent(
                event_id=new_id("evt"),
                event_type="obligation.state",
                component=receipt.module,
                task_id=task_id,
                payload_hash=body["content_hash"],
                timestamp=utcnow(),
                metadata={
                    "obligation_id": receipt.obligation_id,
                    "state": receipt.verdict.value,
                },
            )
        )
        for evidence in body.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            metadata = (
                evidence.get("metadata")
                if isinstance(evidence.get("metadata"), dict)
                else {}
            )
            self.append_event(
                RuntimeEvent(
                    event_id=new_id("evt"),
                    event_type="evidence.attached",
                    component=receipt.module,
                    task_id=task_id,
                    payload_hash=digest(evidence),
                    timestamp=utcnow(),
                    metadata={
                        "obligation_id": receipt.obligation_id,
                        "producer": receipt.module,
                        "verifier": evidence.get("verifier") or receipt.verifier,
                        "producer_provenance": metadata.get(
                            "producer_provenance"
                        ),
                        "verifier_provenance": evidence.get("provenance_group")
                        or metadata.get("verifier_provenance"),
                        "evidence_class": evidence.get("evidence_class"),
                    },
                )
            )
        if task_id is not None:
            self._bump_evidence_version_unlocked(
                task_id,
                reason="receipt.written",
                payload_hash=str(body["content_hash"]),
            )
        return path

    def write_receipt(self, receipt: Receipt) -> Path:
        task_id = receipt.task_id or self.task_for_obligation(receipt.obligation_id)
        with self.lock(f"receipt-{receipt.receipt_id}"):
            if task_id is None:
                return self._write_receipt_unlocked(receipt, None)
            with self.evidence_lock(task_id):
                self._ensure_task_accepts_evidence(task_id)
                return self._write_receipt_unlocked(receipt, task_id)

    def read_receipt(
        self,
        receipt_id: str,
        *,
        require_integrity: bool = True,
    ) -> dict[str, Any] | None:
        return self._read(
            self.receipts / f"{receipt_id}.json",
            require_integrity=require_integrity,
        )

    def receipts_for(
        self,
        obligation_id: str,
        *,
        valid_only: bool = True,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in self.receipts.glob("*.json"):
            row = self._read(path, require_integrity=valid_only)
            if row is None or row.get("obligation_id") != obligation_id:
                continue
            out.append(row)
        out.sort(key=_receipt_order)
        return out

    def write_challenge(self, challenge: Any) -> Path:
        """Persist a new neutral challenge; duplicate identifiers are rejected."""
        body = _serialize(challenge) if is_dataclass(challenge) else dict(challenge)
        challenge_id = str(body.get("challenge_id") or "")
        task_id = str(body.get("task_id") or "")
        if not challenge_id or not task_id:
            raise ValueError("challenge_id and task_id are required")
        path = self.challenges / f"{challenge_id}.json"
        with self.evidence_lock(task_id):
            self._ensure_task_accepts_evidence(task_id)
            with self.lock(f"challenge-{challenge_id}"):
                if path.exists():
                    raise ValueError(f"duplicate challenge_id: {challenge_id}")
                body["state"] = "PROPOSED"
                body["stored_at"] = utcnow()
                body["seq"] = self.next_seq()
                body["content_hash"] = digest(body)
                written = self._write(path, body)
            self._append_challenge_event(
                "challenge.proposed",
                body,
                metadata={
                    "origin": body.get("origin"),
                    "kind": body.get("kind"),
                    "load_bearing": body.get("load_bearing"),
                    "candidate_hash": body.get("candidate_hash"),
                    "scope_hash": body.get("scope_hash"),
                    "proposer_provenance": body.get("proposer_provenance"),
                },
            )
            self._bump_evidence_version_unlocked(
                task_id,
                reason="challenge.proposed",
                payload_hash=str(body["content_hash"]),
            )
        return written

    def read_challenge(
        self,
        challenge_id: str,
        *,
        require_integrity: bool = True,
    ) -> dict[str, Any] | None:
        return self._read(
            self.challenges / f"{challenge_id}.json",
            require_integrity=require_integrity,
        )

    def challenges_for(
        self,
        task_id: str,
        obligation_id: str | None = None,
        *,
        valid_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.challenges.glob("*.json"):
            row = self._read(path, require_integrity=valid_only)
            if row is None or row.get("task_id") != task_id:
                continue
            if obligation_id is not None and row.get("obligation_id") != obligation_id:
                continue
            rows.append(row)
        rows.sort(key=_receipt_order)
        return rows

    def _update_challenge_state_under_evidence_lock(
        self,
        challenge_id: str,
        state: str,
        *,
        selected_plan: dict[str, Any] | None,
        reason: str | None,
        component: str,
        emit_event: bool,
        bump_version: bool,
    ) -> tuple[Path, dict[str, Any]]:
        path = self.challenges / f"{challenge_id}.json"
        with self.lock(f"challenge-{challenge_id}"):
            body = self._read(path)
            if body is None:
                raise ValueError(f"challenge not found or corrupt: {challenge_id}")
            current = str(body.get("state") or "PROPOSED")
            if (
                state != current
                and state
                not in _ALLOWED_CHALLENGE_TRANSITIONS.get(current, frozenset())
            ):
                raise ValueError(f"invalid challenge transition: {current} -> {state}")
            body.pop("content_hash", None)
            body["state"] = state
            if selected_plan is not None:
                body["selected_plan"] = selected_plan
                body["selected_plan_id"] = selected_plan.get("plan_id")
            if reason is not None:
                body["state_reason"] = reason
            body["updated_at"] = utcnow()
            body["seq"] = self.next_seq()
            body["content_hash"] = digest(body)
            written = self._write(path, body)
        event_type = {
            "SELECTED": "challenge.selected",
            "RUNNING": "challenge.running",
            "RESOLVED": "challenge.resolved",
            "UNRESOLVED": "challenge.unresolved",
            "UNAVAILABLE": "challenge.unavailable",
            "DISMISSED_NOT_APPLICABLE": "challenge.dismissed",
        }.get(state)
        if event_type and emit_event:
            metadata: dict[str, Any] = {"state": state, "reason": reason}
            if selected_plan is not None:
                metadata.update(
                    {
                        "plan_id": selected_plan.get("plan_id"),
                        "verifier_module": selected_plan.get("verifier_module"),
                        "capability": selected_plan.get("required_capability"),
                    }
                )
            self._append_challenge_event(
                event_type,
                body,
                component=component,
                metadata=metadata,
            )
        task_id = str(body.get("task_id") or "")
        if bump_version:
            self._bump_evidence_version_unlocked(
                task_id,
                reason=event_type or f"challenge.{state.lower()}",
                payload_hash=str(body["content_hash"]),
            )
        return written, body

    def update_challenge_state(
        self,
        challenge_id: str,
        state: str,
        *,
        selected_plan: dict[str, Any] | None = None,
        reason: str | None = None,
        component: str = "challenge",
        emit_event: bool = True,
    ) -> Path:
        """Apply one validated lifecycle transition while retaining integrity metadata."""
        state = str(state).upper()
        if state not in _ALLOWED_CHALLENGE_TRANSITIONS:
            raise ValueError(f"invalid challenge state: {state}")
        initial = self.read_challenge(challenge_id)
        if initial is None:
            raise ValueError(f"challenge not found or corrupt: {challenge_id}")
        task_id = str(initial.get("task_id") or "")
        if not task_id:
            raise ValueError("challenge lacks task_id")
        with self.evidence_lock(task_id):
            self._ensure_task_accepts_evidence(task_id)
            written, _ = self._update_challenge_state_under_evidence_lock(
                challenge_id,
                state,
                selected_plan=selected_plan,
                reason=reason,
                component=component,
                emit_event=emit_event,
                bump_version=True,
            )
        return written

    def write_challenge_resolution(self, resolution: Any) -> Path:
        """Persist a resolution after validating binding and its claim-native receipt."""
        body = _serialize(resolution) if is_dataclass(resolution) else dict(resolution)
        resolution_id = str(body.get("resolution_id") or "")
        challenge_id = str(body.get("challenge_id") or "")
        if not resolution_id or not challenge_id:
            raise ValueError("resolution_id and challenge_id are required")
        if str(body.get("state")) not in {
            "RESOLVED",
            "UNRESOLVED",
            "UNAVAILABLE",
            "DISMISSED_NOT_APPLICABLE",
        }:
            raise ValueError(
                "resolution state must be terminal, unresolved, unavailable, or dismissed"
            )
        initial = self.read_challenge(challenge_id)
        if initial is None:
            raise ValueError(f"challenge not found or corrupt: {challenge_id}")
        task_id = str(initial.get("task_id") or "")
        if not task_id:
            raise ValueError("challenge lacks task_id")
        path = self.challenge_resolutions / f"{resolution_id}.json"
        with self.evidence_lock(task_id):
            self._ensure_task_accepts_evidence(task_id)
            with self.lock(f"challenge-resolution-{challenge_id}"):
                if path.exists():
                    raise ValueError(f"duplicate resolution_id: {resolution_id}")
                challenge = self.read_challenge(challenge_id)
                if challenge is None:
                    raise ValueError(f"challenge not found or corrupt: {challenge_id}")
                for key in ("candidate_hash", "scope_hash", "obligation_set_hash"):
                    if body.get(key) != challenge.get(key):
                        raise ValueError(f"resolution {key} binding mismatch")
                receipt_id = body.get("verifier_receipt_id")
                verifier_module = body.get("verifier_module")
                if receipt_id is not None:
                    receipt = self.read_receipt(str(receipt_id))
                    if receipt is None:
                        raise ValueError("linked verifier receipt is missing or corrupt")
                    if receipt.get("module") != verifier_module:
                        raise ValueError("linked verifier module mismatch")
                    if receipt.get("obligation_id") != challenge.get("obligation_id"):
                        raise ValueError("linked verifier receipt obligation mismatch")
                    if receipt.get("task_id") not in (None, challenge.get("task_id")):
                        raise ValueError("linked verifier receipt task mismatch")
                    receipt_hash = receipt.get("content_hash")
                    if (
                        body.get("evidence_hash") is not None
                        and body.get("evidence_hash") != receipt_hash
                    ):
                        raise ValueError(
                            "resolution evidence_hash must bind the linked receipt"
                        )
                    body["evidence_hash"] = receipt_hash
                elif body.get("state") == "RESOLVED":
                    raise ValueError(
                        "resolved challenge requires a claim-native verifier receipt"
                    )
                body["stored_at"] = utcnow()
                body["seq"] = self.next_seq()
                body["content_hash"] = digest(body)
                written = self._write(path, body)
                self._update_challenge_state_under_evidence_lock(
                    challenge_id,
                    str(body["state"]),
                    selected_plan=None,
                    reason=body.get("reason"),
                    component=str(body.get("resolver") or "challenge"),
                    emit_event=False,
                    bump_version=False,
                )
            event_type = {
                "RESOLVED": "challenge.resolved",
                "UNRESOLVED": "challenge.unresolved",
                "UNAVAILABLE": "challenge.unavailable",
                "DISMISSED_NOT_APPLICABLE": "challenge.dismissed",
            }[str(body["state"])]
            self._append_challenge_event(
                event_type,
                {**challenge, "content_hash": body["content_hash"]},
                component=str(body.get("resolver") or "challenge"),
                metadata={
                    "resolution_id": resolution_id,
                    "outcome": body.get("outcome"),
                    "linked_receipt_id": body.get("verifier_receipt_id"),
                    "evidence_hash": body.get("evidence_hash"),
                    "candidate_hash": body.get("candidate_hash"),
                    "scope_hash": body.get("scope_hash"),
                    "obligation_set_hash": body.get("obligation_set_hash"),
                },
            )
            self._bump_evidence_version_unlocked(
                task_id,
                reason=event_type,
                payload_hash=str(body["content_hash"]),
            )
        return written

    def read_challenge_resolution(
        self,
        resolution_id: str,
        *,
        require_integrity: bool = True,
    ) -> dict[str, Any] | None:
        return self._read(
            self.challenge_resolutions / f"{resolution_id}.json",
            require_integrity=require_integrity,
        )

    def latest_resolution(
        self,
        challenge_id: str,
        *,
        valid_only: bool = True,
    ) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        for path in self.challenge_resolutions.glob("*.json"):
            row = self._read(path, require_integrity=valid_only)
            if row is not None and row.get("challenge_id") == challenge_id:
                rows.append(row)
        if not rows:
            return None
        rows.sort(key=_receipt_order)
        return rows[-1]

    def _append_challenge_event(
        self,
        event_type: str,
        body: dict[str, Any],
        *,
        component: str = "challenge",
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        base_metadata = {
            "challenge_id": body.get("challenge_id"),
            "obligation_id": body.get("obligation_id"),
        }
        if metadata:
            base_metadata.update(
                {key: value for key, value in metadata.items() if value is not None}
            )
        return self.append_event(
            RuntimeEvent(
                event_id=new_id("evt"),
                event_type=event_type,
                component=component,
                task_id=body.get("task_id"),
                payload_hash=str(body.get("content_hash") or digest(body)),
                timestamp=utcnow(),
                metadata=base_metadata,
            )
        )

    def append_event(self, event: RuntimeEvent) -> Path:
        body = json.loads(canonical_json(event))
        body["content_hash"] = digest(body)
        return self._write(
            self.events
            / f"{event.timestamp.replace(':', '-')}-{event.event_id}.json",
            body,
        )

    def iter_events(
        self,
        task_id: str | None = None,
        *,
        valid_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.events.glob("*.json")):
            row = self._read(path, require_integrity=valid_only)
            if row is None:
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
