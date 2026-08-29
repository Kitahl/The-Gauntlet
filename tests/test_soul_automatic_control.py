from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import egrt_hook  # noqa: E402
import soul_runtime as soul  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import ObligationKind, Receipt, Verdict, digest  # noqa: E402


def init_root(
    path: Path,
    *,
    automatic_assurance: bool = False,
    challenge_mode: str = "off",
) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "governing_files": [],
                "runtime": {
                    "enabled": True,
                    "release_gate": True,
                    "strict_active_task": False,
                    "automatic_graph_revision": True,
                    "automatic_assurance": automatic_assurance,
                },
                "challenge": {"mode": challenge_mode},
            }
        ),
        encoding="utf-8",
    )


def write_clear_receipt(root: Path, task_id: str, obligation) -> Receipt:
    receipt = Receipt(
        receipt_id=f"rcpt-{obligation.obligation_id}",
        module=obligation.required_module,
        obligation_id=obligation.obligation_id,
        verdict=Verdict.CLEARED,
        action="test-clear",
        input_hash=digest({"obligation_id": obligation.obligation_id}),
        task_id=task_id,
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


class SoulControlPlaneTests(unittest.TestCase):
    def test_caller_cannot_predeclare_soul_control_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            with self.assertRaises(ValueError):
                soul.start_task(
                    root,
                    "sanitize metadata",
                    metadata={
                        "label": "would-be-user-data",
                        "soul_superseded_by": "attacker-task",
                        "soul_frozen": True,
                        "soul_release_token": "attacker-token",
                        "active": False,
                        "released": True,
                        "content_hash": "forged",
                    },
                )
            store = RuntimeStore(root)
            self.assertEqual(list(store.tasks.glob("*.json")), [])

    def test_noncontrol_metadata_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(
                root,
                "preserve ordinary metadata",
                metadata={"label": "preserved", "experiment_group": "A"},
            )
            stored = RuntimeStore(root).read_task(task.task_id)
            self.assertEqual(stored["metadata"]["label"], "preserved")
            self.assertEqual(stored["metadata"]["experiment_group"], "A")
            self.assertEqual(stored["metadata"]["soul_status"], "ACTIVE")

    def test_contradictory_supersession_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "lineage integrity")
            store = RuntimeStore(root)
            stored = store.read_task(task.task_id)
            stored["metadata"].update(
                {
                    "soul_status": "SUPERSEDED",
                    "soul_superseded_by": "ghost-task",
                    "soul_supersession_reason_hash": digest("forged"),
                }
            )
            store.write_task(stored)
            with self.assertRaises(soul.SoulGraphError):
                soul.resolve_current_task_id(root, task.task_id)

    def test_route_plan_binds_complete_supersession_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            first = soul.start_task(root, "first frame")
            second = soul.start_task(root, "corrected frame")
            obligation = soul.add_obligation(
                root,
                first.task_id,
                ObligationKind.PROOF,
                "prove the corrected claim",
            )
            plan = soul.plan_routes(root, first.task_id)
            self.assertEqual(plan.task_id, second.task_id)
            self.assertEqual(
                plan.supersession_chain,
                (first.task_id, second.task_id),
            )
            self.assertIn(obligation.obligation_id, plan.selected_obligations)
            self.assertEqual(plan.schema, soul.SOUL_CONTROL_SCHEMA)

    def test_empty_task_returns_unknown_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root, automatic_assurance=True)
            task = soul.start_task(root, "empty task")
            verdict, detail = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertEqual(detail["reason"], "no-load-bearing-obligations")
            self.assertEqual(detail["routing_batches"], [])
            stored = RuntimeStore(root).read_task(task.task_id)
            self.assertEqual(stored["obligations"], [])

    def test_missing_domain_receipt_exposes_bounded_automatic_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "route missing proof")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "prove claim",
            )
            verdict, detail = soul.automatic_release(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertIn(proof.obligation_id, detail["selected_obligations"])
            self.assertTrue(detail["routing_batches"])
            self.assertEqual(detail["routing_batches"][0]["module"], "mind")
            self.assertFalse(
                detail["routing_batches"][0]["execution_authorized"]
            )

    def test_automatic_release_is_idempotent_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "idempotent automatic release")
            proof = soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "prove claim",
            )
            soul.freeze_task(root, task.task_id)
            write_clear_receipt(root, task.task_id, proof)
            first, first_detail = soul.automatic_release(root, task.task_id)
            second, second_detail = soul.automatic_release(root, task.task_id)
            self.assertEqual(first, Verdict.CLEARED)
            self.assertEqual(second, Verdict.CLEARED)
            self.assertFalse(first_detail.get("already_released", False))
            self.assertTrue(second_detail["already_released"])
            self.assertIsNone(second_detail["routing_plan_id"])


class SoulHookFailClosedTests(unittest.TestCase):
    def test_stop_hook_blocks_when_orchestrator_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "hook failure")
            soul.add_obligation(
                root,
                task.task_id,
                ObligationKind.PROOF,
                "claim",
            )
            output = io.StringIO()
            with (
                patch.object(egrt_hook, "project_root", return_value=root),
                patch.object(
                    egrt_hook,
                    "automatic_release",
                    side_effect=RuntimeError("must not be persisted"),
                ),
                patch.object(sys, "stdin", io.StringIO("{}")),
                redirect_stdout(output),
            ):
                code = egrt_hook.stop()
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["decision"], "block")
            self.assertIn("failed closed", payload["reason"])
            self.assertNotIn("must not be persisted", payload["reason"])
            events = RuntimeStore(root).iter_events(task.task_id)
            self.assertTrue(
                any(
                    row.get("event_type") == "orchestrator.unavailable"
                    for row in events
                )
            )


if __name__ == "__main__":
    unittest.main()
