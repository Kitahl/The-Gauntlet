from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_smart_tool_value import UtilityWeights  # noqa: E402
from foil_tool_contract import ToolFamily, ToolOperation  # noqa: E402
from foil_tool_plan_v2 import (  # noqa: E402
    ContinuationEvidence,
    PlanDecisionStatus,
    PlanEvidence,
    PlanStep,
    PlanValuePolicy,
    ToolPlanContractV2,
    ToolPlanCost,
    build_plan_catalog,
    choose_plan,
    decide_incremental_query,
    decide_plan_prelaunch,
)


def plan(*, tokens: int = 100, calls: int = 1) -> ToolPlanContractV2:
    return ToolPlanContractV2(
        "task-1",
        digest("question"),
        digest("A"),
        "plan-1",
        "1",
        (PlanStep("retrieve", ToolFamily.RETRIEVAL, ToolOperation.WEB_RETRIEVAL, digest("question")),),
        ToolPlanCost(
            maximum_input_tokens=tokens,
            maximum_tool_calls=calls,
            maximum_search_calls=1,
            maximum_latency_ms=100,
        ),
        True,
    )


WEIGHTS = UtilityWeights(
    rescue_value_microunits=1_000_000,
    damage_loss_microunits=2_000_000,
    invalid_loss_microunits=500_000,
    token_price_microunits=1,
)


class ToolPlanV2Tests(unittest.TestCase):
    def test_plan_trace_round_trips_and_rejects_tampering(self) -> None:
        item = plan()
        trace = item.trace()
        self.assertEqual(ToolPlanContractV2.from_mapping(trace), item)
        tampered = dict(trace)
        tampered["route_key"] = "EXACT_ARITHMETIC"
        with self.assertRaisesRegex(ValueError, "route key mismatch"):
            ToolPlanContractV2.from_mapping(tampered)
        unknown = dict(trace)
        unknown["gold"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "closed tool-plan-contract schema"):
            ToolPlanContractV2.from_mapping(unknown)

    def test_plan_trace_round_trips_and_rejects_tampering(self) -> None:
        item = plan()
        trace = item.trace()
        self.assertEqual(ToolPlanContractV2.from_mapping(trace), item)
        tampered = dict(trace)
        tampered["route_key"] = "EXACT_ARITHMETIC"
        with self.assertRaisesRegex(ValueError, "route key mismatch"):
            ToolPlanContractV2.from_mapping(tampered)
        unknown = dict(trace)
        unknown["gold"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "closed tool-plan-contract schema"):
            ToolPlanContractV2.from_mapping(unknown)

    def test_plan_is_closed_non_authoritative_and_dependency_ordered(self) -> None:
        item = plan()
        self.assertFalse(item.trace()["answer_change_authority"])
        self.assertEqual(item.route_key, "WEB_RETRIEVAL")
        with self.assertRaisesRegex(ValueError, "earlier steps"):
            ToolPlanContractV2(
                **{
                    **item.__dict__,
                    "steps": (
                        PlanStep("compute", ToolFamily.COMPUTATION, ToolOperation.EXACT_ARITHMETIC, digest("x"), ("retrieve",)),
                        PlanStep("retrieve", ToolFamily.RETRIEVAL, ToolOperation.WEB_RETRIEVAL, digest("q")),
                    ),
                }
            )
        with self.assertRaisesRegex(ValueError, "does not match"):
            PlanStep("bad", ToolFamily.COMPUTATION, ToolOperation.WEB_RETRIEVAL, digest("q"))

    def test_budget_declines_before_execution(self) -> None:
        decision = decide_plan_prelaunch(
            plan(tokens=101),
            remaining_unreserved_tokens=100,
            weights=WEIGHTS,
            policy=PlanValuePolicy(enabled=True, benchmark_exploration=True),
            evidence=None,
        )
        self.assertEqual(decision.status, PlanDecisionStatus.DECLINE_BUDGET)

    def test_exploration_is_typed_and_model_confidence_absent(self) -> None:
        decision = decide_plan_prelaunch(
            plan(),
            remaining_unreserved_tokens=100,
            weights=WEIGHTS,
            policy=PlanValuePolicy(enabled=True, benchmark_exploration=True),
            evidence=None,
        )
        self.assertEqual(decision.status, PlanDecisionStatus.EXECUTE_EXPLORATION)
        self.assertFalse(decision.trace()["probabilities_from_model_self_report"])

    def test_calibrated_positive_plan_beats_more_expensive_plan(self) -> None:
        cheap = plan(tokens=10)
        expensive = ToolPlanContractV2(
            **{**cheap.__dict__, "plan_id": "plan-2", "cost": ToolPlanCost(maximum_input_tokens=20, maximum_search_calls=1)}
        )
        evidence = PlanEvidence(
            cheap.route_key, "1", 100, 60, 0, 0, digest("evidence"), True
        )
        policy = PlanValuePolicy(enabled=True, minimum_observations=20)
        rows = [
            (item, decide_plan_prelaunch(item, remaining_unreserved_tokens=100, weights=WEIGHTS, policy=policy, evidence=evidence))
            for item in (cheap, expensive)
        ]
        selected = choose_plan(rows)
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected[0].plan_id, "plan-1")

    def test_question_only_catalog_includes_retrieve_then_compute(self) -> None:
        question = r"According to the current Fermi gas report, calculate the value \(6 * B\)."
        costs = {
            "SCHOLARLY_RETRIEVAL": ToolPlanCost(maximum_tool_calls=1),
            "EXACT_ARITHMETIC": ToolPlanCost(maximum_tool_calls=1),
            "SCHOLARLY_RETRIEVAL>EXACT_ARITHMETIC": ToolPlanCost(
                maximum_tool_calls=3, maximum_search_calls=1, maximum_fetch_calls=1
            ),
        }
        catalog = build_plan_catalog(
            {"schema": "foil.question-only-route-input.v1", "task_id": "task-1", "question": question},
            "29", costs_by_route_key=costs, provider_cap_enforced=True, plan_version="1",
        )
        self.assertIn("SCHOLARLY_RETRIEVAL>EXACT_ARITHMETIC", {item.route_key for item in catalog})
        self.assertTrue(all(item.a0_digest == digest("29") for item in catalog))

    def test_second_query_requires_positive_conservative_marginal_value(self) -> None:
        evidence = ContinuationEvidence(100, 70, 0, digest("continuation"), True)
        positive = decide_incremental_query(
            incremental_cost_microunits=10,
            weights=WEIGHTS,
            evidence=evidence,
            minimum_observations=20,
        )
        self.assertTrue(positive.execute)
        harmful = decide_incremental_query(
            incremental_cost_microunits=10,
            weights=WEIGHTS,
            evidence=ContinuationEvidence(100, 10, 30, digest("harmful"), True),
            minimum_observations=20,
        )
        self.assertFalse(harmful.execute)
        self.assertFalse(harmful.trace()["probabilities_from_model_self_report"])


if __name__ == "__main__":
    unittest.main()
