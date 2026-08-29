from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import soul_runtime as soul  # noqa: E402
from egrt_challenge import propose_challenge  # noqa: E402
from egrt_challenge_types import (  # noqa: E402
    ChallengeKind,
    ChallengeOrigin,
    ChallengeRequest,
)
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import (  # noqa: E402
    EvidenceClass,
    EvidenceRef,
    ObligationKind,
    Receipt,
    Verdict,
    digest,
)


def init_root(
    path: Path,
    *,
    challenge_mode: str = "shadow",
    automatic_assurance: bool = False,
    strict_active_task: bool = False,
) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "runtime": {
                    "enabled": True,
                    "release_gate": True,
                    "automatic_assurance": automatic_assurance,
                    "automatic_graph_revision": True,
                    "strict_active_task": strict_active_task,
                },
                "challenge": {"mode": challenge_mode},
            }
        ),
        encoding="utf-8",
    )


def current_task_id(root: Path, task_id: str) -> str:
    return soul.resolve_current_task_id(root, task_id)[0]


def write_receipt(
    root: Path,
    task_id: str,
    obligation,
    verdict: Verdict,
    *,
    suffix: str = "",
    with_evidence: bool = False,
) -> Receipt:
    evidence = ()
    if with_evidence:
        evidence = (
            EvidenceRef(
                evidence_class=EvidenceClass.OBSERVED,
                verifier=f"verifier-{suffix or 'one'}",
                provenance_group=f"provenance-{suffix or 'one'}",
                metadata={
                    "producer_provenance": f"producer-{suffix or 'one'}",
                    "verifier_provenance": f"verifier-{suffix or 'one'}",
                },
            ),
        )
    receipt = Receipt(
        receipt_id=(
            f"rcpt-{obligation.obligation_id}-{verdict.value.lower()}-{suffix or 'one'}"
        ),
        module=obligation.required_module,
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="test",
        input_hash=digest(
            {"obligation": obligation.obligation_id, "suffix": suffix}
        ),
        evidence=evidence,
        task_id=task_id,
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def task_obligation(root: Path, task_id: str, kind: ObligationKind) -> dict:
    task = RuntimeStore(root).read_task(task_id)
    if task is None:
        raise AssertionError("task missing")
    for row in task.get("obligations", []):
        if row.get("kind") == kind.value:
            return row
    raise AssertionError(f"{kind.value} obligation missing")


class SoulAutomaticSupersessionTests(unittest.TestCase):
    def test_new_task_automatically_supersedes_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            first = soul.start_task(root, "first frame")
            second = soul.start_task(
                root,
                "corrected frame",
                supersession_reason="first frame was wrong",
            )
            store = RuntimeStore(root)
            old = store.read_task(first.task_id)
            self.assertIsNotNone(old)
            self.assertFalse(old["active"])
            self.assertFalse(old["released"])
            self.assertEqual(old["metadata"]["soul_status"], "SUPERSEDED")
            self.assertEqual(
                old["metadata"]["soul_superseded_by"],
                second.task_id,
            )
            self.assertEqual(
                (store.base / "active_task").read_text().strip(),
                second.task_id,
            )
            resolved, chain = soul.resolve_current_task_id(root, first.task_id)
            self.assertEqual(resolved, second.task_id)
            self.assertEqual(chain, (first.task_id, second.task_id))

    def test_strict_compatibility_mode_can_still_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, strict_active_task=True)
            soul.start_task(root, "first")
            with self.assertRaises(soul.ActiveTaskError):
                soul.start_task(root, "second")

    def test_operations_through_old_id_follow_current_successor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            first = soul.start_task(root, "first")
            second = soul.start_task(root, "second")
            obligation = soul.add_obligation(
                root,
                first.task_id,
                ObligationKind.PROOF,
                "prove on current task",
            )
            plan = soul.plan_routes(root, first.task_id)
            self.assertEqual(plan.task_id, second.task_id)
            self.assertIn(obligation.obligation_id, plan.selected_obligations)
            self.assertEqual(
                plan.supersession_chain,
                (first.task_id, second.task_id),
            )

    def test_post_freeze_obligation_creates_successor_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "revise")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "first obligation",
            )
            soul.freeze_task(root, task.task_id)
            discovery = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.DISCOVERY,
                "newly discovered obligation",
            )
            successor = current_task_id(root, task.task_id)
            self.assertNotEqual(successor, task.task_id)
            old = RuntimeStore(root).read_task(task.task_id)
            new = RuntimeStore(root).read_task(successor)
            self.assertEqual(old["metadata"]["soul_superseded_by"], successor)
            identifiers = {row["obligation_id"] for row in new["obligations"]}
            self.assertIn(proof.obligation_id, identifiers)
            self.assertIn(discovery.obligation_id, identifiers)
            self.assertTrue(new["metadata"]["soul_frozen"])

    def test_predecessor_receipt_cannot_clear_successor_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "receipt binding")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            soul.freeze_task(root, task.task_id)
            write_receipt(root, task.task_id, proof, Verdict.CLEARED)
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.DISCOVERY,
                "new requirement",
            )
            successor = current_task_id(root, task.task_id)
            verdict, detail = soul.release_gate(root, successor)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            proof_row = next(
                row
                for row in detail["obligations"]
                if row["obligation_id"] == proof.obligation_id
            )
            self.assertEqual(proof_row["reason"], "missing-receipt")

    def test_empty_task_remains_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_assurance=True)
            task = soul.start_task(root, "empty")
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            stored = RuntimeStore(root).read_task(task.task_id)
            self.assertEqual(stored.get("obligations"), [])


