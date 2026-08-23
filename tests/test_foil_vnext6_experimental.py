import json

import pytest

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


def test_v1_release_condition_stops_without_extra_review():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty(
                        "identity",
                        ClaimKind.EXTERNAL_FACT,
                        resolved=True,
                    ),
                ),
                completed_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.STOP
    assert decision.should_stop
    assert decision.cost.deliberation_units == 0
    assert decision.budget_after == decision.budget_before


def test_simple_low_complexity_task_uses_direct_route():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(),
            complexity=TaskComplexity.LOW,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.DIRECT
    assert decision.minimum_evidence_authority is EvidenceAuthority.INTERNAL_HEURISTIC
    assert not decision.may_discharge_load_bearing_uncertainty


def test_complex_closed_book_task_uses_decomposition_not_react():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                benchmark="GPQA-Diamond",
                closed_book=True,
                technical_reasoning=True,
            ),
            complexity=TaskComplexity.HIGH,
            subproblem_count=3,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.DECOMPOSE
    assert decision.cost.tool_calls == 0


def test_external_retrieval_discovery_uses_react():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            ),
            sequential_tool_interaction=True,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.REACT
    assert decision.minimum_evidence_authority is EvidenceAuthority.EXTERNAL_OBSERVATION
    assert decision.cost.tool_calls == 1
    assert not decision.may_discharge_load_bearing_uncertainty


def test_external_fact_uncertainty_implies_react_discovery_even_without_flag():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                )
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.REACT
    assert decision.required_verifier is VerifierKind.SOURCE_EVIDENCE


def test_numeric_uncertainty_routes_to_exact_execution_before_candidate():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                closed_book=True,
                technical_reasoning=True,
                uncertainties=(
                    LoadBearingUncertainty("numeric result", ClaimKind.NUMERIC),
                ),
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.EXACT_EXECUTION
    assert decision.required_verifier is VerifierKind.EXACT_CALCULATION
    assert decision.minimum_evidence_authority is EvidenceAuthority.CLAIM_NATIVE
    assert decision.may_discharge_load_bearing_uncertainty


def test_candidate_with_source_obligation_uses_cove_critic_route():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                ),
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.CLAIM_NATIVE_VERIFY
    assert decision.operator_lineage == "CoVe + CRITIC"
    assert decision.required_verifier is VerifierKind.SOURCE_EVIDENCE


def test_candidate_with_execution_obligation_uses_exact_route():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("runtime behavior", ClaimKind.EXECUTABLE),
                ),
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.EXACT_EXECUTION
    assert decision.required_verifier is VerifierKind.EXECUTION_TEST


def test_output_contract_check_is_claim_native_without_external_tool():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                output_contract_required=True,
            )
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.CLAIM_NATIVE_VERIFY
    assert decision.required_verifier is VerifierKind.OUTPUT_CONTRACT
    assert decision.cost.tool_calls == 0


def test_bounded_challenger_search_requires_real_disagreement_and_budget():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(),
            candidate_count=2,
            candidate_disagreement=True,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.BOUNDED_CHALLENGER_SEARCH
    assert decision.cost.branch_slots == 2
    assert not decision.may_discharge_load_bearing_uncertainty


def test_no_disagreement_does_not_trigger_self_consistency_or_tree_search():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(),
            candidate_count=3,
            candidate_disagreement=False,
            complexity=TaskComplexity.LOW,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.DIRECT


def test_branching_never_counts_as_verification():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(),
            candidate_count=2,
            candidate_disagreement=True,
        ),
        budget(),
    )
    assert decision.minimum_evidence_authority is EvidenceAuthority.INTERNAL_HEURISTIC
    assert not decision.may_discharge_load_bearing_uncertainty


def test_reflexion_is_enabled_only_after_demonstrated_targeted_failure():
    task = TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty(
                "candidate defect",
                ClaimKind.LOGICAL,
            ),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )
    decision = POLICY.decide(
        StrategyTaskContext(
            task,
            demonstrated_failure=True,
            failure_target_identified=True,
            reflection_attempts=0,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION
    assert decision.cost.revision_slots == 1
    assert not decision.may_discharge_load_bearing_uncertainty


def test_reflexion_is_not_automatic_and_is_at_most_one_shot():
    task = TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty("candidate defect", ClaimKind.LOGICAL),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )
    no_failure = POLICY.decide(
        StrategyTaskContext(task),
        budget(),
    )
    repeated = POLICY.decide(
        StrategyTaskContext(
            task,
            demonstrated_failure=True,
            failure_target_identified=True,
            reflection_attempts=1,
        ),
        budget(),
    )
    assert no_failure.operator is StrategyOperator.BLOCKED
    assert repeated.operator is StrategyOperator.BLOCKED


def test_mastermind_is_late_bounded_and_not_a_verifier():
    task = TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty("causal route defect", ClaimKind.LOGICAL),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )
    decision = POLICY.decide(
        StrategyTaskContext(
            task,
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=2,
        ),
        budget(independent_reviews_remaining=0),
    )
    assert decision.operator is StrategyOperator.MASTERMIND_CAUSAL_AUDIT
    assert decision.cost.mastermind_loops == 1
    assert decision.minimum_evidence_authority is EvidenceAuthority.INTERNAL_HEURISTIC
    assert not decision.may_discharge_load_bearing_uncertainty


