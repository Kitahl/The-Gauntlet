"""Four bounded host adapters for the FOIL v2 runtime."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Protocol

from egrt_types import digest
from foil_certified_arithmetic import UnsupportedExpression, evaluate_exact, normalize_expression
from foil_route_opportunity_v2 import (
    ComplexityBand,
    QuestionOnlyTaskV2,
    RuntimeToolFamily,
    closed_answer_expression_v2,
)
from foil_tool_contract_v2 import (
    BoundaryFailureCode,
    OperationSpecOrigin,
    PassageEvidenceV2,
    ResourceEnvelopeV2,
    RouteValueEstimate,
    TokenUsageV2,
    ToolContractV2,
    ToolOutcomeV2,
    ToolReceiptV2,
)


class ProbeStatusV2(str):
    APPLICABLE = "APPLICABLE"
    DECLINE = "DECLINE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ToolProbeV2:
    family: RuntimeToolFamily
    status: str
    reason: str
    operation_payload: str
    complexity: ComplexityBand
    envelope: ResourceEnvelopeV2
    value: RouteValueEstimate
    timeout_ms: int
    provider_cap_enforced: bool
    spec_origin: OperationSpecOrigin = OperationSpecOrigin.HOST_DERIVED
    formalization_admission_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", RuntimeToolFamily(self.family))
        if self.status not in {
            ProbeStatusV2.APPLICABLE, ProbeStatusV2.DECLINE, ProbeStatusV2.UNAVAILABLE
        }:
            raise ValueError("unsupported probe status")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("probe requires a reason")
        if not isinstance(self.operation_payload, str) or not self.operation_payload:
            raise ValueError("probe requires operation payload")
        object.__setattr__(self, "complexity", ComplexityBand(self.complexity))
        if not isinstance(self.envelope, ResourceEnvelopeV2):
            raise TypeError("envelope must be ResourceEnvelopeV2")
        if not isinstance(self.value, RouteValueEstimate):
            raise TypeError("value must be RouteValueEstimate")
        if isinstance(self.timeout_ms, bool) or not isinstance(self.timeout_ms, int) or self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if not isinstance(self.provider_cap_enforced, bool):
            raise TypeError("provider_cap_enforced must be bool")

    @property
    def operation_input_digest(self) -> str:
        return digest(self.operation_payload)

    def trace(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "status": self.status,
            "reason": self.reason,
            "operation_input_sha256": self.operation_input_digest,
            "complexity": self.complexity.value,
            "envelope": self.envelope.trace(),
            "value": self.value.trace(),
            "timeout_ms": self.timeout_ms,
            "provider_cap_enforced": self.provider_cap_enforced,
            "spec_origin": self.spec_origin.value,
            "formalization_admission_sha256": self.formalization_admission_digest,
            "raw_operation_stored": False,
        }


class RuntimeToolAdapterV2(Protocol):
    family: RuntimeToolFamily
    tool_id: str
    tool_version: str

    def probe(self, task: QuestionOnlyTaskV2) -> ToolProbeV2: ...

    def execute(
        self, contract: ToolContractV2, task: QuestionOnlyTaskV2, probe: ToolProbeV2
    ) -> ToolReceiptV2: ...


class ToolBoundaryFailure(RuntimeError):
    def __init__(
        self,
        code: BoundaryFailureCode,
        detail: str,
        *,
        usage: TokenUsageV2 | None = None,
        tool_calls: int = 0,
        latency_ms: int = 0,
        monetary_microunits: int = 0,
    ) -> None:
        super().__init__(detail)
        self.code = BoundaryFailureCode(code)
        self.detail = detail
        self.usage = TokenUsageV2() if usage is None else usage
        self.tool_calls = tool_calls
        self.latency_ms = latency_ms
        self.monetary_microunits = monetary_microunits


def _answer(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


_PYTHON_BLOCK = re.compile(r"```python\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_SOLVE = re.compile(
    r"\bsolve\s+(?P<equation>.+?)\s+for\s+(?P<variable>[A-Za-z]\w*)\s*[?.]?$",
    re.IGNORECASE | re.DOTALL,
)


def _python_expression(question: str) -> tuple[str, str] | None:
    blocks = _PYTHON_BLOCK.findall(question)
    if len(blocks) != 1:
        return None
    source = blocks[0].strip()
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return None
    call = tree.body[0].value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "print"
        and len(call.args) == 1
        and not call.keywords
    ):
        return None
    expression = ast.unparse(call.args[0])
    try:
        expression = normalize_expression(expression)
        evaluate_exact(expression)
    except UnsupportedExpression:
        return None
    return source, expression


def _linear(node: ast.AST, variable: str) -> tuple[Fraction, Fraction]:
    if isinstance(node, ast.Expression):
        return _linear(node.body, variable)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Fraction(0), Fraction(str(node.value))
    if isinstance(node, ast.Name) and node.id == variable:
        return Fraction(1), Fraction(0)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        a, b = _linear(node.operand, variable)
        return (a, b) if isinstance(node.op, ast.UAdd) else (-a, -b)
    if isinstance(node, ast.BinOp):
        la, lb = _linear(node.left, variable)
        ra, rb = _linear(node.right, variable)
        if isinstance(node.op, ast.Add):
            return la + ra, lb + rb
        if isinstance(node.op, ast.Sub):
            return la - ra, lb - rb
        if isinstance(node.op, ast.Mult):
            if la and ra:
                raise ValueError("nonlinear multiplication")
            if la:
                return la * rb, lb * rb
            if ra:
                return ra * lb, rb * lb
            return Fraction(0), lb * rb
        if isinstance(node.op, ast.Div):
            if ra or rb == 0:
                raise ValueError("division by a variable or zero")
            return la / rb, lb / rb
        if isinstance(node.op, ast.Pow):
            if ra or rb.denominator != 1 or rb not in {0, 1}:
                raise ValueError("only linear powers are allowed")
            return (Fraction(0), Fraction(1)) if rb == 0 else (la, lb)
    raise ValueError("outside bounded linear language")


def _linear_solution(question: str) -> tuple[str, str] | None:
    match = _SOLVE.search(question)
    if match is None:
        return None
    equation = match.group("equation").strip().replace("^", "**")
    variable = match.group("variable")
    if equation.count("=") != 1:
        return None
    left, right = equation.split("=", 1)
    try:
        la, lb = _linear(ast.parse(left.strip(), mode="eval"), variable)
        ra, rb = _linear(ast.parse(right.strip(), mode="eval"), variable)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return None
    coefficient = la - ra
    constant = lb - rb
    if coefficient == 0:
        return None
    value = -constant / coefficient
    verification = f"({-constant.numerator}/{constant.denominator})/({coefficient.numerator}/{coefficient.denominator})"
    return _answer(value), verification


def _default_value(*, probability_resolution_ppm: int, token_cost: int = 0) -> RouteValueEstimate:
    return RouteValueEstimate(
        probability_base_error_ppm=300_000,
        probability_resolution_ppm=probability_resolution_ppm,
        probability_damage_ppm=0,
        benefit_microunits=1_000_000,
        damage_microunits=2_000_000,
        token_cost_microunits=token_cost,
    )


class ExactArithmeticAdapterV2:
    family = RuntimeToolFamily.EXACT_ARITHMETIC
    tool_id = "foil.exact-arithmetic"
    tool_version = "2"

    def probe(self, task: QuestionOnlyTaskV2) -> ToolProbeV2:
        expression = closed_answer_expression_v2(task.question)
        return ToolProbeV2(
            self.family,
            ProbeStatusV2.APPLICABLE if expression is not None else ProbeStatusV2.DECLINE,
            "unique_closed_expression" if expression is not None else "no_unique_closed_expression",
            expression or task.question_digest,
            ComplexityBand.LOW,
            ResourceEnvelopeV2(maximum_latency_ms=500),
            _default_value(probability_resolution_ppm=990_000),
            500,
            True,
        )

    def execute(self, contract: ToolContractV2, task: QuestionOnlyTaskV2, probe: ToolProbeV2) -> ToolReceiptV2:
        if probe.status != ProbeStatusV2.APPLICABLE or probe.operation_input_digest != contract.operation_input_digest:
            return ToolReceiptV2(
                f"call-{contract.contract_digest[:16]}", contract.contract_digest,
                self.family, ToolOutcomeV2.NOT_APPLICABLE, TokenUsageV2(), 0, 0, 0,
            )
        value = _answer(evaluate_exact(probe.operation_payload))
        return ToolReceiptV2(
            f"call-{contract.contract_digest[:16]}", contract.contract_digest,
            self.family, ToolOutcomeV2.RESOLVED, TokenUsageV2(), 1, 0, 0,
            candidate_answer=value, verification_expression=probe.operation_payload,
        )


class RestrictedPythonAdapterV2:
    family = RuntimeToolFamily.RESTRICTED_PYTHON
    tool_id = "foil.restricted-python"
    tool_version = "2"

    def probe(self, task: QuestionOnlyTaskV2) -> ToolProbeV2:
        extracted = _python_expression(task.question)
        payload = task.question_digest if extracted is None else extracted[1]
        return ToolProbeV2(
            self.family,
            ProbeStatusV2.APPLICABLE if extracted is not None else ProbeStatusV2.DECLINE,
            "single_numeric_print" if extracted is not None else "outside_restricted_python_language",
            payload,
            ComplexityBand.LOW,
            ResourceEnvelopeV2(maximum_latency_ms=500),
            _default_value(probability_resolution_ppm=980_000),
            500,
            True,
        )

    def execute(self, contract: ToolContractV2, task: QuestionOnlyTaskV2, probe: ToolProbeV2) -> ToolReceiptV2:
        if probe.status != ProbeStatusV2.APPLICABLE or probe.operation_input_digest != contract.operation_input_digest:
            return ToolReceiptV2(
                f"call-{contract.contract_digest[:16]}", contract.contract_digest,
                self.family, ToolOutcomeV2.NOT_APPLICABLE, TokenUsageV2(), 0, 0, 0,
            )
        value = _answer(evaluate_exact(probe.operation_payload))
        return ToolReceiptV2(
            f"call-{contract.contract_digest[:16]}", contract.contract_digest,
            self.family, ToolOutcomeV2.RESOLVED, TokenUsageV2(), 1, 0, 0,
            candidate_answer=value, verification_expression=probe.operation_payload,
        )


class SymbolicLinearAdapterV2:
    family = RuntimeToolFamily.SYMBOLIC_COMPUTATION
    tool_id = "foil.symbolic-linear"
    tool_version = "2"

    def probe(self, task: QuestionOnlyTaskV2) -> ToolProbeV2:
        result = _linear_solution(task.question)
        payload = task.question_digest if result is None else result[1]
        return ToolProbeV2(
            self.family,
            ProbeStatusV2.APPLICABLE if result is not None else ProbeStatusV2.DECLINE,
            "single_linear_equation" if result is not None else "outside_bounded_symbolic_language",
            payload,
            ComplexityBand.MEDIUM,
            ResourceEnvelopeV2(maximum_latency_ms=1_000),
            _default_value(probability_resolution_ppm=950_000),
            1_000,
            True,
        )

    def execute(self, contract: ToolContractV2, task: QuestionOnlyTaskV2, probe: ToolProbeV2) -> ToolReceiptV2:
        result = _linear_solution(task.question)
        if result is None or digest(result[1]) != contract.operation_input_digest:
            return ToolReceiptV2(
                f"call-{contract.contract_digest[:16]}", contract.contract_digest,
                self.family, ToolOutcomeV2.NOT_APPLICABLE, TokenUsageV2(), 0, 0, 0,
            )
        answer, verification = result
        # Recompute the emitted verification expression independently.
        if _answer(evaluate_exact(verification)) != answer:
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "symbolic verification mismatch")
        return ToolReceiptV2(
            f"call-{contract.contract_digest[:16]}", contract.contract_digest,
            self.family, ToolOutcomeV2.RESOLVED, TokenUsageV2(), 1, 0, 0,
            candidate_answer=answer, verification_expression=verification,
        )


@dataclass(frozen=True)
class RetrievedPassageBatch:
    passages: tuple[PassageEvidenceV2, ...]
    usage: TokenUsageV2
    tool_calls: int
    latency_ms: int
    monetary_microunits: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.passages, tuple) or not all(isinstance(item, PassageEvidenceV2) for item in self.passages):
            raise TypeError("passages must be PassageEvidenceV2 tuple")
        if not isinstance(self.usage, TokenUsageV2):
            raise TypeError("usage must be TokenUsageV2")


PassageRetrievalRunner = Callable[[str, ResourceEnvelopeV2], RetrievedPassageBatch]


class PassageRetrievalAdapterV2:
    family = RuntimeToolFamily.PASSAGE_RETRIEVAL

    def __init__(
        self,
        runner: PassageRetrievalRunner,
        *,
        envelope: ResourceEnvelopeV2,
        value: RouteValueEstimate,
        tool_id: str,
        tool_version: str,
        provider_cap_enforced: bool,
    ) -> None:
        self.runner = runner
        self.envelope = envelope
        self.value = value
        self.tool_id = tool_id
        self.tool_version = tool_version
        self.provider_cap_enforced = provider_cap_enforced

    def probe(self, task: QuestionOnlyTaskV2) -> ToolProbeV2:
        return ToolProbeV2(
            self.family,
            ProbeStatusV2.APPLICABLE,
            "passage_retrieval_provider_available",
            task.question,
            ComplexityBand.HIGH,
            self.envelope,
            self.value,
            self.envelope.maximum_latency_ms,
            self.provider_cap_enforced,
            OperationSpecOrigin.HOST_RETRIEVAL,
        )

    def execute(self, contract: ToolContractV2, task: QuestionOnlyTaskV2, probe: ToolProbeV2) -> ToolReceiptV2:
        try:
            batch = self.runner(task.question, contract.envelope)
        except ToolBoundaryFailure:
            raise
        if not isinstance(batch, RetrievedPassageBatch):
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "retrieval runner returned wrong type")
        outcome = ToolOutcomeV2.SUPPORTING if batch.passages else ToolOutcomeV2.UNRESOLVED
        return ToolReceiptV2(
            f"call-{contract.contract_digest[:16]}", contract.contract_digest,
            self.family, outcome, batch.usage, batch.tool_calls,
            batch.latency_ms, batch.monetary_microunits, passages=batch.passages,
        )
