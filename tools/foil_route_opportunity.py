"""Question-only route-opportunity discovery for FOIL benchmarks.

This module does not decide whether an answer is correct and does not execute a
tool.  It projects each task down to ``task_id`` plus question text, derives a
small capability frontier from positive structural signals, and emits only
digests and reason codes.  A0, gold, correctness labels, model output, and tool
receipts are deliberately outside the prediction interface.

The resulting artifact is a frozen development hypothesis.  A separate scorer
may later compare it with outcomes, but that comparison cannot retroactively
change the prediction artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from egrt_types import digest
from foil_capabilities import CAPABILITIES


QUESTION_INPUT_SCHEMA = "foil.question-only-route-input.v1"
PREDICTION_SCHEMA = "foil.question-only-route-predictions.v1"
REPORT_SCHEMA = "foil.question-only-route-opportunity-report.v1"


class OpportunityStatus(str, Enum):
    FOUND = "FOUND"
    UNSUPPORTED = "UNSUPPORTED"


class OpportunityClass(str, Enum):
    EXECUTION = "EXECUTION"
    RETRIEVAL = "RETRIEVAL"
    FORMAL = "FORMAL"


_QUESTION_FIELDS = frozenset({"schema", "task_id", "question"})


def _strict_fields(raw: Mapping[str, object], expected: frozenset[str]) -> None:
    actual = frozenset(raw)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"closed schema mismatch: missing={missing}, unknown={unknown}")


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


@dataclass(frozen=True)
class QuestionOnlyTask:
    task_id: str
    question: str
    schema: str = QUESTION_INPUT_SCHEMA

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "QuestionOnlyTask":
        if not isinstance(raw, Mapping):
            raise TypeError("question input must be a mapping")
        _strict_fields(raw, _QUESTION_FIELDS)
        if raw["schema"] != QUESTION_INPUT_SCHEMA:
            raise ValueError("unsupported question-only input schema")
        return cls(
            task_id=_text("task_id", raw["task_id"]),
            question=_text("question", raw["question"]),
        )

    @property
    def question_digest(self) -> str:
        return digest(self.question)


@dataclass(frozen=True)
class RouteCandidate:
    capability: str
    opportunity_class: OpportunityClass
    reason_code: str

    def __post_init__(self) -> None:
        if self.capability not in CAPABILITIES:
            raise ValueError("candidate capability is not registered")
        object.__setattr__(self, "opportunity_class", OpportunityClass(self.opportunity_class))
        _text("reason_code", self.reason_code)

    def trace(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "opportunity_class": self.opportunity_class.value,
            "reason_code": self.reason_code,
            "authority_ceiling": CAPABILITIES[self.capability]["authority_ceiling"],
            "evidence_class": "QUESTION_STRUCTURE_ONLY",
            "requires_runtime_probe": True,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class RouteOpportunity:
    task_id: str
    question_digest: str
    status: OpportunityStatus
    candidates: tuple[RouteCandidate, ...]

    def __post_init__(self) -> None:
        _text("task_id", self.task_id)
        if not re.fullmatch(r"[0-9a-f]{64}", self.question_digest):
            raise ValueError("question_digest must be sha256 hex")
        object.__setattr__(self, "status", OpportunityStatus(self.status))
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be tuple")
        if self.status is OpportunityStatus.FOUND and not self.candidates:
            raise ValueError("FOUND requires at least one candidate")
        if self.status is OpportunityStatus.UNSUPPORTED and self.candidates:
            raise ValueError("UNSUPPORTED cannot carry candidates")
        capabilities = [candidate.capability for candidate in self.candidates]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("candidate capabilities must be unique")

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "task_id": self.task_id,
            "question_digest": self.question_digest,
            "status": self.status.value,
            "candidates": [candidate.trace() for candidate in self.candidates],
            "question_only": True,
            "raw_question_stored": False,
            "a0_observed": False,
            "gold_observed": False,
            "execution_authorized": False,
            "promotion_authorized": False,
        }
        body["opportunity_sha256"] = digest(body)
        return body


_CODE_LANGUAGE = re.compile(
    r"\b(python|gdscript|javascript|typescript|java|rust|c\+\+|script|program|code)\b",
    re.IGNORECASE,
)
_CODE_OBSERVATION = re.compile(
    r"\b(error message|output|evaluat(?:e|es|ion)|returns?|semantics|parse|compile|runtime)\b",
    re.IGNORECASE,
)
_LEGAL_OR_AUTHORITY = re.compile(
    r"\b(act|statutory instrument|section|subsection|regulation|case law|legislation)\b",
    re.IGNORECASE,
)
_VERSIONED_FACT = re.compile(
    r"\b(version|ide|release|current|latest|as of)\b|\b\d+(?:\.\d+){1,3}\b",
    re.IGNORECASE,
)
_MATH_STRUCTURE = re.compile(
    r"\\(?:frac|sum|prod|sqrt|sin|cos|theta|mathcal|operatorname|overline)\b"
    r"|\$[^$]+\$|\\\([^)]*\\\)|\b(probability|radius|diameter|matrix|vector|group|graph)\b",
    re.IGNORECASE,
)
_NUMERIC_ASK = re.compile(
    r"\b(calculate|compute|evaluate|how many|number of|probability|value|operations necessary|minimum|maximum|maximal|smallest|significant digits?)\b",
    re.IGNORECASE,
)
_FORMAL_ASK = re.compile(
    r"\b(prove|show that|in terms of|smallest possible|minimum possible|theorem|subspace|rational subset|circumcircle|moduli space|artin group|extremal function)\b",
    re.IGNORECASE,
)
_SCHOLARLY_NAMED = re.compile(
    r"\b(moduli space|artin group|turan|extremal function|employment rights act|hamiltonian|phonon|fermi gas|compactified|codimension)\b",
    re.IGNORECASE,
)


def discover_route_opportunity(raw: Mapping[str, object]) -> RouteOpportunity:
    """Derive a capability frontier without accepting answer-side fields."""

    task = QuestionOnlyTask.from_mapping(raw)
    question = task.question
    candidates: list[RouteCandidate] = []

    def add(capability: str, kind: OpportunityClass, reason: str) -> None:
        if any(candidate.capability == capability for candidate in candidates):
            return
        candidates.append(RouteCandidate(capability, kind, reason))

    code_semantics = bool(_CODE_LANGUAGE.search(question) and _CODE_OBSERVATION.search(question))
    legal_fact = bool(_LEGAL_OR_AUTHORITY.search(question))
    versioned_fact = bool(_VERSIONED_FACT.search(question))
    math_structure = bool(_MATH_STRUCTURE.search(question))
    numeric_ask = bool(_NUMERIC_ASK.search(question))
    formal_ask = bool(_FORMAL_ASK.search(question))
    scholarly_named = bool(_SCHOLARLY_NAMED.search(question))

    if code_semantics:
        add("CODE_EXECUTION", OpportunityClass.EXECUTION, "EXECUTABLE_PROGRAM_SEMANTICS")
    if math_structure and numeric_ask:
        add(
            "SYMBOLIC_COMPUTATION",
            OpportunityClass.EXECUTION,
            "EXPLICIT_MATHEMATICAL_COMPUTATION",
        )
        add("CODE_EXECUTION", OpportunityClass.EXECUTION, "NUMERIC_EXECUTION_FALLBACK")
    if legal_fact or (versioned_fact and code_semantics):
        add("WEB_SEARCH", OpportunityClass.RETRIEVAL, "VERSIONED_OR_LEGAL_FACT_LOOKUP")
    if scholarly_named:
        add("SCHOLARLY_SEARCH", OpportunityClass.RETRIEVAL, "SPECIALIZED_NAMED_RESULT_LOOKUP")
    if math_structure and formal_ask:
        add("FORMAL_PROOF", OpportunityClass.FORMAL, "PROOF_OR_UNIVERSAL_CONSTRAINT")

    status = OpportunityStatus.FOUND if candidates else OpportunityStatus.UNSUPPORTED
    return RouteOpportunity(task.task_id, task.question_digest, status, tuple(candidates))


def build_prediction_artifact(items_doc: Mapping[str, object]) -> dict[str, object]:
    """Project a benchmark manifest to question-only inputs and freeze predictions."""

    if not isinstance(items_doc, Mapping):
        raise TypeError("items document must be a mapping")
    items = items_doc.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValueError("items document must contain an items sequence")
    predictions: list[dict[str, object]] = []
    task_ids: set[str] = set()
    universe: list[dict[str, str]] = []
    for source in items:
        if not isinstance(source, Mapping):
            raise TypeError("each source item must be a mapping")
        task_id = _text("id", source.get("id"))
        question = _text("question", source.get("question"))
        if task_id in task_ids:
            raise ValueError("duplicate task id in question universe")
        task_ids.add(task_id)
        opportunity = discover_route_opportunity(
            {"schema": QUESTION_INPUT_SCHEMA, "task_id": task_id, "question": question}
        )
        predictions.append(opportunity.trace())
        universe.append({"task_id": task_id, "question_digest": opportunity.question_digest})

    body: dict[str, object] = {
        "schema": PREDICTION_SCHEMA,
        "classification": "FROZEN_QUESTION_ONLY_DEVELOPMENT_PREDICTIONS",
        "source_schema": items_doc.get("schema"),
        "question_universe_sha256": digest(universe),
        "input_fields_used": ["id", "question"],
        "frozen": True,
        "predictions": predictions,
        "cost_and_authority": {
            "provider_calls": 0,
            "model_calls": 0,
            "tool_calls": 0,
            "token_spend": 0,
            "answer_mutations": 0,
            "execution_authorizations": 0,
            "promotion_changes": 0,
        },
        "non_claims": [
            "not verifier applicability",
            "not defect detection",
            "not a rescue estimate",
            "not a deployable router",
            "not promotion evidence",
        ],
    }
    body["prediction_sha256"] = digest(body)
    return body


def validate_prediction_artifact(artifact: Mapping[str, object]) -> None:
    if not isinstance(artifact, Mapping):
        raise TypeError("prediction artifact must be a mapping")
    if artifact.get("schema") != PREDICTION_SCHEMA or artifact.get("frozen") is not True:
        raise ValueError("prediction artifact is not a frozen supported schema")
    supplied = artifact.get("prediction_sha256")
    if not isinstance(supplied, str):
        raise ValueError("prediction artifact lacks prediction_sha256")
    unhashed = dict(artifact)
    unhashed.pop("prediction_sha256", None)
    if digest(unhashed) != supplied:
        raise ValueError("prediction artifact hash mismatch")
    predictions = artifact.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        raise ValueError("prediction artifact must contain predictions")
    seen: set[str] = set()
    for row in predictions:
        if not isinstance(row, Mapping):
            raise TypeError("prediction row must be a mapping")
        task_id = _text("task_id", row.get("task_id"))
        if task_id in seen:
            raise ValueError("prediction artifact contains duplicate task ids")
        seen.add(task_id)


def _task_id_for_unit(unit_id: object, task_ids: Sequence[str]) -> str:
    unit = _text("unit_id", unit_id)
    matches = [task_id for task_id in task_ids if unit.endswith(task_id.removeprefix("hle-"))]
    if len(matches) != 1:
        raise ValueError("audit unit_id does not bind exactly one frozen task")
    return matches[0]


def score_prediction_artifact(
    artifact: Mapping[str, object], audit: Mapping[str, object]
) -> dict[str, object]:
    """Score frozen route hypotheses after answer-side outcomes are available."""

    validate_prediction_artifact(artifact)
    if not isinstance(audit, Mapping) or not isinstance(audit.get("rows"), list):
        raise ValueError("audit must contain a rows list")
    predictions = list(artifact["predictions"])
    task_ids = [str(row["task_id"]) for row in predictions]
    rows_by_task: dict[str, list[Mapping[str, object]]] = {task_id: [] for task_id in task_ids}
    seen_units: set[str] = set()
    for row in audit["rows"]:
        if not isinstance(row, Mapping):
            raise TypeError("audit rows must be mappings")
        unit_id = _text("unit_id", row.get("unit_id"))
        if unit_id in seen_units:
            raise ValueError("audit contains duplicate unit_id")
        seen_units.add(unit_id)
        rows_by_task[_task_id_for_unit(unit_id, task_ids)].append(row)
    if any(not rows for rows in rows_by_task.values()):
        raise ValueError("every frozen task must have at least one audit row")

    status_counts = {status.value: 0 for status in OpportunityStatus}
    status_outcomes = {
        status.value: {
            "questions": 0,
            "questions_with_any_base_miss": 0,
            "questions_with_all_base_miss": 0,
            "audit_rows": 0,
            "base_wrong_rows": 0,
            "historical_rescue_rows": 0,
        }
        for status in OpportunityStatus
    }
    capability_rows: dict[str, dict[str, int]] = {}
    question_rows: list[dict[str, object]] = []
    total_audit_rows = 0
    for prediction in predictions:
        task_id = str(prediction["task_id"])
        status_counts[str(prediction["status"])] += 1
        audit_rows = rows_by_task[task_id]
        total_audit_rows += len(audit_rows)
        base_correct = sum(int(bool(row.get("base_correct"))) for row in audit_rows)
        historical_rescues = sum(int(bool(row.get("rescued"))) for row in audit_rows)
        status_bucket = status_outcomes[str(prediction["status"])]
        status_bucket["questions"] += 1
        status_bucket["questions_with_any_base_miss"] += int(
            base_correct < len(audit_rows)
        )
        status_bucket["questions_with_all_base_miss"] += int(base_correct == 0)
        status_bucket["audit_rows"] += len(audit_rows)
        status_bucket["base_wrong_rows"] += len(audit_rows) - base_correct
        status_bucket["historical_rescue_rows"] += historical_rescues
        capabilities = [
            str(candidate["capability"])
            for candidate in prediction.get("candidates", [])
        ]
        question_rows.append(
            {
                "task_id": task_id,
                "opportunity_sha256": prediction["opportunity_sha256"],
                "status": prediction["status"],
                "candidate_capabilities": capabilities,
                "configuration_rows": len(audit_rows),
                "base_correct_rows": base_correct,
                "base_wrong_rows": len(audit_rows) - base_correct,
                "historical_rescue_rows": historical_rescues,
            }
        )
        for capability in capabilities:
            bucket = capability_rows.setdefault(
                capability,
                {
                    "questions_flagged": 0,
                    "questions_with_any_base_miss": 0,
                    "questions_with_all_base_miss": 0,
                    "audit_rows": 0,
                    "base_wrong_rows": 0,
                    "historical_rescue_rows": 0,
                },
            )
            bucket["questions_flagged"] += 1
            bucket["questions_with_any_base_miss"] += int(base_correct < len(audit_rows))
            bucket["questions_with_all_base_miss"] += int(base_correct == 0)
            bucket["audit_rows"] += len(audit_rows)
            bucket["base_wrong_rows"] += len(audit_rows) - base_correct
            bucket["historical_rescue_rows"] += historical_rescues

    if sum(status_counts.values()) != len(predictions):
        raise AssertionError("status conservation failed")
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "HISTORICAL_QUESTION_ONLY_OPPORTUNITY_DIAGNOSTIC_NOT_EFFICACY",
        "prediction_sha256": artifact["prediction_sha256"],
        "source_audit_sha256": digest(audit),
        "questions": len(predictions),
        "audit_rows": total_audit_rows,
        "repeated_configuration_rows_are_not_independent_questions": True,
        "status_counts": status_counts,
        "status_outcomes": status_outcomes,
        "capability_overlap_note": "capability buckets overlap and must not be summed",
        "capabilities": capability_rows,
        "question_rows": question_rows,
        "cost_and_authority": {
            "provider_calls": 0,
            "model_calls": 0,
            "tool_calls": 0,
            "token_spend": 0,
            "answer_mutations": 0,
            "execution_authorizations": 0,
            "promotion_changes": 0,
        },
        "non_claims": [
            "historical overlap is not causal tool effect",
            "question structure is not verifier applicability",
            "historical rescue overlap is not expected rescue probability",
            "the twenty known questions are development data, not a holdout",
            "no route is calibrated or promoted",
        ],
    }
    report["report_sha256"] = digest(report)
    return report