def test_mastermind_does_not_preempt_mandatory_native_verification():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=5,
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.CLAIM_NATIVE_VERIFY


def test_mastermind_never_exceeds_three_loops():
    with pytest.raises(ValueError):
        StrategyBudget(mastermind_loops_remaining=4)
    task = TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty("causal route defect", ClaimKind.LOGICAL),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )
    decision = POLICY.decide(
        StrategyTaskContext(
            task,
            high_impact=True,
            causal_or_process_defect=True,
            repeated_route_failures=4,
        ),
        budget(mastermind_loops_remaining=0),
    )
    assert decision.operator is StrategyOperator.BLOCKED


def test_unavailable_native_verifier_can_use_independent_review_for_high_impact():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            high_impact=True,
            independent_reviewer_available=True,
            unavailable_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
        ),
        budget(independent_reviews_remaining=1),
    )
    assert decision.operator is StrategyOperator.INDEPENDENT_REVIEW
    assert decision.minimum_evidence_authority is EvidenceAuthority.INDEPENDENT_REVIEW
    assert decision.may_discharge_load_bearing_uncertainty


def test_unavailable_mandatory_verifier_blocks_instead_of_self_critiquing():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                ),
            ),
            unavailable_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
        ),
        budget(),
    )
    assert decision.operator is StrategyOperator.BLOCKED
    assert decision.reason_code == "required_verifier_unavailable"


def test_mandatory_verifier_budget_exhaustion_blocks():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("identity", ClaimKind.EXTERNAL_FACT),
                ),
            )
        ),
        budget(tool_calls_remaining=0),
    )
    assert decision.operator is StrategyOperator.BLOCKED
    assert decision.reason_code == "required_verifier_budget_exhausted"


def test_profile_cannot_remove_freshness_obligation_or_change_operator():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                benchmark="FreshQA",
                has_viable_candidate=True,
                freshness_sensitive=True,
            )
        ),
        budget(),
        ProfileSignal(
            relevance=1.0,
            support=1.0,
            independent_observations=10,
            transfer_confirmations=5,
        ),
    )
    assert decision.base_decision.profile_influence is ProfileInfluence.HIGH
    assert decision.operator is StrategyOperator.CLAIM_NATIVE_VERIFY
    assert decision.required_verifier is VerifierKind.CURRENT_SOURCE


def test_no_distinct_evidence_bearing_action_preserves_unresolved_state():
    task = TaskContext(
        has_viable_candidate=True,
        uncertainties=(
            LoadBearingUncertainty("still unresolved", ClaimKind.LOGICAL),
        ),
        completed_verifiers=frozenset(
            {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
        ),
    )
    decision = POLICY.decide(
        StrategyTaskContext(task),
        budget(),
    )
    assert decision.operator is StrategyOperator.BLOCKED
    assert decision.reason_code == "no_distinct_evidence_bearing_action_available"


def test_budget_never_increases():
    before = budget(
        deliberation_units_remaining=3,
        tool_calls_remaining=2,
        branch_slots_remaining=2,
        revision_slots_remaining=1,
        independent_reviews_remaining=1,
        mastermind_loops_remaining=2,
    )
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            )
        ),
        before,
    )
    after = decision.budget_after
    assert after.deliberation_units_remaining <= before.deliberation_units_remaining
    assert after.tool_calls_remaining <= before.tool_calls_remaining
    assert after.branch_slots_remaining <= before.branch_slots_remaining
    assert after.revision_slots_remaining <= before.revision_slots_remaining
    assert after.independent_reviews_remaining <= before.independent_reviews_remaining
    assert after.mastermind_loops_remaining <= before.mastermind_loops_remaining


def test_public_trace_is_minimal_and_contains_no_private_reasoning():
    decision = POLICY.decide(
        StrategyTaskContext(
            TaskContext(
                benchmark="BrowseComp",
                requires_external_retrieval=True,
            )
        ),
        budget(),
    )
    trace = decision.trace()
    json.dumps(trace)
    forbidden = {
        "scratchpad",
        "chain_of_thought",
        "reasoning_trace",
        "private_reasoning",
        "benchmark_answer",
        "gold_answer",
    }
    assert forbidden.isdisjoint(trace)
    assert set(trace) == {
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
    }
