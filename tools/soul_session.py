"""Durable, authority-neutral session checkpoints for Soul.

This module is a host-loop control surface.  It preserves interruption state and
fails closed on task, route, evidence, or authority drift.  A session or checkpoint
never executes work, satisfies an obligation, validates domain evidence, or grants
release authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from egrt_store import RuntimeStore
from gauntlet_config import load_config, state_dir

SESSION_SCHEMA = "egrt.soul.session.v1"
CHECKPOINT_SCHEMA = "egrt.soul.session-checkpoint.v1"
RESUME_SCHEMA = "egrt.soul.session-resume.v1"
CONTROL_AUTHORITY = "CONTROL_ONLY"
MAX_METADATA_BYTES = 8192
MAX_CURSOR_BYTES = 4096
MAX_ARTIFACT_REFS = 32
DEFAULT_MAX_CHECKPOINTS = 128
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_REASON_RE = re.compile(r"^[A-Z0-9_]{1,64}$")
_RESERVED = {
    "active",
    "authority",
    "content_hash",
    "execution_authorized",
    "generation",
    "raw_goal",
    "raw_prompt",
    "raw_tool_output",
    "release",
    "release_authority",
    "released",
    "schema",
    "session_id",
    "status",
    "task_id",
}
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_TERMINAL = {"CLOSED", "CANCELLED", "INVALIDATED"}


class SoulSessionError(RuntimeError):
    """Base durable-session error."""


class SoulSessionConflict(SoulSessionError):
    """Generation CAS or immutable-state conflict."""


class SoulSessionIntegrityError(SoulSessionError):
    """Persisted content failed its seal or lineage check."""


class SoulSessionUnavailable(SoulSessionError):
    """A required task, route, evidence, or authority view is unavailable."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: item for key, item in value.items() if key != "content_hash"}
    payload["content_hash"] = _hash(payload)
    return payload


def _verify(value: Mapping[str, Any], schema: str) -> None:
    if value.get("schema") != schema:
        raise SoulSessionIntegrityError("unexpected session schema")
    observed = value.get("content_hash")
    if not isinstance(observed, str) or not _HASH_RE.fullmatch(observed):
        raise SoulSessionIntegrityError("missing content hash")
    payload = {key: item for key, item in value.items() if key != "content_hash"}
    if _hash(payload) != observed:
        raise SoulSessionIntegrityError("content hash mismatch")


def _root(root: Path) -> Path:
    root = Path(root)
    try:
        path = state_dir(root, load_config(root))
    except Exception:
        path = root / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dirs(root: Path) -> dict[str, Path]:
    base = _root(root)
    return {
        "sessions": base / "soul_sessions",
        "revisions": base / "soul_session_revisions",
        "checkpoints": base / "soul_session_checkpoints",
        "idempotency": base / "soul_session_idempotency",
    }


