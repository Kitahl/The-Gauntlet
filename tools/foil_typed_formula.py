"""Typed, non-commutative formula comparison for source-bound equations.

The parser intentionally supports a small algebraic language.  Addition is
canonicalized as commutative; multiplication, inverse scope, and the AVG
operator remain ordered/typed.  Unsupported syntax and conflicting source
formulae decline rather than being guessed through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FormulaStatus(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    DIFFERENT = "DIFFERENT"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class FormulaNode:
    kind: str
    value: str = ""
    children: tuple["FormulaNode", ...] = ()

    @property
    def canonical(self) -> str:
        if self.kind in {"SYM", "NUM"}:
            return f"{self.kind}({self.value})"
        children = list(self.children)
        if self.kind == "ADD":
            flattened: list[FormulaNode] = []
            for child in children:
                flattened.extend(child.children if child.kind == "ADD" else (child,))
            return "ADD(" + ",".join(sorted(item.canonical for item in flattened)) + ")"
        if self.kind == "MUL":
            flattened = []
            for child in children:
                flattened.extend(child.children if child.kind == "MUL" else (child,))
            return "MUL(" + ",".join(item.canonical for item in flattened) + ")"
        return self.kind + "(" + ",".join(item.canonical for item in children) + ")"


@dataclass(frozen=True)
class FormulaTask:
    target: str
    reason: str


@dataclass(frozen=True)
class ExtractedFormula:
    raw: str
    target: str
    tree: FormulaNode
    start_offset: int
    end_offset: int

    @property
    def canonical(self) -> str:
        return self.tree.canonical


@dataclass(frozen=True)
class FormulaComparison:
    status: FormulaStatus
    reason: str
    candidate: ExtractedFormula | None = None
    reference: ExtractedFormula | None = None


_FORMULA_TASK = re.compile(
    r"\b(?:what\s+is|give|state|write|derive)\s+(?:the\s+)?"
    r"(?:expression|formula|equation)\s+(?:of|for)\s+"
    r"(?P<target>[A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?)\b",
    re.IGNORECASE,
)
_MATH_DELIMITERS = re.compile(
    r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)|\$(.+?)\$",
    re.DOTALL,
)
_IDENTIFIER = r"(?:AVG|[A-Za-z]_[A-Za-z0-9]|[A-Z][a-z0-9]*|[a-z][a-z0-9_]*)"
_TOKEN = re.compile(_IDENTIFIER + r"|\d+(?:\.\d+)?|[()+\-*/^=,]")


def _symbol(value: str) -> str:
    return value.replace("_", "")


def discover_formula_task(question: str) -> FormulaTask | None:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    match = _FORMULA_TASK.search(question)
    if match is None:
        return None
    return FormulaTask(_symbol(match.group("target").replace("{", "").replace("}", "")), "NAMED_FORMULA_EXPRESSION")


def _prepare(source: str) -> str:
    value = source.strip()
    value = re.sub(r"^\s*(?:\\\(|\\\[|\$\$?|`)+|(?:\\\)|\\\]|\$\$?|`)+\s*$", "", value)
    value = value.replace("\\left", "").replace("\\right", "")
    value = value.replace("\\cdot", "*").replace("\\times", "*")
    value = re.sub(r"\\(?:mathrm|mathbf|mathsf|boldsymbol)\s*\{([^{}]+)\}", r"\1", value)
    value = re.sub(r"([A-Za-z])_\{([A-Za-z0-9]+)\}", r"\1_\2", value)
    value = re.sub(r"\\langle\s*([^{}<>]+?)\s*\\rangle", r"AVG(\1)", value)
    value = re.sub(r"<\s*([^<>]+?)\s*>", r"AVG(\1)", value)
    value = value.replace("^{-1}", "^(-1)")
    value = value.replace("{", "(").replace("}", ")")
    value = value.replace("\\", "")
    return value


class _Parser:
    def __init__(self, source: str):
        prepared = _prepare(source)
        self.tokens = _TOKEN.findall(prepared)
        compact = re.sub(r"\s+", "", prepared)
        if not self.tokens or "".join(self.tokens) != compact:
            raise ValueError("formula contains unsupported syntax")
        self.index = 0

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError("unexpected formula token")
        self.index += 1
        return token

    def parse(self) -> FormulaNode:
        left = self.sum()
        if self.peek() == "=":
            self.take("=")
            node = FormulaNode("EQ", children=(left, self.sum()))
        else:
            node = left
        if self.peek() is not None:
            raise ValueError("trailing formula token")
        return node

    def sum(self) -> FormulaNode:
        node = self.product()
        while self.peek() in {"+", "-"}:
            operation = self.take()
            right = self.product()
            if operation == "-":
                right = FormulaNode("NEG", children=(right,))
            node = FormulaNode("ADD", children=(node, right))
        return node

    def product(self) -> FormulaNode:
        node = self.power()
        while True:
            token = self.peek()
            if token in {"*", "/"}:
                operation = self.take()
                right = self.power()
                node = FormulaNode("MUL" if operation == "*" else "DIV", children=(node, right))
                continue
            if token is not None and (token == "(" or re.fullmatch(_IDENTIFIER + r"|\d+(?:\.\d+)?", token)):
                node = FormulaNode("MUL", children=(node, self.power()))
                continue
            return node

    def power(self) -> FormulaNode:
        node = self.unary()
        if self.peek() == "^":
            self.take("^")
            node = FormulaNode("POW", children=(node, self.unary()))
        return node

    def unary(self) -> FormulaNode:
        if self.peek() in {"+", "-"}:
            operation = self.take()
            node = self.unary()
            return node if operation == "+" else FormulaNode("NEG", children=(node,))
        return self.atom()

    def atom(self) -> FormulaNode:
        token = self.take()
        if token == "(":
            node = self.sum()
            self.take(")")
            return node
        if token == "AVG":
            self.take("(")
            node = self.sum()
            self.take(")")
            return FormulaNode("AVG", children=(node,))
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            return FormulaNode("NUM", token)
        if re.fullmatch(_IDENTIFIER, token):
            return FormulaNode("SYM", _symbol(token))
        raise ValueError("unsupported formula atom")


def parse_formula(source: str) -> FormulaNode:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("formula must be non-empty text")
    return _Parser(source).parse()


def _candidate_segments(text: str, target: str) -> list[tuple[str, int, int]]:
    segments: list[tuple[str, int, int]] = []
    for match in _MATH_DELIMITERS.finditer(text):
        raw = next(group for group in match.groups() if group is not None)
        segments.append((raw, match.start(), match.end()))
    escaped_target = re.escape(target)
    for match in re.finditer(rf"(?<![A-Za-z0-9_]){escaped_target}\s*=", text):
        tail = text[match.start():]
        raw = re.split(r"[;\n]", tail, maxsplit=1)[0].strip().rstrip(".")
        segments.append((raw, match.start(), match.start() + len(raw)))
    if not segments:
        segments.append((text.strip(), 0, len(text)))
    return segments


def extract_target_formulas(text: str, target: str) -> tuple[ExtractedFormula, ...]:
    wanted = _symbol(target)
    found: dict[str, ExtractedFormula] = {}
    for raw, start, end in _candidate_segments(text, wanted):
        try:
            tree = parse_formula(raw)
        except ValueError:
            continue
        if tree.kind != "EQ" or tree.children[0].kind != "SYM" or tree.children[0].value != wanted:
            continue
        item = ExtractedFormula(raw.strip(), wanted, tree, start, end)
        found.setdefault(item.canonical, item)
    return tuple(found[key] for key in sorted(found))


def compare_formula(candidate_text: str, reference_texts: tuple[str, ...], target: str) -> FormulaComparison:
    candidates = extract_target_formulas(candidate_text, target)
    references: dict[str, ExtractedFormula] = {}
    for text in reference_texts:
        for item in extract_target_formulas(text, target):
            references.setdefault(item.canonical, item)
    if len(references) > 1:
        return FormulaComparison(FormulaStatus.AMBIGUOUS, "conflicting_reference_formulas")
    if len(references) != 1 or len(candidates) != 1:
        return FormulaComparison(FormulaStatus.UNSUPPORTED, "formula_not_uniquely_parseable")
    candidate = candidates[0]
    reference = next(iter(references.values()))
    if candidate.canonical == reference.canonical:
        return FormulaComparison(FormulaStatus.EQUIVALENT, "typed_formula_structure_matches", candidate, reference)
    return FormulaComparison(FormulaStatus.DIFFERENT, "typed_formula_structure_differs", candidate, reference)


def unique_reference_formula(
    reference_texts: tuple[str, ...],
    target: str,
) -> ExtractedFormula | None:
    """Return one structurally unique source equation, else decline."""

    references: dict[str, ExtractedFormula] = {}
    for text in reference_texts:
        for item in extract_target_formulas(text, target):
            references.setdefault(item.canonical, item)
    return next(iter(references.values())) if len(references) == 1 else None
