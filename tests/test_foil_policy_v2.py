"""Ported V2 kernel tests.

Source: `tests/test_foil_vnext_v2.py` at `9540860`
(`origin/experiment/foil-vnext5-vnext`). The assertions are the ported originals;
only the import path and the pytest-function-to-`unittest.TestCase` wrapping
changed, because this repository's suite is run by `unittest discover`, which
does not collect bare module-level `test_*` functions.

These tests pin *mechanism*, not efficacy. Nothing here is evidence that a
profile-driven complement improves any outcome.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_policy import (  # noqa: E402
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


class RuntimePolicyV2Tests(unittest.TestCase):
    def test_benchmark_name_is_metadata_not_policy_selector(self):
        decision = POLICY.decide(TaskContext(benchmark="BrowseComp"))
        self.assertIs(decision.task_regime, TaskRegime.MIXED_TOOL_TASK)

        equivalent = POLICY.decide(
            TaskContext(benchmark="arbitrary-name", requires_external_retrieval=True)
        )
        self.assertIs(equivalent.task_regime, TaskRegime.EXTERNAL_RETRIEVAL)

    def test_retrieval_without_candidate_prioritizes_discovery(self):
        decision = POLICY.decide(TaskContext(requires_external_retrieval=True))
        self.assertEqual(decision.primary_effort_mode.value, "discovery")
        self.assertIn(PolicyAction.DISCOVER_CANDIDATES, decision.actions)
        self.assertGreater(
            decision.resource_allocation.search_query_priority,
            decision.resource_allocation.source_followup_priority,
        )

    def test_retrieval_candidate_shifts_to_claim_native_verification(self):
        decision = POLICY.decide(
            TaskContext(
                requires_external_retrieval=True,
                has_viable_candidate=True,
                uncertainties=(
                    LoadBearingUncertainty("candidate identity", ClaimKind.EXTERNAL_FACT),
                ),
            )
        )
        self.assertIn(VerifierKind.SOURCE_EVIDENCE, decision.pending_verifiers)
        self.assertIn(PolicyAction.VERIFY_CANDIDATE, decision.actions)
        self.assertFalse(decision.should_stop)

    def test_profile_detail_alone_cannot_trigger_personalization(self):
        strength = ProfileSignal(
            relevance=1.0,
            support=1.0,
            independent_observations=10,
            transfer_confirmations=5,
            direction=EvidenceDirection.STRENGTH,
            complement=ComplementKind.TOOL_SELECTION,
        )
        decision = POLICY.decide(TaskContext(requires_external_retrieval=True), strength)
        self.assertIs(decision.profile_influence, ProfileInfluence.HIGH)
        self.assertFalse(decision.profile_route_allowed)
        self.assertNotIn(PolicyAction.APPLY_TARGETED_COMPLEMENT, decision.actions)

    def test_correct_task_matched_verified_gap_can_trigger_one_complement(self):
        decision = POLICY.decide(
            TaskContext(requires_external_retrieval=True),
            strong_gap(ComplementKind.TOOL_SELECTION),
        )
        self.assertTrue(decision.profile_route_allowed)
        self.assertIs(decision.targeted_complement, ComplementKind.TOOL_SELECTION)
        self.assertEqual(decision.actions.count(PolicyAction.APPLY_TARGETED_COMPLEMENT), 1)

    def test_wrong_profile_complement_is_negative_control_and_cannot_route(self):
        decision = POLICY.decide(
            TaskContext(requires_external_retrieval=True),
            strong_gap(ComplementKind.QUANTITATIVE_CHECK),
        )
        self.assertIs(decision.profile_influence, ProfileInfluence.HIGH)
        self.assertFalse(decision.profile_route_allowed)
        self.assertIsNone(decision.targeted_complement)

    def test_stale_profile_cannot_route_even_when_otherwise_strong(self):
        decision = POLICY.decide(
            TaskContext(requires_external_retrieval=True),
            strong_gap(ComplementKind.TOOL_SELECTION, stale=True),
        )
        self.assertIs(decision.profile_influence, ProfileInfluence.NONE)
        self.assertFalse(decision.profile_route_allowed)

    def test_gap_without_changed_context_confirmation_cannot_route(self):
        profile = ProfileSignal(
            relevance=0.95,
            support=0.95,
            independent_observations=6,
            transfer_confirmations=0,
            direction=EvidenceDirection.GAP,
            complement=ComplementKind.TOOL_SELECTION,
        )
        decision = POLICY.decide(TaskContext(requires_external_retrieval=True), profile)
        self.assertFalse(decision.profile_route_allowed)

    def test_current_task_hard_obligation_overrides_profile(self):
        decision = POLICY.decide(
            TaskContext(freshness_sensitive=True, has_viable_candidate=True),
            strong_gap(ComplementKind.EVIDENCE_DISCIPLINE),
        )
        self.assertIs(decision.task_regime, TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL)
        self.assertIn(VerifierKind.CURRENT_SOURCE, decision.pending_verifiers)
        self.assertFalse(decision.should_stop)

    def test_stop_suppresses_gratuitous_profile_intervention(self):
        decision = POLICY.decide(
            TaskContext(
                freshness_sensitive=True,
                has_viable_candidate=True,
                completed_verifiers=frozenset({VerifierKind.CURRENT_SOURCE}),
            ),
            strong_gap(ComplementKind.EVIDENCE_DISCIPLINE),
        )
        self.assertTrue(decision.should_stop)
        self.assertFalse(decision.profile_route_allowed)
        self.assertIsNone(decision.targeted_complement)
        self.assertNotIn(PolicyAction.APPLY_TARGETED_COMPLEMENT, decision.actions)
        self.assertIs(decision.actions[-1], PolicyAction.STOP)

    def test_numeric_uncertainty_maps_to_native_check_and_task_complement(self):
        decision = POLICY.decide(
            TaskContext(
                has_viable_candidate=True,
                uncertainties=(LoadBearingUncertainty("result", ClaimKind.NUMERIC),),
            )
        )
        self.assertIn(VerifierKind.EXACT_CALCULATION, decision.pending_verifiers)
        self.assertIn(ComplementKind.QUANTITATIVE_CHECK, decision.task_complements)
        self.assertFalse(decision.should_stop)

    def test_external_action_allocator_never_raises_budget_ceiling(self):
        discovery = POLICY.decide(TaskContext(requires_external_retrieval=True))
        self.assertIsNone(
            POLICY.next_external_action(
                discovery,
                search_queries_used=2,
                source_followups_used=2,
                max_search_queries=2,
                max_source_followups=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
