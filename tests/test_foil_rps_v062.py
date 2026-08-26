"""Invariant tests for host-verifier-first RPS v0.6.2."""

from __future__ import annotations

from dataclasses import fields
import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_policy import PolicyAction, RuntimePolicyV2, TaskContext  # noqa: E402
from foil_rps import CheckKind  # noqa: E402
from foil_rps_v062 import (  # noqa: E402
    BlindRivalReceipt,
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    RPSV062Policy,
    RPSV062Recommendation,
    check_commitment_digest,
    evaluate_rps_v062_shadow,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check() -> PrecommittedHostCheck:
    task = digest("task")
    spec = digest("host exact arithmetic specification")
    return PrecommittedHostCheck(
        task_digest=task,
        answer_form_digest=digest("single option"),
        check_id="arith-1",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=spec,
        commitment_digest=check_commitment_digest(
            task_digest=task,
            answer_form_digest=digest("single option"),
            check_id="arith-1",
            kind=CheckKind.EXACT_RELATION,
            check_spec_digest=spec,
        ),
    )


def host(
    outcome: HostVerifierOutcome,
    *,
    candidate: str = "candidate-a",
    task_digest: str | None = None,
) -> HostVerifierReceipt:
    frozen = check()
    return HostVerifierReceipt(
        task_digest=task_digest or frozen.task_digest,
        check_commitment_digest=frozen.commitment_digest,
        candidate_digest=digest(candidate),
        outcome=outcome,
        observation_digest=(
            None
            if outcome is HostVerifierOutcome.NOT_APPLICABLE
            else digest(f"observation:{outcome.value}")
        ),
    )


def rival(
    answer: str,
    *,
    task_digest: str | None = None,
    answer_form_digest: str | None = None,
) -> BlindRivalReceipt:
    return BlindRivalReceipt(
        task_digest=task_digest or check().task_digest,
        answer_form_digest=answer_form_digest or digest("single option"),
        rival_digest=digest(answer),
        request_digest=digest("blind request"),
        model_route_digest=digest("terra-low"),
        incumbent_withheld=True,
        input_tokens=10,
        output_tokens=4,
    )


class RPSV062ControllerTests(unittest.TestCase):
    def test_default_off_preserves_base_and_rejects_rival_work(self):
        receipt = host(HostVerifierOutcome.NOT_APPLICABLE)
        decision = evaluate_rps_v062_shadow(check(), receipt)
        self.assertIs(decision.recommendation, RPSV062Recommendation.STAND_DOWN)
        self.assertTrue(decision.base_answer_preserved)
        self.assertFalse(decision.execution_authorized)
        self.assertFalse(decision.answer_mutated)
        with self.assertRaisesRegex(ValueError, "disabled"):
            evaluate_rps_v062_shadow(check(), receipt, rival=rival("candidate-b"))

    def test_host_confirmed_stands_down_without_rival(self):
        decision = evaluate_rps_v062_shadow(
            check(),
            host(HostVerifierOutcome.CONFIRMED),
            policy=RPSV062Policy(enabled=True),
        )
        self.assertIs(decision.recommendation, RPSV062Recommendation.STAND_DOWN)
        self.assertFalse(decision.rival_requested)

    def test_host_contradiction_abstains_without_mutation(self):
        decision = evaluate_rps_v062_shadow(
            check(),
            host(HostVerifierOutcome.CONTRADICTED),
            policy=RPSV062Policy(enabled=True),
        )
        self.assertIs(decision.recommendation, RPSV062Recommendation.ABSTAIN)
        self.assertTrue(decision.abstained)
        self.assertFalse(decision.answer_mutated)

    def test_only_unresolved_host_outcomes_request_rival(self):
        for outcome in (
            HostVerifierOutcome.NOT_APPLICABLE,
            HostVerifierOutcome.UNCERTAIN,
        ):
            with self.subTest(outcome=outcome):
                decision = evaluate_rps_v062_shadow(
                    check(), host(outcome), policy=RPSV062Policy(enabled=True)
                )
                self.assertIs(
                    decision.recommendation,
                    RPSV062Recommendation.REQUEST_BLIND_RIVAL,
                )
                self.assertTrue(decision.rival_requested)

    def test_agreement_is_correlated_evidence_not_fast_accept(self):
        receipt = host(HostVerifierOutcome.UNCERTAIN)
        decision = evaluate_rps_v062_shadow(
            check(),
            receipt,
            policy=RPSV062Policy(enabled=True),
            rival=rival("candidate-a"),
        )
        self.assertIs(
            decision.recommendation, RPSV062Recommendation.CORRELATED_AGREEMENT
        )
        self.assertFalse(decision.execution_authorized)
        self.assertFalse(decision.promotion_authorized)

    def test_disagreement_abstains(self):
        decision = evaluate_rps_v062_shadow(
            check(),
            host(HostVerifierOutcome.NOT_APPLICABLE),
            policy=RPSV062Policy(enabled=True),
            rival=rival("candidate-b"),
        )
        self.assertIs(decision.recommendation, RPSV062Recommendation.ABSTAIN)

    def test_resolved_host_check_rejects_wasted_rival(self):
        with self.assertRaisesRegex(ValueError, "must not consume"):
            evaluate_rps_v062_shadow(
                check(),
                host(HostVerifierOutcome.CONFIRMED),
                policy=RPSV062Policy(enabled=True),
                rival=rival("candidate-a"),
            )

    def test_precommit_and_rival_envelopes_have_no_incumbent_field(self):
        self.assertNotIn(
            "candidate_digest", {field.name for field in fields(PrecommittedHostCheck)}
        )
        self.assertNotIn(
            "candidate_digest", {field.name for field in fields(BlindRivalReceipt)}
        )

    def test_bindings_and_boolean_types_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "task binding"):
            evaluate_rps_v062_shadow(
                check(),
                host(HostVerifierOutcome.UNCERTAIN, task_digest=digest("other")),
                policy=RPSV062Policy(enabled=True),
            )
        with self.assertRaisesRegex(ValueError, "answer-form binding"):
            evaluate_rps_v062_shadow(
                check(),
                host(HostVerifierOutcome.UNCERTAIN),
                policy=RPSV062Policy(enabled=True),
                rival=rival("candidate-b", answer_form_digest=digest("free text")),
            )
        with self.assertRaisesRegex(ValueError, "incumbent_withheld"):
            BlindRivalReceipt(
                task_digest=check().task_digest,
                answer_form_digest=digest("form"),
                rival_digest=digest("answer"),
                request_digest=digest("request"),
                model_route_digest=digest("route"),
                incumbent_withheld=False,
                input_tokens=1,
                output_tokens=1,
            )
        with self.assertRaises(TypeError):
            RPSV062Policy(enabled=1)  # type: ignore[arg-type]

    def test_trace_exposes_origin_and_never_authority(self):
        decision = evaluate_rps_v062_shadow(
            check(),
            host(HostVerifierOutcome.NOT_APPLICABLE),
            policy=RPSV062Policy(enabled=True),
            rival=rival("candidate-b"),
        )
        trace = decision.trace()
        self.assertEqual(trace["schema"], "foil.rps-v062-shadow-decision.v1")
        self.assertEqual(trace["host_outcome"], "NOT_APPLICABLE")
        self.assertTrue(trace["rival_used"])
        self.assertFalse(trace["execution_authorized"])
        self.assertFalse(trace["answer_mutated"])
        self.assertFalse(trace["promotion_authorized"])


