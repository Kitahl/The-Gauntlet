from __future__ import annotations

import sys
import tempfile
import unittest
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
from foil_tool_contract_v2 import TokenUsageV2, ToolOutcomeV2, ToolReceiptV2  # noqa: E402


QUESTION = r"Compute \(2 + 3 * 4\)?"


def raw_task() -> dict[str, object]:
    return {"schema": QUESTION_SCHEMA_V2, "task_id": "fault", "question": QUESTION}


def obligation() -> QuestionObligation:
    return QuestionObligation("fault", digest(QUESTION), AnswerKind.NUMBER)


def policy() -> FoilRuntimePolicyV2:
    return FoilRuntimePolicyV2(
        True, True, ComparatorPolicy(), ConstructorPolicyV2()
    )


class RuntimeBoundaryFaultTests(unittest.TestCase):
    def test_resource_overrun_is_typed_and_accounting_is_not_false_green(self) -> None:
        class OverrunAdapter(ExactArithmeticAdapterV2):
            def execute(self, contract, task, probe):  # type: ignore[no-untyped-def]
                return ToolReceiptV2(
                    f"call-{contract.contract_digest[:16]}",
                    contract.contract_digest,
                    self.family,
                    ToolOutcomeV2.RESOLVED,
                    TokenUsageV2(input_tokens=1),
                    1,
                    0,
                    0,
                    candidate_answer="14",
                    verification_expression="2+3*4",
                )

        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                raw_task(), "12", obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: OverrunAdapter()},
                ledger=RuntimeTokenLedger(), policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.TOOL_ERROR)
        self.assertIn("RESOURCE_OVERRUN", receipt.reason)
        self.assertFalse(receipt.cost_accounting_complete)

    def test_malformed_adapter_result_is_typed(self) -> None:
        class MalformedAdapter(ExactArithmeticAdapterV2):
            def execute(self, contract, task, probe):  # type: ignore[no-untyped-def]
                return {"answer": "14"}

        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                raw_task(), "12", obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: MalformedAdapter()},
                ledger=RuntimeTokenLedger(), policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.TOOL_ERROR)
        self.assertIn("MALFORMED_RESULT", receipt.reason)

    def test_persistence_failure_is_typed_and_cannot_report_resolution(self) -> None:
        class BrokenArchive(RawEvidenceArchive):
            def store(self, contract, receipt):  # type: ignore[no-untyped-def]
                raise OSError("disk unavailable")

        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                raw_task(), "12", obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2()},
                ledger=RuntimeTokenLedger(), policy=policy(),
                archive=BrokenArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PERSISTENCE_ERROR)
        self.assertFalse(receipt.answer_changed)
        self.assertFalse(receipt.cost_accounting_complete)

    def test_missing_archive_is_preflight_failure_not_stand_down(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires raw evidence archive"):
            run_foil(
                raw_task(), "12", obligation(),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2()},
                ledger=RuntimeTokenLedger(), policy=policy(), archive=None,
            )


if __name__ == "__main__":
    unittest.main()
