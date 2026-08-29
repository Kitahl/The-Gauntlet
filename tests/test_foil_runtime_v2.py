from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_active_runtime_v2 import FoilRuntimePolicyV2, RuntimeOutcomeV2  # noqa: E402
from foil_bounded_answer_constructor_v2 import (  # noqa: E402
    ConstructorBoundaryFailure,
    ConstructorDraftV2,
    ConstructorPolicyV2,
    ConstructorRequestV2,
    ConstructorTimeout,
    run_bounded_constructor_v2,
)
from foil_contract_codec_v2 import parse_raw_tool_receipt_v2, parse_tool_contract_v2  # noqa: E402
from foil_evidence_archive import RawEvidenceArchive  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    AtomicClaim,
    ClaimKind,
    QuestionObligation,
)
from foil_retrieval_claim_comparator import (  # noqa: E402
    ClaimStatus,
    ComparatorPolicy,
    SemanticComparison,
)
from foil_route_opportunity_v2 import (  # noqa: E402
    QUESTION_SCHEMA_V2,
    OpportunityStatusV2,
    RuntimeToolFamily,
    discover_route_opportunity_v2,
)
from foil_runtime import run_foil  # noqa: E402
from foil_runtime_token_ledger import RuntimeLedgerError, RuntimeTokenLedger  # noqa: E402
from foil_runtime_tools_v2 import (  # noqa: E402
    ExactArithmeticAdapterV2,
    PassageRetrievalAdapterV2,
    ProbeStatusV2,
    RestrictedPythonAdapterV2,
    RetrievedPassageBatch,
    SymbolicLinearAdapterV2,
    ToolBoundaryFailure,
    ToolProbeV2,
)
from foil_tool_contract_v2 import (  # noqa: E402
    BoundaryFailureCode,
    OperationSpecOrigin,
    PassageEvidenceV2,
    ResourceEnvelopeV2,
    RouteValueEstimate,
    TokenUsageV2,
    ToolContractV2,
)


def task(question: str, task_id: str = "task-1") -> dict[str, object]:
    return {"schema": QUESTION_SCHEMA_V2, "task_id": task_id, "question": question}


def obligation(question: str, kind: AnswerKind = AnswerKind.NUMBER) -> QuestionObligation:
    return QuestionObligation("task-1", digest(question), kind)


def positive_value(token_cost: int = 0) -> RouteValueEstimate:
    return RouteValueEstimate(800_000, 900_000, 0, 1_000_000, 2_000_000, token_cost)


def policy(*, enabled: bool = True, change: bool = True, constructor: bool = False, comparator: ComparatorPolicy | None = None) -> FoilRuntimePolicyV2:
    return FoilRuntimePolicyV2(
        enabled,
        change,
        ComparatorPolicy() if comparator is None else comparator,
        ConstructorPolicyV2(enabled=constructor),
    )


class RouteOpportunityV2Tests(unittest.TestCase):
    def test_rejects_answer_or_gold_fields(self) -> None:
        raw = task("Compute 2 + 2?") | {"a0": "4"}
        with self.assertRaisesRegex(ValueError, "unknown=.*a0"):
            discover_route_opportunity_v2(raw)
        raw = task("Compute 2 + 2?") | {"gold": "4"}
        with self.assertRaisesRegex(ValueError, "unknown=.*gold"):
            discover_route_opportunity_v2(raw)

    def test_arithmetic_and_symbolic_are_distinct(self) -> None:
        arithmetic = discover_route_opportunity_v2(task(r"Compute \(2 + 3 * 4\)?"))
        self.assertEqual(arithmetic.candidates[0].family, RuntimeToolFamily.EXACT_ARITHMETIC)
        symbolic = discover_route_opportunity_v2(task("Solve 2*x + 3 = 11 for x."))
        self.assertEqual(symbolic.candidates[0].family, RuntimeToolFamily.SYMBOLIC_COMPUTATION)

    def test_incidental_math_span_is_not_an_answer_obligation(self) -> None:
        result = discover_route_opportunity_v2(
            task("Can two graphs have different numbers of $5$-cycles?")
        )
        self.assertEqual(result.status, OpportunityStatusV2.COVERAGE_GAP)
        self.assertEqual(result.candidates, ())

    def test_what_is_delimited_math_remains_supported(self) -> None:
        result = discover_route_opportunity_v2(task(r"What is \(2 + 3\)?"))
        self.assertEqual(result.candidates[0].family, RuntimeToolFamily.EXACT_ARITHMETIC)

    def test_coverage_gap_is_typed(self) -> None:
        result = discover_route_opportunity_v2(task("Tell me something interesting."))
        self.assertEqual(result.status, OpportunityStatusV2.COVERAGE_GAP)
        self.assertEqual(result.candidates, ())


