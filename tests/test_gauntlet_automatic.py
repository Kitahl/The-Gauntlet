from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gauntlet_automatic as automatic  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import (  # noqa: E402
    Obligation,
    ObligationKind,
    RuntimeEvent,
    TaskState,
    Verdict,
    digest,
)


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def event(
    event_id: str,
    event_type: str,
    *,
    task_id: str,
    metadata: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        component="test",
        task_id=task_id,
        payload_hash=digest({"event_id": event_id, "event_type": event_type}),
        timestamp=f"2026-08-28T00:00:{len(event_id):02d}+00:00",
        metadata=metadata or {},
    )


def make_task(root: Path) -> tuple[str, str]:
    task_id = "task-auto"
    assurance_id = "obl-assurance"
    RuntimeStore(root).write_task(
        TaskState(
            task_id=task_id,
            goal_hash=digest("automatic assurance"),
            obligations=[
                Obligation(
                    assurance_id,
                    ObligationKind.ASSURANCE,
                    "Audit the represented process state",
                    required_module="gauntlet",
                )
            ],
        )
    )
    return task_id, assurance_id


def append_all_operation_triggers(root: Path, task_id: str) -> None:
    store = RuntimeStore(root)
    rows = [
        event("failed-1", "action.failed", task_id=task_id, metadata={"failure_signature": "same"}),
        event("failed-2", "action.failed", task_id=task_id, metadata={"failure_signature": "same"}),
        event("failed-3", "action.failed", task_id=task_id, metadata={"failure_signature": "same"}),
        event("attempt-1", "action.attempted", task_id=task_id, metadata={"blocker_hash": "b", "progress_hash": "p"}),
        event("attempt-2", "action.attempted", task_id=task_id, metadata={"blocker_hash": "b", "progress_hash": "p"}),
        event("attempt-3", "action.attempted", task_id=task_id, metadata={"blocker_hash": "b", "progress_hash": "p"}),
        event("release", "release.attempted", task_id=task_id),
        event("novel", "novelty.claim", task_id=task_id, metadata={"discovery_obligation": "discover"}),
        event("inherited", "claim.adopted", task_id=task_id, metadata={"inherited": True, "derivation_obligation": "derive"}),
        event("evidence", "evidence.attached", task_id=task_id, metadata={"producer": "mind", "verifier": "other", "producer_provenance": "p1", "verifier_provenance": "p2"}),
        event("handoff", "handoff.started", task_id=task_id, metadata={"handoff_id": "h1"}),
        event("contract", "contract.bound", task_id=task_id, metadata={"handoff_id": "h1", "contract_hash": digest("contract")}),
        event("explain", "explanation.claim", task_id=task_id, metadata={"claim_id": "c1", "claim_hash": digest("claim")}),
        event("artifact", "artifact.claim", task_id=task_id, metadata={"claim_id": "c1", "claim_hash": digest("claim")}),
        event("authority", "authority.snapshot", task_id=task_id),
        event("probe", "coverage.probe", task_id=task_id, metadata={"failure_class": "parser", "status": "VALID", "artifact_hash": digest("a"), "scope_hash": digest("s"), "verifier": "probe"}),
    ]
    for row in rows:
        store.append_event(row)


class AutomaticGauntletTests(unittest.TestCase):
    def test_full_mode_selects_every_applicable_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            append_all_operation_triggers(root, task_id)
            plan = automatic.plan_automatic_assurance(
                root, assurance_id, task_id=task_id
            )
            self.assertEqual(set(plan.applicable_operations), set(automatic.low_level.OPERATIONS))
            self.assertEqual(plan.selected_operations, plan.applicable_operations)
            self.assertEqual(plan.deferred_operations, ())

    def test_full_mode_does_not_reduce_coverage_for_small_advisory_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            append_all_operation_triggers(root, task_id)
            plan = automatic.plan_automatic_assurance(
                root,
                assurance_id,
                task_id=task_id,
                policy=automatic.AutomaticAssurancePolicy(
                    max_cost_units=1,
                    max_operations=1,
                ),
            )
            self.assertEqual(plan.selected_operations, plan.applicable_operations)
            self.assertTrue(plan.advisory_budget_exceeded)
            self.assertEqual(plan.deferred_operations, ())

    def test_automatic_full_does_not_stop_after_first_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            append_all_operation_triggers(root, task_id)
            receipt = automatic.run_automatic_assurance(
                root, assurance_id, task_id=task_id
            )
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            metadata = receipt.evidence[0].metadata
            self.assertEqual(
                set(metadata["executed_operations"]),
                set(metadata["selected_operations"]),
            )
            self.assertEqual(len(metadata["executed_operations"]), 10)

    def test_selective_reduction_requires_explicit_experimental_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            append_all_operation_triggers(root, task_id)
            plan = automatic.plan_automatic_assurance(
                root,
                assurance_id,
                task_id=task_id,
                policy=automatic.AutomaticAssurancePolicy(
                    mode="SELECTIVE_EXPERIMENTAL",
                    max_cost_units=1,
                    max_operations=1,
                ),
            )
            self.assertEqual(len(plan.selected_operations), 1)
            self.assertGreater(len(plan.deferred_operations), 0)

    def test_broken_receipt_event_chain_prevents_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            store = RuntimeStore(root)
            store.append_event(event("release", "release.attempted", task_id=task_id))
            store.append_event(event("authority", "authority.snapshot", task_id=task_id))
            store.append_event(
                event(
                    "probe",
                    "coverage.probe",
                    task_id=task_id,
                    metadata={
                        "failure_class": "parser",
                        "status": "VALID",
                        "artifact_hash": digest("a"),
                        "scope_hash": digest("s"),
                        "verifier": "probe",
                    },
                )
            )
            # Plant one integrity-valid receipt directly without the RuntimeStore's
            # corresponding receipt/state events. The controller must not green it.
            body = {
                "receipt_id": "planted",
                "module": "mind",
                "obligation_id": "foreign",
                "verdict": Verdict.CLEARED.value,
                "action": "test",
                "input_hash": digest("i"),
                "output_hash": None,
                "evidence": [],
                "verifier": None,
                "tool_version": None,
                "started_at": None,
                "finished_at": None,
                "unresolved": [],
                "notes": None,
                "task_id": task_id,
                "stored_at": "2026-08-28T00:00:00+00:00",
                "seq": 1,
            }
            body["content_hash"] = digest(body)
            store._write(store.receipts / "planted.json", body)
            receipt = automatic.run_automatic_assurance(
                root, assurance_id, task_id=task_id
            )
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            metadata = receipt.evidence[0].metadata
            self.assertEqual(
                metadata["runtime_event_coverage_status"],
                "UNKNOWN_RUNTIME_EVENT_CHAIN",
            )

    def test_receipt_remains_assurance_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, assurance_id = make_task(root)
            append_all_operation_triggers(root, task_id)
            receipt = automatic.run_automatic_assurance(
                root, assurance_id, task_id=task_id
            )
            metadata = receipt.evidence[0].metadata
            self.assertEqual(metadata["authority"], "ASSURANCE_ONLY")
            self.assertFalse(metadata["target_domain_clearance_authorized"])


if __name__ == "__main__":
    unittest.main()
