"""Closed contracts and evidence receipts for bounded FOIL tool execution.

This module is provider neutral.  A contract binds one question, one frozen A0,
one read-only operation, and the complete pre-launch cost envelope.  Tool output
does not become answer authority merely because a provider returned it.
Retrieval is always supporting evidence in v1. Mechanical results are eligible
for explicit unadmitted benchmark selection, never production authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse

from egrt_types import digest
from foil_capabilities import CAPABILITIES


CONTRACT_SCHEMA = "foil.tool-contract.v1"
RECEIPT_SCHEMA = "foil.tool-receipt.v1"
EVIDENCE_SCHEMA = "foil.tool-evidence-envelope.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ToolFamily(str, Enum):
    COMPUTATION = "COMPUTATION"
    EXECUTION = "EXECUTION"
    RETRIEVAL = "RETRIEVAL"


class ToolOperation(str, Enum):
    EXACT_ARITHMETIC = "EXACT_ARITHMETIC"
    RESTRICTED_PYTHON_OUTPUT = "RESTRICTED_PYTHON_OUTPUT"
    WEB_RETRIEVAL = "WEB_RETRIEVAL"
    SCHOLARLY_RETRIEVAL = "SCHOLARLY_RETRIEVAL"


class ToolOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTING = "SUPPORTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"
    INVALID = "INVALID"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class EvidenceAdmission(str, Enum):
    BENCHMARK_CORRECTIVE_UNADMITTED = "BENCHMARK_CORRECTIVE_UNADMITTED"
    SUPPORT_ONLY = "SUPPORT_ONLY"
    REJECTED = "REJECTED"


_OPERATION_CAPABILITY: Mapping[ToolOperation, str] = {
    ToolOperation.EXACT_ARITHMETIC: "SYMBOLIC_COMPUTATION",
    ToolOperation.RESTRICTED_PYTHON_OUTPUT: "CODE_EXECUTION",
    ToolOperation.WEB_RETRIEVAL: "WEB_SEARCH",
    ToolOperation.SCHOLARLY_RETRIEVAL: "SCHOLARLY_SEARCH",
}
_OPERATION_FAMILY: Mapping[ToolOperation, ToolFamily] = {
    ToolOperation.EXACT_ARITHMETIC: ToolFamily.COMPUTATION,
    ToolOperation.RESTRICTED_PYTHON_OUTPUT: ToolFamily.EXECUTION,
    ToolOperation.WEB_RETRIEVAL: ToolFamily.RETRIEVAL,
    ToolOperation.SCHOLARLY_RETRIEVAL: ToolFamily.RETRIEVAL,
}


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(name: str, value: object) -> int:
    result = _non_negative_int(name, value)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value


def _https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


@dataclass(frozen=True)
class ToolCost:
    """Maximum launch envelope; observed use belongs in :class:`ToolReceipt`."""

    maximum_input_tokens: int = 0
    maximum_cached_input_tokens: int = 0
    maximum_output_tokens: int = 0
    maximum_tool_calls: int = 1
    maximum_latency_ms: int = 1_000
    maximum_monetary_microunits: int = 0
    privacy_cost_microunits: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "maximum_input_tokens",
            "maximum_cached_input_tokens",
            "maximum_output_tokens",
            "maximum_latency_ms",
            "maximum_monetary_microunits",
            "privacy_cost_microunits",
            "retry_count",
        ):
            _non_negative_int(name, getattr(self, name))
        if self.maximum_tool_calls != 1:
            raise ValueError("smart-tool v1 is frozen at one tool call")
        if self.retry_count != 0:
            raise ValueError("smart-tool v1 does not retry")

    @property
    def maximum_total_tokens(self) -> int:
        return (
            self.maximum_input_tokens
            + self.maximum_cached_input_tokens
            + self.maximum_output_tokens
        )

    def trace(self) -> dict[str, int]:
        return {
            "maximum_input_tokens": self.maximum_input_tokens,
            "maximum_cached_input_tokens": self.maximum_cached_input_tokens,
            "maximum_output_tokens": self.maximum_output_tokens,
            "maximum_total_tokens": self.maximum_total_tokens,
            "maximum_tool_calls": self.maximum_tool_calls,
            "maximum_latency_ms": self.maximum_latency_ms,
            "maximum_monetary_microunits": self.maximum_monetary_microunits,
            "privacy_cost_microunits": self.privacy_cost_microunits,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ToolCost":
        expected = {
            "maximum_input_tokens", "maximum_cached_input_tokens",
            "maximum_output_tokens", "maximum_total_tokens",
            "maximum_tool_calls", "maximum_latency_ms",
            "maximum_monetary_microunits", "privacy_cost_microunits",
            "retry_count",
        }
        if set(raw) != expected:
            raise ValueError(
                f"closed cost schema mismatch: missing={sorted(expected - set(raw))}, "
                f"unknown={sorted(set(raw) - expected)}"
            )
        cost = cls(
            maximum_input_tokens=raw["maximum_input_tokens"],  # type: ignore[arg-type]
            maximum_cached_input_tokens=raw["maximum_cached_input_tokens"],  # type: ignore[arg-type]
            maximum_output_tokens=raw["maximum_output_tokens"],  # type: ignore[arg-type]
            maximum_tool_calls=raw["maximum_tool_calls"],  # type: ignore[arg-type]
            maximum_latency_ms=raw["maximum_latency_ms"],  # type: ignore[arg-type]
            maximum_monetary_microunits=raw["maximum_monetary_microunits"],  # type: ignore[arg-type]
            privacy_cost_microunits=raw["privacy_cost_microunits"],  # type: ignore[arg-type]
            retry_count=raw["retry_count"],  # type: ignore[arg-type]
        )
        if raw["maximum_total_tokens"] != cost.maximum_total_tokens:
            raise ValueError("maximum_total_tokens is not conserved")
        return cost


@dataclass(frozen=True)
class ToolContract:
    task_id: str
    question_digest: str
    a0_digest: str
    tool_id: str
    tool_version: str
    capability: str
    family: ToolFamily
    operation: ToolOperation
    operation_input_digest: str
    cost: ToolCost
    timeout_ms: int
    provider_cap_enforced: bool
    schema: str = CONTRACT_SCHEMA
    read_only: bool = True
    answer_change_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema != CONTRACT_SCHEMA:
            raise ValueError("unsupported tool-contract schema")
        for name in ("task_id", "tool_id", "tool_version"):
            _text(name, getattr(self, name))
        for name in ("question_digest", "a0_digest", "operation_input_digest"):
            _sha256(name, getattr(self, name))
        if self.capability not in CAPABILITIES:
            raise ValueError("unknown tool capability")
        object.__setattr__(self, "family", ToolFamily(self.family))
        object.__setattr__(self, "operation", ToolOperation(self.operation))
        if _OPERATION_CAPABILITY[self.operation] != self.capability:
            raise ValueError("operation does not match capability")
        if _OPERATION_FAMILY[self.operation] is not self.family:
            raise ValueError("operation does not match tool family")
        if not isinstance(self.cost, ToolCost):
            raise TypeError("cost must be ToolCost")
        _positive_int("timeout_ms", self.timeout_ms)
        if not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")
        if self.cost.maximum_total_tokens and not self.provider_cap_enforced:
            raise ValueError("token-consuming calls require a provider-enforced cap")
        if self.read_only is not True or self.answer_change_authority is not False:
            raise ValueError("smart-tool v1 contracts are read-only and non-authoritative")

    def body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "a0_digest": self.a0_digest,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "capability": self.capability,
            "family": self.family.value,
            "operation": self.operation.value,
            "operation_input_digest": self.operation_input_digest,
            "cost": self.cost.trace(),
            "timeout_ms": self.timeout_ms,
            "provider_cap_enforced": self.provider_cap_enforced,
            "read_only": True,
            "answer_change_authority": False,
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

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ToolContract":
        expected = {
            "schema", "task_id", "question_digest", "a0_digest", "tool_id",
            "tool_version", "capability", "family", "operation",
            "operation_input_digest", "cost", "timeout_ms",
            "provider_cap_enforced", "read_only", "answer_change_authority",
            "raw_question_stored", "raw_a0_stored", "contract_sha256",
        }
        if set(raw) != expected:
            raise ValueError(
                f"closed contract schema mismatch: missing={sorted(expected - set(raw))}, "
                f"unknown={sorted(set(raw) - expected)}"
            )
        if raw["raw_question_stored"] is not False or raw["raw_a0_stored"] is not False:
            raise ValueError("tool contracts cannot store raw question or A0")
        if not isinstance(raw["cost"], Mapping):
            raise TypeError("cost must be a mapping")
        contract = cls(
            task_id=raw["task_id"],  # type: ignore[arg-type]
            question_digest=raw["question_digest"],  # type: ignore[arg-type]
            a0_digest=raw["a0_digest"],  # type: ignore[arg-type]
            tool_id=raw["tool_id"],  # type: ignore[arg-type]
            tool_version=raw["tool_version"],  # type: ignore[arg-type]
            capability=raw["capability"],  # type: ignore[arg-type]
            family=raw["family"],  # type: ignore[arg-type]
            operation=raw["operation"],  # type: ignore[arg-type]
            operation_input_digest=raw["operation_input_digest"],  # type: ignore[arg-type]
            cost=ToolCost.from_mapping(raw["cost"]),
            timeout_ms=raw["timeout_ms"],  # type: ignore[arg-type]
            provider_cap_enforced=raw["provider_cap_enforced"],  # type: ignore[arg-type]
            schema=raw["schema"],  # type: ignore[arg-type]
            read_only=raw["read_only"],  # type: ignore[arg-type]
            answer_change_authority=raw["answer_change_authority"],  # type: ignore[arg-type]
        )
        if raw["contract_sha256"] != contract.contract_digest:
            raise ValueError("tool-contract digest mismatch")
        return contract


@dataclass(frozen=True)
class ToolReceipt:
    call_id: str
    contract_digest: str
    outcome: ToolOutcome
    candidate_answer: str | None = None
    evidence_digest: str | None = None
    source_urls: tuple[str, ...] = ()
    mechanically_verified: bool = False
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 1
    latency_ms: int = 0
    monetary_microunits: int = 0
    error_code: str | None = None

    def __post_init__(self) -> None:
        _text("call_id", self.call_id)
        _sha256("contract_digest", self.contract_digest)
        object.__setattr__(self, "outcome", ToolOutcome(self.outcome))
        if self.candidate_answer is not None:
            _text("candidate_answer", self.candidate_answer)
        if self.evidence_digest is not None:
            _sha256("evidence_digest", self.evidence_digest)
        if not isinstance(self.source_urls, tuple) or not all(
            isinstance(url, str) and _https_url(url) for url in self.source_urls
        ):
            raise ValueError("source_urls must be canonical HTTPS URLs")
        if not isinstance(self.mechanically_verified, bool):
            raise TypeError("mechanically_verified must be bool")
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "latency_ms",
            "monetary_microunits",
        ):
            _non_negative_int(name, getattr(self, name))
        if self.tool_calls != 1:
            raise ValueError("smart-tool v1 receipts must record exactly one call")
        if self.error_code is not None:
            _text("error_code", self.error_code)
        if self.outcome is ToolOutcome.VERIFIED:
            if not self.mechanically_verified or self.candidate_answer is None:
                raise ValueError("VERIFIED requires a mechanically verified candidate")
        elif self.mechanically_verified:
            raise ValueError("only VERIFIED may be mechanically_verified")
        if self.outcome is ToolOutcome.SUPPORTING:
            if not self.source_urls or self.evidence_digest is None:
                raise ValueError("SUPPORTING requires sources and evidence digest")
        if self.outcome in {ToolOutcome.ERROR, ToolOutcome.TIMEOUT, ToolOutcome.INVALID}:
            if self.error_code is None:
                raise ValueError("failure outcomes require error_code")
        elif self.error_code is not None:
            raise ValueError("non-failure outcomes cannot carry error_code")

    @property
    def actual_total_tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens

    def validate_against(self, contract: ToolContract) -> None:
        if not isinstance(contract, ToolContract):
            raise TypeError("contract must be ToolContract")
        if self.contract_digest != contract.contract_digest:
            raise ValueError("tool receipt does not bind contract")
        if self.actual_total_tokens > contract.cost.maximum_total_tokens:
            raise ValueError("tool receipt exceeds reserved token envelope")
        if self.latency_ms > contract.cost.maximum_latency_ms:
            raise ValueError("tool receipt exceeds latency envelope")
        if self.monetary_microunits > contract.cost.maximum_monetary_microunits:
            raise ValueError("tool receipt exceeds monetary envelope")
        if contract.family is ToolFamily.RETRIEVAL and self.mechanically_verified:
            raise ValueError("retrieval cannot create corrective authority in v1")
        if contract.family is not ToolFamily.RETRIEVAL and self.source_urls:
            raise ValueError("mechanical tools cannot smuggle retrieval sources")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": RECEIPT_SCHEMA,
            "call_id": self.call_id,
            "contract_sha256": self.contract_digest,
            "outcome": self.outcome.value,
            "candidate_digest": (
                None if self.candidate_answer is None else digest(self.candidate_answer)
            ),
            "evidence_digest": self.evidence_digest,
            "source_urls": list(self.source_urls),
            "mechanically_verified": self.mechanically_verified,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "actual_total_tokens": self.actual_total_tokens,
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "error_code": self.error_code,
            "raw_candidate_stored": False,
            "raw_evidence_stored": False,
        }
        body["receipt_sha256"] = digest(body)
        return body


@dataclass(frozen=True)
class EvidenceEnvelope:
    contract_digest: str
    receipt_digest: str
    admission: EvidenceAdmission
    candidate_answer: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _sha256("contract_digest", self.contract_digest)
        _sha256("receipt_digest", self.receipt_digest)
        object.__setattr__(self, "admission", EvidenceAdmission(self.admission))
        if self.candidate_answer is not None:
            _text("candidate_answer", self.candidate_answer)
        if not isinstance(self.reasons, tuple) or not self.reasons or not all(
            isinstance(reason, str) and reason for reason in self.reasons
        ):
            raise ValueError("evidence envelope requires reason codes")
        if self.admission is EvidenceAdmission.BENCHMARK_CORRECTIVE_UNADMITTED and self.candidate_answer is None:
            raise ValueError("benchmark corrective evidence requires a candidate")

    @classmethod
    def from_receipt(
        cls, contract: ToolContract, receipt: ToolReceipt
    ) -> "EvidenceEnvelope":
        receipt.validate_against(contract)
        receipt_digest = str(receipt.trace()["receipt_sha256"])
        if receipt.outcome is ToolOutcome.VERIFIED:
            admission = EvidenceAdmission.BENCHMARK_CORRECTIVE_UNADMITTED
            reasons = ("mechanical_result_confirmed_but_generated_extraction_unadmitted",)
        elif receipt.outcome is ToolOutcome.SUPPORTING:
            admission = EvidenceAdmission.SUPPORT_ONLY
            reasons = ("retrieval_requires_independent_claim_comparator",)
        else:
            admission = EvidenceAdmission.REJECTED
            reasons = (f"tool_outcome_{receipt.outcome.value.lower()}",)
        return cls(
            contract.contract_digest,
            receipt_digest,
            admission,
            receipt.candidate_answer,
            reasons,
        )

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": EVIDENCE_SCHEMA,
            "contract_sha256": self.contract_digest,
            "receipt_sha256": self.receipt_digest,
            "admission": self.admission.value,
            "candidate_digest": (
                None if self.candidate_answer is None else digest(self.candidate_answer)
            ),
            "reasons": list(self.reasons),
            "origin": "TOOL_GENERATED",
            "raw_candidate_stored": False,
            "generated_contract_admitted": False,
            "answer_change_authority": False,
            "benchmark_selection_eligible": self.admission is EvidenceAdmission.BENCHMARK_CORRECTIVE_UNADMITTED,
        }
        body["envelope_sha256"] = digest(body)
        return body
