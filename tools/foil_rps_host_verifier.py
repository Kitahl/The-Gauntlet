"""Answer-blind check selection and deterministic Stage-1 verification for RPS.

Selection accepts only a host task descriptor; the candidate answer is supplied
later to :func:`verify_answer`. This structural split prevents answer-conditioned
check choice. It does not prove temporal ordering, which remains a host receipt
obligation.

The first version supports only closed, deterministic surfaces:

* certified numeric equality (including a separately selected power language);
* closed JSON object shape and primitive field types;
* structured quantity JSON with a small, exact unit-dimension table.

Unknown syntax returns NOT_APPLICABLE. No model, network, tool, profile, answer
mutation, or production authority is used.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Mapping

from foil_certified_arithmetic import (
    CERTIFIED_LANGUAGE,
    POWER_LANGUAGE,
    extract_step,
    extract_steps,
)
from foil_rps import CheckKind
from foil_rps_v062 import (
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    check_commitment_digest,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HostTaskType(str, Enum):
    ARITHMETIC_EQUALITY = "ARITHMETIC_EQUALITY"
    ARITHMETIC_POWER_EQUALITY = "ARITHMETIC_POWER_EQUALITY"
    PROCESSBENCH_FIRST_ERROR = "PROCESSBENCH_FIRST_ERROR"
    JSON_SCHEMA = "JSON_SCHEMA"
    UNIT_QUANTITY = "UNIT_QUANTITY"
    UNSUPPORTED = "UNSUPPORTED"


class Stage1Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class JsonPrimitive(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"


def _digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _canonical(value: object) -> str:
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JsonFieldSpec:
    name: str
    primitive: JsonPrimitive

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("field name must be non-empty text")
        if not isinstance(self.primitive, JsonPrimitive):
            raise TypeError("primitive must be JsonPrimitive")


@dataclass(frozen=True)
class HostTaskDescriptor:
    task_digest: str
    answer_form_digest: str
    task_type: HostTaskType
    json_fields: tuple[JsonFieldSpec, ...] = ()
    expected_dimension: str | None = None
    source_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _digest("task_digest", self.task_digest)
        _digest("answer_form_digest", self.answer_form_digest)
        if not isinstance(self.task_type, HostTaskType):
            raise TypeError("task_type must be HostTaskType")
        if not isinstance(self.json_fields, tuple) or not all(
            isinstance(field, JsonFieldSpec) for field in self.json_fields
        ):
            raise TypeError("json_fields must be a tuple of JsonFieldSpec")
        if len({field.name for field in self.json_fields}) != len(self.json_fields):
            raise ValueError("JSON field names must be unique")
        if self.task_type is HostTaskType.JSON_SCHEMA and not self.json_fields:
            raise ValueError("JSON_SCHEMA requires at least one field")
        if self.task_type is not HostTaskType.JSON_SCHEMA and self.json_fields:
            raise ValueError("only JSON_SCHEMA accepts json_fields")
        if self.task_type is HostTaskType.UNIT_QUANTITY:
            if self.expected_dimension not in {"LENGTH", "MASS", "TIME"}:
                raise ValueError("UNIT_QUANTITY requires a supported dimension")
        elif self.expected_dimension is not None:
            raise ValueError("only UNIT_QUANTITY accepts expected_dimension")
        if self.task_type is HostTaskType.PROCESSBENCH_FIRST_ERROR:
            if not self.source_steps or not all(
                isinstance(step, str) and step.strip() for step in self.source_steps
            ):
                raise ValueError(
                    "PROCESSBENCH_FIRST_ERROR requires non-empty source_steps"
                )
        elif self.source_steps:
            raise ValueError("only PROCESSBENCH_FIRST_ERROR accepts source_steps")


@dataclass(frozen=True)
class SelectedHostCheck:
    task_type: HostTaskType
    precommit: PrecommittedHostCheck | None
    spec: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.task_type, HostTaskType):
            raise TypeError("task_type must be HostTaskType")
        if self.task_type is HostTaskType.UNSUPPORTED:
            if self.precommit is not None or self.spec:
                raise ValueError("unsupported selection must be empty")
        elif not isinstance(self.precommit, PrecommittedHostCheck):
            raise TypeError("supported selection requires a precommit")


@dataclass(frozen=True)
class Stage1Result:
    outcome: Stage1Outcome
    reason: str
    candidate_digest: str
    observation_digest: str | None
    receipt: HostVerifierReceipt | None
    provider_calls: int = 0
    model_tokens: int = 0
    answer_mutations: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, Stage1Outcome):
            raise TypeError("outcome must be Stage1Outcome")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text")
        _digest("candidate_digest", self.candidate_digest)
        if self.observation_digest is not None:
            _digest("observation_digest", self.observation_digest)
        if self.receipt is not None and not isinstance(self.receipt, HostVerifierReceipt):
            raise TypeError("receipt must be HostVerifierReceipt or None")
        if self.provider_calls or self.model_tokens or self.answer_mutations:
            raise ValueError("Stage 1 must have zero model/action cost")


def _spec_for(task: HostTaskDescriptor) -> tuple[CheckKind, dict[str, object]] | None:
    if task.task_type is HostTaskType.ARITHMETIC_EQUALITY:
        return CheckKind.EXACT_RELATION, {"language": CERTIFIED_LANGUAGE}
    if task.task_type is HostTaskType.ARITHMETIC_POWER_EQUALITY:
        return CheckKind.EXACT_RELATION, {"language": POWER_LANGUAGE}
    if task.task_type is HostTaskType.PROCESSBENCH_FIRST_ERROR:
        findings = tuple(
            finding
            for language in (CERTIFIED_LANGUAGE, POWER_LANGUAGE)
            for finding in extract_steps(task.source_steps, language=language)
            if finding.violating
        )
        earliest = min((finding.step_index for finding in findings), default=None)
        return CheckKind.EXACT_RELATION, {
            "expected_answer": None if earliest is None else str(earliest),
            "languages": [CERTIFIED_LANGUAGE, POWER_LANGUAGE],
            "source_steps_sha256": _canonical(list(task.source_steps)),
            "vacuous": earliest is None,
        }
    if task.task_type is HostTaskType.JSON_SCHEMA:
        return CheckKind.REPRESENTATION_CONSISTENCY, {
            "closed": True,
            "fields": [
                {"name": field.name, "primitive": field.primitive.value}
                for field in task.json_fields
            ],
        }
    if task.task_type is HostTaskType.UNIT_QUANTITY:
        return CheckKind.REPRESENTATION_CONSISTENCY, {
            "closed": True,
            "shape": {"value": "RATIONAL", "unit": "UNIT"},
            "expected_dimension": task.expected_dimension,
        }
    return None


def select_check(task: HostTaskDescriptor) -> SelectedHostCheck:
    """Select and freeze one check without accepting an answer parameter."""

    if not isinstance(task, HostTaskDescriptor):
        raise TypeError("task must be HostTaskDescriptor")
    selected = _spec_for(task)
    if selected is None:
        return SelectedHostCheck(task.task_type, None, {})
    kind, spec = selected
    spec_digest = _canonical(spec)
    check_id = f"rps-stage1:{task.task_type.value.lower()}"
    commitment = check_commitment_digest(
        task_digest=task.task_digest,
        answer_form_digest=task.answer_form_digest,
        check_id=check_id,
        kind=kind,
        check_spec_digest=spec_digest,
    )
    return SelectedHostCheck(
        task.task_type,
        PrecommittedHostCheck(
            task_digest=task.task_digest,
            answer_form_digest=task.answer_form_digest,
            check_id=check_id,
            kind=kind,
            check_spec_digest=spec_digest,
            commitment_digest=commitment,
        ),
        spec,
    )


def _parse_json_object(answer: object) -> dict[str, object] | None:
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except json.JSONDecodeError:
            return None
    if not isinstance(answer, dict) or not all(isinstance(key, str) for key in answer):
        return None
    return answer


def _primitive_matches(value: object, expected: JsonPrimitive) -> bool:
    if expected is JsonPrimitive.STRING:
        return isinstance(value, str)
    if expected is JsonPrimitive.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is JsonPrimitive.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is JsonPrimitive.BOOLEAN:
        return isinstance(value, bool)
    if expected is JsonPrimitive.OBJECT:
        return isinstance(value, dict)
    return isinstance(value, list)


_UNITS: Mapping[str, tuple[str, Fraction]] = {
    "m": ("LENGTH", Fraction(1)),
    "cm": ("LENGTH", Fraction(1, 100)),
    "km": ("LENGTH", Fraction(1000)),
    "kg": ("MASS", Fraction(1)),
    "g": ("MASS", Fraction(1, 1000)),
    "s": ("TIME", Fraction(1)),
    "min": ("TIME", Fraction(60)),
    "h": ("TIME", Fraction(3600)),
}


def _evaluate(
    selected: SelectedHostCheck, answer: object
) -> tuple[Stage1Outcome, str, object | None]:
    if selected.task_type is HostTaskType.UNSUPPORTED:
        return Stage1Outcome.NOT_APPLICABLE, "unsupported_task_type", None
    if selected.task_type in {
        HostTaskType.ARITHMETIC_EQUALITY,
        HostTaskType.ARITHMETIC_POWER_EQUALITY,
    }:
        language = str(selected.spec["language"])
        if isinstance(answer, str):
            findings = extract_step(answer, step_index=0, language=language)
        elif isinstance(answer, (list, tuple)) and all(
            isinstance(step, str) for step in answer
        ):
            findings = extract_steps(answer, language=language)
        elif (
            isinstance(answer, dict)
            and set(answer) == {"steps"}
            and isinstance(answer["steps"], list)
            and all(isinstance(step, str) for step in answer["steps"])
        ):
            findings = extract_steps(answer["steps"], language=language)
        else:
            return Stage1Outcome.NOT_APPLICABLE, "arithmetic_answer_not_text_or_steps", None
        if not findings:
            return Stage1Outcome.NOT_APPLICABLE, "no_certified_equality", None
        observation = [finding.to_dict() for finding in findings]
        if any(finding.violating for finding in findings):
            return Stage1Outcome.FAIL, "certified_false_equality", observation
        return Stage1Outcome.PASS, "all_certified_equalities_hold", observation
    if selected.task_type is HostTaskType.PROCESSBENCH_FIRST_ERROR:
        expected = selected.spec["expected_answer"]
        if expected is None:
            return (
                Stage1Outcome.NOT_APPLICABLE,
                "vacuous_no_certified_first_error",
                None,
            )
        if isinstance(answer, str):
            candidate = answer.strip()
        elif (
            isinstance(answer, dict)
            and set(answer) == {"answer", "abstain"}
            and isinstance(answer["answer"], str)
            and isinstance(answer["abstain"], bool)
        ):
            if answer["abstain"]:
                return Stage1Outcome.UNCERTAIN, "candidate_abstained", None
            candidate = answer["answer"].strip()
        else:
            return (
                Stage1Outcome.NOT_APPLICABLE,
                "first_error_candidate_not_supported",
                None,
            )
        observation = {
            "candidate": candidate,
            "expected": expected,
            "vacuous": False,
        }
        if candidate == expected:
            return Stage1Outcome.PASS, "first_error_matches", observation
        return Stage1Outcome.FAIL, "first_error_mismatch", observation
    if selected.task_type is HostTaskType.JSON_SCHEMA:
        parsed = _parse_json_object(answer)
        if parsed is None:
            return Stage1Outcome.FAIL, "answer_is_not_a_json_object", None
        fields = selected.spec["fields"]
        assert isinstance(fields, list)
        expected = {str(field["name"]): JsonPrimitive(str(field["primitive"])) for field in fields}
        if set(parsed) != set(expected):
            return Stage1Outcome.FAIL, "closed_json_fields_mismatch", sorted(parsed)
        if not all(_primitive_matches(parsed[name], primitive) for name, primitive in expected.items()):
            return Stage1Outcome.FAIL, "json_primitive_type_mismatch", parsed
        return Stage1Outcome.PASS, "closed_json_schema_satisfied", parsed
    parsed = _parse_json_object(answer)
    if parsed is None or set(parsed) != {"value", "unit"}:
        return Stage1Outcome.FAIL, "quantity_shape_mismatch", None
    if not isinstance(parsed["unit"], str) or parsed["unit"] not in _UNITS:
        return Stage1Outcome.NOT_APPLICABLE, "unknown_unit", parsed
    try:
        value = Fraction(str(parsed["value"]))
    except (ValueError, ZeroDivisionError):
        return Stage1Outcome.FAIL, "quantity_value_not_rational", parsed
    dimension, scale = _UNITS[parsed["unit"]]
    observation = {
        "canonical_value": str(value * scale),
        "dimension": dimension,
        "unit": parsed["unit"],
    }
    if dimension != selected.spec["expected_dimension"]:
        return Stage1Outcome.FAIL, "unit_dimension_mismatch", observation
    return Stage1Outcome.PASS, "unit_dimension_matches", observation


def verify_answer(selected: SelectedHostCheck, answer: object) -> Stage1Result:
    if not isinstance(selected, SelectedHostCheck):
        raise TypeError("selected must be SelectedHostCheck")
    candidate_digest = _canonical(answer)
    outcome, reason, observation = _evaluate(selected, answer)
    if outcome is Stage1Outcome.NOT_APPLICABLE:
        observation = None
    observation_digest = _canonical(observation) if observation is not None else None
    if selected.precommit is None:
        return Stage1Result(outcome, reason, candidate_digest, observation_digest, None)
    mapped = {
        Stage1Outcome.PASS: HostVerifierOutcome.CONFIRMED,
        Stage1Outcome.FAIL: HostVerifierOutcome.CONTRADICTED,
        Stage1Outcome.NOT_APPLICABLE: HostVerifierOutcome.NOT_APPLICABLE,
        Stage1Outcome.UNCERTAIN: HostVerifierOutcome.UNCERTAIN,
    }[outcome]
    receipt = HostVerifierReceipt(
        task_digest=selected.precommit.task_digest,
        check_commitment_digest=selected.precommit.commitment_digest,
        candidate_digest=candidate_digest,
        outcome=mapped,
        observation_digest=observation_digest,
    )
    return Stage1Result(outcome, reason, candidate_digest, observation_digest, receipt)
