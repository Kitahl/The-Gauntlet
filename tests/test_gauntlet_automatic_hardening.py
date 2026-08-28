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
    EvidenceClass,
    EvidenceRef,
    Obligation,
    ObligationKind,
    Receipt,
    RuntimeEvent,
    TaskState,
    Verdict,
    digest,
)


def init_root(root: Path) -> None:
    (root / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def append_event(
    store: RuntimeStore,
    task_id: str,
    event_id: str,
    event_type: str,
    *,
    metadata: dict | None = None,
) -> None:
    store.append_event(
        RuntimeEvent(
            event_id=event_id,
            event_type=event_type,
            component="test",
            task_id=task_id,
            payload_hash=digest({"event_id": event_id, "event_type": event_type}),
            timestamp="2026-08-28T00:00:00+00:00",
            metadata=metadata or {},
        )
    )


def make_release_task(root: Path) -> tuple[str, Obligation, Obligation]:
    task_id = "task-release"
    proof = Obligation(
        "obl-proof",
        ObligationKind.PROOF,
        "Prove the release claim",
        required_module="mind",
    )
    assurance = Obligation(
        "obl-assurance",
        ObligationKind.ASSURANCE,
        "Audit release",
        required_module="gauntlet",
        metadata={"depends_on": [proof.obligation_id]},
    )
    RuntimeStore(root).write_task(
        TaskState(
            task_id=task_id,
            goal_hash=digest("release"),
            obligations=[proof, assurance],
        )
    )
    return task_id, proof, assurance


def release_events(store: RuntimeStore, task_id: str) -> None:
    append_event(store, task_id, "release", "release.attempted")
    append_event(store, task_id, "authority", "authority.snapshot")
    append_event(
        store,
        task_id,
        "probe",
        "coverage.probe",
        metadata={
            "failure_class": "parser",
            "status": "VALID",
            "artifact_hash": digest("artifact"),
            "scope_hash": digest("scope"),
            "verifier": "independent-probe",
        },
    )


def proof_receipt(
    task_id: str,
    proof: Obligation,
    receipt_id: str,
    *,
    verdict: Verdict = Verdict.CLEARED,
    with_evidence: bool = True,
) -> Receipt:
    evidence = ()
    if with_evidence:
        evidence = (
            EvidenceRef(
                evidence_class=EvidenceClass.OBSERVED,
                verifier=f"verifier-{receipt_id}",
                provenance_group=f"verifier-provenance-{receipt_id}",
                metadata={
                    "producer_provenance": f"producer-provenance-{receipt_id}",
                    "verifier_provenance": f"verifier-provenance-{receipt_id}",
                },
            ),
        )
    return Receipt(
        receipt_id=receipt_id,
        module="mind",
        obligation_id=proof.obligation_id,
        verdict=verdict,
        action="proof",
        input_hash=digest(receipt_id),
        evidence=evidence,
        task_id=task_id,
    )


class AutomaticGauntletHardeningTests(unittest.TestCase):
    def test_release_without_domain_evidence_runs_self_and_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, proof, assurance = make_release_task(root)
            store = RuntimeStore(root)
            store.write_receipt(
                proof_receipt(
                    task_id,
                    proof,
                    "receipt-without-evidence",
                    with_evidence=False,
                )
            )
            release_events(store, task_id)

            receipt = automatic.run_automatic_assurance(
                root,
                assurance.obligation_id,
                task_id=task_id,
            )

            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            metadata = receipt.evidence[0].metadata
            self.assertIn("self", metadata["executed_operations"])
            self.assertTrue(
                any(
                    item.startswith("self:current load-bearing receipt")
                    for item in receipt.unresolved
                )
            )

    def test_state_event_must_bind_the_exact_receipt_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, proof, assurance = make_release_task(root)
            store = RuntimeStore(root)
            store.write_receipt(proof_receipt(task_id, proof, "receipt-bound"))
            release_events(store, task_id)

            state_event = next(
                row
                for row in store.iter_events(task_id)
                if row.get("event_type") == "obligation.state"
            )
            event_path = store.events / f"{state_event['event_id']}.json"
            planted = store._read(event_path, require_integrity=False)
            self.assertIsNotNone(planted)
            planted.pop("content_hash", None)
            planted["payload_hash"] = digest("different-receipt")
            planted["content_hash"] = digest(planted)
            store._write(event_path, planted)

            receipt = automatic.run_automatic_assurance(
                root,
                assurance.obligation_id,
                task_id=task_id,
            )
            metadata = receipt.evidence[0].metadata
            self.assertEqual(
                metadata["runtime_event_coverage_status"],
                "UNKNOWN_RUNTIME_EVENT_CHAIN",
            )
            self.assertTrue(
                any("obligation-state-event-missing-or-unbound" in gap for gap in receipt.unresolved)
            )

    def test_one_evidence_event_cannot_cover_two_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task_id, proof, assurance = make_release_task(root)
            store = RuntimeStore(root)
            store.write_receipt(proof_receipt(task_id, proof, "receipt-one"))
            store.write_receipt(proof_receipt(task_id, proof, "receipt-two"))
            release_events(store, task_id)

            evidence_paths = []
            for path in store.events.glob("*.json"):
                row = store._read(path)
                if row and row.get("event_type") == "evidence.attached":
                    evidence_paths.append(path)
            self.assertEqual(len(evidence_paths), 2)
            evidence_paths[0].unlink()

            receipt = automatic.run_automatic_assurance(
                root,
                assurance.obligation_id,
                task_id=task_id,
            )
            metadata = receipt.evidence[0].metadata
            self.assertEqual(
                metadata["runtime_event_coverage_status"],
                "UNKNOWN_RUNTIME_EVENT_CHAIN",
            )
            self.assertTrue(
                any("evidence-event-missing-or-unbound" in gap for gap in receipt.unresolved)
            )

    def test_monotonic_sequence_outranks_future_wall_clock_text(self) -> None:
        older = {
            "receipt_id": "older",
            "seq": 1,
            "stored_at": "2099-01-01T00:00:00+00:00",
        }
        newer = {
            "receipt_id": "newer",
            "seq": 2,
            "stored_at": "2000-01-01T00:00:00+00:00",
        }
        ordered = automatic._ordered_receipts([newer, older])
        self.assertEqual([row["receipt_id"] for row in ordered], ["older", "newer"])


if __name__ == "__main__":
    unittest.main()
