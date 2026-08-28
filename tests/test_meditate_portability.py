from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import meditate_runtime as meditate  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import Obligation, ObligationKind, RuntimeEvent, TaskState, digest  # noqa: E402


def init_root(path: Path) -> tuple[RuntimeStore, TaskState]:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state"}),
        encoding="utf-8",
    )
    obligation = Obligation(
        obligation_id="obl-preflight",
        kind=ObligationKind.PREFLIGHT,
        claim="decide",
        required_module="meditate",
    )
    task = TaskState(
        task_id="task-preflight",
        goal_hash=digest("goal"),
        obligations=[obligation],
    )
    store = RuntimeStore(path)
    store.write_task(task)
    return store, task


def authority_event(
    *,
    event_id: str,
    event_type: str,
    task_id: str,
    timestamp: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        component="test",
        task_id=task_id,
        payload_hash=digest({"event_type": event_type, "timestamp": timestamp}),
        timestamp=timestamp,
    )


class MeditateAuthorityOrderingTests(unittest.TestCase):
    def test_equal_timestamp_change_and_snapshot_fail_closed_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, task = init_root(root)
            stamp = "2026-08-28T12:00:00+00:00"
            # Event IDs deliberately sort opposite to semantic creation order. The
            # verdict must depend on timestamps, not filename or UUID ordering.
            store.append_event(
                authority_event(
                    event_id="evt-z-snapshot",
                    event_type="authority.snapshot",
                    task_id=task.task_id,
                    timestamp=stamp,
                )
            )
            store.append_event(
                authority_event(
                    event_id="evt-a-changed",
                    event_type="authority.changed",
                    task_id=task.task_id,
                    timestamp=stamp,
                )
            )
            triggers = meditate.derive_triggers(root, task.task_id)
            self.assertTrue(triggers.stale_authority)

    def test_strictly_newer_snapshot_clears_stale_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, task = init_root(root)
            store.append_event(
                authority_event(
                    event_id="evt-changed",
                    event_type="authority.changed",
                    task_id=task.task_id,
                    timestamp="2026-08-28T12:00:00+00:00",
                )
            )
            store.append_event(
                authority_event(
                    event_id="evt-snapshot",
                    event_type="authority.snapshot",
                    task_id=task.task_id,
                    timestamp="2026-08-28T12:00:01+00:00",
                )
            )
            triggers = meditate.derive_triggers(root, task.task_id)
            self.assertFalse(triggers.stale_authority)


if __name__ == "__main__":
    unittest.main()
