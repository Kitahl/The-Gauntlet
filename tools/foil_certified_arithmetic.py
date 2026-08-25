"""Exact arithmetic checks for a deliberately small LaTeX language.

Supported language (``certified-v2``)
-------------------------------------
The checker accepts only an entire, explicitly delimited LaTeX math span whose
top-level form is a chain of two or more numeric expressions joined by ``=``.
Expressions may contain:

* base-10 integers and finite decimals (commas are allowed only as thousands
  separators);
* unary ``+``/``-`` and explicit ``+``, ``-``, ``*``, ``/``, ``\\times``,
  ``\\cdot``, and ``\\div`` operators;
* explicit parentheses and ``\\frac{...}{...}``/``\\dfrac``/``\\tfrac``;
* transparent ``\\boxed{...}``, ``\\left`` and ``\\right`` wrappers.

Everything else is outside the language and is ``NOT_APPLICABLE``.  In
particular the checker rejects variables or assignments, implicit
multiplication, roots and transcendental constants, units/text/currency,
percent notation, powers, congruences/moduli, approximations, inequalities, ranges,
sets, and any candidate that crosses a math-span boundary.  Values are
evaluated as :class:`fractions.Fraction`; there is no floating-point tolerance.
The surrounding step must also be assertive: a closed lexical exclusion rejects
explicit approximations, quotient/remainder descriptions, trial assumptions,
and displayed counterexamples.  Finally, unequal division-to-number displays
are skipped when the exact quotient has a non-terminating base-10 expansion,
because the notation cannot distinguish rounding from exact assertion.

``audit-legacy-v0`` is retained only to reproduce and diagnose the permissive
extractor that motivated P0.5.  It must never be used for an authority decision.
The public :func:`check` function always uses the frozen ``certified-v2`` rule.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

CERTIFIED_V1_LANGUAGE = "certified-v1"
ASSERTIVE_LANGUAGE = "certified-v1-assertive"
DIVISION_SAFE_LANGUAGE = "certified-v1-division-safe"
CERTIFIED_LANGUAGE = "certified-v2"
POWER_LANGUAGE = "numeric-power-equality-v1"
RAW_NUMERIC_LANGUAGE = "raw-numeric-equality-v1"
AUDIT_LANGUAGE = "audit-legacy-v0"
MAX_MATH_SPAN_CHARS = 2_000
MAX_RAW_LINES = 128
MAX_AST_NODES = 128
MAX_POWER = 12
MAX_ABS_NUMERATOR = 10**18
MAX_DENOMINATOR = 10**12

_MATH_SPAN = re.compile(
    r"(?P<display>\\\[(?P<display_body>.*?)\\\])"
    r"|(?P<inline>\\\((?P<inline_body>.*?)\\\))"
    r"|(?P<double>\$\$(?P<double_body>.*?)\$\$)"
    r"|(?P<single>(?<!\\)\$(?P<single_body>.*?)(?<!\\)\$)",
    re.DOTALL,
)
_FORBIDDEN_CONTEXT = re.compile(
    r"\\(?:approx|sim|simeq|cong|equiv|pmod|mod|text|mathrm|operatorname|"
    r"begin|end|in|leq|geq|neq|ne|lt|gt|%|sqrt|pi|infty)\b"
    r"|[<>≈≃≅≡≤≥≠%]|\\[{}]",
    re.IGNORECASE,
)
_LATEX_COMMAND = re.compile(r"\\[A-Za-z]+")
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")
_NUMBER = r"(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)"
_LEGACY_TEXT = re.compile(r"\\(?:text|mathrm)\{[^{}]*\}", re.IGNORECASE)
_NON_ASSERTIVE_CONTEXT = re.compile(
    r"\b(?:approximat(?:e|ely|ion)|rounded?|rounding|remainder|false|"
    r"not divisible|does not work|check if|suppose|assume)\b"
    r"|\b(?:does not|doesn't|doesnt|not)\s+(?:equal|equate)\b"
    r"|\b(?:let us|let's|lets|we)\s+try\b|\btry\s+(?:another|a different)\b",
    re.IGNORECASE,
)
_RAW_LIST_PREFIX = re.compile(r"^\s*(?:(?:[-*+])|(?:\d{1,3}[.)]))\s+")
_RAW_NUMERIC_BODY = re.compile(r"[\d.,\s()+\-*/=]+")


class UnsupportedExpression(ValueError):
    """Raised when text is outside the declared arithmetic language."""


@dataclass(frozen=True)
class MathSpan:
    source: str
    body: str
    start: int
    end: int


@dataclass(frozen=True)
class EqualityFinding:
    language: str
    step_index: int
    source_span: str
    left_source: str
    right_source: str
    left_value: Fraction
    right_value: Fraction

    @property
    def violating(self) -> bool:
        return self.left_value != self.right_value

    def to_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "step_index": self.step_index,
            "source_span": self.source_span,
            "left_source": self.left_source,
            "right_source": self.right_source,
            "left_value": _fraction_text(self.left_value),
            "right_value": _fraction_text(self.right_value),
            "violating": self.violating,
        }


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _math_spans(text: str) -> tuple[MathSpan, ...]:
    if not isinstance(text, str):
        raise TypeError("solution text must be str")
    spans: list[MathSpan] = []
    for match in _MATH_SPAN.finditer(text):
        body = next(
            value
            for value in (
                match.group("display_body"),
                match.group("inline_body"),
                match.group("double_body"),
                match.group("single_body"),
            )
            if value is not None
        )
        if len(body) <= MAX_MATH_SPAN_CHARS:
            spans.append(MathSpan(match.group(0), body, match.start(), match.end()))
    return tuple(spans)


def _balanced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise UnsupportedExpression("expected braced group")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise UnsupportedExpression("unbalanced braces")


def _rewrite_command_groups(text: str) -> str:
    """Rewrite the few declared structural commands without interpreting prose."""

    result: list[str] = []
    index = 0
    while index < len(text):
        matched = False
        for command in (r"\boxed", r"\frac", r"\dfrac", r"\tfrac"):
            if not text.startswith(command, index):
                continue
            cursor = index + len(command)
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            first, cursor = _balanced_group(text, cursor)
            if command == r"\boxed":
                result.append("(" + _rewrite_command_groups(first) + ")")
            else:
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
                second, cursor = _balanced_group(text, cursor)
                result.append(
                    "(("
                    + _rewrite_command_groups(first)
                    + ")/("
                    + _rewrite_command_groups(second)
                    + "))"
                )
            index = cursor
            matched = True
            break
        if matched:
            continue
        result.append(text[index])
        index += 1
    return "".join(result)


def _normalize_expression(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise UnsupportedExpression("empty expression")
    text = source.strip()
    if _FORBIDDEN_CONTEXT.search(text):
        raise UnsupportedExpression("forbidden context")
    text = text.replace(r"\left", "").replace(r"\right", "")
    text = text.replace(r"\times", "*").replace(r"\cdot", "*")
    text = text.replace(r"\div", "/")
    text = re.sub(r"\\[,!;:]", "", text)
    text = text.replace("~", "")
    text = _rewrite_command_groups(text)
    text = re.sub(r"\^\s*\{\s*([+-]?\d+)\s*\}", r"**(\1)", text)
    text = re.sub(r"\^\s*([+-]?\d+)", r"**(\1)", text)
    text = _THOUSANDS_COMMA.sub("", text)
    if "," in text:
        raise UnsupportedExpression("comma outside thousands separator")
    if _LATEX_COMMAND.search(text) or re.search(r"[A-Za-z]", text):
        raise UnsupportedExpression("symbolic or unknown command")
    if "{" in text or "}" in text or "[" in text or "]" in text:
        raise UnsupportedExpression("unsupported grouping")
    if re.search(r"\d\s*\(", text) or re.search(r"\)\s*\d", text):
        raise UnsupportedExpression("implicit multiplication")
    if re.search(r"\)\s*\(", text):
        raise UnsupportedExpression("implicit multiplication")
    if re.search(r"\d\s+\d", text):
        raise UnsupportedExpression("adjacent numbers")
    if not re.fullmatch(r"[\d.\s()+\-*/]*", text):
        raise UnsupportedExpression("unsupported token")
    return text


def _bounded(value: Fraction) -> Fraction:
    if abs(value.numerator) > MAX_ABS_NUMERATOR or value.denominator > MAX_DENOMINATOR:
        raise UnsupportedExpression("numeric bound exceeded")
    return value


def _eval_node(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsupportedExpression("non-numeric literal")
        if isinstance(node.value, int):
            return _bounded(Fraction(node.value))
        return _bounded(Fraction(str(node.value)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        try:
            if isinstance(node.op, ast.Add):
                return _bounded(left + right)
            if isinstance(node.op, ast.Sub):
                return _bounded(left - right)
            if isinstance(node.op, ast.Mult):
                return _bounded(left * right)
            if isinstance(node.op, ast.Div):
                return _bounded(left / right)
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1 or not 0 <= right.numerator <= MAX_POWER:
                    raise UnsupportedExpression("power outside declared bound")
                return _bounded(left**right.numerator)
        except ZeroDivisionError as exc:
            raise UnsupportedExpression("division by zero") from exc
    raise UnsupportedExpression("unsupported AST node")


def evaluate_exact(source: str) -> Fraction:
    normalized = _normalize_expression(source)
    try:
        tree = ast.parse(normalized, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise UnsupportedExpression("invalid expression") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise UnsupportedExpression("AST bound exceeded")
    return _eval_node(tree)


def normalize_expression(source: str) -> str:
    """Return the closed normalized expression consumed by the exact verifier."""

    return _normalize_expression(source)


def _top_level_equalities(body: str) -> tuple[str, ...]:
    parts: list[str] = []
    start = 0
    paren_depth = 0
    brace_depth = 0
    for index, char in enumerate(body):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == "=" and paren_depth == 0 and brace_depth == 0:
            parts.append(body[start:index])
            start = index + 1
        if paren_depth < 0 or brace_depth < 0:
            return ()
    if not parts or paren_depth or brace_depth:
        return ()
    parts.append(body[start:])
    return tuple(parts)


def _has_nonterminating_decimal(value: Fraction) -> bool:
    denominator = value.denominator
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    return denominator != 1


def _division_decimal_ambiguity(
    left_source: str,
    right_source: str,
    left_value: Fraction,
    right_value: Fraction,
) -> bool:
    """Reject quotient displays that could be rounded or integer division."""

    left_division = "/" in left_source or r"\div" in left_source or r"\frac" in left_source
    right_division = "/" in right_source or r"\div" in right_source or r"\frac" in right_source
    if left_division == right_division:
        return False
    quotient = left_value if left_division else right_value
    displayed = right_source if left_division else left_source
    return _has_nonterminating_decimal(quotient) and re.search(r"\d", displayed) is not None


def _certified_from_span(
    span: MathSpan,
    step_index: int,
    *,
    step_text: str,
    language: str,
) -> tuple[EqualityFinding, ...]:
    if _FORBIDDEN_CONTEXT.search(span.body):
        return ()
    if language in {
        ASSERTIVE_LANGUAGE,
        DIVISION_SAFE_LANGUAGE,
        CERTIFIED_LANGUAGE,
        POWER_LANGUAGE,
    }:
        if _NON_ASSERTIVE_CONTEXT.search(step_text):
            return ()
    if language == CERTIFIED_LANGUAGE and "^" in span.body:
        return ()
    if language == POWER_LANGUAGE and "^" not in span.body:
        return ()
    parts = _top_level_equalities(span.body)
    if len(parts) < 2:
        return ()
    try:
        values = tuple(evaluate_exact(part) for part in parts)
    except UnsupportedExpression:
        return ()
    findings: list[EqualityFinding] = []
    for left, right, left_value, right_value in zip(parts, parts[1:], values, values[1:]):
        if language in {
            DIVISION_SAFE_LANGUAGE,
            CERTIFIED_LANGUAGE,
            POWER_LANGUAGE,
        } and _division_decimal_ambiguity(
            left, right, left_value, right_value
        ):
            continue
        findings.append(
            EqualityFinding(
                language,
                step_index,
                span.source,
                left.strip(),
                right.strip(),
                left_value,
                right_value,
            )
        )
    return tuple(findings)


def _legacy_fragment(side: str) -> str | None:
    """Mimic the prior LaTeX-aware unit stripping for audit reproduction only."""

    fragment = side
    previous = None
    while previous != fragment:
        previous = fragment
        fragment = _LEGACY_TEXT.sub("", fragment)
    fragment = fragment.replace(r"\$", "")
    fragment = re.sub(r"(\d+(?:\.\d+)?)\s*\\%", r"(\1/100)", fragment)
    fragment = fragment.replace("&", "").replace(r"\\", " ").strip()
    return fragment or None


def _audit_from_span(span: MathSpan, step_index: int) -> tuple[EqualityFinding, ...]:
    """Permissive benchmark-only extraction used to enumerate parser defects."""

    parts = span.body.split("=")
    if len(parts) < 2:
        return ()
    findings: list[EqualityFinding] = []
    for left_side, right_side in zip(parts, parts[1:]):
        left = _legacy_fragment(left_side)
        right = _legacy_fragment(right_side)
        if left is None or right is None:
            continue
        try:
            left_value = evaluate_exact(left)
            right_value = evaluate_exact(right)
        except UnsupportedExpression:
            continue
        findings.append(
            EqualityFinding(
                AUDIT_LANGUAGE,
                step_index,
                span.source,
                left,
                right,
                left_value,
                right_value,
            )
        )
    return tuple(findings)


def _raw_numeric_from_text(
    step_text: str, step_index: int
) -> tuple[EqualityFinding, ...]:
    """Recognize only complete undelimited numeric-equality lines.

    Arbitrary prose fragments are never scanned.  A line may have only a
    Markdown bullet/ordinal prefix followed by the closed numeric grammar.
    """

    findings: list[EqualityFinding] = []
    lines = step_text.splitlines() or [step_text]
    if len(lines) > MAX_RAW_LINES:
        return ()
    for line in lines:
        if len(line) > MAX_MATH_SPAN_CHARS:
            continue
        body = _RAW_LIST_PREFIX.sub("", line, count=1).strip()
        if (
            not body
            or "^" in body
            or _RAW_NUMERIC_BODY.fullmatch(body) is None
        ):
            continue
        parts = _top_level_equalities(body)
        if len(parts) < 2:
            continue
        try:
            values = tuple(evaluate_exact(part) for part in parts)
        except UnsupportedExpression:
            continue
        for left, right, left_value, right_value in zip(
            parts, parts[1:], values, values[1:]
        ):
            if _division_decimal_ambiguity(
                left, right, left_value, right_value
            ):
                continue
            findings.append(
                EqualityFinding(
                    RAW_NUMERIC_LANGUAGE,
                    step_index,
                    line.strip(),
                    left.strip(),
                    right.strip(),
                    left_value,
                    right_value,
                )
            )
    return tuple(findings)


def extract_step(
    step_text: str,
    *,
    step_index: int,
    language: str = CERTIFIED_LANGUAGE,
) -> tuple[EqualityFinding, ...]:
    if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
        raise ValueError("step_index must be a non-negative integer")
    if language not in {
        CERTIFIED_LANGUAGE,
        DIVISION_SAFE_LANGUAGE,
        ASSERTIVE_LANGUAGE,
        CERTIFIED_V1_LANGUAGE,
        POWER_LANGUAGE,
        RAW_NUMERIC_LANGUAGE,
        AUDIT_LANGUAGE,
    }:
        raise ValueError("unknown declared language")
    if language == AUDIT_LANGUAGE:
        return tuple(
            finding
            for span in _math_spans(step_text)
            for finding in _audit_from_span(span, step_index)
        )
    if language == RAW_NUMERIC_LANGUAGE:
        return _raw_numeric_from_text(step_text, step_index)
    return tuple(
        finding
        for span in _math_spans(step_text)
        for finding in _certified_from_span(
            span,
            step_index,
            step_text=step_text,
            language=language,
        )
    )


def extract_steps(
    steps: Iterable[str], *, language: str = CERTIFIED_LANGUAGE
) -> tuple[EqualityFinding, ...]:
    if isinstance(steps, (str, bytes)):
        raise TypeError("steps must be an iterable of strings")
    findings: list[EqualityFinding] = []
    for index, step in enumerate(steps):
        if not isinstance(step, str):
            raise TypeError("each step must be str")
        findings.extend(extract_step(step, step_index=index, language=language))
    return tuple(findings)


def check(solution_text: str) -> tuple[int, int]:
    """Return ``(checkable_equalities, false_equalities)`` under certified-v2."""

    findings = extract_step(solution_text, step_index=0, language=CERTIFIED_LANGUAGE)
    return len(findings), sum(finding.violating for finding in findings)
