"""P0 task-requirement -> evidence -> minimum-complement routing tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence as ev  # noqa: E402
import foil_requirements as req  # noqa: E402
from foil_policy import ComplementKind, RuntimePolicyV2, TaskContext  # noqa: E402


def observations(correct: bool, count: int, *, capability: str, reps=("a",)):
    return tuple(
        ev.Observation(
            correct,
            ev.EvidenceTier.REAL_WORK,
            capability=capability,
            representation=reps[index % len(reps)],
        )
        for index in range(count)
    )


def bundle(
    correct: bool,
    count: int,
    capability: str,
    *,
    transfers: int = 1,
    stale=False,
    context="mechanism review",
):
    return req.CapabilityEvidence(
        observations(correct, count, capability=capability),
        context=context,
        transfer_confirmations=transfers,
        stale=stale,
    )


class RequirementCoverageTests(unittest.TestCase):
    def setUp(self):
        self.requirement = req.TaskCapabilityRequirement(
            "R1",
            "causal reasoning",
            req.RequirementImportance.HIGH,
            req.RequiredLevel.STRONG,
            evidence_obligation="counterfactual discriminator",
            representation="a",
            context="mechanism review",
        )

    def test_requirement_is_explicit_and_normalized(self):
        self.assertEqual(self.requirement.capability, "causal_reasoning")
        self.assertIs(
            req.complement_for_capability(self.requirement.capability),
            ComplementKind.CAUSAL_REASONING,
        )
        self.assertIsNone(req.complement_for_capability("unmapped specialty"))

    def test_requirement_identity_and_capability_reject_non_text_values(self):
        with self.assertRaises(ValueError):
            req.TaskCapabilityRequirement(None, "causal_reasoning")
        with self.assertRaises(ValueError):
            req.TaskCapabilityRequirement("R1", None)
        with self.assertRaises(ValueError):
            req.TaskCapabilityRequirement("", "causal_reasoning")

    def test_unknown_is_not_a_gap_and_does_not_route(self):
        routed = req.route_requirements(TaskContext(), [self.requirement])
        coverage = routed.coverages[0]
        self.assertIs(coverage.state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)
        self.assertEqual(routed.policy_decision.route_basis, "none")

    def test_irrelevant_profile_capability_is_not_detected_as_required(self):
        profile = {"quantitative_checking": bundle(False, 6, "quantitative_checking")}
        routed = req.route_requirements(TaskContext(), [self.requirement], profile_evidence=profile)
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)

    def test_supported_transferred_profile_gap_routes_one_complement(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", transfers=1)
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.PROBABLE_GAP)
        self.assertIs(routed.selected_complement, ComplementKind.CAUSAL_REASONING)
        self.assertEqual(routed.policy_decision.route_basis, "profile")
        self.assertEqual(routed.selected_requirement_id, "R1")

    def test_profile_gap_without_transfer_does_not_route(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", transfers=0)
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.PROBABLE_GAP)
        self.assertIsNone(routed.selected_complement)
        self.assertEqual(routed.policy_decision.route_basis, "none")

    def test_current_success_overrides_stale_profile_gap(self):
        working = req.CapabilityEvidence(
            observations(True, 1, capability="causal_reasoning", reps=("a",)),
            context="mechanism review",
        )
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", transfers=1, stale=True)
            },
            current_task_evidence={"causal_reasoning": working},
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.COVERED_WORKING)
        self.assertFalse(routed.coverages[0].meets_required_level)
        self.assertIsNone(routed.selected_complement)

    def test_wrong_profile_cannot_dominate_strong_current_evidence(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", transfers=1)
            },
            current_task_evidence={"causal_reasoning": bundle(True, 6, "causal_reasoning")},
        )
        coverage = routed.coverages[0]
        self.assertIs(coverage.state, req.CoverageState.COVERED_STRONG)
        self.assertIs(coverage.evidence_source, req.EvidenceSource.CURRENT_TASK)
        self.assertTrue(coverage.meets_required_level)
        self.assertIsNone(routed.selected_complement)

    def test_current_task_gap_overrides_profile_strength(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={"causal_reasoning": bundle(True, 6, "causal_reasoning")},
            current_task_evidence={"causal_reasoning": bundle(False, 6, "causal_reasoning")},
        )
        self.assertIs(routed.selected_complement, ComplementKind.CAUSAL_REASONING)
        self.assertEqual(routed.policy_decision.route_basis, "current_task_evidence")

    def test_one_current_miss_is_uncertain_not_gap(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            current_task_evidence={
                "causal_reasoning": req.CapabilityEvidence(
                    observations(False, 1, capability="causal_reasoning", reps=("a",)),
                    context="mechanism review",
                )
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNCERTAIN)
        self.assertIsNone(routed.selected_complement)

    def test_representation_mismatch_is_unknown_not_gap(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            current_task_evidence={
                "causal_reasoning": req.CapabilityEvidence(
                    observations(False, 6, capability="causal_reasoning", reps=("b",)),
                    context="mechanism review",
                )
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)

    def test_context_mismatch_is_unknown_not_gap(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": req.CapabilityEvidence(
                    observations(False, 6, capability="causal_reasoning"),
                    transfer_confirmations=2,
                    context="unrelated setting",
                )
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)

    def test_stale_profile_snapshot_is_unknown_not_gap(self):
        row = {
            "observations": [
                {
                    "outcome": "failure",
                    "tier": ev.EvidenceTier.REAL_WORK.value,
                    "representation": "a",
                }
                for _ in range(6)
            ]
        }
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile={"profile_status": "STALE", "domains": {"causal_reasoning": row}},
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)

    def test_unmapped_capability_gap_cannot_guess_a_complement(self):
        requirement = req.TaskCapabilityRequirement("R-unmapped", "orbital basket weaving")
        routed = req.route_requirements(
            TaskContext(),
            [requirement],
            current_task_evidence={
                requirement.capability: bundle(False, 6, requirement.capability)
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.PROBABLE_GAP)
        self.assertIsNone(routed.coverages[0].complement)
        self.assertIsNone(routed.selected_complement)

    def test_single_explicit_profile_domain_alias_is_adapted(self):
        requirement = req.TaskCapabilityRequirement("R-alias", "causal reasoning")
        row = {
            "observations": [
                {
                    "outcome": "failure",
                    "tier": ev.EvidenceTier.REAL_WORK.value,
                    "representation": ("a" if index % 2 == 0 else "b"),
                }
                for index in range(6)
            ]
        }
        row["transfer_confirmations"] = 1
        routed = req.route_requirements(
            TaskContext(),
            [requirement],
            profile={"profile_status": "DEEP", "domains": {"causal_inference": row}},
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.PROBABLE_GAP)
        self.assertIs(routed.selected_complement, ComplementKind.CAUSAL_REASONING)
        self.assertEqual(routed.policy_decision.route_basis, "profile")

    def test_representation_diversity_does_not_manufacture_transfer(self):
        requirement = req.TaskCapabilityRequirement("R-no-transfer", "causal reasoning")
        row = {
            "observations": [
                {
                    "outcome": "failure",
                    "tier": ev.EvidenceTier.REAL_WORK.value,
                    "representation": ("a" if index % 2 == 0 else "b"),
                }
                for index in range(6)
            ]
        }
        routed = req.route_requirements(
            TaskContext(),
            [requirement],
            profile={"profile_status": "DEEP", "domains": {"causal_inference": row}},
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.PROBABLE_GAP)
        self.assertEqual(routed.coverages[0].transfer_confirmations, 0)
        self.assertIsNone(routed.selected_complement)

    def test_malformed_snapshot_transfer_count_fails_closed(self):
        row = {"transfer_confirmations": "many", "observations": []}
        with self.assertRaises(ValueError):
            req.profile_evidence_from_snapshot(
                {"domains": {"causal_reasoning": row}}, [self.requirement]
            )

    def test_direct_transfer_count_must_be_an_integer(self):
        for value in (True, 1.5, "1", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                req.CapabilityEvidence(transfer_confirmations=value)

    def test_missing_required_context_is_unknown_not_gap(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", context=None)
            },
        )
        self.assertIs(routed.coverages[0].state, req.CoverageState.UNKNOWN)
        self.assertIsNone(routed.selected_complement)

    def test_unroutable_high_priority_profile_gap_does_not_block_task_gap(self):
        high = req.TaskCapabilityRequirement(
            "R-high", "causal_reasoning", req.RequirementImportance.HIGH
        )
        low = req.TaskCapabilityRequirement(
            "R-low", "quantitative_checking", req.RequirementImportance.LOW
        )
        routed = req.route_requirements(
            TaskContext(),
            [high, low],
            profile_evidence={
                "causal_reasoning": bundle(False, 6, "causal_reasoning", transfers=0, context=None)
            },
            current_task_evidence={
                "quantitative_checking": bundle(False, 6, "quantitative_checking", context=None)
            },
        )
        self.assertEqual(routed.selected_requirement_id, "R-low")
        self.assertIs(routed.selected_complement, ComplementKind.QUANTITATIVE_CHECK)
        self.assertEqual(routed.policy_decision.route_basis, "current_task_evidence")

    def test_high_importance_gap_wins_stable_minimum_complement(self):
        low = req.TaskCapabilityRequirement(
            "R1-low",
            "quantitative_checking",
            req.RequirementImportance.LOW,
        )
        high = req.TaskCapabilityRequirement(
            "R2-high",
            "causal_reasoning",
            req.RequirementImportance.HIGH,
        )
        routed = req.route_requirements(
            TaskContext(),
            [low, high],
            current_task_evidence={
                "quantitative_checking": bundle(False, 6, "quantitative_checking"),
                "causal_reasoning": bundle(False, 6, "causal_reasoning"),
            },
        )
        self.assertEqual(routed.selected_requirement_id, "R2-high")
        self.assertIs(routed.selected_complement, ComplementKind.CAUSAL_REASONING)

    def test_recommended_critical_and_minimal_values_are_preserved(self):
        requirement = req.TaskCapabilityRequirement(
            "R-critical",
            "causal_reasoning",
            req.RequirementImportance.CRITICAL,
            req.RequiredLevel.MINIMAL,
        )
        coverage = req.resolve_requirements([requirement])[0]
        self.assertEqual(coverage.trace()["importance"], "CRITICAL")
        self.assertEqual(coverage.trace()["required_level"], "MINIMAL")

    def test_duplicate_capabilities_merge_to_strongest_requirement(self):
        low = req.TaskCapabilityRequirement(
            "R-low",
            "causal_reasoning",
            req.RequirementImportance.LOW,
            req.RequiredLevel.MINIMAL,
            representation="a",
        )
        critical = req.TaskCapabilityRequirement(
            "R-critical",
            "causal_reasoning",
            req.RequirementImportance.CRITICAL,
            req.RequiredLevel.STRONG,
            context="mechanism review",
        )
        merged = req.merge_requirements([low, critical])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].requirement_id, "R-critical")
        self.assertIs(merged[0].importance, req.RequirementImportance.CRITICAL)
        self.assertIs(merged[0].required_level, req.RequiredLevel.STRONG)
        self.assertEqual(merged[0].representation, "a")
        self.assertEqual(merged[0].context, "mechanism review")

    def test_conflicting_duplicate_capability_qualifiers_fail_closed(self):
        left = req.TaskCapabilityRequirement("R-left", "causal_reasoning", representation="diagram")
        right = req.TaskCapabilityRequirement(
            "R-right", "causal_reasoning", representation="equation"
        )
        with self.assertRaises(ValueError):
            req.merge_requirements([left, right])

    def test_duplicate_requirement_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            req.resolve_requirements([self.requirement, self.requirement])

    def test_receipt_has_no_raw_observation_payload(self):
        routed = req.route_requirements(
            TaskContext(),
            [self.requirement],
            current_task_evidence={"causal_reasoning": bundle(False, 6, "causal_reasoning")},
        )
        trace = routed.trace()
        encoded = json.dumps(trace)
        self.assertNotIn("counterfactual discriminator", encoded)
        self.assertNotIn("mechanism review", encoded)
        self.assertNotIn('"observations"', encoded)
        self.assertFalse(trace["raw_observations_stored"])
        self.assertEqual(len(trace["decision_sha256"]), 64)


class RuntimePolicyTaskEvidenceTests(unittest.TestCase):
    def test_direct_task_gap_must_be_required_by_the_task(self):
        with self.assertRaises(ValueError):
            RuntimePolicyV2().decide(
                TaskContext(), current_task_gap=ComplementKind.CAUSAL_REASONING
            )

    def test_direct_task_gap_is_distinct_from_profile_routing(self):
        decision = RuntimePolicyV2().decide(
            TaskContext(required_complements=frozenset({ComplementKind.CAUSAL_REASONING})),
            current_task_gap=ComplementKind.CAUSAL_REASONING,
        )
        self.assertFalse(decision.profile_route_allowed)
        self.assertEqual(decision.route_basis, "current_task_evidence")
        self.assertEqual(decision.trace()["route_basis"], "current_task_evidence")


if __name__ == "__main__":
    unittest.main()
