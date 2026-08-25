"""Pure, default-off annotated-arithmetic obligation discovery."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Mapping

from egrt_types import digest, text_digest
from egrt_verifiers import DEFAULT_REGISTRY

DISCOVERY_REQUEST_SCHEMA = "foil.obligation-discovery.request.v1"
DISCOVERY_ENVELOPE_SCHEMA = "foil.generated-spec-envelope.v1"
DISCOVERY_ROUTE_ID = "gsm8k.annotated-arithmetic.v1"
DISCOVERY_VERSION = "foil-obligation-discovery.v1"
MAX_TASK_CHARS, MAX_A0_CHARS, MAX_ANNOTATIONS, MAX_AST_NODES = 20_000, 20_000, 16, 31
_FIELDS = frozenset({"task_text", "a0_text", "task_digest", "a0_digest"})
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?")
_PROMPT_NUMBER = re.compile(r"(?<![\w.])-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?(?![\w.])")
_ANNOTATION = re.compile(r"<<\s*([^<>\r\n]{1,160}?)\s*=\s*([^<>\r\n]{1,64}?)\s*>>")
_FINAL = re.compile(r"(?m)^\s*A:\s*([^\r\n]+?)\s*$")


class DiscoveryStatus(str, Enum):
    FOUND = "FOUND"
    PARTIAL = "PARTIAL"
    ABSTAIN = "ABSTAIN"
    UNSUPPORTED = "UNSUPPORTED"


class DiscoveryRequestError(ValueError):
    """The closed no-oracle request boundary was crossed."""


@dataclass(frozen=True)
class DiscoveryPolicy:
    enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")


@dataclass(frozen=True)
class DiscoveryEnvelope:
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
            raise ValueError("envelope route/schema is fixed")
        if not isinstance(self.status, DiscoveryStatus) or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("envelope status/reason is invalid")
        for name in ("route_binding_digest", "input_digest", "task_digest", "a0_digest"):
            _digest(name, getattr(self, name))
        if not isinstance(self.base_answer, str) or text_digest(self.base_answer) != self.a0_digest:
            raise ValueError("envelope must preserve bound A0")
        if self.status is DiscoveryStatus.FOUND:
            if not isinstance(self.task_spec, Mapping) or self.task_spec_digest != digest(dict(self.task_spec)):
                raise ValueError("FOUND requires content-addressed task spec")
        elif self.task_spec is not None or self.task_spec_digest is not None:
            raise ValueError("only FOUND may carry task spec")
        if self.execution_authorized or not self.admission_required or any((self.provider_calls, self.profile_writes, self.action_count)) or self.answer_mutated:
            raise ValueError("discovery is unadmitted and side-effect free")

    @property
    def envelope_digest(self) -> str:
        return digest(self)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "route": self.route, "route_binding_digest": self.route_binding_digest,
                "status": self.status.value, "reason": self.reason, "input_digest": self.input_digest,
                "task_digest": self.task_digest, "a0_digest": self.a0_digest, "base_answer": self.base_answer,
                "task_spec": dict(self.task_spec) if self.task_spec is not None else None,
                "task_spec_digest": self.task_spec_digest, "origin": self.origin, "admission_required": self.admission_required,
                "execution_authorized": self.execution_authorized, "provider_calls": self.provider_calls,
                "profile_writes": self.profile_writes, "action_count": self.action_count,
                "answer_mutated": self.answer_mutated, "envelope_digest": self.envelope_digest}


def _digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise DiscoveryRequestError(f"{name} must be lowercase SHA-256")
    return value


def _request(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise DiscoveryRequestError("request must be object")
    fields = set(value)
    if fields != _FIELDS:
        raise DiscoveryRequestError(f"request fields are closed (unknown={sorted(fields - _FIELDS)}, missing={sorted(_FIELDS - fields)})")
    task, answer = value["task_text"], value["a0_text"]
    if not isinstance(task, str) or not isinstance(answer, str):
        raise DiscoveryRequestError("task_text and a0_text must be strings")
    task_digest, a0_digest = _digest("task_digest", value["task_digest"]), _digest("a0_digest", value["a0_digest"])
    if text_digest(task) != task_digest or text_digest(answer) != a0_digest:
        raise DiscoveryRequestError("content digest does not bind supplied text")
    return {"task_text": task, "a0_text": answer, "task_digest": task_digest, "a0_digest": a0_digest}


def _binding() -> str:
    return digest({"route": DISCOVERY_ROUTE_ID, "version": DISCOVERY_VERSION, "request_schema": DISCOVERY_REQUEST_SCHEMA,
                   "envelope_schema": DISCOVERY_ENVELOPE_SCHEMA, "bounds": (MAX_TASK_CHARS, MAX_A0_CHARS, MAX_ANNOTATIONS, MAX_AST_NODES),
                   "verifiers": tuple((name, DEFAULT_REGISTRY.resolve(name).version) for name in ("builtin.exact_arithmetic", "builtin.numeric_provenance", "builtin.exact_match"))})


def _envelope(req: Mapping[str, str], status: DiscoveryStatus, reason: str, spec: Mapping[str, Any] | None = None) -> DiscoveryEnvelope:
    candidate = dict(spec) if spec is not None else None
    return DiscoveryEnvelope(DISCOVERY_ENVELOPE_SCHEMA, DISCOVERY_ROUTE_ID, _binding(), status, reason,
        digest({"route": DISCOVERY_ROUTE_ID, "version": DISCOVERY_VERSION, "task_digest": req["task_digest"], "a0_digest": req["a0_digest"]}),
        req["task_digest"], req["a0_digest"], req["a0_text"], candidate, digest(candidate) if candidate is not None else None)


def _number(value: str) -> Fraction:
    if not _NUMBER.fullmatch(value) or len(value.replace("-", "").replace("/", "").replace(".", "")) > 128:
        raise ValueError("unsupported numeric literal")
    return Fraction(value)


def _rat(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _value(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return Fraction(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, float):
        return _number(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        left, right = _value(node.left), _value(node.right)
        if isinstance(node.op, ast.Add): return left + right
        if isinstance(node.op, ast.Sub): return left - right
        if isinstance(node.op, ast.Mult): return left * right
        if isinstance(node.op, ast.Div):
            if right == 0: raise ValueError("division by zero")
            return left / right
        if right.denominator != 1 or abs(right.numerator) > 10: raise ValueError("unsupported exponent")
        return left ** right.numerator
    raise ValueError("unsupported expression syntax")


def _operands(node: ast.AST) -> tuple[Fraction, ...]:
    found: list[Fraction] = []
    def visit(current: ast.AST) -> None:
        if isinstance(current, ast.Constant) and isinstance(current.value, (int, float)) and not isinstance(current.value, bool):
            found.append(_number(str(current.value)))
        elif isinstance(current, ast.UnaryOp) and isinstance(current.op, (ast.UAdd, ast.USub)):
            if isinstance(current.operand, ast.Constant):
                value = _number(str(current.operand.value)); found.append(value if isinstance(current.op, ast.UAdd) else -value)
            else: visit(current.operand)
        elif isinstance(current, ast.BinOp):
            visit(current.left); visit(current.right)
    visit(node)
    if not found or len(found) > 8: raise ValueError("unsupported operand count")
    return tuple(found)


@dataclass(frozen=True)
class _Annotation:
    expression: str
    result: str
    operands: tuple[str, ...]


def _annotations(answer: str) -> tuple[_Annotation, ...]:
    rows = tuple(_ANNOTATION.finditer(answer))
    if len(rows) > MAX_ANNOTATIONS: raise OverflowError("too many annotations")
    if not rows:
        if "<<" in answer or ">>" in answer: raise ValueError("malformed annotation delimiters")
        return ()
    out = []
    for row in rows:
        expression, result = row.group(1).strip(), row.group(2).strip()
        try:
            tree = ast.parse(expression, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES: raise ValueError("expression exceeds AST bound")
            operands = _operands(tree.body); _value(tree.body); expected = _number(result)
        except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f"unsupported annotation: {exc}") from exc
        out.append(_Annotation(expression, _rat(expected), tuple(_rat(x) for x in operands)))
    return tuple(out)


def _sources(task: str) -> list[str]:
    result = []
    for item in _PROMPT_NUMBER.finditer(task):
        try: result.append(_rat(_number(item.group(0))))
        except ValueError: pass
    return result[:64]


def _claim(key: str, statement: str, kind: str, predicate: str, verifier: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"claim_key": key, "statement_digest": text_digest(statement), "claim_kind": kind, "decidability": "DETERMINISTIC", "applicability": "APPLICABLE",
            "reason": "bounded parser extraction; unadmitted pending formalization evidence", "obligations": [{"obligation_key": key, "description": statement,
            "weight_range": {"start": 1, "end": 1}, "predicate_kind": predicate, "verifier_id": verifier,
            "verifier_version": DEFAULT_REGISTRY.resolve(verifier).version, "verifier_input": dict(payload)}]}


def _spec(req: Mapping[str, str], rows: tuple[_Annotation, ...], final: str) -> dict[str, Any]:
    claims, sources = [], _sources(req["task_text"])
    for index, row in enumerate(rows, 1):
        claims.append(_claim(f"annotation-{index}-arithmetic", f"annotated arithmetic {index} is exact", "EXACT_ARITHMETIC", "EXACT_ARITHMETIC", "builtin.exact_arithmetic", {"expression": row.expression, "expected": row.result}))
        claims.append(_claim(f"annotation-{index}-provenance", f"annotated arithmetic {index} operands derive from prompt or prior results", "NUMERIC_PROVENANCE", "NUMERIC_PROVENANCE", "builtin.numeric_provenance", {"operands": list(row.operands), "sources": list(sources)}))
        sources.append(row.result)
    claims.append(_claim("final-result-consistency", "A: result equals the final annotated result", "EXACT_MATCH", "EXACT_MATCH", "builtin.exact_match", {"actual": final, "expected": rows[-1].result}))
    return {"schema": "egrt.foil-v5.structured-task-spec.v1", "compiler_version": "foil-obligation-compiler.v1", "task_digest": req["task_digest"], "a0_digest": req["a0_digest"], "config_digest": _binding(), "claims": claims}


def discover_obligations(request: Mapping[str, object], *, policy: DiscoveryPolicy = DiscoveryPolicy()) -> DiscoveryEnvelope:
    """Discover only the narrow annotated-arithmetic execution class, default off."""
    if not isinstance(policy, DiscoveryPolicy): raise TypeError("policy must be DiscoveryPolicy")
    req = _request(request)
    if not policy.enabled: return _envelope(req, DiscoveryStatus.ABSTAIN, "route_disabled_by_default")
    if len(req["task_text"]) > MAX_TASK_CHARS or len(req["a0_text"]) > MAX_A0_CHARS: return _envelope(req, DiscoveryStatus.UNSUPPORTED, "input_exceeds_route_bounds")
    try: rows = _annotations(req["a0_text"])
    except OverflowError: return _envelope(req, DiscoveryStatus.UNSUPPORTED, "annotation_count_exceeds_route_bounds")
    except ValueError as exc: return _envelope(req, DiscoveryStatus.PARTIAL, str(exc))
    if not rows: return _envelope(req, DiscoveryStatus.ABSTAIN, "no_annotated_arithmetic_found")
    finals = tuple(_FINAL.finditer(req["a0_text"]))
    if len(finals) != 1: return _envelope(req, DiscoveryStatus.PARTIAL, "exactly one final A: result is required")
    try: final = _rat(_number(finals[0].group(1).strip()))
    except ValueError: return _envelope(req, DiscoveryStatus.PARTIAL, "final A: result is not a supported number")
    return _envelope(req, DiscoveryStatus.FOUND, "bounded_annotated_arithmetic_found", _spec(req, rows, final))


discover_gsm8k_annotated_arithmetic = discover_obligations