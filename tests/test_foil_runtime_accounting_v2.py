from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_active_runtime_v2 import FoilRuntimePolicyV2, RuntimeOutcomeV2  # noqa: E402
from foil_bounded_answer_constructor_v2 import ConstructorPolicyV2  # noqa: E402
from foil_evidence_archive import RawEvidenceArchive  # noqa: E402
from foil_evidence_contract import AnswerKind, QuestionObligation  # noqa: E402
from foil_retrieval_claim_comparator import ComparatorPolicy  # noqa: E402
from foil_route_opportunity_v2 import QUESTION_SCHEMA_V2, RuntimeToolFamily  # noqa: E402
from foil_runtime_active import run_foil  # noqa: E402
from foil_runtime_token_ledger import RuntimeTokenLedger  # noqa: E402
from foil_runtime_tools_v2 import ExactArithmeticAdapterV2  # noqa: E402
from foil_tool_contract_v2 import (  # noqa: E402
    ResourceEnvelopeV2,
    TokenUsageV2,
    ToolOutcomeV2,
    ToolReceiptV2,
)


QUESTION = r"Compute \(2 + 3 * 4\)?"


def _task() -> dict[str, object]:
    return {"schema": QUESTION_SCHEMA_V2, "task_id": "accounting", "question": QUESTION}


def _obligation() -> QuestionObligation:
    return QuestionObligation("accounting", digest(QUESTION), AnswerKind.NUMBER)


def _policy() -> FoilRuntimePolicyV2:
    return FoilRuntimePolicyV2(True, True, ComparatorPolicy(), ConstructorPolicyV2())


class _TokenUsingArithmetic(ExactArithmeticAdapterV2):
    def probe(self, task):  # type: ignore[no-untyped-def]
        return replace(
            super().probe(task),
            envelope=ResourceEnvelopeV2(
                maximum_input_tokens=10,
                maximum_tool_calls=1,
                maximum_latency_ms=500,
            ),
        )

    def execute(self, contract, task, probe):  # type: ignore[no-untyped-def]
        return ToolReceiptV2(
            f"call-{contract.contract_digest[:16]}",
            contract.contract_digest,
            self.family,
            ToolOutcomeV2.RESOLVED,
            TokenUsageV2(input_tokens=3),
            1,
            0,
            0,
            candidate_answer="14",
            verification_expression="2+3*4",
        )


class RuntimeFailureAccountingTests(unittest.TestCase):
    def test_resource_overrun_retains_actual_spend(self) -> None:
        class OverrunAdapter(ExactArithmeticAdapterV2):
            def execute(self, contract, task, probe):  # type: ignore[no-untyped-def]
                return ToolReceiptV2(
                    f"call-{contract.contract_digest[:16]}",
                    contract.contract_digest,
                    self.family,
                    ToolOutcomeV2.RESOLVED,
                    TokenUsageV2(input_tokens=3),
                    1,
                    0,
                    0,
                    candidate_answer="14",
                    verification_expression="2+3*4",
                )

        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                _task(),
                "12",
                _obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: OverrunAdapter()},
                ledger=RuntimeTokenLedger(),
                policy=_policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.TOOL_ERROR)
        self.assertFalse(receipt.cost_accounting_complete)
        self.assertEqual(receipt.ledger_after["spent_usage"]["input_tokens"], 3)
        settlement = receipt.ledger_after["settlements"][0]
        self.assertTrue(settlement["cancelled"])
        self.assertIn("resource_envelope_exceeded", settlement["reason"])

    def test_persistence_failure_retains_previously_observed_spend(self) -> None:
        class BrokenArchive(RawEvidenceArchive):
            def store(self, contract, receipt):  # type: ignore[no-untyped-def]
                raise OSError("disk unavailable")

        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                _task(),
                "12",
                _obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: _TokenUsingArithmetic()},
                ledger=RuntimeTokenLedger(),
                policy=_policy(),
                archive=BrokenArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PERSISTENCE_ERROR)
        self.assertEqual(receipt.ledger_after["spent_usage"]["input_tokens"], 3)
        settlement = receipt.ledger_after["settlements"][0]
        self.assertTrue(settlement["cancelled"])
        self.assertEqual(settlement["reason"], "raw_evidence_persistence_failed")


if __name__ == "__main__":
    unittest.main()
