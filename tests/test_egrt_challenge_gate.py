from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from _challenge_helpers import init_root, request  # noqa: E402
from egrt_challenge import (  # noqa: E402
    ChallengePolicy,
    ChallengeSelectionError,
    challenge_gate,
    propose_challenge,
    record_resolution,
    select_minimum_discriminator,
)
from egrt_challenge_types import (  # noqa: E402
    ChallengeResolution,
    ChallengeState,
    DiscriminatorPlan,
    ResolutionOutcome,
)
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import Receipt, Verdict  # noqa: E402


class ChallengeGateTests(unittest.TestCase):
    def test_challenge_gate_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            challenge = request()
            propose_challenge(root, challenge)
            self.assertEqual(challenge_gate(root, challenge.task_id, challenge.obligation_id, mode="off")[0], Verdict.CLEARED)
            shadow, detail = challenge_gate(root, challenge.task_id, challenge.obligation_id, mode="shadow")
            self.assertEqual(shadow, Verdict.CLEARED)
            self.assertEqual(detail["counterfactual_verdict"], Verdict.UNKNOWN.value)
            self.assertEqual(challenge_gate(root, challenge.task_id, challenge.obligation_id, mode="enforced")[0], Verdict.UNKNOWN)

    def test_unavailable_and_refutation_have_distinct_severity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            unavailable = request(challenge_id="unavailable")
            propose_challenge(root, unavailable)
            record_resolution(root, ChallengeResolution(
                resolution_id="unavailable-resolution",
                challenge_id=unavailable.challenge_id,
                state=ChallengeState.UNAVAILABLE,
                outcome=ResolutionOutcome.INCONCLUSIVE,
                verifier_receipt_id=None,
                verifier_module=None,
                evidence_hash=None,
                candidate_hash=unavailable.candidate_hash,
                scope_hash=unavailable.scope_hash,
                obligation_set_hash=unavailable.obligation_set_hash,
                resolver="mind",
                reason="solver absent",
            ))
            self.assertEqual(challenge_gate(root, unavailable.task_id, unavailable.obligation_id, mode="enforced")[0], Verdict.UNAVAILABLE)

            root2 = Path(directory) / "second"
            root2.mkdir()
            init_root(root2)
            refuted = request(challenge_id="refuted")
            propose_challenge(root2, refuted)
            store = RuntimeStore(root2)
            store.write_receipt(Receipt(
                "counterexample", "mind", refuted.obligation_id, Verdict.ISSUE,
                "counterexample-check", "x", task_id=refuted.task_id,
            ))
            stored = store.read_receipt("counterexample")
            record_resolution(root2, ChallengeResolution(
                resolution_id="refuted-resolution",
                challenge_id=refuted.challenge_id,
                state=ChallengeState.RESOLVED,
                outcome=ResolutionOutcome.REFUTES_BASE,
                verifier_receipt_id="counterexample",
                verifier_module="mind",
                evidence_hash=stored["content_hash"],
                candidate_hash=refuted.candidate_hash,
                scope_hash=refuted.scope_hash,
                obligation_set_hash=refuted.obligation_set_hash,
                resolver="mind",
            ))
            self.assertEqual(challenge_gate(root2, refuted.task_id, refuted.obligation_id, mode="enforced")[0], Verdict.ISSUE)

    def test_minimum_discriminator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            challenge = request()
            propose_challenge(root, challenge)
            weak = DiscriminatorPlan(
                "weak", challenge.challenge_id, "review", "generic review", "mind", None,
                "maybe support", "maybe refute", max_cost_rank=3,
                metadata={"capability_available": True, "discrimination_rank": 1},
            )
            decisive = DiscriminatorPlan(
                "decisive", challenge.challenge_id, "enumeration", "exact enumeration", "mind", "FINITE_ENUMERATION",
                "all cases pass", "witness", max_cost_rank=1,
                metadata={"capability_available": True, "discrimination_rank": 3},
            )
            selected = select_minimum_discriminator(root, challenge.challenge_id, [weak, decisive], policy=ChallengePolicy.from_root(root))
            self.assertEqual(selected.plan_id, "decisive")

    def test_incomparable_discriminators_require_host_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            challenge = request()
            propose_challenge(root, challenge)
            information = DiscriminatorPlan(
                "information", challenge.challenge_id, "a", "a", "mind", None, "s", "r",
                max_cost_rank=3, metadata={"capability_available": True, "information_rank": 3, "risk_reduction_rank": 1},
            )
            safety = DiscriminatorPlan(
                "safety", challenge.challenge_id, "b", "b", "mind", None, "s", "r",
                max_cost_rank=1, metadata={"capability_available": True, "information_rank": 1, "risk_reduction_rank": 3},
            )
            with self.assertRaises(ChallengeSelectionError):
                select_minimum_discriminator(root, challenge.challenge_id, [information, safety], policy=ChallengePolicy.from_root(root))
            self.assertEqual(RuntimeStore(root).read_challenge(challenge.challenge_id)["state"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
