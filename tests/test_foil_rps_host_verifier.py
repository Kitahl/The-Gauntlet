"""Tests for answer-blind deterministic RPS Stage 1."""

from __future__ import annotations

from dataclasses import fields
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps_host_verifier import (  # noqa: E402
    HostTaskDescriptor,
    HostTaskType,
    JsonFieldSpec,
    JsonPrimitive,
    Stage1Outcome,
    select_check,
    verify_answer,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task(task_type: HostTaskType, **kwargs: object) -> HostTaskDescriptor:
    return HostTaskDescriptor(
        task_digest=digest("task"),
        answer_form_digest=digest("answer-form"),
        task_type=task_type,
        **kwargs,
    )


class HostVerifierTests(unittest.TestCase):
    def test_selector_has_no_answer_field_or_parameter(self):
        self.assertNotIn("answer", {field.name for field in fields(HostTaskDescriptor)})
        first = select_check(task(HostTaskType.ARITHMETIC_EQUALITY))
        second = select_check(task(HostTaskType.ARITHMETIC_EQUALITY))
        self.assertEqual(first, second)

    def test_certified_arithmetic_pass_fail_and_decline(self):
        selected = select_check(task(HostTaskType.ARITHMETIC_EQUALITY))
        self.assertEqual(
            verify_answer(selected, r"\[2+2=4\]").outcome, Stage1Outcome.PASS
        )
        failed = verify_answer(selected, r"\[2+2=5\]")
        self.assertEqual(failed.outcome, Stage1Outcome.FAIL)
        self.assertIsNotNone(failed.receipt)
        self.assertEqual(
            verify_answer(selected, "The answer is probably four.").outcome,
            Stage1Outcome.NOT_APPLICABLE,
        )
        structured = verify_answer(
            selected,
            ["Suppose a different case.", r"\[2+2=5\]"],
        )
        self.assertEqual(structured.outcome, Stage1Outcome.FAIL)
        self.assertIsNotNone(structured.receipt)
        self.assertEqual(structured.receipt.candidate_digest, structured.candidate_digest)

    def test_powers_are_separate_from_certified_v2(self):
        ordinary = select_check(task(HostTaskType.ARITHMETIC_EQUALITY))
        power = select_check(task(HostTaskType.ARITHMETIC_POWER_EQUALITY))
        text = r"\[1404=2^2\times3^2\times13\]"
        self.assertEqual(
            verify_answer(ordinary, text).outcome, Stage1Outcome.NOT_APPLICABLE
        )
        self.assertEqual(verify_answer(power, text).outcome, Stage1Outcome.FAIL)

    def test_closed_json_schema(self):
        selected = select_check(
            task(
                HostTaskType.JSON_SCHEMA,
                json_fields=(
                    JsonFieldSpec("answer", JsonPrimitive.INTEGER),
                    JsonFieldSpec("explanation", JsonPrimitive.STRING),
                ),
            )
        )
        self.assertEqual(
            verify_answer(selected, {"answer": 4, "explanation": "exact"}).outcome,
            Stage1Outcome.PASS,
        )
        self.assertEqual(
            verify_answer(selected, {"answer": "4", "explanation": "exact"}).outcome,
            Stage1Outcome.FAIL,
        )
        self.assertEqual(
            verify_answer(
                selected, {"answer": 4, "explanation": "exact", "extra": True}
            ).outcome,
            Stage1Outcome.FAIL,
        )

    def test_structured_unit_dimension_is_exact_and_unknown_declines(self):
        selected = select_check(
            task(HostTaskType.UNIT_QUANTITY, expected_dimension="LENGTH")
        )
        self.assertEqual(
            verify_answer(selected, {"value": "150", "unit": "cm"}).outcome,
            Stage1Outcome.PASS,
        )
        self.assertEqual(
            verify_answer(selected, {"value": "3", "unit": "kg"}).outcome,
            Stage1Outcome.FAIL,
        )
        self.assertEqual(
            verify_answer(selected, {"value": "3", "unit": "parsec"}).outcome,
            Stage1Outcome.NOT_APPLICABLE,
        )

    def test_processbench_first_error_is_computed_before_candidate(self):
        selected = select_check(
            task(
                HostTaskType.PROCESSBENCH_FIRST_ERROR,
                source_steps=(r"\[2+2=4\]", r"\[3+3=7\]", r"\[4+4=9\]"),
            )
        )
        self.assertEqual(selected.spec["expected_answer"], "1")
        self.assertEqual(verify_answer(selected, "1").outcome, Stage1Outcome.PASS)
        mismatch = verify_answer(selected, {"answer": "OK", "abstain": False})
        self.assertEqual(mismatch.outcome, Stage1Outcome.FAIL)
        self.assertEqual(
            verify_answer(selected, {"answer": "", "abstain": True}).outcome,
            Stage1Outcome.UNCERTAIN,
        )

    def test_processbench_vacuous_check_declines_instead_of_passing(self):
        selected = select_check(
            task(
                HostTaskType.PROCESSBENCH_FIRST_ERROR,
                source_steps=(r"\[2+2=4\]", r"\[3+3=6\]"),
            )
        )
        self.assertTrue(selected.spec["vacuous"])
        result = verify_answer(selected, "OK")
        self.assertEqual(result.outcome, Stage1Outcome.NOT_APPLICABLE)
        self.assertEqual(result.reason, "vacuous_no_certified_first_error")

    def test_unsupported_task_declines_without_receipt(self):
        selected = select_check(task(HostTaskType.UNSUPPORTED))
        result = verify_answer(selected, "anything")
        self.assertEqual(result.outcome, Stage1Outcome.NOT_APPLICABLE)
        self.assertIsNone(result.receipt)


if __name__ == "__main__":
    unittest.main()
