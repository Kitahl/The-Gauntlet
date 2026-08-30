"""Read-only Gauntlet status and advisory FOIL route adapter."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

ADAPTER_SCHEMA = "gauntlet.adapter.v1"
FOIL_ROUTE_SCHEMA = "gauntlet.foil-route.v1"
LEAN_PREFETCH_SCHEMA = "gauntlet.lean-prefetch.v1"
COMPACT_STATUS_SCHEMA = "gauntlet.compact-status.v1"
MAX_ROUTE_INPUT_BYTES = 131_072
MAX_COMPACT_OBLIGATIONS = 128
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AdapterError(RuntimeError):
    """Typed, fail-closed adapter error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _DuplicateKeyError(ValueError):
    pass


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _configure_imports(root: Path) -> None:
    tools_root = root / "tools"
    required = (
        tools_root / "__init__.py",
        tools_root / "egrt_store.py",
        tools_root / "soul_runtime.py",
        tools_root / "foil_policy.py",
        tools_root / "foil_capabilities.py",
    )
    if not all(path.is_file() for path in required):
        raise AdapterError(
            "GAUNTLET_REPOSITORY_INVALID",
            "Gauntlet authority or FOIL policy files are missing from the repository",
        )

    vendor_root = (root / "vendor" / "hermes-agent").resolve(strict=False)
    retained: list[str] = []
    seen: set[str] = set()
    for entry in sys.path:
        if not entry:
            continue
        resolved = Path(entry).resolve(strict=False)
        if _is_within(resolved, vendor_root):
            continue
        rendered = str(resolved)
        if rendered in seen:
            continue
        seen.add(rendered)
        retained.append(rendered)

    ordered = [str(root), str(tools_root)]
    sys.path[:] = ordered + [entry for entry in retained if entry not in ordered]
    os.environ["PYTHONPATH"] = str(root)
    os.chdir(root)


def _task_id() -> str:
    task_id = os.environ.get("GAUNTLET_TASK_ID", "").strip()
    if not task_id:
        raise AdapterError(
            "TASK_ID_MISSING",
            "GAUNTLET_TASK_ID is required; task identity is never inferred from text",
        )
    if not TASK_ID_PATTERN.fullmatch(task_id) or ".." in task_id:
        raise AdapterError(
            "TASK_ID_INVALID",
            "GAUNTLET_TASK_ID contains unsupported characters",
        )
    return task_id


def _authority_projection() -> dict[str, bool]:
    return {
        "receipt_creation": False,
        "verdict_change": False,
        "obligation_clearance": False,
        "task_release": False,
    }


def _base_document(action: str, task_id: str) -> dict[str, Any]:
    return {
        "schema": ADAPTER_SCHEMA,
        "action": action,
        "task_id": task_id,
        "canonical_source": "egrt.runtime.v1",
        "read_only": True,
        "mutation_performed": False,
        "authority": _authority_projection(),
    }


def _foil_base_document(task_id: str) -> dict[str, Any]:
    return {
        "schema": FOIL_ROUTE_SCHEMA,
        "action": "foil-route",
        "task_id": task_id,
        "canonical_source": "egrt.runtime.v1",
        "status": "OK",
        "mode": "SHADOW",
        "authority_ceiling": "ADAPTATION_ONLY",
        "read_only": True,
        "mutation_performed": False,
        "execution_authorized": False,
        "toolset_narrowing_applied": False,
        "profile_used": False,
        "private_profile_data_transmitted": False,
        "stop_is_advisory": True,
        "authority": _authority_projection(),
    }


def _lean_prefetch_base_document(task_id: str) -> dict[str, Any]:
    return {
        "schema": LEAN_PREFETCH_SCHEMA,
        "action": "lean-prefetch",
        "task_id": task_id,
        "canonical_source": "egrt.runtime.v1",
        "status": "OK",
        "read_only": True,
        "mutation_performed": False,
        "authority": _authority_projection(),
    }


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bind_content_hash(document: dict[str, Any]) -> dict[str, Any]:
    result = dict(document)
    result.pop("content_hash", None)
    result["content_hash"] = _canonical_hash(result)
    return result