class SoulAutomaticRoutingTests(unittest.TestCase):
    def test_default_routes_every_dependency_ready_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "all ready")
            obligations = [
                soul.add_obligation(
                    root,
                    task.task_id,
                    ObligationKind.ENGINEERING,
                    f"engineering {index}",
                    metadata={"cost_units": 50 + index},
                )
                for index in range(12)
            ]
            plan = soul.plan_routes(root, task.task_id)
            self.assertEqual(plan.policy.mode, "AUTOMATIC_ALL_READY")
            self.assertEqual(
                set(plan.selected_obligations),
                {row.obligation_id for row in obligations},
            )
            self.assertEqual(plan.excluded_obligations, ())
            self.assertEqual(plan.liveness_status, "RUNNABLE")

    def test_budgeted_experiment_skips_expensive_and_runs_later_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "budget fill")
            expensive = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "expensive high priority",
                metadata={"cost_units": 8, "risk_rank": 5},
            )
            cheap_one = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.DISCOVERY,
                "cheap one",
                metadata={"cost_units": 2, "risk_rank": 4},
            )
            cheap_two = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.ENGINEERING,
                "cheap two",
                metadata={"cost_units": 2, "risk_rank": 3},
            )
            plan = soul.plan_routes(
                root,
                task.task_id,
                policy=soul.RoutingPolicy(
                    mode="BUDGETED_EXPERIMENTAL",
                    max_cost_units=4,
                ),
            )
            self.assertNotIn(expensive.obligation_id, plan.selected_obligations)
            self.assertIn(cheap_one.obligation_id, plan.selected_obligations)
            self.assertIn(cheap_two.obligation_id, plan.selected_obligations)
            self.assertIn(
                (expensive.obligation_id, "MAX_COST_UNITS_EXPERIMENTAL"),
                plan.excluded_obligations,
            )

    def test_dependency_blocks_child_until_parent_clears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "dependency")
            parent = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "parent",
            )
            child = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.ENGINEERING,
                "child",
                metadata={"depends_on": [parent.obligation_id]},
            )
            first = soul.plan_routes(root, task.task_id)
            self.assertIn(parent.obligation_id, first.selected_obligations)
            self.assertNotIn(child.obligation_id, first.selected_obligations)
            self.assertIn(
                (child.obligation_id, (parent.obligation_id,)),
                first.dependency_blocked,
            )
            write_receipt(root, task.task_id, parent, Verdict.CLEARED)
            second = soul.plan_routes(root, task.task_id)
            self.assertEqual(second.selected_obligations, (child.obligation_id,))

    def test_same_module_transport_batch_requires_isolated_subrequests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "batch")
            first = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.ENGINEERING,
                "one",
            )
            second = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.ENGINEERING,
                "two",
            )
            plan = soul.plan_routes(root, task.task_id)
            self.assertEqual(len(plan.batches), 1)
            batch = plan.batches[0]
            self.assertEqual(
                set(batch.obligation_ids),
                {first.obligation_id, second.obligation_id},
            )
            self.assertEqual(
                batch.context_sharing_status,
                "AUTOMATIC_ISOLATED_SUBREQUESTS_REQUIRED",
            )
            self.assertEqual(
                batch.equivalence_status,
                "PARTITION_REQUIRED_NOT_EMPIRICALLY_CLAIMED",
            )

    def test_explicit_shared_context_remains_unvalidated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "shared")
            for claim in ("one", "two"):
                soul.add_obligation(
                    root,
                    task.task_id,
                    ObligationKind.ENGINEERING,
                    claim,
                    metadata={"shared_context_group": "same-system"},
                )
            plan = soul.plan_routes(root, task.task_id)
            self.assertEqual(len(plan.batches), 1)
            self.assertEqual(
                plan.batches[0].context_sharing_status,
                "CALLER_OPT_IN_SHARED_CONTEXT",
            )
            self.assertEqual(plan.batches[0].equivalence_status, "NOT_ESTABLISHED")

    def test_explicit_empty_module_set_stalls_without_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "availability")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            plan = soul.plan_routes(
                root,
                task.task_id,
                policy=soul.RoutingPolicy(available_modules=()),
            )
            self.assertEqual(plan.selected_obligations, ())
            self.assertIn(
                (obligation.obligation_id, "MODULE_UNAVAILABLE"),
                plan.excluded_obligations,
            )
            self.assertEqual(plan.liveness_status, "STALLED_MODULE_UNAVAILABLE")

    def test_unavailable_dependency_reports_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "frontier")
            parent = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "parent",
            )
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.ENGINEERING,
                "child",
                metadata={"depends_on": [parent.obligation_id]},
            )
            plan = soul.plan_routes(
                root,
                task.task_id,
                policy=soul.RoutingPolicy(available_modules=("power",)),
            )
            self.assertEqual(plan.liveness_status, "STALLED_MODULE_UNAVAILABLE")
            self.assertIn(parent.obligation_id, plan.stall_frontier)

    def test_plan_is_deterministic_for_same_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "deterministic")
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            first = soul.plan_routes(root, task.task_id)
            second = soul.plan_routes(root, task.task_id)
            self.assertEqual(first.plan_hash, second.plan_hash)
            self.assertEqual(
                first.selection_certificate_hash,
                second.selection_certificate_hash,
            )

    def test_route_state_contains_no_raw_goal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            marker = "private-goal-marker-automatic-1882"
            task = soul.start_task(root, marker)
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            soul.plan_routes(root, task.task_id)
            serialized = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (RuntimeStore(root).base / "soul_routes").glob("*.json")
            )
            self.assertNotIn(marker, serialized)


