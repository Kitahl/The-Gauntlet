from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from egrt_types import digest  # noqa: E402
from foil_active_runtime_v2 import FoilRuntimePolicyV2, RuntimeOutcomeV2  # noqa: E402
from foil_bounded_answer_constructor_v2 import ConstructorPolicyV2  # noqa: E402
from foil_evidence_contract import AnswerKind, QuestionObligation  # noqa: E402
from foil_retrieval_claim_comparator import ComparatorPolicy  # noqa: E402
from foil_route_opportunity_v2 import QUESTION_SCHEMA_V2  # noqa: E402
from foil_runtime import run_foil as compatibility_run_foil  # noqa: E402
from foil_runtime_active import run_foil as canonical_run_foil  # noqa: E402
from foil_runtime_benchmark_integration import (  # noqa: E402
    ACCOUNTING_INVALID,
    ACCOUNTING_VALID,
    receipt_accounting_fields,
    run_benchmark_row,
)
from foil_runtime_token_ledger import RuntimeTokenLedger  # noqa: E402


class RuntimeBenchmarkIntegrationTests(unittest.TestCase):
    def _direct_run(self):  # type: ignore[no-untyped-def]
        question = "State the color named in the question: blue."
        task = {"schema": QUESTION_SCHEMA_V2, "task_id": "bench-row", "question": question}
        obligation = QuestionObligation("bench-row", digest(question), AnswerKind.EXACT_TEXT)
        policy = FoilRuntimePolicyV2(
            False,
            False,
            ComparatorPolicy(),
            ConstructorPolicyV2(),
            require_raw_archive=False,
        )
        return run_benchmark_row(
            task,
            "blue",
            obligation,
            adapters={},
            ledger=RuntimeTokenLedger(),
            policy=policy,
            archive=None,
        )

    def test_compatibility_entry_is_the_canonical_boundary(self) -> None:
        self.assertIs(compatibility_run_foil, canonical_run_foil)

    def test_direct_zero_usage_is_valid_when_explicitly_complete(self) -> None:
        final, row = self._direct_run()
        self.assertEqual(final, "blue")
        self.assertEqual(row["foil_runtime_outcome"], RuntimeOutcomeV2.DIRECT.value)
        self.assertEqual(row["accounting_status"], ACCOUNTING_VALID)
        self.assertTrue(row["cost_accounting_complete"])
        self.assertEqual(
            row["spent_usage"],
            {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
        )

    def test_incomplete_receipt_preserves_observed_spend_and_is_invalid(self) -> None:
        _, row = self._direct_run()
        receipt = row["foil_runtime_receipt"]
        self.assertIsInstance(receipt, dict)

        question = "State the color named in the question: blue."
        task = {"schema": QUESTION_SCHEMA_V2, "task_id": "bench-row", "question": question}
        obligation = QuestionObligation("bench-row", digest(question), AnswerKind.EXACT_TEXT)
        _, canonical_receipt = canonical_run_foil(
            task,
            "blue",
            obligation,
            adapters={},
            ledger=RuntimeTokenLedger(),
            policy=FoilRuntimePolicyV2(
                False,
                False,
                ComparatorPolicy(),
                ConstructorPolicyV2(),
                require_raw_archive=False,
            ),
            archive=None,
        )
        incomplete = replace(
            canonical_receipt,
            cost_accounting_complete=False,
            ledger_after={
                **canonical_receipt.ledger_after,
                "spent_usage": {
                    "input_tokens": 3,
                    "cached_input_tokens": 1,
                    "output_tokens": 2,
                    "total_tokens": 6,
                },
            },
        )
        fields = receipt_accounting_fields(incomplete)
        self.assertEqual(fields["accounting_status"], ACCOUNTING_INVALID)
        self.assertEqual(fields["spent_usage"]["total_tokens"], 6)  # type: ignore[index]
        self.assertIn(
            "runtime_marked_accounting_incomplete",
            fields["accounting_invalid_reasons"],
        )

    def test_missing_usage_is_not_converted_to_zero(self) -> None:
        question = "State the color named in the question: blue."
        task = {"schema": QUESTION_SCHEMA_V2, "task_id": "bench-row", "question": question}
        obligation = QuestionObligation("bench-row", digest(question), AnswerKind.EXACT_TEXT)
        _, receipt = canonical_run_foil(
            task,
            "blue",
            obligation,
            adapters={},
            ledger=RuntimeTokenLedger(),
            policy=FoilRuntimePolicyV2(
                False,
                False,
                ComparatorPolicy(),
                ConstructorPolicyV2(),
                require_raw_archive=False,
            ),
            archive=None,
        )
        fields = receipt_accounting_fields(
            replace(receipt, ledger_after={"schema": "foil.runtime-token-ledger.v2"})
        )
        self.assertEqual(fields["accounting_status"], ACCOUNTING_INVALID)
        self.assertIsNone(fields["spent_usage"])
        self.assertIn("spent_usage_missing", fields["accounting_invalid_reasons"])

    def test_total_mismatch_is_accounting_invalid(self) -> None:
        question = "State the color named in the question: blue."
        task = {"schema": QUESTION_SCHEMA_V2, "task_id": "bench-row", "question": question}
        obligation = QuestionObligation("bench-row", digest(question), AnswerKind.EXACT_TEXT)
        _, receipt = canonical_run_foil(
            task,
            "blue",
            obligation,
            adapters={},
            ledger=RuntimeTokenLedger(),
            policy=FoilRuntimePolicyV2(
                False,
                False,
                ComparatorPolicy(),
                ConstructorPolicyV2(),
                require_raw_archive=False,
            ),
            archive=None,
        )
        bad_usage = {
            "input_tokens": 1,
            "cached_input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 5,
        }
        fields = receipt_accounting_fields(
            replace(receipt, ledger_after={**receipt.ledger_after, "spent_usage": bad_usage})
        )
        self.assertEqual(fields["accounting_status"], ACCOUNTING_INVALID)
        self.assertEqual(fields["spent_usage"], bad_usage)
        self.assertIn("spent_usage_total_mismatch", fields["accounting_invalid_reasons"])


if __name__ == "__main__":
    unittest.main()
