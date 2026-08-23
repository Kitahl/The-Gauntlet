import json
import unittest

from experiments.foil_vnext.runtime_policy import (
    ClaimKind,
    LoadBearingUncertainty,
    ProfileInfluence,
    ProfileSignal,
    TaskContext,
    VerifierKind,
)
from experiments.foil_vnext6.runtime_policy import (
    ComposableRuntimePolicy,
    EvidenceAuthority,
    StrategyBudget,
    StrategyOperator,
    StrategyTaskContext,
    TaskComplexity,
)

POLICY = ComposableRuntimePolicy()


def budget(**overrides):
    values = {
        "deliberation_units_remaining": 4,
        "tool_calls_remaining": 4,
        "branch_slots_remaining": 2,
        "revision_slots_remaining": 1,
        "independent_reviews_remaining": 0,
        "mastermind_loops_remaining": 3,
    }
    values.update(overrides)
    return StrategyBudget(**values)


def logical_residual_task():
    return TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty("residual defect", ClaimKind.LOGICAL),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )


def decide(task=None, *, remaining=None, profile=None, **strategy):
    context = StrategyTaskContext(task or TaskContext(), **strategy)
    return POLICY.decide(context, remaining or budget(), profile)


class ComposableRuntimePolicyTests(unittest.TestCase):
    def test_01_v1_release_stops_without_extra_review(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                        resolved=True,
                    ),
                ),
                completed_verifiers=frozenset(
                    {VerifierKind.SOURCE_EVIDENCE}
                ),
            )
        )
        self.assertIs(decision.operator, StrategyOperator.STOP)
        self.assertTrue(decision.should_stop)
        self.assertEqual(decision.budget_after, decision.budget_before)

    def test_02_low_complexity_uses_direct_route(self):
        decision = decide(complexity=TaskComplexity.LOW)
        self.assertIs(decision.operator, StrategyOperator.DIRECT)
        self.assertIs(
            decision.minimum_evidence_authority,
            EvidenceAuthority.INTERNAL_HEURISTIC,
        )
        self.assertFalse(decision.may_discharge_load_bearing_uncertainty)

    def test_03_complex_closed_book_uses_decomposition(self):
        decision = decide(
            TaskContext(
                benchmark="GPQA-Diamond",
                closed_book=True,
                technical_reasoning=True,
            ),
            complexity=TaskComplexity.HIGH,
            subproblem_count=3,
        )
        self.assertIs(decision.operator, StrategyOperator.DECOMPOSE)
        self.assertEqual(decision.cost.tool_calls, 0)

    def test_04_external_discovery_uses_react(self):
        decision = decide(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            ),
            sequential_tool_interaction=True,
        )
        self.assertIs(decision.operator, StrategyOperator.REACT)
        self.assertIs(
            decision.minimum_evidence_authority,
            EvidenceAuthority.EXTERNAL_OBSERVATION,
        )
        self.assertFalse(decision.may_discharge_load_bearing_uncertainty)

    def test_05_external_fact_uncertainty_implies_react(self):
        decision = decide(
            TaskContext(
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                )
            )
        )
        self.assertIs(decision.operator, StrategyOperator.REACT)
        self.assertIs(
            decision.required_verifier,
            VerifierKind.SOURCE_EVIDENCE,
        )

    def test_06_numeric_uncertainty_uses_exact_execution(self):
        decision = decide(
            TaskContext(
                closed_book=True,
                technical_reasoning=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "numeric result",
                        ClaimKind.NUMERIC,
                    ),
                ),
            )
        )
        self.assertIs(decision.operator, StrategyOperator.EXACT_EXECUTION)
        self.assertIs(
            decision.required_verifier,
            VerifierKind.EXACT_CALCULATION,
        )
        self.assertTrue(decision.may_discharge_load_bearing_uncertainty)

    def test_07_source_obligation_uses_cove_critic(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                ),
            )
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.CLAIM_NATIVE_VERIFY,
        )
        self.assertEqual(decision.operator_lineage, "CoVe + CRITIC")

    def test_08_execution_obligation_uses_exact_route(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "runtime behavior",
                        ClaimKind.EXECUTABLE,
                    ),
                ),
            )
        )
        self.assertIs(decision.operator, StrategyOperator.EXACT_EXECUTION)
        self.assertIs(
            decision.required_verifier,
            VerifierKind.EXECUTION_TEST,
        )

    def test_09_output_contract_is_claim_native_without_tool(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                output_contract_required=True,
            )
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.CLAIM_NATIVE_VERIFY,
        )
        self.assertIs(
            decision.required_verifier,
            VerifierKind.OUTPUT_CONTRACT,
        )
        self.assertEqual(decision.cost.tool_calls, 0)

    def test_10_real_disagreement_enables_bounded_challenger(self):
        decision = decide(
            candidate_count=2,
            candidate_disagreement=True,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.BOUNDED_CHALLENGER_SEARCH,
        )
        self.assertEqual(decision.cost.branch_slots, 2)

    def test_11_no_disagreement_keeps_direct_route(self):
        decision = decide(
            complexity=TaskComplexity.LOW,
            candidate_count=3,
            candidate_disagreement=False,
        )
        self.assertIs(decision.operator, StrategyOperator.DIRECT)

    def test_12_branching_never_counts_as_verification(self):
        decision = decide(
            candidate_count=2,
            candidate_disagreement=True,
        )
        self.assertIs(
            decision.minimum_evidence_authority,
            EvidenceAuthority.INTERNAL_HEURISTIC,
        )
        self.assertFalse(decision.may_discharge_load_bearing_uncertainty)

    def test_13_reflexion_requires_demonstrated_targeted_failure(self):
        decision = decide(
            logical_residual_task(),
            demonstrated_failure=True,
            failure_target_identified=True,
            reflection_attempts=0,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION,
        )
        self.assertEqual(decision.cost.revision_slots, 1)

    def test_14_reflexion_is_not_automatic_or_repeatable(self):
        no_failure = decide(logical_residual_task())
        repeated = decide(
            logical_residual_task(),
            demonstrated_failure=True,
            failure_target_identified=True,
            reflection_attempts=1,
        )
        self.assertIs(no_failure.operator, StrategyOperator.BLOCKED)
        self.assertIs(repeated.operator, StrategyOperator.BLOCKED)

    def test_15_mastermind_is_late_bounded_and_nonverifying(self):
        decision = decide(
            logical_residual_task(),
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=2,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.MASTERMIND_CAUSAL_AUDIT,
        )
        self.assertEqual(decision.cost.mastermind_loops, 1)
        self.assertFalse(decision.may_discharge_load_bearing_uncertainty)

    def test_16_mastermind_cannot_preempt_native_verification(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                ),
            ),
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=5,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.CLAIM_NATIVE_VERIFY,
        )

    def test_17_mastermind_never_exceeds_three_loops(self):
        with self.assertRaises(ValueError):
            StrategyBudget(mastermind_loops_remaining=4)
        decision = decide(
            logical_residual_task(),
            remaining=budget(mastermind_loops_remaining=0),
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=4,
        )
        self.assertIs(decision.operator, StrategyOperator.BLOCKED)

    def test_18_unavailable_native_verifier_can_use_independent_review(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                ),
            ),
            remaining=budget(independent_reviews_remaining=1),
            high_impact=True,
            independent_reviewer_available=True,
            unavailable_verifiers=frozenset(
                {VerifierKind.SOURCE_EVIDENCE}
            ),
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.INDEPENDENT_REVIEW,
        )
        self.assertTrue(decision.may_discharge_load_bearing_uncertainty)

    def test_19_unavailable_mandatory_verifier_blocks(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                ),
            ),
            unavailable_verifiers=frozenset(
                {VerifierKind.SOURCE_EVIDENCE}
            ),
        )
        self.assertIs(decision.operator, StrategyOperator.BLOCKED)
        self.assertEqual(
            decision.reason_code,
            "required_verifier_unavailable",
        )

    def test_20_mandatory_verifier_budget_exhaustion_blocks(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                    ),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
        )
        self.assertIs(decision.operator, StrategyOperator.BLOCKED)
        self.assertEqual(
            decision.reason_code,
            "required_verifier_budget_exhausted",
        )

    def test_21_profile_cannot_remove_freshness_obligation(self):
        decision = decide(
            TaskContext(
                benchmark="FreshQA",
                has_viable_candidate=True,
                freshness_sensitive=True,
            ),
            profile=ProfileSignal(
                relevance=1.0,
                support=1.0,
                independent_observations=10,
                transfer_confirmations=5,
            ),
        )
        self.assertIs(
            decision.base_decision.profile_influence,
            ProfileInfluence.HIGH,
        )
        self.assertIs(
            decision.required_verifier,
            VerifierKind.CURRENT_SOURCE,
        )

    def test_22_no_distinct_evidence_action_preserves_unresolved_state(self):
        decision = decide(logical_residual_task())
        self.assertIs(decision.operator, StrategyOperator.BLOCKED)
        self.assertEqual(
            decision.reason_code,
            "no_distinct_evidence_bearing_action_available",
        )

    def test_23_budget_is_componentwise_monotone(self):
        before = budget(
            deliberation_units_remaining=3,
            tool_calls_remaining=2,
            branch_slots_remaining=2,
            revision_slots_remaining=1,
            independent_reviews_remaining=1,
            mastermind_loops_remaining=2,
        )
        after = decide(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            ),
            remaining=before,
        ).budget_after
        self.assertLessEqual(
            after.deliberation_units_remaining,
            before.deliberation_units_remaining,
        )
        self.assertLessEqual(
            after.tool_calls_remaining,
            before.tool_calls_remaining,
        )
        self.assertLessEqual(
            after.branch_slots_remaining,
            before.branch_slots_remaining,
        )
        self.assertLessEqual(
            after.revision_slots_remaining,
            before.revision_slots_remaining,
        )
        self.assertLessEqual(
            after.independent_reviews_remaining,
            before.independent_reviews_remaining,
        )
        self.assertLessEqual(
            after.mastermind_loops_remaining,
            before.mastermind_loops_remaining,
        )

    def test_24_public_trace_is_minimal_and_private_reasoning_free(self):
        trace = decide(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            )
        ).trace()
        json.dumps(trace)
        forbidden = {
            "scratchpad",
            "chain_of_thought",
            "reasoning_trace",
            "private_reasoning",
            "benchmark_answer",
            "gold_answer",
        }
        self.assertTrue(forbidden.isdisjoint(trace))
        self.assertEqual(
            set(trace),
            {
                "controller_version",
                "task_regime",
                "strategy_operator",
                "strategy_lineage",
                "reason_code",
                "minimum_evidence_authority",
                "required_verifier",
                "may_discharge_load_bearing_uncertainty",
                "load_bearing_uncertainty_count",
                "profile_influence",
                "deliberation_units_remaining",
                "tool_calls_remaining",
                "branch_slots_remaining",
                "revision_slots_remaining",
                "independent_reviews_remaining",
                "mastermind_loops_remaining",
                "stop_reason",
            },
        )


if __name__ == "__main__":
    unittest.main()
