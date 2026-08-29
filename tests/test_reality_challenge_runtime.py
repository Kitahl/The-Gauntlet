from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reality_runtime as reality  # noqa: E402
import soul_runtime as soul  # noqa: E402
import space_runtime as space  # noqa: E402
from egrt_challenge import record_resolution, resolution_for_receipt  # noqa: E402
from egrt_challenge_types import ChallengeKind, ResolutionOutcome  # noqa: E402
from egrt_store import RuntimeStore, new_id, utcnow  # noqa: E402
from egrt_types import (  # noqa: E402
    ArtifactRef,
    ObligationKind,
    Receipt,
    Verdict,
    digest,
)


CLAIM_SCOPE = (
    "Within the registered assessed scope, the nearest prior art does not match "
    "the candidate changed assumption and mechanism."
)


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "runtime": {"enabled": True, "schema": "egrt.runtime.v1"},
                "challenge": {
                    "mode": "shadow",
                    "max_total_per_obligation": 4,
                    "max_load_bearing_per_obligation": 2,
                    "max_selected_discriminators": 2,
                    "allow_foil_proposals": True,
                    "require_claim_native_receipt": True,
                    "block_on_unavailable_load_bearing": True,
                    "persist_raw_text": False,
                },
            }
        ),
        encoding="utf-8",
    )


