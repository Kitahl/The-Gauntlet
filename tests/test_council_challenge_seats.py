from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import council_runtime as council  # noqa: E402
from egrt_challenge_types import (  # noqa: E402
    ChallengeKind,
    ChallengeOrigin,
    ChallengeRequest,
)
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import (  # noqa: E402
    Obligation,
    ObligationKind,
    TaskState,
    Verdict,
    digest,
)


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


class CouncilChallengeSeatTests(unittest.TestCase):
    def _task(self, root: Path) -> tuple[str, str, str]:
        task_id = "task-council-vnext"
        review_id = "obl-review"
        target_id = "obl-proof"
        RuntimeStore(root).write_task(
            TaskState(
                task_id=task_id,
                goal_hash=digest("review a proof candidate"),
                obligations=[
                    Obligation(
                        review_id,
                        ObligationKind.REVIEW,
                        "Run the controlled review protocol",
                        required_module="council",
                    ),
                    Obligation(
                        target_id,
                        ObligationKind.PROOF,
                        "Prove the bound candidate",
                        required_module="mind",
                    ),
                ],
            )
        )
        return task_id, review_id, target_id

    def _seats(
        self,
        target_id: str,
        *,
        shared_reviewer: bool = False,
    ) -> list[council.CouncilSeat]:
        provenance = "same-model-v1" if shared_reviewer else None
        return [
            council.CouncilSeat(
                "s1",
                "formal correctness",
                "Do the competing quantifier scopes agree?",
                "exact proof",
                "formal-evidence",
                ChallengeKind.ALTERNATE_FORMALIZATION,
                "derive both formalizations exactly",
                "FORMAL_PROOF",
                target_id,
                "exhibit the scope whose exact result differs",
                provenance,
            ),
            council.CouncilSeat(
                "s2",
                "evidence / provenance",
                "Does the source record support the encoded premise?",
                "source assessment",
                "source-evidence",
                ChallengeKind.SOURCE_CONFLICT,
                "assess the first-party provenance chain",
                "SCHOLARLY_SEARCH",
                target_id,
                "identify the conflicting first-party record",
                provenance,
            ),
            council.CouncilSeat(
                "s3",
                "skeptic",
                "Does a finite counterexample refute the candidate?",
                "bounded adversarial search",
                "counterexample-evidence",
                ChallengeKind.COUNTEREXAMPLE,
                "enumerate the smallest witness domain",
                "FORMAL_PROOF",
                target_id,
                "produce the concrete witness and failed predicate",
                "different-model-v2" if shared_reviewer else None,
            ),
        ]

    def _run_review(
        self,
        root: Path,
        target_id: str,
        *,
        task_id: str | None = None,
        shared_reviewer: bool = False,
    ) -> council.CouncilState:
        seats = self._seats(target_id, shared_reviewer=shared_reviewer)
        state = council.create_council(
            root,
            "artifact-hash",
            "budget-hash",
            seats,
            task_id=task_id,
        )
        submissions = {
            "s1": council.SeatSubmission(
                "scope may differ",
                ("c1",),
                ("e1",),
                ("p1",),
                0.7,
                ("finding-scope",),
            ),
            "s2": council.SeatSubmission(
                "source chain may conflict",
                ("c2",),
                ("e2",),
                ("p2",),
                0.6,
                ("finding-source",),
            ),
            "s3": council.SeatSubmission(
                "counterexample may exist",
                ("c3",),
                ("e3",),
                ("p3",),
                0.8,
                ("finding-counterexample",),
            ),
        }
        nonces: dict[str, str] = {}
        for seat_id, submission in submissions.items():
            _, nonces[seat_id] = council.commit(
                root,
                state.council_id,
                seat_id,
                submission,
            )
        for seat_id, submission in submissions.items():
            self.assertTrue(
                council.reveal(
                    root,
                    state.council_id,
                    seat_id,
                    submission,
                    nonces[seat_id],
                )
            )
        council.record_cross_critique(
            root,
            state.council_id,
            council.CrossCritique(
                "s1",
                "s2",
                surviving_findings=("finding-source",),
            ),
        )
        council.record_cross_critique(
            root,
            state.council_id,
            council.CrossCritique(
                "s2",
                "s3",
                surviving_findings=("finding-counterexample",),
            ),
        )
        council.record_cross_critique(
            root,
            state.council_id,
            council.CrossCritique(
                "s3",
                "s1",
                surviving_findings=("finding-scope",),
            ),
        )
        return state

    def test_distinct_seat_challenges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            duplicate = [
                council.CouncilSeat(
                    "a",
                    "skeptic",
                    "q1",
                    "m1",
                    None,
                    ChallengeKind.COUNTEREXAMPLE,
                    "same discriminator",
                    "FORMAL_PROOF",
                    "target",
                    "specific refuter one",
                ),
                council.CouncilSeat(
                    "b",
                    "formal correctness",
                    "q2",
                    "m2",
                    None,
                    ChallengeKind.COUNTEREXAMPLE,
                    "different discriminator",
                    "FORMAL_PROOF",
                    "target",
                    "specific refuter two",
                ),
                council.CouncilSeat(
                    "c",
                    "measurement validity",
                    "q3",
                    "m3",
                    "partition-c",
                    ChallengeKind.BASELINE_OR_ESTIMAND,
                    "design check",
                    "STATISTICAL_ANALYSIS",
                    "target",
                    "compare the frozen direct baseline",
                ),
            ]
            with self.assertRaises(ValueError):
                council.create_council(root, "artifact", "budget", duplicate)

            state = council.create_council(
                root,
                "artifact",
                "budget",
                self._seats("target"),
            )
            self.assertEqual(
                {seat.challenge_contract for seat in state.seats},
                {"vnext"},
            )
            self.assertEqual(
                len({seat.question for seat in state.seats}),
                len(state.seats),
            )

    def test_generic_skeptic_refuter_rejected(self) -> None:
        with self.assertRaises(ValueError):
            council.CouncilSeat(
                "s3",
                "skeptic",
                "Does the candidate survive a concrete attack?",
                "bounded adversarial search",
                "counterexample-evidence",
                ChallengeKind.COUNTEREXAMPLE,
                "enumerate the smallest witness domain",
                "FORMAL_PROOF",
                "target",
                "be critical",
            )

    def test_council_finding_creates_challenge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, review_id, target_id = self._task(root)
            state = self._run_review(root, target_id, task_id=task_id)
            finding = council.CouncilFinding(
                finding_id="finding-scope",
                seat_id="s1",
                target_module="mind",
                target_obligation_id=target_id,
                challenge_kind=ChallengeKind.ALTERNATE_FORMALIZATION,
                hypothesis="The natural-language quantifier scope may encode a different theorem",
                refuter="exhibit the scope whose exact result differs",
                consequence_if_true="The current proof candidate addresses the wrong scoped claim",
                candidate_hash=digest("candidate"),
                scope_hash=digest("scope"),
                obligation_set_hash=digest("obligation-set"),
                required_capability="FORMAL_PROOF",
                evidence_partition="formal-evidence",
            )
            council.record_finding(root, state.council_id, finding)
            direct = council.record_control(
                root,
                review_id,
                artifact_hash="artifact-hash",
                budget_hash="budget-hash",
                kind="DIRECT",
                output_hash=digest("direct"),
                verdict=Verdict.CLEARED,
                verifier="direct-review",
            )
            receipt = council.finalize(
                root,
                state.council_id,
                review_id,
                synthesis_hash=digest("synthesis"),
                supported_findings=["finding-scope"],
                direct_control_receipt=direct.receipt_id,
            )
            self.assertEqual(receipt.verdict, Verdict.CLEARED)

            request = council.propose_supported_finding_challenge(
                root,
                state.council_id,
                "finding-scope",
            )
            self.assertEqual(request.origin, ChallengeOrigin.COUNCIL)
            self.assertEqual(request.obligation_id, target_id)
            self.assertEqual(request.target_module, "mind")
            self.assertFalse(request.metadata["domain_clearance_authorized"])
            stored = RuntimeStore(root).read_challenge(request.challenge_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored["state"], "PROPOSED")
            self.assertFalse(
                any(
                    row.get("module") == "council"
                    for row in RuntimeStore(root).receipts_for(target_id)
                )
            )

    def test_domain_authority_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, target_id = self._task(root)
            state = self._run_review(root, target_id, task_id=task_id)
            direct = council.record_control(
                root,
                target_id,
                artifact_hash="artifact-hash",
                budget_hash="budget-hash",
                kind="DIRECT",
                output_hash=digest("direct"),
                verdict=Verdict.CLEARED,
                verifier="direct-review",
            )
            with self.assertRaises(council.CouncilAuthorityError):
                council.finalize(
                    root,
                    state.council_id,
                    target_id,
                    synthesis_hash=digest("synthesis"),
                    supported_findings=["finding-scope"],
                    direct_control_receipt=direct.receipt_id,
                )

    def test_vnext_supported_finding_requires_structured_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, review_id, target_id = self._task(root)
            state = self._run_review(root, target_id, task_id=task_id)
            direct = council.record_control(
                root,
                review_id,
                artifact_hash="artifact-hash",
                budget_hash="budget-hash",
                kind="DIRECT",
                output_hash=digest("direct"),
                verdict=Verdict.CLEARED,
                verifier="direct-review",
            )
            receipt = council.finalize(
                root,
                state.council_id,
                review_id,
                synthesis_hash=digest("synthesis"),
                supported_findings=["finding-scope"],
                direct_control_receipt=direct.receipt_id,
            )
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertTrue(
                any(
                    item.startswith("supported-finding-missing-structured-record:")
                    for item in receipt.unresolved
                )
            )

    def test_direct_control_still_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, review_id, target_id = self._task(root)
            state = self._run_review(root, target_id, task_id=task_id)
            receipt = council.finalize(
                root,
                state.council_id,
                review_id,
                synthesis_hash=digest("synthesis"),
                supported_findings=["finding-scope"],
            )
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertTrue(
                any("direct-control" in item for item in receipt.unresolved)
            )

    def test_same_model_seats_are_not_independent_by_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = self._run_review(
                root,
                "target",
                shared_reviewer=True,
            )
            matrix = council.overlap_matrix(
                council._load(root, state.council_id)
            )
            self.assertEqual(
                matrix["diagnostics"]["independence_status"],
                "NOT_ESTABLISHED_BY_SEAT_COUNT",
            )
            self.assertGreaterEqual(
                matrix["diagnostics"]["same_reviewer_provenance_pairs"],
                1,
            )
            self.assertTrue(
                all(
                    row["independence_status"] == "NOT_ESTABLISHED"
                    for row in matrix["pairs"]
                )
            )

    def test_derive_seats_from_open_challenges(self) -> None:
        hashes = {
            "candidate_hash": digest("candidate"),
            "scope_hash": digest("scope"),
            "obligation_set_hash": digest("set"),
        }
        rows = [
            ChallengeRequest(
                challenge_id="c-formal",
                task_id="task",
                obligation_id="target",
                target_module="mind",
                origin=ChallengeOrigin.MODULE_NATIVE,
                kind=ChallengeKind.ALTERNATE_FORMALIZATION,
                hypothesis="Two formalizations may disagree",
                alternative="alternate scope",
                refuter="derive both exactly",
                consequence_if_true="candidate scope is wrong",
                load_bearing=True,
                required_capability="FORMAL_PROOF",
                proposer="mind",
                **hashes,
            ),
            ChallengeRequest(
                challenge_id="c-source",
                task_id="task",
                obligation_id="target",
                target_module="space",
                origin=ChallengeOrigin.MODULE_NATIVE,
                kind=ChallengeKind.SOURCE_CONFLICT,
                hypothesis="Sources may share derivative provenance",
                alternative=None,
                refuter="inspect first-party lineage",
                consequence_if_true="support is not independent",
                load_bearing=True,
                required_capability="SCHOLARLY_SEARCH",
                proposer="space",
                **hashes,
            ),
            ChallengeRequest(
                challenge_id="c-exec",
                task_id="task",
                obligation_id="target",
                target_module="power",
                origin=ChallengeOrigin.MODULE_NATIVE,
                kind=ChallengeKind.FAILURE_CLASS,
                hypothesis="The real entrypoint may fail",
                alternative=None,
                refuter="execute the real entrypoint",
                consequence_if_true="candidate is not operational",
                load_bearing=True,
                required_capability="CODE_EXECUTION",
                proposer="power",
                **hashes,
            ),
        ]
        seats = council.derive_challenge_seats(rows)
        self.assertEqual(len(seats), 3)
        self.assertTrue(
            any("skeptic" in seat.role.lower() for seat in seats)
        )
        self.assertTrue(
            all(seat.target_obligation_id == "target" for seat in seats)
        )
        self.assertTrue(
            all(seat.challenge_contract == "vnext" for seat in seats)
        )


if __name__ == "__main__":
    unittest.main()
