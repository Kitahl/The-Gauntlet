"""Fail-closed tests for benchmark-active RPS v0.6.3."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps import CheckKind  # noqa: E402
from foil_rps_host_verifier import (  # noqa: E402
    HostTaskDescriptor,
    HostTaskType,
    select_check,
    verify_answer,
)
from foil_rps_v062 import (  # noqa: E402
    BlindRivalReceipt,
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
    check_commitment_digest,
)
from foil_rps_v063 import (  # noqa: E402
    RPSV063Action,
    RPSV063Policy,
    evaluate_unique_host_result,
    evaluate_verified_correction,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check() -> PrecommittedHostCheck:
    task_digest = digest("task")
    answer_form = digest("integer")
    specification = digest("exact expected integer")
    commitment = check_commitment_digest(
        task_digest=task_digest,
        answer_form_digest=answer_form,
        check_id="integer-check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=specification,
    )
    return PrecommittedHostCheck(
        task_digest=task_digest,
        answer_form_digest=answer_form,
        check_id="integer-check",
        kind=CheckKind.EXACT_RELATION,
        check_spec_digest=specification,
        commitment_digest=commitment,
    )


def host(answer: str, outcome: HostVerifierOutcome) -> HostVerifierReceipt:
    frozen = check()
    return HostVerifierReceipt(
        task_digest=frozen.task_digest,
        check_commitment_digest=frozen.commitment_digest,
        candidate_digest=digest(answer),
        outcome=outcome,
        observation_digest=(
            None
            if outcome is HostVerifierOutcome.NOT_APPLICABLE
            else digest(f"observation:{answer}:{outcome.value}")
        ),
    )


def rival(answer: str) -> BlindRivalReceipt:
    frozen = check()
    return BlindRivalReceipt(
        task_digest=frozen.task_digest,
        answer_form_digest=frozen.answer_form_digest,
        rival_digest=digest(answer),
        request_digest=digest("task-only-rival-request"),
        model_route_digest=digest("different-route"),
        incumbent_withheld=True,
        input_tokens=10,
        output_tokens=2,
    )


class RPSV063Tests(unittest.TestCase):
    def processbench_check(self, *steps: str):
        return select_check(
            HostTaskDescriptor(
                task_digest=digest("processbench-task:" + "|".join(steps)),
                answer_form_digest=digest("processbench-answer"),
                task_type=HostTaskType.PROCESSBENCH_FIRST_ERROR,
                source_steps=tuple(steps),
            )
        )

    def test_unique_task_side_result_changes_benchmark_answer(self):
        selected = self.processbench_check(r"\[2+2=4\]", r"\[3+3=7\]")
        base = verify_answer(selected, {"answer": "OK", "abstain": False})
        host_candidate = {"answer": "1", "abstain": False}
        decision = evaluate_unique_host_result(
            selected,
            base,
            host_candidate,
            policy=RPSV063Policy(enabled=True),
        )
        self.assertEqual(decision.action, RPSV063Action.SELECT_HOST_RESULT)
        self.assertTrue(decision.answer_change_authorized)
        self.assertEqual(
            decision.selected_digest,
            verify_answer(selected, host_candidate).candidate_digest,
        )
        self.assertFalse(decision.production_authorized)

    def test_unique_host_result_keeps_confirmed_and_requests_on_decline(self):
        detected = self.processbench_check(r"\[2+2=5\]")
        confirmed = verify_answer(detected, {"answer": "0", "abstain": False})
        kept = evaluate_unique_host_result(
            detected, confirmed, policy=RPSV063Policy(enabled=True)
        )
        self.assertEqual(kept.action, RPSV063Action.KEEP_BASE)

        vacuous = self.processbench_check(r"\[2+2=4\]")
        declined = verify_answer(vacuous, {"answer": "OK", "abstain": False})
        request = evaluate_unique_host_result(
            vacuous, declined, policy=RPSV063Policy(enabled=True)
        )
        self.assertEqual(request.action, RPSV063Action.REQUEST_BLIND_RIVAL)

    def test_non_unique_contradiction_abstains(self):
        selected = select_check(
            HostTaskDescriptor(
                task_digest=digest("arithmetic"),
                answer_form_digest=digest("answer"),
                task_type=HostTaskType.ARITHMETIC_EQUALITY,
            )
        )
        base = verify_answer(selected, r"\[2+2=5\]")
        decision = evaluate_unique_host_result(
            selected, base, policy=RPSV063Policy(enabled=True)
        )
        self.assertEqual(decision.action, RPSV063Action.ABSTAIN)

    def test_disabled_and_confirmed_base_keep_original(self):
        disabled = evaluate_verified_correction(
            check(), host("A", HostVerifierOutcome.CONTRADICTED)
        )
        self.assertEqual(disabled.action, RPSV063Action.KEEP_BASE)
        confirmed = evaluate_verified_correction(
            check(),
            host("A", HostVerifierOutcome.CONFIRMED),
            policy=RPSV063Policy(enabled=True),
        )
        self.assertEqual(confirmed.action, RPSV063Action.KEEP_BASE)

    def test_only_contradicted_a_confirmed_distinct_b_changes(self):
        decision = evaluate_verified_correction(
            check(),
            host("A", HostVerifierOutcome.CONTRADICTED),
            policy=RPSV063Policy(enabled=True),
            rival=rival("B"),
            rival_host=host("B", HostVerifierOutcome.CONFIRMED),
        )
        self.assertEqual(decision.action, RPSV063Action.SELECT_VERIFIED_RIVAL)
        self.assertTrue(decision.answer_change_authorized)
        self.assertEqual(decision.selected_digest, digest("B"))

    def test_decline_requests_rival_but_cannot_self_adjudicate_it(self):
        request = evaluate_verified_correction(
            check(),
            host("A", HostVerifierOutcome.NOT_APPLICABLE),
            policy=RPSV063Policy(enabled=True),
        )
        self.assertEqual(request.action, RPSV063Action.REQUEST_BLIND_RIVAL)
        unresolved = evaluate_verified_correction(
            check(),
            host("A", HostVerifierOutcome.NOT_APPLICABLE),
            policy=RPSV063Policy(enabled=True),
            rival=rival("B"),
            rival_host=host("B", HostVerifierOutcome.NOT_APPLICABLE),
        )
        self.assertEqual(unresolved.action, RPSV063Action.ABSTAIN)

    def test_unconfirmed_rival_abstains(self):
        decision = evaluate_verified_correction(
            check(),
            host("A", HostVerifierOutcome.CONTRADICTED),
            policy=RPSV063Policy(enabled=True),
            rival=rival("B"),
            rival_host=host("B", HostVerifierOutcome.UNCERTAIN),
        )
        self.assertEqual(decision.action, RPSV063Action.ABSTAIN)

    def test_binding_mismatch_and_non_benchmark_policy_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "no production authority"):
            RPSV063Policy(enabled=True, benchmark_only=False)
        mismatched = HostVerifierReceipt(
            task_digest=digest("different-task"),
            check_commitment_digest=check().commitment_digest,
            candidate_digest=digest("B"),
            outcome=HostVerifierOutcome.CONFIRMED,
            observation_digest=digest("observation"),
        )
        with self.assertRaisesRegex(ValueError, "task binding"):
            evaluate_verified_correction(
                check(),
                host("A", HostVerifierOutcome.CONTRADICTED),
                policy=RPSV063Policy(enabled=True),
                rival=rival("B"),
                rival_host=mismatched,
            )


if __name__ == "__main__":
    unittest.main()
