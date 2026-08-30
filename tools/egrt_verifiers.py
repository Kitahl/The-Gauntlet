"""Closed, deterministic, in-process verifier registry.

The registry intentionally offers only pure built-ins.  It contains no network,
shell, subprocess, dynamic import, or provider execution surface.
"""
from __future__ import annotations

import ast
import hashlib
import json
import platform
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping

from egrt_types import canonical_json, digest


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class VerifierSpec:
    verifier_id: str
    version: str
    provenance_group: str
    input_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("verifier_id", "version", "provenance_group"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.input_keys, tuple) or not self.input_keys:
            raise ValueError("input_keys must be a non-empty tuple")
        for item in self.input_keys:
            _require_text("input_key", item)


@dataclass(frozen=True)
class VerifierResult:
    verifier_id: str
    verifier_version: str
    provenance_group: str
    status: VerificationStatus
    reason: str
    input_digest: str
    output_digest: str

    def __post_init__(self) -> None:
        for name in ("verifier_id", "verifier_version", "provenance_group", "reason"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.status, VerificationStatus):
            raise TypeError("status must be VerificationStatus")
        for name in ("input_digest", "output_digest"):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError(f"{name} must be a SHA-256 digest")

    @property
    def evidence_digest(self) -> str:
        return digest(self)


Adapter = Callable[[Mapping[str, Any]], tuple[VerificationStatus, str, Any]]


