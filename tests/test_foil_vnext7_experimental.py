import json
import unittest

from experiments.foil_vnext.runtime_policy import (
    ClaimKind,
    LoadBearingUncertainty,
    TaskContext,
    VerifierKind,
)
from experiments.foil_vnext6.runtime_policy import (
    EvidenceAuthority,
    StrategyBudget,
    StrategyOperator,
    StrategyTaskContext,
)
from experiments.foil_vnext7.runtime_policy import (
    CachedEvidenceHint,
    DiscoveryObjective,
    EvidenceTypedRuntimePolicy,
    EvidenceTypedTaskContext,
)

POLICY = EvidenceTypedRuntimePolicy()
TASK_ID = "v7-policy-task"


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


def decide(task=None, *, remaining=None, cached=(), **strategy):
    context = EvidenceTypedTaskContext(
        StrategyTaskContext(task or TaskContext(), **strategy),
        task_instance_id=TASK_ID,
        cached_evidence=cached,
    )
    return POLICY.decide(context, remaining or budget())


def logical_residual():
    return TaskContext(
        has_viable_candidate=True,
        uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )


class EvidenceTypedRuntimePolicyTests(unittest.TestCase):
    def test_01_direct_route_remains_zero_target(self):
        decision = decide()
        self.assertIs(decision.operator, StrategyOperator.DIRECT)
        self.assertEqual(decision.verification_targets, ())
        self.assertEqual(decision.discovery_target_ids, ())

    def test_02_claim_verifier_gets_atomic_target(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            )
        )
        self.assertIs(decision.required_verifier, VerifierKind.SOURCE_EVIDENCE)
        self.assertEqual(
            tuple(target.target_id for target in decision.verification_targets),
            ("C1",),
        )
        self.assertFalse(decision.verification_targets[0].synthetic)

    def test_03_freshness_obligation_gets_synthetic_target(self):
        decision = decide(
            TaskContext(
                benchmark="FreshQA",
                has_viable_candidate=True,
                freshness_sensitive=True,
            )
        )
        self.assertIs(decision.required_verifier, VerifierKind.CURRENT_SOURCE)
        self.assertEqual(
            tuple(target.target_id for target in decision.verification_targets),
            ("O:current_source",),
        )
        self.assertTrue(decision.verification_targets[0].synthetic)

    def test_04_output_contract_gets_synthetic_target(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                output_contract_required=True,
            )
        )
        self.assertIs(decision.required_verifier, VerifierKind.OUTPUT_CONTRACT)
        self.assertEqual(
            tuple(target.target_id for target in decision.verification_targets),
            ("O:output_contract",),
        )

    def test_05_residual_independent_review_preserves_native_verifier(self):
        decision = decide(
            logical_residual(),
            remaining=budget(independent_reviews_remaining=1),
            high_impact=True,
            independent_reviewer_available=True,
        )
        self.assertIs(decision.operator, StrategyOperator.INDEPENDENT_REVIEW)
        self.assertIs(
            decision.required_verifier,
            VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
        )
        self.assertEqual(
            tuple(target.target_id for target in decision.verification_targets),
            ("C1",),
        )

    def test_06_cached_source_reprices_external_call_to_zero(self):
        cached = (
            CachedEvidenceHint(TASK_ID, "C1", VerifierKind.SOURCE_EVIDENCE),
        )
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            cached=cached,
        )
        self.assertTrue(decision.reuse_cached_evidence)
        self.assertIs(decision.operator, StrategyOperator.CLAIM_NATIVE_VERIFY)
        self.assertEqual(decision.cost.tool_calls, 0)
        self.assertEqual(decision.cost.deliberation_units, 1)

    def test_07_cached_source_recovers_tool_budget_block(self):
        cached = (
            CachedEvidenceHint(TASK_ID, "C1", VerifierKind.SOURCE_EVIDENCE),
        )
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
            cached=cached,
        )
        self.assertFalse(decision.blocked)
        self.assertTrue(decision.reuse_cached_evidence)
        self.assertEqual(decision.cost.tool_calls, 0)

    def test_08_stale_cache_does_not_bypass_tool_budget(self):
        cached = (
            CachedEvidenceHint(
                TASK_ID,
                "C1",
                VerifierKind.SOURCE_EVIDENCE,
                stale=True,
            ),
        )
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
            cached=cached,
        )
        self.assertTrue(decision.blocked)
        self.assertFalse(decision.reuse_cached_evidence)

    def test_09_current_source_cache_requires_freshness(self):
        cached = (
            CachedEvidenceHint(TASK_ID, "C1", VerifierKind.CURRENT_SOURCE),
        )
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                freshness_sensitive=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.FRESH_FACT),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
            cached=cached,
        )
        self.assertTrue(decision.blocked)

    def test_10_fresh_current_source_cache_is_reusable(self):
        cached = (
            CachedEvidenceHint(
                TASK_ID,
                "C1",
                VerifierKind.CURRENT_SOURCE,
                freshness_checked=True,
            ),
        )
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                freshness_sensitive=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.FRESH_FACT),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
            cached=cached,
        )
        self.assertFalse(decision.blocked)
        self.assertTrue(decision.reuse_cached_evidence)
        self.assertEqual(decision.cost.tool_calls, 0)

    def test_11_independent_review_without_cache_stays_independent(self):
        decision = decide(
            logical_residual(),
            remaining=budget(independent_reviews_remaining=1),
            high_impact=True,
            independent_reviewer_available=True,
        )
        self.assertIs(
            decision.strategy.minimum_evidence_authority,
            EvidenceAuthority.INDEPENDENT_REVIEW,
        )

    def test_12_parent_stop_is_still_final(self):
        decision = decide(TaskContext(has_viable_candidate=True))
        self.assertIs(decision.operator, StrategyOperator.STOP)
        self.assertTrue(decision.should_stop)
        self.assertEqual(decision.verification_targets, ())
        self.assertEqual(decision.discovery_target_ids, ())

    def test_13_mastermind_remains_nonverifying(self):
        decision = decide(
            logical_residual(),
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=2,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.MASTERMIND_CAUSAL_AUDIT,
        )
        self.assertFalse(
            decision.strategy.may_discharge_load_bearing_uncertainty
        )

    def test_14_branching_remains_nonverifying(self):
        decision = decide(
            candidate_count=2,
            candidate_disagreement=True,
        )
        self.assertIs(
            decision.operator,
            StrategyOperator.BOUNDED_CHALLENGER_SEARCH,
        )
        self.assertFalse(
            decision.strategy.may_discharge_load_bearing_uncertainty
        )

    def test_15_trace_is_public_state_only(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            )
        )
        trace = decision.trace()
        json.dumps(trace)
        self.assertEqual(trace["controller_version"], POLICY.version)
        self.assertEqual(trace["task_instance_id"], TASK_ID)
        self.assertEqual(trace["verification_target_count"], 1)
        self.assertEqual(trace["discovery_target_count"], 0)
        self.assertIsNone(trace["discovery_objective"])
        self.assertFalse(trace["cached_evidence_reused"])
        for forbidden in (
            "chain_of_thought",
            "scratchpad",
            "private_reasoning",
            "gold_answer",
        ):
            self.assertNotIn(forbidden, trace)

    def test_16_cache_cannot_downgrade_independent_review(self):
        decision = decide(
            logical_residual(),
            remaining=budget(independent_reviews_remaining=1),
            cached=(
                CachedEvidenceHint(
                    TASK_ID,
                    "C1",
                    VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
                ),
            ),
            high_impact=True,
            independent_reviewer_available=True,
        )
        self.assertIs(decision.operator, StrategyOperator.INDEPENDENT_REVIEW)
        self.assertIs(
            decision.strategy.minimum_evidence_authority,
            EvidenceAuthority.INDEPENDENT_REVIEW,
        )
        self.assertFalse(decision.reuse_cached_evidence)

    def test_17_cache_from_another_task_cannot_change_routing(self):
        decision = decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            remaining=budget(tool_calls_remaining=0),
            cached=(
                CachedEvidenceHint(
                    "other-task",
                    "C1",
                    VerifierKind.SOURCE_EVIDENCE,
                ),
            ),
        )
        self.assertTrue(decision.blocked)
        self.assertFalse(decision.reuse_cached_evidence)

    def test_18_react_targets_load_bearing_external_uncertainty(self):
        decision = decide(
            TaskContext(
                uncertainties=(
                    LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),
                ),
            )
        )
        self.assertIs(decision.operator, StrategyOperator.REACT)
        self.assertEqual(decision.verification_targets, ())
        self.assertEqual(decision.discovery_target_ids, ("C1",))
        self.assertIs(
            decision.discovery_objective,
            DiscoveryObjective.LOAD_BEARING_INFORMATION_GAIN_PER_COST,
        )

    def test_19_react_without_atomic_claim_gets_discovery_obligation(self):
        decision = decide(
            TaskContext(requires_external_retrieval=True),
            sequential_tool_interaction=True,
        )
        self.assertIs(decision.operator, StrategyOperator.REACT)
        self.assertEqual(decision.verification_targets, ())
        self.assertEqual(
            decision.discovery_target_ids,
            ("D:external_observation",),
        )
        self.assertIs(
            decision.discovery_objective,
            DiscoveryObjective.LOAD_BEARING_INFORMATION_GAIN_PER_COST,
        )


if __name__ == "__main__":
    unittest.main()
