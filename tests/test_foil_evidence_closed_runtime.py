from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_answer_selector import SelectorPolicy  # noqa: E402
from foil_benchmark_budget import BenchmarkTokenLedger  # noqa: E402
from foil_bounded_answer_constructor import (  # noqa: E402
    ConstructorDraft,
    ConstructorPolicy,
)
from foil_evidence_closed_runtime import (  # noqa: E402
    EvidenceClosedRuntimePolicy,
    run_evidence_closed_benchmark,
)
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    AtomicClaim,
    ClaimKind,
    ComputationBinding,
    ComputationReceipt,
    ContentSafety,
    EvidenceDocument,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
)
from foil_retrieval_claim_comparator import (  # noqa: E402
    ClaimStatus,
    ComparatorPolicy,
    SemanticComparison,
)
from foil_route_opportunity import QUESTION_INPUT_SCHEMA  # noqa: E402
from foil_smart_tool_value import UtilityWeights  # noqa: E402
from foil_tool_contract import ToolFamily, ToolOperation  # noqa: E402
from foil_tool_plan_v2 import (  # noqa: E402
    PlanStep,
    PlanValuePolicy,
    ToolPlanContractV2,
    ToolPlanCost,
)


QUESTION = "Which section of the Employment Rights Act governs this regulation?"


def raw_task(question: str = QUESTION) -> dict[str, object]:
    return {"schema": QUESTION_INPUT_SCHEMA, "task_id": "task-1", "question": question}


def obligation(question: str = QUESTION, kind: AnswerKind = AnswerKind.EXACT_TEXT) -> QuestionObligation:
    return QuestionObligation("task-1", digest(question), kind)


def retrieval_plan(a0: str, question: str = QUESTION) -> ToolPlanContractV2:
    return ToolPlanContractV2(
        "task-1", digest(question), digest(a0), "retrieval-plan", "1",
        (PlanStep("retrieve", ToolFamily.RETRIEVAL, ToolOperation.WEB_RETRIEVAL, digest(question)),),
        ToolPlanCost(
            maximum_input_tokens=20,
            maximum_output_tokens=8,
            maximum_tool_calls=2,
            maximum_search_calls=1,
            maximum_fetch_calls=1,
            maximum_sources=1,
            maximum_evidence_characters=9,
            maximum_model_passes=2,
            maximum_latency_ms=100,
        ),
        True,
    )


def retrieval_packet(question: str = QUESTION, *, safety: ContentSafety = ContentSafety.SANITIZED_DATA_ONLY) -> EvidencePacket:
    document = EvidenceDocument(
        "doc-1", "https://example.com/statute", "Statute", "section 7",
        "2026-08-28T00:00:00Z", SourceClass.PRIMARY, "statute", safety,
    )
    span = EvidenceSpan("span-1", "doc-1", 0, 9, "section 7")
    return EvidencePacket(
        digest(question), (document,), (span,), input_tokens=10, output_tokens=5,
        tool_calls=2, search_calls=1, fetch_calls=1, latency_ms=10,
    )


def semantic(claim: AtomicClaim, spans: tuple[EvidenceSpan, ...]) -> SemanticComparison:
    status = ClaimStatus.SUPPORTED if claim.normalized_value == "section 7" else ClaimStatus.CONTRADICTED
    return SemanticComparison(status, 990_000, (spans[0].span_id,), "synthetic_blind_comparison", 4, 0, 1)


def constructor(question: str, item: QuestionObligation, packet: EvidencePacket, cap: int) -> ConstructorDraft:
    if cap != 2:
        raise AssertionError("unexpected constructor cap")
    claim = AtomicClaim(
        "claim-b", "section 7", ClaimKind.ANSWER, "section 7",
        evidence_span_ids=("span-1",),
    )
    return ConstructorDraft("section 7", (claim,), 6, 0, 2, "bounded_extract")


def policy(*, selection: bool = True) -> EvidenceClosedRuntimePolicy:
    return EvidenceClosedRuntimePolicy(
        enabled=True,
        plan_value=PlanValuePolicy(enabled=True, benchmark_exploration=True),
        weights=UtilityWeights(1_000_000, 2_000_000, 500_000, token_price_microunits=1),
        comparator=ComparatorPolicy(
            semantic_enabled=True,
            allow_unadmitted_benchmark_selection=True,
            minimum_semantic_confidence_ppm=950_000,
        ),
        constructor=ConstructorPolicy(enabled=True, maximum_output_tokens=2),
        selector=SelectorPolicy(benchmark_selection_enabled=selection),
    )


