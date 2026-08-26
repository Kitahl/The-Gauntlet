"""Task-only blind-rival contract and mechanical Stage-2 comparison.

The request builder has no incumbent-answer parameter. It accepts only a
closed task object, constructs a prescribed alternate route, and binds that
prompt by digest. Stage 2 may keep A on mechanically normalized agreement; a
disagreement, abstention, or unsupported representation abstains unless some
separate future deterministic discriminator resolves it.

This module performs no I/O, provider calls, profile writes, or production
answer mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from enum import Enum
from fractions import Fraction

from foil_rps_v062 import BlindRivalReceipt

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")
_RATIONAL = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]+)?|[0-9]+/[1-9][0-9]*)$")


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


class ComparatorKind(str, Enum):
    PROCESSBENCH_FIRST_ERROR = "PROCESSBENCH_FIRST_ERROR"
    EXACT_MULTIPLE_CHOICE = "EXACT_MULTIPLE_CHOICE"
    CANONICAL_RATIONAL = "CANONICAL_RATIONAL"


class BlindComparisonOutcome(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    ABSTAIN = "ABSTAIN"
    UNSUPPORTED = "UNSUPPORTED"


class Stage2Action(str, Enum):
    KEEP_BASE = "KEEP_BASE"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class RivalTask:
    task_digest: str
    answer_form_digest: str
    benchmark: str
    problem: str
    steps: tuple[str, ...]
    comparator: ComparatorKind

    def __post_init__(self) -> None:
        _require_digest("task_digest", self.task_digest)
        _require_digest("answer_form_digest", self.answer_form_digest)
        if self.benchmark not in {
            "PROCESSBENCH_GSM8K",
            "MULTIPLE_CHOICE",
            "NUMERIC_ANSWER",
        }:
            raise ValueError("unsupported blind-rival benchmark")
        if not isinstance(self.problem, str) or not self.problem.strip():
            raise ValueError("problem must be non-empty text")
        if not isinstance(self.steps, tuple) or not all(
            isinstance(step, str) and step.strip() for step in self.steps
        ):
            raise TypeError("steps must be a tuple of non-empty strings")
        if self.benchmark == "PROCESSBENCH_GSM8K" and not self.steps:
            raise ValueError("ProcessBench blind rivals require source steps")
        if self.benchmark != "PROCESSBENCH_GSM8K" and self.steps:
            raise ValueError("only ProcessBench blind rivals accept source steps")
        if not isinstance(self.comparator, ComparatorKind):
            raise TypeError("comparator must be ComparatorKind")
        expected = {
            "PROCESSBENCH_GSM8K": ComparatorKind.PROCESSBENCH_FIRST_ERROR,
            "MULTIPLE_CHOICE": ComparatorKind.EXACT_MULTIPLE_CHOICE,
            "NUMERIC_ANSWER": ComparatorKind.CANONICAL_RATIONAL,
        }[self.benchmark]
        if self.comparator is not expected:
            raise ValueError("benchmark/comparator mismatch")


@dataclass(frozen=True)
class BlindRivalRequest:
    task_digest: str
    answer_form_digest: str
    comparator: ComparatorKind
    method_id: str
    prompt: str
    prompt_digest: str
    request_digest: str
    incumbent_withheld: bool = True

    def __post_init__(self) -> None:
        _require_digest("task_digest", self.task_digest)
        _require_digest("answer_form_digest", self.answer_form_digest)
        _require_digest("prompt_digest", self.prompt_digest)
        _require_digest("request_digest", self.request_digest)
        if not isinstance(self.comparator, ComparatorKind):
            raise TypeError("comparator must be ComparatorKind")
        if not isinstance(self.method_id, str) or not self.method_id.strip():
            raise ValueError("method_id must be non-empty text")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be non-empty text")
        if self.incumbent_withheld is not True:
            raise ValueError("blind-rival requests require incumbent_withheld=true")
        if self.prompt_digest != digest(self.prompt):
            raise ValueError("prompt_digest does not bind prompt")
        expected = digest(
            {
                "schema": "foil.rps-stage2-blind-request.v1",
                "task_digest": self.task_digest,
                "answer_form_digest": self.answer_form_digest,
                "comparator": self.comparator.value,
                "method_id": self.method_id,
                "prompt_digest": self.prompt_digest,
                "incumbent_withheld": True,
            }
        )
        if self.request_digest != expected:
            raise ValueError("request_digest does not bind request")


def _processbench_prompt(task: RivalTask) -> tuple[str, str]:
    steps = "\n".join(f"[{index}] {step}" for index, step in enumerate(task.steps))
    method_id = "reverse-check-then-forward-earliest-v1"
    prompt = (
        "Solve this task in a fresh context. No previous candidate answer is supplied. "
        "First recompute the proposed solution from the last step backward, then scan "
        "forward to identify the earliest error. Return answer=OK if every step is "
        "correct; otherwise return the zero-based integer index of the first erroneous "
        "step. Set abstain=false unless the text is insufficient. In method_summary, "
        "briefly name the recomputation that determined the answer. Do not use tools, "
        "files, the network, or outside context. Return only the required JSON object.\n\n"
        f"Problem:\n{task.problem}\n\nProposed solution:\n{steps}"
    )
    return method_id, prompt


def _multiple_choice_prompt(task: RivalTask) -> tuple[str, str]:
    method_id = "elimination-from-question-only-v1"
    return method_id, (
        "Solve this multiple-choice task in a fresh context. No previous candidate "
        "answer is supplied. Eliminate options from the question evidence, then return "
        "exactly one option letter in answer. Set abstain=true if the supplied task is "
        "insufficient. Briefly name the elimination in method_summary. Do not use tools, "
        "files, the network, or outside context. Return only the required JSON object.\n\n"
        f"Task:\n{task.problem}"
    )


def _numeric_prompt(task: RivalTask) -> tuple[str, str]:
    method_id = "independent-exact-recomputation-v1"
    return method_id, (
        "Solve this numeric task in a fresh context. No previous candidate answer is "
        "supplied. Recompute with exact rational arithmetic and return only the final "
        "integer, decimal, or fraction in answer. Set abstain=true if the task is "
        "insufficient. Briefly name the recomputation in method_summary. Do not use "
        "tools, files, the network, or outside context. Return only the required JSON "
        f"object.\n\nTask:\n{task.problem}"
    )


def build_blind_rival_request(task: RivalTask) -> BlindRivalRequest:
    """Build B from task-only state; this signature intentionally cannot accept A."""

    if not isinstance(task, RivalTask):
        raise TypeError("task must be RivalTask")
    if task.comparator is ComparatorKind.PROCESSBENCH_FIRST_ERROR:
        method_id, prompt = _processbench_prompt(task)
    elif task.comparator is ComparatorKind.EXACT_MULTIPLE_CHOICE:
        method_id, prompt = _multiple_choice_prompt(task)
    else:
        method_id, prompt = _numeric_prompt(task)
    prompt_digest = digest(prompt)
    request_digest = digest(
        {
            "schema": "foil.rps-stage2-blind-request.v1",
            "task_digest": task.task_digest,
            "answer_form_digest": task.answer_form_digest,
            "comparator": task.comparator.value,
            "method_id": method_id,
            "prompt_digest": prompt_digest,
            "incumbent_withheld": True,
        }
    )
    return BlindRivalRequest(
        task_digest=task.task_digest,
        answer_form_digest=task.answer_form_digest,
        comparator=task.comparator,
        method_id=method_id,
        prompt=prompt,
        prompt_digest=prompt_digest,
        request_digest=request_digest,
    )


def _closed_answer(value: object, *, rival: bool) -> tuple[str, bool] | None:
    expected = {"answer", "abstain", "method_summary"} if rival else {
        "answer",
        "abstain",
    }
    if not isinstance(value, dict) or set(value) != expected:
        return None
    if not isinstance(value["answer"], str) or not isinstance(value["abstain"], bool):
        return None
    if rival and (
        not isinstance(value["method_summary"], str)
        or not 1 <= len(value["method_summary"].strip()) <= 400
    ):
        return None
    return value["answer"].strip(), value["abstain"]


def _normalize(kind: ComparatorKind, answer: str) -> str | None:
    if kind is ComparatorKind.PROCESSBENCH_FIRST_ERROR:
        upper = answer.upper()
        return upper if upper == "OK" or _INTEGER.fullmatch(answer) else None
    if kind is ComparatorKind.EXACT_MULTIPLE_CHOICE:
        upper = answer.upper()
        return upper if upper in {"A", "B", "C", "D", "E"} else None
    if not _RATIONAL.fullmatch(answer):
        return None
    try:
        return str(Fraction(answer))
    except (ValueError, ZeroDivisionError):
        return None


def compare_answers(
    kind: ComparatorKind, base_answer: object, rival_answer: object
) -> BlindComparisonOutcome:
    if not isinstance(kind, ComparatorKind):
        raise TypeError("kind must be ComparatorKind")
    base = _closed_answer(base_answer, rival=False)
    rival = _closed_answer(rival_answer, rival=True)
    if base is None or rival is None:
        return BlindComparisonOutcome.UNSUPPORTED
    if base[1] or rival[1]:
        return BlindComparisonOutcome.ABSTAIN
    normalized_base = _normalize(kind, base[0])
    normalized_rival = _normalize(kind, rival[0])
    if normalized_base is None or normalized_rival is None:
        return BlindComparisonOutcome.UNSUPPORTED
    return (
        BlindComparisonOutcome.AGREE
        if normalized_base == normalized_rival
        else BlindComparisonOutcome.DISAGREE
    )


def make_rival_receipt(
    request: BlindRivalRequest,
    rival_answer: object,
    *,
    model_route_digest: str,
    input_tokens: int,
    output_tokens: int,
) -> BlindRivalReceipt:
    if not isinstance(request, BlindRivalRequest):
        raise TypeError("request must be BlindRivalRequest")
    if _closed_answer(rival_answer, rival=True) is None:
        raise ValueError("rival answer violates the closed Stage-2 schema")
    _require_digest("model_route_digest", model_route_digest)
    return BlindRivalReceipt(
        task_digest=request.task_digest,
        answer_form_digest=request.answer_form_digest,
        rival_digest=digest(rival_answer),
        request_digest=request.request_digest,
        model_route_digest=model_route_digest,
        incumbent_withheld=True,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


@dataclass(frozen=True)
class Stage2Decision:
    outcome: BlindComparisonOutcome
    action: Stage2Action
    reason: str
    base_digest: str
    rival_digest: str
    selected_digest: str | None
    supporting_only: bool
    production_authorized: bool = False
    promotion_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, BlindComparisonOutcome):
            raise TypeError("outcome must be BlindComparisonOutcome")
        if not isinstance(self.action, Stage2Action):
            raise TypeError("action must be Stage2Action")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text")
        _require_digest("base_digest", self.base_digest)
        _require_digest("rival_digest", self.rival_digest)
        if self.selected_digest is not None:
            _require_digest("selected_digest", self.selected_digest)
        if self.production_authorized or self.promotion_authorized:
            raise ValueError("Stage 2 has no production or promotion authority")
        if self.action is Stage2Action.KEEP_BASE:
            if (
                self.outcome is not BlindComparisonOutcome.AGREE
                or self.selected_digest != self.base_digest
                or self.supporting_only is not True
            ):
                raise ValueError("agreement may only support keeping A")
        elif self.selected_digest is not None or self.supporting_only:
            raise ValueError("abstention cannot select or support an answer")

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.rps-stage2-decision.v1",
            "outcome": self.outcome.value,
            "action": self.action.value,
            "reason": self.reason,
            "base_digest": self.base_digest,
            "rival_digest": self.rival_digest,
            "selected_digest": self.selected_digest,
            "supporting_only": self.supporting_only,
            "production_authorized": False,
            "promotion_authorized": False,
        }


def finalize_stage2(
    request: BlindRivalRequest,
    base_answer: object,
    rival_answer: object,
    receipt: BlindRivalReceipt,
) -> Stage2Decision:
    if not isinstance(request, BlindRivalRequest):
        raise TypeError("request must be BlindRivalRequest")
    if not isinstance(receipt, BlindRivalReceipt):
        raise TypeError("receipt must be BlindRivalReceipt")
    if receipt.task_digest != request.task_digest:
        raise ValueError("rival receipt task mismatch")
    if receipt.answer_form_digest != request.answer_form_digest:
        raise ValueError("rival receipt answer-form mismatch")
    if receipt.request_digest != request.request_digest:
        raise ValueError("rival receipt request mismatch")
    if receipt.rival_digest != digest(rival_answer):
        raise ValueError("rival receipt answer mismatch")
    outcome = compare_answers(request.comparator, base_answer, rival_answer)
    base_digest = digest(base_answer)
    if outcome is BlindComparisonOutcome.AGREE:
        return Stage2Decision(
            outcome,
            Stage2Action.KEEP_BASE,
            "blind_routes_mechanically_agree_supporting_only",
            base_digest,
            receipt.rival_digest,
            base_digest,
            True,
        )
    return Stage2Decision(
        outcome,
        Stage2Action.ABSTAIN,
        {
            BlindComparisonOutcome.DISAGREE: "blind_routes_disagree_without_discriminator",
            BlindComparisonOutcome.ABSTAIN: "at_least_one_route_abstained",
            BlindComparisonOutcome.UNSUPPORTED: "mechanical_comparator_unsupported",
        }[outcome],
        base_digest,
        receipt.rival_digest,
        None,
        False,
    )


def request_has_no_incumbent_surface() -> bool:
    forbidden = {"answer", "candidate", "incumbent", "gold", "correct"}
    return forbidden.isdisjoint(field.name.lower() for field in fields(RivalTask))