def _release_projection(root: Path, task_id: str) -> dict[str, Any]:
    from soul_runtime import release_gate

    verdict, detail = release_gate(root, task_id)
    return {
        "verdict": verdict.value,
        "release_eligible": verdict.value == "CLEARED",
        "detail": detail,
    }


def _task_projection(task: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    detail = release.get("detail")
    gate_rows = detail.get("obligations", []) if isinstance(detail, dict) else []
    states = {
        row.get("obligation_id"): row
        for row in gate_rows
        if isinstance(row, dict) and row.get("obligation_id")
    }
    obligations: list[dict[str, Any]] = []
    for row in task.get("obligations", []):
        if not isinstance(row, dict):
            continue
        obligation_id = str(row.get("obligation_id") or "")
        projected = {
            "obligation_id": obligation_id,
            "kind": row.get("kind"),
            "claim": row.get("claim"),
            "load_bearing": bool(row.get("load_bearing", True)),
            "required_module": row.get("required_module"),
        }
        gate_state = states.get(obligation_id)
        if gate_state is not None:
            projected["release_gate"] = gate_state
        obligations.append(projected)

    return {
        "task_id": task.get("task_id"),
        "goal_hash": task.get("goal_hash"),
        "active": bool(task.get("active", False)),
        "released": bool(task.get("released", False)),
        "schema": task.get("schema"),
        "content_hash": task.get("content_hash"),
        "obligations": obligations,
    }


def _sha256_base64url(value: Any) -> str | None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        return None
    return base64.urlsafe_b64encode(bytes.fromhex(value)).decode("ascii").rstrip("=")


def _gate_states(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    detail = release.get("detail")
    rows = detail.get("obligations", []) if isinstance(detail, dict) else []
    return {
        str(row.get("obligation_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("obligation_id")
    }


def _reason_codes(gate: dict[str, Any] | None) -> list[str]:
    if not isinstance(gate, dict):
        return []
    reason = gate.get("reason")
    return [reason] if isinstance(reason, str) and reason else []


def _receipt_content_hash_hex(
    store: Any,
    gate: dict[str, Any] | None,
) -> str | None:
    if not isinstance(gate, dict):
        return None
    receipt_id = gate.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        return None
    receipt = store.read_receipt(receipt_id, require_integrity=True)
    if not isinstance(receipt, dict):
        return None
    value = receipt.get("content_hash")
    return value if isinstance(value, str) and SHA256_PATTERN.fullmatch(value) else None


def _receipt_content_hash(store: Any, gate: dict[str, Any] | None) -> str | None:
    return _sha256_base64url(_receipt_content_hash_hex(store, gate))


def _compact_status_projection(
    root: Path,
    task: dict[str, Any],
    release: dict[str, Any],
) -> dict[str, Any]:
    """Return a claim-free, bounded canonical status projection."""

    from egrt_store import RuntimeStore

    task_rows = task.get("obligations", [])
    if not isinstance(task_rows, list) or len(task_rows) > MAX_COMPACT_OBLIGATIONS:
        raise AdapterError(
            "COMPACT_STATUS_OBLIGATION_LIMIT",
            f"compact status supports at most {MAX_COMPACT_OBLIGATIONS} obligations",
        )

    states = _gate_states(release)
    store = RuntimeStore(root)
    obligations: list[list[Any]] = []
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        obligation_id = str(row.get("obligation_id") or "")
        gate = states.get(obligation_id)
        if isinstance(gate, dict):
            verdict = str(gate.get("verdict") or "UNKNOWN")
        elif row.get("load_bearing", True) is False:
            verdict = "NOT_LOAD_BEARING"
        else:
            verdict = "UNKNOWN"
        obligations.append(
            [
                obligation_id,
                row.get("kind"),
                row.get("required_module"),
                verdict,
                _reason_codes(gate),
                _sha256_base64url(_canonical_hash(row.get("claim"))),
                _receipt_content_hash(store, gate),
            ]
        )

    verdict_codes = sorted({str(row[3]) for row in obligations})
    reason_code_values = sorted(
        {str(reason) for row in obligations for reason in row[4] if isinstance(reason, str)}
    )
    verdict_indexes = {value: index for index, value in enumerate(verdict_codes)}
    reason_indexes = {value: index for index, value in enumerate(reason_code_values)}
    for row in obligations:
        row[3] = verdict_indexes[str(row[3])]
        row[4] = [reason_indexes[str(reason)] for reason in row[4]]
    release_detail = release.get("detail")
    release_reasons: list[str] = []
    if isinstance(release_detail, dict):
        reason = release_detail.get("reason")
        if isinstance(reason, str) and reason:
            release_reasons.append(reason)
    for gate in states.values():
        for reason in _reason_codes(gate):
            if reason not in release_reasons:
                release_reasons.append(reason)

    document = {
        "schema": COMPACT_STATUS_SCHEMA,
        "task_id": task.get("task_id"),
        "active": bool(task.get("active", False)),
        "released": bool(task.get("released", False)),
        "hash_encoding": "sha256-base64url-no-pad",
        "task_content_hash": _sha256_base64url(task.get("content_hash")),
        "goal_hash": _sha256_base64url(task.get("goal_hash")),
        "release_verdict": release.get("verdict"),
        "release_reason_codes": release_reasons,
        "verdict_codes": verdict_codes,
        "reason_codes": reason_code_values,
        "obligation_fields": [
            "obligation_id",
            "kind",
            "required_module",
            "verdict_index",
            "reason_code_indexes",
            "claim_hash",
            "current_receipt_hash",
        ],
        "obligations": obligations,
    }
    return _bind_content_hash(document)


def _obligation_projection(
    root: Path,
    task: dict[str, Any],
    release: dict[str, Any],
    obligation_id: str,
) -> dict[str, Any]:
    from egrt_store import RuntimeStore

    match = next(
        (
            row
            for row in task.get("obligations", [])
            if isinstance(row, dict) and row.get("obligation_id") == obligation_id
        ),
        None,
    )
    if match is None:
        raise AdapterError(
            "OBLIGATION_NOT_FOUND",
            f"task {task.get('task_id')} has no obligation {obligation_id}",
        )
    gate = _gate_states(release).get(obligation_id)
    store = RuntimeStore(root)
    current_receipt_hash = _receipt_content_hash_hex(store, gate)
    projection = {
        "obligation_id": obligation_id,
        "kind": match.get("kind"),
        "claim": match.get("claim"),
        "claim_hash": _canonical_hash(match.get("claim")),
        "load_bearing": bool(match.get("load_bearing", True)),
        "required_module": match.get("required_module"),
        "task_content_hash": task.get("content_hash"),
        "release_gate": {
            "verdict": gate.get("verdict") if isinstance(gate, dict) else "UNKNOWN",
            "reason_codes": _reason_codes(gate),
            "current_receipt_id": (gate.get("receipt_id") if isinstance(gate, dict) else None),
            "current_receipt_hash": current_receipt_hash,
            "historical_receipt_count": (
                len(gate.get("historical_receipt_ids", []))
                if isinstance(gate, dict)
                and isinstance(gate.get("historical_receipt_ids", []), list)
                else 0
            ),
        },
    }
    return _bind_content_hash(projection)


def _read_task(root: Path, task_id: str) -> dict[str, Any]:
    from egrt_store import RuntimeStore

    task = RuntimeStore(root).read_task(task_id, require_integrity=True)
    if task is None:
        raise AdapterError(
            "TASK_NOT_FOUND",
            f"no integrity-valid canonical task exists for {task_id}",
        )
    if task.get("task_id") != task_id:
        raise AdapterError(
            "TASK_ID_MISMATCH",
            "canonical task identity did not match the requested task",
        )
    content_hash = task.get("content_hash")
    if not isinstance(content_hash, str) or not SHA256_PATTERN.fullmatch(content_hash):
        raise AdapterError(
            "TASK_CONTENT_HASH_INVALID",
            "canonical task omitted a valid content hash",
        )
    return task


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _route_input() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_ROUTE_INPUT_BYTES + 1)
    if len(raw) > MAX_ROUTE_INPUT_BYTES:
        raise AdapterError(
            "FOIL_ROUTE_INPUT_TOO_LARGE",
            "FOIL route input exceeded the bounded adapter limit",
        )
    if not raw:
        raise AdapterError(
            "FOIL_ROUTE_INPUT_MISSING",
            "FOIL route requires one bounded capability-snapshot object on stdin",
        )
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_to_object)
    except UnicodeDecodeError as exc:
        raise AdapterError(
            "FOIL_ROUTE_INPUT_INVALID",
            "FOIL route input must be UTF-8 JSON",
        ) from exc
    except (_DuplicateKeyError, json.JSONDecodeError) as exc:
        raise AdapterError(
            "FOIL_ROUTE_INPUT_INVALID",
            f"FOIL route input is invalid JSON: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise AdapterError(
            "FOIL_ROUTE_INPUT_INVALID",
            "FOIL route input must be a JSON object",
        )

    allowed = {
        "available_capabilities",
        "tool_count",
        "tool_manifest_hash",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise AdapterError(
            "FOIL_ROUTE_INPUT_UNKNOWN_FIELDS",
            "unsupported FOIL route input fields: " + ", ".join(unknown),
        )
    if set(value) != allowed:
        missing = sorted(allowed - set(value))
        raise AdapterError(
            "FOIL_ROUTE_INPUT_MISSING_FIELDS",
            "missing FOIL route input fields: " + ", ".join(missing),
        )

    capabilities = value["available_capabilities"]
    if not isinstance(capabilities, list):
        raise AdapterError(
            "FOIL_ROUTE_CAPABILITIES_INVALID",
            "available_capabilities must be an array",
        )
    if len(capabilities) > 128:
        raise AdapterError(
            "FOIL_ROUTE_CAPABILITIES_INVALID",
            "available_capabilities exceeded the 128-item limit",
        )

    from foil_capabilities import capability_names

    known = set(capability_names())
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(capabilities):
        if not isinstance(item, str) or not item:
            raise AdapterError(
                "FOIL_ROUTE_CAPABILITIES_INVALID",
                f"available_capabilities[{index}] must be a non-empty string",
            )
        name = item.upper()
        if name not in known:
            raise AdapterError(
                "FOIL_ROUTE_CAPABILITY_UNKNOWN",
                f"unknown semantic capability: {name}",
            )
        if name in seen:
            raise AdapterError(
                "FOIL_ROUTE_CAPABILITY_DUPLICATE",
                f"duplicate semantic capability: {name}",
            )
        seen.add(name)
        normalized.append(name)

    tool_count = value["tool_count"]
    if (
        isinstance(tool_count, bool)
        or not isinstance(tool_count, int)
        or tool_count < 0
        or tool_count > 10_000
    ):
        raise AdapterError(
            "FOIL_ROUTE_TOOL_COUNT_INVALID",
            "tool_count must be an integer from 0 through 10000",
        )

    manifest_hash = value["tool_manifest_hash"]
    if not isinstance(manifest_hash, str) or not SHA256_PATTERN.fullmatch(manifest_hash):
        raise AdapterError(
            "FOIL_ROUTE_TOOL_HASH_INVALID",
            "tool_manifest_hash must be a lowercase SHA-256 digest",
        )
    return {
        "available_capabilities": tuple(sorted(normalized)),
        "tool_count": tool_count,
        "tool_manifest_hash": manifest_hash,
    }


_BOOL_CONTEXT_FIELDS = {
    "requires_external_retrieval",
    "freshness_sensitive",
    "closed_book",
    "technical_reasoning",
    "abstract_transformation",
    "closed_context",
    "multi_hop",
    "mixed_tool_task",
    "has_viable_candidate",
    "output_contract_required",
}
_CONTEXT_FIELDS = _BOOL_CONTEXT_FIELDS | {
    "answer_confidence",
    "supplied_example_count",
    "required_complements",
}


def _task_context_metadata(task: dict[str, Any]) -> dict[str, Any]:
    metadata = task.get("metadata")
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise AdapterError(
            "FOIL_TASK_METADATA_INVALID",
            "canonical task metadata must be an object",
        )
    context = metadata.get("foil_task_context", {})
    if context is None:
        return {}
    if not isinstance(context, dict):
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            "metadata.foil_task_context must be an object",
        )
    unknown = sorted(set(context) - _CONTEXT_FIELDS)
    if unknown:
        raise AdapterError(
            "FOIL_TASK_CONTEXT_UNKNOWN_FIELDS",
            "unsupported foil_task_context fields: " + ", ".join(unknown),
        )
    return context


def _strict_bool(context: dict[str, Any], name: str, default: bool) -> bool:
    if name not in context:
        return default
    value = context[name]
    if not isinstance(value, bool):
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            f"foil_task_context.{name} must be a boolean",
        )
    return value


def _strict_confidence(context: dict[str, Any]) -> float:
    value = context.get("answer_confidence", 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            "foil_task_context.answer_confidence must be numeric",
        )
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            "foil_task_context.answer_confidence must be finite and in [0, 1]",
        )
    return result