def _lock(name: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(name, threading.RLock())


def _write(path: Path, value: Mapping[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _bytes(value) + b"\n"
    if exclusive:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise SoulSessionConflict(f"immutable state exists: {path.name}") from exc
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SoulSessionIntegrityError(f"unreadable state: {path.name}") from exc
    if not isinstance(value, dict):
        raise SoulSessionIntegrityError("persisted state is not an object")
    return value


def _sanitize(value: Any, *, depth: int = 0, internal: bool = False) -> Any:
    if depth > 8:
        raise ValueError("metadata nesting exceeds 8 levels")
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str) and len(value) > 2048:
            raise ValueError("metadata string exceeds 2048 characters")
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("metadata contains non-finite float")
        return value
    if isinstance(value, Mapping):
        if len(value) > 128:
            raise ValueError("metadata object exceeds 128 keys")
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("metadata keys must be non-empty strings")
            lowered = key.casefold()
            if not internal and (lowered in _RESERVED or lowered.startswith("soul_")):
                raise ValueError(f"reserved control metadata key: {key}")
            result[key] = _sanitize(item, depth=depth + 1, internal=internal)
        return result
    if isinstance(value, (list, tuple)):
        if len(value) > 128:
            raise ValueError("metadata array exceeds 128 entries")
        return [_sanitize(item, depth=depth + 1, internal=internal) for item in value]
    raise TypeError(f"value is not JSON-safe: {type(value).__name__}")


def _bounded(
    value: Mapping[str, Any] | None,
    *,
    limit: int,
    label: str,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping or None")
    result = _sanitize(value)
    if not isinstance(result, dict):
        raise TypeError(f"{label} must be a mapping")
    if len(_bytes(result)) > limit:
        raise ValueError(f"{label} exceeds {limit} bytes")
    return result


def _task_binding(root: Path, requested_task_id: str) -> dict[str, Any]:
    if not requested_task_id:
        raise ValueError("task_id must be non-empty")
    try:
        from soul_vnext.automatic_control import resolve_current_task_id

        resolved, chain = resolve_current_task_id(root, requested_task_id)
    except Exception as exc:
        raise SoulSessionUnavailable("task lineage unavailable") from exc
    task = RuntimeStore(root).read_task(resolved)
    if not isinstance(task, Mapping):
        raise SoulSessionUnavailable("resolved task unavailable")
    task_hash = task.get("content_hash")
    if not isinstance(task_hash, str) or not _HASH_RE.fullmatch(task_hash):
        task_hash = _hash(task)
    obligations = sorted(
        str(row.get("obligation_id") or row.get("id"))
        for row in task.get("obligations", [])
        if isinstance(row, Mapping) and (row.get("obligation_id") or row.get("id"))
    )
    return {
        "requested_task_id": requested_task_id,
        "resolved_task_id": resolved,
        "supersession_chain": list(chain),
        "task_snapshot_hash": task_hash,
        "obligation_set_hash": _hash(obligations),
    }


def _route_binding(root: Path, task_id: str, route_plan_id: str | None) -> dict[str, Any]:
    if route_plan_id is None:
        return {
            "route_plan_id": None,
            "route_plan_hash": None,
            "selected_obligation_ids": [],
            "session_mode": "OBSERVATION_ONLY",
        }
    store = RuntimeStore(root)
    plan = None
    reader = getattr(store, "read_named_state", None)
    if callable(reader):
        try:
            plan = reader("soul_routes", route_plan_id)
        except TypeError:
            plan = None
    if plan is None:
        path = _root(root) / "soul_routes" / f"{route_plan_id}.json"
        if path.exists():
            plan = _read(path)
    if not isinstance(plan, Mapping):
        raise SoulSessionUnavailable("route plan unavailable")
    if plan.get("task_id") != task_id:
        raise SoulSessionUnavailable("route plan belongs to another task")
    if plan.get("execution_authorized") is True:
        raise SoulSessionIntegrityError("route plan cannot authorize execution")
    plan_hash = plan.get("content_hash") or plan.get("plan_hash")
    if not isinstance(plan_hash, str) or not _HASH_RE.fullmatch(plan_hash):
        plan_hash = _hash(plan)
    selected = plan.get("selected_obligations") or []
    if not isinstance(selected, (list, tuple)):
        raise SoulSessionIntegrityError("selected obligations malformed")
    return {
        "route_plan_id": route_plan_id,
        "route_plan_hash": plan_hash,
        "selected_obligation_ids": sorted(str(item) for item in selected),
        "session_mode": "ROUTED_CONTROL",
    }


def _snapshot(root: Path, task_id: str) -> tuple[str, str]:
    base = _root(root)
    evidence: list[dict[str, Any]] = []
    names = {
        "receipts",
        "challenges",
        "challenge_resolutions",
        "evidence",
        "release_seals",
    }
    for path in sorted(base.rglob("*.json")):
        if not any(part.casefold() in names for part in path.parts):
            continue
        raw = path.read_bytes()
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, Mapping):
            found = decoded.get("task_id")
            if found is not None and found != task_id:
                continue
        evidence.append(
            {
                "path": path.relative_to(base).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    authority: list[dict[str, Any]] = []
    for path in (Path(root) / ".gauntlet.json", base / "gauntlet_monitor.json"):
        authority.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                if path.exists()
                else None,
            }
        )
    return _hash(evidence), _hash(authority)


def _session_path(root: Path, session_id: str) -> Path:
    return _dirs(root)["sessions"] / f"{session_id}.json"


def _load_session(root: Path, session_id: str) -> dict[str, Any]:
    path = _session_path(root, session_id)
    if not path.exists():
        raise KeyError(f"unknown Soul session {session_id}")
    value = _read(path)
    _verify(value, SESSION_SCHEMA)
    return value


def _persist_session(root: Path, session: Mapping[str, Any]) -> None:
    revision = (
        _dirs(root)["revisions"]
        / str(session["session_id"])
        / f"{int(session['generation']):08d}.json"
    )
    _write(revision, session, exclusive=True)
    _write(_session_path(root, str(session["session_id"])), session)


def _generation(session: Mapping[str, Any], expected: int) -> None:
    if not isinstance(expected, int) or expected < 0:
        raise ValueError("expected_generation must be non-negative integer")
    if session.get("generation") != expected:
        raise SoulSessionConflict(
            f"stale generation: expected {expected}, observed {session.get('generation')}"
        )


def _binding_state(root: Path, session: Mapping[str, Any]) -> str:
    task = _task_binding(root, str(session["requested_task_id"]))
    for key in (
        "resolved_task_id",
        "supersession_chain",
        "task_snapshot_hash",
        "obligation_set_hash",
    ):
        if task[key] != session.get(key):
            return "STALE_TASK"
    route = _route_binding(root, str(session["resolved_task_id"]), session.get("route_plan_id"))
    if route["route_plan_hash"] != session.get("route_plan_hash"):
        return "STALE_ROUTE"
    if route["selected_obligation_ids"] != session.get("selected_obligation_ids"):
        return "STALE_ROUTE"
    evidence, authority = _snapshot(root, str(session["resolved_task_id"]))
    if authority != session.get("authority_snapshot_hash"):
        return "STALE_AUTHORITY"
    if evidence != session.get("evidence_snapshot_hash"):
        return "STALE_EVIDENCE"
    return "READY"


def _invalidate(root: Path, session: Mapping[str, Any], reason: str) -> dict[str, Any]:
    updated = dict(session)
    updated.update(
        {
            "status": "INVALIDATED",
            "generation": int(session["generation"]) + 1,
            "invalidated_reason_code": reason,
            "updated_at": _now(),
        }
    )
    sealed = _seal(updated)
    _persist_session(root, sealed)
    return sealed


def open_session(
    root: Path,
    task_id: str,
    *,
    route_plan_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    max_checkpoints: int = DEFAULT_MAX_CHECKPOINTS,
) -> dict[str, Any]:
    """Open an idempotent, content-bound control session."""
    if not isinstance(max_checkpoints, int) or not 1 <= max_checkpoints <= 4096:
        raise ValueError("max_checkpoints must be between 1 and 4096")
    safe_metadata = _bounded(metadata, limit=MAX_METADATA_BYTES, label="metadata")
    task = _task_binding(root, task_id)
    route = _route_binding(root, str(task["resolved_task_id"]), route_plan_id)
    evidence, authority = _snapshot(root, str(task["resolved_task_id"]))
    idempotency_hash = _hash(idempotency_key) if idempotency_key else None
    binding_hash = _hash(
        {
            "task": task,
            "route": route,
            "evidence": evidence,
            "authority": authority,
            "metadata": safe_metadata,
            "max_checkpoints": max_checkpoints,
        }
    )
    lock_name = idempotency_hash or str(task["resolved_task_id"])
    with _lock(f"open:{lock_name}"):
        if idempotency_hash:
            index_path = _dirs(root)["idempotency"] / f"{idempotency_hash}.json"
            if index_path.exists():
                index = _read(index_path)
                _verify(index, "egrt.soul.session-idempotency.v1")
                if index.get("binding_hash") != binding_hash:
                    raise SoulSessionConflict("idempotency key rebound to different input")
                return _load_session(root, str(index["session_id"]))
        session_id = f"soul-session-{uuid.uuid4().hex}"
        now = _now()
        session = _seal(
            {
                "schema": SESSION_SCHEMA,
                "session_id": session_id,
                **task,
                **route,
                "binding_hash": binding_hash,
                "evidence_snapshot_hash": evidence,
                "authority_snapshot_hash": authority,
                "status": "OPEN",
                "generation": 0,
                "checkpoint_count": 0,
                "max_checkpoints": max_checkpoints,
                "latest_checkpoint_id": None,
                "latest_checkpoint_hash": None,
                "idempotency_key_hash": idempotency_hash,
                "created_at": now,
                "updated_at": now,
                "metadata": safe_metadata,
                "authority": CONTROL_AUTHORITY,
                "execution_authorized": False,
                "domain_evidence_authority": False,
                "release_authority": False,
                "host_commit_required": True,
            }
        )
        _persist_session(root, session)
        if idempotency_hash:
            index = _seal(
                {
                    "schema": "egrt.soul.session-idempotency.v1",
                    "session_id": session_id,
                    "binding_hash": binding_hash,
                    "idempotency_key_hash": idempotency_hash,
                }
            )
            _write(index_path, index, exclusive=True)
        return session


def _artifacts(references: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if references is None:
        return []
    if len(references) > MAX_ARTIFACT_REFS:
        raise ValueError("too many artifact references")
    result: list[dict[str, Any]] = []
    for reference in references:
        artifact_id = reference.get("artifact_id")
        content_hash = reference.get("content_hash")
        kind = reference.get("kind", "ARTIFACT")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("artifact_id must be non-empty")
        if not isinstance(content_hash, str) or not _HASH_RE.fullmatch(content_hash):
            raise ValueError("artifact content_hash must be SHA-256")
        if not isinstance(kind, str) or not 1 <= len(kind) <= 64:
            raise ValueError("artifact kind must contain 1 to 64 characters")
        result.append(
            {
                "artifact_id_hash": _hash(artifact_id),
                "content_hash": content_hash,
                "kind": kind,
            }
        )
    return result


def checkpoint_session(
    root: Path,
    session_id: str,
    *,
    expected_generation: int,
    cursor: Mapping[str, Any] | None = None,
    observed_obligation_ids: Iterable[str] = (),
    artifact_refs: Sequence[Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
    pause: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Append a generation-guarded checkpoint; progress remains HOST_HINT_ONLY."""
    safe_cursor = _bounded(cursor, limit=MAX_CURSOR_BYTES, label="cursor")
    safe_metadata = _bounded(metadata, limit=MAX_METADATA_BYTES, label="metadata")
    artifacts = _artifacts(artifact_refs)
    observed = sorted({str(item) for item in observed_obligation_ids})
    with _lock(session_id):
        session = _load_session(root, session_id)
        _generation(session, expected_generation)
        if session["status"] in _TERMINAL:
            raise SoulSessionConflict("terminal session cannot be checkpointed")
        if int(session["checkpoint_count"]) >= int(session["max_checkpoints"]):
            raise SoulSessionConflict("checkpoint limit reached")
        selected = set(session.get("selected_obligation_ids") or [])
        unknown = sorted(set(observed) - selected)
        if unknown:
            raise ValueError(f"unselected obligation progress: {unknown}")
        state = _binding_state(root, session)
        if state in {"STALE_TASK", "STALE_ROUTE", "STALE_AUTHORITY"}:
            _invalidate(root, session, state)
            raise SoulSessionConflict(f"session invalidated: {state}")
        current_evidence, _ = _snapshot(root, str(session["resolved_task_id"]))
        generation = int(session["generation"]) + 1
        checkpoint_id = f"soul-checkpoint-{uuid.uuid4().hex}"
        checkpoint = _seal(
            {
                "schema": CHECKPOINT_SCHEMA,
                "checkpoint_id": checkpoint_id,
                "session_id": session_id,
                "generation": generation,
                "parent_checkpoint_hash": session.get("latest_checkpoint_hash"),
                "task_snapshot_hash": session["task_snapshot_hash"],
                "route_plan_hash": session.get("route_plan_hash"),
                "previous_evidence_snapshot_hash": session["evidence_snapshot_hash"],
                "evidence_snapshot_hash": current_evidence,
                "authority_snapshot_hash": session["authority_snapshot_hash"],
                "cursor": safe_cursor,
                "observed_obligation_ids": observed,
                "artifact_refs": artifacts,
                "progress_authority": "HOST_HINT_ONLY",
                "metadata": safe_metadata,
                "created_at": _now(),
                "authority": CONTROL_AUTHORITY,
                "execution_authorized": False,
                "domain_evidence_authority": False,
                "release_authority": False,
            }
        )
        checkpoint_path = _dirs(root)["checkpoints"] / f"{checkpoint_id}.json"
        _write(checkpoint_path, checkpoint, exclusive=True)
        updated = dict(session)
        updated.update(
            {
                "status": "PAUSED" if pause else "OPEN",
                "generation": generation,
                "checkpoint_count": int(session["checkpoint_count"]) + 1,
                "latest_checkpoint_id": checkpoint_id,
                "latest_checkpoint_hash": checkpoint["content_hash"],
                "evidence_snapshot_hash": current_evidence,
                "updated_at": _now(),
            }
        )
        sealed = _seal(updated)
        _persist_session(root, sealed)
        return sealed, checkpoint


def _latest_checkpoint(root: Path, session: Mapping[str, Any]) -> None:
    checkpoint_id = session.get("latest_checkpoint_id")
    checkpoint_hash = session.get("latest_checkpoint_hash")
    if checkpoint_id is None and checkpoint_hash is None:
        if session.get("checkpoint_count") != 0:
            raise SoulSessionIntegrityError("checkpoint count has no head")
        return
    if not isinstance(checkpoint_id, str) or not isinstance(checkpoint_hash, str):
        raise SoulSessionIntegrityError("incomplete checkpoint head")
    checkpoint = _read(_dirs(root)["checkpoints"] / f"{checkpoint_id}.json")
    _verify(checkpoint, CHECKPOINT_SCHEMA)
    if checkpoint["content_hash"] != checkpoint_hash:
        raise SoulSessionIntegrityError("checkpoint head hash mismatch")
    if checkpoint.get("session_id") != session.get("session_id"):
        raise SoulSessionIntegrityError("checkpoint belongs to another session")
    if checkpoint.get("generation") != session.get("generation"):
        raise SoulSessionIntegrityError("checkpoint generation mismatch")


def resume_session(
    root: Path,
    session_id: str,
    *,
    expected_generation: int | None = None,
) -> dict[str, Any]:
    """Return a bounded resume manifest after exact drift validation."""
    with _lock(session_id):
        session = _load_session(root, session_id)
        if expected_generation is not None:
            _generation(session, expected_generation)
        if session["status"] in _TERMINAL:
            return {
                "schema": RESUME_SCHEMA,
                "status": session["status"],
                "reason_code": session.get("invalidated_reason_code"),
                "session_id": session_id,
                "generation": session["generation"],
                "authority": CONTROL_AUTHORITY,
                "resume_authorized": False,
                "execution_authorized": False,
                "release_authority": False,
            }
        _latest_checkpoint(root, session)
        state = _binding_state(root, session)
        if state != "READY":
            invalidated = _invalidate(root, session, state)
            return {
                "schema": RESUME_SCHEMA,
                "status": "INVALIDATED",
                "reason_code": state,
                "session_id": session_id,
                "generation": invalidated["generation"],
                "authority": CONTROL_AUTHORITY,
                "resume_authorized": False,
                "execution_authorized": False,
                "release_authority": False,
            }
        return {
            "schema": RESUME_SCHEMA,
            "status": "READY",
            "session_id": session_id,
            "generation": session["generation"],
            "requested_task_id": session["requested_task_id"],
            "resolved_task_id": session["resolved_task_id"],
            "supersession_chain": list(session["supersession_chain"]),
            "route_plan_id": session.get("route_plan_id"),
            "selected_obligation_ids": list(session["selected_obligation_ids"][:64]),
            "latest_checkpoint_id": session.get("latest_checkpoint_id"),
            "latest_checkpoint_hash": session.get("latest_checkpoint_hash"),
            "session_content_hash": session["content_hash"],
            "authority": CONTROL_AUTHORITY,
            "resume_authorized": False,
            "execution_authorized": False,
            "domain_evidence_authority": False,
            "release_authority": False,
            "host_revalidation_required": True,
        }


def close_session(
    root: Path,
    session_id: str,
    *,
    expected_generation: int,
    reason_code: str = "HOST_CLOSED",
    cancelled: bool = False,
) -> dict[str, Any]:
    """Close/cancel a session without changing task or release state."""
    if not _REASON_RE.fullmatch(reason_code):
        raise ValueError("reason_code must be uppercase machine-readable token")
    with _lock(session_id):
        session = _load_session(root, session_id)
        if session["status"] in {"CLOSED", "CANCELLED"}:
            return session
        _generation(session, expected_generation)
        if session["status"] == "INVALIDATED":
            raise SoulSessionConflict("invalidated session is terminal")
        updated = dict(session)
        updated.update(
            {
                "status": "CANCELLED" if cancelled else "CLOSED",
                "generation": int(session["generation"]) + 1,
                "closed_reason_code": reason_code,
                "updated_at": _now(),
            }
        )
        sealed = _seal(updated)
        _persist_session(root, sealed)
        return sealed


def list_session_frontier(
    root: Path,
    *,
    task_id: str | None = None,
    limit: int = 128,
) -> list[dict[str, Any]]:
    """Return a bounded non-terminal session frontier."""
    if not isinstance(limit, int) or not 1 <= limit <= 1024:
        raise ValueError("limit must be between 1 and 1024")
    directory = _dirs(root)["sessions"]
    if not directory.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        session = _read(path)
        _verify(session, SESSION_SCHEMA)
        if session["status"] in _TERMINAL:
            continue
        if task_id is not None and task_id not in {
            session.get("requested_task_id"),
            session.get("resolved_task_id"),
        }:
            continue
        rows.append(
            {
                "session_id": session["session_id"],
                "status": session["status"],
                "generation": session["generation"],
                "requested_task_id": session["requested_task_id"],
                "resolved_task_id": session["resolved_task_id"],
                "route_plan_id": session.get("route_plan_id"),
                "checkpoint_count": session["checkpoint_count"],
                "latest_checkpoint_id": session.get("latest_checkpoint_id"),
                "authority": CONTROL_AUTHORITY,
                "execution_authorized": False,
                "release_authority": False,
            }
        )
        if len(rows) >= limit:
            break
    return rows


__all__ = [
    "CHECKPOINT_SCHEMA",
    "CONTROL_AUTHORITY",
    "RESUME_SCHEMA",
    "SESSION_SCHEMA",
    "SoulSessionConflict",
    "SoulSessionError",
    "SoulSessionIntegrityError",
    "SoulSessionUnavailable",
    "checkpoint_session",
    "close_session",
    "list_session_frontier",
    "open_session",
    "resume_session",
]
