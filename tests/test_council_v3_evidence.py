from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import council_runtime as council  # noqa: E402
import council_v3_evidence as v3  # noqa: E402
from egrt_challenge_types import ChallengeKind  # noqa: E402
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


class CouncilV3EvidenceTests(unittest.TestCase):
    def _task(self, root: Path) -> tuple[str, str, str]:
        task_id = "task-council-v3"
        review_id = "obl-review-v3"
        target_id = "obl-proof-v3"
        RuntimeStore(root).write_task(
            TaskState(
                task_id=task_id,
                goal_hash=digest("review a candidate with seat-local evidence acquisition"),
                obligations=[
                    Obligation(
                        review_id,
                        ObligationKind.REVIEW,
                        "Run Council v3 controlled review",
                        required_module="council",
                    ),
                    Obligation(
                        target_id,
                        ObligationKind.PROOF,
                        "Target proof obligation",
                        required_module="mind",
                    ),
                ],
            )
        )
        return task_id, review_id, target_id

    def _seats(self, target_id: str) -> list[council.CouncilSeat]:
        return [
            council.CouncilSeat(
                "s1",
                "formal correctness",
                "Do alternate formalizations agree?",
                "exact proof",
                "partition-formal",
                ChallengeKind.ALTERNATE_FORMALIZATION,
                "compare both formalizations exactly",
                "FORMAL_PROOF",
                target_id,
                "produce the formal scope where results differ",
                "reviewer-a",
            ),
            council.CouncilSeat(
                "s2",
                "evidence / provenance",
                "Does the source record support the premise?",
                "source assessment",
                "partition-source",
                ChallengeKind.SOURCE_CONFLICT,
                "resolve the primary-source conflict",
                "SCHOLARLY_SEARCH",
                target_id,
                "identify the conflicting primary-source record",
                "reviewer-b",
            ),
            council.CouncilSeat(
                "s3",
                "skeptic",
                "Does a bounded counterexample refute the claim?",
                "counterexample search",
                "partition-counterexample",
                ChallengeKind.COUNTEREXAMPLE,
                "enumerate the smallest witness domain",
                "FORMAL_PROOF",
                target_id,
                "produce the concrete witness and failed predicate",
                "reviewer-c",
            ),
        ]

    def _budgets(
        self,
    ) -> tuple[
        v3.EvidenceBudget,
        dict[str, v3.EvidenceBudget],
        dict[str, v3.EvidenceUtilityPolicy],
    ]:
        total = v3.EvidenceBudget(
            token_limit=3000,
            money_microunits_limit=3000,
            latency_ms_limit=3000,
            tool_call_limit=9,
        )
        seats = {
            seat_id: v3.EvidenceBudget(
                token_limit=1000,
                money_microunits_limit=1000,
                latency_ms_limit=3000,
                tool_call_limit=3,
            )
            for seat_id in ("s1", "s2", "s3")
        }
        policies = {
            seat_id: v3.EvidenceUtilityPolicy(
                rescue_value=10.0,
                damage_loss=10.0,
                token_price=0.001,
                money_price=0.0,
                latency_price=0.0,
                privacy_price=0.0,
                failure_loss=1.0,
                minimum_margin=0.0,
            )
            for seat_id in ("s1", "s2", "s3")
        }
        return total, seats, policies

    def _create(self, root: Path) -> tuple[council.CouncilState, str, str, str]:
        task_id, review_id, target_id = self._task(root)
        total, seats, policies = self._budgets()
        state = v3.create_council_v3(
            root,
            "artifact-v3",
            "budget-v3",
            self._seats(target_id),
            total_budget=total,
            seat_budgets=seats,
            utility_policies=policies,
            task_id=task_id,
        )
        return state, task_id, review_id, target_id

    def _candidate(
        self,
        seat_id: str,
        bundle_id: str,
        capability: str,
        *,
        rescue_lcb: float = 0.8,
        damage_ucb: float = 0.1,
        token_cost: int = 100,
        tool_id: str | None = None,
        side_effect_class: str = "READ_ONLY",
        task_only_frontier: bool = True,
        hidden_gold_dependent: bool = False,
        dependency_edges: tuple[tuple[str, str], ...] = (),
        tool_ids: tuple[str, ...] | None = None,
    ) -> v3.EvidenceBundleCandidate:
        if tool_ids is None:
            tool_ids = (tool_id or f"tool-{bundle_id}",)
        contracts = tuple((tool, digest({"tool": tool, "version": 1})) for tool in tool_ids)
        return v3.EvidenceBundleCandidate(
            bundle_id=bundle_id,
            seat_id=seat_id,
            provided_capabilities=(capability,),
            tool_ids=tool_ids,
            tool_contracts=contracts,
            estimate_receipt_ids=(f"estimate-{bundle_id}",),
            estimate_receipt_digests=(digest({"estimate": bundle_id}),),
            rescue_probability_lcb=rescue_lcb,
            valid_evidence_probability_lcb=0.9,
            damage_probability_ucb=damage_ucb,
            token_cost=token_cost,
            money_microunits_cost=0,
            latency_ms=10,
            privacy_cost=0.0,
            failure_probability_ucb=0.0,
            dependency_edges=dependency_edges,
            task_only_frontier=task_only_frontier,
            hidden_gold_dependent=hidden_gold_dependent,
            side_effect_class=side_effect_class,
        )

    def _candidates(self) -> dict[str, list[v3.EvidenceBundleCandidate]]:
        return {
            "s1": [self._candidate("s1", "b1", "FORMAL_PROOF")],
            "s2": [self._candidate("s2", "b2", "SCHOLARLY_SEARCH")],
            "s3": [self._candidate("s3", "b3", "FORMAL_PROOF")],
        }

    def _receipt(
        self,
        council_id: str,
        seat_id: str,
        bundle_id: str,
        *,
        source_digest: str | None = None,
        evidence_status: str = "VALID",
        admitted: tuple[str, ...] | None = None,
        reused_from: tuple[str, ...] = (),
    ) -> v3.SeatEvidenceReceipt:
        if admitted is None:
            admitted = (f"evidence-{seat_id}",) if evidence_status == "VALID" else ()
        return v3.SeatEvidenceReceipt(
            evidence_envelope_id=f"env-{seat_id}",
            council_id=council_id,
            seat_id=seat_id,
            bundle_id=bundle_id,
            evidence_status=evidence_status,
            executed_tool_ids=(f"tool-{bundle_id}",),
            tool_receipt_ids=(f"tool-receipt-{seat_id}",),
            source_artifact_digests=(source_digest or digest({"source": seat_id}),),
            provenance_groups=(f"prov-{seat_id}",),
            admitted_evidence_ids=admitted,
            token_used=100,
            money_microunits_used=0,
            latency_ms=10,
            calls_attempted=1,
            calls_completed=1,
            calls_failed=0,
            calls_cancelled=0,
            output_digest=digest({"output": seat_id}),
            reused_from_seat_ids=reused_from,
        )

    def test_positive_utility_selects_deterministically_before_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            stronger = self._candidate("s1", "strong", "FORMAL_PROOF", rescue_lcb=0.9)
            weaker = self._candidate("s1", "weak", "FORMAL_PROOF", rescue_lcb=0.6)
            candidates = self._candidates()
            candidates["s1"] = [weaker, stronger]
            plans = v3.freeze_evidence_plans(root, state.council_id, candidates)
            self.assertEqual(plans["s1"]["selected_bundle_id"], "strong")
            self.assertTrue(plans["s1"]["frozen_before_any_commit"])
            self.assertTrue(plans["s1"]["plan_hash"])

    def test_nonpositive_bundle_stands_down(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            candidates = self._candidates()
            candidates["s1"] = [
                self._candidate(
                    "s1",
                    "bad",
                    "FORMAL_PROOF",
                    rescue_lcb=0.05,
                    damage_ucb=0.95,
                )
            ]
            plans = v3.freeze_evidence_plans(root, state.council_id, candidates)
            self.assertIsNone(plans["s1"]["selected_bundle_id"])
            self.assertEqual(
                plans["s1"]["selection_reason"],
                "STAND_DOWN_NONPOSITIVE_OR_INFEASIBLE",
            )

    def test_hidden_gold_and_non_read_only_bundles_are_infeasible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            candidates = self._candidates()
            candidates["s1"] = [
                self._candidate(
                    "s1",
                    "gold",
                    "FORMAL_PROOF",
                    hidden_gold_dependent=True,
                ),
                self._candidate(
                    "s1",
                    "write",
                    "FORMAL_PROOF",
                    side_effect_class="CONSEQUENTIAL",
                ),
            ]
            plans = v3.freeze_evidence_plans(root, state.council_id, candidates)
            reasons = {
                row["bundle_id"]: row["exclusion_reason"]
                for row in plans["s1"]["candidate_rows"]
            }
            self.assertEqual(reasons["gold"], "HIDDEN_GOLD_DEPENDENT")
            self.assertEqual(reasons["write"], "NON_READ_ONLY")
            self.assertIsNone(plans["s1"]["selected_bundle_id"])

    def test_frozen_seat_budgets_cannot_overallocate_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, target_id = self._task(root)
            with self.assertRaises(ValueError):
                v3.create_council_v3(
                    root,
                    "artifact-v3",
                    "budget-v3",
                    self._seats(target_id),
                    total_budget=v3.EvidenceBudget(100, 100, 100, 3),
                    seat_budgets={
                        "s1": v3.EvidenceBudget(100, 30, 100, 1),
                        "s2": v3.EvidenceBudget(100, 30, 100, 1),
                        "s3": v3.EvidenceBudget(100, 30, 100, 1),
                    },
                    utility_policies={
                        seat_id: v3.EvidenceUtilityPolicy(
                            10.0, 10.0, 0.001, 0.0, 0.0, 0.0, 1.0
                        )
                        for seat_id in ("s1", "s2", "s3")
                    },
                    task_id=task_id,
                )

    def test_dependency_cycles_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._candidate(
                "s1",
                "cycle",
                "FORMAL_PROOF",
                tool_ids=("a", "b"),
                dependency_edges=(("a", "b"), ("b", "a")),
            )

    def test_all_evidence_finishes_before_any_commit_and_no_cross_seat_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            v3.freeze_evidence_plans(root, state.council_id, self._candidates())
            v3.record_seat_evidence(
                root,
                state.council_id,
                self._receipt(state.council_id, "s1", "b1"),
            )
            with self.assertRaises(ValueError):
                v3.commit_v3(
                    root,
                    state.council_id,
                    "s1",
                    council.SeatSubmission("h", (), ("evidence-s1",), ("prov-s1",)),
                )
            with self.assertRaises(ValueError):
                v3.record_seat_evidence(
                    root,
                    state.council_id,
                    self._receipt(
                        state.council_id,
                        "s2",
                        "b2",
                        reused_from=("s1",),
                    ),
                )

    def test_invalid_evidence_cannot_be_admitted(self) -> None:
        with self.assertRaises(ValueError):
            self._receipt(
                "council-x",
                "s1",
                "b1",
                evidence_status="INVALID",
                admitted=("fabricated-support",),
            )

    def test_submission_must_match_frozen_evidence_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            v3.freeze_evidence_plans(root, state.council_id, self._candidates())
            for seat_id, bundle_id in (("s1", "b1"), ("s2", "b2"), ("s3", "b3")):
                v3.record_seat_evidence(
                    root,
                    state.council_id,
                    self._receipt(state.council_id, seat_id, bundle_id),
                )
            with self.assertRaises(ValueError):
                v3.commit_v3(
                    root,
                    state.council_id,
                    "s1",
                    council.SeatSubmission(
                        "h",
                        (),
                        ("wrong-evidence",),
                        ("prov-s1",),
                    ),
                )

    def test_source_overlap_is_measured_without_independence_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, _, _ = self._create(root)
            v3.freeze_evidence_plans(root, state.council_id, self._candidates())
            shared = digest("shared-primary-source")
            v3.record_seat_evidence(
                root,
                state.council_id,
                self._receipt(state.council_id, "s1", "b1", source_digest=shared),
            )
            v3.record_seat_evidence(
                root,
                state.council_id,
                self._receipt(state.council_id, "s2", "b2", source_digest=shared),
            )
            v3.record_seat_evidence(
                root,
                state.council_id,
                self._receipt(state.council_id, "s3", "b3"),
            )
            matrix = v3.evidence_overlap_matrix(root, state.council_id)
            pair = next(
                row for row in matrix["pairs"]
                if {row["left"], row["right"]} == {"s1", "s2"}
            )
            self.assertEqual(pair["source_overlap"], 1.0)
            self.assertEqual(pair["independence_status"], "NOT_ESTABLISHED")
            self.assertEqual(
                matrix["diagnostics"]["independence_status"],
                "NOT_ESTABLISHED_BY_SEAT_COUNT",
            )

    def test_finalize_v3_preserves_review_only_authority_and_binds_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state, _, review_id, target_id = self._create(root)
            v3.freeze_evidence_plans(root, state.council_id, self._candidates())
            submissions: dict[str, council.SeatSubmission] = {}
            nonces: dict[str, str] = {}
            for seat_id, bundle_id in (("s1", "b1"), ("s2", "b2"), ("s3", "b3")):
                v3.record_seat_evidence(
                    root,
                    state.council_id,
                    self._receipt(state.council_id, seat_id, bundle_id),
                )
                submissions[seat_id] = council.SeatSubmission(
                    f"hypothesis-{seat_id}",
                    (f"claim-{seat_id}",),
                    (f"evidence-{seat_id}",),
                    (f"prov-{seat_id}",),
                    findings=(f"finding-{seat_id}",),
                )
            for seat_id, submission in submissions.items():
                _, nonces[seat_id] = v3.commit_v3(
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
                council.CrossCritique("s1", "s2", surviving_findings=("finding-s2",)),
            )
            council.record_cross_critique(
                root,
                state.council_id,
                council.CrossCritique("s2", "s3", surviving_findings=("finding-s3",)),
            )
            council.record_cross_critique(
                root,
                state.council_id,
                council.CrossCritique("s3", "s1", surviving_findings=("finding-s1",)),
            )

            finding = council.CouncilFinding(
                finding_id="finding-s1",
                seat_id="s1",
                target_module="mind",
                target_obligation_id=target_id,
                challenge_kind=ChallengeKind.ALTERNATE_FORMALIZATION,
                hypothesis="formal scope may split",
                refuter="produce the formal scope where results differ",
                consequence_if_true="candidate scope must be regenerated",
                candidate_hash=digest("candidate"),
                scope_hash=digest("scope"),
                obligation_set_hash=digest("obligation-set"),
                required_capability="FORMAL_PROOF",
                evidence_partition="partition-formal",
            )
            council.record_finding(root, state.council_id, finding)
            control = council.record_control(
                root,
                review_id,
                artifact_hash="artifact-v3",
                budget_hash="budget-v3",
                kind="DIRECT",
                output_hash=digest("direct"),
                verdict=Verdict.CLEARED,
                verifier="direct-control",
            )
            receipt = v3.finalize_v3(
                root,
                state.council_id,
                review_id,
                synthesis_hash=digest("synthesis"),
                supported_findings=["finding-s1"],
                direct_control_receipt=control.receipt_id,
            )
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            metadata = receipt.evidence[0].metadata
            self.assertEqual(metadata["authority"], "REVIEW_ONLY")
            self.assertFalse(metadata["target_domain_clearance_authorized"])
            self.assertNotEqual(receipt.output_hash, digest("synthesis"))
            stored = RuntimeStore(root).read_named_state("council_v3", state.council_id)
            self.assertEqual(stored["phase"], "CLOSED")
            self.assertEqual(stored["audit"]["review_receipt_id"], receipt.receipt_id)
            self.assertEqual(stored["audit"]["violations"], [])


if __name__ == "__main__":
    unittest.main()
