"""Strict typed JSONL contracts for the isolated runtime worker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TextIO

from gauntlet_host.constants import (
    HOST_PROTOCOL_VERSION,
    LEAN_PROFILE_NAME,
    MAX_JSONL_BYTES,
    SUPPORTED_RUNTIME_PROFILES,
    WORKER_REQUEST_TYPE,
    WORKER_RESULT_TYPE,
)


class WorkerOperation(StrEnum):
    """Operations understood by the isolated worker boundary."""

    PROBE_IMPORTS = "probe_imports"
    RUN = "run"


class WorkerStatus(StrEnum):
    """Transport-level worker outcomes, never Gauntlet verdicts."""

    OK = "OK"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    """One parent-to-worker request."""

    request_id: str
    task_id: str
    operation: WorkerOperation
    runtime_profile: str = LEAN_PROFILE_NAME
    session_id: str | None = None
    prompt: str = ""
    cwd: str | None = None
    model: str | None = None
    provider: str | None = None
    toolsets: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkerError:
    """Machine-readable worker failure detail."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """One worker-to-parent result with no evidential authority fields."""

    request_id: str
    task_id: str
    status: WorkerStatus
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: WorkerError | None = None


class IPCContractError(ValueError):
    """Raised when a JSONL record violates the worker protocol."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_string(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool = False,
    maximum: int = 256,
) -> str:
    if not isinstance(value, str):
        raise IPCContractError("INVALID_FIELD_TYPE", f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise IPCContractError("INVALID_FIELD_VALUE", f"{field_name} must not be empty")
    if len(value) > maximum:
        raise IPCContractError(
            "FIELD_TOO_LARGE",
            f"{field_name} exceeds the {maximum}-character limit",
        )
    return value


def _optional_string(value: Any, *, field_name: str, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name=field_name, maximum=maximum)


def _decode_json_object(line: str, *, record_name: str) -> dict[str, Any]:
    if len(line.encode("utf-8")) > MAX_JSONL_BYTES:
        raise IPCContractError(
            f"{record_name.upper()}_TOO_LARGE",
            f"{record_name} exceeds the {MAX_JSONL_BYTES}-byte JSONL limit",
        )
    try:
        value = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKeyError as exc:
        raise IPCContractError("DUPLICATE_JSON_KEY", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise IPCContractError("INVALID_JSON", f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise IPCContractError(
            "INVALID_RECORD",
            f"{record_name} must be a JSON object",
        )
    return value


def _encode_json_object(value: dict[str, Any], *, record_name: str) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise IPCContractError(
            f"UNENCODABLE_{record_name.upper()}",
            f"{record_name} is not JSON-serializable: {exc}",
        ) from exc
    if len(encoded.encode("utf-8")) > MAX_JSONL_BYTES:
        raise IPCContractError(
            f"{record_name.upper()}_TOO_LARGE",
            f"{record_name} exceeds the {MAX_JSONL_BYTES}-byte JSONL limit",
        )
    return encoded


def _decode_toolsets(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise IPCContractError("INVALID_FIELD_TYPE", "toolsets must be an array")

    toolsets: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        toolset = _require_string(item, field_name=f"toolsets[{index}]")
        if toolset in seen:
            raise IPCContractError("DUPLICATE_TOOLSET", f"duplicate toolset: {toolset}")
        seen.add(toolset)
        toolsets.append(toolset)
    return tuple(toolsets)


def encode_request(request: RuntimeRequest) -> str:
    """Encode one deterministic parent-to-worker request."""

    value: dict[str, Any] = {
        "schema": HOST_PROTOCOL_VERSION,
        "type": WORKER_REQUEST_TYPE,
        "request_id": request.request_id,
        "task_id": request.task_id,
        "operation": request.operation.value,
        "runtime_profile": request.runtime_profile,
        "prompt": request.prompt,
        "toolsets": list(request.toolsets),
        "metadata": request.metadata,
    }
    if request.session_id is not None:
        value["session_id"] = request.session_id
    if request.cwd is not None:
        value["cwd"] = request.cwd
    if request.model is not None:
        value["model"] = request.model
    if request.provider is not None:
        value["provider"] = request.provider
    return _encode_json_object(value, record_name="request")


def decode_request(line: str) -> RuntimeRequest:
    """Decode one strict JSONL request line."""

    value = _decode_json_object(line, record_name="request")
    allowed_fields = {
        "schema",
        "type",
        "request_id",
        "task_id",
        "operation",
        "runtime_profile",
        "session_id",
        "prompt",
        "cwd",
        "model",
        "provider",
        "toolsets",
        "metadata",
    }
    unknown_fields = sorted(set(value) - allowed_fields)
    if unknown_fields:
        raise IPCContractError(
            "UNKNOWN_FIELDS",
            f"unknown request fields: {', '.join(unknown_fields)}",
        )

    if value.get("schema") != HOST_PROTOCOL_VERSION:
        raise IPCContractError(
            "UNSUPPORTED_SCHEMA",
            f"schema must be {HOST_PROTOCOL_VERSION}",
        )
    if value.get("type") != WORKER_REQUEST_TYPE:
        raise IPCContractError(
            "INVALID_RECORD_TYPE",
            f"type must be {WORKER_REQUEST_TYPE}",
        )

    request_id = _require_string(value.get("request_id"), field_name="request_id")
    task_id = _require_string(value.get("task_id"), field_name="task_id")
    operation_text = _require_string(value.get("operation"), field_name="operation")
    try:
        operation = WorkerOperation(operation_text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in WorkerOperation)
        raise IPCContractError(
            "UNSUPPORTED_OPERATION",
            f"operation must be one of: {allowed}",
        ) from exc

    runtime_profile = _require_string(
        value.get("runtime_profile", LEAN_PROFILE_NAME),
        field_name="runtime_profile",
    )
    if runtime_profile not in SUPPORTED_RUNTIME_PROFILES:
        raise IPCContractError(
            "UNSUPPORTED_RUNTIME_PROFILE",
            "runtime_profile must be one of: " + ", ".join(SUPPORTED_RUNTIME_PROFILES),
        )

    prompt = _require_string(
        value.get("prompt", ""),
        field_name="prompt",
        allow_empty=True,
        maximum=MAX_JSONL_BYTES,
    )
    if operation is WorkerOperation.RUN and not prompt.strip():
        raise IPCContractError("MISSING_PROMPT", "run requests require a non-empty prompt")

    metadata = value.get("metadata", {})
    if not isinstance(metadata, dict):
        raise IPCContractError("INVALID_FIELD_TYPE", "metadata must be an object")

    return RuntimeRequest(
        request_id=request_id,
        task_id=task_id,
        operation=operation,
        runtime_profile=runtime_profile,
        session_id=_optional_string(
            value.get("session_id"),
            field_name="session_id",
            maximum=128,
        ),
        prompt=prompt,
        cwd=_optional_string(value.get("cwd"), field_name="cwd"),
        model=_optional_string(value.get("model"), field_name="model"),
        provider=_optional_string(value.get("provider"), field_name="provider"),
        toolsets=_decode_toolsets(value.get("toolsets")),
        metadata=dict(metadata),
    )


def encode_result(result: RuntimeResult) -> str:
    """Encode one deterministic JSONL result line without a trailing newline."""

    value: dict[str, Any] = {
        "schema": HOST_PROTOCOL_VERSION,
        "type": WORKER_RESULT_TYPE,
        "request_id": result.request_id,
        "task_id": result.task_id,
        "status": result.status.value,
        "event": result.event,
        "payload": result.payload,
    }
    if result.error is not None:
        value["error"] = {
            "code": result.error.code,
            "message": result.error.message,
        }
    return _encode_json_object(value, record_name="result")


def decode_result(line: str) -> RuntimeResult:
    """Decode one strict worker-to-parent result line."""

    value = _decode_json_object(line, record_name="result")
    allowed_fields = {
        "schema",
        "type",
        "request_id",
        "task_id",
        "status",
        "event",
        "payload",
        "error",
    }
    unknown_fields = sorted(set(value) - allowed_fields)
    if unknown_fields:
        raise IPCContractError(
            "UNKNOWN_FIELDS",
            f"unknown result fields: {', '.join(unknown_fields)}",
        )

    if value.get("schema") != HOST_PROTOCOL_VERSION:
        raise IPCContractError(
            "UNSUPPORTED_SCHEMA",
            f"schema must be {HOST_PROTOCOL_VERSION}",
        )
    if value.get("type") != WORKER_RESULT_TYPE:
        raise IPCContractError(
            "INVALID_RECORD_TYPE",
            f"type must be {WORKER_RESULT_TYPE}",
        )

    request_id = _require_string(value.get("request_id"), field_name="request_id")
    task_id = _require_string(value.get("task_id"), field_name="task_id")
    status_text = _require_string(value.get("status"), field_name="status")
    try:
        status = WorkerStatus(status_text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in WorkerStatus)
        raise IPCContractError(
            "INVALID_WORKER_STATUS",
            f"status must be one of: {allowed}",
        ) from exc

    event = _require_string(value.get("event"), field_name="event")
    payload = value.get("payload", {})
    if not isinstance(payload, dict):
        raise IPCContractError("INVALID_FIELD_TYPE", "payload must be an object")

    error_value = value.get("error")
    error: WorkerError | None = None
    if error_value is not None:
        if not isinstance(error_value, dict):
            raise IPCContractError("INVALID_FIELD_TYPE", "error must be an object")
        unknown_error_fields = sorted(set(error_value) - {"code", "message"})
        if unknown_error_fields:
            raise IPCContractError(
                "UNKNOWN_FIELDS",
                f"unknown error fields: {', '.join(unknown_error_fields)}",
            )
        error = WorkerError(
            code=_require_string(error_value.get("code"), field_name="error.code"),
            message=_require_string(
                error_value.get("message"),
                field_name="error.message",
                maximum=16_384,
            ),
        )

    if status is WorkerStatus.OK and error is not None:
        raise IPCContractError("INVALID_RESULT", "OK results must not contain an error")
    if status is not WorkerStatus.OK and error is None:
        raise IPCContractError(
            "INVALID_RESULT",
            "ERROR and UNAVAILABLE results require an error object",
        )

    return RuntimeResult(
        request_id=request_id,
        task_id=task_id,
        status=status,
        event=event,
        payload=dict(payload),
        error=error,
    )


def write_result(stream: TextIO, result: RuntimeResult) -> None:
    """Write and flush one worker result as JSONL."""

    stream.write(encode_result(result))
    stream.write("\n")
    stream.flush()


def contract_error_result(exc: IPCContractError) -> RuntimeResult:
    """Convert a request-contract failure into a structured result."""

    return RuntimeResult(
        request_id="unknown",
        task_id="unknown",
        status=WorkerStatus.ERROR,
        event="worker.request_rejected",
        error=WorkerError(code=exc.code, message=exc.message),
    )