def _strict_example_count(context: dict[str, Any]) -> int:
    value = context.get("supplied_example_count", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1_000_000:
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            "foil_task_context.supplied_example_count must be from 0 to 1000000",
        )
    return value


def _strict_enum_set(
    context: dict[str, Any],
    name: str,
    enum_type: Any,
) -> frozenset[Any]:
    value = context.get(name, [])
    if not isinstance(value, list):
        raise AdapterError(
            "FOIL_TASK_CONTEXT_INVALID",
            f"foil_task_context.{name} must be an array",
        )
    result: set[Any] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise AdapterError(
                "FOIL_TASK_CONTEXT_INVALID",
                f"foil_task_context.{name}[{index}] must be a string",
            )
        try:
            member = enum_type(item)
        except ValueError as exc:
            raise AdapterError(
                "FOIL_TASK_CONTEXT_INVALID",
                f"foil_task_context.{name}[{index}] is not supported",
            ) from exc
        if member in result:
            raise AdapterError(
                "FOIL_TASK_CONTEXT_INVALID",
                f"foil_task_context.{name} contains a duplicate value",
            )
        result.add(member)
    return frozenset(result)


_DEFAULT_CLAIM_KINDS = {
    "DISCOVERY": "external_fact",
    "PROOF": "logical",
    "SYNTHESIS": "logical",
    "ENGINEERING": "executable",
    "EVALUATION": "numeric",
    "ASSURANCE": "output_contract",
    "PREFLIGHT": "logical",
    "REVIEW": "logical",
    "ADAPTATION": "logical",
    "ADVERSARY": "logical",
}


