"""Validate and store privacy-preserving provider-boundary measurements."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from gauntlet_host.constants import (
    MAX_JSONL_BYTES,
    TOKEN_MEASUREMENT_PROTOCOL_VERSION,
)

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_RAW_KEYS = {
    "messages",
    "prompt",
    "request_payload",
    "response_payload",
    "system_prompt",
    "tool_output",
    "tool_result",
    "user_message",
}
AUTHORITY_FIELDS = {
    "cleared",
    "evidence_class",
    "receipt",
    "receipts",
    "release",
    "released",
    "verdict",
}


class TokenMeasurementError(RuntimeError):
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
        raise TokenMeasurementError("INVALID_FIELD", f"{name} must be a non-empty string")
    if len(value) > limit:
        raise TokenMeasurementError("FIELD_TOO_LARGE", f"{name} exceeds {limit} characters")
    return value


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TokenMeasurementError("INVALID_FIELD", f"{name} must be an object")
    return value


def _nonnegative(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise TokenMeasurementError(
            "INVALID_FIELD",
            f"{name} must be a non-negative number",
        )


def _optional_nonnegative(value: Any, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise TokenMeasurementError(
            "INVALID_FIELD",
            f"{name} must be null or a non-negative number",
        )


def _digest(value: Any, name: str) -> None:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise TokenMeasurementError("INVALID_DIGEST", f"{name} must be a keyed digest")


def _validate_measurement_shape(value: Mapping[str, Any]) -> None:
    composition = _object(value.get("request_composition"), "request_composition")
    _digest(composition.get("payload_hmac_sha256"), "payload_hmac_sha256")
    for name in ("canonical_chars", "canonical_utf8_bytes", "local_estimated_tokens"):
        _nonnegative(composition.get(name), f"request_composition.{name}")
    _optional_nonnegative(
        composition.get("wire_utf8_bytes"),
        "request_composition.wire_utf8_bytes",
    )

    reconciliation = _object(composition.get("reconciliation"), "reconciliation")
    if reconciliation.get("non_overlapping") is not True:
        raise TokenMeasurementError(
            "COMPONENT_RECONCILIATION_FAILED",
            "request components must be non-overlapping",
        )
    if reconciliation.get("reconciles_to_canonical_payload") is not True:
        raise TokenMeasurementError(
            "COMPONENT_RECONCILIATION_FAILED",
            "request components must reconcile to the canonical payload",
        )

    components = _object(composition.get("components"), "request_composition.components")
    if not components:
        raise TokenMeasurementError("INVALID_FIELD", "request components cannot be empty")
    for component_name, component_value in components.items():
        component = _object(component_value, f"components.{component_name}")
        availability = component.get("availability")
        if availability == "MEASURED":
            for name in ("items", "chars", "utf8_bytes", "local_estimated_tokens"):
                _nonnegative(component.get(name), f"components.{component_name}.{name}")
            _digest(component.get("hmac_sha256"), f"components.{component_name}.hmac_sha256")
        elif availability == "UNAVAILABLE":
            _text(component.get("reason"), f"components.{component_name}.reason", 512)
            if component.get("hmac_sha256") is not None:
                raise TokenMeasurementError(
                    "INVALID_FIELD",
                    f"components.{component_name}.hmac_sha256 must be null",
                )
        else:
            raise TokenMeasurementError(
                "INVALID_FIELD",
                f"components.{component_name}.availability is unsupported",
            )

    usage = _object(value.get("provider_usage"), "provider_usage")
    if usage.get("source") != "provider_reported":
        raise TokenMeasurementError(
            "INVALID_FIELD",
            "provider_usage.source must be provider_reported",
        )
    for name in (
        "input_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "billable_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        _optional_nonnegative(usage.get(name), f"provider_usage.{name}")

    for name in ("attempt", "retry_count", "fallback_index", "tool_call_count"):
        _optional_nonnegative(value.get(name), name)
    if not isinstance(value.get("fallback_detected"), bool):
        raise TokenMeasurementError("INVALID_FIELD", "fallback_detected must be boolean")
    if not isinstance(value.get("auxiliary_stream"), bool):
        raise TokenMeasurementError("INVALID_FIELD", "auxiliary_stream must be boolean")

    outcome = _object(value.get("outcome"), "outcome")
    if outcome.get("status") not in {"OK", "ERROR"}:
        raise TokenMeasurementError("INVALID_FIELD", "outcome.status is unsupported")
    timing = _object(value.get("timing"), "timing")
    _text(timing.get("started_at"), "timing.started_at", 64)
    _text(timing.get("finished_at"), "timing.finished_at", 64)
    for name in ("latency_ms", "time_to_first_token_ms"):
        _optional_nonnegative(timing.get(name), f"timing.{name}")

    _object(value.get("endpoint_identity"), "endpoint_identity")
    _object(value.get("source"), "source")
    _object(value.get("runtime_estimates"), "runtime_estimates")
    cost = _object(value.get("cost"), "cost")
    if cost.get("status") != "UNPRICED":
        raise TokenMeasurementError("INVALID_FIELD", "TOKEN-000 cost must remain unpriced")

    key_id = value.get("digest_key_id")
    if not isinstance(key_id, str) or not re.fullmatch(r"[0-9a-f]{16}", key_id):
        raise TokenMeasurementError("INVALID_DIGEST", "digest_key_id is invalid")


def _reject_raw_and_authority_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TokenMeasurementError("INVALID_FIELD", f"{path} contains a non-string key")
            if key in FORBIDDEN_RAW_KEYS:
                raise TokenMeasurementError(
                    "RAW_CONTENT_FIELD_REJECTED",
                    f"{path}.{key} is not permitted in token measurements",
                )
            if key in AUTHORITY_FIELDS:
                raise TokenMeasurementError(
                    "AUTHORITY_FIELD_REJECTED",
                    f"{path}.{key} is not permitted in operational measurements",
                )
            _reject_raw_and_authority_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_raw_and_authority_keys(item, f"{path}[{index}]")


def _request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_JSONL_BYTES + 1)
    if len(raw) > MAX_JSONL_BYTES:
        raise TokenMeasurementError("REQUEST_TOO_LARGE", "measurement request is too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenMeasurementError("INVALID_JSON", "stdin must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise TokenMeasurementError("INVALID_REQUEST", "measurement request must be an object")
    _reject_raw_and_authority_keys(value)
    return value


def _runtime_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if not raw:
        raise TokenMeasurementError("RUNTIME_HOME_MISSING", "HERMES_HOME is required")
    home = Path(raw).expanduser().resolve(strict=False)
    if home == (Path.home() / ".hermes").resolve(strict=False):
        raise TokenMeasurementError("RUNTIME_HOME_COLLISION", "ordinary Hermes home is forbidden")
    return home


def build_measurement(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != TOKEN_MEASUREMENT_PROTOCOL_VERSION:
        raise TokenMeasurementError("SCHEMA_MISMATCH", "unsupported token measurement schema")
    task_id = _text(value.get("task_id"), "task_id")
    request_id = _text(value.get("host_request_id"), "host_request_id")
    _text(value.get("dispatch_id"), "dispatch_id")
    request_kind = _text(value.get("request_kind"), "request_kind", limit=32)
    if request_kind not in {"conversation", "auxiliary"}:
        raise TokenMeasurementError(
            "REQUEST_KIND_INVALID",
            "request_kind must be conversation or auxiliary",
        )
    if not IDENTIFIER.fullmatch(task_id) or ".." in task_id:
        raise TokenMeasurementError("TASK_ID_INVALID", "task_id contains unsupported characters")
    if task_id != os.environ.get("GAUNTLET_TASK_ID", "").strip():
        raise TokenMeasurementError("TASK_ID_MISMATCH", "task identity is not host-bound")
    if request_id != os.environ.get("GAUNTLET_HOST_REQUEST_ID", "").strip():
        raise TokenMeasurementError("REQUEST_ID_MISMATCH", "request identity is not host-bound")

    _validate_measurement_shape(value)
    privacy = value.get("privacy")
    if not isinstance(privacy, dict) or any(
        privacy.get(name) is not False
        for name in ("raw_prompt_persisted", "raw_tool_output_persisted", "raw_response_persisted")
    ):
        raise TokenMeasurementError(
            "PRIVACY_ATTESTATION_INVALID",
            "raw prompt, tool output, and response persistence must all be false",
        )

    document = dict(value)
    document["request_kind"] = request_kind
    document["event"] = "runtime.llm.dispatch.finished"
    document["provenance"] = {
        "producer": "gauntlet-token-000",
        "event_source": (
            "hermes.llm_execution"
            if request_kind == "conversation"
            else "agent.auxiliary_client.relay"
        ),
        "final_provider_boundary": True,
        "wire_bytes_available": False,
    }
    document["authority_ceiling"] = "OBSERVATION_ONLY"
    document["canonical_receipt_created"] = False
    document["canonical_state_mutated"] = False
    document.pop("content_hash", None)
    digest = hashlib.sha256(_canonical(document)).hexdigest()
    document["measurement_id"] = f"tok_{digest}"
    document["content_hash"] = digest
    return document


def store_measurement(value: Mapping[str, Any]) -> dict[str, Any]:
    measurement = build_measurement(value)
    task_bucket = hashlib.sha256(measurement["task_id"].encode()).hexdigest()[:24]
    request_bucket = hashlib.sha256(measurement["host_request_id"].encode()).hexdigest()[:24]
    path = (
        _runtime_home()
        / "measurements"
        / "token-efficiency"
        / task_bucket
        / request_bucket
        / f"{measurement['measurement_id']}.json"
    )
    data = _canonical(measurement) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != data:
            raise TokenMeasurementError("MEASUREMENT_COLLISION", "measurement hash collision")
        state = "EXISTS"
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        state = "RECORDED"
    return {
        "schema": "gauntlet.token-measurement-store-result.v1",
        "status": state,
        "measurement_id": measurement["measurement_id"],
        "content_hash": measurement["content_hash"],
        "path": str(path),
        "authority_ceiling": "OBSERVATION_ONLY",
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }


def _error(exc: TokenMeasurementError) -> dict[str, Any]:
    return {
        "schema": "gauntlet.token-measurement-store-result.v1",
        "status": "ERROR",
        "error": {"code": exc.code, "message": exc.message},
        "authority_ceiling": "OBSERVATION_ONLY",
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }


def main() -> int:
    if len(sys.argv) != 1:
        result = _error(
            TokenMeasurementError(
                "INVALID_ARGUMENTS",
                "token measurement bridge accepts stdin only",
            )
        )
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 2
    try:
        result = store_measurement(_request())
        code = 0
    except TokenMeasurementError as exc:
        result, code = _error(exc), 2
    except Exception as exc:
        result, code = (
            _error(
                TokenMeasurementError(
                    "MEASUREMENT_STORE_ERROR",
                    f"operational store failed: {type(exc).__name__}",
                )
            ),
            2,
        )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