class EvidenceClosedRuntimeTests(unittest.TestCase):
    def test_end_to_end_retrieval_comparison_constructs_and_selects(self) -> None:
        a0 = "section 3"
        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),),
            plan_evidence={}, ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(),
            constructor_runner=constructor, semantic_comparator=semantic,
        )
        trace = receipt.trace()
        self.assertEqual(final, "section 7")
        self.assertEqual(trace["selection"]["outcome"], "SELECT_B_BENCHMARK_UNADMITTED")
        self.assertEqual(trace["active_route"]["action"], "SELECT_VERIFIED")
        self.assertEqual(trace["ledger_after"]["spent_total_tokens"], 28)
        self.assertFalse(trace["constructor_a0_exposed"])
        self.assertFalse(trace["comparator_answer_identity_exposed"])
        self.assertFalse(trace["production_authorized"])

    def test_correct_a0_skips_constructor_and_is_preserved(self) -> None:
        a0 = "section 7"
        called = False

        def must_not_construct(*args: object) -> ConstructorDraft:
            nonlocal called
            called = True
            raise AssertionError("supported A0 must skip constructor")

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),),
            plan_evidence={}, ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(),
            constructor_runner=must_not_construct, semantic_comparator=semantic,
        )
        self.assertFalse(called)
        self.assertEqual(final, a0)
        self.assertEqual(receipt.trace()["constructor"]["reason"], "a0_supported_skip_constructor")
        self.assertEqual(receipt.ledger_after["spent_total_tokens"], 20)

    def test_low_confidence_or_disabled_selection_preserves_a0(self) -> None:
        a0 = "section 3"

        def weak(claim: AtomicClaim, spans: tuple[EvidenceSpan, ...]) -> SemanticComparison:
            return SemanticComparison(ClaimStatus.CONTRADICTED, 800_000, ("span-1",), "below_floor", 4, 0, 1)

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),), plan_evidence={},
            ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(), constructor_runner=constructor,
            semantic_comparator=weak,
        )
        self.assertEqual(final, a0)
        self.assertEqual(receipt.trace()["selection"]["outcome"], "KEEP_A0_NO_CONTRADICTION")

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),), plan_evidence={},
            ledger=BenchmarkTokenLedger(28), policy=policy(selection=False),
            plan_runner=lambda plan, task: retrieval_packet(), constructor_runner=constructor,
            semantic_comparator=semantic,
        )
        self.assertEqual(final, a0)
        self.assertEqual(receipt.trace()["selection"]["outcome"], "KEEP_A0_AUTHORITY_DISABLED")

    def test_unsafe_content_and_token_overrun_fail_closed(self) -> None:
        a0 = "section 3"
        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),), plan_evidence={},
            ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(safety=ContentSafety.RAW_UNTRUSTED),
            constructor_runner=constructor, semantic_comparator=semantic,
        )
        self.assertEqual(final, a0)
        self.assertFalse(receipt.cost_accounting_complete)
        self.assertEqual(receipt.ledger_after["reserved_total_tokens"], 0)

        def overrun(plan: ToolPlanContractV2, task: object) -> EvidencePacket:
            packet = retrieval_packet()
            return EvidencePacket(
                packet.question_digest, packet.documents, packet.spans,
                input_tokens=21, output_tokens=8, tool_calls=2,
                search_calls=1, fetch_calls=1, latency_ms=10,
            )

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),), plan_evidence={},
            ledger=BenchmarkTokenLedger(28), policy=policy(), plan_runner=overrun,
            constructor_runner=constructor, semantic_comparator=semantic,
        )
        self.assertEqual(final, a0)
        self.assertFalse(receipt.cost_accounting_complete)

    def test_constructor_provider_exception_preserves_a0_and_marks_unknown_cost(self) -> None:
        a0 = "section 3"

        def failed_provider(*args: object) -> ConstructorDraft:
            raise TimeoutError("provider may have consumed tokens")

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(retrieval_plan(a0),),
            plan_evidence={}, ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(),
            constructor_runner=failed_provider, semantic_comparator=semantic,
        )
        self.assertEqual(final, a0)
        self.assertFalse(receipt.cost_accounting_complete)
        self.assertEqual(receipt.trace()["constructor"]["outcome"], "ERROR")
        self.assertEqual(receipt.ledger_after["reserved_total_tokens"], 0)

    def test_end_to_end_latency_and_money_envelopes_include_model_stages(self) -> None:
        a0 = "section 3"
        base = retrieval_plan(a0)
        tight = ToolPlanContractV2(
            **{
                **base.__dict__,
                "cost": ToolPlanCost(
                    maximum_input_tokens=20, maximum_output_tokens=8,
                    maximum_tool_calls=2, maximum_search_calls=1,
                    maximum_fetch_calls=1, maximum_sources=1,
                    maximum_evidence_characters=9, maximum_model_passes=2,
                    maximum_latency_ms=20, maximum_monetary_microunits=3,
                ),
            }
        )

        def priced_constructor(
            question: str, item: QuestionObligation, packet: EvidencePacket, cap: int
        ) -> ConstructorDraft:
            draft = constructor(question, item, packet, cap)
            return ConstructorDraft(
                draft.answer, draft.claims, draft.input_tokens,
                draft.cached_input_tokens, draft.output_tokens, draft.reason,
                latency_ms=11, monetary_microunits=2,
            )

        def priced_semantic(
            claim: AtomicClaim, spans: tuple[EvidenceSpan, ...]
        ) -> SemanticComparison:
            result = semantic(claim, spans)
            return SemanticComparison(
                result.status, result.confidence_ppm, result.evidence_span_ids,
                result.reason, result.input_tokens, result.cached_input_tokens,
                result.output_tokens, latency_ms=1, monetary_microunits=1,
            )

        final, receipt = run_evidence_closed_benchmark(
            raw_task(), a0, obligation(), plans=(tight,), plan_evidence={},
            ledger=BenchmarkTokenLedger(28), policy=policy(),
            plan_runner=lambda plan, task: retrieval_packet(),
            constructor_runner=priced_constructor,
            semantic_comparator=priced_semantic,
        )
        self.assertEqual(final, a0)
        self.assertFalse(receipt.cost_accounting_complete)

    def test_hidden_gold_and_plan_a0_binding_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed schema mismatch"):
            run_evidence_closed_benchmark(
                raw_task() | {"gold": "section 7"}, "section 3", obligation(),
                plans=(retrieval_plan("section 3"),), plan_evidence={},
                ledger=BenchmarkTokenLedger(28), policy=policy(),
                plan_runner=lambda plan, task: retrieval_packet(),
                constructor_runner=constructor, semantic_comparator=semantic,
            )
        with self.assertRaisesRegex(ValueError, "does not bind"):
            run_evidence_closed_benchmark(
                raw_task(), "different A0", obligation(),
                plans=(retrieval_plan("section 3"),), plan_evidence={},
                ledger=BenchmarkTokenLedger(28), policy=policy(),
                plan_runner=lambda plan, task: retrieval_packet(),
                constructor_runner=constructor, semantic_comparator=semantic,
            )

    def test_retrieval_to_computation_provenance_selects_benchmark_candidate(self) -> None:
        question = r"According to the current Fermi gas report, calculate the value \(6 * B\)."
        a0 = "29"
        plan = ToolPlanContractV2(
            "task-1", digest(question), digest(a0), "hybrid", "1",
            (
                PlanStep("retrieve", ToolFamily.RETRIEVAL, ToolOperation.SCHOLARLY_RETRIEVAL, digest(question)),
                PlanStep("compute", ToolFamily.COMPUTATION, ToolOperation.EXACT_ARITHMETIC, digest("6*B"), ("retrieve",)),
            ),
            ToolPlanCost(
                maximum_input_tokens=20, maximum_output_tokens=8,
                maximum_tool_calls=3, maximum_search_calls=1,
                maximum_fetch_calls=1, maximum_sources=1,
                maximum_evidence_characters=1, maximum_model_passes=2,
                maximum_latency_ms=100,
            ),
            True,
        )
        document = EvidenceDocument(
            "doc", "https://example.com/paper", "Paper", "5",
            "2026-08-28", SourceClass.SCHOLARLY, "paper",
        )
        span = EvidenceSpan("span-b", "doc", 0, 1, "5")
        computation = ComputationReceipt(
            "compute-1", "6 * B", (ComputationBinding("B", "5", "span-b"),), "30"
        )
        packet = EvidencePacket(
            digest(question), (document,), (span,), (computation,),
            input_tokens=10, output_tokens=5, tool_calls=3,
            search_calls=1, fetch_calls=1, latency_ms=10,
        )

        def build(question: str, item: QuestionObligation, packet: EvidencePacket, cap: int) -> ConstructorDraft:
            claim = AtomicClaim(
                "claim-30", "30", ClaimKind.COMPUTATION_RESULT, "30",
                computation_receipt_ids=("compute-1",),
            )
            return ConstructorDraft("30", (claim,), 6, 0, 2, "computed_candidate")

        final, receipt = run_evidence_closed_benchmark(
            raw_task(question), a0, obligation(question, AnswerKind.NUMBER),
            plans=(plan,), plan_evidence={}, ledger=BenchmarkTokenLedger(28),
            policy=policy(), plan_runner=lambda plan, task: packet,
            constructor_runner=build,
            semantic_comparator=lambda claim, spans: SemanticComparison(
                ClaimStatus.CONTRADICTED, 990_000, ("span-b",), "wrong_numeric_candidate", 4, 0, 1
            ),
        )
        self.assertEqual(final, "30")
        verdict = receipt.trace()["b_assessment"]["verdicts"][0]
        self.assertEqual(verdict["method"], "EXACT_COMPUTATION")
        self.assertEqual(verdict["authority"], "HYBRID_UNADMITTED")


if __name__ == "__main__":
    unittest.main()