class ContractAndLedgerV2Tests(unittest.TestCase):
    def contract(self) -> ToolContractV2:
        return ToolContractV2(
            "task-1",
            digest("q"),
            digest("a"),
            RuntimeToolFamily.EXACT_ARITHMETIC,
            "foil.test",
            "2",
            digest("2+2"),
            OperationSpecOrigin.HOST_DERIVED,
            ResourceEnvelopeV2(maximum_latency_ms=100),
            positive_value(),
            100,
        )

    def test_contract_round_trip_and_unknown_field_rejection(self) -> None:
        contract = self.contract()
        self.assertEqual(parse_tool_contract_v2(contract.trace()), contract)
        poisoned = contract.trace() | {"gold": "4"}
        with self.assertRaisesRegex(ValueError, "unknown=.*gold"):
            parse_tool_contract_v2(poisoned)

    def test_generated_operation_requires_admission(self) -> None:
        with self.assertRaisesRegex(ValueError, "formalization_admission"):
            ToolContractV2(
                "task-1", digest("q"), digest("a"),
                RuntimeToolFamily.SYMBOLIC_COMPUTATION,
                "foil.generated", "2", digest("x"),
                OperationSpecOrigin.ADMITTED_GENERATED,
                ResourceEnvelopeV2(maximum_latency_ms=100),
                positive_value(), 100,
            )

    def test_ledger_is_aggregate_unbounded_but_per_call_bounded(self) -> None:
        ledger = RuntimeTokenLedger()
        envelope = ResourceEnvelopeV2(maximum_input_tokens=10, maximum_tool_calls=1, maximum_latency_ms=100)
        for index in range(3):
            call_id = f"call-{index}"
            ledger.reserve(
                call_id=call_id,
                contract_digest=digest(call_id),
                envelope=envelope,
                value=positive_value(),
                provider_cap_enforced=True,
            )
            ledger.settle(
                call_id, usage=TokenUsageV2(10, 0, 0), tool_calls=1,
                latency_ms=10, monetary_microunits=0,
            )
        trace = ledger.trace()
        self.assertIsNone(trace["aggregate_token_ceiling"])
        self.assertEqual(trace["spent_usage"]["total_tokens"], 30)
        self.assertTrue(trace["conserved"])

    def test_ledger_declines_non_positive_value(self) -> None:
        value = RouteValueEstimate(0, 0, 0, 1, 1, 1)
        with self.assertRaisesRegex(RuntimeLedgerError, "not positive"):
            RuntimeTokenLedger().reserve(
                call_id="x", contract_digest=digest("x"),
                envelope=ResourceEnvelopeV2(maximum_latency_ms=10),
                value=value, provider_cap_enforced=True,
            )


class ConstructorV2Tests(unittest.TestCase):
    def request(self) -> ConstructorRequestV2:
        from foil_evidence_contract import EvidencePacket

        question = "According to the official source, which code applies?"
        return ConstructorRequestV2(
            question,
            obligation(question, AnswerKind.EXACT_TEXT),
            EvidencePacket(digest(question), (), ()),
            None,
        )

    def test_no_artificial_output_cap_is_valid(self) -> None:
        request = self.request()

        def runner(_: ConstructorRequestV2) -> ConstructorDraftV2:
            return ConstructorDraftV2(None, (), TokenUsageV2(12, 0, 4), "no evidence", digest("prompt"))

        receipt = run_bounded_constructor_v2(
            request, policy=ConstructorPolicyV2(enabled=True), runner=runner
        )
        self.assertEqual(receipt.outcome.value, "NO_CANDIDATE")
        self.assertEqual(receipt.usage.total_tokens, 16)

    def test_declared_timeout_keeps_real_accounting(self) -> None:
        request = self.request()

        def runner(_: ConstructorRequestV2) -> ConstructorDraftV2:
            raise ConstructorTimeout("timed out", usage=TokenUsageV2(8, 2, 1), latency_ms=99)

        receipt = run_bounded_constructor_v2(
            request, policy=ConstructorPolicyV2(enabled=True), runner=runner
        )
        self.assertEqual(receipt.outcome.value, "TIMEOUT")
        self.assertEqual(receipt.usage.total_tokens, 11)
        self.assertEqual(receipt.latency_ms, 99)

    def test_programmer_exception_is_not_silently_swallowed(self) -> None:
        request = self.request()

        def runner(_: ConstructorRequestV2) -> ConstructorDraftV2:
            raise ValueError("broken configuration")

        with self.assertRaisesRegex(ValueError, "broken configuration"):
            run_bounded_constructor_v2(
                request, policy=ConstructorPolicyV2(enabled=True), runner=runner
            )


