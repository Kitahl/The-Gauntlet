"""Read-only Gauntlet status tools and observation-only runtime hooks."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any

ADAPTER_SCHEMA = "gauntlet.adapter.v1"
OBSERVATION_SCHEMA = "gauntlet.observation-store-result.v1"
TOOLSET = "gauntlet"
ADAPTER_TIMEOUT = 20.0
OBSERVATION_TIMEOUT = 10.0
MAX_ADAPTER_OUTPUT = 262_144

logger = logging.getLogger(__name__)
_pending: dict[tuple[str, str, str], tuple[str, float]] = {}
_pending_lock = threading.Lock()


class BridgeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _safe(value: Any) -> str:
    text = " ".join(str(value).split())
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    return re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "<redacted-key>", text)[:1_000]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BridgeError("BRIDGE_ENVIRONMENT_MISSING", f"{name} is required")
    return value


def _error(action: str, exc: BridgeError) -> str:
    return json.dumps(
        {
            "schema": ADAPTER_SCHEMA,
            "action": action,
            "status": "ERROR",
            "error": {"code": exc.code, "message": _safe(exc.message)},
            "read_only": True,
            "mutation_performed": False,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _status_call(action: str, arguments: Any) -> str:
    try:
        if arguments not in (None, {}):
            raise BridgeError(
                "TOOL_ARGUMENTS_REJECTED",
                "Gauntlet status tools do not accept arguments",
            )
        task_id = _env("GAUNTLET_TASK_ID")
        root = Path(_env("GAUNTLET_REPO_ROOT")).resolve()
        adapter = Path(_env("GAUNTLET_MODULE_CLI")).resolve()
        expected = (root / "gauntlet_host" / "module_cli.py").resolve()
        if adapter != expected or not adapter.is_file():
            raise BridgeError("MODULE_ADAPTER_PATH_MISMATCH", "invalid module adapter")
        environment = dict(os.environ)
        environment.update(
            {
                "GAUNTLET_TASK_ID": task_id,
                "PYTHONPATH": str(root),
                "PYTHONUNBUFFERED": "1",
            }
        )
        for name in ("HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS", "HERMES_INTERACTIVE"):
            environment.pop(name, None)
        completed = subprocess.run(
            [sys.executable, str(adapter), "--root", str(root), action],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ADAPTER_TIMEOUT,
            check=False,
        )
        if len(completed.stdout) > MAX_ADAPTER_OUTPUT:
            raise BridgeError("MODULE_ADAPTER_OUTPUT_TOO_LARGE", "adapter output too large")
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(records) != 1:
            raise BridgeError("MODULE_ADAPTER_PROTOCOL_ERROR", "expected one JSON record")
        value = json.loads(records[0])
        if not isinstance(value, dict):
            raise BridgeError("MODULE_ADAPTER_PROTOCOL_ERROR", "result must be an object")
        if value.get("schema") != ADAPTER_SCHEMA:
            raise BridgeError("MODULE_ADAPTER_SCHEMA_MISMATCH", "invalid adapter schema")
        if value.get("action") != action or value.get("task_id") != task_id:
            raise BridgeError("MODULE_ADAPTER_CORRELATION_MISMATCH", "adapter mismatch")
        if value.get("read_only") is not True or value.get("mutation_performed") is not False:
            raise BridgeError("MODULE_ADAPTER_AUTHORITY_VIOLATION", "adapter was not read-only")
        expected_exit = 0 if value.get("status") == "OK" else 2
        if completed.returncode != expected_exit:
            raise BridgeError("MODULE_ADAPTER_EXIT_MISMATCH", "adapter exit mismatch")
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except subprocess.TimeoutExpired:
        return _error(action, BridgeError("MODULE_ADAPTER_TIMEOUT", "adapter timed out"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error(action, BridgeError("MODULE_ADAPTER_FAILURE", str(exc)))
    except BridgeError as exc:
        return _error(action, exc)
    except Exception as exc:
        return _error(action, BridgeError("MODULE_ADAPTER_UNEXPECTED_FAILURE", str(exc)))


def _task_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _status_call("task-status", arguments)


def _release_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _status_call("release-status", arguments)


def _hash(value: Any) -> str:
    def fallback(item: Any) -> dict[str, str]:
        return {"type": type(item).__qualname__, "repr": _safe(repr(item))[:2_000]}

    try:
        data = json.dumps(
            value,
            default=fallback,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except Exception:
        data = fallback(value)["repr"].encode(errors="replace")
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hook_inputs(
    positional: tuple[Any, ...], values: dict[str, Any]
) -> tuple[str, Any, Any, str, str]:
    name = values.get("tool_name") or values.get("function_name")
    arguments = values.get("args")
    if arguments is None:
        arguments = values.get("function_args", values.get("arguments"))
    result = values.get("result")
    if name is None and positional:
        name = positional[0]
    if arguments is None and len(positional) > 1:
        arguments = positional[1]
    if result is None and len(positional) > 2:
        result = positional[2]
    return (
        str(name or "unknown-tool"),
        arguments,
        result,
        str(values.get("session_id") or "unknown-session"),
        str(values.get("tool_call_id") or values.get("call_id") or "unknown-call"),
    )


def _key(name: str, session_id: str, call_id: str) -> tuple[str, str, str]:
    return session_id, call_id, name


def _pre(*positional: Any, **values: Any) -> None:
    name, _, _, session_id, call_id = _hook_inputs(positional, values)
    with _pending_lock:
        _pending[_key(name, session_id, call_id)] = (_now(), time.monotonic())


def _status(result: Any, values: dict[str, Any]) -> str:
    explicit = str(values.get("status") or "").upper()
    mapping = {
        "SUCCESS": "OK",
        "SUCCEEDED": "OK",
        "COMPLETED": "OK",
        "FAILED": "ERROR",
        "FAILURE": "ERROR",
        "TIMED_OUT": "TIMEOUT",
        "NOT_AVAILABLE": "UNAVAILABLE",
        "CANCELED": "CANCELLED",
    }
    explicit = mapping.get(explicit, explicit)
    if explicit in {"OK", "ERROR", "TIMEOUT", "UNAVAILABLE", "CANCELLED"}:
        return explicit
    if values.get("timed_out") is True:
        return "TIMEOUT"
    if values.get("cancelled") is True or values.get("canceled") is True:
        return "CANCELLED"
    if values.get("error") is not None or values.get("exception") is not None:
        return "ERROR"
    if isinstance(result, dict) and result.get("success") is False:
        return "ERROR"
    return "OK"


def _record(document: dict[str, Any]) -> None:
    try:
        root = Path(_env("GAUNTLET_REPO_ROOT")).resolve()
        bridge = Path(_env("GAUNTLET_OBSERVATION_BRIDGE")).resolve()
        expected = (root / "gauntlet_host" / "observation_bridge.py").resolve()
        if bridge != expected or not bridge.is_file():
            raise BridgeError("OBSERVATION_BRIDGE_PATH_MISMATCH", "invalid bridge")
        completed = subprocess.run(
            [sys.executable, str(bridge)],
            input=json.dumps(document, separators=(",", ":"), sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            timeout=OBSERVATION_TIMEOUT,
            check=False,
        )
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode != 0 or len(records) != 1:
            raise BridgeError("OBSERVATION_BRIDGE_FAILURE", "bridge failed safely")
        if json.loads(records[0]).get("schema") != OBSERVATION_SCHEMA:
            raise BridgeError("OBSERVATION_SCHEMA_MISMATCH", "invalid bridge schema")
    except Exception as exc:
        logger.warning("Gauntlet observation hook failed safely: %s", _safe(exc))


def _post(*positional: Any, **values: Any) -> None:
    finished_at = _now()
    finished_clock = time.monotonic()
    name, arguments, result, session_id, call_id = _hook_inputs(positional, values)
    with _pending_lock:
        start = _pending.pop(_key(name, session_id, call_id), None)
    supplied = values.get("duration_ms")
    if isinstance(supplied, bool) or not isinstance(supplied, (int, float)):
        supplied = None
    if start is None:
        started_at = finished_at
        duration_ms = float(supplied or 0.0)
    else:
        started_at, started_clock = start
        duration_ms = (
            float(supplied)
            if supplied is not None
            else max(0.0, (finished_clock - started_clock) * 1_000)
        )
    try:
        task_id = _env("GAUNTLET_TASK_ID")
    except BridgeError:
        return
    _record(
        {
            "task_id": task_id,
            "runtime_session_id": session_id,
            "tool_call_id": call_id,
            "tool": name,
            "status": _status(result, values),
            "input_hash": _hash(arguments),
            "output_hash": _hash(result),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": max(0.0, duration_ms),
        }
    )


_TASK_SCHEMA = {
    "description": (
        "Read canonical status for the exact host-bound task. Read-only: cannot "
        "create receipts, change verdicts, clear obligations, or release a task."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
_RELEASE_SCHEMA = {
    "description": (
        "Read Soul release-gate status for the exact host-bound task. This reports "
        "eligibility only and performs no mutation."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="gauntlet_task_status",
        toolset=TOOLSET,
        schema=_TASK_SCHEMA,
        handler=_task_status,
        description=_TASK_SCHEMA["description"],
        emoji="",
    )
    ctx.register_tool(
        name="gauntlet_release_status",
        toolset=TOOLSET,
        schema=_RELEASE_SCHEMA,
        handler=_release_status,
        description=_RELEASE_SCHEMA["description"],
        emoji="",
    )
    ctx.register_hook("pre_tool_call", _pre)
    ctx.register_hook("post_tool_call", _post)
