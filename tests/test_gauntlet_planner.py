from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gauntlet_runtime as gauntlet  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import (  # noqa: E402
    Obligation,
    ObligationKind,
    Receipt,
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


def runtime_event(
    event_id: str,
    event_type: str,
    *,
    task_id: str = "task-a",
    component: str = "test",
    metadata: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        component=component,
        task_id=task_id,
        payload_hash=digest({"event_id": event_id, "event_type": event_type}),
        timestamp=f"2026-08-27T00:00:{len(event_id):02d}+00:00",
        metadata=metadata or {},
    )


class GauntletMinimalPlannerTests(unittest.TestCase):
    def _task(self, root: Path, *, clear_proof: bool = True) -> tuple[str, str, str]:
        task_id = "task-a"
        proof_id = "obl-proof"
        assurance_id = "obl-assurance"
        store = RuntimeStore(root)
        store.write_task(
            TaskState(
                task_id=task_id,
                goal_hash=digest("candidate release"),
                obligations=[
                    Obligation(
                        proof_id,
                        ObligationKind.PROOF,
                        "Prove the candidate",
                        required_module="mind",
                    ),
                    Obligation(
                        assurance_id,
                        ObligationKind.ASSURANCE,
                        "Audit represented process hazards",
                        required_module="gauntlet",
                    ),
                ],
            )
        )
        if clear_proof:
            store.write_receipt(
                Receipt(
                    receipt_id="proof-receipt",
                    module="mind",
                    obligation_id=proof_id,
                    verdict=Verdict.CLEARED,
                    action="proof",
                    input_hash=digest("proof-input"),
                    task_id=task_id,
                )
            )
        store.append_event(runtime_event("snapshot", "authority.snapshot", task_id=task_id))
        gauntlet.emit_probe(
            root,
            task_id,
            "parser-confusion",
            probe_hash=digest("probe"),
            verifier="independent-probe",
        )
        store.append_event(runtime_event("release", "release.attempted", task_id=task_id))
        return task_id, proof_id, assurance_id

    def test_release_plan_selects_only_triggered_hazards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root)
            plan = gauntlet.plan_assurance(root, assurance_id, task_id=task_id)
            self.assertEqual(plan.selected_operations, ("audit", "refresh", "oob"))
            self.assertEqual(len(plan.candidates), 3)
            self.assertEqual(plan.planned_cost_units, 3)
            self.assertLess(plan.planned_cost_units, plan.registry_cost_units)

    def test_release_gate_stops_after_first_blocking_issue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root, clear_proof=False)
            receipt = gauntlet.run_assurance(root, assurance_id, task_id=task_id)
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            metadata = receipt.evidence[0].metadata
            self.assertEqual(metadata["executed_operations"], ["audit"])
            self.assertEqual(metadata["metrics"]["executed_operation_count"], 1)
            self.assertGreater(metadata["metrics"]["avoided_registry_cost_units"], 0)

    def test_diagnostic_mode_does_not_early_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root, clear_proof=False)
            receipt = gauntlet.run_assurance(
                root,
                assurance_id,
                task_id=task_id,
                policy=gauntlet.AssurancePolicy(mode="DIAGNOSTIC"),
            )
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertEqual(
                receipt.evidence[0].metadata["executed_operations"],
                ["audit", "refresh", "oob"],
            )

    def test_budget_exclusion_prevents_false_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root)
            receipt = gauntlet.run_assurance(
                root,
                assurance_id,
                task_id=task_id,
                policy=gauntlet.AssurancePolicy(max_cost_units=1, max_operations=1),
            )
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            excluded = receipt.evidence[0].metadata["excluded_operations"]
            self.assertEqual({row[0] for row in excluded}, {"refresh", "oob"})

    def test_plan_is_deterministic_on_frozen_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root)
            first = gauntlet.plan_assurance(root, assurance_id, task_id=task_id)
            second = gauntlet.plan_assurance(root, assurance_id, task_id=task_id)
            self.assertEqual(first.plan_hash, second.plan_hash)
            self.assertEqual(
                first.minimality_certificate_hash,
                second.minimality_certificate_hash,
            )

    def test_cross_task_receipt_cannot_clear_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, proof_id, assurance_id = self._task(root, clear_proof=False)
            RuntimeStore(root).write_receipt(
                Receipt(
                    receipt_id="foreign-proof",
                    module="mind",
                    obligation_id=proof_id,
                    verdict=Verdict.CLEARED,
                    action="proof",
                    input_hash=digest("foreign"),
                    task_id="task-b",
                )
            )
            receipt = gauntlet.run_assurance(root, assurance_id, task_id=task_id)
            self.assertEqual(receipt.verdict, Verdict.ISSUE)
            self.assertIn("MISSING", receipt.notes or "")

    def test_non_assurance_authority_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            store = RuntimeStore(root)
            store.write_task(
                TaskState(
                    task_id="task-a",
                    goal_hash=digest("proof only"),
                    obligations=[
                        Obligation(
                            "obl-proof",
                            ObligationKind.PROOF,
                            "claim",
                            required_module="mind",
                        )
                    ],
                )
            )
            with self.assertRaises(gauntlet.GauntletAuthorityError):
                gauntlet.run_assurance(root, "obl-proof", task_id="task-a")

    def test_single_compact_receipt_reports_derived_not_token_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, _, assurance_id = self._task(root)
            before = len(list(RuntimeStore(root).receipts.glob("*.json")))
            receipt = gauntlet.run_assurance(root, assurance_id, task_id=task_id)
            after = len(list(RuntimeStore(root).receipts.glob("*.json")))
            self.assertEqual(after - before, 1)
            metrics = receipt.evidence[0].metadata["metrics"]
            self.assertEqual(metrics["cost_unit_status"], "DERIVED_NOT_TOKENS")
            self.assertEqual(metrics["semantic_tool_calls"], 0)
            self.assertEqual(metrics["efficacy_status"], "NOT_ESTABLISHED")


