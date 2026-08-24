"""Content-addressed protocol contract for FOIL v5 shadow evaluation.

This module validates and seals an evaluation protocol.  It never executes a
model, invokes a tool, or changes a candidate's release state.  In particular,
there are no implicit promotion thresholds: every required gate must be bound
explicitly before the protocol can be sealed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA = "egrt.foil-v5-protocol.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_BINDINGS = frozenset(
    {
        "model_config_sha256",
        "system_prompt_sha256",
        "foil_skill_sha256",
        "task_prompt_sha256",
        "tool_regime_sha256",
        "base_answers_sha256",
        "scanner_sha256",
        "diagnostic_bank_sha256",
        "parser_sha256",
        "applicability_sha256",
    }
)
REQUIRED_PARTITIONS = frozenset({"development", "lock", "prospective"})
REQUIRED_GATES = frozenset(
    {
        "compiler_coverage",
        "compiler_precision",
        "verifier_validity",
        "residual_recall",
        "false_activation_rate",
        "incremental_value",
        "cost_completeness",
        "negative_controls",
    }
)
REQUIRED_EFFECT_CLASSES = frozenset(
    {
        "local",
        "model",
        "tool",
        "network",
        "subprocess",
        "retry",
        "async",
        "profile",
        "router",
        "parser",
    }
)


class ProtocolValidationError(ValueError):
    """The protocol is malformed, incomplete, or no longer content-addressed."""


def canonical_json(value: object) -> str:
    """Return the unique JSON representation used by every v5 content digest."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ProtocolValidationError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_nonempty_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolValidationError(f"{name} must be non-empty text")
    return value


def _require_mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolValidationError(f"{name} must be an object")
    return value


def _validate_binding(protocol: Mapping[str, Any]) -> None:
    _require_nonempty_text("candidate_id", protocol.get("candidate_id"))
    _require_sha256("candidate_sha256", protocol.get("candidate_sha256"))
    bindings = _require_mapping("bindings", protocol.get("bindings"))
    unknown = set(bindings) - REQUIRED_BINDINGS
    if unknown:
        raise ProtocolValidationError(f"bindings contains unknown fields: {sorted(unknown)}")
    missing = REQUIRED_BINDINGS - set(bindings)
    if missing:
        raise ProtocolValidationError(f"bindings missing required fields: {sorted(missing)}")
    for name in REQUIRED_BINDINGS:
        _require_sha256(f"bindings.{name}", bindings[name])


def _validate_partitions(protocol: Mapping[str, Any]) -> None:
    partitions = _require_mapping("partitions", protocol.get("partitions"))
    unknown = set(partitions) - REQUIRED_PARTITIONS
    if unknown:
        raise ProtocolValidationError(f"partitions contains unknown fields: {sorted(unknown)}")
    missing = REQUIRED_PARTITIONS - set(partitions)
    if missing:
        raise ProtocolValidationError(f"partitions missing required fields: {sorted(missing)}")
    observed_ids: set[str] = set()
    for name in sorted(REQUIRED_PARTITIONS):
        row = _require_mapping(f"partitions.{name}", partitions[name])
        _require_sha256(f"partitions.{name}.artifact_sha256", row.get("artifact_sha256"))
        item_ids = row.get("item_ids")
        if not isinstance(item_ids, Sequence) or isinstance(item_ids, (str, bytes)):
            raise ProtocolValidationError(f"partitions.{name}.item_ids must be a non-empty list")
        if not item_ids or any(not isinstance(item, str) or not item for item in item_ids):
            raise ProtocolValidationError(f"partitions.{name}.item_ids must be non-empty text")
        overlap = observed_ids.intersection(item_ids)
        if overlap:
            raise ProtocolValidationError(
                f"partitions must be disjoint; {name} overlaps on {sorted(overlap)}"
            )
        observed_ids.update(item_ids)


