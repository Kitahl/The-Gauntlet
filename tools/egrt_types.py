"""Typed runtime contracts for BASTION-01's evidence-control runtime.

This module is intentionally dependency-light so every public runtime component can
share the same state/receipt/verdict vocabulary without importing an agent framework.
Raw prompts and tool outputs are not part of the generic persisted schema.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

SCHEMA_VERSION = "egrt.runtime.v1"


class Verdict(str, Enum):
    CLEARED = "CLEARED"
    ISSUE = "ISSUE"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class SupportMode(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    ASSISTED = "ASSISTED"
    MANUAL = "MANUAL"
    UNAVAILABLE = "UNAVAILABLE"


class ObligationKind(str, Enum):
    PROOF = "PROOF"
    DISCOVERY = "DISCOVERY"
    SYNTHESIS = "SYNTHESIS"
    ENGINEERING = "ENGINEERING"
    EVALUATION = "EVALUATION"
    ASSURANCE = "ASSURANCE"
    PREFLIGHT = "PREFLIGHT"
    REVIEW = "REVIEW"
    ADAPTATION = "ADAPTATION"
    ADVERSARY = "ADVERSARY"


class EvidenceClass(str, Enum):
    PROVEN = "PROVEN"
    MEASURED = "MEASURED"
    CITED = "CITED"
    DERIVED = "DERIVED"
    OBSERVED = "OBSERVED"
    HEURISTIC = "HEURISTIC"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArtifactRef:
    locator: str
    sha256: str | None = None
    version: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class EvidenceRef:
    evidence_class: EvidenceClass
    artifact: ArtifactRef | None = None
    claim: str | None = None
    verifier: str | None = None
    provenance_group: str | None = None
    fresh_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    kind: ObligationKind
    claim: str
    load_bearing: bool = True
    required_module: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    module: str
    obligation_id: str
    verdict: Verdict
    action: str
    input_hash: str
    output_hash: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    verifier: str | None = None
    tool_version: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    unresolved: tuple[str, ...] = ()
    notes: str | None = None
    task_id: str | None = None
    schema: str = SCHEMA_VERSION


@dataclass
class TaskState:
    task_id: str
    goal_hash: str
    obligations: list[Obligation] = field(default_factory=list)
    active: bool = True
    released: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    event_type: str
    component: str
    task_id: str | None
    payload_hash: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION
