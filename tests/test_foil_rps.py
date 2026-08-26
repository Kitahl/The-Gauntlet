"""Invariant tests for the default-off RPS v0.6.1 shadow controller."""

from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_policy import (  # noqa: E402
    ClaimKind,
    LoadBearingUncertainty,
    PolicyAction,
    RuntimePolicyV2,
    TaskContext,
    VerifierKind,
)
from foil_rps import (  # noqa: E402
    CheckKind,
    CheckOutcome,
    HingeCoverage,
    ParityObservation,
    RPSRecommendation,
    RPSShadowPolicy,
    ReasoningCapsule,
    assess_check,
    evaluate_rps_shadow,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def capsule() -> ReasoningCapsule:
    return ReasoningCapsule(
        candidate_digest=digest("candidate"),
        hinge_digests=(digest("supporting hinge"), digest("fragile hinge")),
        fragile_hinge=1,
        answer_form_digest=digest("single option label"),
    )


def observation(
    *,
    kind: CheckKind = CheckKind.PAIRWISE_DISCRIMINATOR,
    hinge_index: int = 1,
    candidate: str | None = "candidate prediction",
    challenger: str | None = "challenger prediction",
    observed: str | None = "candidate prediction",
    applicable: bool = True,
) -> ParityObservation:
    return ParityObservation(
        check_id="check-1",
        kind=kind,
        hinge_index=hinge_index,
        candidate_expected_digest=digest(candidate) if candidate is not None else None,
        challenger_expected_digest=(
            digest(challenger) if challenger is not None else None
        ),
        observed_digest=digest(observed) if observed is not None else None,
        applicable=applicable,
    )


class RPSShadowControllerTests(unittest.TestCase):
    def test_default_is_disabled_and_preserves_base(self):
        decision = evaluate_rps_shadow(capsule(), observation())
        self.assertIs(decision.recommendation, RPSRecommendation.STAND_DOWN)
        self.assertTrue(decision.base_answer_preserved)
        self.assertFalse(decision.execution_authorized)
        self.assertFalse(decision.answer_mutated)
        self.assertTrue(decision.host_action_required)

    def test_non_discriminating_pass_cannot_fast_accept(self):
        primary = observation(
            kind=CheckKind.INVARIANT,
            candidate="same invariant",
            challenger="same invariant",
            observed="same invariant",
        )
        decision = evaluate_rps_shadow(
            capsule(), primary, policy=RPSShadowPolicy(enabled=True)
        )
        self.assertIs(decision.primary.outcome, CheckOutcome.PASS)
        self.assertIs(decision.primary.coverage, HingeCoverage.SUPPORTING)
        self.assertIs(decision.recommendation, RPSRecommendation.RUN_P2)

    def test_decisive_pairwise_pass_recommends_fast_accept(self):
        decision = evaluate_rps_shadow(
            capsule(), observation(), policy=RPSShadowPolicy(enabled=True)
        )
        self.assertIs(decision.primary.coverage, HingeCoverage.DECISIVE)
        self.assertIs(decision.primary.outcome, CheckOutcome.PASS)
        self.assertIs(decision.recommendation, RPSRecommendation.FAST_ACCEPT)
        self.assertFalse(decision.execution_authorized)

    def test_decisive_pairwise_failure_recommends_local_repair(self):
        decision = evaluate_rps_shadow(
            capsule(),
            observation(observed="challenger prediction"),
            policy=RPSShadowPolicy(enabled=True),
        )
        self.assertIs(decision.primary.outcome, CheckOutcome.FAIL)
        self.assertIs(decision.recommendation, RPSRecommendation.LOCAL_REPAIR)

    def test_exact_relation_failure_is_decisive_without_challenger(self):
        decision = evaluate_rps_shadow(
            capsule(),
            observation(
                kind=CheckKind.EXACT_RELATION,
                challenger=None,
                observed="not the exact result",
            ),
            policy=RPSShadowPolicy(enabled=True),
        )
        self.assertIs(decision.primary.coverage, HingeCoverage.DECISIVE)
        self.assertIs(decision.primary.outcome, CheckOutcome.FAIL)
        self.assertIs(decision.recommendation, RPSRecommendation.LOCAL_REPAIR)

    def test_missing_observation_requests_secondary_check(self):
        decision = evaluate_rps_shadow(
            capsule(),
            observation(observed=None),
            policy=RPSShadowPolicy(enabled=True),
        )
        self.assertIs(decision.primary.outcome, CheckOutcome.UNCERTAIN)
        self.assertIs(decision.recommendation, RPSRecommendation.RUN_P2)

    def test_same_kind_secondary_is_not_orthogonal(self):
        decision = evaluate_rps_shadow(
            capsule(),
            observation(observed=None),
            secondary=observation(observed="candidate prediction"),
            policy=RPSShadowPolicy(enabled=True),
        )
        self.assertIs(decision.recommendation, RPSRecommendation.ABSTAIN)
        self.assertEqual(decision.reason, "p2_not_orthogonal")

    def test_orthogonal_decisive_secondary_can_resolve(self):
        decision = evaluate_rps_shadow(
            capsule(),
            observation(
                kind=CheckKind.INVARIANT,
                candidate="same",
                challenger="same",
                observed="same",
            ),
            secondary=observation(
                kind=CheckKind.COUNTEREXAMPLE,
                observed="challenger prediction",
            ),
            policy=RPSShadowPolicy(enabled=True),
        )
        self.assertIs(decision.recommendation, RPSRecommendation.LOCAL_REPAIR)
        self.assertIs(decision.secondary.coverage, HingeCoverage.DECISIVE)

    def test_not_applicable_check_carries_no_hidden_values(self):
        primary = observation(
            candidate=None,
            challenger=None,
            observed=None,
            applicable=False,
        )
        assessment = assess_check(capsule(), primary)
        self.assertIs(assessment.outcome, CheckOutcome.NOT_APPLICABLE)
        self.assertIs(assessment.coverage, HingeCoverage.NONE)

    def test_check_outside_capsule_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the capsule"):
            assess_check(capsule(), observation(hinge_index=2))

    def test_policy_stop_law_rejects_bool_and_changed_ceiling(self):
        with self.assertRaises(TypeError):
            RPSShadowPolicy(max_primary_checks=True)
        with self.assertRaisesRegex(ValueError, "ceilings are frozen"):
            RPSShadowPolicy(max_secondary_checks=2)
        with self.assertRaisesRegex(ValueError, "shadow-only"):
            RPSShadowPolicy(observe_only=False)

    def test_public_trace_excludes_predictions_and_observations(self):
        decision = evaluate_rps_shadow(
            capsule(), observation(), policy=RPSShadowPolicy(enabled=True)
        )
        trace_text = repr(decision.trace())
        self.assertNotIn(digest("candidate prediction"), trace_text)
        self.assertNotIn(digest("challenger prediction"), trace_text)
        self.assertTrue(decision.trace()["base_answer_preserved"])
        self.assertFalse(decision.trace()["execution_authorized"])

    def test_terminal_recommendations_obey_decisive_outcome_law(self):
        enabled = RPSShadowPolicy(enabled=True)
        possible = (None, "candidate prediction", "challenger prediction", "other")
        for kind in CheckKind:
            for hinge_index in (0, 1):
                for challenger in (None, "candidate prediction", "challenger prediction"):
                    for observed in possible:
                        with self.subTest(
                            kind=kind,
                            hinge_index=hinge_index,
                            challenger=challenger,
                            observed=observed,
                        ):
                            check = observation(
                                kind=kind,
                                hinge_index=hinge_index,
                                challenger=challenger,
                                observed=observed,
                            )
                            assessment = assess_check(capsule(), check)
                            decision = evaluate_rps_shadow(
                                capsule(), check, policy=enabled
                            )
                            if (
                                assessment.coverage is HingeCoverage.DECISIVE
                                and assessment.outcome is CheckOutcome.PASS
                            ):
                                expected = RPSRecommendation.FAST_ACCEPT
                            elif (
                                assessment.coverage is HingeCoverage.DECISIVE
                                and assessment.outcome is CheckOutcome.FAIL
                            ):
                                expected = RPSRecommendation.LOCAL_REPAIR
                            else:
                                expected = RPSRecommendation.RUN_P2
                            self.assertIs(decision.recommendation, expected)

    def test_module_imports_only_pure_standard_library_helpers(self):
        source = (ROOT / "tools" / "foil_rps.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module != "__future__"
        )
        self.assertEqual(imported, {"dataclasses", "enum", "re"})


class RPSRuntimePolicyWiringTests(unittest.TestCase):
    def setUp(self):
        self.task = TaskContext(
            closed_book=True,
            technical_reasoning=True,
            has_viable_candidate=True,
        )

    def test_runtime_policy_gate_is_default_off(self):
        implicit = RuntimePolicyV2().decide(self.task)
        explicit = RuntimePolicyV2(rps_shadow_enabled=False).decide(self.task)
        self.assertEqual(implicit, explicit)
        self.assertNotIn(PolicyAction.OBSERVE_RESIDUAL_PARITY, implicit.actions)

    def test_enabled_gate_observes_only_after_base_stop(self):
        policy = RuntimePolicyV2(rps_shadow_enabled=True)
        decision = policy.decide(self.task)
        self.assertTrue(decision.should_stop)
        self.assertIn(PolicyAction.OBSERVE_RESIDUAL_PARITY, decision.actions)
        self.assertIs(decision.actions[-1], PolicyAction.STOP)
        result = policy.observe_residual_parity(decision, capsule(), observation())
        self.assertIs(result.recommendation, RPSRecommendation.FAST_ACCEPT)
        self.assertTrue(result.base_answer_preserved)
        self.assertFalse(result.execution_authorized)

    def test_runtime_admission_cannot_be_bypassed(self):
        policy = RuntimePolicyV2()
        decision = policy.decide(self.task)
        with self.assertRaisesRegex(PermissionError, "disabled"):
            policy.observe_residual_parity(decision, capsule(), observation())

        admitted_elsewhere = RuntimePolicyV2(rps_shadow_enabled=True).decide(self.task)
        with self.assertRaisesRegex(PermissionError, "disabled"):
            policy.observe_residual_parity(
                admitted_elsewhere, capsule(), observation()
            )

    def test_unresolved_hinge_does_not_bypass_base_policy(self):
        task = TaskContext(
            closed_book=True,
            technical_reasoning=True,
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("hinge", ClaimKind.LOGICAL),),
        )
        decision = RuntimePolicyV2(rps_shadow_enabled=True).decide(task)
        self.assertFalse(decision.should_stop)
        self.assertNotIn(PolicyAction.OBSERVE_RESIDUAL_PARITY, decision.actions)

    def test_stronger_completed_verifier_suppresses_shadow_rps(self):
        for verifier in (
            VerifierKind.EXACT_CALCULATION,
            VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
            VerifierKind.EXECUTION_TEST,
        ):
            with self.subTest(verifier=verifier):
                task = TaskContext(
                    closed_book=True,
                    technical_reasoning=True,
                    has_viable_candidate=True,
                    completed_verifiers=frozenset({verifier}),
                )
                decision = RuntimePolicyV2(rps_shadow_enabled=True).decide(task)
                self.assertNotIn(
                    PolicyAction.OBSERVE_RESIDUAL_PARITY, decision.actions
                )

    def test_non_closed_book_task_is_ineligible(self):
        decision = RuntimePolicyV2(rps_shadow_enabled=True).decide(
            TaskContext(has_viable_candidate=True)
        )
        self.assertNotIn(PolicyAction.OBSERVE_RESIDUAL_PARITY, decision.actions)

    def test_constructor_requires_real_boolean(self):
        with self.assertRaises(TypeError):
            RuntimePolicyV2(rps_shadow_enabled=1)


if __name__ == "__main__":
    unittest.main()
