from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_benchmark_budget import BenchmarkTokenLedger  # noqa: E402
from foil_route_opportunity import QUESTION_INPUT_SCHEMA  # noqa: E402
from foil_smart_tool_runtime import (  # noqa: E402
    CallbackRetrievalAdapter,
    ExactArithmeticAdapter,
    RestrictedPythonOutputAdapter,
    RetrievalResult,
    SmartToolRuntimePolicy,
    run_smart_verify,
)
from foil_smart_tool_value import (  # noqa: E402
    DifficultyBand,
    UtilityWeights,
    ValueGatePolicy,
)
from foil_tool_contract import ToolCost, ToolFamily  # noqa: E402


def task(question: str) -> dict[str, object]:
    return {"schema": QUESTION_INPUT_SCHEMA, "task_id": "task-1", "question": question}


POLICY = SmartToolRuntimePolicy(
    enabled=True,
    value_gate=ValueGatePolicy(enabled=True, benchmark_exploration=True),
    weights=UtilityWeights(
        rescue_value_microunits=1_000_000,
        damage_loss_microunits=2_000_000,
        invalid_loss_microunits=500_000,
        token_price_microunits=1,
    ),
    allow_unadmitted_benchmark_selection=True,
)


class SmartToolRuntimeTests(unittest.TestCase):
    def test_exact_arithmetic_actively_repairs_wrong_a0(self) -> None:
        final, receipt = run_smart_verify(
            task(r"Compute \(2 + 3 * 4\)?"),
            "12",
            adapters={"SYMBOLIC_COMPUTATION": ExactArithmeticAdapter()},
            evidence={},
            ledger=BenchmarkTokenLedger(0),
            policy=POLICY,
        )
        trace = receipt.trace()
        self.assertEqual(final, "14")
        self.assertTrue(trace["active_verify_executed"])
        self.assertFalse(trace["shadow_only"])
        self.assertTrue(trace["answer_changed"])
        self.assertEqual(trace["active_route_receipt"]["action"], "SELECT_VERIFIED")
        self.assertEqual(trace["ledger_after"]["spent_total_tokens"], 0)

    def test_restricted_python_is_bounded_and_active(self) -> None:
        question = "What exact output does this Python program return?\n```python\nprint(3 * 7)\n```"
        final, receipt = run_smart_verify(
            task(question),
            "18",
            adapters={"CODE_EXECUTION": RestrictedPythonOutputAdapter()},
            evidence={},
            ledger=BenchmarkTokenLedger(0),
            policy=POLICY,
        )
        self.assertEqual(final, "21")
        self.assertEqual(receipt.selected_capability, "CODE_EXECUTION")
        self.assertEqual(receipt.trace()["contract"]["operation"], "RESTRICTED_PYTHON_OUTPUT")

    def test_retrieval_runs_and_spends_but_cannot_replace_a0(self) -> None:
        calls = 0

        def retrieve(question: str, maximum_tokens: int) -> RetrievalResult:
            nonlocal calls
            calls += 1
            self.assertEqual(maximum_tokens, 15)
            return RetrievalResult(
                "section 7",
                "The source identifies section 7.",
                ("https://example.com/statute",),
                10,
                0,
                5,
                25,
            )

        adapter = CallbackRetrievalAdapter(
            capability="WEB_SEARCH",
            runner=retrieve,
            maximum_cost=ToolCost(
                maximum_input_tokens=10,
                maximum_output_tokens=5,
                maximum_latency_ms=100,
            ),
            difficulty=DifficultyBand.HARD,
            provider_cap_enforced=True,
            tool_id="host.web",
            tool_version="1",
        )
        final, receipt = run_smart_verify(
            task("Which section of the Employment Rights Act governs this regulation?"),
            "section 3",
            adapters={"WEB_SEARCH": adapter},
            evidence={},
            ledger=BenchmarkTokenLedger(20),
            policy=POLICY,
        )
        self.assertEqual(calls, 1)
        self.assertEqual(final, "section 3")
        self.assertFalse(receipt.answer_changed)
        self.assertEqual(receipt.trace()["evidence"]["admission"], "SUPPORT_ONLY")
        self.assertEqual(receipt.ledger_after["spent_total_tokens"], 15)

    def test_budget_declines_before_retrieval_call(self) -> None:
        called = False

        def retrieve(question: str, maximum_tokens: int) -> RetrievalResult:
            nonlocal called
            called = True
            raise AssertionError("must not launch")

        adapter = CallbackRetrievalAdapter(
            capability="WEB_SEARCH",
            runner=retrieve,
            maximum_cost=ToolCost(
                maximum_input_tokens=10,
                maximum_output_tokens=5,
                maximum_latency_ms=100,
            ),
            difficulty=DifficultyBand.HARD,
            provider_cap_enforced=True,
            tool_id="host.web",
            tool_version="1",
        )
        final, receipt = run_smart_verify(
            task("Which section of the Employment Rights Act applies?"),
            "A",
            adapters={"WEB_SEARCH": adapter},
            evidence={},
            ledger=BenchmarkTokenLedger(14),
            policy=POLICY,
        )
        self.assertFalse(called)
        self.assertEqual(final, "A")
        self.assertFalse(receipt.active_verify_executed)

    def test_selection_is_a0_blind(self) -> None:
        kwargs = dict(
            raw_task=task(r"Compute \(11 + 9\)?"),
            adapters={"SYMBOLIC_COMPUTATION": ExactArithmeticAdapter()},
            evidence={},
            policy=POLICY,
        )
        _, first = run_smart_verify(a0="wrong-one", ledger=BenchmarkTokenLedger(0), **kwargs)
        _, second = run_smart_verify(a0="another wrong answer", ledger=BenchmarkTokenLedger(0), **kwargs)
        self.assertEqual(first.selected_capability, second.selected_capability)
        self.assertEqual(first.probes, second.probes)
        self.assertNotEqual(first.a0_digest, second.a0_digest)

    def test_hidden_gold_and_unknown_fields_never_enter_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed schema mismatch"):
            run_smart_verify(
                task(r"Compute \(2+2\)?") | {"gold": "4"},
                "3",
                adapters={"SYMBOLIC_COMPUTATION": ExactArithmeticAdapter()},
                evidence={},
                ledger=BenchmarkTokenLedger(0),
                policy=POLICY,
            )

    def test_adapter_exception_preserves_a0_and_marks_accounting_incomplete(self) -> None:
        def retrieve(question: str, maximum_tokens: int) -> RetrievalResult:
            raise RuntimeError("provider failed after launch")

        adapter = CallbackRetrievalAdapter(
            capability="WEB_SEARCH",
            runner=retrieve,
            maximum_cost=ToolCost(maximum_output_tokens=5, maximum_latency_ms=100),
            difficulty=DifficultyBand.HARD,
            provider_cap_enforced=True,
            tool_id="host.web",
            tool_version="1",
        )
        final, receipt = run_smart_verify(
            task("Which section of the Employment Rights Act applies?"),
            "A",
            adapters={"WEB_SEARCH": adapter},
            evidence={},
            ledger=BenchmarkTokenLedger(5),
            policy=POLICY,
        )
        self.assertEqual(final, "A")
        self.assertFalse(receipt.cost_accounting_complete)
        self.assertEqual(receipt.ledger_after["reserved_total_tokens"], 0)
    def test_generated_contract_cannot_change_a0_without_benchmark_opt_in(self) -> None:
        safe_policy = SmartToolRuntimePolicy(
            enabled=True,
            value_gate=ValueGatePolicy(enabled=True, benchmark_exploration=True),
            weights=UtilityWeights(
                rescue_value_microunits=1_000_000,
                damage_loss_microunits=2_000_000,
                invalid_loss_microunits=500_000,
            ),
        )
        final, receipt = run_smart_verify(
            task(r"Compute \(2+2\)?"),
            "3",
            adapters={"SYMBOLIC_COMPUTATION": ExactArithmeticAdapter()},
            evidence={},
            ledger=BenchmarkTokenLedger(0),
            policy=safe_policy,
        )
        self.assertEqual(final, "3")
        trace = receipt.trace()
        self.assertEqual(trace["evidence"]["admission"], "BENCHMARK_CORRECTIVE_UNADMITTED")
        self.assertFalse(trace["evidence"]["answer_change_authority"])
        self.assertEqual(trace["active_route_receipt"]["action"], "VERIFY_STAND_DOWN")



if __name__ == "__main__":
    unittest.main()