class RealityChallengeRuntimeTests(unittest.TestCase):
    def _task(
        self,
        root: Path,
        *,
        two_discovery: bool = False,
    ) -> tuple[str, str, str, str | None]:
        task = soul.start_task(root, "synthesize one bounded candidate mechanism")
        discovery = soul.add_obligation(
            root,
            task.task_id,
            ObligationKind.DISCOVERY,
            "assess concrete candidate prior art",
        )
        other: str | None = None
        if two_discovery:
            extra = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.DISCOVERY,
                "assess unrelated prior art",
            )
            other = extra.obligation_id
        synthesis = soul.add_obligation(
            root,
            task.task_id,
            ObligationKind.SYNTHESIS,
            "synthesize a testable candidate",
            metadata={"depends_on": [discovery.obligation_id]},
        )
        soul.freeze_task(root, task.task_id)
        return task.task_id, discovery.obligation_id, synthesis.obligation_id, other

    def _candidate(
        self,
        obligation_id: str,
        *,
        candidate_id: str = "candidate-1",
        changed_assumption: str = "allow local state to condition the next mechanism",
        mechanism: str = "condition the transition on a bounded local state witness",
        metadata: dict | None = None,
    ) -> reality.MethodCandidate:
        merged = {
            "scope_hash": digest({"scope": candidate_id}),
            "prior_art_claim_scope": CLAIM_SCOPE,
        }
        if metadata:
            merged.update(metadata)
        return reality.MethodCandidate(
            candidate_id=candidate_id,
            obligation_id=obligation_id,
            gap="existing mechanism cannot condition on the required local state",
            failed_constraint="next action must depend on bounded local context",
            changed_assumption=changed_assumption,
            mechanism=mechanism,
            nearest_prior_art=("KnownMechanismA",),
            actual_delta="adds an explicit local-state-conditioned transition",
            inputs=("problem state", "local witness"),
            outputs=("next action",),
            invariants=("bounded state", "deterministic binding"),
            dependencies=("Space assessed prior art",),
            failure_modes=("local state is uninformative",),
            negative_control="restore the baseline assumption while holding all else fixed",
            transfer_target="repeat on a different problem-family representation",
            ablation_plan="remove the local-state transition and measure the predeclared signal",
            verifier_plan="independent Time evaluation with a predeclared scorer",
            tags=("bounded", "mechanism"),
            metadata=merged,
        )

    def _space_evidence(
        self,
        root: Path,
        task_id: str,
        discovery_id: str,
        candidate: reality.MethodCandidate,
        *,
        derivative: bool = False,
        retrieval_only: bool = False,
        plan_scope_hash: str | None = None,
        candidate_hash_override: str | None = None,
    ) -> tuple[Receipt, Receipt | None, dict]:
        plan = space.SearchPlan(
            plan_id=new_id("space-plan"),
            obligation_id=discovery_id,
            question="Does assessed prior art match this concrete candidate mechanism?",
            queries=("candidate mechanism comparison",),
            sources=("fake",),
            max_queries=1,
            saturation_queries=1,
            task_id=task_id,
            candidate_hash=(
                candidate_hash_override
                if candidate_hash_override is not None
                else reality.candidate_hash(candidate)
            ),
            scope_hash=(
                plan_scope_hash
                if plan_scope_hash is not None
                else str(candidate.metadata["scope_hash"])
            ),
        )
        with patch.dict(
            space.ADAPTERS,
            {
                "fake": lambda _query, _limit: [
                    {
                        "title": "Nearest assessed prior art",
                        "doi": "10.1/nearest",
                        "source_index": "fake",
                    }
                ]
            },
            clear=True,
        ):
            retrieval, result = space.run_plan(root, plan)
        if retrieval_only:
            return retrieval, None, result
        assessments = [
            space.SourceAssessment(
                "assessment-a",
                ArtifactRef("prior-art-a.pdf", sha256="a" * 64),
                "SUPPORTS",
                "independent-reviewer-a",
                CLAIM_SCOPE,
                "lineage-a",
            )
        ]
        if derivative:
            assessments.append(
                space.SourceAssessment(
                    "assessment-b",
                    ArtifactRef("prior-art-b.pdf", sha256="b" * 64),
                    "SUPPORTS",
                    "independent-reviewer-b",
                    CLAIM_SCOPE,
                    "lineage-a",
                )
            )
        assessment = space.assess_sources(
            root,
            discovery_id,
            retrieval.receipt_id,
            assessments,
        )
        return retrieval, assessment, result

    def _recorded(
        self,
        root: Path,
        *,
        metadata: dict | None = None,
        changed_assumption: str = "allow local state to condition the next mechanism",
        candidate_id: str = "candidate-1",
        derivative: bool = False,
    ) -> tuple[reality.MethodCandidate, Receipt, reality.CandidateAttackBundle]:
        if not (root / ".gauntlet.json").exists():
            init_root(root)
        task_id, discovery_id, synthesis_id, _ = self._task(root)
        candidate = self._candidate(
            synthesis_id,
            candidate_id=candidate_id,
            changed_assumption=changed_assumption,
            metadata=metadata,
        )
        _, assessment, _ = self._space_evidence(
            root,
            task_id,
            discovery_id,
            candidate,
            derivative=derivative,
        )
        assert assessment is not None
        receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
        bundle = reality.load_attack_bundle(root, candidate.candidate_id)
        self.assertIsNotNone(bundle)
        assert bundle is not None
        return candidate, receipt, bundle

    def _challenge(
        self,
        root: Path,
        bundle: reality.CandidateAttackBundle,
        kind: ChallengeKind,
    ) -> dict:
        store = RuntimeStore(root)
        for challenge_id in bundle.challenge_ids:
            row = store.read_challenge(challenge_id)
            if row and row.get("kind") == kind.value:
                return row
        self.fail(f"challenge {kind.value} not found")

    # 1
    def test_candidate_attack_bundle_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, receipt, bundle = self._recorded(Path(directory))
            self.assertEqual(bundle.candidate_id, candidate.candidate_id)
            self.assertEqual(len(bundle.challenge_ids), 4)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)

    # 2
    def test_bundle_candidate_task_scope_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, bundle = self._recorded(root)
            self.assertEqual(bundle.candidate_hash, reality.candidate_hash(candidate))
            self.assertEqual(bundle.scope_hash, candidate.metadata["scope_hash"])
            self.assertIsNotNone(bundle.task_id)
            for challenge_id in bundle.challenge_ids:
                row = RuntimeStore(root).read_challenge(challenge_id)
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row["candidate_hash"], bundle.candidate_hash)
                self.assertEqual(row["scope_hash"], bundle.scope_hash)
                self.assertEqual(row["task_id"], bundle.task_id)

    # 3
    def test_novelty_costume_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, bundle = self._recorded(Path(directory))
            challenge = self._challenge(
                Path(directory), bundle, ChallengeKind.NOVELTY_COSTUME
            )
            self.assertEqual(challenge["origin"], "MODULE_NATIVE")
            self.assertEqual(challenge["target_module"], "reality")

    # 4
    def test_costume_requires_real_space_source_assessment_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, receipt, bundle = self._recorded(root)
            costume = self._challenge(root, bundle, ChallengeKind.NOVELTY_COSTUME)
            self.assertEqual(costume["state"], "RESOLVED")
            resolution = RuntimeStore(root).latest_resolution(costume["challenge_id"])
            self.assertIsNotNone(resolution)
            assert resolution is not None
            self.assertEqual(resolution["verifier_module"], "space")
            self.assertIn(
                resolution["verifier_receipt_id"],
                bundle.nearest_prior_art_receipt_ids,
            )
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(candidate.obligation_id, bundle.obligation_id)

    # 5
    def test_raw_space_retrieval_cannot_resolve_costume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, discovery_id, synthesis_id, _ = self._task(root)
            candidate = self._candidate(synthesis_id)
            retrieval, _, _ = self._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
                retrieval_only=True,
            )
            receipt = reality.record_candidate(root, candidate, [retrieval.receipt_id])
            bundle = reality.load_attack_bundle(root, candidate.candidate_id)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            costume = self._challenge(root, bundle, ChallengeKind.NOVELTY_COSTUME)
            self.assertNotEqual(costume["state"], "RESOLVED")
            self.assertNotEqual(receipt.verdict, Verdict.CLEARED)

    # 6
    def test_caller_supplied_fake_prior_art_receipt_rejected(self) -> None:
        candidate = self._candidate("obl-synthesis")
        verdict, reasons = reality.admission(
            candidate,
            [
                {
                    "module": "space",
                    "action": "source-assessment",
                    "verdict": "CLEARED",
                    "content_hash": "f" * 64,
                }
            ],
        )
        self.assertEqual(verdict, Verdict.UNKNOWN)
        self.assertIn("no evidence authority", " ".join(reasons))

    # 7
    def test_derivative_source_copies_do_not_become_independent_novelty_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, bundle = self._recorded(Path(directory), derivative=True)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(bundle.metadata["prior_art_independence_group_count"], 1)
            self.assertEqual(bundle.metadata["prior_art_derivative_evidence_count"], 1)

    # 8
    def test_unresolved_costume_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, discovery_id, synthesis_id, _ = self._task(root)
            candidate = self._candidate(synthesis_id)
            retrieval, _, _ = self._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
                retrieval_only=True,
            )
            receipt = reality.record_candidate(root, candidate, [retrieval.receipt_id])
            self.assertIn(receipt.verdict, {Verdict.UNKNOWN, Verdict.UNAVAILABLE})
            self.assertNotEqual(receipt.verdict, Verdict.CLEARED)

    # 9
    def test_assumption_knockout_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, bundle = self._recorded(Path(directory))
            challenge = self._challenge(
                Path(directory), bundle, ChallengeKind.ASSUMPTION_KNOCKOUT
            )
            self.assertEqual(challenge["kind"], "ASSUMPTION_KNOCKOUT")

    # 10
    def test_assumption_knockout_candidate_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, bundle = self._recorded(root)
            challenge = self._challenge(
                root, bundle, ChallengeKind.ASSUMPTION_KNOCKOUT
            )
            self.assertEqual(challenge["candidate_hash"], reality.candidate_hash(candidate))
            self.assertEqual(challenge["scope_hash"], bundle.scope_hash)
            self.assertEqual(challenge["obligation_id"], candidate.obligation_id)

    # 11
    def test_assumption_knockout_unresolved_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, receipt, bundle = self._recorded(
                root,
                changed_assumption="rename only",
            )
            challenge = self._challenge(
                root, bundle, ChallengeKind.ASSUMPTION_KNOCKOUT
            )
            self.assertEqual(challenge["state"], "UNRESOLVED")
            verdict, _ = reality.evaluate_admission(root, candidate, bundle)
            self.assertNotEqual(verdict, Verdict.CLEARED)
            self.assertNotEqual(receipt.verdict, Verdict.CLEARED)

    # 12
    def test_candidate_with_no_meaningful_changed_assumption_cannot_fake_difference(self) -> None:
        candidate = self._candidate(
            "obl-synthesis",
            changed_assumption="cosmetic only",
            metadata={"change_class": "wording"},
        )
        self.assertFalse(reality.meaningful_changed_assumption(candidate))
        verdict, _ = reality.admission(candidate, [])
        self.assertEqual(verdict, Verdict.ISSUE)

    # 13
    def test_competing_mechanism_generated_when_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, receipt, bundle = self._recorded(
                root,
                metadata={
                    "competing_mechanism_required": True,
                    "competing_mechanism": "global-state transition",
                    "competing_discriminator": "hold local witness fixed while varying global state",
                },
            )
            challenge = self._challenge(
                root, bundle, ChallengeKind.COMPETING_MECHANISM
            )
            self.assertEqual(challenge["metadata"]["mechanism_b"], "global-state transition")
            self.assertNotEqual(challenge["state"], "DISMISSED_NOT_APPLICABLE")
            self.assertEqual(receipt.verdict, Verdict.CLEARED)

    # 14
    def test_explicit_not_applicable_competing_mechanism_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, receipt, bundle = self._recorded(root)
            challenge = self._challenge(
                root, bundle, ChallengeKind.COMPETING_MECHANISM
            )
            self.assertEqual(challenge["state"], "DISMISSED_NOT_APPLICABLE")
            self.assertEqual(receipt.verdict, Verdict.CLEARED)

    # 15
    def test_wording_only_candidates_rejected_as_diversity(self) -> None:
        left = self._candidate("obl", candidate_id="left")
        right = replace(
            left,
            candidate_id="right",
            tags=("different-label",),
            metadata={**left.metadata, "presentation_name": "renamed module"},
        )
        row = reality.diversity_matrix([left, right])[0]
        self.assertTrue(row["mechanism_signature_same"])
        self.assertFalse(row["meaningfully_distinct"])

    # 16
    def test_genuinely_different_mechanism_recognized(self) -> None:
        left = self._candidate("obl", candidate_id="left")
        right = self._candidate(
            "obl",
            candidate_id="right",
            changed_assumption="remove the local-state requirement entirely",
            mechanism="use an explicit global constraint solver",
        )
        row = reality.diversity_matrix([left, right])[0]
        self.assertFalse(row["mechanism_signature_same"])
        self.assertTrue(row["meaningfully_distinct"])

    # 17
    def test_negative_control_discriminator_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, bundle = self._recorded(Path(directory))
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(bundle.metadata["minimum_discriminator_family"], "negative_control")

    # 18
    def test_ablation_discriminator_selection(self) -> None:
        objectives = {
            "negative_control": {
                "discrimination_rank": 2,
                "information_rank": 2,
                "risk_reduction_rank": 2,
                "cost_rank": 3,
            },
            "ablation": {
                "discrimination_rank": 5,
                "information_rank": 5,
                "risk_reduction_rank": 5,
                "cost_rank": 1,
            },
            "transfer": {
                "discrimination_rank": 1,
                "information_rank": 1,
                "risk_reduction_rank": 1,
                "cost_rank": 4,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, bundle = self._recorded(
                Path(directory),
                metadata={"discriminator_objectives": objectives},
            )
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(bundle.metadata["minimum_discriminator_family"], "ablation")

    # 19
    def test_transfer_discriminator_selection(self) -> None:
        objectives = {
            "negative_control": {
                "discrimination_rank": 2,
                "information_rank": 2,
                "risk_reduction_rank": 2,
                "cost_rank": 3,
            },
            "ablation": {
                "discrimination_rank": 1,
                "information_rank": 1,
                "risk_reduction_rank": 1,
                "cost_rank": 4,
            },
            "transfer": {
                "discrimination_rank": 5,
                "information_rank": 5,
                "risk_reduction_rank": 5,
                "cost_rank": 1,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, bundle = self._recorded(
                Path(directory),
                metadata={"discriminator_objectives": objectives},
            )
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(bundle.metadata["minimum_discriminator_family"], "transfer")

    # 20
    def test_ambiguous_incomparable_discriminator_remains_unresolved(self) -> None:
        objectives = {
            "negative_control": {
                "discrimination_rank": 5,
                "information_rank": 1,
                "risk_reduction_rank": 3,
                "cost_rank": 1,
            },
            "ablation": {
                "discrimination_rank": 1,
                "information_rank": 5,
                "risk_reduction_rank": 3,
                "cost_rank": 1,
            },
            "transfer": {
                "discrimination_rank": 1,
                "information_rank": 1,
                "risk_reduction_rank": 1,
                "cost_rank": 5,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, receipt, bundle = self._recorded(
                root,
                metadata={"discriminator_objectives": objectives},
            )
            challenge = self._challenge(
                root, bundle, ChallengeKind.MINIMUM_DISCRIMINATOR
            )
            self.assertEqual(challenge["state"], "UNRESOLVED")
            verdict, _ = reality.evaluate_admission(root, candidate, bundle)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)

    # 21
    def test_candidate_hash_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, bundle = self._recorded(root)
            altered = replace(candidate, mechanism="a different mechanism after binding")
            verdict, reasons = reality.evaluate_admission(root, altered, bundle)
            self.assertEqual(verdict, Verdict.ISSUE)
            self.assertIn("candidate_hash mismatch", " ".join(reasons))

    # 22
    def test_scope_hash_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, bundle = self._recorded(root)
            bad = reality._make_bundle(
                bundle_id=bundle.bundle_id,
                task_id=bundle.task_id,
                obligation_id=bundle.obligation_id,
                candidate_id=bundle.candidate_id,
                candidate_hash_value=bundle.candidate_hash,
                scope_hash=digest({"wrong": "scope"}),
                obligation_set_hash=bundle.obligation_set_hash,
                challenge_ids=bundle.challenge_ids,
                selected_discriminator_ids=bundle.selected_discriminator_ids,
                nearest_prior_art_receipt_ids=bundle.nearest_prior_art_receipt_ids,
                status=bundle.status,
                unresolved=bundle.unresolved,
                metadata=bundle.metadata,
            )
            verdict, reasons = reality.evaluate_admission(root, candidate, bad)
            self.assertEqual(verdict, Verdict.ISSUE)
            self.assertIn("scope_hash mismatch", " ".join(reasons))

    # 23
    def test_prior_art_receipt_for_wrong_obligation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, synthesis_id, other = self._task(root, two_discovery=True)
            assert other is not None
            candidate = self._candidate(synthesis_id)
            _, assessment, _ = self._space_evidence(root, task_id, other, candidate)
            assert assessment is not None
            receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertIn("wrong prior-art obligation", " ".join(receipt.unresolved))

    # 24
    def test_admission_cleared_means_testable_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, _ = self._recorded(Path(directory))
            notes = json.loads(receipt.notes or "{}")
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertTrue(notes["testable_candidate"])
            self.assertEqual(notes["authority"], "SYNTHESIS_ONLY")
            self.assertTrue(notes["admission_only"])

    # 25
    def test_cleared_admission_does_not_set_novelty_true(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, _ = self._recorded(Path(directory))
            notes = json.loads(receipt.notes or "{}")
            self.assertFalse(notes["novelty_established"])

    # 26
    def test_cleared_admission_does_not_set_efficacy_true(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, _ = self._recorded(Path(directory))
            notes = json.loads(receipt.notes or "{}")
            self.assertFalse(notes["efficacy_established"])

    # 27
    def test_reality_cannot_clear_engineering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, _ = self._recorded(Path(directory))
            notes = json.loads(receipt.notes or "{}")
            self.assertFalse(notes["engineering_verified"])
            self.assertFalse(notes["execution_authorized"])

    # 28
    def test_reality_cannot_clear_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, receipt, _ = self._recorded(Path(directory))
            notes = json.loads(receipt.notes or "{}")
            self.assertFalse(notes["evaluation_cleared"])
            self.assertFalse(notes["host_write_authorized"])

    # 29
    def test_self_certification_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, _, bundle = self._recorded(root)
            store = RuntimeStore(root)
            assumption = self._challenge(
                root, bundle, ChallengeKind.ASSUMPTION_KNOCKOUT
            )
            self_receipt = Receipt(
                receipt_id=new_id("rcpt"),
                module="reality",
                obligation_id=candidate.obligation_id,
                verdict=Verdict.CLEARED,
                action="self-certified-assumption-knockout",
                input_hash=digest({"candidate": candidate.candidate_id}),
                verifier="reality_runtime:self",
                started_at=utcnow(),
                finished_at=utcnow(),
                task_id=bundle.task_id,
            )
            store.write_receipt(self_receipt)
            resolution = resolution_for_receipt(
                root,
                assumption["challenge_id"],
                self_receipt.receipt_id,
                outcome=ResolutionOutcome.SUPPORTS_BASE,
                resolver="reality_runtime:self",
            )
            record_resolution(root, resolution)
            verdict, reasons = reality.evaluate_admission(root, candidate, bundle)
            self.assertEqual(verdict, Verdict.ISSUE)
            self.assertIn("self-certification", " ".join(reasons))

    # 30
    def test_historical_methodcandidate_construction_and_receipt_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, discovery_id, synthesis_id, _ = self._task(root)
            candidate = reality.MethodCandidate(
                "legacy-candidate",
                synthesis_id,
                "gap",
                "constraint",
                "change one structural assumption",
                "bounded mechanism",
                ("prior",),
                "delta",
                ("input",),
                ("output",),
                ("invariant",),
                ("dependency",),
                ("failure",),
                "negative control",
                "transfer target",
                "ablation plan",
                "verifier plan",
                metadata={
                    "scope_hash": digest({"scope": "legacy"}),
                    "prior_art_claim_scope": CLAIM_SCOPE,
                },
            )
            _, assessment, _ = self._space_evidence(
                root, task_id, discovery_id, candidate
            )
            assert assessment is not None
            receipt = reality.record_candidate(root, candidate, [assessment.receipt_id])
            self.assertEqual(receipt.module, "reality")
            self.assertEqual(receipt.action, "candidate-admission")
            self.assertEqual(receipt.verdict, Verdict.CLEARED)

    # 31
    def test_reality_has_no_foil_import(self) -> None:
        source_path = ROOT / "tools" / "reality_runtime.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                names = []
            for name in names:
                if name == "foil" or name.startswith("foil_") or name.startswith("foil."):
                    forbidden.append(name)
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
