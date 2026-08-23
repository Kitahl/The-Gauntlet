from experiments.foil_vnext.runtime_policy_v2 import (
    ClaimKind,
    ComplementKind,
    EvidenceDirection,
    LoadBearingUncertainty,
    PolicyAction,
    ProfileInfluence,
    ProfileSignal,
    RuntimePolicyV2,
    TaskContext,
    TaskRegime,
    VerifierKind,
)


POLICY = RuntimePolicyV2()


def strong_gap(complement: ComplementKind, *, stale: bool = False) -> ProfileSignal:
    return ProfileSignal(
        relevance=0.95,
        support=0.95,
        independent_observations=6,
        transfer_confirmations=2,
        stale=stale,
        direction=EvidenceDirection.GAP,
        complement=complement,
    )


def test_benchmark_name_is_metadata_not_policy_selector():
    decision = POLICY.decide(TaskContext(benchmark="BrowseComp"))
    assert decision.task_regime is TaskRegime.MIXED_TOOL_TASK

    equivalent = POLICY.decide(
        TaskContext(benchmark="arbitrary-name", requires_external_retrieval=True)
    )
    assert equivalent.task_regime is TaskRegime.EXTERNAL_RETRIEVAL


def test_retrieval_without_candidate_prioritizes_discovery():
    decision = POLICY.decide(TaskContext(requires_external_retrieval=True))
    assert decision.primary_effort_mode.value == "discovery"
    assert PolicyAction.DISCOVER_CANDIDATES in decision.actions
    assert (
        decision.resource_allocation.search_query_priority
        > decision.resource_allocation.source_followup_priority
    )


def test_retrieval_candidate_shifts_to_claim_native_verification():
    decision = POLICY.decide(
        TaskContext(
            requires_external_retrieval=True,
            has_viable_candidate=True,
            uncertainties=(
                LoadBearingUncertainty("candidate identity", ClaimKind.EXTERNAL_FACT),
            ),
        )
    )
    assert VerifierKind.SOURCE_EVIDENCE in decision.pending_verifiers
    assert PolicyAction.VERIFY_CANDIDATE in decision.actions
    assert not decision.should_stop


def test_profile_detail_alone_cannot_trigger_personalization():
    strength = ProfileSignal(
        relevance=1.0,
        support=1.0,
        independent_observations=10,
        transfer_confirmations=5,
        direction=EvidenceDirection.STRENGTH,
        complement=ComplementKind.TOOL_SELECTION,
    )
    decision = POLICY.decide(
        TaskContext(requires_external_retrieval=True), strength
    )
    assert decision.profile_influence is ProfileInfluence.HIGH
    assert not decision.profile_route_allowed
    assert PolicyAction.APPLY_TARGETED_COMPLEMENT not in decision.actions


def test_correct_task_matched_verified_gap_can_trigger_one_complement():
    decision = POLICY.decide(
        TaskContext(requires_external_retrieval=True),
        strong_gap(ComplementKind.TOOL_SELECTION),
    )
    assert decision.profile_route_allowed
    assert decision.targeted_complement is ComplementKind.TOOL_SELECTION
    assert decision.actions.count(PolicyAction.APPLY_TARGETED_COMPLEMENT) == 1


def test_wrong_profile_complement_is_negative_control_and_cannot_route():
    decision = POLICY.decide(
        TaskContext(requires_external_retrieval=True),
        strong_gap(ComplementKind.QUANTITATIVE_CHECK),
    )
    assert decision.profile_influence is ProfileInfluence.HIGH
    assert not decision.profile_route_allowed
    assert decision.targeted_complement is None


def test_stale_profile_cannot_route_even_when_otherwise_strong():
    decision = POLICY.decide(
        TaskContext(requires_external_retrieval=True),
        strong_gap(ComplementKind.TOOL_SELECTION, stale=True),
    )
    assert decision.profile_influence is ProfileInfluence.NONE
    assert not decision.profile_route_allowed


def test_gap_without_changed_context_confirmation_cannot_route():
    profile = ProfileSignal(
        relevance=0.95,
        support=0.95,
        independent_observations=6,
        transfer_confirmations=0,
        direction=EvidenceDirection.GAP,
        complement=ComplementKind.TOOL_SELECTION,
    )
    decision = POLICY.decide(TaskContext(requires_external_retrieval=True), profile)
    assert not decision.profile_route_allowed


def test_current_task_hard_obligation_overrides_profile():
    decision = POLICY.decide(
        TaskContext(freshness_sensitive=True, has_viable_candidate=True),
        strong_gap(ComplementKind.EVIDENCE_DISCIPLINE),
    )
    assert decision.task_regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL
    assert VerifierKind.CURRENT_SOURCE in decision.pending_verifiers
    assert not decision.should_stop


def test_stop_suppresses_gratuitous_profile_intervention():
    decision = POLICY.decide(
        TaskContext(
            freshness_sensitive=True,
            has_viable_candidate=True,
            completed_verifiers=frozenset({VerifierKind.CURRENT_SOURCE}),
        ),
        strong_gap(ComplementKind.EVIDENCE_DISCIPLINE),
    )
    assert decision.should_stop
    assert not decision.profile_route_allowed
    assert decision.targeted_complement is None
    assert PolicyAction.APPLY_TARGETED_COMPLEMENT not in decision.actions
    assert decision.actions[-1] is PolicyAction.STOP


def test_numeric_uncertainty_maps_to_native_check_and_task_complement():
    decision = POLICY.decide(
        TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("result", ClaimKind.NUMERIC),),
        )
    )
    assert VerifierKind.EXACT_CALCULATION in decision.pending_verifiers
    assert ComplementKind.QUANTITATIVE_CHECK in decision.task_complements
    assert not decision.should_stop


def test_external_action_allocator_never_raises_budget_ceiling():
    discovery = POLICY.decide(TaskContext(requires_external_retrieval=True))
    assert (
        POLICY.next_external_action(
            discovery,
            search_queries_used=2,
            source_followups_used=2,
            max_search_queries=2,
            max_source_followups=2,
        )
        is None
    )
