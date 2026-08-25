"""Default-off certified arithmetic rule bank for generated FOIL obligations.

This is one narrow execution-class generator, not a general prose formalizer.
It reads only the bound task/A0 pair, emits content-addressed unadmitted specs,
and has no provider, network, profile, action, repair, or answer-mutation path.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping

from egrt_types import digest, text_digest
from egrt_verifiers import DEFAULT_REGISTRY
from foil_certified_arithmetic import (
    CERTIFIED_LANGUAGE,
    MAX_ABS_NUMERATOR,
    MAX_AST_NODES,
    MAX_DENOMINATOR,
    MAX_MATH_SPAN_CHARS,
    MAX_POWER,
    MAX_RAW_LINES,
    POWER_LANGUAGE,
    RAW_NUMERIC_LANGUAGE,
    EqualityFinding,
    extract_step,
    normalize_expression,
)
from foil_obligation_compiler import COMPILER_VERSION, TASK_SPEC_SCHEMA
from foil_obligation_discovery import (
    MAX_A0_CHARS,
    MAX_TASK_CHARS,
    DiscoveryPolicy,
    DiscoveryRequestError,
    DiscoveryStatus,
    _request,
)

RULE_BANK_REQUEST_SCHEMA = "foil.arithmetic-rule-bank.request.v1"
RULE_BANK_ENVELOPE_SCHEMA = "foil.generated-spec-envelope.v1"
RULE_BANK_ROUTE_ID = "math.certified-arithmetic-rule-bank.v1"
RULE_BANK_VERSION = "foil-arithmetic-rule-bank.v1"
RULE_IDS = (
    CERTIFIED_LANGUAGE,
    POWER_LANGUAGE,
    RAW_NUMERIC_LANGUAGE,
    "trace-constraint-consistency-v1",
)
MAX_GENERATED_CLAIMS = 64
MAX_TRACE_CONSTRAINTS = 16

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TRACE_LIST_PREFIX = re.compile(r"^\s*(?:(?:[-*+])|(?:\d{1,3}[.)]))\s+")
_TRACE_ALLOWED = re.compile(r"[\d.\sA-Z()+\-*/=;]+")
_IMPLICIT_COEFFICIENT = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*([A-Z])\b"
)


@dataclass(frozen=True)
class TraceConstraintGroup:
    variable: str
    constraints: tuple[tuple[Fraction, Fraction], ...]
    source_span: str


@dataclass(frozen=True)
class ArithmeticRuleBankEnvelope:
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
    rule_counts: Mapping[str, int]
    origin: str = field(default="GENERATED_UNADMITTED", init=False)
    admission_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    provider_calls: int = field(default=0, init=False)
    token_count: int = field(default=0, init=False)
    profile_writes: int = field(default=0, init=False)
    action_count: int = field(default=0, init=False)
    answer_mutated: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.schema != RULE_BANK_ENVELOPE_SCHEMA or self.route != RULE_BANK_ROUTE_ID:
            raise ValueError("arithmetic rule-bank envelope route/schema is fixed")
        if not isinstance(self.status, DiscoveryStatus):
            raise TypeError("status must be DiscoveryStatus")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be non-empty")
        for name in (
            "route_binding_digest",
            "input_digest",
            "task_digest",
            "a0_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
                raise DiscoveryRequestError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.base_answer, str) or text_digest(self.base_answer) != self.a0_digest:
            raise ValueError("rule bank must preserve the bound A0")
        if (
            not isinstance(self.rule_counts, Mapping)
            or set(self.rule_counts) != set(RULE_IDS)
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in self.rule_counts.values()
            )
        ):
            raise ValueError("rule_counts must be closed non-negative counts")
        if self.status is DiscoveryStatus.FOUND:
            if (
                not isinstance(self.task_spec, Mapping)
                or self.task_spec_digest != digest(dict(self.task_spec))
            ):
                raise ValueError("FOUND requires a content-addressed task spec")
        elif self.task_spec is not None or self.task_spec_digest is not None:
            raise ValueError("only FOUND may carry a task spec")
        if (
            self.execution_authorized
            or not self.admission_required
            or any(
                (
                    self.provider_calls,
                    self.token_count,
                    self.profile_writes,
                    self.action_count,
                )
            )
            or self.answer_mutated
        ):
            raise ValueError("rule bank is unadmitted and side-effect free")

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
            "rule_counts": dict(self.rule_counts),
            "origin": self.origin,
            "admission_required": self.admission_required,
            "execution_authorized": self.execution_authorized,
            "provider_calls": self.provider_calls,
            "token_count": self.token_count,
            "profile_writes": self.profile_writes,
            "action_count": self.action_count,
            "answer_mutated": self.answer_mutated,
            "envelope_digest": self.envelope_digest,
        }


def _binding() -> str:
    return digest(
        {
            "route": RULE_BANK_ROUTE_ID,
            "version": RULE_BANK_VERSION,
            "request_schema": RULE_BANK_REQUEST_SCHEMA,
            "envelope_schema": RULE_BANK_ENVELOPE_SCHEMA,
            "rules": RULE_IDS,
            "bounds": {
                "task_chars": MAX_TASK_CHARS,
                "a0_chars": MAX_A0_CHARS,
                "math_span_chars": MAX_MATH_SPAN_CHARS,
                "raw_lines": MAX_RAW_LINES,
                "ast_nodes": MAX_AST_NODES,
                "power": MAX_POWER,
                "numerator": MAX_ABS_NUMERATOR,
                "denominator": MAX_DENOMINATOR,
                "claims": MAX_GENERATED_CLAIMS,
                "trace_constraints": MAX_TRACE_CONSTRAINTS,
            },
            "verifiers": tuple(
                (name, DEFAULT_REGISTRY.resolve(name).version)
                for name in (
                    "builtin.certified_arithmetic_equality",
                    "builtin.trace_constraint_consistency",
                )
            ),
        }
    )


def _empty_counts() -> dict[str, int]:
    return {rule: 0 for rule in RULE_IDS}


def _envelope(
    req: Mapping[str, str],
    status: DiscoveryStatus,
    reason: str,
    *,
    spec: Mapping[str, Any] | None = None,
    counts: Mapping[str, int] | None = None,
) -> ArithmeticRuleBankEnvelope:
    candidate = dict(spec) if spec is not None else None
    return ArithmeticRuleBankEnvelope(
        RULE_BANK_ENVELOPE_SCHEMA,
        RULE_BANK_ROUTE_ID,
        _binding(),
        status,
        reason,
        digest(
            {
                "route": RULE_BANK_ROUTE_ID,
                "version": RULE_BANK_VERSION,
                "task_digest": req["task_digest"],
                "a0_digest": req["a0_digest"],
            }
        ),
        req["task_digest"],
        req["a0_digest"],
        req["a0_text"],
        candidate,
        digest(candidate) if candidate is not None else None,
        dict(counts or _empty_counts()),
    )


def _bounded(value: Fraction) -> Fraction:
    if abs(value.numerator) > MAX_ABS_NUMERATOR or value.denominator > MAX_DENOMINATOR:
        raise ValueError("trace arithmetic numeric bound exceeded")
    return value


def _affine(node: ast.AST, variable: str) -> tuple[Fraction, Fraction]:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("trace constraint requires numeric literals")
        value = Fraction(node.value) if isinstance(node.value, int) else Fraction(str(node.value))
        return Fraction(0), _bounded(value)
    if isinstance(node, ast.Name):
        if node.id != variable:
            raise ValueError("trace constraint contains an unknown variable")
        return Fraction(1), Fraction(0)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        coefficient, constant = _affine(node.operand, variable)
        if isinstance(node.op, ast.USub):
            return _bounded(-coefficient), _bounded(-constant)
        return coefficient, constant
    if not isinstance(node, ast.BinOp):
        raise ValueError("trace constraint contains unsupported syntax")
    left_coefficient, left_constant = _affine(node.left, variable)
    right_coefficient, right_constant = _affine(node.right, variable)
    if isinstance(node.op, ast.Add):
        return (
            _bounded(left_coefficient + right_coefficient),
            _bounded(left_constant + right_constant),
        )
    if isinstance(node.op, ast.Sub):
        return (
            _bounded(left_coefficient - right_coefficient),
            _bounded(left_constant - right_constant),
        )
    if isinstance(node.op, ast.Mult):
        if left_coefficient and right_coefficient:
            raise ValueError("nonlinear trace constraint")
        return (
            _bounded(
                left_coefficient * right_constant
                + right_coefficient * left_constant
            ),
            _bounded(left_constant * right_constant),
        )
    if isinstance(node.op, ast.Div):
        if right_coefficient or right_constant == 0:
            raise ValueError("trace division requires a nonzero constant divisor")
        return (
            _bounded(left_coefficient / right_constant),
            _bounded(left_constant / right_constant),
        )
    if isinstance(node.op, ast.Pow):
        if right_coefficient or right_constant.denominator != 1:
            raise ValueError("trace exponent must be a constant integer")
        exponent = right_constant.numerator
        if not 0 <= exponent <= MAX_POWER:
            raise ValueError("trace exponent outside declared bound")
        if left_coefficient and exponent not in (0, 1):
            raise ValueError("nonlinear trace constraint")
        if exponent == 0:
            return Fraction(0), Fraction(1)
        if exponent == 1:
            return left_coefficient, left_constant
        return Fraction(0), _bounded(left_constant**exponent)
    raise ValueError("trace constraint contains unsupported operator")


def _affine_expression(source: str, variable: str) -> tuple[Fraction, Fraction]:
    normalized = _IMPLICIT_COEFFICIENT.sub(r"\1*\2", source).strip()
    if len(normalized) > MAX_MATH_SPAN_CHARS or not re.fullmatch(
        r"[\d.\sA-Z()+\-*/]*", normalized
    ):
        raise ValueError("trace expression is outside the closed grammar")
    tree = ast.parse(normalized, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("trace constraint AST bound exceeded")
    return _affine(tree.body, variable)


def _trace_groups(text: str) -> tuple[TraceConstraintGroup, ...]:
    lines = text.splitlines() or [text]
    if len(lines) > MAX_RAW_LINES:
        return ()
    groups: list[TraceConstraintGroup] = []
    for line in lines:
        body = _TRACE_LIST_PREFIX.sub("", line, count=1).strip()
        if (
            not body
            or len(body) > MAX_MATH_SPAN_CHARS
            or _TRACE_ALLOWED.fullmatch(body) is None
        ):
            continue
        clauses = tuple(item.strip() for item in body.split(";"))
        if not 2 <= len(clauses) <= MAX_TRACE_CONSTRAINTS:
            continue
        variables = set(re.findall(r"\b([A-Z])\b", body))
        variables.update(match.group(2) for match in _IMPLICIT_COEFFICIENT.finditer(body))
        if len(variables) != 1:
            continue
        variable = next(iter(variables))
        rows: list[tuple[Fraction, Fraction]] = []
        try:
            for clause in clauses:
                if clause.count("=") != 1:
                    raise ValueError("each trace constraint must contain one equality")
                left, right = clause.split("=", 1)
                left_coefficient, left_constant = _affine_expression(left, variable)
                right_coefficient, right_constant = _affine_expression(right, variable)
                rows.append(
                    (
                        _bounded(left_coefficient - right_coefficient),
                        _bounded(left_constant - right_constant),
                    )
                )
        except (SyntaxError, ValueError, ZeroDivisionError):
            continue
        if any(coefficient for coefficient, _ in rows):
            groups.append(TraceConstraintGroup(variable, tuple(rows), line.strip()))
    return tuple(groups)


def _rational(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _claim(
    key: str,
    statement: str,
    predicate: str,
    verifier: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "claim_key": key,
        "statement_digest": text_digest(statement),
        "claim_kind": "EXACT_ARITHMETIC",
        "decidability": "DETERMINISTIC",
        "applicability": "APPLICABLE",
        "reason": "bounded rule-bank extraction; unadmitted pending route evidence",
        "obligations": [
            {
                "obligation_key": key,
                "description": statement,
                "weight_range": {"start": 1, "end": 1},
                "predicate_kind": predicate,
                "verifier_id": verifier,
                "verifier_version": DEFAULT_REGISTRY.resolve(verifier).version,
                "verifier_input": dict(payload),
            }
        ],
    }


def _equality_claim(
    index: int, finding: EqualityFinding
) -> dict[str, Any]:
    statement = (
        f"{finding.language} extracted equality {index} is exact under its "
        "closed grammar"
    )
    return _claim(
        f"{finding.language}-{index}",
        statement,
        "CERTIFIED_ARITHMETIC_EQUALITY",
        "builtin.certified_arithmetic_equality",
        {
            "left_expression": normalize_expression(finding.left_source),
            "right_expression": normalize_expression(finding.right_source),
        },
    )


def _trace_claim(index: int, group: TraceConstraintGroup) -> dict[str, Any]:
    statement = (
        f"joint trace constraint group {index} for {group.variable} is "
        "consistent; no step localization or repair is authorized"
    )
    return _claim(
        f"trace-constraint-consistency-v1-{index}",
        statement,
        "TRACE_CONSTRAINT_CONSISTENCY",
        "builtin.trace_constraint_consistency",
        {
            "variable": group.variable,
            "constraints": [
                {
                    "coefficient": _rational(coefficient),
                    "constant": _rational(constant),
                }
                for coefficient, constant in group.constraints
            ],
        },
    )


def _spec(
    req: Mapping[str, str],
    findings: tuple[EqualityFinding, ...],
    groups: tuple[TraceConstraintGroup, ...],
) -> dict[str, Any]:
    claims = [
        _equality_claim(index, finding)
        for index, finding in enumerate(findings, 1)
    ]
    claims.extend(_trace_claim(index, group) for index, group in enumerate(groups, 1))
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": req["task_digest"],
        "a0_digest": req["a0_digest"],
        "config_digest": _binding(),
        "claims": claims,
    }


def discover_arithmetic_rule_bank(
    request: Mapping[str, object],
    *,
    policy: DiscoveryPolicy = DiscoveryPolicy(),
) -> ArithmeticRuleBankEnvelope:
    """Discover bounded arithmetic obligations without an oracle, default off."""

    if not isinstance(policy, DiscoveryPolicy):
        raise TypeError("policy must be DiscoveryPolicy")
    req = _request(request)
    if not policy.enabled:
        return _envelope(req, DiscoveryStatus.ABSTAIN, "route_disabled_by_default")
    if len(req["task_text"]) > MAX_TASK_CHARS or len(req["a0_text"]) > MAX_A0_CHARS:
        return _envelope(req, DiscoveryStatus.UNSUPPORTED, "input_exceeds_route_bounds")

    findings: list[EqualityFinding] = []
    counts = _empty_counts()
    for language in (CERTIFIED_LANGUAGE, POWER_LANGUAGE, RAW_NUMERIC_LANGUAGE):
        extracted = extract_step(req["a0_text"], step_index=0, language=language)
        counts[language] = len(extracted)
        findings.extend(extracted)
    groups = _trace_groups(req["a0_text"])
    counts["trace-constraint-consistency-v1"] = len(groups)
    if len(findings) + len(groups) > MAX_GENERATED_CLAIMS:
        return _envelope(
            req,
            DiscoveryStatus.UNSUPPORTED,
            "generated_claim_count_exceeds_route_bound",
            counts=counts,
        )
    if not findings and not groups:
        status = DiscoveryStatus.PARTIAL if "=" in req["a0_text"] else DiscoveryStatus.ABSTAIN
        reason = (
            "equalities_present_but_outside_certified_rule_bank"
            if status is DiscoveryStatus.PARTIAL
            else "no_certified_arithmetic_candidate_found"
        )
        return _envelope(req, status, reason, counts=counts)
    try:
        spec = _spec(req, tuple(findings), groups)
    except ValueError:
        return _envelope(
            req,
            DiscoveryStatus.PARTIAL,
            "extracted_candidate_failed_closed_normalization",
            counts=counts,
        )
    return _envelope(
        req,
        DiscoveryStatus.FOUND,
        "bounded_certified_arithmetic_rules_found",
        spec=spec,
        counts=counts,
    )


discover_certified_arithmetic = discover_arithmetic_rule_bank