def _obligation_claim_kind(row: dict[str, Any], claim_kind_type: Any) -> Any:
    metadata = row.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise AdapterError(
            "FOIL_OBLIGATION_METADATA_INVALID",
            "canonical obligation metadata must be an object",
        )
    raw = metadata.get("foil_claim_kind")
    if raw is None:
        raw = _DEFAULT_CLAIM_KINDS.get(str(row.get("kind") or ""), "logical")
    if not isinstance(raw, str):
        raise AdapterError(
            "FOIL_CLAIM_KIND_INVALID",
            "obligation metadata foil_claim_kind must be a string",
        )
    try:
        return claim_kind_type(raw)
    except ValueError as exc:
        raise AdapterError(
            "FOIL_CLAIM_KIND_INVALID",
            f"unsupported FOIL claim kind on obligation {row.get('obligation_id')}",
        ) from exc


def _build_task_context(
    task: dict[str, Any],
    release: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    from foil_policy import (
        ClaimKind,
        ComplementKind,
        LoadBearingUncertainty,
        TaskContext,
    )

    detail = release.get("detail")
    gate_rows = detail.get("obligations", []) if isinstance(detail, dict) else []
    states = {
        str(row.get("obligation_id") or ""): row
        for row in gate_rows
        if isinstance(row, dict) and row.get("obligation_id")
    }

    uncertainties: list[LoadBearingUncertainty] = []
    claim_kinds: set[ClaimKind] = set()
    for row in task.get("obligations", []):
        if not isinstance(row, dict):
            continue
        load_bearing = row.get("load_bearing", True)
        if not isinstance(load_bearing, bool):
            raise AdapterError(
                "FOIL_OBLIGATION_INVALID",
                "canonical obligation load_bearing must be a boolean",
            )
        if not load_bearing:
            continue
        obligation_id = str(row.get("obligation_id") or "")
        if not obligation_id:
            raise AdapterError(
                "FOIL_OBLIGATION_INVALID",
                "load-bearing obligation is missing obligation_id",
            )
        claim_kind = _obligation_claim_kind(row, ClaimKind)
        claim_kinds.add(claim_kind)
        gate = states.get(obligation_id, {})
        resolved = isinstance(gate, dict) and gate.get("verdict") == "CLEARED"
        uncertainties.append(
            LoadBearingUncertainty(
                label=obligation_id,
                claim_kind=claim_kind,
                decisive=True,
                resolved=resolved,
            )
        )

    context = _task_context_metadata(task)
    requires_external = bool(
        claim_kinds.intersection({ClaimKind.EXTERNAL_FACT, ClaimKind.FRESH_FACT})
    )
    freshness_sensitive = ClaimKind.FRESH_FACT in claim_kinds
    output_contract = ClaimKind.OUTPUT_CONTRACT in claim_kinds

    complements = _strict_enum_set(
        context,
        "required_complements",
        ComplementKind,
    )
    task_context = TaskContext(
        requires_external_retrieval=_strict_bool(
            context,
            "requires_external_retrieval",
            requires_external,
        ),
        freshness_sensitive=_strict_bool(
            context,
            "freshness_sensitive",
            freshness_sensitive,
        ),
        closed_book=_strict_bool(context, "closed_book", False),
        technical_reasoning=_strict_bool(
            context,
            "technical_reasoning",
            False,
        ),
        abstract_transformation=_strict_bool(
            context,
            "abstract_transformation",
            False,
        ),
        closed_context=_strict_bool(context, "closed_context", False),
        multi_hop=_strict_bool(context, "multi_hop", False),
        mixed_tool_task=_strict_bool(
            context,
            "mixed_tool_task",
            len(claim_kinds) > 1,
        ),
        has_viable_candidate=_strict_bool(
            context,
            "has_viable_candidate",
            False,
        ),
        answer_confidence=_strict_confidence(context),
        supplied_example_count=_strict_example_count(context),
        output_contract_required=_strict_bool(
            context,
            "output_contract_required",
            output_contract,
        ),
        uncertainties=tuple(uncertainties),
        completed_verifiers=frozenset(),
        required_complements=complements,
    )
    projection = {
        "source": "CANONICAL_TASK_AND_EXPLICIT_FOIL_METADATA",
        "claim_text_transmitted": False,
        "load_bearing_obligation_count": len(uncertainties),
        "claim_kinds": sorted(item.value for item in claim_kinds),
        "explicit_context_fields": sorted(context),
    }
    return task_context, projection


_VERIFIER_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "source_evidence": (
        "WEB_SEARCH",
        "SCHOLARLY_SEARCH",
        "FILES_LIBRARY",
        "REPOSITORY",
    ),
    "current_source": ("WEB_SEARCH",),
    "exact_calculation": ("SYMBOLIC_COMPUTATION", "CODE_EXECUTION"),
    "supplied_example_consistency": ("REASONING", "CODE_EXECUTION"),
    "execution_test": ("CODE_EXECUTION",),
    "contradiction_counterexample": (
        "REASONING",
        "FORMAL_PROOF",
        "SYMBOLIC_COMPUTATION",
    ),
    "output_contract": ("REASONING", "CODE_EXECUTION"),
}