class GauntletMonitorHardeningTests(unittest.TestCase):
    def test_self_missing_provenance_is_unknown_not_cleared(self) -> None:
        events = [
            {
                "event_id": "evidence",
                "event_type": "evidence.attached",
                "metadata": {"producer": "mind", "verifier": "checker"},
            }
        ]
        verdict, _ = gauntlet.monitor_structured("self", events, [])
        self.assertEqual(verdict, Verdict.UNKNOWN)

    def test_derive_refuses_cross_task_receipt(self) -> None:
        events = [
            {
                "event_id": "claim",
                "event_type": "claim.adopted",
                "metadata": {"inherited": True, "derivation_obligation": "derive-1"},
            }
        ]
        receipts = [
            {
                "obligation_id": "derive-1",
                "module": "mind",
                "task_id": "task-b",
                "verdict": Verdict.CLEARED.value,
            }
        ]
        verdict, _ = gauntlet.monitor_structured(
            "derive",
            events,
            receipts,
            task_id="task-a",
        )
        self.assertEqual(verdict, Verdict.ISSUE)

    def test_fresh_snapshot_supersedes_historical_authority_change(self) -> None:
        events = [
            {"event_id": "old", "event_type": "authority.changed", "metadata": {}},
            {"event_id": "new", "event_type": "authority.snapshot", "metadata": {}},
        ]
        verdict, _ = gauntlet.monitor_structured("refresh", events, [])
        self.assertEqual(verdict, Verdict.CLEARED)

    def test_boundary_requires_content_bound_contract(self) -> None:
        events = [
            {
                "event_id": "handoff",
                "event_type": "handoff.started",
                "metadata": {"handoff_id": "h1"},
            },
            {
                "event_id": "contract",
                "event_type": "contract.bound",
                "metadata": {"handoff_id": "h1"},
            },
        ]
        verdict, _ = gauntlet.monitor_structured("boundary", events, [])
        self.assertEqual(verdict, Verdict.UNKNOWN)

    def test_oob_name_without_status_and_binding_is_unknown(self) -> None:
        events = [
            {"event_id": "release", "event_type": "release.attempted", "metadata": {}},
            {
                "event_id": "probe",
                "event_type": "coverage.probe",
                "metadata": {"failure_class": "parser-confusion"},
            },
        ]
        verdict, _ = gauntlet.monitor_structured("oob", events, [])
        self.assertEqual(verdict, Verdict.UNKNOWN)

    def test_explanation_without_hash_bound_artifact_is_unknown(self) -> None:
        events = [
            {
                "event_id": "explain",
                "event_type": "explanation.claim",
                "metadata": {"claim_id": "c1", "claim_hash": digest("claim")},
            },
            {
                "event_id": "artifact",
                "event_type": "artifact.claim",
                "metadata": {"claim_id": "c1"},
            },
        ]
        verdict, _ = gauntlet.monitor_structured("explain", events, [])
        self.assertEqual(verdict, Verdict.UNKNOWN)

    def test_costume_requires_actual_space_receipt_not_receipt_event(self) -> None:
        events = [
            {
                "event_id": "novel",
                "event_type": "novelty.claim",
                "metadata": {"discovery_obligation": "discover-1"},
            },
            {
                "event_id": "claim-only",
                "event_type": "receipt.written",
                "component": "space",
                "metadata": {
                    "obligation_id": "discover-1",
                    "verdict": Verdict.CLEARED.value,
                    "action": "source-assessment",
                },
            },
        ]
        verdict, _ = gauntlet.monitor_structured(
            "costume",
            events,
            [],
            task_id="task-a",
        )
        self.assertEqual(verdict, Verdict.ISSUE)


if __name__ == "__main__":
    unittest.main()
