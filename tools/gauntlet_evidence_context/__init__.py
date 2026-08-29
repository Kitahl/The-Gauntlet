"""Additive evidence-context contracts for Gauntlet Process Assurance.

The base ``egrt.runtime.v1`` receipt verdict remains readable and unchanged.  This
module adds an opt-in, content-addressed envelope for stronger lifecycle admission.
Gauntlet may inspect that envelope, but it remains ``ASSURANCE_ONLY`` and cannot turn
provenance integrity, independent review, or a formal pass into claim-native truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from egrt_types import Verdict, digest

EVIDENCE_CONTEXT_SCHEMA = "egrt.gauntlet.evidence-context.v1"
EVIDENCE_CONTEXT_METADATA_KEY = "gauntlet_evidence_context"
EVIDENCE_REQUIREMENT_METADATA_KEY = "gauntlet_evidence_requirement"
ASSURANCE_AUTHORITY = "ASSURANCE_ONLY"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVALUATION_FIELDS = frozenset(
    {
        "model_identity",
        "model_version",
        "harness_identity",
        "harness_version",
        "prompt_digest",
        "evaluator_version",
        "oracle_semantics",
        "accepted_equivalence_relation",
        "tool_versions",
        "environment_identity",
        "budget",
        "retry_policy",
        "context_policy",
        "source_artifact_hash",
        "session_state",
    }
)


class EvidenceContextError(ValueError):
    """Raised when a typed evidence-context object is malformed or tampered."""


class ExecutionStatus(str, Enum):
    CLAIMED = "CLAIMED"
    EXECUTED = "EXECUTED"
    TESTED = "TESTED"


class ValidityStatus(str, Enum):
    UNCHECKED = "UNCHECKED"
    FORMAL_PASS = "FORMAL_PASS"
    STATISTICAL_PASS = "STATISTICAL_PASS"
    DETERMINISTIC_PASS = "DETERMINISTIC_PASS"
    FAIL = "FAIL"


class FidelityStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCHECKED = "UNCHECKED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class IndependenceStatus(str, Enum):
    SELF = "SELF"
    CROSS_CHECKED = "CROSS_CHECKED"
    INDEPENDENT = "INDEPENDENT"


class ProvenanceStatus(str, Enum):
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    BOUND = "BOUND"


class AdmissionStatus(str, Enum):
    PENDING = "PENDING"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


class SessionState(str, Enum):
    COLD_START = "COLD_START"
    WARMED_STATE = "WARMED_STATE"
    EXTENDED_SESSION = "EXTENDED_SESSION"
    RESUMED_STATE = "RESUMED_STATE"
    STALE_STATE = "STALE_STATE"
    SUPERSEDED_STATE = "SUPERSEDED_STATE"


class TransitionCause(str, Enum):
    BOUND_RECEIPT = "BOUND_RECEIPT"
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"


def _enum_value(enum_type: type[Enum], value: Any, name: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceContextError(f"invalid {name}: {value!r}") from exc


def _require_nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceContextError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_nonempty(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_nonempty(value, name)


def _require_sha256(value: Any, name: str) -> str:
    value = _require_nonempty(value, name)
    if not _SHA256.fullmatch(value):
        raise EvidenceContextError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _optional_sha256(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_sha256(value, name)


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceContextError(f"{name} must be bool")
    return value


def _strict_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceContextError(f"{name} must be a non-negative int")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceContextError(f"{name} must be an object")
    return value


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise EvidenceContextError(f"unknown {name} fields: {unknown}")


@dataclass(frozen=True)
class EvidenceQualifiers:
    """Six orthogonal evidence dimensions; no dimension implies another."""

    execution_status: ExecutionStatus
    validity_status: ValidityStatus
    fidelity_status: FidelityStatus
    independence_status: IndependenceStatus
    provenance_status: ProvenanceStatus
    admission_status: AdmissionStatus

    def __post_init__(self) -> None:
        expected = (
            ("execution_status", ExecutionStatus),
            ("validity_status", ValidityStatus),
            ("fidelity_status", FidelityStatus),
            ("independence_status", IndependenceStatus),
            ("provenance_status", ProvenanceStatus),
            ("admission_status", AdmissionStatus),
        )
        for name, enum_type in expected:
            if not isinstance(getattr(self, name), enum_type):
                raise EvidenceContextError(f"{name} must be {enum_type.__name__}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceQualifiers:
        value = _mapping(value, "qualifiers")
        allowed = {
            "execution_status",
            "validity_status",
            "fidelity_status",
            "independence_status",
            "provenance_status",
            "admission_status",
        }
        _reject_unknown(value, allowed, "qualifier")
        missing = sorted(allowed - set(value))
        if missing:
            raise EvidenceContextError(f"missing qualifier fields: {missing}")
        return cls(
            execution_status=_enum_value(
                ExecutionStatus, value["execution_status"], "execution_status"
            ),
            validity_status=_enum_value(
                ValidityStatus, value["validity_status"], "validity_status"
            ),
            fidelity_status=_enum_value(
                FidelityStatus, value["fidelity_status"], "fidelity_status"
            ),
            independence_status=_enum_value(
                IndependenceStatus,
                value["independence_status"],
                "independence_status",
            ),
            provenance_status=_enum_value(
                ProvenanceStatus, value["provenance_status"], "provenance_status"
            ),
            admission_status=_enum_value(
                AdmissionStatus, value["admission_status"], "admission_status"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "execution_status": self.execution_status.value,
            "validity_status": self.validity_status.value,
            "fidelity_status": self.fidelity_status.value,
            "independence_status": self.independence_status.value,
            "provenance_status": self.provenance_status.value,
            "admission_status": self.admission_status.value,
        }


@dataclass(frozen=True)
class EvaluationContextIdentity:
    """Content identity for a load-bearing evaluation context."""

    model_identity: str | None = None
    model_version: str | None = None
    harness_identity: str | None = None
    harness_version: str | None = None
    prompt_digest: str | None = None
    evaluator_version: str | None = None
    oracle_semantics: str | None = None
    accepted_equivalence_relation: str | None = None
    tool_versions: tuple[tuple[str, str], ...] = ()
    environment_identity: str | None = None
    budget: str | None = None
    retry_policy: str | None = None
    context_policy: str | None = None
    source_artifact_hash: str | None = None
    session_state: SessionState = SessionState.COLD_START

    def __post_init__(self) -> None:
        optional_text = (
            "model_identity",
            "model_version",
            "harness_identity",
            "harness_version",
            "evaluator_version",
            "oracle_semantics",
            "accepted_equivalence_relation",
            "environment_identity",
            "budget",
            "retry_policy",
            "context_policy",
        )
        for name in optional_text:
            value = getattr(self, name)
            if value is not None:
                _require_nonempty(value, name)
        if self.prompt_digest is not None:
            _require_sha256(self.prompt_digest, "prompt_digest")
        if self.source_artifact_hash is not None:
            _require_sha256(self.source_artifact_hash, "source_artifact_hash")
        if not isinstance(self.session_state, SessionState):
            raise EvidenceContextError("session_state must be SessionState")
        normalized = tuple(sorted(self.tool_versions))
        if normalized != self.tool_versions:
            raise EvidenceContextError("tool_versions must be sorted")
        if len({name for name, _ in self.tool_versions}) != len(self.tool_versions):
            raise EvidenceContextError("tool_versions names must be unique")
        for name, version in self.tool_versions:
            _require_nonempty(name, "tool_versions name")
            _require_nonempty(version, f"tool version for {name}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvaluationContextIdentity:
        value = _mapping(value, "evaluation_context")
        _reject_unknown(value, set(_EVALUATION_FIELDS), "evaluation_context")
        raw_tools = value.get("tool_versions", {})
        if isinstance(raw_tools, Mapping):
            tools = tuple(sorted((str(name), str(version)) for name, version in raw_tools.items()))
        elif isinstance(raw_tools, Sequence) and not isinstance(raw_tools, (str, bytes)):
            try:
                tools = tuple(sorted((str(row[0]), str(row[1])) for row in raw_tools))
            except (IndexError, TypeError) as exc:
                raise EvidenceContextError("tool_versions must contain name/version pairs") from exc
        else:
            raise EvidenceContextError("tool_versions must be an object or pair list")
        return cls(
            model_identity=_optional_nonempty(value.get("model_identity"), "model_identity"),
            model_version=_optional_nonempty(value.get("model_version"), "model_version"),
            harness_identity=_optional_nonempty(
                value.get("harness_identity"), "harness_identity"
            ),
            harness_version=_optional_nonempty(
                value.get("harness_version"), "harness_version"
            ),
            prompt_digest=_optional_sha256(value.get("prompt_digest"), "prompt_digest"),
            evaluator_version=_optional_nonempty(
                value.get("evaluator_version"), "evaluator_version"
            ),
            oracle_semantics=_optional_nonempty(
                value.get("oracle_semantics"), "oracle_semantics"
            ),
            accepted_equivalence_relation=_optional_nonempty(
                value.get("accepted_equivalence_relation"),
                "accepted_equivalence_relation",
            ),
            tool_versions=tools,
            environment_identity=_optional_nonempty(
                value.get("environment_identity"), "environment_identity"
            ),
            budget=_optional_nonempty(value.get("budget"), "budget"),
            retry_policy=_optional_nonempty(value.get("retry_policy"), "retry_policy"),
            context_policy=_optional_nonempty(
                value.get("context_policy"), "context_policy"
            ),
            source_artifact_hash=_optional_sha256(
                value.get("source_artifact_hash"), "source_artifact_hash"
            ),
            session_state=_enum_value(
                SessionState,
                value.get("session_state", SessionState.COLD_START.value),
                "session_state",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_identity": self.model_identity,
            "model_version": self.model_version,
            "harness_identity": self.harness_identity,
            "harness_version": self.harness_version,
            "prompt_digest": self.prompt_digest,
            "evaluator_version": self.evaluator_version,
            "oracle_semantics": self.oracle_semantics,
            "accepted_equivalence_relation": self.accepted_equivalence_relation,
            "tool_versions": dict(self.tool_versions),
            "environment_identity": self.environment_identity,
            "budget": self.budget,
            "retry_policy": self.retry_policy,
            "context_policy": self.context_policy,
            "source_artifact_hash": self.source_artifact_hash,
            "session_state": self.session_state.value,
        }

    @property
    def identity_hash(self) -> str:
        return digest(self.to_dict())

    def missing_fields(self, required: Sequence[str]) -> tuple[str, ...]:
        missing: list[str] = []
        body = self.to_dict()
        for name in required:
            if name not in _EVALUATION_FIELDS:
                raise EvidenceContextError(f"unknown required evaluation field: {name}")
            value = body.get(name)
            if value in (None, "", {}, []):
                missing.append(name)
        return tuple(missing)


@dataclass(frozen=True)
class ProvenanceAdapterBinding:
    """Neutral adapter record; integrity and lineage never imply factual validity."""

    backend: str
    adapter_version: str
    record_digest: str
    subject_digest: str
    attestation_digest: str | None = None
    semantics: str = "INTEGRITY_AND_LINEAGE_ONLY"

    def __post_init__(self) -> None:
        _require_nonempty(self.backend, "backend")
        _require_nonempty(self.adapter_version, "adapter_version")
        _require_sha256(self.record_digest, "record_digest")
        _require_sha256(self.subject_digest, "subject_digest")
        if self.attestation_digest is not None:
            _require_sha256(self.attestation_digest, "attestation_digest")
        if self.semantics != "INTEGRITY_AND_LINEAGE_ONLY":
            raise EvidenceContextError("provenance adapter semantics cannot grant truth")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ProvenanceAdapterBinding:
        value = _mapping(value, "provenance")
        allowed = {
            "backend",
            "adapter_version",
            "record_digest",
            "subject_digest",
            "attestation_digest",
            "semantics",
        }
        _reject_unknown(value, allowed, "provenance")
        return cls(
            backend=_require_nonempty(value.get("backend"), "backend"),
            adapter_version=_require_nonempty(
                value.get("adapter_version"), "adapter_version"
            ),
            record_digest=_require_sha256(value.get("record_digest"), "record_digest"),
            subject_digest=_require_sha256(
                value.get("subject_digest"), "subject_digest"
            ),
            attestation_digest=_optional_sha256(
                value.get("attestation_digest"), "attestation_digest"
            ),
            semantics=str(value.get("semantics", "INTEGRITY_AND_LINEAGE_ONLY")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "adapter_version": self.adapter_version,
            "record_digest": self.record_digest,
            "subject_digest": self.subject_digest,
            "attestation_digest": self.attestation_digest,
            "semantics": self.semantics,
        }

    @property
    def binding_hash(self) -> str:
        return digest(self.to_dict())


class ProvenanceAdapter(Protocol):
    """Compatibility port for W3C PROV, Flowcept, in-toto, or another backend."""

    def bind(self, record: Mapping[str, Any]) -> ProvenanceAdapterBinding:
        """Return a normalized integrity/lineage binding without deciding truth."""


@dataclass(frozen=True)
class LifecycleTransitionAuthority:
    """Typed cause for a lifecycle transition; free-text completion claims are ignored."""

    cause: TransitionCause
    target_state: str
    source_state_hash: str
    receipt_id: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    evidence_generation: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.cause, TransitionCause):
            raise EvidenceContextError("cause must be TransitionCause")
        _require_nonempty(self.target_state, "target_state")
        _require_sha256(self.source_state_hash, "source_state_hash")
        _strict_nonnegative_int(self.evidence_generation, "evidence_generation")
        if self.cause == TransitionCause.BOUND_RECEIPT:
            _require_nonempty(self.receipt_id, "receipt_id")
            if self.rule_id is not None or self.rule_version is not None:
                raise EvidenceContextError("bound receipt transition cannot name a rule")
        else:
            _require_nonempty(self.rule_id, "rule_id")
            _require_nonempty(self.rule_version, "rule_version")
            if self.receipt_id is not None:
                raise EvidenceContextError("deterministic rule transition cannot name a receipt")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> LifecycleTransitionAuthority:
        value = _mapping(value, "lifecycle_transition")
        allowed = {
            "cause",
            "target_state",
            "source_state_hash",
            "receipt_id",
            "rule_id",
            "rule_version",
            "evidence_generation",
        }
        _reject_unknown(value, allowed, "lifecycle_transition")
        return cls(
            cause=_enum_value(TransitionCause, value.get("cause"), "cause"),
            target_state=_require_nonempty(value.get("target_state"), "target_state"),
            source_state_hash=_require_sha256(
                value.get("source_state_hash"), "source_state_hash"
            ),
            receipt_id=_optional_nonempty(value.get("receipt_id"), "receipt_id"),
            rule_id=_optional_nonempty(value.get("rule_id"), "rule_id"),
            rule_version=_optional_nonempty(value.get("rule_version"), "rule_version"),
            evidence_generation=_strict_nonnegative_int(
                value.get("evidence_generation", 0), "evidence_generation"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause.value,
            "target_state": self.target_state,
            "source_state_hash": self.source_state_hash,
            "receipt_id": self.receipt_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "evidence_generation": self.evidence_generation,
        }

    @property
    def rule_key(self) -> str | None:
        if self.cause != TransitionCause.DETERMINISTIC_RULE:
            return None
        return f"{self.rule_id}@{self.rule_version}"


@dataclass(frozen=True)
class EvidenceContextEnvelope:
    """Content-addressed, opt-in evidence context persisted inside EvidenceRef metadata."""

    qualifiers: EvidenceQualifiers
    source_artifact_hash: str
    source_state_hash: str
    session_state: SessionState
    lifecycle_transition: LifecycleTransitionAuthority | None = None
    evaluation_context: EvaluationContextIdentity | None = None
    provenance: ProvenanceAdapterBinding | None = None
    required_evaluation_fields: tuple[str, ...] = ()
    session_lineage_hash: str | None = None
    rerun_generation: int = 0
    supersedes_context_hash: str | None = None
    failure_categories: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)
    schema: str = EVIDENCE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.qualifiers, EvidenceQualifiers):
            raise EvidenceContextError("qualifiers must be EvidenceQualifiers")
        if self.lifecycle_transition is not None and not isinstance(
            self.lifecycle_transition, LifecycleTransitionAuthority
        ):
            raise EvidenceContextError(
                "lifecycle_transition must be LifecycleTransitionAuthority"
            )
        if self.evaluation_context is not None and not isinstance(
            self.evaluation_context, EvaluationContextIdentity
        ):
            raise EvidenceContextError(
                "evaluation_context must be EvaluationContextIdentity"
            )
        if self.provenance is not None and not isinstance(
            self.provenance, ProvenanceAdapterBinding
        ):
            raise EvidenceContextError("provenance must be ProvenanceAdapterBinding")
        if self.schema != EVIDENCE_CONTEXT_SCHEMA:
            raise EvidenceContextError(f"unsupported evidence context schema: {self.schema}")
        _require_sha256(self.source_artifact_hash, "source_artifact_hash")
        _require_sha256(self.source_state_hash, "source_state_hash")
        if not isinstance(self.session_state, SessionState):
            raise EvidenceContextError("session_state must be SessionState")
        if self.session_state == SessionState.RESUMED_STATE:
            _require_sha256(self.session_lineage_hash, "session_lineage_hash")
        elif self.session_lineage_hash is not None:
            _require_sha256(self.session_lineage_hash, "session_lineage_hash")
        _strict_nonnegative_int(self.rerun_generation, "rerun_generation")
        if self.supersedes_context_hash is not None:
            _require_sha256(self.supersedes_context_hash, "supersedes_context_hash")
        if tuple(sorted(set(self.required_evaluation_fields))) != self.required_evaluation_fields:
            raise EvidenceContextError("required_evaluation_fields must be unique and sorted")
        for field_name in self.required_evaluation_fields:
            if field_name not in _EVALUATION_FIELDS:
                raise EvidenceContextError(
                    f"unknown required evaluation field: {field_name}"
                )
        if self.required_evaluation_fields and self.evaluation_context is None:
            raise EvidenceContextError(
                "required_evaluation_fields need an evaluation_context"
            )
        if self.evaluation_context is not None:
            if self.evaluation_context.session_state != self.session_state:
                raise EvidenceContextError(
                    "evaluation_context session_state must match envelope session_state"
                )
        if tuple(sorted(set(self.failure_categories))) != self.failure_categories:
            raise EvidenceContextError("failure_categories must be unique and sorted")
        for category in self.failure_categories:
            _require_nonempty(category, "failure category")
        if not isinstance(self.extensions, Mapping):
            raise EvidenceContextError("extensions must be an object")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceContextEnvelope:
        value = _mapping(value, "evidence_context")
        allowed = {
            "schema",
            "qualifiers",
            "source_artifact_hash",
            "source_state_hash",
            "session_state",
            "lifecycle_transition",
            "evaluation_context",
            "provenance",
            "required_evaluation_fields",
            "session_lineage_hash",
            "rerun_generation",
            "supersedes_context_hash",
            "failure_categories",
            "extensions",
            "content_hash",
        }
        _reject_unknown(value, allowed, "evidence_context")
        expected = _require_sha256(value.get("content_hash"), "content_hash")
        body = {key: raw for key, raw in value.items() if key != "content_hash"}
        if digest(body) != expected:
            raise EvidenceContextError("evidence context content_hash mismatch")
        raw_lifecycle = value.get("lifecycle_transition")
        raw_evaluation = value.get("evaluation_context")
        raw_provenance = value.get("provenance")
        raw_required = value.get("required_evaluation_fields", [])
        raw_categories = value.get("failure_categories", [])
        if not isinstance(raw_required, Sequence) or isinstance(raw_required, (str, bytes)):
            raise EvidenceContextError("required_evaluation_fields must be an array")
        if not isinstance(raw_categories, Sequence) or isinstance(raw_categories, (str, bytes)):
            raise EvidenceContextError("failure_categories must be an array")
        return cls(
            qualifiers=EvidenceQualifiers.from_mapping(
                _mapping(value.get("qualifiers"), "qualifiers")
            ),
            source_artifact_hash=_require_sha256(
                value.get("source_artifact_hash"), "source_artifact_hash"
            ),
            source_state_hash=_require_sha256(
                value.get("source_state_hash"), "source_state_hash"
            ),
            session_state=_enum_value(
                SessionState, value.get("session_state"), "session_state"
            ),
            lifecycle_transition=(
                LifecycleTransitionAuthority.from_mapping(
                    _mapping(raw_lifecycle, "lifecycle_transition")
                )
                if raw_lifecycle is not None
                else None
            ),
            evaluation_context=(
                EvaluationContextIdentity.from_mapping(
                    _mapping(raw_evaluation, "evaluation_context")
                )
                if raw_evaluation is not None
                else None
            ),
            provenance=(
                ProvenanceAdapterBinding.from_mapping(
                    _mapping(raw_provenance, "provenance")
                )
                if raw_provenance is not None
                else None
            ),
            required_evaluation_fields=tuple(sorted(str(item) for item in raw_required)),
            session_lineage_hash=_optional_sha256(
                value.get("session_lineage_hash"), "session_lineage_hash"
            ),
            rerun_generation=_strict_nonnegative_int(
                value.get("rerun_generation", 0), "rerun_generation"
            ),
            supersedes_context_hash=_optional_sha256(
                value.get("supersedes_context_hash"), "supersedes_context_hash"
            ),
            failure_categories=tuple(sorted(str(item) for item in raw_categories)),
            extensions=dict(_mapping(value.get("extensions", {}), "extensions")),
            schema=str(value.get("schema", "")),
        )

    def body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "qualifiers": self.qualifiers.to_dict(),
            "source_artifact_hash": self.source_artifact_hash,
            "source_state_hash": self.source_state_hash,
            "session_state": self.session_state.value,
            "lifecycle_transition": (
                self.lifecycle_transition.to_dict()
                if self.lifecycle_transition is not None
                else None
            ),
            "evaluation_context": (
                self.evaluation_context.to_dict()
                if self.evaluation_context is not None
                else None
            ),
            "provenance": self.provenance.to_dict() if self.provenance is not None else None,
            "required_evaluation_fields": list(self.required_evaluation_fields),
            "session_lineage_hash": self.session_lineage_hash,
            "rerun_generation": self.rerun_generation,
            "supersedes_context_hash": self.supersedes_context_hash,
            "failure_categories": list(self.failure_categories),
            "extensions": dict(self.extensions),
        }

    @property
    def content_hash(self) -> str:
        return digest(self.body())

    def to_dict(self) -> dict[str, Any]:
        body = self.body()
        body["content_hash"] = digest(body)
        return body


@dataclass(frozen=True)
class EvidenceContextRequirement:
    """Opt-in host requirement; omitted profiles preserve legacy receipt readability."""

    required: bool = False
    require_tested_execution: bool = True
    require_fidelity: bool = False
    require_independence: bool = False
    require_bound_provenance: bool = True
    require_evaluation_identity: bool = False
    required_evaluation_fields: tuple[str, ...] = ()
    current_source_artifact_hash: str | None = None
    current_source_state_hash: str | None = None
    current_generation: int | None = None
    allowed_validity_statuses: tuple[ValidityStatus, ...] = (
        ValidityStatus.FORMAL_PASS,
        ValidityStatus.STATISTICAL_PASS,
        ValidityStatus.DETERMINISTIC_PASS,
    )
    registered_transition_rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "required",
            "require_tested_execution",
            "require_fidelity",
            "require_independence",
            "require_bound_provenance",
            "require_evaluation_identity",
        ):
            _strict_bool(getattr(self, name), name)
        if tuple(sorted(set(self.required_evaluation_fields))) != self.required_evaluation_fields:
            raise EvidenceContextError("required_evaluation_fields must be unique and sorted")
        for field_name in self.required_evaluation_fields:
            if field_name not in _EVALUATION_FIELDS:
                raise EvidenceContextError(
                    f"unknown required evaluation field: {field_name}"
                )
        if self.current_source_artifact_hash is not None:
            _require_sha256(
                self.current_source_artifact_hash, "current_source_artifact_hash"
            )
        if self.current_source_state_hash is not None:
            _require_sha256(self.current_source_state_hash, "current_source_state_hash")
        if self.current_generation is not None:
            _strict_nonnegative_int(self.current_generation, "current_generation")
        if not self.allowed_validity_statuses:
            raise EvidenceContextError("allowed_validity_statuses cannot be empty")
        if any(not isinstance(item, ValidityStatus) for item in self.allowed_validity_statuses):
            raise EvidenceContextError("allowed_validity_statuses must contain ValidityStatus")
        if ValidityStatus.UNCHECKED in self.allowed_validity_statuses:
            raise EvidenceContextError("UNCHECKED cannot be an admitted validity status")
        if ValidityStatus.FAIL in self.allowed_validity_statuses:
            raise EvidenceContextError("FAIL cannot be an admitted validity status")
        if tuple(sorted(set(self.registered_transition_rules))) != self.registered_transition_rules:
            raise EvidenceContextError("registered_transition_rules must be unique and sorted")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> EvidenceContextRequirement:
        if value is None:
            return cls()
        value = _mapping(value, "evidence requirement")
        allowed = {
            "required",
            "require_tested_execution",
            "require_fidelity",
            "require_independence",
            "require_bound_provenance",
            "require_evaluation_identity",
            "required_evaluation_fields",
            "current_source_artifact_hash",
            "current_source_state_hash",
            "current_generation",
            "allowed_validity_statuses",
            "registered_transition_rules",
        }
        _reject_unknown(value, allowed, "evidence requirement")
        raw_required_fields = value.get("required_evaluation_fields", [])
        raw_validity = value.get(
            "allowed_validity_statuses",
            [
                ValidityStatus.FORMAL_PASS.value,
                ValidityStatus.STATISTICAL_PASS.value,
                ValidityStatus.DETERMINISTIC_PASS.value,
            ],
        )
        raw_rules = value.get("registered_transition_rules", [])
        for raw, name in (
            (raw_required_fields, "required_evaluation_fields"),
            (raw_validity, "allowed_validity_statuses"),
            (raw_rules, "registered_transition_rules"),
        ):
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                raise EvidenceContextError(f"{name} must be an array")
        return cls(
            required=_strict_bool(value.get("required", False), "required"),
            require_tested_execution=_strict_bool(
                value.get("require_tested_execution", True),
                "require_tested_execution",
            ),
            require_fidelity=_strict_bool(
                value.get("require_fidelity", False), "require_fidelity"
            ),
            require_independence=_strict_bool(
                value.get("require_independence", False), "require_independence"
            ),
            require_bound_provenance=_strict_bool(
                value.get("require_bound_provenance", True),
                "require_bound_provenance",
            ),
            require_evaluation_identity=_strict_bool(
                value.get("require_evaluation_identity", False),
                "require_evaluation_identity",
            ),
            required_evaluation_fields=tuple(
                sorted(str(item) for item in raw_required_fields)
            ),
            current_source_artifact_hash=_optional_sha256(
                value.get("current_source_artifact_hash"),
                "current_source_artifact_hash",
            ),
            current_source_state_hash=_optional_sha256(
                value.get("current_source_state_hash"), "current_source_state_hash"
            ),
            current_generation=(
                _strict_nonnegative_int(value["current_generation"], "current_generation")
                if "current_generation" in value
                else None
            ),
            allowed_validity_statuses=tuple(
                sorted(
                    (
                        _enum_value(ValidityStatus, item, "allowed_validity_status")
                        for item in raw_validity
                    ),
                    key=lambda item: item.value,
                )
            ),
            registered_transition_rules=tuple(sorted(str(item) for item in raw_rules)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "require_tested_execution": self.require_tested_execution,
            "require_fidelity": self.require_fidelity,
            "require_independence": self.require_independence,
            "require_bound_provenance": self.require_bound_provenance,
            "require_evaluation_identity": self.require_evaluation_identity,
            "required_evaluation_fields": list(self.required_evaluation_fields),
            "current_source_artifact_hash": self.current_source_artifact_hash,
            "current_source_state_hash": self.current_source_state_hash,
            "current_generation": self.current_generation,
            "allowed_validity_statuses": [
                item.value for item in self.allowed_validity_statuses
            ],
            "registered_transition_rules": list(self.registered_transition_rules),
        }


@dataclass(frozen=True)
class EvidenceContextAssessment:
    verdict: Verdict
    status: str
    reasons: tuple[str, ...] = ()
    context_hash: str | None = None
    admission_status: AdmissionStatus | None = None
    legacy_readable: bool = False
    authority: str = ASSURANCE_AUTHORITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "status": self.status,
            "reasons": list(self.reasons),
            "context_hash": self.context_hash,
            "admission_status": (
                self.admission_status.value if self.admission_status is not None else None
            ),
            "legacy_readable": self.legacy_readable,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class TaskEvidenceContextAssessment:
    verdict: Verdict
    status: str
    rows: tuple[dict[str, Any], ...]
    summary: str
    authority: str = ASSURANCE_AUTHORITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "status": self.status,
            "rows": [dict(row) for row in self.rows],
            "summary": self.summary,
            "authority": self.authority,
        }


def _merge_requirement_mappings(
    task_metadata: Mapping[str, Any], obligation_metadata: Mapping[str, Any]
) -> EvidenceContextRequirement:
    merged: dict[str, Any] = {}
    for metadata in (task_metadata, obligation_metadata):
        raw = metadata.get(EVIDENCE_REQUIREMENT_METADATA_KEY)
        if raw is None:
            continue
        merged.update(dict(_mapping(raw, EVIDENCE_REQUIREMENT_METADATA_KEY)))
    return EvidenceContextRequirement.from_mapping(merged if merged else None)


def _assessment(
    verdict: Verdict,
    status: str,
    reasons: Sequence[str],
    envelope: EvidenceContextEnvelope,
) -> EvidenceContextAssessment:
    return EvidenceContextAssessment(
        verdict=verdict,
        status=status,
        reasons=tuple(reasons),
        context_hash=envelope.content_hash,
        admission_status=envelope.qualifiers.admission_status,
    )


def assess_envelope(
    envelope: EvidenceContextEnvelope,
    requirement: EvidenceContextRequirement,
    *,
    receipt_id: str,
    current_source_state_hash: str | None = None,
    current_source_artifact_hash: str | None = None,
    current_generation: int | None = None,
) -> EvidenceContextAssessment:
    """Assess one typed envelope without converting one evidence dimension into another."""

    issues: list[str] = []
    unresolved: list[str] = []
    qualifiers = envelope.qualifiers

    expected_state = requirement.current_source_state_hash or current_source_state_hash
    expected_artifact = (
        requirement.current_source_artifact_hash or current_source_artifact_hash
    )
    expected_generation = (
        requirement.current_generation
        if requirement.current_generation is not None
        else current_generation
    )

    if envelope.session_state == SessionState.STALE_STATE:
        unresolved.append("STALE_STATE_NOT_CURRENT")
    if envelope.session_state == SessionState.SUPERSEDED_STATE:
        unresolved.append("SUPERSEDED_STATE_NOT_CURRENT")
    if expected_state is not None and envelope.source_state_hash != expected_state:
        unresolved.append("SOURCE_STATE_CHANGED")
    if expected_artifact is not None and envelope.source_artifact_hash != expected_artifact:
        unresolved.append("SOURCE_ARTIFACT_CHANGED")
    if expected_generation is not None and envelope.rerun_generation != expected_generation:
        unresolved.append("RERUN_GENERATION_INVALIDATED")

    if qualifiers.validity_status == ValidityStatus.FAIL:
        issues.append("VALIDITY_FAILED")
    elif qualifiers.validity_status not in requirement.allowed_validity_statuses:
        unresolved.append("VALIDITY_UNCHECKED_OR_OUT_OF_PROFILE")

    if qualifiers.fidelity_status == FidelityStatus.FAILED:
        issues.append("FIDELITY_FAILED")
    elif requirement.require_fidelity and qualifiers.fidelity_status != FidelityStatus.PASSED:
        unresolved.append("FIDELITY_REQUIRED_BUT_UNRESOLVED")

    if qualifiers.execution_status == ExecutionStatus.CLAIMED:
        unresolved.append("SELF_ATTESTED_EXECUTION_ONLY")
    elif (
        requirement.require_tested_execution
        and qualifiers.execution_status != ExecutionStatus.TESTED
    ):
        unresolved.append("TESTED_EXECUTION_REQUIRED")

    if (
        requirement.require_independence
        and qualifiers.independence_status != IndependenceStatus.INDEPENDENT
    ):
        unresolved.append("INDEPENDENCE_REQUIRED_BUT_UNRESOLVED")

    if (
        requirement.require_bound_provenance
        and qualifiers.provenance_status != ProvenanceStatus.BOUND
    ):
        unresolved.append("BOUND_PROVENANCE_REQUIRED")
    if qualifiers.provenance_status == ProvenanceStatus.BOUND:
        if envelope.provenance is None:
            issues.append("BOUND_PROVENANCE_WITHOUT_ADAPTER_RECORD")
        elif envelope.provenance.subject_digest != envelope.source_artifact_hash:
            issues.append("PROVENANCE_SUBJECT_BINDING_MISMATCH")

    if requirement.require_evaluation_identity and envelope.evaluation_context is None:
        unresolved.append("EVALUATION_CONTEXT_REQUIRED")
    if envelope.evaluation_context is not None:
        required_fields = tuple(
            sorted(
                set(requirement.required_evaluation_fields)
                | set(envelope.required_evaluation_fields)
            )
        )
        missing = envelope.evaluation_context.missing_fields(required_fields)
        if missing:
            unresolved.append(f"EVALUATION_CONTEXT_MISSING:{','.join(missing)}")
        if (
            envelope.evaluation_context.source_artifact_hash is not None
            and envelope.evaluation_context.source_artifact_hash
            != envelope.source_artifact_hash
        ):
            issues.append("EVALUATION_SOURCE_BINDING_MISMATCH")

    lifecycle = envelope.lifecycle_transition
    if lifecycle is None:
        unresolved.append("LIFECYCLE_TRANSITION_CAUSE_MISSING")
    else:
        if lifecycle.source_state_hash != envelope.source_state_hash:
            issues.append("LIFECYCLE_SOURCE_STATE_BINDING_MISMATCH")
        if lifecycle.evidence_generation != envelope.rerun_generation:
            issues.append("LIFECYCLE_GENERATION_BINDING_MISMATCH")
        if lifecycle.cause == TransitionCause.BOUND_RECEIPT:
            if lifecycle.receipt_id != receipt_id:
                issues.append("LIFECYCLE_RECEIPT_BINDING_MISMATCH")
        else:
            rule_key = lifecycle.rule_key
            if rule_key not in requirement.registered_transition_rules:
                unresolved.append("DETERMINISTIC_RULE_NOT_REGISTERED")

    if qualifiers.admission_status == AdmissionStatus.REJECTED:
        issues.append("ADMISSION_REJECTED")
    elif qualifiers.admission_status == AdmissionStatus.PENDING:
        unresolved.append("ADMISSION_PENDING")

    # A record that declares itself ADMITTED while any independent gate is unresolved
    # is a contradictory admission claim, not merely missing evidence.
    if qualifiers.admission_status == AdmissionStatus.ADMITTED and unresolved:
        issues.append("ADMITTED_WITH_UNRESOLVED_REQUIREMENTS")

    if issues:
        return _assessment(Verdict.ISSUE, "EVIDENCE_CONTEXT_REJECTED", issues + unresolved, envelope)
    if unresolved:
        return _assessment(
            Verdict.UNKNOWN,
            "EVIDENCE_CONTEXT_UNRESOLVED",
            unresolved,
            envelope,
        )
    return _assessment(Verdict.CLEARED, "EVIDENCE_CONTEXT_ADMITTED", (), envelope)


def receipt_context_mappings(receipt: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for evidence in receipt.get("evidence", []):
        if not isinstance(evidence, Mapping):
            continue
        metadata = evidence.get("metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        raw = metadata.get(EVIDENCE_CONTEXT_METADATA_KEY)
        if raw is not None:
            rows.append(_mapping(raw, EVIDENCE_CONTEXT_METADATA_KEY))
    return tuple(rows)


def assess_receipt_context(
    receipt: Mapping[str, Any],
    requirement: EvidenceContextRequirement,
    *,
    current_source_state_hash: str | None = None,
    current_source_artifact_hash: str | None = None,
    current_generation: int | None = None,
) -> EvidenceContextAssessment:
    """Read old receipts compatibly and assess opted-in typed envelopes strictly."""

    mappings = receipt_context_mappings(receipt)
    if not mappings:
        if requirement.required:
            return EvidenceContextAssessment(
                verdict=Verdict.UNKNOWN,
                status="REQUIRED_EVIDENCE_CONTEXT_MISSING",
                reasons=("BOUND_RECEIPT_OR_REGISTERED_RULE_REQUIRED",),
            )
        return EvidenceContextAssessment(
            verdict=Verdict.CLEARED,
            status="LEGACY_UNQUALIFIED_READABLE",
            reasons=("NO_STRONGER_ADMISSION_INFERRED",),
            legacy_readable=True,
        )

    assessments: list[EvidenceContextAssessment] = []
    for raw in mappings:
        try:
            envelope = EvidenceContextEnvelope.from_mapping(raw)
        except EvidenceContextError as exc:
            return EvidenceContextAssessment(
                verdict=Verdict.ISSUE,
                status="INVALID_OR_TAMPERED_EVIDENCE_CONTEXT",
                reasons=(str(exc),),
            )
        assessments.append(
            assess_envelope(
                envelope,
                requirement,
                receipt_id=str(receipt.get("receipt_id") or ""),
                current_source_state_hash=current_source_state_hash,
                current_source_artifact_hash=current_source_artifact_hash,
                current_generation=current_generation,
            )
        )

    issue = next((row for row in assessments if row.verdict == Verdict.ISSUE), None)
    if issue is not None:
        return issue
    unknown = next((row for row in assessments if row.verdict == Verdict.UNKNOWN), None)
    if unknown is not None:
        return unknown
    return EvidenceContextAssessment(
        verdict=Verdict.CLEARED,
        status="ALL_EVIDENCE_CONTEXTS_ADMITTED",
        reasons=(),
        context_hash=digest([row.context_hash for row in assessments]),
        admission_status=AdmissionStatus.ADMITTED,
    )


def _receipt_order(row: Mapping[str, Any]) -> tuple[int, int, str]:
    sequence = row.get("seq")
    stamp = str(
        row.get("stored_at")
        or row.get("finished_at")
        or row.get("started_at")
        or ""
    )
    if isinstance(sequence, int) and not isinstance(sequence, bool):
        return 1, sequence, stamp
    return 0, 0, stamp


def assess_task_evidence_context(
    task: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]],
    *,
    task_id: str | None,
    assurance_obligation_id: str,
) -> TaskEvidenceContextAssessment:
    """Assess current load-bearing receipts at Gauntlet's existing audit boundary."""

    if task is None:
        return TaskEvidenceContextAssessment(
            verdict=Verdict.UNKNOWN,
            status="TASK_CONTEXT_UNAVAILABLE",
            rows=(),
            summary="bound task is unavailable for evidence-context assurance",
        )
    task_metadata = task.get("metadata", {})
    task_metadata = task_metadata if isinstance(task_metadata, Mapping) else {}
    task_hash = task.get("content_hash")
    ordered = sorted((dict(receipt) for receipt in receipts), key=_receipt_order)
    rows: list[dict[str, Any]] = []
    active_assessments: list[EvidenceContextAssessment] = []

    for obligation in task.get("obligations", []):
        if not isinstance(obligation, Mapping) or not obligation.get("load_bearing", True):
            continue
        obligation_id = str(obligation.get("obligation_id") or "")
        if not obligation_id or obligation_id == assurance_obligation_id:
            continue
        obligation_metadata = obligation.get("metadata", {})
        obligation_metadata = (
            obligation_metadata if isinstance(obligation_metadata, Mapping) else {}
        )
        try:
            requirement = _merge_requirement_mappings(
                task_metadata, obligation_metadata
            )
        except EvidenceContextError as exc:
            assessment = EvidenceContextAssessment(
                verdict=Verdict.ISSUE,
                status="INVALID_EVIDENCE_REQUIREMENT",
                reasons=(str(exc),),
            )
            rows.append(
                {
                    "obligation_id": obligation_id,
                    "receipt_id": None,
                    "requirement": None,
                    "assessment": assessment.to_dict(),
                }
            )
            active_assessments.append(assessment)
            continue

        expected_module = obligation.get("required_module")
        matches = [
            receipt
            for receipt in ordered
            if receipt.get("obligation_id") == obligation_id
            and (expected_module is None or receipt.get("module") == expected_module)
            and (task_id is None or receipt.get("task_id") == task_id)
        ]
        if not matches:
            # The existing audit monitor owns missing-receipt semantics.
            continue
        receipt = matches[-1]
        has_context = bool(receipt_context_mappings(receipt))
        assessment = assess_receipt_context(
            receipt,
            requirement,
            current_source_state_hash=(
                requirement.current_source_state_hash
                or (str(task_hash) if isinstance(task_hash, str) else None)
            ),
            current_source_artifact_hash=requirement.current_source_artifact_hash,
            current_generation=requirement.current_generation,
        )
        row = {
            "obligation_id": obligation_id,
            "receipt_id": receipt.get("receipt_id"),
            "required": requirement.required,
            "has_context": has_context,
            "requirement_hash": digest(requirement.to_dict()),
            "assessment": assessment.to_dict(),
        }
        rows.append(row)
        if requirement.required or has_context or assessment.verdict == Verdict.ISSUE:
            active_assessments.append(assessment)

    if any(row.verdict == Verdict.ISSUE for row in active_assessments):
        verdict = Verdict.ISSUE
        status = "EVIDENCE_CONTEXT_GATE_REJECTED"
    elif any(row.verdict == Verdict.UNKNOWN for row in active_assessments):
        verdict = Verdict.UNKNOWN
        status = "EVIDENCE_CONTEXT_GATE_UNRESOLVED"
    else:
        verdict = Verdict.CLEARED
        status = (
            "EVIDENCE_CONTEXT_GATE_ADMITTED"
            if active_assessments
            else "LEGACY_COMPATIBLE_NO_PROMOTION"
        )

    problem_reasons = [
        f"{row['obligation_id']}:{reason}"
        for row in rows
        for reason in row["assessment"]["reasons"]
        if row["assessment"]["verdict"] != Verdict.CLEARED.value
    ]
    if problem_reasons:
        summary = "evidence-context gate: " + "; ".join(problem_reasons)
    elif status == "LEGACY_COMPATIBLE_NO_PROMOTION":
        summary = (
            "legacy receipts remain readable; no stronger evidence-context admission "
            "was inferred"
        )
    else:
        summary = "all opted-in evidence-context transitions are bound and admitted"
    return TaskEvidenceContextAssessment(
        verdict=verdict,
        status=status,
        rows=tuple(rows),
        summary=summary,
    )