_ACTION_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "prefer_current_source": ("WEB_SEARCH",),
    "reason_closed_book": ("REASONING", "TEXT_GENERATION"),
    "induce_rule": ("REASONING", "TEXT_GENERATION"),
    "check_rule_against_all_examples": ("REASONING", "CODE_EXECUTION"),
    "decompose_supplied_evidence": ("REASONING", "TEXT_GENERATION"),
    "mix_tools_and_reasoning": ("REASONING", "TEXT_GENERATION"),
    "check_output_contract": ("REASONING", "CODE_EXECUTION"),
}

_COMPLEMENT_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "formalization": ("FORMAL_PROOF", "REASONING"),
    "decomposition": ("REASONING",),
    "error_detection": ("REASONING", "CODE_EXECUTION"),
    "evidence_discipline": (
        "WEB_SEARCH",
        "SCHOLARLY_SEARCH",
        "FILES_LIBRARY",
        "REPOSITORY",
    ),
    "causal_reasoning": ("REASONING",),
    "quantitative_check": ("SYMBOLIC_COMPUTATION", "CODE_EXECUTION"),
    "implementation_execution": ("CODE_EXECUTION",),
    "planning_prioritization": ("REASONING",),
    "calibration": ("REASONING",),
    "transfer_adaptation": ("REASONING",),
    "tool_selection": ("REASONING",),
    "uncertainty_management": ("REASONING",),
}


