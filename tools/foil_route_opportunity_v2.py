"""Task-only route opportunity discovery for the reusable FOIL v2 runtime.

The selector sees only a closed ``task_id``/``question`` input.  It names a
small, cheapest-first capability frontier; it does not inspect A0, correctness,
gold, profile state, or prior route outcomes.  Applicability is only a proposal
until the corresponding host adapter probes the task.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from egrt_types import digest
from foil_certified_arithmetic import UnsupportedExpression, evaluate_exact, normalize_expression
from foil_formal_decidability import derive_formal_decidability_proof
from foil_typed_formula import discover_formula_task


QUESTION_SCHEMA_V2 = "foil.question-only-route-input.v2"
OPPORTUNITY_SCHEMA_V2 = "foil.route-opportunity.v2"
_FIELDS = frozenset({"schema", "task_id", "question"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeToolFamily(str, Enum):
    EXACT_ARITHMETIC = "EXACT_ARITHMETIC"
    RESTRICTED_PYTHON = "RESTRICTED_PYTHON"
    SYMBOLIC_COMPUTATION = "SYMBOLIC_COMPUTATION"
    PASSAGE_RETRIEVAL = "PASSAGE_RETRIEVAL"
    FORMAL_DECIDABILITY = "FORMAL_DECIDABILITY"


class OpportunityStatusV2(str, Enum):
    FOUND = "FOUND"
    COVERAGE_GAP = "COVERAGE_GAP"


class ComplexityBand(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_COST_ORDER = {
    RuntimeToolFamily.EXACT_ARITHMETIC: 0,
    RuntimeToolFamily.RESTRICTED_PYTHON: 1,
    RuntimeToolFamily.SYMBOLIC_COMPUTATION: 2,
    RuntimeToolFamily.PASSAGE_RETRIEVAL: 3,
    RuntimeToolFamily.FORMAL_DECIDABILITY: -1,
}


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _strict(raw: Mapping[str, object]) -> None:
    actual = frozenset(raw)
    if actual != _FIELDS:
        raise ValueError(
            f"closed route-input schema mismatch: missing={sorted(_FIELDS - actual)}, "
            f"unknown={sorted(actual - _FIELDS)}"
        )


@dataclass(frozen=True)
class QuestionOnlyTaskV2:
    task_id: str
    question: str
    schema: str = QUESTION_SCHEMA_V2

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "QuestionOnlyTaskV2":
        if not isinstance(raw, Mapping):
            raise TypeError("route input must be a mapping")
        _strict(raw)
        if raw["schema"] != QUESTION_SCHEMA_V2:
            raise ValueError("unsupported route-input schema")
        return cls(_text("task_id", raw["task_id"]), _text("question", raw["question"]))

    @property
    def question_digest(self) -> str:
        return digest(self.question)


@dataclass(frozen=True)
class RouteCandidateV2:
    family: RuntimeToolFamily
    reason_code: str
    complexity: ComplexityBand

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", RuntimeToolFamily(self.family))
        object.__setattr__(self, "complexity", ComplexityBand(self.complexity))
        _text("reason_code", self.reason_code)

    @property
    def cost_rank(self) -> int:
        return _COST_ORDER[self.family]

    def trace(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "reason_code": self.reason_code,
            "complexity": self.complexity.value,
            "cost_rank": self.cost_rank,
            "requires_runtime_probe": True,
            "question_structure_only": True,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class RouteOpportunityV2:
    task_id: str
    question_digest: str
    status: OpportunityStatusV2
    candidates: tuple[RouteCandidateV2, ...]
    schema: str = OPPORTUNITY_SCHEMA_V2

    def __post_init__(self) -> None:
        _text("task_id", self.task_id)
        if self.schema != OPPORTUNITY_SCHEMA_V2:
            raise ValueError("unsupported route-opportunity schema")
        if not isinstance(self.question_digest, str) or _SHA256.fullmatch(self.question_digest) is None:
            raise ValueError("question_digest must be lowercase SHA-256")
        object.__setattr__(self, "status", OpportunityStatusV2(self.status))
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(item, RouteCandidateV2) for item in self.candidates
        ):
            raise TypeError("candidates must be a RouteCandidateV2 tuple")
        if self.status is OpportunityStatusV2.FOUND and not self.candidates:
            raise ValueError("FOUND requires a candidate")
        if self.status is OpportunityStatusV2.COVERAGE_GAP and self.candidates:
            raise ValueError("COVERAGE_GAP cannot carry candidates")
        families = [item.family for item in self.candidates]
        if len(families) != len(set(families)):
            raise ValueError("candidate families must be unique")
        if list(self.candidates) != sorted(self.candidates, key=lambda item: item.cost_rank):
            raise ValueError("candidates must be cheapest-first")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": self.schema,
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "status": self.status.value,
            "candidates": [item.trace() for item in self.candidates],
            "question_only": True,
            "a0_observed": False,
            "gold_observed": False,
            "profile_observed": False,
            "execution_authorized": False,
            "promotion_authorized": False,
        }
        body["opportunity_sha256"] = digest(body)
        return body


_MATH_SPAN = re.compile(r"\\\((.*?)\\\)|\$(.*?)\$", re.DOTALL)
_EXPLICIT_ARITHMETIC_REQUEST = re.compile(
    r"\b(?:compute|calculate|evaluate)\b",
    re.IGNORECASE,
)
_WHAT_IS_MATH = re.compile(
    r"\bwhat\s+is\s+(?:the\s+(?:exact\s+)?(?:value|result)\s+of\s+)?\s*(?:\\\(|\$)",
    re.IGNORECASE,
)
_PLAIN_COMPUTE = re.compile(
    r"\b(?:compute|calculate|evaluate)\s+(?:the\s+value\s+of\s+)?(.+?)(?:\?|\.$|$)",
    re.IGNORECASE | re.DOTALL,
)
_PYTHON_BLOCK = re.compile(r"```python\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_SYMBOLIC = re.compile(
    r"\b(?:solve|simplify|factor|expand|differentiate|integrate)\b",
    re.IGNORECASE,
)
_RETRIEVAL = re.compile(
    r"\b(?:who|when|where|which|cite|source|according to|current|latest|version|"
    r"published|paper|law|regulation|statute|historical|official)\b",
    re.IGNORECASE,
)


def closed_answer_expression_v2(question: str) -> str | None:
    """Return one exact expression only when the question asks for its value.

    Mathematical notation inside a question is not automatically the answer
    obligation. In particular, a categorical question may mention a number
    such as ``$5$`` without asking the respondent to compute five. This parser
    therefore requires an explicit arithmetic request before a delimited math
    span can become an answer-producing route.
    """

    values: list[str] = []
    if _EXPLICIT_ARITHMETIC_REQUEST.search(question) or _WHAT_IS_MATH.search(question):
        for match in _MATH_SPAN.finditer(question):
            source = next(value for value in match.groups() if value is not None)
            try:
                evaluate_exact(source)
            except UnsupportedExpression:
                continue
            values.append(normalize_expression(source))
    plain = _PLAIN_COMPUTE.search(question)
    if plain is not None:
        source = plain.group(1).strip()
        try:
            evaluate_exact(source)
        except UnsupportedExpression:
            pass
        else:
            values.append(normalize_expression(source))
    unique = set(values)
    return next(iter(unique)) if len(unique) == 1 else None


def _restricted_python(question: str) -> bool:
    blocks = _PYTHON_BLOCK.findall(question)
    if len(blocks) != 1:
        return False
    try:
        tree = ast.parse(blocks[0].strip(), mode="exec")
    except SyntaxError:
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    value = tree.body[0].value
    return bool(
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "print"
        and len(value.args) == 1
        and not value.keywords
    )


def _complexity(question: str, family: RuntimeToolFamily) -> ComplexityBand:
    adjusted = len(question) + (80 if family is RuntimeToolFamily.PASSAGE_RETRIEVAL else 0)
    if adjusted <= 120:
        return ComplexityBand.LOW
    if adjusted <= 500:
        return ComplexityBand.MEDIUM
    return ComplexityBand.HIGH


def discover_route_opportunity_v2(raw: Mapping[str, object]) -> RouteOpportunityV2:
    """Return a frozen, question-only, cheapest-first capability frontier."""

    task = QuestionOnlyTaskV2.from_mapping(raw)
    found: dict[RuntimeToolFamily, str] = {}
    if derive_formal_decidability_proof(task.question) is not None:
        found[RuntimeToolFamily.FORMAL_DECIDABILITY] = "CLOSED_TOTAL_LANGUAGE_DECIDABILITY_PROOF"
    if closed_answer_expression_v2(task.question) is not None:
        found[RuntimeToolFamily.EXACT_ARITHMETIC] = "UNIQUE_CLOSED_ARITHMETIC_EXPRESSION"
    if _restricted_python(task.question):
        found[RuntimeToolFamily.RESTRICTED_PYTHON] = "SINGLE_RESTRICTED_PYTHON_PRINT"
    if _SYMBOLIC.search(task.question):
        found[RuntimeToolFamily.SYMBOLIC_COMPUTATION] = "EXPLICIT_SYMBOLIC_OPERATION"
    formula_task = discover_formula_task(task.question)
    if formula_task is not None:
        found[RuntimeToolFamily.PASSAGE_RETRIEVAL] = "NAMED_FORMULA_LOOKUP"
    elif _RETRIEVAL.search(task.question):
        found[RuntimeToolFamily.PASSAGE_RETRIEVAL] = "FACT_OR_SOURCE_LOOKUP"

    candidates = tuple(
        RouteCandidateV2(family, found[family], _complexity(task.question, family))
        for family in sorted(found, key=lambda item: _COST_ORDER[item])
    )
    status = OpportunityStatusV2.FOUND if candidates else OpportunityStatusV2.COVERAGE_GAP
    return RouteOpportunityV2(task.task_id, task.question_digest, status, candidates)
