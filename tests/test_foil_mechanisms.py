from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_mechanisms import (  # noqa: E402
    AcquisitionObservation,
    AcquisitionProposal,
    ChallengerCandidate,
    FoilP1Mechanisms,
    MechanismFlags,
    VerifierResult,
    VerifierStatus,
)
from foil_policy import ClaimKind, LoadBearingUncertainty, TaskContext, VerifierKind  # noqa: E402
from foil_signal_boundary import SignalAuthority  # noqa: E402


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


TASK = TaskContext(
    uncertainties=(
        LoadBearingUncertainty("a numeric result", ClaimKind.NUMERIC),
        LoadBearingUncertainty("a source claim", ClaimKind.EXTERNAL_FACT),
    )
)


class FoilP1MechanismTests(unittest.TestCase):
    def test_defaults_are_independently_ablated(self) -> None:
        controller = FoilP1Mechanisms()
        trace = controller.ablation_trace()
        self.assertEqual(trace["enabled_mechanisms"], ())
        self.assertEqual(len(trace["ablated_mechanisms"]), 4)
        self.assertEqual(
            controller.select_claim_native_verifiers(TASK).stop_reason, "feature_disabled"
        )
        self.assertEqual(
            controller.plan_targeted_acquisition(TASK, ()).stop_reason, "feature_disabled"
        )
        self.assertEqual(controller.select_challengers(()).stop_reason, "feature_disabled")

    def test_claim_native_verifiers_choose_only_open_decisive_claims(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(claim_native_verifier=True))
        receipt = controller.select_claim_native_verifiers(TASK)
        self.assertEqual(
            receipt.selected,
            (VerifierKind.EXACT_CALCULATION, VerifierKind.SOURCE_EVIDENCE),
        )
        self.assertEqual(receipt.trace()["authority"], SignalAuthority.CONTROL_ONLY.value)
        closed = TaskContext(
            uncertainties=(LoadBearingUncertainty("done", ClaimKind.NUMERIC, resolved=True),)
        )
        self.assertEqual(controller.select_claim_native_verifiers(closed).selected, ())

    def test_acquisition_is_bounded_targeted_and_never_closes_from_observation(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(targeted_acquisition=True))
        native = controller.select_claim_native_verifiers(TASK)
        first, second = native.uncertainty_sha256
        used, action_a, action_b, irrelevant = map(digest, ("used", "a", "b", "other"))
        receipt = controller.plan_targeted_acquisition(
            TASK,
            (
                AcquisitionProposal(used, first),
                AcquisitionProposal(action_a, first),
                AcquisitionProposal(action_a, second),
                AcquisitionProposal(irrelevant, digest("not-pending")),
                AcquisitionProposal(action_b, second),
            ),
            observations=(AcquisitionObservation(digest("observation"), first),),
            used_action_sha256=frozenset({used}),
            max_actions=2,
        )
        self.assertEqual(receipt.selected_action_sha256, (action_a, action_b))
        self.assertEqual(receipt.pending_uncertainty_sha256, (first, second))
        self.assertTrue(receipt.trace()["observations_are_evidence"] is False)
        self.assertEqual(receipt.stop_reason, "budget_exhausted")

    def test_acquisition_budget_and_fault_paths(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(targeted_acquisition=True))
        target = controller.select_claim_native_verifiers(TASK).uncertainty_sha256[0]
        with self.assertRaises(ValueError):
            controller.plan_targeted_acquisition(TASK, (), max_actions=0)
        self.assertEqual(
            controller.plan_targeted_acquisition(
                TASK, (AcquisitionProposal(digest("x"), target),), max_actions=3
            ).stop_reason,
            "no_new_targeted_action",
        )

    def test_challengers_require_two_to_four_budget_and_distinct_digests(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(challenger_search=True))
        a, b, c, d = map(digest, ("a", "b", "c", "d"))
        b1, b2, b3 = map(digest, ("b1", "b2", "b3"))
        receipt = controller.select_challengers(
            (
                ChallengerCandidate(a, b1, digest("agree-a")),
                ChallengerCandidate(a, b2),
                ChallengerCandidate(b, b1),
                ChallengerCandidate(c, b3, digest("agree-c")),
                ChallengerCandidate(d, digest("b4")),
            ),
            max_candidates=2,
        )
        self.assertEqual(receipt.selected_candidate_sha256, (a, c))
        self.assertEqual(receipt.stop_reason, "budget_exhausted")
        self.assertFalse(receipt.trace()["branch_agreement_is_evidence"])
        with self.assertRaises(ValueError):
            controller.select_challengers((), max_candidates=1)
        with self.assertRaises(ValueError):
            controller.select_challengers((), max_candidates=5)

    def test_verifier_result_is_control_only_and_nonpasses_block_updates(self) -> None:
        result = VerifierResult(
            VerifierKind.EXACT_CALCULATION,
            VerifierStatus.UNKNOWN,
            provenance_sha256=(digest("provenance"),),
        )
        self.assertTrue(result.blocks_competence_update)
        self.assertFalse(result.trace()["automatic_evidence_admission"])
        with self.assertRaises(ValueError):
            VerifierResult(
                VerifierKind.EXACT_CALCULATION, VerifierStatus.PASS, authority="EVIDENCE_CANDIDATE"
            )

    def test_critic_repair_requires_concrete_failure_and_recheck_with_one_revision(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(critic_repair=True))
        candidate, scope = digest("candidate"), digest("scope")
        failed = VerifierResult(
            VerifierKind.EXACT_CALCULATION,
            VerifierStatus.FAIL,
            provenance_sha256=(digest("proof"),),
            failure_scope_sha256=scope,
        )
        receipt = controller.plan_critic_repair(candidate, failed)
        self.assertEqual(receipt.revision_count, 1)
        self.assertTrue(receipt.requires_recheck)
        self.assertEqual(receipt.recheck_verifier, VerifierKind.EXACT_CALCULATION)
        self.assertEqual(receipt.scope_sha256, scope)
        exhausted = controller.plan_critic_repair(candidate, failed, prior_revisions=1)
        self.assertFalse(exhausted.requires_recheck)
        self.assertEqual(exhausted.stop_reason, "revision_budget_exhausted")
        unknown = VerifierResult(VerifierKind.EXACT_CALCULATION, VerifierStatus.UNKNOWN)
        self.assertEqual(
            controller.plan_critic_repair(candidate, unknown).stop_reason,
            "no_concrete_verifier_failure",
        )
        unscoped = VerifierResult(VerifierKind.EXACT_CALCULATION, VerifierStatus.FAIL)
        self.assertEqual(
            controller.plan_critic_repair(candidate, unscoped).stop_reason,
            "failure_scope_unavailable",
        )

    def test_each_flag_is_independent(self) -> None:
        controller = FoilP1Mechanisms(MechanismFlags(challenger_search=True))
        self.assertFalse(controller.select_claim_native_verifiers(TASK).enabled)
        self.assertFalse(controller.plan_targeted_acquisition(TASK, ()).enabled)
        self.assertTrue(controller.select_challengers(()).enabled)
        self.assertFalse(
            controller.plan_critic_repair(
                digest("candidate"),
                VerifierResult(
                    VerifierKind.EXACT_CALCULATION,
                    VerifierStatus.FAIL,
                    failure_scope_sha256=digest("scope"),
                ),
            ).enabled
        )


if __name__ == "__main__":
    unittest.main()