def _capability_requirements(decision: Any) -> list[dict[str, Any]]:
    groups: list[tuple[str, tuple[str, ...]]] = [
        ("model_reasoning", ("REASONING", "TEXT_GENERATION"))
    ]
    groups.extend(
        (f"verifier:{item.value}", _VERIFIER_CAPABILITIES[item.value])
        for item in decision.pending_verifiers
    )
    for action in decision.actions:
        acceptable = _ACTION_CAPABILITIES.get(action.value)
        if acceptable is not None:
            groups.append((f"action:{action.value}", acceptable))
    for complement in sorted(
        decision.task_complements,
        key=lambda item: item.value,
    ):
        acceptable = _COMPLEMENT_CAPABILITIES[complement.value]
        groups.append((f"complement:{complement.value}", acceptable))

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for requirement, acceptable in groups:
        key = (requirement, acceptable)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "requirement": requirement,
                "acceptable_capabilities": list(acceptable),
            }
        )
    return result


def _minimum_bundle(
    requirements: list[dict[str, Any]],
    available: tuple[str, ...],
) -> tuple[list[str], list[dict[str, Any]]]:
    available_set = set(available)
    selected: list[str] = []
    missing: list[dict[str, Any]] = []
    for group in requirements:
        acceptable = group["acceptable_capabilities"]
        chosen = next(
            (item for item in acceptable if item in available_set),
            None,
        )
        if chosen is None:
            missing.append(
                {
                    "requirement": group["requirement"],
                    "acceptable_capabilities": list(acceptable),
                }
            )
        elif chosen not in selected:
            selected.append(chosen)
    return selected, missing


