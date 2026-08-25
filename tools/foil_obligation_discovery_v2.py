"""Version-isolated provenance repair for annotated-arithmetic discovery.

R1.6/v1 is intentionally left reproducible.  This successor widens only the
numeric provenance vocabulary, remains default-off, and still emits generated,
unadmitted task specs with no action authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping

from egrt_types import digest, text_digest
from egrt_verifiers import DEFAULT_REGISTRY
from foil_obligation_discovery import (
    MAX_ANNOTATIONS,
    MAX_A0_CHARS,
    MAX_AST_NODES,
    MAX_TASK_CHARS,
    DiscoveryPolicy,
    DiscoveryRequestError,
    DiscoveryStatus,
    _FINAL,
    _annotations,
    _claim,
    _number,
    _rat,
    _request,
)

DISCOVERY_REQUEST_SCHEMA = "foil.obligation-discovery.request.v2"
DISCOVERY_ENVELOPE_SCHEMA = "foil.generated-spec-envelope.v1"
DISCOVERY_ROUTE_ID = "gsm8k.annotated-arithmetic.v2"
DISCOVERY_VERSION = "foil-obligation-discovery.v2"
MAX_SOURCES = 128

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PROMPT_NUMBER = re.compile(
    r"(?<![\w.])-?(?:\d+(?:,\d{3})*)(?:\.\d+)?(?:/[1-9]\d*)?(?!(?:\.\d)|\d)"
)
_PERCENT = re.compile(
    r"(?<![\w.])(-?(?:\d+(?:,\d{3})*)(?:\.\d+)?)\s*%(?P<tail>\s+(?:more|less))?",
    re.IGNORECASE,
)
_LEXICAL_FACTORS: tuple[tuple[re.Pattern[str], int], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), value)
    for pattern, value in (
        (r"\b(?:twice|double|half|one[- ]half)\b", 2),
        (r"\b(?:thrice|triple|third|one[- ]third)\b", 3),
        (r"\b(?:quadruple|fourth|quarter|one[- ]fourth)\b", 4),
        (r"\b(?:fifth|one[- ]fifth)\b", 5),
        (r"\b(?:sixth|one[- ]sixth)\b", 6),
        (r"\b(?:seventh|one[- ]seventh)\b", 7),
        (r"\b(?:eighth|one[- ]eighth)\b", 8),
        (r"\b(?:ninth|one[- ]ninth)\b", 9),
        (r"\b(?:tenth|one[- ]tenth)\b", 10),
    )
)
_RELATIONAL_FACTOR = re.compile(
    r"\b(?:twice|double|half|one[- ]half|thrice|triple)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class DiscoveryEnvelopeV2:
    schema: str
    route: str
    route_binding_digest: str
    status: DiscoveryStatus
    reason: str
    input_digest: str
    task_digest: str
    a0_digest: str
    base_answer: str
    task_spec: Mapping[str, Any] | None
    task_spec_digest: str | None
    origin: str = field(default="GENERATED_UNADMITTED", init=False)
    admission_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    provider_calls: int = field(default=0, init=False)
    profile_writes: int = field(default=0, init=False)
    action_count: int = field(default=0, init=False)
    answer_mutated: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.schema != DISCOVERY_ENVELOPE_SCHEMA or self.route != DISCOVERY_ROUTE_ID:
            raise ValueError("v2 envelope route/schema is fixed")
        if not isinstance(self.status, DiscoveryStatus) or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("v2 envelope status/reason is invalid")
        for name in ("route_binding_digest", "input_digest", "task_digest", "a0_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _DIGEST.fullmatch(value):
                raise DiscoveryRequestError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.base_answer, str) or text_digest(self.base_answer) != self.a0_digest:
            raise ValueError("v2 envelope must preserve bound A0")
        if self.status is DiscoveryStatus.FOUND:
            if not isinstance(self.task_spec, Mapping) or self.task_spec_digest != digest(dict(self.task_spec)):
                raise ValueError("FOUND requires content-addressed task spec")
        elif self.task_spec is not None or self.task_spec_digest is not None:
            raise ValueError("only FOUND may carry task spec")
        if self.execution_authorized or not self.admission_required or any(
            (self.provider_calls, self.profile_writes, self.action_count)
        ) or self.answer_mutated:
            raise ValueError("v2 discovery is unadmitted and side-effect free")

    @property
    def envelope_digest(self) -> str:
        return digest(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "route": self.route,
            "route_binding_digest": self.route_binding_digest,
            "status": self.status.value,
            "reason": self.reason,
            "input_digest": self.input_digest,
            "task_digest": self.task_digest,
            "a0_digest": self.a0_digest,
            "base_answer": self.base_answer,
            "task_spec": dict(self.task_spec) if self.task_spec is not None else None,
            "task_spec_digest": self.task_spec_digest,
            "origin": self.origin,
            "admission_required": self.admission_required,
            "execution_authorized": self.execution_authorized,
            "provider_calls": self.provider_calls,
            "profile_writes": self.profile_writes,
            "action_count": self.action_count,
            "answer_mutated": self.answer_mutated,
            "envelope_digest": self.envelope_digest,
        }


def _binding() -> str:
    return digest(
        {
            "route": DISCOVERY_ROUTE_ID,
            "version": DISCOVERY_VERSION,
            "request_schema": DISCOVERY_REQUEST_SCHEMA,
            "envelope_schema": DISCOVERY_ENVELOPE_SCHEMA,
            "bounds": (
                MAX_TASK_CHARS,
                MAX_A0_CHARS,
                MAX_ANNOTATIONS,
                MAX_AST_NODES,
                MAX_SOURCES,
            ),
            "verifiers": tuple(
                (name, DEFAULT_REGISTRY.resolve(name).version)
                for name in (
                    "builtin.exact_arithmetic",
                    "builtin.numeric_provenance_v2",
                    "builtin.exact_match",
                )
            ),
        }
    )


def _envelope(
    req: Mapping[str, str],
    status: DiscoveryStatus,
    reason: str,
    spec: Mapping[str, Any] | None = None,
) -> DiscoveryEnvelopeV2:
    candidate = dict(spec) if spec is not None else None
    return DiscoveryEnvelopeV2(
        DISCOVERY_ENVELOPE_SCHEMA,
        DISCOVERY_ROUTE_ID,
        _binding(),
        status,
        reason,
        digest(
            {
                "route": DISCOVERY_ROUTE_ID,
                "version": DISCOVERY_VERSION,
                "task_digest": req["task_digest"],
                "a0_digest": req["a0_digest"],
            }
        ),
        req["task_digest"],
        req["a0_digest"],
        req["a0_text"],
        candidate,
        digest(candidate) if candidate is not None else None,
    )


def _canonical(value: Fraction | str) -> str:
    parsed = value if isinstance(value, Fraction) else Fraction(value.replace(",", ""))
    return _rat(parsed)


def _source(
    value: Fraction | str,
    kind: str,
    *,
    parents: tuple[Fraction | str, ...] = (),
    operator: str = "NONE",
) -> dict[str, Any]:
    return {
        "value": _canonical(value),
        "kind": kind,
        "parents": [_canonical(parent) for parent in parents],
        "operator": operator,
    }


def _append_unique(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    if row not in rows:
        rows.append(row)
    if len(rows) > MAX_SOURCES:
        raise OverflowError("numeric provenance source bound exceeded")


def _prompt_sources(task: str) -> list[dict[str, Any]]:
    """Extract roots plus a closed, mechanically checkable derivation grammar."""

    rows: list[dict[str, Any]] = []
    roots: list[Fraction] = []
    for match in _PROMPT_NUMBER.finditer(task):
        try:
            value = Fraction(match.group(0).replace(",", ""))
        except (ValueError, ZeroDivisionError):
            continue
        if value not in roots:
            roots.append(value)
        _append_unique(rows, _source(value, "ROOT"))
        if "/" in match.group(0):
            _append_unique(
                rows,
                _source(Fraction(value.numerator), "FRACTION_COMPONENT", parents=(value,), operator="NUMERATOR"),
            )
            _append_unique(
                rows,
                _source(Fraction(value.denominator), "FRACTION_COMPONENT", parents=(value,), operator="DENOMINATOR"),
            )

    identity = Fraction(1)
    _append_unique(rows, _source(identity, "IDENTITY"))

    lexical_factors: set[int] = set()
    for pattern, factor in _LEXICAL_FACTORS:
        if pattern.search(task):
            lexical_factors.add(factor)
            _append_unique(rows, _source(Fraction(factor), "LEXICAL_FACTOR"))
            _append_unique(
                rows,
                _source(Fraction(1, factor), "LEXICAL_RATIO", parents=(Fraction(factor),), operator="RECIPROCAL"),
            )

    for match in _PERCENT.finditer(task):
        percent = Fraction(match.group(1).replace(",", ""))
        ratio = percent / 100
        _append_unique(rows, _source(ratio, "PERCENT", parents=(percent,), operator="DIVIDE_100"))
        tail = (match.group("tail") or "").strip().lower()
        if tail == "more":
            _append_unique(rows, _source(identity + ratio, "ONE_STEP", parents=(identity, ratio), operator="ADD"))
        elif tail == "less":
            _append_unique(rows, _source(identity - ratio, "ONE_STEP", parents=(identity, ratio), operator="SUB"))

    if _RELATIONAL_FACTOR.search(task):
        for root in roots:
            for factor in sorted(lexical_factors & {2, 3}):
                scale = Fraction(factor)
                _append_unique(rows, _source(root * scale, "ONE_STEP", parents=(root, scale), operator="MUL"))
                _append_unique(rows, _source(root / scale, "ONE_STEP", parents=(root, scale), operator="DIV"))
    return rows


def _spec(req: Mapping[str, str], rows: tuple[Any, ...], final: str) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    sources = _prompt_sources(req["task_text"])
    for index, row in enumerate(rows, 1):
        claims.append(
            _claim(
                f"annotation-{index}-arithmetic",
                f"annotated arithmetic {index} is exact",
                "EXACT_ARITHMETIC",
                "EXACT_ARITHMETIC",
                "builtin.exact_arithmetic",
                {"expression": row.expression, "expected": row.result},
            )
        )
        claims.append(
            _claim(
                f"annotation-{index}-provenance-v2",
                f"annotated arithmetic {index} operands have bounded structured provenance",
                "NUMERIC_PROVENANCE",
                "NUMERIC_PROVENANCE_V2",
                "builtin.numeric_provenance_v2",
                {"operands": list(row.operands), "sources": list(sources)},
            )
        )
        _append_unique(sources, _source(row.result, "PRIOR_RESULT"))
    claims.append(
        _claim(
            "final-result-consistency",
            "A: result equals the final annotated result",
            "EXACT_MATCH",
            "EXACT_MATCH",
            "builtin.exact_match",
            {"actual": final, "expected": rows[-1].result},
        )
    )
    return {
        "schema": "egrt.foil-v5.structured-task-spec.v1",
        "compiler_version": "foil-obligation-compiler.v1",
        "task_digest": req["task_digest"],
        "a0_digest": req["a0_digest"],
        "config_digest": _binding(),
        "claims": claims,
    }


def discover_obligations_v2(
    request: Mapping[str, object], *, policy: DiscoveryPolicy = DiscoveryPolicy()
) -> DiscoveryEnvelopeV2:
    """Run the default-off v2 execution-class generator without any oracle."""

    if not isinstance(policy, DiscoveryPolicy):
        raise TypeError("policy must be DiscoveryPolicy")
    req = _request(request)
    if not policy.enabled:
        return _envelope(req, DiscoveryStatus.ABSTAIN, "route_disabled_by_default")
    if len(req["task_text"]) > MAX_TASK_CHARS or len(req["a0_text"]) > MAX_A0_CHARS:
        return _envelope(req, DiscoveryStatus.UNSUPPORTED, "input_exceeds_route_bounds")
    try:
        rows = _annotations(req["a0_text"])
    except OverflowError:
        return _envelope(req, DiscoveryStatus.UNSUPPORTED, "annotation_count_exceeds_route_bounds")
    except ValueError as exc:
        return _envelope(req, DiscoveryStatus.PARTIAL, str(exc))
    if not rows:
        return _envelope(req, DiscoveryStatus.ABSTAIN, "no_annotated_arithmetic_found")
    finals = tuple(_FINAL.finditer(req["a0_text"]))
    if len(finals) != 1:
        return _envelope(req, DiscoveryStatus.PARTIAL, "exactly one final A: result is required")
    try:
        final = _rat(_number(finals[0].group(1).strip()))
        spec = _spec(req, rows, final)
    except OverflowError as exc:
        return _envelope(req, DiscoveryStatus.UNSUPPORTED, str(exc))
    except ValueError as exc:
        return _envelope(req, DiscoveryStatus.PARTIAL, str(exc))
    return _envelope(req, DiscoveryStatus.FOUND, "bounded_annotated_arithmetic_v2_found", spec)


discover_gsm8k_annotated_arithmetic_v2 = discover_obligations_v2
