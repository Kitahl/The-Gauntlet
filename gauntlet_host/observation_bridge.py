"""Write content-addressed operational tool observations outside canonical state."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping

if __package__ in {None, ""}:
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from gauntlet_host.constants import MAX_JSONL_BYTES, OBSERVATION_PROTOCOL_VERSION

TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
STATUSES = {"OK", "ERROR", "TIMEOUT", "UNAVAILABLE", "CANCELLED"}
FIELDS = {
    "task_id",
    "runtime_session_id",
    "tool_call_id",
    "tool",
    "status",
    "input_hash",
    "output_hash",
    "started_at",
    "finished_at",
    "duration_ms",
}
AUTHORITY_FIELDS = {
    "verdict",
    "receipt",
    "receipts",
    "evidence_class",
    "release",
    "released",
    "cleared",
}


class ObservationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _text(value: Any, name: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError("INVALID_FIELD", f"{name} must be a non-empty string")
    if len(value) > limit:
        raise ObservationError("FIELD_TOO_LARGE", f"{name} exceeds {limit} characters")
    return value


def _digest(value: Any, name: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = _text(value, name, 64)
    if not DIGEST.fullmatch(text):
        raise ObservationError("INVALID_DIGEST", f"{name} must be a SHA-256 digest")
    return text


def _request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_JSONL_BYTES + 1)
    if len(raw) > MAX_JSONL_BYTES:
        raise ObservationError("REQUEST_TOO_LARGE", "observation request is too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObservationError("INVALID_JSON", "stdin must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise ObservationError("INVALID_REQUEST", "observation request must be an object")
    unknown = sorted(set(value) - FIELDS)
    if unknown:
        raise ObservationError("UNKNOWN_FIELDS", f"unknown fields: {', '.join(unknown)}")
    forbidden = sorted(AUTHORITY_FIELDS.intersection(value))
    if forbidden:
        raise ObservationError(
            "AUTHORITY_FIELD_REJECTED",
            f"forbidden authority fields: {', '.join(forbidden)}",
        )
    return value


def _runtime_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if not raw:
        raise ObservationError("RUNTIME_HOME_MISSING", "HERMES_HOME is required")
    home = Path(raw).expanduser().resolve(strict=False)
    if home == (Path.home() / ".hermes").resolve(strict=False):
        raise ObservationError("RUNTIME_HOME_COLLISION", "ordinary Hermes home is forbidden")
    return home


def build_observation(value: Mapping[str, Any]) -> dict[str, Any]:
    task_id = _text(value.get("task_id"), "task_id")
    bound = os.environ.get("GAUNTLET_TASK_ID", "").strip()
    if not bound or task_id != bound:
        raise ObservationError("TASK_ID_MISMATCH", "task identity is not host-bound")
    if not TASK_ID.fullmatch(task_id) or ".." in task_id:
        raise ObservationError("TASK_ID_INVALID", "task_id contains unsupported characters")

    status = _text(value.get("status"), "status", 32)
    if status not in STATUSES:
        raise ObservationError("INVALID_STATUS", "unsupported operational status")
    duration = value.get("duration_ms")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ObservationError("INVALID_DURATION", "duration_ms must be numeric")
    if duration < 0 or duration > 86_400_000:
        raise ObservationError("INVALID_DURATION", "duration_ms is outside its bound")

    document: dict[str, Any] = {
        "schema": OBSERVATION_PROTOCOL_VERSION,
        "event": "runtime.tool.finished",
        "task_id": task_id,
        "runtime_session_id": _text(
            value.get("runtime_session_id") or "unknown-session",
            "runtime_session_id",
        ),
        "tool_call_id": _text(
            value.get("tool_call_id") or "unknown-call",
            "tool_call_id",
        ),
        "tool": _text(value.get("tool"), "tool"),
        "status": status,
        "input_hash": _digest(value.get("input_hash"), "input_hash"),
        "output_hash": _digest(value.get("output_hash"), "output_hash", True),
        "started_at": _text(value.get("started_at"), "started_at", 64),
        "finished_at": _text(value.get("finished_at"), "finished_at", 64),
        "duration_ms": round(float(duration), 3),
        "provenance": {
            "producer": "gauntlet-fastpath-plugin",
            "event_source": "hermes.post_tool_call",
            "raw_input_persisted": False,
            "raw_output_persisted": False,
        },
        "authority_ceiling": "OBSERVATION_ONLY",
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }
    digest = hashlib.sha256(_canonical(document)).hexdigest()
    document["observation_id"] = f"obs_{digest}"
    document["content_hash"] = digest
    return document


def store_observation(value: Mapping[str, Any]) -> dict[str, Any]:
    observation = build_observation(value)
    task_bucket = hashlib.sha256(observation["task_id"].encode()).hexdigest()[:24]
    path = (
        _runtime_home()
        / "observations"
        / task_bucket
        / f"{observation['observation_id']}.json"
    )
    data = _canonical(observation) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ObservationError("OBSERVATION_COLLISION", "observation hash collision")
        state = "EXISTS"
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        state = "RECORDED"
    return {
        "schema": "gauntlet.observation-store-result.v1",
        "status": state,
        "observation_id": observation["observation_id"],
        "content_hash": observation["content_hash"],
        "path": str(path),
        "authority_ceiling": "OBSERVATION_ONLY",
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }


def _error(exc: ObservationError) -> dict[str, Any]:
    return {
        "schema": "gauntlet.observation-store-result.v1",
        "status": "ERROR",
        "error": {"code": exc.code, "message": exc.message},
        "authority_ceiling": "OBSERVATION_ONLY",
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps(_error(ObservationError(
            "INVALID_ARGUMENTS",
            "observation bridge accepts stdin only",
        )), sort_keys=True))
        return 2
    try:
        result = store_observation(_request())
        code = 0
    except ObservationError as exc:
        result, code = _error(exc), 2
    except Exception as exc:
        result, code = _error(ObservationError(
            "OBSERVATION_STORE_ERROR",
            f"operational store failed: {type(exc).__name__}",
        )), 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
