"""Closed, deterministic, in-process verifier registry.

The registry intentionally offers only pure built-ins.  It contains no network,
shell, subprocess, dynamic import, or provider execution surface.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
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


_BUILTINS: dict[str, tuple[VerifierSpec, Adapter]] = {
    "builtin.exact_arithmetic": (VerifierSpec("builtin.exact_arithmetic", "1", "egrt.builtin", ("expression", "expected")), _exact_arithmetic),
    "builtin.json_exact": (VerifierSpec("builtin.json_exact", "1", "egrt.builtin", ("actual", "expected")), _json_exact),
    "builtin.digest_exact": (VerifierSpec("builtin.digest_exact", "1", "egrt.builtin", ("value", "expected_digest")), _digest_exact),
    "builtin.exact_match": (VerifierSpec("builtin.exact_match", "1", "egrt.builtin", ("actual", "expected")), _exact_match),
    "builtin.numeric_tolerance": (VerifierSpec("builtin.numeric_tolerance", "1", "egrt.builtin", ("actual", "expected", "tolerance")), _numeric_tolerance),
}


class DeterministicVerifierRegistry:
    """A closed registry: callers can resolve/run, never register arbitrary code."""

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(_BUILTINS))

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
