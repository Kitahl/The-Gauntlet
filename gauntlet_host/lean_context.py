"""Parent-prefetched, bounded volatile context for the lean Gauntlet profile."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from gauntlet_host import foil_bridge
from gauntlet_host.constants import (
    COMPACT_STATUS_PROTOCOL_VERSION,
    DEFAULT_ADAPTER_TIMEOUT_SECONDS,
    LEAN_PREFETCH_PROTOCOL_VERSION,
    MAX_LEAN_PREFETCH_OUTPUT_BYTES,
    MAX_ROUTE_CAPSULE_CHARS,
    MAX_STATUS_CAPSULE_CHARS,
)
from gauntlet_host.tool_surface import (
    ToolSurfaceError,
    build_tool_surface_plan,
    validate_tool_surface_plan,
)

ACTIVE_MANIFEST_REVISION = "gauntlet-status.v1"
LEAN_CONTEXT_SCHEMA = "gauntlet.lean-context.v1"
SPARSE_CONTEXT_SCHEMA = "gauntlet.sparse-context-plan.v1"
SPARSE_CONTEXT_ENGINE = "gauntlet-sparse"
LEAN_PROFILE_NAME = "gauntlet-lean.v1"
SPARSE_ACTIVATION_HISTORY_CHARS = 8_192
SPARSE_RECENT_TURNS = 3
SPARSE_RETRIEVAL_TOP_K = 3
SPARSE_MAX_SELECTED_MESSAGES = 18
MAX_JIT_SNIPPETS = 8
MAX_JIT_SNIPPET_CHARS = 4_000
MAX_JIT_CONTEXT_CHARS = 12_000
_CONTEXT_MARKER = "[GAUNTLET LEAN VOLATILE CONTEXT]"
_CONTEXT_END_MARKER = "[/GAUNTLET LEAN VOLATILE CONTEXT]"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_B64_SHA256_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_OBLIGATION_FIELDS = [
    "obligation_id",
    "kind",
    "required_module",
    "verdict_index",
    "reason_code_indexes",
    "claim_hash",
    "current_receipt_hash",
]

_COMPACT_DESCRIPTION = (
    "Refresh compact canonical status for the exact host-bound task. Read-only; "
    "returns IDs, kinds, required modules, verdicts, reason codes, and hashes."
)
_OBLIGATION_DESCRIPTION = (
    "Read exact canonical detail for one obligation ID, including its claim and "
    "current release row. Read-only and bounded to one obligation."
)
_RELEASE_DESCRIPTION = (
    "Refresh Soul release-gate status for the exact host-bound task. This reports "
    "eligibility only and performs no mutation."
)


class LeanContextError(RuntimeError):
    """Typed failure while preparing or validating lean runtime context."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _zero_argument_tool(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }


def status_tool_definitions() -> list[dict[str, Any]]:
    """Return the frozen model-visible manifest for gauntlet-lean.v1."""

    obligation = {
        "type": "function",
        "function": {
            "name": "gauntlet_obligation_get",
            "description": _OBLIGATION_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "obligation_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 256,
                    }
                },
                "required": ["obligation_id"],
                "additionalProperties": False,
            },
        },
    }
    return [
        _zero_argument_tool(
            "gauntlet_task_status_compact",
            _COMPACT_DESCRIPTION,
        ),
        obligation,
        _zero_argument_tool(
            "gauntlet_release_status",
            _RELEASE_DESCRIPTION,
        ),
    ]


def active_manifest_hash() -> str:
    return foil_bridge.capability_snapshot(status_tool_definitions())["tool_manifest_hash"]


