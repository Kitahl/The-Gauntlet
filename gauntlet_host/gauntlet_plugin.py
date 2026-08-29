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
MAX_ADAPTER_OUTPUT_CHARS = 262_144
ADAPTER_TIMEOUT_SECONDS = 20.0
OBSERVATION_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)
_pending_calls: dict[tuple[str, str, str], tuple[str, float]] = {}
_pending_lock = threading.Lock()


class PluginBridgeError(RuntimeError):
    """Typed failure at a runtime-to-Gauntlet subprocess boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _safe_message(value: Any) -> str:
    text = " ".join(str(value).split())
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        text,
    )
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "<redacted-key>", text)
    return (text or "runtime bridge failure")[:1_000]


def _canonical_hash(value: Any) -> str:
    def fallback(item: Any) -> dict[str, str]:
        return {
            "type": f"{type(item).__module__}.{type(item).__qualname__}",
            "repr": _safe_message(repr(item))[:2_000],
        }

    try:
        encoded = json.dumps(
            value,
            default=fallback,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except Exception:
        encoded = fallback(value)["repr"].encode("utf-8", errors="replace")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error_document(action: str, code: str, message: str) -> str:
    return json.dumps(
        {
            "schema": ADAPTER_SCHEMA,
            "action": action,
            "status": "ERROR",
            "error": {
                "code": code,
                "message": _safe_message(message),
            },
            "read_only": True,
            "mutation_performed": False,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PluginBridgeError(
            "BRIDGE_ENVIRONMENT_MISSING",
            f"required runtime bridge variable {name} is not set",
        )
    return value


def _validate_arguments(arguments: Any) -> None:
    if arguments is None:
        return
    if isinstance(arguments, dict) and not arguments:
        return
    raise PluginBridgeError(
        "TOOL_ARGUMENTS_REJECTED",
        "Gauntlet status tools do not accept arguments",
    )


def _adapter_paths() -> tuple[Path, Path]:
    repo_root = Path(_required_environment("GAUNTLET_REPO_ROOT")).resolve()
    module_cli = Path(_required_environment("GAUNTLET_MODULE_CLI")).resolve()
    expected_cli = (repo_root / "gauntlet_host" / "module_cli.py").resolve()
    if module_cli != expected_cli:
        raise PluginBridgeError(
            "MODULE_ADAPTER_PATH_MISMATCH",
            "runtime bridge adapter path does not match the Gauntlet repository",
        )
    if not (repo_root / "tools" / "soul_runtime.py").is_file():
        raise PluginBridgeError(
            "GAUNTLET_REPOSITORY_INVALID",
            "Gauntlet authority files are missing from the configured repository root",
        )
    if not module_cli.is_file():
        raise PluginBridgeError(
            "MODULE_ADAPTER_MISSING",
            f"Gauntlet module adapter is missing: {module_cli}",
        )
    return repo_root, module_cli


def _parse_adapter_output(action: str, task_id: str, stdout: str) -> dict[str, Any]:
    if len(stdout) > MAX_ADAPTER_OUTPUT_CHARS:
        raise PluginBridgeError(
            "MODULE_ADAPTER_OUTPUT_TOO_LARGE",
            "Gauntlet module adapter output exceeded the bounded tool-result limit",
        )
    records = [line for line in stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise PluginBridgeError(
            "MODULE_ADAPTER_PROTOCOL_ERROR",
            "Gauntlet module adapter must return exactly one JSON record",
        )
    try:
        value = json.loads(records[0])
    except json.JSONDecodeError as exc:
        raise PluginBridgeError(
            "MODULE_ADAPTER_PROTOCOL_ERROR",
            f"Gauntlet module adapter returned invalid JSON: {exc.msg}",
        ) from exc
    if not isinstance(value, dict):
        raise PluginBridgeError(
            "MODULE_ADAPTER_PROTOCOL_ERROR",
            "Gauntlet module adapter result must be a JSON object",
        )
    if value.get("schema") != ADAPTER_SCHEMA:
        raise PluginBridgeError(
            "MODULE_ADAPTER_SCHEMA_MISMATCH",
            f"Gauntlet module adapter schema must be {ADAPTER_SCHEMA}",
        )
    if value.get("action") != action or value.get("task_id") != task_id:
        raise PluginBridgeError(
            "MODULE_ADAPTER_CORRELATION_MISMATCH",
            "Gauntlet module adapter result did not match the requested action and task",
        )
    if value.get("read_only") is not True:
        raise PluginBridgeError(
            "MODULE_ADAPTER_AUTHORITY_VIOLATION",
            "Gauntlet module adapter did not attest to the read-only status contract",
        )
    if value.get("mutation_performed") is not False:
        raise PluginBridgeError(
            "MODULE_ADAPTER_AUTHORITY_VIOLATION",
            "Gauntlet status adapter reported a state mutation",
        )
    return value


def _call_adapter(action: str, arguments: Any) -> str:
    try:
        _validate_arguments(arguments)
        task_id = _required_environment("GAUNTLET_TASK_ID")
        repo_root, module_cli = _adapter_paths()
        environment = dict(os.environ)
        environment["GAUNTLET_TASK_ID"] = task_id
        environment["PYTHONPATH"] = str(repo_root)
        environment["PYTHONUNBUFFERED"] = "1"
        for bypass in (
            "HERMES_YOLO_MODE",
            "HERMES_ACCEPT_HOOKS",
            "HERMES_INTERACTIVE",
        ):
            environment.pop(bypass, None)

        completed = subprocess.run(
            [
                sys.executable,
                str(module_cli),
                "--root",
                str(repo_root),
                action,
            ],
            cwd=repo_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ADAPTER_TIMEOUT_SECONDS,
            check=False,
        )
        value = _parse_adapter_output(action, task_id, completed.stdout)
        status = value.get("status")
        expected_exit = 0 if status == "OK" else 2
        if completed.returncode != expected_exit:
            raise PluginBridgeError(
                "MODULE_ADAPTER_EXIT_MISMATCH",
                (
                    f"Gauntlet module adapter exited with {completed.returncode}; "
                    f"status {status!r} requires {expected_exit}"
                ),
            )
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except subprocess.TimeoutExpired:
        return _error_document(
            action,
            "MODULE_ADAPTER_TIMEOUT",
            f"Gauntlet module adapter exceeded {ADAPTER_TIMEOUT_SECONDS:g} seconds",
        )
    except OSError as exc:
        return _error_document(action, "MODULE_ADAPTER_START_FAILED", str(exc))
    except PluginBridgeError as exc:
        return _error_document(action, exc.code, exc.message)
    except Exception as exc:
        return _error_document(action, "MODULE_ADAPTER_UNEXPECTED_FAILURE", str(exc))


def _task_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _call_adapter("task-status", arguments)


def _release_status(arguments: dict[str, Any] | None = None, **_: Any) -> str:
    return _call_adapter("release-status", arguments)


def _call_key(
    tool_name: str,
    session_id: str,
    tool_call_id: str,
) -> tuple[str, str, str]:
    return (
        session_id or "unknown-session",
        tool_call_id or "unknown-call",
        tool_name or "unknown-tool",
    )


def _on_pre_tool_call(
    tool_name: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> None:
    key = _call_key(tool_name, session_id, tool_call_id)
    with _pending_lock:
        _pending_calls[key] = (_utc_now(), time.monotonic())


def _tool_status(result: Any, values: dict[str, Any]) -> str:
    if values.get("timed_out") is True:
        return "TIMEOUT"
    if values.get("cancelled") is True:
        return "CANCELLED"
    if values.get("unavailable") is True:
        return "UNAVAILABLE"
    if values.get("error") is not None or values.get("exception") is not None:
        return "ERROR"
    if isinstance(result, dict):
        candidate = str(result.get("status") or "").upper()
        if candidate in {"ERROR", "TIMEOUT", "UNAVAILABLE", "CANCELLED"}:
            return candidate
        if result.get("success") is False:
            return "ERROR"
    return "OK"


def _observation_path() -> Path:
    bridge = Path(_required_environment("GAUNTLET_OBSERVATION_BRIDGE")).resolve()
    repo_root = Path(_required_environment("GAUNTLET_REPO_ROOT")).resolve()
    expected = (repo_root / "gauntlet_host" / "observation_bridge.py").resolve()
    if bridge != expected or not bridge.is_file():
        raise PluginBridgeError(
            "OBSERVATION_BRIDGE_PATH_MISMATCH",
            "runtime observation bridge path is not the expected Gauntlet file",
        )
    return bridge


def _record_observation(document: dict[str, Any]) -> None:
    try:
        bridge = _observation_path()
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        completed = subprocess.run(
            [sys.executable, str(bridge)],
            input=json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=OBSERVATION_TIMEOUT_SECONDS,
            check=False,
        )
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode != 0 or len(records) != 1:
            logger.warning(
                "Gauntlet observation bridge failed safely: exit=%s",
                completed.returncode,
            )
            return
        result = json.loads(records[0])
        if result.get("schema") != OBSERVATION_SCHEMA:
            logger.warning("Gauntlet observation bridge returned an invalid schema")
    except Exception as exc:
        logger.warning(
            "Gauntlet observation hook failed safely: %s",
            _safe_message(exc),
        )


def _on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    session_id: str = "",
    tool_call_id: str = "",
    **values: Any,
) -> None:
    finished_at = _utc_now()
    finished_monotonic = time.monotonic()
    key = _call_key(tool_name, session_id, tool_call_id)
    with _pending_lock:
        start = _pending_calls.pop(key, None)
    if start is None:
        started_at = finished_at
        duration_ms = 0.0
    else:
        started_at, started_monotonic = start
        duration_ms = max(0.0, (finished_monotonic - started_monotonic) * 1_000)

    try:
        task_id = _required_environment("GAUNTLET_TASK_ID")
    except PluginBridgeError:
        return

    _record_observation(
        {
            "task_id": task_id,
            "runtime_session_id": session_id or "unknown-session",
            "tool_call_id": tool_call_id or "unknown-call",
            "tool": tool_name or "unknown-tool",
            "status": _tool_status(result, values),
            "input_hash": _canonical_hash(args),
            "output_hash": _canonical_hash(result),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "provenance": {
                "producer": "gauntlet-fastpath-plugin",
                "event_source": "hermes.post_tool_call",
                "raw_input_persisted": False,
                "raw_output_persisted": False,
            },
        }
    )


_TASK_STATUS_SCHEMA = {
    "description": (
        "Read the canonical Gauntlet task and obligation status for the exact "
        "GAUNTLET_TASK_ID bound by the host. This tool is read-only and cannot "
        "create receipts, change verdicts, clear obligations, or release a task."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

_RELEASE_STATUS_SCHEMA = {
    "description": (
        "Read the current Soul release-gate result for the exact host-bound task. "
        "This reports eligibility only; it never calls release_task and performs "
        "no mutation."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


def register(ctx: Any) -> None:
    """Register read-only tools and observation-only lifecycle hooks."""

    ctx.register_tool(
        name="gauntlet_task_status",
        toolset=TOOLSET,
        schema=_TASK_STATUS_SCHEMA,
        handler=_task_status,
        description=_TASK_STATUS_SCHEMA["description"],
        emoji="",
    )
    ctx.register_tool(
        name="gauntlet_release_status",
        toolset=TOOLSET,
        schema=_RELEASE_STATUS_SCHEMA,
        handler=_release_status,
        description=_RELEASE_STATUS_SCHEMA["description"],
        emoji="",
    )
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
