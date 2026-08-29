from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import soul_session as sessions


class _FakeStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read_task(self, task_id: str):
        return {
            "task_id": task_id,
            "content_hash": "1" * 64,
            "obligations": [
                {"obligation_id": "obl-1"},
                {"obligation_id": "obl-2"},
            ],
        }

    def read_named_state(self, category: str, state_id: str):
        return None


class SoulSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = {
            "requested_task_id": "task-old",
            "resolved_task_id": "task-current",
            "supersession_chain": ["task-old", "task-current"],
            "task_snapshot_hash": "1" * 64,
            "obligation_set_hash": "2" * 64,
        }
        self.route = {
            "route_plan_id": "route-1",
            "route_plan_hash": "3" * 64,
            "selected_obligation_ids": ["obl-1", "obl-2"],
            "session_mode": "ROUTED_CONTROL",
        }
        self.patches = [
            patch.object(sessions, "RuntimeStore", _FakeStore),
            patch.object(
                sessions,
                "_task_binding",
                side_effect=lambda root, task_id: dict(self.task),
            ),
            patch.object(
                sessions,
                "_route_binding",
                side_effect=lambda root, task_id, route_id: dict(self.route),
            ),
            patch.object(sessions, "_snapshot", return_value=("4" * 64, "5" * 64)),
        ]
        for active in self.patches:
            active.start()

    def tearDown(self) -> None:
        for active in reversed(self.patches):
            active.stop()
        self.temporary.cleanup()

    def _open(self, **kwargs):
        return sessions.open_session(
            self.root,
            "task-old",
            route_plan_id="route-1",
            idempotency_key="same-request",
            **kwargs,
        )

    def test_open_is_idempotent_and_non_authorizing(self) -> None:
        first = self._open(metadata={"caller_note": "bounded"})
        second = self._open(metadata={"caller_note": "bounded"})
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(first["authority"], "CONTROL_ONLY")
        self.assertFalse(first["execution_authorized"])
        self.assertFalse(first["domain_evidence_authority"])
        self.assertFalse(first["release_authority"])
        revisions = list(sessions._dirs(self.root)["revisions"].rglob("*.json"))
        self.assertEqual(len(revisions), 1)

    def test_reserved_metadata_is_rejected_before_persistence(self) -> None:
        with self.assertRaises(ValueError):
            self._open(metadata={"nested": {"raw_prompt": "do not persist"}})
        self.assertFalse(sessions._dirs(self.root)["sessions"].exists())

    def test_checkpoint_is_append_only_and_generation_guarded(self) -> None:
        opened = self._open()
        updated, checkpoint = sessions.checkpoint_session(
            self.root,
            opened["session_id"],
            expected_generation=0,
            cursor={"batch_index": 0, "phase_code": "WAITING_RECEIPT"},
            observed_obligation_ids=["obl-1"],
            artifact_refs=[
                {
                    "artifact_id": "private-path-not-persisted",
                    "content_hash": "a" * 64,
                    "kind": "RESULT",
                }
            ],
            pause=True,
        )
        self.assertEqual(updated["generation"], 1)
        self.assertEqual(updated["status"], "PAUSED")
        self.assertEqual(checkpoint["progress_authority"], "HOST_HINT_ONLY")
        self.assertNotIn("private-path-not-persisted", json.dumps(checkpoint))
        with self.assertRaises(sessions.SoulSessionConflict):
            sessions.checkpoint_session(
                self.root,
                opened["session_id"],
                expected_generation=0,
            )
        checkpoint_files = list(sessions._dirs(self.root)["checkpoints"].glob("*.json"))
        self.assertEqual(len(checkpoint_files), 1)
        revisions = list(sessions._dirs(self.root)["revisions"].rglob("*.json"))
        self.assertEqual(len(revisions), 2)

    def test_resume_ready_is_manifest_only(self) -> None:
        opened = self._open()
        manifest = sessions.resume_session(
            self.root,
            opened["session_id"],
            expected_generation=0,
        )
        self.assertEqual(manifest["status"], "READY")
        self.assertFalse(manifest["resume_authorized"])
        self.assertFalse(manifest["execution_authorized"])
        self.assertFalse(manifest["domain_evidence_authority"])
        self.assertFalse(manifest["release_authority"])
        self.assertTrue(manifest["host_revalidation_required"])

    def test_evidence_drift_invalidates(self) -> None:
        opened = self._open()
        with patch.object(sessions, "_snapshot", return_value=("9" * 64, "5" * 64)):
            manifest = sessions.resume_session(
                self.root,
                opened["session_id"],
                expected_generation=0,
            )
        self.assertEqual(manifest["status"], "INVALIDATED")
        self.assertEqual(manifest["reason_code"], "STALE_EVIDENCE")
        persisted = json.loads(
            (
                sessions._dirs(self.root)["sessions"]
                / f"{opened['session_id']}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(persisted["status"], "INVALIDATED")
        self.assertEqual(persisted["generation"], 1)

    def test_task_drift_invalidates(self) -> None:
        opened = self._open()
        self.task["resolved_task_id"] = "task-newer"
        manifest = sessions.resume_session(self.root, opened["session_id"])
        self.assertEqual(manifest["status"], "INVALIDATED")
        self.assertEqual(manifest["reason_code"], "STALE_TASK")

    def test_tampered_checkpoint_fails_integrity(self) -> None:
        opened = self._open()
        updated, checkpoint = sessions.checkpoint_session(
            self.root,
            opened["session_id"],
            expected_generation=0,
        )
        path = (
            sessions._dirs(self.root)["checkpoints"]
            / f"{checkpoint['checkpoint_id']}.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["cursor"] = {"batch_index": 99}
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(sessions.SoulSessionIntegrityError):
            sessions.resume_session(
                self.root,
                opened["session_id"],
                expected_generation=updated["generation"],
            )

    def test_checkpoint_limit_preserves_history(self) -> None:
        opened = sessions.open_session(
            self.root,
            "task-old",
            route_plan_id="route-1",
            max_checkpoints=1,
        )
        updated, _ = sessions.checkpoint_session(
            self.root,
            opened["session_id"],
            expected_generation=0,
        )
        with self.assertRaises(sessions.SoulSessionConflict):
            sessions.checkpoint_session(
                self.root,
                opened["session_id"],
                expected_generation=updated["generation"],
            )
        checkpoints = list(sessions._dirs(self.root)["checkpoints"].glob("*.json"))
        self.assertEqual(len(checkpoints), 1)

    def test_close_never_claims_release(self) -> None:
        opened = self._open()
        closed = sessions.close_session(
            self.root,
            opened["session_id"],
            expected_generation=0,
            reason_code="HOST_FINISHED",
        )
        self.assertEqual(closed["status"], "CLOSED")
        self.assertFalse(closed["release_authority"])
        manifest = sessions.resume_session(self.root, opened["session_id"])
        self.assertEqual(manifest["status"], "CLOSED")
        self.assertFalse(manifest["resume_authorized"])


if __name__ == "__main__":
    unittest.main()