def _validate_gates(protocol: Mapping[str, Any]) -> None:
    gates = _require_mapping("gates", protocol.get("gates"))
    unknown = set(gates) - REQUIRED_GATES
    if unknown:
        raise ProtocolValidationError(f"gates contains unknown fields: {sorted(unknown)}")
    missing = REQUIRED_GATES - set(gates)
    if missing:
        raise ProtocolValidationError(f"gates missing required fields: {sorted(missing)}")
    for name in REQUIRED_GATES:
        gate = _require_mapping(f"gates.{name}", gates[name])
        # A candidate must choose its own bound and direction before data lock.
        if gate.get("bound") is None:
            raise ProtocolValidationError(f"gates.{name}.bound cannot be null or defaulted")
        if gate.get("direction") not in {"min", "max", "exact", "required"}:
            raise ProtocolValidationError(f"gates.{name}.direction is invalid")
        _require_nonempty_text(f"gates.{name}.metric", gate.get("metric"))


def _validate_execution_contract(protocol: Mapping[str, Any]) -> None:
    allowed = protocol.get("allowed_effect_classes")
    forbidden = protocol.get("forbidden_effect_classes")
    if not isinstance(allowed, Sequence) or isinstance(allowed, (str, bytes)):
        raise ProtocolValidationError("allowed_effect_classes must be a list")
    if not isinstance(forbidden, Sequence) or isinstance(forbidden, (str, bytes)):
        raise ProtocolValidationError("forbidden_effect_classes must be a list")
    allowed_set, forbidden_set = set(allowed), set(forbidden)
    if not allowed_set.issubset(REQUIRED_EFFECT_CLASSES):
        raise ProtocolValidationError("allowed_effect_classes contains an unknown class")
    if not forbidden_set.issubset(REQUIRED_EFFECT_CLASSES):
        raise ProtocolValidationError("forbidden_effect_classes contains an unknown class")
    if allowed_set.intersection(forbidden_set):
        raise ProtocolValidationError("an effect class cannot be both allowed and forbidden")
    if not forbidden_set:
        raise ProtocolValidationError("forbidden_effect_classes must be explicit")
    taxonomy = protocol.get("no_answer_taxonomy")
    if not isinstance(taxonomy, Sequence) or isinstance(taxonomy, (str, bytes)) or not taxonomy:
        raise ProtocolValidationError("no_answer_taxonomy must be a non-empty list")
    if any(not isinstance(item, str) or not item for item in taxonomy):
        raise ProtocolValidationError("no_answer_taxonomy entries must be non-empty text")
    authority = _require_mapping("authority", protocol.get("authority"))
    for name in ("issuer", "expires_at", "replay_protection", "candidate_id"):
        _require_nonempty_text(f"authority.{name}", authority.get(name))
    if authority["candidate_id"] != protocol["candidate_id"]:
        raise ProtocolValidationError("authority.candidate_id must bind the protocol candidate")


def validate_protocol(protocol: Mapping[str, Any], *, require_seal: bool = False) -> None:
    """Validate a protocol without selecting any threshold or executing any work."""

    if not isinstance(protocol, Mapping):
        raise ProtocolValidationError("protocol must be an object")
    if protocol.get("schema") != SCHEMA:
        raise ProtocolValidationError(f"schema must be {SCHEMA}")
    _validate_binding(protocol)
    _validate_partitions(protocol)
    _validate_gates(protocol)
    _validate_execution_contract(protocol)
    seal = protocol.get("protocol_sha256")
    if require_seal:
        _require_sha256("protocol_sha256", seal)
        unsigned = {key: value for key, value in protocol.items() if key != "protocol_sha256"}
        if content_sha256(unsigned) != seal:
            raise ProtocolValidationError(
                "protocol_sha256 does not match canonical protocol content"
            )
    elif seal is not None:
        _require_sha256("protocol_sha256", seal)


def seal_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached copy with a canonical content seal.

    A previously sealed protocol may be re-sealed only when its existing seal
    already matches.  Thus an edited protocol must receive a new candidate ID.
    """

    candidate = copy.deepcopy(dict(protocol))
    existing = candidate.pop("protocol_sha256", None)
    validate_protocol(candidate)
    digest = content_sha256(candidate)
    if existing is not None and existing != digest:
        raise ProtocolValidationError("cannot re-seal modified content under an existing seal")
    candidate["protocol_sha256"] = digest
    validate_protocol(candidate, require_seal=True)
    return candidate