class SoulChallengeRoutingTests(unittest.TestCase):
    def _challenge(self, root: Path, task_id: str, obligation, frozen: dict) -> None:
        propose_challenge(
            root,
            ChallengeRequest(
                challenge_id=f"challenge-{obligation.obligation_id}",
                task_id=task_id,
                obligation_id=obligation.obligation_id,
                target_module=obligation.required_module,
                origin=ChallengeOrigin.USER,
                kind=ChallengeKind.COUNTEREXAMPLE,
                hypothesis="a counterexample may exist",
                alternative="the current claim is sound",
                refuter="resolve with claim-native evidence",
                consequence_if_true="release would be unsound",
                load_bearing=True,
                required_capability="FORMAL_PROOF",
                candidate_hash=digest("candidate"),
                scope_hash=digest("scope"),
                obligation_set_hash=frozen["metadata"][
                    "soul_obligation_set_hash"
                ],
                proposer="test",
            ),
        )

    def test_shadow_challenge_is_routed_but_does_not_block_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="shadow")
            task = soul.start_task(root, "shadow")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            frozen = soul.freeze_task(root, task.task_id)
            write_receipt(root, task.task_id, obligation, Verdict.CLEARED)
            self._challenge(root, task.task_id, obligation, frozen)
            plan = soul.plan_routes(root, task.task_id)
            self.assertIn(obligation.obligation_id, plan.selected_obligations)
            verdict, detail = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.CLEARED)
            self.assertEqual(detail["obligations"][0]["challenge_mode"], "shadow")

    def test_enforced_open_challenge_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="enforced")
            task = soul.start_task(root, "enforced")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            frozen = soul.freeze_task(root, task.task_id)
            write_receipt(root, task.task_id, obligation, Verdict.CLEARED)
            self._challenge(root, task.task_id, obligation, frozen)
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)


