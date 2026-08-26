"""Fail-closed tests for task-only blind-rival Stage 2."""

from __future__ import annotations

import hashlib
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps_blind_rival import (  # noqa: E402
    BlindComparisonOutcome,
    ComparatorKind,
    RivalTask,
    Stage2Action,
    build_blind_rival_request,
    compare_answers,
    digest,
    finalize_stage2,
    make_rival_receipt,
    request_has_no_incumbent_surface,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task() -> RivalTask:
    return RivalTask(
        task_digest=sha("task"),
        answer_form_digest=sha("answer-form"),
        benchmark="PROCESSBENCH_GSM8K",
        problem="Find the first erroneous step.",
        steps=(r"\[2+2=4\]", r"\[3+3=7\]"),
        comparator=ComparatorKind.PROCESSBENCH_FIRST_ERROR,
    )


def rival(answer: str, *, abstain: bool = False) -> dict[str, object]:
    return {
        "answer": answer,
        "abstain": abstain,
        "method_summary": "Recomputed the equalities in reverse and forward order.",
    }


class BlindRivalTests(unittest.TestCase):
    def test_request_builder_has_no_incumbent_or_answer_parameter(self):
        self.assertEqual(list(inspect.signature(build_blind_rival_request).parameters), ["task"])
        self.assertTrue(request_has_no_incumbent_surface())
        request = build_blind_rival_request(task())
        self.assertTrue(request.incumbent_withheld)
        self.assertNotIn("FROZEN-INCUMBENT-SENTINEL", request.prompt)

    def test_request_is_deterministic_and_task_changes_are_positive_control(self):
        first = build_blind_rival_request(task())
        second = build_blind_rival_request(task())
        self.assertEqual(first, second)
        changed = RivalTask(
            task_digest=sha("changed-task"),
            answer_form_digest=task().answer_form_digest,
            benchmark=task().benchmark,
            problem=task().problem + " Changed.",
            steps=task().steps,
            comparator=task().comparator,
        )
        self.assertNotEqual(
            first.request_digest, build_blind_rival_request(changed).request_digest
        )

    def test_processbench_choice_and_rational_comparators_are_closed(self):
        base = {"answer": "01", "abstain": False}
        self.assertIs(
            compare_answers(
                ComparatorKind.PROCESSBENCH_FIRST_ERROR, base, rival("1")
            ),
            BlindComparisonOutcome.UNSUPPORTED,
        )
        self.assertIs(
            compare_answers(
                ComparatorKind.EXACT_MULTIPLE_CHOICE,
                {"answer": "b", "abstain": False},
                rival("B"),
            ),
            BlindComparisonOutcome.AGREE,
        )
        self.assertIs(
            compare_answers(
                ComparatorKind.CANONICAL_RATIONAL,
                {"answer": "0.5", "abstain": False},
                rival("1/2"),
            ),
            BlindComparisonOutcome.AGREE,
        )
        self.assertIs(
            compare_answers(
                ComparatorKind.CANONICAL_RATIONAL,
                {"answer": "nan", "abstain": False},
                rival("nan"),
            ),
            BlindComparisonOutcome.UNSUPPORTED,
        )

    def test_agreement_supports_a_and_disagreement_abstains(self):
        request = build_blind_rival_request(task())
        matching = rival("OK")
        receipt = make_rival_receipt(
            request,
            matching,
            model_route_digest=sha("terra-low"),
            input_tokens=10,
            output_tokens=2,
        )
        agreed = finalize_stage2(
            request, {"answer": "OK", "abstain": False}, matching, receipt
        )
        self.assertIs(agreed.action, Stage2Action.KEEP_BASE)
        self.assertTrue(agreed.supporting_only)

        distinct = rival("1")
        distinct_receipt = make_rival_receipt(
            request,
            distinct,
            model_route_digest=sha("terra-low"),
            input_tokens=10,
            output_tokens=2,
        )
        disagreed = finalize_stage2(
            request,
            {"answer": "OK", "abstain": False},
            distinct,
            distinct_receipt,
        )
        self.assertIs(disagreed.outcome, BlindComparisonOutcome.DISAGREE)
        self.assertIs(disagreed.action, Stage2Action.ABSTAIN)
        self.assertIsNone(disagreed.selected_digest)

    def test_tampered_receipts_and_nonboolean_abstain_fail_closed(self):
        request = build_blind_rival_request(task())
        answer = rival("OK")
        receipt = make_rival_receipt(
            request,
            answer,
            model_route_digest=sha("route"),
            input_tokens=1,
            output_tokens=1,
        )
        tampered = dict(answer)
        tampered["answer"] = "1"
        with self.assertRaisesRegex(ValueError, "answer mismatch"):
            finalize_stage2(
                request, {"answer": "OK", "abstain": False}, tampered, receipt
            )
        malformed = {"answer": "OK", "abstain": "false", "method_summary": "x"}
        with self.assertRaisesRegex(ValueError, "closed Stage-2 schema"):
            make_rival_receipt(
                request,
                malformed,
                model_route_digest=sha("route"),
                input_tokens=1,
                output_tokens=1,
            )


if __name__ == "__main__":
    unittest.main()