class FoilRuntimeV2Tests(unittest.TestCase):
    def run_mechanical(self, question: str, a0: str, adapter: object) -> tuple[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            return run_foil(
                task(question),
                a0,
                obligation(question),
                adapters={adapter.family: adapter},  # type: ignore[attr-defined]
                ledger=RuntimeTokenLedger(),
                policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )

    def test_disabled_is_real_direct(self) -> None:
        question = r"Compute \(2 + 3 * 4\)?"
        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                task(question), "12", obligation(question),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2()},
                ledger=RuntimeTokenLedger(), policy=policy(enabled=False, change=False),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.DIRECT)
        self.assertEqual(receipt.probes, ())

    def test_exact_arithmetic_actively_repairs(self) -> None:
        final, receipt = self.run_mechanical(
            r"Compute \(2 + 3 * 4\)?", "12", ExactArithmeticAdapterV2()
        )
        self.assertEqual(final, "14")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.VERIFY_RESOLVED)
        self.assertTrue(receipt.answer_changed)
        self.assertFalse(receipt.trace()["shadow_only"])

    def test_numeric_result_cannot_replace_a_proposition(self) -> None:
        question = r"Compute \(2 + 3\), then answer whether the result is prime."
        with tempfile.TemporaryDirectory() as directory:
            ledger = RuntimeTokenLedger()
            final, receipt = run_foil(
                task(question),
                "Yes",
                obligation(question, AnswerKind.PROPOSITION),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2()},
                ledger=ledger,
                policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "Yes")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PRESERVED_A0)
        self.assertIn("answer_kind_mismatch=EXACT_ARITHMETIC", receipt.reason)
        self.assertIsNone(receipt.selected_family)
        self.assertEqual(ledger.spent_usage.total_tokens, 0)

    def test_correct_a0_is_preserved_and_resolved(self) -> None:
        final, receipt = self.run_mechanical(
            r"Compute \(2 + 3 * 4\)?", "14", ExactArithmeticAdapterV2()
        )
        self.assertEqual(final, "14")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PRESERVED_A0)
        self.assertFalse(receipt.answer_changed)

    def test_symbolic_linear_actively_repairs(self) -> None:
        final, receipt = self.run_mechanical(
            "Solve 2*x + 3 = 11 for x.", "3", SymbolicLinearAdapterV2()
        )
        self.assertEqual(final, "4")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.VERIFY_RESOLVED)

    def test_restricted_python_actively_repairs(self) -> None:
        question = "What is the exact output?\n```python\nprint(3 * 7)\n```"
        final, receipt = self.run_mechanical(question, "18", RestrictedPythonAdapterV2())
        self.assertEqual(final, "21")
        self.assertEqual(receipt.selected_family, RuntimeToolFamily.RESTRICTED_PYTHON)

    def test_coverage_gap_stands_down_without_tool(self) -> None:
        question = "Tell me something interesting."
        with tempfile.TemporaryDirectory() as directory:
            ledger = RuntimeTokenLedger()
            final, receipt = run_foil(
                task(question), "Original", obligation(question, AnswerKind.EXACT_TEXT),
                adapters={}, ledger=ledger, policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "Original")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.COVERAGE_GAP)
        self.assertEqual(ledger.spent_usage.total_tokens, 0)

    def retrieval_adapter(self) -> PassageRetrievalAdapterV2:
        content = "The official code is ZX-9."
        start = content.index("ZX-9")

        def retrieve(_: str, __: ResourceEnvelopeV2) -> RetrievedPassageBatch:
            return RetrievedPassageBatch(
                (
                    PassageEvidenceV2(
                        "doc-1", "https://example.org/official", "Official",
                        content, "2026-08-28T00:00:00Z", start, start + 4,
                        "INSTITUTIONAL", "example.org",
                    ),
                ),
                TokenUsageV2(4, 0, 2),
                2,
                20,
            )

        return PassageRetrievalAdapterV2(
            retrieve,
            envelope=ResourceEnvelopeV2(
                maximum_input_tokens=30, maximum_output_tokens=20,
                maximum_tool_calls=2, maximum_model_passes=3,
                maximum_latency_ms=200, maximum_evidence_characters=200,
            ),
            value=positive_value(5_000),
            tool_id="foil.test-retrieval", tool_version="1",
            provider_cap_enforced=True,
        )

    @staticmethod
    def constructor(request: ConstructorRequestV2) -> ConstructorDraftV2:
        span = request.evidence_packet.spans[0]
        claim = AtomicClaim(
            "claim-code", "ZX-9", ClaimKind.ANSWER, "ZX-9",
            evidence_span_ids=(span.span_id,),
        )
        return ConstructorDraftV2(
            "ZX-9", (claim,), TokenUsageV2(3, 0, 2),
            "answer copied from exact bound passage", digest("constructor-prompt"), 10,
        )

    def test_retrieval_archives_passage_and_preserves_without_contradiction(self) -> None:
        question = "According to the official source, which code applies?"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final, receipt = run_foil(
                task(question), "OLD", obligation(question, AnswerKind.EXACT_TEXT),
                adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: self.retrieval_adapter()},
                ledger=RuntimeTokenLedger(), policy=policy(constructor=True),
                archive=RawEvidenceArchive(root), constructor_runner=self.constructor,
            )
            files = list(root.glob("*.json"))
            self.assertEqual(len(files), 1)
            raw = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(final, "OLD")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.PRESERVED_A0)
        self.assertEqual(raw["raw_receipt"]["passages"][0]["passage"], "ZX-9")
        self.assertEqual(receipt.b_assessment["supported"], 1)

    def test_admitted_semantic_contradiction_can_unlock_retrieved_candidate(self) -> None:
        question = "According to the official source, which code applies?"

        def comparator(claim: AtomicClaim, spans: tuple[object, ...]) -> SemanticComparison:
            return SemanticComparison(
                ClaimStatus.CONTRADICTED, 1_000_000,
                tuple(getattr(item, "span_id") for item in spans),
                "admitted comparator found incumbent contradiction",
                input_tokens=1, output_tokens=1,
            )

        compare_policy = ComparatorPolicy(
            semantic_enabled=True,
            semantic_route_admitted=True,
            minimum_semantic_confidence_ppm=950_000,
        )
        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                task(question), "OLD", obligation(question, AnswerKind.EXACT_TEXT),
                adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: self.retrieval_adapter()},
                ledger=RuntimeTokenLedger(),
                policy=policy(constructor=True, comparator=compare_policy),
                archive=RawEvidenceArchive(Path(directory)),
                constructor_runner=self.constructor, semantic_comparator=comparator,
            )
        self.assertEqual(final, "ZX-9")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.FULL_RESOLVED)
        self.assertTrue(receipt.answer_changed)

    def test_uncalibrated_semantic_cannot_enter_active_selection(self) -> None:
        compare_policy = ComparatorPolicy(semantic_enabled=True, semantic_route_admitted=False)
        question = "According to the official source, which code applies?"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unadmitted semantic"):
                run_foil(
                    task(question), "OLD", obligation(question, AnswerKind.EXACT_TEXT),
                    adapters={RuntimeToolFamily.PASSAGE_RETRIEVAL: self.retrieval_adapter()},
                    ledger=RuntimeTokenLedger(),
                    policy=policy(constructor=True, comparator=compare_policy),
                    archive=RawEvidenceArchive(Path(directory)),
                    constructor_runner=self.constructor,
                    semantic_comparator=lambda claim, spans: SemanticComparison(
                        ClaimStatus.CONTRADICTED, 1_000_000, (), "unsafe"
                    ),
                )

    def test_tool_timeout_is_typed_and_preserves_a0(self) -> None:
        class TimeoutAdapter(ExactArithmeticAdapterV2):
            def execute(self, contract, task_value, probe):  # type: ignore[no-untyped-def]
                raise ToolBoundaryFailure(
                    BoundaryFailureCode.TIMEOUT, "host timeout", latency_ms=400
                )

        question = r"Compute \(2 + 3 * 4\)?"
        with tempfile.TemporaryDirectory() as directory:
            final, receipt = run_foil(
                task(question), "12", obligation(question),
                adapters={RuntimeToolFamily.EXACT_ARITHMETIC: TimeoutAdapter()},
                ledger=RuntimeTokenLedger(), policy=policy(),
                archive=RawEvidenceArchive(Path(directory)),
            )
        self.assertEqual(final, "12")
        self.assertEqual(receipt.outcome, RuntimeOutcomeV2.TOOL_TIMEOUT)
        self.assertTrue(receipt.cost_accounting_complete)

    def test_raw_receipt_codec_checks_offsets_and_digests(self) -> None:
        passage = PassageEvidenceV2(
            "doc", "https://example.org/x", "T", "abc ZX-9 xyz", "now",
            4, 8,
        )
        from foil_tool_contract_v2 import ToolOutcomeV2, ToolReceiptV2

        receipt = ToolReceiptV2(
            "call", digest("contract"), RuntimeToolFamily.PASSAGE_RETRIEVAL,
            ToolOutcomeV2.SUPPORTING, TokenUsageV2(), 1, 0, 0,
            passages=(passage,),
        )
        raw = receipt.trace(include_raw=True)
        self.assertEqual(parse_raw_tool_receipt_v2(raw), receipt)
        poisoned = json.loads(json.dumps(raw))
        poisoned["passages"][0]["passage"] = "wrong"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            parse_raw_tool_receipt_v2(poisoned)


if __name__ == "__main__":
    unittest.main()