class RPSV062RuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.task = TaskContext(
            closed_book=True,
            technical_reasoning=True,
            has_viable_candidate=True,
        )

    def test_route_is_default_off_and_mutually_exclusive_with_v061(self):
        decision = RuntimePolicyV2().decide(self.task)
        self.assertNotIn(PolicyAction.OBSERVE_RPS_V062, decision.actions)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            RuntimePolicyV2(rps_shadow_enabled=True, rps_v062_shadow_enabled=True)

    def test_enabled_route_is_shadow_action_before_stop(self):
        policy = RuntimePolicyV2(rps_v062_shadow_enabled=True)
        decision = policy.decide(self.task)
        self.assertIn(PolicyAction.OBSERVE_RPS_V062, decision.actions)
        self.assertIs(decision.actions[-1], PolicyAction.STOP)
        result = policy.observe_rps_v062(
            decision, check(), host(HostVerifierOutcome.NOT_APPLICABLE)
        )
        self.assertIs(
            result.recommendation, RPSV062Recommendation.REQUEST_BLIND_RIVAL
        )

    def test_unadmitted_task_cannot_bypass_policy(self):
        policy = RuntimePolicyV2(rps_v062_shadow_enabled=True)
        decision = policy.decide(TaskContext(has_viable_candidate=True))
        self.assertNotIn(PolicyAction.OBSERVE_RPS_V062, decision.actions)
        with self.assertRaisesRegex(PermissionError, "did not admit"):
            policy.observe_rps_v062(
                decision, check(), host(HostVerifierOutcome.NOT_APPLICABLE)
            )


if __name__ == "__main__":
    unittest.main()