def _validate_jit_snippet(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise LeanContextError("JIT_CONTEXT_INVALID", "JIT context snippet must be an object")
    if set(value) != {
        "snippet_id",
        "kind",
        "provenance",
        "source_hash",
        "content",
        "authority",
    }:
        raise LeanContextError(
            "JIT_CONTEXT_INVALID",
            "JIT context snippet fields did not match the frozen contract",
        )
    snippet_id = value.get("snippet_id")
    kind = value.get("kind")
    provenance = value.get("provenance")
    source_hash = value.get("source_hash")
    content = value.get("content")
    if not isinstance(snippet_id, str) or not _IDENTIFIER_PATTERN.fullmatch(snippet_id):
        raise LeanContextError("JIT_CONTEXT_INVALID", "JIT snippet ID is invalid")
    if kind not in {"skill", "memory", "profile"}:
        raise LeanContextError("JIT_CONTEXT_INVALID", "JIT snippet kind is unsupported")
    if (
        not isinstance(provenance, str)
        or not provenance.strip()
        or len(provenance) > 512
        or any(char in provenance for char in "\r\n")
    ):
        raise LeanContextError("JIT_CONTEXT_INVALID", "JIT snippet provenance is invalid")
    if not isinstance(content, str) or not content or len(content) > MAX_JIT_SNIPPET_CHARS:
        raise LeanContextError("JIT_CONTEXT_INVALID", "JIT snippet content is invalid")
    if _CONTEXT_MARKER in content or _CONTEXT_END_MARKER in content:
        raise LeanContextError("JIT_CONTEXT_MARKER_COLLISION", "JIT snippet used a reserved marker")
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if source_hash != expected_hash:
        raise LeanContextError(
            "JIT_CONTEXT_HASH_MISMATCH",
            "JIT snippet source hash did not match its content",
        )
    if value.get("authority") != "CONTEXT_ONLY":
        raise LeanContextError(
            "JIT_CONTEXT_AUTHORITY_INVALID",
            "JIT snippets cannot claim canonical or execution authority",
        )
    return {
        "snippet_id": snippet_id,
        "kind": kind,
        "provenance": provenance.strip(),
        "source_hash": source_hash,
        "content": content,
        "authority": "CONTEXT_ONLY",
    }


def build_sparse_context_plan(
    *,
    session_binding_id: str,
    profile_name: str,
    selected_snippets: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    if not isinstance(session_binding_id, str) or not session_binding_id:
        raise LeanContextError(
            "SPARSE_CONTEXT_BINDING_MISSING",
            "sparse context requires the parent-derived session binding",
        )
    if profile_name != LEAN_PROFILE_NAME:
        raise LeanContextError(
            "SPARSE_CONTEXT_PROFILE_INVALID",
            "sparse context requires the isolated lean runtime profile",
        )
    if len(selected_snippets) > MAX_JIT_SNIPPETS:
        raise LeanContextError("JIT_CONTEXT_TOO_LARGE", "too many JIT context snippets")
    snippets = [_validate_jit_snippet(value) for value in selected_snippets]
    ids = [snippet["snippet_id"] for snippet in snippets]
    if len(ids) != len(set(ids)):
        raise LeanContextError("JIT_CONTEXT_DUPLICATE", "JIT snippet IDs must be unique")
    if sum(len(snippet["content"]) for snippet in snippets) > MAX_JIT_CONTEXT_CHARS:
        raise LeanContextError("JIT_CONTEXT_TOO_LARGE", "JIT context exceeded its total bound")
    payload = {
        "schema": SPARSE_CONTEXT_SCHEMA,
        "engine": SPARSE_CONTEXT_ENGINE,
        "task_binding_id": session_binding_id,
        "profile_name": profile_name,
        "activation_history_chars": SPARSE_ACTIVATION_HISTORY_CHARS,
        "recent_turns": SPARSE_RECENT_TURNS,
        "retrieval_top_k": SPARSE_RETRIEVAL_TOP_K,
        "max_selected_messages": SPARSE_MAX_SELECTED_MESSAGES,
        "selected_snippets": snippets,
        "persisted_transcript_mutation_allowed": False,
        "snippet_authority_allowed": False,
    }
    payload["content_hash"] = _canonical_hash(payload)
    return payload


def validate_sparse_context_plan(
    value: Any,
    *,
    session_binding_id: str,
    profile_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SPARSE_CONTEXT_SCHEMA:
        raise LeanContextError(
            "SPARSE_CONTEXT_PLAN_MISSING",
            "worker request omitted the sparse context plan",
        )
    supplied_hash = value.get("content_hash")
    if not isinstance(supplied_hash, str) or not _SHA256_PATTERN.fullmatch(supplied_hash):
        raise LeanContextError(
            "SPARSE_CONTEXT_HASH_INVALID",
            "sparse context plan omitted a valid content hash",
        )
    payload = dict(value)
    payload.pop("content_hash", None)
    if _canonical_hash(payload) != supplied_hash:
        raise LeanContextError(
            "SPARSE_CONTEXT_HASH_MISMATCH",
            "sparse context plan content hash did not match its payload",
        )
    if (
        value.get("engine") != SPARSE_CONTEXT_ENGINE
        or value.get("task_binding_id") != session_binding_id
        or value.get("profile_name") != profile_name
    ):
        raise LeanContextError(
            "SPARSE_CONTEXT_ISOLATION_MISMATCH",
            "sparse context plan did not match the task binding and runtime profile",
        )
    expected_scalars = {
        "activation_history_chars": SPARSE_ACTIVATION_HISTORY_CHARS,
        "recent_turns": SPARSE_RECENT_TURNS,
        "retrieval_top_k": SPARSE_RETRIEVAL_TOP_K,
        "max_selected_messages": SPARSE_MAX_SELECTED_MESSAGES,
        "persisted_transcript_mutation_allowed": False,
        "snippet_authority_allowed": False,
    }
    if any(value.get(key) != expected for key, expected in expected_scalars.items()):
        raise LeanContextError(
            "SPARSE_CONTEXT_POLICY_MISMATCH",
            "sparse context plan changed a frozen selection policy field",
        )
    snippets = value.get("selected_snippets")
    if not isinstance(snippets, list) or len(snippets) > MAX_JIT_SNIPPETS:
        raise LeanContextError("JIT_CONTEXT_INVALID", "selected JIT context is invalid")
    validated = [_validate_jit_snippet(item) for item in snippets]
    ids = [snippet["snippet_id"] for snippet in validated]
    if (
        len(ids) != len(set(ids))
        or sum(len(item["content"]) for item in validated) > MAX_JIT_CONTEXT_CHARS
    ):
        raise LeanContextError("JIT_CONTEXT_INVALID", "selected JIT context is invalid")
    return value


def _validate_content_hash(value: dict[str, Any], *, label: str) -> None:
    supplied = value.get("content_hash")
    if not isinstance(supplied, str) or not _SHA256_PATTERN.fullmatch(supplied):
        raise LeanContextError(
            f"{label}_CONTENT_HASH_INVALID",
            f"{label} omitted a valid content hash",
        )
    payload = dict(value)
    payload.pop("content_hash", None)
    if _canonical_hash(payload) != supplied:
        raise LeanContextError(
            f"{label}_CONTENT_HASH_MISMATCH",
            f"{label} content hash did not match its payload",
        )


def _contains_exact_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_exact_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_exact_key(item, key) for item in value)
    return False


def _validate_compact_status(task_id: str, status: Any) -> dict[str, Any]:
    if not isinstance(status, dict):
        raise LeanContextError(
            "COMPACT_STATUS_INVALID",
            "compact status must be a JSON object",
        )
    if status.get("schema") != COMPACT_STATUS_PROTOCOL_VERSION:
        raise LeanContextError(
            "COMPACT_STATUS_SCHEMA_MISMATCH",
            f"compact status schema must be {COMPACT_STATUS_PROTOCOL_VERSION}",
        )
    if status.get("task_id") != task_id:
        raise LeanContextError(
            "COMPACT_STATUS_CORRELATION_MISMATCH",
            "compact status did not match the host-bound task",
        )
    if _contains_exact_key(status, "claim"):
        raise LeanContextError(
            "COMPACT_STATUS_CLAIM_LEAK",
            "compact status contained exact claim text",
        )
    if status.get("obligation_fields") != _OBLIGATION_FIELDS:
        raise LeanContextError(
            "COMPACT_STATUS_FIELDS_INVALID",
            "compact status obligation field order is not recognized",
        )
    verdict_codes = status.get("verdict_codes")
    reason_codes = status.get("reason_codes")
    if (
        not isinstance(verdict_codes, list)
        or not all(isinstance(item, str) and item for item in verdict_codes)
        or not isinstance(reason_codes, list)
        or not all(isinstance(item, str) and item for item in reason_codes)
    ):
        raise LeanContextError(
            "COMPACT_STATUS_CODEBOOK_INVALID",
            "compact status verdict/reason codebooks are invalid",
        )
    obligations = status.get("obligations")
    if not isinstance(obligations, list) or len(obligations) > 128:
        raise LeanContextError(
            "COMPACT_STATUS_OBLIGATIONS_INVALID",
            "compact status obligations must be an array of at most 128 rows",
        )
    for index, row in enumerate(obligations):
        if not isinstance(row, list) or len(row) != len(_OBLIGATION_FIELDS):
            raise LeanContextError(
                "COMPACT_STATUS_ROW_INVALID",
                f"compact status obligation row {index} is malformed",
            )
        if not isinstance(row[0], str) or not row[0]:
            raise LeanContextError(
                "COMPACT_STATUS_ROW_INVALID",
                f"compact status obligation row {index} omitted its ID",
            )
        if (
            isinstance(row[3], bool)
            or not isinstance(row[3], int)
            or not 0 <= row[3] < len(verdict_codes)
            or not isinstance(row[4], list)
            or any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or not 0 <= item < len(reason_codes)
                for item in row[4]
            )
        ):
            raise LeanContextError(
                "COMPACT_STATUS_ROW_INVALID",
                f"compact status obligation row {index} has invalid code indexes",
            )
        for digest_index in (5, 6):
            digest = row[digest_index]
            if digest is not None and (
                not isinstance(digest, str) or not _B64_SHA256_PATTERN.fullmatch(digest)
            ):
                raise LeanContextError(
                    "COMPACT_STATUS_HASH_INVALID",
                    f"compact status obligation row {index} has an invalid hash",
                )
    _validate_content_hash(status, label="COMPACT_STATUS")
    return status


def _validate_prefetch(
    task_id: str,
    value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise LeanContextError(
            "LEAN_PREFETCH_PROTOCOL_ERROR",
            "lean prefetch result must be a JSON object",
        )
    if value.get("schema") != LEAN_PREFETCH_PROTOCOL_VERSION:
        raise LeanContextError(
            "LEAN_PREFETCH_SCHEMA_MISMATCH",
            f"lean prefetch schema must be {LEAN_PREFETCH_PROTOCOL_VERSION}",
        )
    if value.get("action") != "lean-prefetch" or value.get("task_id") != task_id:
        raise LeanContextError(
            "LEAN_PREFETCH_CORRELATION_MISMATCH",
            "lean prefetch did not match the host-bound task",
        )
    if value.get("read_only") is not True or value.get("mutation_performed") is not False:
        raise LeanContextError(
            "LEAN_PREFETCH_AUTHORITY_VIOLATION",
            "lean prefetch was not a read-only operation",
        )
    authority = value.get("authority")
    if not isinstance(authority, dict) or any(item is not False for item in authority.values()):
        raise LeanContextError(
            "LEAN_PREFETCH_AUTHORITY_VIOLATION",
            "lean prefetch claimed canonical authority",
        )
    _validate_content_hash(value, label="LEAN_PREFETCH")
    route = value.get("foil_route")
    if not isinstance(route, dict):
        raise LeanContextError(
            "LEAN_PREFETCH_ROUTE_INVALID",
            "lean prefetch omitted its full FOIL route",
        )
    try:
        route = foil_bridge.validate_advisory_route(task_id, route)
    except foil_bridge.FoilRouteBridgeError as exc:
        raise LeanContextError(exc.code, exc.message) from exc
    status = _validate_compact_status(task_id, value.get("compact_status"))
    return route, status


def _adapter_environment(task_id: str, repository_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["GAUNTLET_TASK_ID"] = task_id
    environment["PYTHONPATH"] = str(repository_root)
    environment["PYTHONUNBUFFERED"] = "1"
    for name in (
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_INTERACTIVE",
    ):
        environment.pop(name, None)
    return environment


def _write_route_record(runtime_home: Path, route: dict[str, Any]) -> Path:
    route_hash = str(route["content_hash"])
    root = runtime_home / "operational" / "foil-routes"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    destination = root / f"{route_hash}.json"
    content = _canonical_json(route) + "\n"
    if destination.exists():
        try:
            if destination.read_text(encoding="utf-8") != content:
                raise LeanContextError(
                    "FOIL_ROUTE_RECORD_COLLISION",
                    "existing operational route record did not match its content hash",
                )
        except OSError as exc:
            raise LeanContextError(
                "FOIL_ROUTE_RECORD_UNREADABLE",
                "cannot read the existing operational route record",
            ) from exc
        return destination

    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise LeanContextError(
            "FOIL_ROUTE_RECORD_WRITE_FAILED",
            "cannot persist the operational FOIL route record",
        ) from exc
    return destination


@dataclass(frozen=True, slots=True)
class LeanContext:
    task_id: str
    active_manifest_revision: str
    active_manifest_hash: str
    foil_route: dict[str, Any]
    compact_status: dict[str, Any]
    route_record_path: str
    tool_surface_plan: dict[str, Any] | None = None
    sparse_context_plan: dict[str, Any] | None = None

    def to_metadata(
        self,
        *,
        session_binding_id: str,
        profile_name: str = LEAN_PROFILE_NAME,
        selected_snippets: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        try:
            tool_plan = build_tool_surface_plan(
                status_tool_definitions(),
                self.foil_route,
            )
        except ToolSurfaceError as exc:
            raise LeanContextError(exc.code, exc.message) from exc
        if tool_plan["planned_manifest_hash"] != self.active_manifest_hash:
            raise LeanContextError(
                "ACTIVE_MANIFEST_HASH_MISMATCH",
                "tool-surface plan did not match the frozen active manifest",
            )
        sparse_plan = build_sparse_context_plan(
            session_binding_id=session_binding_id,
            profile_name=profile_name,
            selected_snippets=selected_snippets,
        )
        return {
            "schema": LEAN_CONTEXT_SCHEMA,
            "task_id": self.task_id,
            "active_manifest_revision": self.active_manifest_revision,
            "active_manifest_hash": self.active_manifest_hash,
            "foil_route": self.foil_route,
            "compact_status": self.compact_status,
            "tool_surface_plan": tool_plan,
            "sparse_context_plan": sparse_plan,
            "route_record": {
                "path": self.route_record_path,
                "content_hash": self.foil_route["content_hash"],
                "private": True,
                "canonical_evidence": False,
            },
        }

    @classmethod
    def from_metadata(
        cls,
        task_id: str,
        value: Any,
        *,
        session_binding_id: str,
        profile_name: str,
    ) -> "LeanContext":
        if not isinstance(value, dict) or value.get("schema") != LEAN_CONTEXT_SCHEMA:
            raise LeanContextError(
                "LEAN_CONTEXT_MISSING",
                "worker request omitted the parent-prefetched lean context",
            )
        if value.get("task_id") != task_id:
            raise LeanContextError(
                "LEAN_CONTEXT_CORRELATION_MISMATCH",
                "lean context did not match the host-bound task",
            )
        if value.get("active_manifest_revision") != ACTIVE_MANIFEST_REVISION:
            raise LeanContextError(
                "ACTIVE_MANIFEST_REVISION_MISMATCH",
                "lean context active manifest revision is not supported",
            )
        expected_manifest_hash = active_manifest_hash()
        if value.get("active_manifest_hash") != expected_manifest_hash:
            raise LeanContextError(
                "ACTIVE_MANIFEST_HASH_MISMATCH",
                "lean context active manifest hash is not current",
            )
        route = value.get("foil_route")
        try:
            route = foil_bridge.validate_advisory_route(task_id, route)
        except (TypeError, foil_bridge.FoilRouteBridgeError) as exc:
            if isinstance(exc, foil_bridge.FoilRouteBridgeError):
                raise LeanContextError(exc.code, exc.message) from exc
            raise LeanContextError(
                "LEAN_CONTEXT_ROUTE_INVALID",
                "lean context FOIL route is invalid",
            ) from exc
        status = _validate_compact_status(task_id, value.get("compact_status"))
        try:
            tool_plan = validate_tool_surface_plan(value.get("tool_surface_plan"))
        except ToolSurfaceError as exc:
            raise LeanContextError(exc.code, exc.message) from exc
        if (
            tool_plan.get("foil_proposal_hash") != route["content_hash"]
            or tool_plan.get("foil_selected_capability_ids")
            != list(route.get("minimum_capability_bundle", []))
            or tool_plan.get("planned_manifest_hash") != expected_manifest_hash
        ):
            raise LeanContextError(
                "TOOL_SURFACE_ROUTE_MISMATCH",
                "tool-surface plan did not bind the validated FOIL proposal and manifest",
            )
        sparse_plan = validate_sparse_context_plan(
            value.get("sparse_context_plan"),
            session_binding_id=session_binding_id,
            profile_name=profile_name,
        )
        record = value.get("route_record")
        if (
            not isinstance(record, dict)
            or record.get("content_hash") != route["content_hash"]
            or record.get("private") is not True
            or record.get("canonical_evidence") is not False
            or not isinstance(record.get("path"), str)
        ):
            raise LeanContextError(
                "LEAN_CONTEXT_RECORD_INVALID",
                "lean context route record reference is invalid",
            )
        return cls(
            task_id=task_id,
            active_manifest_revision=ACTIVE_MANIFEST_REVISION,
            active_manifest_hash=expected_manifest_hash,
            foil_route=route,
            compact_status=status,
            route_record_path=record["path"],
            tool_surface_plan=tool_plan,
            sparse_context_plan=sparse_plan,
        )

    def route_capsule(self) -> dict[str, Any]:
        missing: list[str] = []
        for row in self.foil_route.get("missing_capabilities", []):
            if not isinstance(row, dict):
                continue
            for capability in row.get("acceptable_capabilities", []):
                if isinstance(capability, str) and capability not in missing:
                    missing.append(capability)
        return {
            "route_hash": self.foil_route["content_hash"],
            "route_revision": self.foil_route["policy_version"],
            "primary_mode": self.foil_route["primary_effort_mode"],
            "selected_capability_ids": self.foil_route["minimum_capability_bundle"],
            "required_verifier_ids": self.foil_route["required_verifiers"],
            "missing_capability_ids": missing,
            "should_stop": self.foil_route["should_stop"],
        }

    def capsule_metrics(self) -> dict[str, int]:
        route_chars = len(_canonical_json(self.route_capsule()))
        status_chars = len(_canonical_json(self.compact_status))
        return {
            "route_chars": route_chars,
            "route_estimated_tokens": math.ceil(route_chars / 4),
            "status_chars": status_chars,
            "status_estimated_tokens": math.ceil(status_chars / 4),
        }

    def instruction(self) -> str:
        route_text = _canonical_json(self.route_capsule())
        status_text = _canonical_json(self.compact_status)
        if len(route_text) > MAX_ROUTE_CAPSULE_CHARS:
            raise LeanContextError(
                "FOIL_ROUTE_CAPSULE_TOO_LARGE",
                "compact FOIL route exceeded its bounded prompt allowance",
            )
        if len(status_text) > MAX_STATUS_CAPSULE_CHARS:
            raise LeanContextError(
                "COMPACT_STATUS_CAPSULE_TOO_LARGE",
                "compact canonical status exceeded its bounded prompt allowance",
            )
        return (
            _CONTEXT_MARKER
            + "\nParent-prefetched canonical status is current for this turn. "
            + "Use status tools only to refresh; use gauntlet_obligation_get only "
            + "when one exact claim is required. required_module is deterministic "
            + "host routing. The FOIL route is advisory and has no canonical authority.\n"
            + "route="
            + route_text
            + "\nstatus="
            + status_text
            + "\n"
            + _CONTEXT_END_MARKER
        )

    def inject(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise LeanContextError(
                "LEAN_CONTEXT_PROMPT_INVALID",
                "lean context requires a non-empty prompt",
            )
        if _CONTEXT_MARKER in prompt or _CONTEXT_END_MARKER in prompt:
            raise LeanContextError(
                "LEAN_CONTEXT_PROMPT_COLLISION",
                "runtime prompt contains a reserved lean-context marker",
            )
        return prompt + "\n\n" + self.instruction()


def drop_stale_lean_context_sidecars(history: Any) -> int:
    """Drop only prior API sidecars that exactly wrap a clean lean-runtime turn."""

    if not isinstance(history, list):
        return 0
    dropped = 0
    for message in history:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        sidecar = message.get("api_content")
        if not isinstance(content, str) or not isinstance(sidecar, str):
            continue
        expected_prefix = content + "\n\n" + _CONTEXT_MARKER + "\n"
        if sidecar.startswith(expected_prefix) and sidecar.endswith(_CONTEXT_END_MARKER):
            message.pop("api_content", None)
            dropped += 1
    return dropped


def prefetch_lean_context(
    *,
    task_id: str,
    repository_root: Path,
    runtime_home: Path,
    timeout_seconds: float = DEFAULT_ADAPTER_TIMEOUT_SECONDS,
) -> LeanContext:
    """Fetch compact status and the full advisory route in one parent call."""

    root = repository_root.expanduser().resolve(strict=False)
    adapter = (root / "gauntlet_host" / "module_cli.py").resolve(strict=False)
    if not adapter.is_file():
        raise LeanContextError(
            "LEAN_PREFETCH_ADAPTER_MISSING",
            "lean prefetch adapter is missing from the active repository",
        )
    snapshot = foil_bridge.capability_snapshot(status_tool_definitions())
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(adapter),
                "--root",
                str(root),
                "lean-prefetch",
            ],
            input=_canonical_json(snapshot),
            cwd=root,
            env=_adapter_environment(task_id, root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LeanContextError(
            "LEAN_PREFETCH_TIMEOUT",
            "lean prefetch adapter exceeded its bounded timeout",
        ) from exc
    except OSError as exc:
        raise LeanContextError(
            "LEAN_PREFETCH_START_FAILED",
            "lean prefetch adapter could not start",
        ) from exc

    if len(completed.stdout.encode("utf-8")) > MAX_LEAN_PREFETCH_OUTPUT_BYTES:
        raise LeanContextError(
            "LEAN_PREFETCH_OUTPUT_TOO_LARGE",
            "lean prefetch adapter exceeded its bounded output limit",
        )
    records = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise LeanContextError(
            "LEAN_PREFETCH_PROTOCOL_ERROR",
            "lean prefetch adapter must return exactly one JSON record",
        )
    try:
        value = json.loads(records[0])
    except json.JSONDecodeError as exc:
        raise LeanContextError(
            "LEAN_PREFETCH_PROTOCOL_ERROR",
            "lean prefetch adapter returned invalid JSON",
        ) from exc
    expected_exit = 0 if isinstance(value, dict) and value.get("status") == "OK" else 2
    if completed.returncode != expected_exit:
        raise LeanContextError(
            "LEAN_PREFETCH_EXIT_MISMATCH",
            "lean prefetch adapter status and exit code did not agree",
        )
    if expected_exit != 0:
        error = value.get("error") if isinstance(value, dict) else None
        code = (
            str(error.get("code") or "LEAN_PREFETCH_UNAVAILABLE")
            if isinstance(error, dict)
            else "LEAN_PREFETCH_UNAVAILABLE"
        )
        message = (
            str(error.get("message") or "lean prefetch unavailable")
            if isinstance(error, dict)
            else "lean prefetch unavailable"
        )
        raise LeanContextError(code, message)

    route, status = _validate_prefetch(task_id, value)
    destination = _write_route_record(runtime_home.resolve(strict=False), route)
    context = LeanContext(
        task_id=task_id,
        active_manifest_revision=ACTIVE_MANIFEST_REVISION,
        active_manifest_hash=snapshot["tool_manifest_hash"],
        foil_route=route,
        compact_status=status,
        route_record_path=str(destination),
    )
    context.instruction()
    return context
