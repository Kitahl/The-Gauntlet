"""Read-only Gauntlet status tools loaded through the vendored plugin ABI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ADAPTER_SCHEMA = "gauntlet.adapter.v1"
TOOLSET = "gauntlet"
MAX_ADAPTER_OUTPUT_CHARS = 262_144
ADAPTER_TIMEOUT_SECONDS = 20.0


class PluginBridgeError(RuntimeError):
    """Typed failure at the runtime-to-Gauntlet subprocess boundary."""

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
    """Register the minimal read-only Gauntlet tool surface."""

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
