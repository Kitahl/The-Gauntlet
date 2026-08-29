"""Neutral, additive challenge contracts for the EGR typed runtime.

The challenge schema is deliberately separate from ``egrt.runtime.v1``. A challenge
is a proposal about a bound candidate; it is not evidence and cannot satisfy the
underlying domain obligation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from egrt_types import ArtifactRef

SCHEMA_VERSION = "egrt.challenge.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ChallengeOrigin(str, Enum):
    USER = "USER"
    MODULE_NATIVE = "MODULE_NATIVE"
    FOIL = "FOIL"
    GAUNTLET = "GAUNTLET"
    COUNCIL = "COUNCIL"


class ChallengeKind(str, Enum):
    ALTERNATE_FORMALIZATION = "ALTERNATE_FORMALIZATION"
    CLAIM_NEGATION = "CLAIM_NEGATION"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    ASSUMPTION_KNOCKOUT = "ASSUMPTION_KNOCKOUT"
    REPRESENTATION_SWAP = "REPRESENTATION_SWAP"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    RETRIEVAL_REFRAME = "RETRIEVAL_REFRAME"
    NOVELTY_COSTUME = "NOVELTY_COSTUME"
    COMPETING_MECHANISM = "COMPETING_MECHANISM"
    MINIMUM_DISCRIMINATOR = "MINIMUM_DISCRIMINATOR"
    FAILURE_CLASS = "FAILURE_CLASS"
    METAMORPHIC_RELATION = "METAMORPHIC_RELATION"
    BASELINE_OR_ESTIMAND = "BASELINE_OR_ESTIMAND"
    CONTAMINATION = "CONTAMINATION"
    STATE_DRIFT = "STATE_DRIFT"
    DECISION_REVERSAL = "DECISION_REVERSAL"
    REVIEW_DIVERSITY = "REVIEW_DIVERSITY"
    OUTPUT_CONTRACT = "OUTPUT_CONTRACT"


class ChallengeState(str, Enum):
    PROPOSED = "PROPOSED"
    SELECTED = "SELECTED"
    RUNNING = "RUNNING"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    UNAVAILABLE = "UNAVAILABLE"
    DISMISSED_NOT_APPLICABLE = "DISMISSED_NOT_APPLICABLE"


class ResolutionOutcome(str, Enum):
    SUPPORTS_BASE = "SUPPORTS_BASE"
    REFUTES_BASE = "REFUTES_BASE"
    SCOPE_SPLIT = "SCOPE_SPLIT"
    INCONCLUSIVE = "INCONCLUSIVE"


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_optional_text(name: str, value: object) -> None:
    if value is not None:
        _require_text(name, value)


def _require_hash(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _require_rank(name: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int or None")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_mapping(name: str, value: object) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be dict")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be str")


@dataclass(frozen=True)
class ChallengeRequest:
    challenge_id: str
    task_id: str
    obligation_id: str
    target_module: str
    origin: ChallengeOrigin
    kind: ChallengeKind
    hypothesis: str
    alternative: str | None
    refuter: str
    consequence_if_true: str
    load_bearing: bool
    required_capability: str | None
    candidate_hash: str
    scope_hash: str
    obligation_set_hash: str
    proposer: str
    proposer_provenance: str | None = None
    information_rank: int | None = None
    risk_rank: int | None = None
    cost_rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "challenge_id", "task_id", "obligation_id", "target_module",
            "hypothesis", "refuter", "consequence_if_true", "proposer",
        ):
            _require_text(name, getattr(self, name))
        if not isinstance(self.origin, ChallengeOrigin):
            raise TypeError("origin must be ChallengeOrigin")
        if not isinstance(self.kind, ChallengeKind):
            raise TypeError("kind must be ChallengeKind")
        if not isinstance(self.load_bearing, bool):
            raise TypeError("load_bearing must be bool")
        for name in ("alternative", "required_capability", "proposer_provenance"):
            _require_optional_text(name, getattr(self, name))
        for name in ("candidate_hash", "scope_hash", "obligation_set_hash"):
            _require_hash(name, getattr(self, name))
        for name in ("information_rank", "risk_rank", "cost_rank"):
            _require_rank(name, getattr(self, name))
        _require_mapping("metadata", self.metadata)
        if self.schema != SCHEMA_VERSION:
            raise ValueError(f"schema must be {SCHEMA_VERSION}")


@dataclass(frozen=True)
class DiscriminatorPlan:
    plan_id: str
    challenge_id: str
    mode: str
    action: str
    verifier_module: str
    required_capability: str | None
    expected_support_signal: str
    expected_refute_signal: str
    input_artifacts: tuple[ArtifactRef, ...] = ()
    timeout_seconds: int | None = None
    max_cost_rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "plan_id", "challenge_id", "mode", "action", "verifier_module",
            "expected_support_signal", "expected_refute_signal",
        ):
            _require_text(name, getattr(self, name))
        _require_optional_text("required_capability", self.required_capability)
        if not isinstance(self.input_artifacts, tuple):
            raise TypeError("input_artifacts must be tuple")
        if any(not isinstance(item, ArtifactRef) for item in self.input_artifacts):
            raise TypeError("input_artifacts must contain ArtifactRef values")
        _require_rank("max_cost_rank", self.max_cost_rank)
        if self.timeout_seconds is not None:
            if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int):
                raise TypeError("timeout_seconds must be int or None")
            if self.timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be positive")
        _require_mapping("metadata", self.metadata)
        if self.schema != SCHEMA_VERSION:
            raise ValueError(f"schema must be {SCHEMA_VERSION}")


@dataclass(frozen=True)
class ChallengeResolution:
    resolution_id: str
    challenge_id: str
    state: ChallengeState
    outcome: ResolutionOutcome
    verifier_receipt_id: str | None
    verifier_module: str | None
    evidence_hash: str | None
    candidate_hash: str
    scope_hash: str
    obligation_set_hash: str
    resolver: str
    resolver_provenance: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("resolution_id", "challenge_id", "resolver"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.state, ChallengeState):
            raise TypeError("state must be ChallengeState")
        if not isinstance(self.outcome, ResolutionOutcome):
            raise TypeError("outcome must be ResolutionOutcome")
        for name in ("verifier_receipt_id", "verifier_module", "resolver_provenance", "reason"):
            _require_optional_text(name, getattr(self, name))
        if self.evidence_hash is not None:
            _require_hash("evidence_hash", self.evidence_hash)
        for name in ("candidate_hash", "scope_hash", "obligation_set_hash"):
            _require_hash(name, getattr(self, name))
        _require_mapping("metadata", self.metadata)
        if (self.verifier_receipt_id is None) != (self.verifier_module is None):
            raise ValueError("verifier_receipt_id and verifier_module must be provided together")
        if self.state is ChallengeState.RESOLVED and self.outcome is ResolutionOutcome.INCONCLUSIVE:
            raise ValueError("RESOLVED cannot have an INCONCLUSIVE outcome")
        if self.state in {
            ChallengeState.PROPOSED,
            ChallengeState.SELECTED,
            ChallengeState.RUNNING,
            ChallengeState.UNRESOLVED,
            ChallengeState.UNAVAILABLE,
        } and self.outcome is not ResolutionOutcome.INCONCLUSIVE:
            raise ValueError(f"{self.state.value} requires INCONCLUSIVE outcome")
        if self.state is ChallengeState.DISMISSED_NOT_APPLICABLE and not self.reason:
            raise ValueError("dismissed challenge requires a reason")
        if self.schema != SCHEMA_VERSION:
            raise ValueError(f"schema must be {SCHEMA_VERSION}")
