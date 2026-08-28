"""Closed claim, evidence, and computation-provenance contracts for FOIL v2.

Raw source text exists only in the in-memory packet.  Every persisted trace is
digest-only.  A span is accepted only when it is an exact slice of the bound
document.  A computation receipt proves arithmetic over its declared inputs;
it does not by itself prove that retrieved prose supplied the right inputs.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Mapping
from urllib.parse import urlparse

from egrt_types import digest


OBLIGATION_SCHEMA = "foil.question-obligation.v1"
PACKET_SCHEMA = "foil.evidence-packet.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class AnswerKind(str, Enum):
    EXACT_TEXT = "EXACT_TEXT"
    NUMBER = "NUMBER"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    PROPOSITION = "PROPOSITION"


class ClaimKind(str, Enum):
    ANSWER = "ANSWER"
    FACT = "FACT"
    COMPUTATION_RESULT = "COMPUTATION_RESULT"


class CandidateOrigin(str, Enum):
    BASE = "BASE"
    EVIDENCE_CONSTRUCTED = "EVIDENCE_CONSTRUCTED"


class SourceClass(str, Enum):
    PRIMARY = "PRIMARY"
    SCHOLARLY = "SCHOLARLY"
    INSTITUTIONAL = "INSTITUTIONAL"
    SECONDARY = "SECONDARY"
    UNKNOWN = "UNKNOWN"


class ContentSafety(str, Enum):
    SANITIZED_DATA_ONLY = "SANITIZED_DATA_ONLY"
    RAW_UNTRUSTED = "RAW_UNTRUSTED"
    REJECTED = "REJECTED"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _optional_text(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _text(name, value)


def _sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def _strict(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise ValueError(
            f"closed {label} schema mismatch: missing={sorted(expected - set(raw))}, "
            f"unknown={sorted(set(raw) - expected)}"
        )


@dataclass(frozen=True)
class QuestionObligation:
    task_id: str
    question_digest: str
    answer_kind: AnswerKind
    requested_unit: str | None = None
    temporal_scope: str | None = None
    jurisdiction: str | None = None
    schema: str = OBLIGATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != OBLIGATION_SCHEMA:
            raise ValueError("unsupported question-obligation schema")
        _text("task_id", self.task_id)
        _sha256("question_digest", self.question_digest)
        object.__setattr__(self, "answer_kind", AnswerKind(self.answer_kind))
        for name in ("requested_unit", "temporal_scope", "jurisdiction"):
            _optional_text(name, getattr(self, name))

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": self.schema,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "answer_kind": self.answer_kind.value,
            "requested_unit": self.requested_unit,
            "temporal_scope": self.temporal_scope,
            "jurisdiction": self.jurisdiction,
            "raw_question_stored": False,
        }
        body["obligation_sha256"] = digest(body)
        return body

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "QuestionObligation":
        expected = {
            "schema", "task_id", "question_digest", "answer_kind",
            "requested_unit", "temporal_scope", "jurisdiction",
            "raw_question_stored", "obligation_sha256",
        }
        _strict(raw, expected, "question-obligation")
        if raw["raw_question_stored"] is not False:
            raise ValueError("question obligation cannot persist raw question")
        item = cls(
            task_id=raw["task_id"],  # type: ignore[arg-type]
            question_digest=raw["question_digest"],  # type: ignore[arg-type]
            answer_kind=raw["answer_kind"],  # type: ignore[arg-type]
            requested_unit=raw["requested_unit"],  # type: ignore[arg-type]
            temporal_scope=raw["temporal_scope"],  # type: ignore[arg-type]
            jurisdiction=raw["jurisdiction"],  # type: ignore[arg-type]
            schema=raw["schema"],  # type: ignore[arg-type]
        )
        if raw["obligation_sha256"] != item.trace()["obligation_sha256"]:
            raise ValueError("question-obligation digest mismatch")
        return item


@dataclass(frozen=True)
class EvidenceDocument:
    document_id: str
    source_url: str
    title: str
    content: str
    retrieved_at: str
    source_class: SourceClass
    independent_group: str
    content_safety: ContentSafety = ContentSafety.SANITIZED_DATA_ONLY
    temporal_scope: str | None = None
    jurisdiction: str | None = None

    def __post_init__(self) -> None:
        for name in ("document_id", "title", "content", "retrieved_at", "independent_group"):
            _text(name, getattr(self, name))
        if not _https_url(self.source_url):
            raise ValueError("source_url must be canonical HTTPS without credentials")
        object.__setattr__(self, "source_class", SourceClass(self.source_class))
        object.__setattr__(self, "content_safety", ContentSafety(self.content_safety))
        _optional_text("temporal_scope", self.temporal_scope)
        _optional_text("jurisdiction", self.jurisdiction)

    @property
    def content_digest(self) -> str:
        return digest(self.content)

    def trace(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "source_url": self.source_url,
            "title_digest": digest(self.title),
            "content_sha256": self.content_digest,
            "retrieved_at": self.retrieved_at,
            "source_class": self.source_class.value,
            "independent_group": self.independent_group,
            "content_safety": self.content_safety.value,
            "temporal_scope": self.temporal_scope,
            "jurisdiction": self.jurisdiction,
            "raw_content_stored": False,
        }


@dataclass(frozen=True)
class EvidenceSpan:
    span_id: str
    document_id: str
    start_offset: int
    end_offset: int
    text: str

    def __post_init__(self) -> None:
        _text("span_id", self.span_id)
        _text("document_id", self.document_id)
        _count("start_offset", self.start_offset)
        _count("end_offset", self.end_offset)
        if self.end_offset <= self.start_offset:
            raise ValueError("evidence span must be non-empty")
        _text("text", self.text)

    def validate_against(self, document: EvidenceDocument) -> None:
        if self.document_id != document.document_id:
            raise ValueError("span does not bind document")
        if self.end_offset > len(document.content):
            raise ValueError("span exceeds document")
        if document.content[self.start_offset:self.end_offset] != self.text:
            raise ValueError("span text is not the exact document slice")

    def trace(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "document_id": self.document_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "text_sha256": digest(self.text),
            "raw_text_stored": False,
        }


@dataclass(frozen=True)
class ComputationBinding:
    name: str
    value: str
    evidence_span_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("binding name must be a simple identifier")
        _fraction(self.value)
        if self.evidence_span_id is not None:
            _text("evidence_span_id", self.evidence_span_id)


def _fraction(value: str) -> Fraction:
    _text("rational value", value)
    try:
        parsed = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("value must be a canonical rational") from exc
    canonical = (
        str(parsed.numerator)
        if parsed.denominator == 1
        else f"{parsed.numerator}/{parsed.denominator}"
    )
    if value != canonical:
        raise ValueError("value must be a canonical rational")
    return parsed


def _evaluate(node: ast.AST, bindings: Mapping[str, Fraction]) -> Fraction:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, bindings)
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return Fraction(node.value)
    if isinstance(node, ast.Name) and node.id in bindings:
        return bindings[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, bindings)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _evaluate(node.left, bindings)
        right = _evaluate(node.right, bindings)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ValueError("division by zero")
        return left / right
    raise ValueError("expression is outside the exact arithmetic language")


def canonical_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


@dataclass(frozen=True)
class ComputationReceipt:
    receipt_id: str
    expression: str
    bindings: tuple[ComputationBinding, ...]
    output: str
    mechanically_verified: bool = True

    def __post_init__(self) -> None:
        _text("receipt_id", self.receipt_id)
        _text("expression", self.expression)
        if not isinstance(self.bindings, tuple) or not all(
            isinstance(item, ComputationBinding) for item in self.bindings
        ):
            raise TypeError("bindings must be ComputationBinding tuple")
        names = [item.name for item in self.bindings]
        if len(names) != len(set(names)):
            raise ValueError("computation binding names must be unique")
        if self.mechanically_verified is not True:
            raise ValueError("computation receipts must be mechanically verified")
        try:
            tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("invalid computation expression") from exc
        actual = canonical_fraction(
            _evaluate(tree, {item.name: _fraction(item.value) for item in self.bindings})
        )
        if self.output != actual:
            raise ValueError("computation output does not match exact evaluation")

    @property
    def receipt_digest(self) -> str:
        return digest(self.trace())

    def trace(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "expression": self.expression,
            "bindings": [
                {
                    "name": item.name,
                    "value": item.value,
                    "evidence_span_id": item.evidence_span_id,
                }
                for item in self.bindings
            ],
            "output": self.output,
            "mechanically_verified": True,
        }


@dataclass(frozen=True)
class EvidencePacket:
    question_digest: str
    documents: tuple[EvidenceDocument, ...]
    spans: tuple[EvidenceSpan, ...]
    computations: tuple[ComputationReceipt, ...] = ()
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    search_calls: int = 0
    fetch_calls: int = 0
    latency_ms: int = 0
    monetary_microunits: int = 0
    schema: str = PACKET_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PACKET_SCHEMA:
            raise ValueError("unsupported evidence-packet schema")
        _sha256("question_digest", self.question_digest)
        for name, value, expected in (
            ("documents", self.documents, EvidenceDocument),
            ("spans", self.spans, EvidenceSpan),
            ("computations", self.computations, ComputationReceipt),
        ):
            if not isinstance(value, tuple) or not all(isinstance(item, expected) for item in value):
                raise TypeError(f"{name} must be a tuple of {expected.__name__}")
        for name in (
            "input_tokens", "cached_input_tokens", "output_tokens", "tool_calls",
            "search_calls", "fetch_calls", "latency_ms", "monetary_microunits",
        ):
            _count(name, getattr(self, name))
        if self.search_calls + self.fetch_calls > self.tool_calls:
            raise ValueError("search and fetch calls exceed total tool calls")
        document_map = {item.document_id: item for item in self.documents}
        if len(document_map) != len(self.documents):
            raise ValueError("document ids must be unique")
        span_map = {item.span_id: item for item in self.spans}
        if len(span_map) != len(self.spans):
            raise ValueError("span ids must be unique")
        for span in self.spans:
            document = document_map.get(span.document_id)
            if document is None:
                raise ValueError("span references unknown document")
            span.validate_against(document)
        receipt_ids = {item.receipt_id for item in self.computations}
        if len(receipt_ids) != len(self.computations):
            raise ValueError("computation receipt ids must be unique")
        for receipt in self.computations:
            for binding in receipt.bindings:
                if binding.evidence_span_id is not None and binding.evidence_span_id not in span_map:
                    raise ValueError("computation binding references unknown span")

    @property
    def actual_total_tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens

    @property
    def packet_digest(self) -> str:
        return str(self.trace()["packet_sha256"])

    def span(self, span_id: str) -> EvidenceSpan:
        for span in self.spans:
            if span.span_id == span_id:
                return span
        raise KeyError(span_id)

    def computation(self, receipt_id: str) -> ComputationReceipt:
        for receipt in self.computations:
            if receipt.receipt_id == receipt_id:
                return receipt
        raise KeyError(receipt_id)

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": self.schema,
            "question_digest": self.question_digest,
            "documents": [item.trace() for item in self.documents],
            "spans": [item.trace() for item in self.spans],
            "computations": [item.trace() for item in self.computations],
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "actual_total_tokens": self.actual_total_tokens,
            "tool_calls": self.tool_calls,
            "search_calls": self.search_calls,
            "fetch_calls": self.fetch_calls,
            "latency_ms": self.latency_ms,
            "monetary_microunits": self.monetary_microunits,
            "raw_evidence_stored": False,
        }
        body["packet_sha256"] = digest(body)
        return body


@dataclass(frozen=True)
class AtomicClaim:
    claim_id: str
    text: str
    kind: ClaimKind
    normalized_value: str
    critical: bool = True
    evidence_span_ids: tuple[str, ...] = ()
    computation_receipt_ids: tuple[str, ...] = ()
    unit: str | None = None
    temporal_scope: str | None = None
    jurisdiction: str | None = None

    def __post_init__(self) -> None:
        for name in ("claim_id", "text", "normalized_value"):
            _text(name, getattr(self, name))
        object.__setattr__(self, "kind", ClaimKind(self.kind))
        if not isinstance(self.critical, bool):
            raise TypeError("critical must be bool")
        for name in ("unit", "temporal_scope", "jurisdiction"):
            _optional_text(name, getattr(self, name))
        for name in ("evidence_span_ids", "computation_receipt_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
                raise TypeError(f"{name} must be a tuple of non-empty strings")

    def trace(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text_sha256": digest(self.text),
            "kind": self.kind.value,
            "normalized_value": self.normalized_value,
            "critical": self.critical,
            "evidence_span_ids": list(self.evidence_span_ids),
            "computation_receipt_ids": list(self.computation_receipt_ids),
            "unit": self.unit,
            "temporal_scope": self.temporal_scope,
            "jurisdiction": self.jurisdiction,
            "raw_text_stored": False,
        }


@dataclass(frozen=True)
class CandidateAnswer:
    answer_id: str
    answer: str
    answer_kind: AnswerKind
    claims: tuple[AtomicClaim, ...]
    origin: CandidateOrigin

    def __post_init__(self) -> None:
        _text("answer_id", self.answer_id)
        _text("answer", self.answer)
        object.__setattr__(self, "answer_kind", AnswerKind(self.answer_kind))
        object.__setattr__(self, "origin", CandidateOrigin(self.origin))
        if not isinstance(self.claims, tuple) or not self.claims or not all(
            isinstance(item, AtomicClaim) for item in self.claims
        ):
            raise TypeError("claims must be a non-empty AtomicClaim tuple")
        ids = [item.claim_id for item in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claim ids must be unique within an answer")

    @property
    def answer_digest(self) -> str:
        return digest(self.answer)

    def trace(self) -> dict[str, object]:
        return {
            "answer_id": self.answer_id,
            "answer_sha256": self.answer_digest,
            "answer_kind": self.answer_kind.value,
            "claims": [item.trace() for item in self.claims],
            "origin": self.origin.value,
            "raw_answer_stored": False,
        }


def single_answer_candidate(
    answer: str,
    *,
    answer_kind: AnswerKind,
    origin: CandidateOrigin,
    evidence_span_ids: tuple[str, ...] = (),
    computation_receipt_ids: tuple[str, ...] = (),
    unit: str | None = None,
    temporal_scope: str | None = None,
    jurisdiction: str | None = None,
) -> CandidateAnswer:
    """Create the narrow single-claim candidate used by short-answer benchmarks."""

    _text("answer", answer)
    identifier = digest({"answer": answer, "origin": CandidateOrigin(origin).value})[:16]
    claim = AtomicClaim(
        claim_id=f"claim-{identifier}",
        text=answer,
        kind=(
            ClaimKind.COMPUTATION_RESULT
            if computation_receipt_ids
            else ClaimKind.ANSWER
        ),
        normalized_value=answer.strip(),
        evidence_span_ids=evidence_span_ids,
        computation_receipt_ids=computation_receipt_ids,
        unit=unit,
        temporal_scope=temporal_scope,
        jurisdiction=jurisdiction,
    )
    return CandidateAnswer(
        answer_id=f"answer-{identifier}",
        answer=answer,
        answer_kind=answer_kind,
        claims=(claim,),
        origin=origin,
    )
