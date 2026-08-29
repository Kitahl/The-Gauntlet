from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import reality_runtime as reality  # noqa: E402
import space_runtime as space  # noqa: E402
import test_reality_challenge_runtime as fixtures  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import ArtifactRef, Verdict  # noqa: E402


class RealityHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fixtures.RealityChallengeRuntimeTests(methodName="runTest")

    def _refuting_assessment(
        self,
        root: Path,
        discovery_id: str,
        search_receipt_id: str,
    ):
        return space.assess_sources(
            root,
            discovery_id,
            search_receipt_id,
            [
                space.SourceAssessment(
                    "assessment-refute",
                    ArtifactRef("prior-art-refute.pdf", sha256="f" * 64),
                    "REFUTES",
                    "independent-reviewer-refute",
                    fixtures.CLAIM_SCOPE,
                    "lineage-refute",
                )
            ],
        )

    def test_space_refutation_blocks_costume_and_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.init_root(root)
            task_id, discovery_id, synthesis_id, _ = self.fixture._task(root)
            candidate = self.fixture._candidate(synthesis_id)
            retrieval, _, _ = self.fixture._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
                retrieval_only=True,
            )
            refuting = self._refuting_assessment(
                root,
                discovery_id,
                retrieval.receipt_id,
            )
            self.assertEqual(refuting.verdict, Verdict.CLEARED)
            receipt = reality.record_candidate(root, candidate, [refuting.receipt_id])
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertIn("refutes", " ".join(receipt.unresolved).lower())
            bundle = reality.load_attack_bundle(root, candidate.candidate_id)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            store = RuntimeStore(root)
            costume = next(
                store.read_challenge(challenge_id)
                for challenge_id in bundle.challenge_ids
                if (store.read_challenge(challenge_id) or {}).get("kind")
                == "NOVELTY_COSTUME"
            )
            self.assertIsNotNone(costume)
            assert costume is not None
            self.assertNotEqual(costume["state"], "RESOLVED")

    def test_latest_candidate_bound_assessment_outranks_stale_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.init_root(root)
            task_id, discovery_id, synthesis_id, _ = self.fixture._task(root)
            candidate = self.fixture._candidate(synthesis_id)
            retrieval, support, _ = self.fixture._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
            )
            assert support is not None
            refuting = self._refuting_assessment(
                root,
                discovery_id,
                retrieval.receipt_id,
            )
            self.assertEqual(refuting.verdict, Verdict.CLEARED)
            # Deliberately pass only the stale support receipt. Reality must discover
            # and honor the newer candidate-bound Space assessment by store order.
            receipt = reality.record_candidate(root, candidate, [support.receipt_id])
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertIn("current space assessment refutes", " ".join(receipt.unresolved).lower())

    def test_named_competing_mechanism_requires_explicit_discriminator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.init_root(root)
            task_id, discovery_id, synthesis_id, _ = self.fixture._task(root)
            candidate = self.fixture._candidate(
                synthesis_id,
                metadata={
                    "competing_mechanism": "global-state transition",
                    "competing_mechanism_required": True,
                },
            )
            _, support, _ = self.fixture._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
            )
            assert support is not None
            receipt = reality.record_candidate(root, candidate, [support.receipt_id])
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertIn("a-vs-b discriminator", " ".join(receipt.unresolved).lower())

    def test_invariants_and_dependencies_are_required_for_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.init_root(root)
            task_id, discovery_id, synthesis_id, _ = self.fixture._task(root)
            candidate = replace(
                self.fixture._candidate(synthesis_id),
                invariants=(),
                dependencies=(),
            )
            _, support, _ = self.fixture._space_evidence(
                root,
                task_id,
                discovery_id,
                candidate,
            )
            assert support is not None
            receipt = reality.record_candidate(root, candidate, [support.receipt_id])
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            reasons = " ".join(receipt.unresolved).lower()
            self.assertIn("invariants are required", reasons)
            self.assertIn("dependencies are required", reasons)


if __name__ == "__main__":
    unittest.main()