def evidence_metadata(
    envelope: EvidenceContextEnvelope,
    *,
    producer_provenance: str | None = None,
    verifier_provenance: str | None = None,
) -> dict[str, Any]:
    """Build EvidenceRef metadata without granting authority beyond assurance."""

    metadata: dict[str, Any] = {
        EVIDENCE_CONTEXT_METADATA_KEY: envelope.to_dict(),
        "evidence_context_schema": EVIDENCE_CONTEXT_SCHEMA,
        "authority": ASSURANCE_AUTHORITY,
        "target_domain_clearance_authorized": False,
    }
    if producer_provenance is not None:
        metadata["producer_provenance"] = producer_provenance
    if verifier_provenance is not None:
        metadata["verifier_provenance"] = verifier_provenance
    return metadata


__all__ = [
    "ASSURANCE_AUTHORITY",
    "AdmissionStatus",
    "EVIDENCE_CONTEXT_METADATA_KEY",
    "EVIDENCE_CONTEXT_SCHEMA",
    "EVIDENCE_REQUIREMENT_METADATA_KEY",
    "EvidenceContextAssessment",
    "EvidenceContextEnvelope",
    "EvidenceContextError",
    "EvidenceContextRequirement",
    "EvidenceQualifiers",
    "EvaluationContextIdentity",
    "ExecutionStatus",
    "FidelityStatus",
    "IndependenceStatus",
    "LifecycleTransitionAuthority",
    "ProvenanceAdapter",
    "ProvenanceAdapterBinding",
    "ProvenanceStatus",
    "SessionState",
    "TaskEvidenceContextAssessment",
    "TransitionCause",
    "ValidityStatus",
    "assess_envelope",
    "assess_receipt_context",
    "assess_task_evidence_context",
    "evidence_metadata",
    "receipt_context_mappings",
]