def _foil_route(
    task: dict[str, Any],
    release: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    snapshot_source: str = "RUNTIME_REPORTED_TOOL_DEFINITIONS",
) -> dict[str, Any]:
    from foil_policy import RuntimePolicyV2

    if task.get("active") is not True or task.get("released") is not False:
        raise AdapterError(
            "FOIL_TASK_NOT_ACTIVE",
            "FOIL route requires an active, unreleased canonical task",
        )
    task_context, context_projection = _build_task_context(task, release)
    decision = RuntimePolicyV2().decide(task_context, profile=None)
    requirements = _capability_requirements(decision)
    available = snapshot["available_capabilities"]
    selected, missing = _minimum_bundle(requirements, available)

    document = _foil_base_document(str(task["task_id"]))
    document.update(
        {
            "task_content_hash": task.get("content_hash"),
            "policy_version": RuntimePolicyV2.version,
            "task_context": context_projection,
            "trace": decision.trace(),
            "primary_effort_mode": decision.primary_effort_mode.value,
            "task_complements": sorted(item.value for item in decision.task_complements),
            "targeted_complement": (
                decision.targeted_complement.value
                if decision.targeted_complement is not None
                else None
            ),
            "required_verifiers": [item.value for item in decision.required_verifiers],
            "pending_verifiers": [item.value for item in decision.pending_verifiers],
            "actions": [item.value for item in decision.actions],
            "should_stop": decision.should_stop,
            "stop_reason": decision.stop_reason,
            "resource_allocation": {
                "retrieval_allowed": decision.resource_allocation.retrieval_allowed,
                "search_query_priority": (decision.resource_allocation.search_query_priority),
                "source_followup_priority": (decision.resource_allocation.source_followup_priority),
                "rationale": decision.resource_allocation.rationale,
            },
            "capability_snapshot": {
                "source": snapshot_source,
                "verified_by_gauntlet": False,
                "available": list(available),
                "tool_count": snapshot["tool_count"],
                "tool_manifest_hash": snapshot["tool_manifest_hash"],
            },
            "capability_requirements": requirements,
            "minimum_capability_bundle": selected,
            "capability_bundle_complete": not missing,
            "missing_capabilities": missing,
        }
    )
    return _bind_content_hash(document)


