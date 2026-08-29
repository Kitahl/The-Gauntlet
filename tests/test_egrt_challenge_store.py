from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from _challenge_helpers import init_root, request  # noqa: E402
from egrt_challenge import propose_challenge, record_resolution  # noqa: E402
from egrt_challenge_types import (  # noqa: E402
    ChallengeResolution,
    ChallengeState,
    ResolutionOutcome,
)
from egrt_store import RuntimeStore, verify_content_hash  # noqa: E402
from egrt_types import Receipt, Verdict, digest  # noqa: E402


class ChallengeStoreTests(unittest.TestCase):
    def test_challenge_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            path = propose_challenge(root, request())
            body = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(verify_content_hash(body))
            body["hypothesis"] = "tampered"
            path.write_text(json.dumps(body), encoding="utf-8")
            self.assertIsNone(RuntimeStore(root).read_challenge("challenge-1"))

    def test_challenge_state_machine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            propose_challenge(root, request())
            with self.assertRaises(ValueError):
                propose_challenge(root, request())
            store = RuntimeStore(root)
            store.update_challenge_state("challenge-1", "DISMISSED_NOT_APPLICABLE", reason="not applicable")
            with self.assertRaises(ValueError):
                store.update_challenge_state("challenge-1", "SELECTED")

    def test_challenge_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            challenge = request()
            propose_challenge(root, challenge)
            store = RuntimeStore(root)
            receipt = Receipt(
                receipt_id="receipt-1",
                module="mind",
                obligation_id=challenge.obligation_id,
                verdict=Verdict.CLEARED,
                action="exact-check",
                input_hash=digest({"x": 1}),
                task_id=challenge.task_id,
            )
            store.write_receipt(receipt)
            stored_receipt = store.read_receipt(receipt.receipt_id)
            resolution = ChallengeResolution(
                resolution_id="resolution-1",
                challenge_id=challenge.challenge_id,
                state=ChallengeState.RESOLVED,
                outcome=ResolutionOutcome.SUPPORTS_BASE,
                verifier_receipt_id=receipt.receipt_id,
                verifier_module="mind",
                evidence_hash=stored_receipt["content_hash"],
                candidate_hash=challenge.candidate_hash,
                scope_hash=challenge.scope_hash,
                obligation_set_hash=challenge.obligation_set_hash,
                resolver="mind",
            )
            path = record_resolution(root, resolution)
            self.assertTrue(verify_content_hash(json.loads(path.read_text(encoding="utf-8"))))
            self.assertEqual(store.read_challenge(challenge.challenge_id)["state"], "RESOLVED")
            events = [event for event in store.iter_events(challenge.task_id) if event["event_type"] == "challenge.resolved"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["metadata"]["linked_receipt_id"], receipt.receipt_id)

    def test_wrong_module_receipt_cannot_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            challenge = request()
            propose_challenge(root, challenge)
            store = RuntimeStore(root)
            store.write_receipt(Receipt(
                receipt_id="receipt-1",
                module="space",
                obligation_id=challenge.obligation_id,
                verdict=Verdict.CLEARED,
                action="source-check",
                input_hash="x",
                task_id=challenge.task_id,
            ))
            resolution = ChallengeResolution(
                resolution_id="resolution-1",
                challenge_id=challenge.challenge_id,
                state=ChallengeState.RESOLVED,
                outcome=ResolutionOutcome.SUPPORTS_BASE,
                verifier_receipt_id="receipt-1",
                verifier_module="mind",
                evidence_hash=None,
                candidate_hash=challenge.candidate_hash,
                scope_hash=challenge.scope_hash,
                obligation_set_hash=challenge.obligation_set_hash,
                resolver="mind",
            )
            with self.assertRaises(ValueError):
                record_resolution(root, resolution)


if __name__ == "__main__":
    unittest.main()
