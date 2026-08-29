from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from _challenge_helpers import init_root  # noqa: E402
from egrt_challenge import propose_challenge  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import EvidenceClass, Verdict, digest  # noqa: E402
from mind_runtime import (  # noqa: E402
    ProofChallengeBundle,
    ProofObligation,
    counterexample_receipt,
    exact_enumeration_receipt,
    finalize_proof_bundle,
    generate_native_challenges,
    natural_formal_scope_receipt,
    propose_formalizations,
    resolve_proof_challenge,
    run_z3_smt2,
    select_proof_discriminator,
    symbolic_equivalence_receipt,
)


class MindChallengeRuntimeTests(unittest.TestCase):
    def _obligation(self, task_id: str = "task-mind") -> ProofObligation:
        return ProofObligation(
            obligation_id="obl-mind",
            natural_claim="For every integer x in the declared domain, x squared is nonnegative.",
            formal_claim="x**2 >= 0",
            assumptions=("x is an integer",),
            domain="finite-integer",
            metadata={
                "task_id": task_id,
                "quantifier_map": ("forall x",),
                "alternate_formalizations": (
                    {"formal_claim": "x*x >= 0", "quantifier_map": ("forall x",)},
                ),
            },
        )

    def test_proposes_explicit_alternate_formalizations_and_bound_challenges(self) -> None:
        obligation = self._obligation()
        candidates = propose_formalizations(obligation)
        self.assertEqual(len(candidates), 2)
        base, alternate = candidates
        scope_hash = digest({"scope": "declared integers"})
        obligation_set_hash = digest({"obligations": [obligation.obligation_id]})
        challenges = generate_native_challenges(
            base,
            (alternate,),
            task_id="task-mind",
            scope_hash=scope_hash,
            obligation_set_hash=obligation_set_hash,
        )
        self.assertEqual(len(challenges), 2)
        self.assertTrue(all(item.candidate_hash == base.candidate_hash for item in challenges))
        self.assertEqual({item.kind.value for item in challenges}, {"ALTERNATE_FORMALIZATION", "COUNTEREXAMPLE"})

    def test_symbolic_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            polynomial = symbolic_equivalence_receipt(root, obligation, "(x + 1)**2", "x**2 + 2*x + 1")
            trig = symbolic_equivalence_receipt(root, obligation, "sin(x)**2 + cos(x)**2", "1")
            different = symbolic_equivalence_receipt(root, obligation, "x + 1", "x + 2")
            self.assertEqual(polynomial.verdict, Verdict.CLEARED)
            self.assertEqual(trig.verdict, Verdict.CLEARED)
            self.assertEqual(different.verdict, Verdict.ISSUE)
            self.assertTrue(all(receipt.evidence[0].evidence_class is EvidenceClass.PROVEN for receipt in (polynomial, trig, different)))

    def test_exact_enumeration_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            receipt = exact_enumeration_receipt(root, obligation, {"x": range(-2, 3)}, lambda x: x < 2)
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertIn("COUNTEREXAMPLE", receipt.notes or "")
            self.assertIsNotNone(receipt.evidence[0].artifact)

    def test_model_only_witness_never_becomes_proven(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            candidate = propose_formalizations(obligation)[0]
            receipt = counterexample_receipt(root, obligation, candidate, {"x": 2})
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(receipt.evidence[0].evidence_class, EvidenceClass.HEURISTIC)

    def test_missing_solver_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            with patch("mind_runtime._sympy_available", return_value=False):
                receipt = symbolic_equivalence_receipt(root, obligation, "sqrt(x**2)", "x")
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
            self.assertEqual(run_z3_smt2(root / "missing.smt2")["verdict"], Verdict.UNAVAILABLE.value)

    def test_natural_formal_scope_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            base = propose_formalizations(obligation)[0]
            scope_hash = digest({"scope": "declared"})
            obligation_set_hash = digest({"obligations": [obligation.obligation_id]})
            bundle = ProofChallengeBundle(
                "scope-only", obligation.obligation_id, base.candidate_id, (), (), (),
                task_id="task-mind", base_candidate_hash=base.candidate_hash,
                scope_hash=scope_hash, obligation_set_hash=obligation_set_hash,
            )
            self.assertEqual(finalize_proof_bundle(root, bundle).verdict, Verdict.UNKNOWN)
            scope_receipt = natural_formal_scope_receipt(
                root, obligation, base, scope_hash=scope_hash, verifier="mind:scope-review", supported=True
            )
            resolved = ProofChallengeBundle(
                **{**bundle.__dict__, "natural_scope_receipt_id": scope_receipt.receipt_id}
            )
            self.assertEqual(finalize_proof_bundle(root, resolved).verdict, Verdict.CLEARED)

    def test_alternate_formalization_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            base, alternate = propose_formalizations(obligation)
            scope_hash = digest({"scope": "x in -2..2"})
            obligation_set_hash = digest({"obligations": [obligation.obligation_id]})
            challenges = generate_native_challenges(
                base,
                (alternate,),
                task_id="task-mind",
                scope_hash=scope_hash,
                obligation_set_hash=obligation_set_hash,
            )
            for challenge in challenges:
                propose_challenge(root, challenge)
            plan = select_proof_discriminator(challenges, {"SYMBOLIC_EQUIVALENCE": True, "FINITE_ENUMERATION": True})
            bundle = ProofChallengeBundle(
                bundle_id="bundle-1",
                obligation_id=obligation.obligation_id,
                base_candidate_id=base.candidate_id,
                alternate_candidate_ids=(alternate.candidate_id,),
                challenge_ids=tuple(item.challenge_id for item in challenges),
                selected_plan_ids=(plan.plan_id,),
                task_id="task-mind",
                base_candidate_hash=base.candidate_hash,
                scope_hash=scope_hash,
                obligation_set_hash=obligation_set_hash,
            )
            blocked = finalize_proof_bundle(root, bundle)
            self.assertEqual(blocked.verdict, Verdict.UNKNOWN)

            bound_obligation = ProofObligation(
                **{**obligation.__dict__, "metadata": {**obligation.metadata, "candidate_hash": base.candidate_hash, "scope_hash": scope_hash}},
            )
            equivalent = symbolic_equivalence_receipt(root, bound_obligation, base.formal_claim, alternate.formal_claim)
            exhaustive = exact_enumeration_receipt(root, bound_obligation, {"x": range(-2, 3)}, lambda x: x * x >= 0)
            resolve_proof_challenge(root, challenges[0], equivalent)
            resolve_proof_challenge(root, challenges[1], exhaustive)

            still_scope_unknown = finalize_proof_bundle(root, bundle)
            self.assertEqual(still_scope_unknown.verdict, Verdict.UNKNOWN)
            self.assertTrue(any("scope" in item for item in still_scope_unknown.unresolved))

            scope_receipt = natural_formal_scope_receipt(
                root,
                obligation,
                base,
                scope_hash=scope_hash,
                verifier="mind:explicit-scope-review",
                supported=True,
                provenance_group="scope-review-1",
            )
            complete_bundle = ProofChallengeBundle(
                **{**bundle.__dict__, "natural_scope_receipt_id": scope_receipt.receipt_id},
            )
            cleared = finalize_proof_bundle(root, complete_bundle)
            self.assertEqual(cleared.verdict, Verdict.CLEARED)
            self.assertEqual(RuntimeStore(root).read_receipt(cleared.receipt_id)["module"], "mind")

    def test_counterexample_refutes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = self._obligation()
            base = propose_formalizations(obligation)[0]
            scope_hash = digest({"scope": "x in -2..2"})
            obligation_set_hash = digest({"obligations": [obligation.obligation_id]})
            challenge = generate_native_challenges(
                base, (), task_id="task-mind", scope_hash=scope_hash, obligation_set_hash=obligation_set_hash,
            )[0]
            propose_challenge(root, challenge)
            bound = ProofObligation(**{**obligation.__dict__, "metadata": {**obligation.metadata, "candidate_hash": base.candidate_hash, "scope_hash": scope_hash}})
            counterexample = exact_enumeration_receipt(root, bound, {"x": range(-2, 3)}, lambda x: x < 2)
            resolve_proof_challenge(root, challenge, counterexample)
            bundle = ProofChallengeBundle(
                "bundle-refuted", obligation.obligation_id, base.candidate_id, (), (challenge.challenge_id,), (),
                task_id="task-mind", base_candidate_hash=base.candidate_hash,
                scope_hash=scope_hash, obligation_set_hash=obligation_set_hash,
            )
            self.assertEqual(finalize_proof_bundle(root, bundle).verdict, Verdict.ISSUE)


if __name__ == "__main__":
    unittest.main()