def _lean_prefetch(
    root: Path,
    task: dict[str, Any],
    release: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    route = _foil_route(
        task,
        release,
        snapshot,
        snapshot_source="PARENT_COMPILED_GAUNTLET_STATUS_MANIFEST",
    )
    document = _lean_prefetch_base_document(str(task["task_id"]))
    document["compact_status"] = _compact_status_projection(root, task, release)
    document["foil_route"] = route
    return _bind_content_hash(document)


def _execute(
    root: Path,
    action: str,
    task_id: str,
    obligation_id: str | None = None,
) -> dict[str, Any]:
    task = _read_task(root, task_id)
    release = _release_projection(root, task_id)

    if action == "foil-route":
        return _foil_route(task, release, _route_input())
    if action == "lean-prefetch":
        return _lean_prefetch(root, task, release, _route_input())

    document = _base_document(action, task_id)
    document["status"] = "OK"
    if action == "task-status":
        document["task"] = _task_projection(task, release)
        document["release"] = release
    elif action == "task-status-compact":
        document["compact_status"] = _compact_status_projection(root, task, release)
    elif action == "obligation-get":
        if (
            not isinstance(obligation_id, str)
            or not TASK_ID_PATTERN.fullmatch(obligation_id)
            or ".." in obligation_id
        ):
            raise AdapterError(
                "OBLIGATION_ID_INVALID",
                "--obligation-id must contain a valid obligation identifier",
            )
        document["obligation"] = _obligation_projection(
            root,
            task,
            release,
            obligation_id,
        )
    elif action == "release-status":
        document["task_released"] = bool(task.get("released", False))
        document["release"] = release
    else:
        raise AdapterError(
            "UNSUPPORTED_ACTION",
            f"unsupported read-only adapter action: {action}",
        )
    return document


def _error_document(
    action: str,
    task_id: str,
    exc: AdapterError,
) -> dict[str, Any]:
    if action == "foil-route":
        document = _foil_base_document(task_id)
        document.update(
            {
                "status": "ERROR",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            }
        )
        return _bind_content_hash(document)

    if action == "lean-prefetch":
        document = _lean_prefetch_base_document(task_id)
        document.update(
            {
                "status": "ERROR",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            }
        )
        return _bind_content_hash(document)

    document = _base_document(action, task_id)
    document.update(
        {
            "status": "ERROR",
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        }
    )
    return document


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python gauntlet_host/module_cli.py",
        description=(
            "Read canonical status or compute one proposal-only FOIL route without mutation."
        ),
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "action",
        choices=(
            "task-status",
            "task-status-compact",
            "obligation-get",
            "release-status",
            "foil-route",
            "lean-prefetch",
        ),
    )
    parser.add_argument("--obligation-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve(strict=False)
    task_id = os.environ.get("GAUNTLET_TASK_ID", "").strip() or "unknown"
    try:
        _configure_imports(root)
        task_id = _task_id()
        document = _execute(
            root,
            args.action,
            task_id,
            obligation_id=args.obligation_id,
        )
        exit_code = 0
    except AdapterError as exc:
        document = _error_document(args.action, task_id, exc)
        exit_code = 2
    except Exception as exc:
        document = _error_document(
            args.action,
            task_id,
            AdapterError(
                "ADAPTER_INTERNAL_ERROR",
                "unexpected read-only adapter failure: " + type(exc).__name__,
            ),
        )
        exit_code = 2

    print(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
