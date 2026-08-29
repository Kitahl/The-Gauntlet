"""Closed, provider-neutral contracts for FOIL v2 tool execution.

V2 keeps operation families distinct, binds every call to one frozen question
and A0, and separates a compact public receipt from the raw passage archive.
Unknown fields fail closed when a trace is reconstructed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse

from egrt_types import digest
from foil_route_opportunity_v2 import RuntimeToolFamily


CONTRACT_SCHEMA_V2 = "foil.tool-contract.v2"
RECEIPT_SCHEMA_V2 = "foil.tool-receipt.v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PPM = 1_000_000


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive(name: str, value: object) -> int:
    result = _count(name, value)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _ppm(name: str, value: object) -> int:
    result = _count(name, value)
    if result > PPM:
        raise ValueError(f"{name} must be integer ppm")
    return result


def _sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.username is None


def _closed(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(raw)
    if actual != expected:
        raise ValueError(
            f"closed {label} schema mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


class OperationSpecOrigin(str, Enum):
    HOST_DERIVED = "HOST_DERIVED"
    ADMITTED_GENERATED = "ADMITTED_GENERATED"
    HOST_RETRIEVAL = "HOST_RETRIEVAL"


class ToolOutcomeV2(str, Enum):
    RESOLVED = "RESOLVED"
    SUPPORTING = "SUPPORTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNRESOLVED = "UNRESOLVED"
    INVALID = "INVALID"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class BoundaryFailureCode(str, Enum):
    MALFORMED_RESULT = "MALFORMED_RESULT"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    SOURCE_FETCH_FAILED = "SOURCE_FETCH_FAILED"
    PASSAGE_MISMATCH = "PASSAGE_MISMATCH"
    RESOURCE_OVERRUN = "RESOURCE_OVERRUN"
    ADMISSION_MISSING = "ADMISSION_MISSING"
    ADMISSION_STALE = "ADMISSION_STALE"


class EvidenceAuthorityV2(str, Enum):
    MECHANICAL = "MECHANICAL"
    SUPPORTING_ONLY = "SUPPORTING_ONLY"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TokenUsageV2:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
            _count(name, getattr(self, name))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens

    def trace(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ResourceEnvelopeV2:
    maximum_input_tokens: int = 0
    maximum_cached_input_tokens: int = 0
    maximum_output_tokens: int = 0
    maximum_tool_calls: int = 1
    maximum_model_passes: int = 0
    maximum_latency_ms: int = 1_000
    maximum_monetary_microunits: int = 0
    maximum_evidence_characters: int = 0

    def __post_init__(self) -> None:
        for name in (
            "maximum_input_tokens", "maximum_cached_input_tokens",
            "maximum_output_tokens", "maximum_tool_calls", "maximum_model_passes",
            "maximum_latency_ms", "maximum_monetary_microunits",
            "maximum_evidence_characters",
        ):
            _count(name, getattr(self, name))
        if self.maximum_tool_calls == 0:
            raise ValueError("a tool envelope requires at least one tool call")
        if self.maximum_latency_ms == 0:
            raise ValueError("a tool envelope requires a positive timeout")

    @property
    def maximum_total_tokens(self) -> int:
        return self.maximum_input_tokens + self.maximum_cached_input_tokens + self.maximum_output_tokens

    def trace(self) -> dict[str, int]:
        return {
            "maximum_input_tokens": self.maximum_input_tokens,
            "maximum_cached_input_tokens": self.maximum_cached_input_tokens,
            "maximum_output_tokens": self.maximum_output_tokens,
            "maximum_total_tokens": self.maximum_total_tokens,
            "maximum_tool_calls": self.maximum_tool_calls,
            "maximum_model_passes": self.maximum_model_passes,
            "maximum_latency_ms": self.maximum_latency_ms,
            "maximum_monetary_microunits": self.maximum_monetary_microunits,
            "maximum_evidence_characters": self.maximum_evidence_characters,
        }


@dataclass(frozen=True)
class RouteValueEstimate:
    probability_base_error_ppm: int
    probability_resolution_ppm: int
    probability_damage_ppm: int
    benefit_microunits: int
    damage_microunits: int
    token_cost_microunits: int
    fixed_cost_microunits: int = 0

    def __post_init__(self) -> None:
        for name in (
            "probability_base_error_ppm", "probability_resolution_ppm",
            "probability_damage_ppm",
        ):
            _ppm(name, getattr(self, name))
        for name in (
            "benefit_microunits", "damage_microunits", "token_cost_microunits",
            "fixed_cost_microunits",
        ):
            _count(name, getattr(self, name))

    @property
    def expected_gain_microunits(self) -> int:
        rescue = (
            self.probability_base_error_ppm
            * self.probability_resolution_ppm
            * self.benefit_microunits
        ) // (PPM * PPM)
        harm = self.probability_damage_ppm * self.damage_microunits // PPM
        return rescue - harm - self.token_cost_microunits - self.fixed_cost_microunits

    @property
    def executes(self) -> bool:
        return self.expected_gain_microunits > 0

    def trace(self) -> dict[str, object]:
        return {
            "probability_base_error_ppm": self.probability_base_error_ppm,
            "probability_resolution_ppm": self.probability_resolution_ppm,
            "probability_damage_ppm": self.probability_damage_ppm,
            "benefit_microunits": self.benefit_microunits,
            "damage_microunits": self.damage_microunits,
            "token_cost_microunits": self.token_cost_microunits,
            "fixed_cost_microunits": self.fixed_cost_microunits,
            "expected_gain_microunits": self.expected_gain_microunits,
            "executes": self.executes,
        }


@dataclass(frozen=True)
class ToolContractV2:
    task_id: str
    question_digest: str
    a0_digest: str
    family: RuntimeToolFamily
    tool_id: str
    tool_version: str
    operation_input_digest: str
    spec_origin: OperationSpecOrigin
    envelope: ResourceEnvelopeV2
    value: RouteValueEstimate
    timeout_ms: int
    formalization_admission_digest: str | None = None
    schema: str = CONTRACT_SCHEMA_V2
    read_only: bool = True
    production_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema != CONTRACT_SCHEMA_V2:
            raise ValueError("unsupported v2 tool-contract schema")
        for name in ("task_id", "tool_id", "tool_version"):
            _text(name, getattr(self, name))
        for name in ("question_digest", "a0_digest", "operation_input_digest"):
            _sha256(name, getattr(self, name))
        object.__setattr__(self, "family", RuntimeToolFamily(self.family))
        object.__setattr__(self, "spec_origin", OperationSpecOrigin(self.spec_origin))
        if not isinstance(self.envelope, ResourceEnvelopeV2):
            raise TypeError("envelope must be ResourceEnvelopeV2")
        if not isinstance(self.value, RouteValueEstimate):
            raise TypeError("value must be RouteValueEstimate")
        _positive("timeout_ms", self.timeout_ms)
        if self.timeout_ms > self.envelope.maximum_latency_ms:
            raise ValueError("timeout exceeds resource envelope")
        if self.spec_origin is OperationSpecOrigin.ADMITTED_GENERATED:
            _sha256("formalization_admission_digest", self.formalization_admission_digest)
        elif self.formalization_admission_digest is not None:
            raise ValueError("host-derived operations cannot carry formalization admission")
        if self.family is RuntimeToolFamily.PASSAGE_RETRIEVAL and self.spec_origin is not OperationSpecOrigin.HOST_RETRIEVAL:
            raise ValueError("passage retrieval requires HOST_RETRIEVAL origin")
        if self.family is not RuntimeToolFamily.PASSAGE_RETRIEVAL and self.spec_origin is OperationSpecOrigin.HOST_RETRIEVAL:
            raise ValueError("HOST_RETRIEVAL origin is retrieval-only")
        if self.read_only is not True or self.production_authorized is not False:
            raise ValueError("v2 tool contracts are read-only and non-authoritative")

    def body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "a0_digest": self.a0_digest,
            "family": self.family.value,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "operation_input_digest": self.operation_input_digest,
            "spec_origin": self.spec_origin.value,
            "formalization_admission_sha256": self.formalization_admission_digest,
            "envelope": self.envelope.trace(),
            "value": self.value.trace(),
            "timeout_ms": self.timeout_ms,
            "read_only": True,
            "production_authorized": False,
            "raw_question_stored": False,
            "raw_a0_stored": False,
        }

    @property
    def contract_digest(self) -> str:
        return digest(self.body())

    def trace(self) -> dict[str, object]:
        body = self.body()
        body["contract_sha256"] = self.contract_digest
        return body


@dataclass(frozen=True)
class PassageEvidenceV2:
    document_id: str
    source_url: str
    title: str
    content: str
    retrieved_at: str
    start_offset: int
    end_offset: int
    source_class: str = "UNKNOWN"
    independent_group: str = "unknown"

    def __post_init__(self) -> None:
        for name in ("document_id", "title", "content", "retrieved_at", "source_class", "independent_group"):
            _text(name, getattr(self, name))
        if not isinstance(self.source_url, str) or not _https(self.source_url):
            raise ValueError("source_url must be canonical HTTPS without credentials")
        _count("start_offset", self.start_offset)
        _count("end_offset", self.end_offset)
        if self.end_offset <= self.start_offset or self.end_offset > len(self.content):
            raise ValueError("passage offsets must select a non-empty content slice")
        if not self.passage.strip():
            raise ValueError("passage slice must contain text")

    @property
    def passage(self) -> str:
        return self.content[self.start_offset:self.end_offset]

    @property
    def content_digest(self) -> str:
        return digest(self.content)

    @property
    def passage_digest(self) -> str:
        return digest(self.passage)

    def trace(self, *, include_raw: bool = False) -> dict[str, object]:
        body: dict[str, object] = {
            "document_id": self.document_id,
            "source_url": self.source_url,
            "title_sha256": digest(self.title),
            "content_sha256": self.content_digest,
            "retrieved_at": self.retrieved_at,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "passage_sha256": self.passage_digest,
            "source_class": self.source_class,
            "independent_group": self.independent_group,
            "raw_content_stored": include_raw,
        }
        if include_raw:
            body.update({"title": self.title, "content": self.content, "passage": self.passage})
        return body


@dataclass(frozen=True)
class ToolReceiptV2:
    call_id: str
    contract_digest: str
    family: RuntimeToolFamily
    outcome: ToolOutcomeV2
    usage: TokenUsageV2
    tool_calls: int
    latency_ms: int
    monetary_microunits: int
    candidate_answer: str | None = None
    verification_expression: str | None = None
    passages: tuple[PassageEvidenceV2, ...] = ()
    boundary_failure: BoundaryFailureCode | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        _text("call_id", self.call_id)
        _sha256("contract_digest", self.contract_digest)
        object.__setattr__(self, "family", RuntimeToolFamily(self.family))
        object.__setattr__(self, "outcome", ToolOutcomeV2(self.outcome))
        if not isinstance(self.usage, TokenUsageV2):
            raise TypeError("usage must be TokenUsageV2")
        _count("tool_calls", self.tool_calls)
        _count("latency_ms", self.latency_ms)
        _count("monetary_microunits", self.monetary_microunits)
        if self.candidate_answer is not None:
            _text("candidate_answer", self.candidate_answer)
        if self.verification_expression is not None:
            _text("verification_expression", self.verification_expression)
        if not isinstance(self.passages, tuple) or not all(isinstance(item, PassageEvidenceV2) for item in self.passages):
            raise TypeError("passages must be a PassageEvidenceV2 tuple")
        failure = self.outcome in {ToolOutcomeV2.INVALID, ToolOutcomeV2.ERROR, ToolOutcomeV2.TIMEOUT}
        if failure:
            if self.boundary_failure is None:
                raise ValueError("failure outcomes require boundary_failure")
            object.__setattr__(self, "boundary_failure", BoundaryFailureCode(self.boundary_failure))
            _text("error_detail", self.error_detail)
        elif self.boundary_failure is not None or self.error_detail is not None:
            raise ValueError("non-failure outcomes cannot carry boundary failure")
        if self.outcome is ToolOutcomeV2.RESOLVED:
            if self.family is RuntimeToolFamily.PASSAGE_RETRIEVAL:
                raise ValueError("retrieval cannot be mechanically resolved")
            if self.candidate_answer is None or self.verification_expression is None:
                raise ValueError("RESOLVED requires answer and verification expression")
        if self.outcome is ToolOutcomeV2.SUPPORTING:
            if self.family is not RuntimeToolFamily.PASSAGE_RETRIEVAL or not self.passages:
                raise ValueError("SUPPORTING requires passage retrieval evidence")
        if self.family is RuntimeToolFamily.PASSAGE_RETRIEVAL and self.verification_expression is not None:
            raise ValueError("retrieval cannot carry a mechanical expression")
        if self.family is not RuntimeToolFamily.PASSAGE_RETRIEVAL and self.passages:
            raise ValueError("mechanical tools cannot carry passages")

    @property
    def authority(self) -> EvidenceAuthorityV2:
        if self.outcome is ToolOutcomeV2.RESOLVED:
            return EvidenceAuthorityV2.MECHANICAL
        if self.outcome is ToolOutcomeV2.SUPPORTING:
            return EvidenceAuthorityV2.SUPPORTING_ONLY
        return EvidenceAuthorityV2.REJECTED

    def validate_against(self, contract: ToolContractV2) -> None:
        if self.contract_digest != contract.contract_digest or self.family is not contract.family:
            raise ValueError("tool receipt does not bind contract")
        envelope = contract.envelope
        if self.usage.input_tokens > envelope.maximum_input_tokens:
            raise ValueError("receipt exceeds input-token envelope")
        if self.usage.cached_input_tokens > envelope.maximum_cached_input_tokens:
            raise ValueError("receipt exceeds cached-input envelope")
        if self.usage.output_tokens > envelope.maximum_output_tokens:
            raise ValueError("receipt exceeds output-token envelope")
        if self.tool_calls > envelope.maximum_tool_calls:
            raise ValueError("receipt exceeds tool-call envelope")
        if self.latency_ms > envelope.maximum_latency_ms:
            raise ValueError("receipt exceeds latency envelope")
        if self.monetary_microunits > envelope.maximum_monetary_microunits:
            raise ValueError("receipt exceeds monetary envelope")
        if sum(len(item.content) for item in self.passages) > envelope.maximum_evidence_characters:
            raise ValueError("receipt exceeds evidence-character envelope")

    def trace(self, *, include_raw: bool = False) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": RECEIPT_SCHEMA_V2,
            "call_id": self.call_id,
            "contract_sha256": self.contract_digest,
            "family": self.family.value,
            "outcome": self.outcome.value,
            "authority": self.authority.value,
            "usage": self.usage.trace(),
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "candidate_sha256": None if self.candidate_answer is None else digest(self.candidate_answer),
            "verification_expression_sha256": (
                None if self.verification_expression is None else digest(self.verification_expression)
            ),
            "passages": [item.trace(include_raw=include_raw) for item in self.passages],
            "boundary_failure": None if self.boundary_failure is None else self.boundary_failure.value,
            "error_detail": self.error_detail if include_raw else None,
            "raw_candidate_stored": include_raw and self.candidate_answer is not None,
            "raw_evidence_stored": include_raw and bool(self.passages),
            "production_authorized": False,
        }
        if include_raw:
            body["candidate_answer"] = self.candidate_answer
            body["verification_expression"] = self.verification_expression
        body["receipt_sha256"] = digest(body)
        return body
