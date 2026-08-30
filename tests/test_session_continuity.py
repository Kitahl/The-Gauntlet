"""TOKEN-010 task-bound Hermes session continuity contracts."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from gauntlet_host.ipc import (
    RuntimeRequest,
    WorkerOperation,
    decode_request,
    encode_request,
)
from gauntlet_host.session_binding import (
    SessionTurnLockTimeout,
    derive_session_id,
    exclusive_session_turn_lock,
    session_turn_lock_path,
)


class SessionBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.key = self.root / ".hmac-key"
        self.key.write_bytes(bytes(range(32)))

    def test_binding_is_stable_private_and_task_isolated(self) -> None:
        first = derive_session_id("task-private-alpha", self.key)
        restarted = derive_session_id("task-private-alpha", self.key)
        other = derive_session_id("task-private-beta", self.key)

        self.assertEqual(first, restarted)
        self.assertNotEqual(first, other)
        self.assertTrue(first.startswith("gauntlet-"))
        self.assertNotIn("task-private-alpha", first)

    def test_ipc_round_trip_carries_explicit_session_binding(self) -> None:
        request = RuntimeRequest(
            request_id="request-1",
            task_id="task-1",
            operation=WorkerOperation.RUN,
            session_id=derive_session_id("task-1", self.key),
            prompt="continue",
        )
        self.assertEqual(decode_request(encode_request(request)), request)

    def test_kernel_lock_serializes_same_session_and_releases(self) -> None:
        session_id = derive_session_id("task-lock", self.key)
        lock = session_turn_lock_path(self.root / "locks", session_id)
        entered = threading.Event()
        release = threading.Event()

        def holder() -> None:
            with exclusive_session_turn_lock(lock, timeout=2.0):
                entered.set()
                release.wait(timeout=2.0)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(timeout=2.0))
        with self.assertRaises(SessionTurnLockTimeout):
            with exclusive_session_turn_lock(lock, timeout=0.0):
                pass
        release.set()
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        with exclusive_session_turn_lock(lock, timeout=0.0):
            pass


if __name__ == "__main__":
    unittest.main()
