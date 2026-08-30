"""Aggregate TOKEN-000 dispatch records for one host request."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gauntlet_host.constants import (
    TOKEN_MEASUREMENT_PROTOCOL_VERSION,
    TOKEN_MEASUREMENT_SUMMARY_VERSION,
)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _bucket(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _valid(document: dict[str, Any], task_id: str, request_id: str) -> bool:
    if document.get("schema") != TOKEN_MEASUREMENT_PROTOCOL_VERSION:
        return False
    if document.get("task_id") != task_id or document.get("host_request_id") != request_id:
        return False
    supplied = document.get("content_hash")
    if not isinstance(supplied, str) or len(supplied) != 64:
        return False
    payload = dict(document)
    payload.pop("content_hash", None)
    payload.pop("measurement_id", None)
    return hashlib.sha256(_canonical(payload)).hexdigest() == supplied


def _sessions(records: list[dict[str, Any]]) -> list[str]:
    return sorted({str(item.get("runtime_session_id")) for item in records})


def summarize_measurements(
    runtime_home: str,
    *,
    task_id: str,
    request_id: str,
    expected_api_calls: Any,
    provider_usage: dict[str, Any],
) -> dict[str, Any]:
    root = (
        Path(runtime_home)
        / "measurements"
        / "token-efficiency"
        / _bucket(task_id)
        / _bucket(request_id)
    )
    records: list[dict[str, Any]] = []
    invalid_records = 0
    if root.is_dir():
        for path in sorted(root.glob("tok_*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid_records += 1
                continue
            if not isinstance(value, dict) or not _valid(value, task_id, request_id):
                invalid_records += 1
                continue
            records.append(value)

    records.sort(
        key=lambda item: (
            item.get("attempt") if isinstance(item.get("attempt"), (int, float)) else 10**9,
            str(item.get("dispatch_id") or ""),
        )
    )
    conversation_records = [item for item in records if item.get("request_kind") == "conversation"]
    auxiliary_records = [item for item in records if item.get("request_kind") == "auxiliary"]
    unknown_records = [
        item for item in records if item.get("request_kind") not in {"conversation", "auxiliary"}
    ]
    expected = (
        int(expected_api_calls)
        if isinstance(expected_api_calls, int) and not isinstance(expected_api_calls, bool)
        else None
    )
    dropped = max(0, expected - len(conversation_records)) if expected is not None else None
    measurement_ids = [str(item.get("measurement_id")) for item in records]
    source_pairs = sorted(
        {
            (
                str(item.get("source", {}).get("running_commit") or ""),
                str(item.get("source", {}).get("running_tree") or ""),
            )
            for item in records
        }
    )
    return {
        "schema": TOKEN_MEASUREMENT_SUMMARY_VERSION,
        "phase": "TOKEN-000",
        "mode": "MEASUREMENT_ONLY",
        "host_request_id": request_id,
        "dispatches_recorded": len(records),
        "conversation_dispatches_recorded": len(conversation_records),
        "auxiliary_dispatches_recorded": len(auxiliary_records),
        "unknown_dispatches_recorded": len(unknown_records),
        "expected_api_calls": expected,
        "measurement_drop_count": dropped,
        "invalid_record_count": invalid_records,
        "measurement_complete": (
            dropped == 0 and invalid_records == 0 and not unknown_records
            if dropped is not None
            else False
        ),
        "measurement_ids": measurement_ids,
        "conversation_measurement_ids": [
            str(item.get("measurement_id")) for item in conversation_records
        ],
        "auxiliary_measurement_ids": [
            str(item.get("measurement_id")) for item in auxiliary_records
        ],
        "runtime_session_ids": _sessions(records),
        "conversation_runtime_session_ids": _sessions(conversation_records),
        "auxiliary_runtime_session_ids": _sessions(auxiliary_records),
        "source_identities": [
            {"commit": commit or None, "tree": tree or None} for commit, tree in source_pairs
        ],
        "provider_usage_aggregate": provider_usage,
        "provider_usage_aggregate_scope": "conversation_only",
        "auxiliary_usage_source": "per-dispatch records",
        "raw_prompt_persisted": False,
        "raw_tool_output_persisted": False,
        "raw_response_persisted": False,
        "canonical_receipt_created": False,
        "canonical_state_mutated": False,
    }
