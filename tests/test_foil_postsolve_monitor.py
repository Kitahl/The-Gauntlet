from __future__ import annotations

import hashlib
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_postsolve_monitor import (  # noqa: E402
    PostSolveAction,
    PostSolveCursor,
    PostSolveEvent,
    PostSolveMonitorPolicy,
    evaluate_postsolve_event,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def event(sequence: int, payload: str | None = None, kind: str = "answer.sealed") -> PostSolveEvent:
    return PostSolveEvent(
        event_id=f"event-{sequence}",
        event_type=kind,
        sequence=sequence,
        task_digest=d("task"),
        answer_digest=d("answer"),
        payload_digest=d(payload or f"payload-{sequence}"),
    )


class PostSolveMonitorTests(unittest.TestCase):
    def test_disabled_is_zero_work_and_does_not_advance_cursor(self):
        cursor = PostSolveCursor()
        decision = evaluate_postsolve_event(event(1), PostSolveMonitorPolicy(), cursor)
        self.assertEqual(decision.action, PostSolveAction.STAND_DOWN)
        self.assertEqual(decision.cursor, cursor)
        self.assertEqual(
            (decision.model_calls, decision.tool_calls, decision.network_calls, decision.tokens),
            (0, 0, 0, 0),
        )
        self.assertFalse(decision.answer_mutated)

    def test_observe_never_triggers_scan(self):
        decision = evaluate_postsolve_event(
            event(1), PostSolveMonitorPolicy(enabled=True, observe_only=True)
        )
        self.assertEqual(decision.action, PostSolveAction.OBSERVE)
        self.assertEqual(decision.cursor.scan_triggers, 0)

    def test_smart_trigger_is_bounded_deduplicated_and_cooled_down(self):
        policy = PostSolveMonitorPolicy(
            enabled=True,
            observe_only=False,
            max_scan_triggers=2,
            cooldown_events=1,
        )
        first = evaluate_postsolve_event(event(1), policy)
        cooldown = evaluate_postsolve_event(event(2), policy, first.cursor)
        second = evaluate_postsolve_event(event(3), policy, cooldown.cursor)
        exhausted = evaluate_postsolve_event(event(5), policy, second.cursor)
        duplicate = evaluate_postsolve_event(
            event(6, payload="payload-1"), policy, exhausted.cursor
        )
        self.assertEqual(first.action, PostSolveAction.SCAN)
        self.assertEqual(cooldown.reason, "cooldown_active")
        self.assertEqual(second.action, PostSolveAction.SCAN)
        self.assertEqual(exhausted.reason, "scan_budget_exhausted")
        self.assertEqual(duplicate.reason, "duplicate_payload")

    def test_unsubscribed_and_stale_events_fail_closed(self):
        policy = PostSolveMonitorPolicy(enabled=True, observe_only=False, max_scan_triggers=1)
        ignored = evaluate_postsolve_event(event(1, kind="task.started"), policy)
        stale = evaluate_postsolve_event(event(1), policy, ignored.cursor)
        self.assertEqual(ignored.reason, "event_not_subscribed")
        self.assertEqual(stale.action, PostSolveAction.UNKNOWN)

    def test_no_nonzero_token_budget_or_hidden_work_is_constructible(self):
        with self.assertRaises(ValueError):
            PostSolveMonitorPolicy(token_budget=1)
        decision_params = inspect.signature(
            type(evaluate_postsolve_event(event(1), PostSolveMonitorPolicy())).__init__
        ).parameters
        self.assertNotIn("active_context", decision_params)
        source = (ROOT / "tools" / "foil_postsolve_monitor.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "import requests",
            "import subprocess",
            "import socket",
            "while true",
            "threading",
            "asyncio",
        ):
            self.assertNotIn(forbidden, source)

    def test_seen_payload_window_is_strictly_bounded(self):
        policy = PostSolveMonitorPolicy(
            enabled=True,
            observe_only=True,
            max_seen_payloads=8,
        )
        cursor = PostSolveCursor()
        for sequence in range(1, 101):
            cursor = evaluate_postsolve_event(event(sequence), policy, cursor).cursor
        self.assertEqual(len(cursor.seen_payload_digests), 8)
        self.assertEqual(cursor.seen_payload_digests[-1], d("payload-100"))


if __name__ == "__main__":
    unittest.main()