class SoulAutomaticAssuranceTests(unittest.TestCase):
    def test_assurance_is_injected_only_when_domain_work_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_assurance=True)
            empty = soul.start_task(root, "empty")
            verdict, _ = soul.release_gate(root, empty.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            empty_task = RuntimeStore(root).read_task(empty.task_id)
            self.assertFalse(
                any(
                    row.get("kind") == ObligationKind.ASSURANCE.value
                    for row in empty_task.get("obligations", [])
                )
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_assurance=True)
            task = soul.start_task(root, "domain")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            frozen = soul.freeze_task(root, task.task_id)
            assurance = task_obligation(
                root,
                str(frozen["task_id"]),
                ObligationKind.ASSURANCE,
            )
            self.assertTrue(assurance["load_bearing"])
            self.assertIn(proof.obligation_id, assurance["metadata"]["depends_on"])

    def test_automatic_release_runs_gauntlet_and_clears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(
                root,
                challenge_mode="off",
                automatic_assurance=True,
            )
            task = soul.start_task(root, "automatic release")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            frozen = soul.freeze_task(root, task.task_id)
            resolved_id = str(frozen["task_id"])
            write_receipt(root, resolved_id, proof, Verdict.CLEARED)
            from gauntlet_runtime import emit_probe

            emit_probe(
                root,
                resolved_id,
                "automatic-release-probe",
                probe_hash=digest("probe"),
                verifier="independent-probe",
            )
            verdict, detail = soul.automatic_release(root, task.task_id)
            self.assertEqual(verdict, Verdict.CLEARED)
            self.assertIsNotNone(detail["assurance_receipt_id"])
            self.assertEqual(detail["routing_liveness_status"], "RUNNABLE")
            stored = RuntimeStore(root).read_task(resolved_id)
            self.assertTrue(stored["released"])

    def test_automatic_release_reports_unresolved_domain_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(
                root,
                challenge_mode="off",
                automatic_assurance=True,
            )
            task = soul.start_task(root, "blocked release")
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            frozen = soul.freeze_task(root, task.task_id)
            resolved_id = str(frozen["task_id"])
            from gauntlet_runtime import emit_probe

            emit_probe(
                root,
                resolved_id,
                "automatic-release-probe",
                probe_hash=digest("probe"),
                verifier="independent-probe",
            )
            verdict, detail = soul.automatic_release(root, task.task_id)
            self.assertNotEqual(verdict, Verdict.CLEARED)
            self.assertEqual(detail["resolved_task_id"], resolved_id)
            self.assertIsNotNone(detail["assurance_receipt_id"])


class SoulReleaseConsistencyTests(unittest.TestCase):
    def test_receipt_sequence_outranks_wall_clock_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="off")
            task = soul.start_task(root, "sequence")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            first = write_receipt(
                root,
                task.task_id,
                obligation,
                Verdict.CLEARED,
                suffix="old",
            )
            second = write_receipt(
                root,
                task.task_id,
                obligation,
                Verdict.ISSUE,
                suffix="new",
            )
            store = RuntimeStore(root)
            old = store.read_receipt(first.receipt_id, require_integrity=False)
            new = store.read_receipt(second.receipt_id, require_integrity=False)
            old["stored_at"] = "2099-01-01T00:00:00+00:00"
            old.pop("content_hash", None)
            old["content_hash"] = digest(old)
            store._write(store.receipts / f"{first.receipt_id}.json", old)
            new["stored_at"] = "2000-01-01T00:00:00+00:00"
            new.pop("content_hash", None)
            new["content_hash"] = digest(new)
            store._write(store.receipts / f"{second.receipt_id}.json", new)
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.ISSUE)

    def test_release_is_idempotent_and_soul_writes_no_domain_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="off")
            task = soul.start_task(root, "release")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            write_receipt(root, task.task_id, obligation, Verdict.CLEARED)
            first, _ = soul.release_task(root, task.task_id)
            second, detail = soul.release_task(root, task.task_id)
            self.assertEqual(first, Verdict.CLEARED)
            self.assertEqual(second, Verdict.CLEARED)
            self.assertTrue(detail["already_released"])
            receipts = [
                RuntimeStore(root).read_receipt(path.stem)
                for path in RuntimeStore(root).receipts.glob("*.json")
            ]
            self.assertFalse(
                any(row and row.get("module") == "soul" for row in receipts)
            )

    def test_post_release_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, challenge_mode="off")
            task = soul.start_task(root, "sealed")
            obligation = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            write_receipt(root, task.task_id, obligation, Verdict.CLEARED)
            verdict, _ = soul.release_task(root, task.task_id)
            self.assertEqual(verdict, Verdict.CLEARED)
            with self.assertRaises(ValueError):
                write_receipt(
                    root,
                    task.task_id,
                    obligation,
                    Verdict.ISSUE,
                    suffix="late",
                )


if __name__ == "__main__":
    unittest.main()