def _fraction_value(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _fraction_value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        left, right = _fraction_value(node.left), _fraction_value(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ValueError("division by zero")
            return left / right
        if right.denominator != 1 or abs(right.numerator) > 1000:
            raise ValueError("exponent must be an integer with magnitude at most 1000")
        return left**right.numerator
    raise ValueError("expression contains an unsupported syntax node")


def _exact_arithmetic(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    expression, expected = data.get("expression"), data.get("expected")
    if not isinstance(expression, str) or not isinstance(expected, str):
        return VerificationStatus.UNKNOWN, "expression and expected must be strings", None
    try:
        actual = _fraction_value(ast.parse(expression, mode="eval").body)
        target = Fraction(expected)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return VerificationStatus.UNKNOWN, "invalid exact arithmetic input", None
    return (
        VerificationStatus.PASS if actual == target else VerificationStatus.FAIL,
        "exact arithmetic matched" if actual == target else "exact arithmetic differed",
        str(actual),
    )


def _json_exact(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    actual, expected = data.get("actual"), data.get("expected")
    if not isinstance(actual, str) or not isinstance(expected, str):
        return VerificationStatus.UNKNOWN, "actual and expected must be JSON strings", None
    try:
        left, right = json.loads(actual), json.loads(expected)
    except json.JSONDecodeError:
        return VerificationStatus.UNKNOWN, "invalid JSON input", None
    matched = canonical_json(left) == canonical_json(right)
    return (VerificationStatus.PASS if matched else VerificationStatus.FAIL, "JSON matched" if matched else "JSON differed", matched)


def _digest_exact(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    value, expected = data.get("value"), data.get("expected_digest")
    if not isinstance(value, (str, bytes)) or not isinstance(expected, str):
        return VerificationStatus.UNKNOWN, "value and expected_digest are required", None
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        return (
            VerificationStatus.UNKNOWN,
            "expected_digest must be a lowercase SHA-256 digest",
            None,
        )
    raw = value.encode("utf-8") if isinstance(value, str) else value
    actual = hashlib.sha256(raw).hexdigest()
    matched = actual == expected
    return (
        VerificationStatus.PASS if matched else VerificationStatus.FAIL,
        "digest matched" if matched else "digest differed",
        actual,
    )


def _exact_match(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    if "actual" not in data or "expected" not in data:
        return VerificationStatus.UNKNOWN, "actual and expected are required", None
    matched = data["actual"] == data["expected"]
    return (VerificationStatus.PASS if matched else VerificationStatus.FAIL, "exact values matched" if matched else "exact values differed", matched)


def _numeric_tolerance(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    try:
        actual = Decimal(str(data["actual"]))
        expected = Decimal(str(data["expected"]))
        tolerance = Decimal(str(data.get("tolerance", "0")))
        if not actual.is_finite() or not expected.is_finite() or not tolerance.is_finite() or tolerance < 0:
            raise InvalidOperation
    except (InvalidOperation, KeyError, ValueError):
        return VerificationStatus.UNKNOWN, "actual, expected, and non-negative tolerance are required", None
    delta = abs(actual - expected)
    matched = delta <= tolerance
    return (VerificationStatus.PASS if matched else VerificationStatus.FAIL, "numeric tolerance matched" if matched else "numeric tolerance exceeded", str(delta))


def _canonical_rational(value: object) -> Fraction:
    if not isinstance(value, str) or not value:
        raise ValueError("rational must be non-empty text")
    numerator, separator, denominator = value.partition("/")
    if separator != "/" or "/" in denominator or not numerator or not denominator:
        raise ValueError("rational must be canonical numerator/denominator")
    digits = numerator[1:] if numerator.startswith("-") else numerator
    if not digits or not digits.isdigit() or not denominator.isdigit() or (len(digits) > 1 and digits.startswith("0")) or denominator.startswith("0"):
        raise ValueError("rational must be canonical numerator/denominator")
    parsed = Fraction(int(numerator), int(denominator))
    if f"{parsed.numerator}/{parsed.denominator}" != value:
        raise ValueError("rational must be reduced with a positive denominator")
    return parsed


def canonical_rational(value: object) -> str:
    parsed = _canonical_rational(value)
    return f"{parsed.numerator}/{parsed.denominator}"


_CERTIFIED_EXPRESSION = re.compile(r"[\d.\s()+\-*/]+")
_TRACE_VARIABLE = re.compile(r"[A-Z]")
_MAX_CERTIFIED_EXPRESSION_CHARS = 2_000
_MAX_CERTIFIED_AST_NODES = 128
_MAX_CERTIFIED_POWER = 12
_MAX_CERTIFIED_NUMERATOR = 10**18
_MAX_CERTIFIED_DENOMINATOR = 10**12
_TRACE_CONSTRAINT_FIELDS = frozenset({"coefficient", "constant"})


def _bounded_certified(value: Fraction) -> Fraction:
    if (
        abs(value.numerator) > _MAX_CERTIFIED_NUMERATOR
        or value.denominator > _MAX_CERTIFIED_DENOMINATOR
    ):
        raise ValueError("certified arithmetic numeric bound exceeded")
    return value


def _certified_fraction_value(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("certified arithmetic requires numeric literals")
        value = Fraction(node.value) if isinstance(node.value, int) else Fraction(str(node.value))
        return _bounded_certified(value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _certified_fraction_value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _certified_fraction_value(node.left)
        right = _certified_fraction_value(node.right)
        if isinstance(node.op, ast.Add):
            return _bounded_certified(left + right)
        if isinstance(node.op, ast.Sub):
            return _bounded_certified(left - right)
        if isinstance(node.op, ast.Mult):
            return _bounded_certified(left * right)
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ValueError("division by zero")
            return _bounded_certified(left / right)
        if isinstance(node.op, ast.Pow):
            if (
                right.denominator != 1
                or not 0 <= right.numerator <= _MAX_CERTIFIED_POWER
            ):
                raise ValueError("power outside certified bound")
            return _bounded_certified(left**right.numerator)
    raise ValueError("certified arithmetic contains unsupported syntax")


def _certified_expression_value(source: object) -> Fraction:
    if (
        not isinstance(source, str)
        or not source
        or len(source) > _MAX_CERTIFIED_EXPRESSION_CHARS
        or _CERTIFIED_EXPRESSION.fullmatch(source) is None
    ):
        raise ValueError("expression is outside the certified grammar")
    tree = ast.parse(source, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > _MAX_CERTIFIED_AST_NODES:
        raise ValueError("certified arithmetic AST bound exceeded")
    return _certified_fraction_value(tree.body)


def _certified_arithmetic_equality(
    data: Mapping[str, Any],
) -> tuple[VerificationStatus, str, Any]:
    if set(data) != {"left_expression", "right_expression"}:
        return VerificationStatus.UNKNOWN, "certified equality input schema is closed", None
    try:
        left = _certified_expression_value(data["left_expression"])
        right = _certified_expression_value(data["right_expression"])
    except (SyntaxError, ValueError, ZeroDivisionError):
        return VerificationStatus.UNKNOWN, "invalid certified arithmetic equality", None
    matched = left == right
    return (
        VerificationStatus.PASS if matched else VerificationStatus.FAIL,
        "certified arithmetic equality matched"
        if matched
        else "certified arithmetic equality differed",
        {
            "left": f"{left.numerator}/{left.denominator}",
            "right": f"{right.numerator}/{right.denominator}",
        },
    )


def _trace_constraint_consistency(
    data: Mapping[str, Any],
) -> tuple[VerificationStatus, str, Any]:
    if set(data) != {"variable", "constraints"}:
        return VerificationStatus.UNKNOWN, "trace constraint input schema is closed", None
    variable, rows = data["variable"], data["constraints"]
    if (
        not isinstance(variable, str)
        or _TRACE_VARIABLE.fullmatch(variable) is None
        or not isinstance(rows, list)
        or not 2 <= len(rows) <= 16
    ):
        return VerificationStatus.UNKNOWN, "trace constraints exceed the closed bounds", None
    solutions: set[Fraction] = set()
    try:
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _TRACE_CONSTRAINT_FIELDS:
                raise ValueError("constraint record schema is closed")
            raw_coefficient, raw_constant = row["coefficient"], row["constant"]
            if (
                not isinstance(raw_coefficient, str)
                or not isinstance(raw_constant, str)
                or len(raw_coefficient) > 128
                or len(raw_constant) > 128
            ):
                raise ValueError("constraint rational text exceeds its bound")
            coefficient = _bounded_certified(
                _canonical_rational(raw_coefficient)
            )
            constant = _bounded_certified(_canonical_rational(raw_constant))
            if coefficient == 0:
                if constant != 0:
                    return (
                        VerificationStatus.FAIL,
                        "trace constraints are jointly inconsistent",
                        {"constraint_count": len(rows)},
                    )
                continue
            solutions.add(-constant / coefficient)
    except ValueError:
        return VerificationStatus.UNKNOWN, "trace constraints require canonical rationals", None
    matched = len(solutions) <= 1
    return (
        VerificationStatus.PASS if matched else VerificationStatus.FAIL,
        "trace constraints are jointly consistent"
        if matched
        else "trace constraints are jointly inconsistent",
        {"constraint_count": len(rows)},
    )


def _numeric_provenance(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    operands, sources = data.get("operands"), data.get("sources")
    if not isinstance(operands, list) or not isinstance(sources, list):
        return VerificationStatus.UNKNOWN, "operands and sources must be lists", None
    if not operands or not sources or len(operands) > 8 or len(sources) > 64:
        return VerificationStatus.UNKNOWN, "numeric provenance input exceeds bounded non-empty lists", None
    try:
        seen = frozenset(canonical_rational(item) for item in sources)
        values = tuple(canonical_rational(item) for item in operands)
    except ValueError:
        return VerificationStatus.UNKNOWN, "numeric provenance requires canonical rationals", None
    matched = all(item in seen for item in values)
    return (VerificationStatus.PASS if matched else VerificationStatus.FAIL,
            "all operands have prompt-or-prior-result provenance" if matched else "one or more operands lack prompt-or-prior-result provenance",
            {"operands": values, "source_count": len(seen)})

_PROVENANCE_V2_FIELDS = frozenset({"value", "kind", "parents", "operator"})
_PROVENANCE_V2_SHAPES: dict[str, tuple[int, frozenset[str]]] = {
    "ROOT": (0, frozenset({"NONE"})),
    "PRIOR_RESULT": (0, frozenset({"NONE"})),
    "IDENTITY": (0, frozenset({"NONE"})),
    "LEXICAL_FACTOR": (0, frozenset({"NONE"})),
    "LEXICAL_RATIO": (1, frozenset({"RECIPROCAL"})),
    "PERCENT": (1, frozenset({"DIVIDE_100"})),
    "FRACTION_COMPONENT": (1, frozenset({"NUMERATOR", "DENOMINATOR"})),
    "ONE_STEP": (2, frozenset({"ADD", "SUB", "MUL", "DIV"})),
}


def _provenance_v2_expected(kind: str, parents: tuple[Fraction, ...], operator: str) -> Fraction | None:
    if kind in {"ROOT", "PRIOR_RESULT", "LEXICAL_FACTOR"}:
        return None
    if kind == "IDENTITY":
        return Fraction(1)
    if kind == "LEXICAL_RATIO":
        return Fraction(1, 1) / parents[0] if parents[0] else None
    if kind == "PERCENT":
        return parents[0] / 100
    if kind == "FRACTION_COMPONENT":
        return Fraction(parents[0].numerator if operator == "NUMERATOR" else parents[0].denominator)
    left, right = parents
    if operator == "ADD":
        return left + right
    if operator == "SUB":
        return left - right
    if operator == "MUL":
        return left * right
    if operator == "DIV":
        return left / right if right else None
    return None


def _numeric_provenance_v2(data: Mapping[str, Any]) -> tuple[VerificationStatus, str, Any]:
    operands, sources = data.get("operands"), data.get("sources")
    if not isinstance(operands, list) or not isinstance(sources, list):
        return VerificationStatus.UNKNOWN, "v2 operands and sources must be lists", None
    if not operands or not sources or len(operands) > 8 or len(sources) > 128:
        return VerificationStatus.UNKNOWN, "v2 numeric provenance exceeds bounded non-empty lists", None
    try:
        values = tuple(canonical_rational(item) for item in operands)
    except ValueError:
        return VerificationStatus.UNKNOWN, "v2 operands require canonical rationals", None
    admitted: set[str] = set()
    for row in sources:
        if not isinstance(row, Mapping) or set(row) != _PROVENANCE_V2_FIELDS:
            return VerificationStatus.UNKNOWN, "v2 source records use a closed schema", None
        kind, operator, parents_raw = row["kind"], row["operator"], row["parents"]
        if kind not in _PROVENANCE_V2_SHAPES or not isinstance(operator, str) or not isinstance(parents_raw, list):
            return VerificationStatus.UNKNOWN, "v2 source kind/operator/parents are invalid", None
        parent_count, allowed_operators = _PROVENANCE_V2_SHAPES[kind]
        if len(parents_raw) != parent_count or operator not in allowed_operators:
            return VerificationStatus.UNKNOWN, "v2 source derivation shape is invalid", None
        try:
            value = _canonical_rational(row["value"])
            parents = tuple(_canonical_rational(item) for item in parents_raw)
        except ValueError:
            return VerificationStatus.UNKNOWN, "v2 sources require canonical rationals", None
        expected = _provenance_v2_expected(kind, parents, operator)
        if expected is not None and value != expected:
            return VerificationStatus.FAIL, "v2 source derivation does not rederive mechanically", None
        if kind == "LEXICAL_FACTOR" and (value.denominator != 1 or not 2 <= abs(value.numerator) <= 10):
            return VerificationStatus.FAIL, "v2 lexical factor is outside the closed range", None
        admitted.add(f"{value.numerator}/{value.denominator}")
    matched = all(item in admitted for item in values)
    return (
        VerificationStatus.PASS if matched else VerificationStatus.FAIL,
        "all operands have bounded structured provenance" if matched else "one or more operands lack bounded structured provenance",
        {"operands": values, "source_count": len(admitted)},
    )

_BUILTINS: dict[str, tuple[VerifierSpec, Adapter]] = {
    "builtin.exact_arithmetic": (VerifierSpec("builtin.exact_arithmetic", "1", "egrt.builtin", ("expression", "expected")), _exact_arithmetic),
    "builtin.json_exact": (VerifierSpec("builtin.json_exact", "1", "egrt.builtin", ("actual", "expected")), _json_exact),
    "builtin.digest_exact": (VerifierSpec("builtin.digest_exact", "1", "egrt.builtin", ("value", "expected_digest")), _digest_exact),
    "builtin.exact_match": (VerifierSpec("builtin.exact_match", "1", "egrt.builtin", ("actual", "expected")), _exact_match),
    "builtin.numeric_tolerance": (VerifierSpec("builtin.numeric_tolerance", "1", "egrt.builtin", ("actual", "expected", "tolerance")), _numeric_tolerance),
    "builtin.numeric_provenance": (VerifierSpec("builtin.numeric_provenance", "1", "egrt.builtin", ("operands", "sources")), _numeric_provenance),
    "builtin.numeric_provenance_v2": (VerifierSpec("builtin.numeric_provenance_v2", "2", "egrt.builtin", ("operands", "sources")), _numeric_provenance_v2),
    "builtin.certified_arithmetic_equality": (
        VerifierSpec(
            "builtin.certified_arithmetic_equality",
            "1",
            "egrt.builtin",
            ("left_expression", "right_expression"),
        ),
        _certified_arithmetic_equality,
    ),
    "builtin.trace_constraint_consistency": (
        VerifierSpec(
            "builtin.trace_constraint_consistency",
            "1",
            "egrt.builtin",
            ("variable", "constraints"),
        ),
        _trace_constraint_consistency,
    ),
}


class DeterministicVerifierRegistry:
    """A closed registry: callers can resolve/run, never register arbitrary code."""

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(_BUILTINS))

    @property
    def module_digest(self) -> str:
        """Digest the complete built-in implementation module."""

        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    @property
    def environment_digest(self) -> str:
        """Bind receipts to the interpreter and verifier module actually used."""

        return digest(
            {
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
                "verifier_module_sha256": self.module_digest,
            }
        )

    def implementation_digest(self, verifier_id: str) -> str:
        """Content-bind one registered entry point and all module helpers it uses."""

        self.resolve(verifier_id)
        adapter = _BUILTINS[verifier_id][1]
        return digest(
            {
                "module_sha256": self.module_digest,
                "callable": adapter.__qualname__,
            }
        )

    def resolve(self, verifier_id: str) -> VerifierSpec:
        _require_text("verifier_id", verifier_id)
        try:
            return _BUILTINS[verifier_id][0]
        except KeyError as exc:
            raise KeyError(f"unregistered verifier: {verifier_id}") from exc

    def run(self, verifier_id: str, data: Mapping[str, Any]) -> VerifierResult:
        spec = self.resolve(verifier_id)
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        missing = [key for key in spec.input_keys if key not in data]
        if missing:
            status, reason, output = VerificationStatus.UNKNOWN, f"missing required input: {','.join(missing)}", None
        else:
            status, reason, output = _BUILTINS[verifier_id][1](data)
        return VerifierResult(
            verifier_id=spec.verifier_id,
            verifier_version=spec.version,
            provenance_group=spec.provenance_group,
            status=status,
            reason=reason,
            input_digest=digest(dict(data)),
            output_digest=digest(output),
        )

    def register(self, *_: object, **__: object) -> None:
        raise TypeError("the deterministic verifier registry is closed")


DEFAULT_REGISTRY = DeterministicVerifierRegistry()
