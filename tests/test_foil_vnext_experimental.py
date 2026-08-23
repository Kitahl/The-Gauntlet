from experiments.foil_vnext.runtime_policy import (
    ClaimKind,
    EffortMode,
    LoadBearingUncertainty,
    PolicyAction,
    ProfileInfluence,
    ProfileSignal,
    RuntimePolicy,
    TaskContext,
    TaskRegime,
    VerifierKind,
)


POLICY = RuntimePolicy()


def test_retrieval_without_candidate_prioritizes_discovery():
    decision = POLICY.decide(
        TaskContext(benchmark="BrowseComp", requires_external_retrieval=True)
    )
    assert decision.task_regime is TaskRegime.EXTERNAL_RETRIEVAL
    assert decision.primary_effort_mode is EffortMode.DISCOVERY
    assert PolicyAction.DISCOVER_CANDIDATES in decision.actions
    assert decision.resource_allocation.search_query_priority > decision.resource_allocation.source_followup_priority
    assert not decision.should_stop


def test_retrieval_with_candidate_shifts_to_decisive_verification():
    decision = POLICY.decide(
        TaskContext(
            benchmark="BrowseComp",
            requires_external_retrieval=True,
            has_viable_candidate=True,
            uncertainties=(
                LoadBearingUncertainty("identity supported", ClaimKind.EXTERNAL_FACT),
            ),
        )
    )
    assert decision.primary_effort_mode is EffortMode.VERIFICATION
    assert VerifierKind.SOURCE_EVIDENCE in decision.pending_verifiers
    assert PolicyAction.VERIFY_CANDIDATE in decision.actions
    assert decision.resource_allocation.source_followup_priority > decision.resource_allocation.search_query_priority


def test_freshness_prefers_current_source_even_with_confidence():
    decision = POLICY.decide(
        TaskContext(
            benchmark="FreshQA",
            freshness_sensitive=True,
            has_viable_candidate=True,
            answer_confidence=0.99,
        )
    )
    assert decision.task_regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL
    assert VerifierKind.CURRENT_SOURCE in decision.pending_verifiers
    assert PolicyAction.PREFER_CURRENT_SOURCE in decision.actions
    assert not decision.should_stop


def test_closed_book_technical_task_avoids_unnecessary_retrieval():
    decision = POLICY.decide(
        TaskContext(
            benchmark="GPQA-Diamond",
            closed_book=True,
            technical_reasoning=True,
        )
    )
    assert decision.task_regime is TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING
    assert decision.primary_effort_mode is EffortMode.REASONING
    assert not decision.resource_allocation.retrieval_allowed
    assert PolicyAction.REASON_CLOSED_BOOK in decision.actions


def test_abstract_transformation_checks_candidate_rule_against_all_examples():
    decision = POLICY.decide(
        TaskContext(
            benchmark="ARC-AGI-2",
            abstract_transformation=True,
            has_viable_candidate=True,
            supplied_example_count=3,
        )
    )
    assert decision.task_regime is TaskRegime.ABSTRACT_TRANSFORMATION
    assert PolicyAction.CHECK_RULE_AGAINST_ALL_EXAMPLES in decision.actions
    assert VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY in decision.pending_verifiers
    assert not decision.should_stop


def test_closed_context_multihop_decomposes_only_supplied_evidence():
    decision = POLICY.decide(
        TaskContext(
            benchmark="HotpotQA",
            closed_context=True,
            multi_hop=True,
        )
    )
    assert decision.task_regime is TaskRegime.CLOSED_CONTEXT_MULTI_HOP
    assert PolicyAction.DECOMPOSE_SUPPLIED_EVIDENCE in decision.actions
    assert not decision.resource_allocation.retrieval_allowed


def test_weak_profile_evidence_cannot_change_routing():
    decision = POLICY.decide(
        TaskContext(benchmark="GPQA-Diamond", closed_book=True, technical_reasoning=True),
        ProfileSignal(
            relevance=0.9,
            support=0.4,
            independent_observations=1,
            transfer_confirmations=0,
        ),
    )
    assert decision.profile_influence in {ProfileInfluence.NONE, ProfileInfluence.LOW}
    assert not decision.profile_route_allowed
    assert PolicyAction.APPLY_PROFILE_SUPPORT not in decision.actions
    assert decision.task_regime is TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING


def test_high_confidence_does_not_override_unresolved_decisive_uncertainty():
    decision = POLICY.decide(
        TaskContext(
            benchmark="BrowseComp",
            requires_external_retrieval=True,
            has_viable_candidate=True,
            answer_confidence=0.999,
            uncertainties=(
                LoadBearingUncertainty("candidate identity", ClaimKind.EXTERNAL_FACT),
            ),
        )
    )
    assert not decision.should_stop
    assert decision.primary_effort_mode is EffortMode.VERIFICATION
    assert decision.stop_reason == "continue_verification"


def test_resolved_decisive_uncertainties_stop_without_gratuitous_review():
    decision = POLICY.decide(
        TaskContext(
            benchmark="BrowseComp",
            requires_external_retrieval=True,
            has_viable_candidate=True,
            uncertainties=(
                LoadBearingUncertainty(
                    "candidate identity", ClaimKind.EXTERNAL_FACT, resolved=True
                ),
            ),
            completed_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
        )
    )
    assert decision.should_stop
    assert decision.stop_reason == "all_decisive_uncertainties_resolved"
    assert decision.actions[-1] is PolicyAction.STOP
    assert "review" not in " ".join(action.value for action in decision.actions)


def test_profile_cannot_override_freshness_hard_obligation():
    decision = POLICY.decide(
        TaskContext(
            benchmark="FreshQA",
            has_viable_candidate=True,
            freshness_sensitive=True,
        ),
        ProfileSignal(
            relevance=1.0,
            support=1.0,
            independent_observations=10,
            transfer_confirmations=5,
        ),
    )
    assert decision.profile_influence is ProfileInfluence.HIGH
    assert decision.profile_route_allowed
    assert decision.task_regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL
    assert VerifierKind.CURRENT_SOURCE in decision.pending_verifiers
    assert not decision.should_stop


def test_external_action_allocator_obeys_fixed_ceiling_and_mode():
    discovery = POLICY.decide(TaskContext(benchmark="BrowseComp"))
    assert POLICY.next_external_action(
        discovery,
        search_queries_used=0,
        source_followups_used=0,
        max_search_queries=2,
        max_source_followups=2,
    ) == "search_query"

    verification = POLICY.decide(
        TaskContext(
            benchmark="BrowseComp",
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("source", ClaimKind.EXTERNAL_FACT),),
        )
    )
    assert POLICY.next_external_action(
        verification,
        search_queries_used=0,
        source_followups_used=0,
        max_search_queries=2,
        max_source_followups=2,
    ) == "source_followup"
