"""D6, D7 - the frozen-evaluation task/budget ledger.

The guard is an accounting ledger, not a security boundary; these tests pin the
accounting properties it does claim. The concurrency and lock-release tests are
the ones that actually exercise the platform lock, which is fcntl.flock on POSIX
and msvcrt.locking on Windows.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_task_guard as tg  # noqa: E402


class TaskGuardTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.state = self.dir / "run.json"
        tg._atomic_save(self.state, tg.start_state(
            task_id="t", prompt="p", condition="C", budgets={"q": 3},
            dataset_revision="ds@abc", as_of="2026-08-22"))

    def _spend(self, **kw):
        with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                  operation="q", **kw):
            pass

    def test_budget_fails_closed(self):
        for _ in range(3):
            self._spend()
        with self.assertRaises(tg.BudgetExhausted):
            self._spend()

    def test_failed_operation_does_not_consume_budget(self):
        """A transport failure must refund the hold rather than burn a query."""
        with self.assertRaises(RuntimeError):
            with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                      operation="q"):
                raise RuntimeError("transport failure")
        self.assertEqual(json.loads(self.state.read_text())["used"]["q"], 0)

    def test_spend_on_error_charges_the_attempt(self):
        """Positive control for the refund: the same failure minus the refund."""
        with self.assertRaises(RuntimeError):
            with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                      operation="q", spend_on_error=True):
                raise RuntimeError("transport failure")
        self.assertEqual(json.loads(self.state.read_text())["used"]["q"], 1)

    def test_binding_mismatch_is_rejected(self):
        for kwargs in ({"task_id": "other"}, {"condition": "D"}, {"prompt": "different"}):
            args = {"task_id": "t", "prompt": "p", "condition": "C", "operation": "q", **kwargs}
            with self.assertRaises(tg.BindingMismatch):
                with tg.guarded_operation(self.state, **args):
                    pass

    def test_prompt_sha256_is_an_equivalent_binding_path(self):
        """The hook process holds the digest, never the prompt text."""
        digest = tg.prompt_hash("p")
        with tg.guarded_operation(self.state, task_id="t", prompt_sha256=digest,
                                  condition="C", operation="q"):
            pass
        self.assertEqual(json.loads(self.state.read_text())["used"]["q"], 1)
        with self.assertRaises(tg.BindingMismatch):
            with tg.guarded_operation(self.state, task_id="t", condition="C", operation="q",
                                      prompt_sha256="0" * 64):
                pass

    def test_neither_prompt_nor_digest_is_a_binding_failure_not_a_pass(self):
        with self.assertRaises(tg.BindingMismatch):
            with tg.guarded_operation(self.state, task_id="t", condition="C", operation="q"):
                pass

    def test_unbudgeted_operation_is_refused(self):
        with self.assertRaises(tg.BindingMismatch):
            with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                      operation="not_budgeted"):
                pass

    def test_stale_lock_file_does_not_brick_the_run(self):
        """v1 deadlocked permanently on a lock left by a dead process.

        The lock file's *content* now carries no meaning at all - the lock is a
        kernel byte-range lock on the handle - so garbage in the file cannot
        block anything. Writing garbage is the point of the test.
        """
        lock = self.state.with_suffix(self.state.suffix + ".lock")
        lock.write_text("pid=999999 time=0 garbage\n", encoding="utf-8")
        self._spend()
        self.assertEqual(json.loads(self.state.read_text())["used"]["q"], 1)
        self.assertTrue(lock.is_file(), "the lock file is persistent, never unlinked")

    def test_event_chain_detects_edits_and_deletions(self):
        self._spend()
        state = json.loads(self.state.read_text())
        self.assertTrue(tg.attest(state)["valid"])
        edited = json.loads(self.state.read_text())
        edited["events"][1]["operation"] = "elsewhere"
        self.assertFalse(tg.attest(edited)["valid"])
        deleted = json.loads(self.state.read_text())
        del deleted["events"][1]
        self.assertFalse(tg.attest(deleted)["valid"])

    def test_attest_records_the_tip_of_the_chain_in_the_state(self):
        self._spend()
        state = json.loads(self.state.read_text())
        self.assertEqual(state["event_count"], len(state["events"]))
        self.assertEqual(state["head"], state["events"][-1]["digest"])
        receipt = tg.attest(state)
        self.assertTrue(receipt["valid"], receipt)
        self.assertEqual(receipt["head"], state["head"])
        self.assertEqual(receipt["event_count"], state["event_count"])

    def test_untouched_state_attests_valid(self):
        """Positive control for every truncation case below."""
        for _ in range(3):
            self._spend()
        self.assertTrue(tg.attest(json.loads(self.state.read_text()))["valid"])

    def test_tail_truncation_is_detected(self):
        """C1 - the chain alone cannot see events removed from its end.

        Deleting the last N events leaves every remaining digest correct, so v2
        attested valid while `used` still reported the full spend: a receipt
        showing three searches with the evidence of two.
        """
        for _ in range(3):
            self._spend()
        for cut in (1, 3):
            state = json.loads(self.state.read_text())
            before = dict(state["used"])
            del state["events"][-cut:]
            receipt = tg.attest(state)
            self.assertFalse(receipt["valid"], f"cut={cut}: {receipt}")
            self.assertIn("truncation", receipt["reason"], receipt)
            self.assertEqual(state["used"], before,
                             "the attack leaves `used` intact; that is what makes it one")

    def test_tail_truncation_with_a_repaired_count_and_head_is_still_detected(self):
        """The determined version: trim, then fix the two tip fields to match.

        The chain is consistent and the tip agrees with it, so only the
        `used` replay is left to catch it - which is why the replay exists.
        """
        for _ in range(3):
            self._spend()
        state = json.loads(self.state.read_text())
        del state["events"][-3:]
        state["event_count"] = len(state["events"])
        state["head"] = state["events"][-1]["digest"]
        receipt = tg.attest(state)
        self.assertFalse(receipt["valid"], receipt)
        self.assertEqual(receipt["reason"], "used does not match replay")

    def test_editing_used_without_touching_the_events_is_detected(self):
        for _ in range(2):
            self._spend()
        state = json.loads(self.state.read_text())
        state["used"]["q"] = 0
        receipt = tg.attest(state)
        self.assertFalse(receipt["valid"], receipt)
        self.assertEqual(receipt["reason"], "used does not match replay")
        self.assertEqual(receipt["replayed_used"], {"q": 2})

    def test_removing_the_tip_fields_is_not_a_way_around_the_check(self):
        self._spend()
        for field in ("event_count", "head"):
            state = json.loads(self.state.read_text())
            del state[field]
            receipt = tg.attest(state)
            self.assertFalse(receipt["valid"], field)
            self.assertIn(field, receipt["reason"])

    def test_replay_ignores_events_that_do_not_move_the_counter(self):
        """A refusal and a broker journal row both carry `operation`.

        Counting either would make a healthy run fail its own replay.
        """
        for _ in range(3):
            self._spend()
        with tg.exclusive_state_lock(self.state):
            state = tg.load(self.state)
            tg._append_event(state, {"time": tg.now(), "kind": "BLOCKED_BUDGET",
                                     "operation": "q", "used": 3, "limit": 3})
            tg._append_event(state, {"time": tg.now(), "kind": "BROKER", "operation": "q",
                                     "decision": "deny", "tool": "WebSearch"})
            tg._atomic_save(self.state, state)
        state = json.loads(self.state.read_text())
        self.assertEqual(tg.replay_used(state["events"]), {"q": 3})
        self.assertTrue(tg.attest(state)["valid"])

    def test_a_released_reservation_replays_to_a_refund(self):
        with self.assertRaises(RuntimeError):
            with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                      operation="q"):
                raise RuntimeError("transport failure")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["used"]["q"], 0)
        self.assertEqual(tg.replay_used(state["events"]), {"q": 0})
        self.assertTrue(tg.attest(state)["valid"])

    def test_receipt_fields_required_by_the_prescoring_checklist_exist(self):
        state = json.loads(self.state.read_text())
        for field in ("profile_payload_sha256", "dataset_revision", "as_of", "decoding",
                      "prompt_sha256"):
            self.assertIn(field, state)

    def test_concurrent_workers_cannot_overspend(self):
        """12 threads against a budget of 5 grant exactly 5.

        This is the test the O_EXCL fallback failed on Windows: it granted 2 and
        raised LockTimeout for the rest, because a sentinel file held by a live
        process is not a lock and its liveness heuristic refused real contenders.
        """
        state = self.dir / "c.json"
        tg._atomic_save(state, tg.start_state(task_id="t", prompt="p", condition="C",
                                              budgets={"q": 5}))
        granted, refused, errors = [], [], []

        def worker():
            try:
                with tg.guarded_operation(state, task_id="t", prompt="p", condition="C",
                                          operation="q"):
                    time.sleep(0.002)
                granted.append(1)
            except tg.BudgetExhausted:
                refused.append(1)
            except BaseException as exc:  # noqa: BLE001 - surfaced, never swallowed
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(granted), 5)
        self.assertEqual(len(refused), 7)
        final = json.loads(state.read_text())
        self.assertEqual(final["used"]["q"], 5)
        self.assertTrue(tg.attest(final)["valid"])


HOLDER_SOURCE = textwrap.dedent(
    """
    import sys, time
    sys.path.insert(0, sys.argv[1])
    from pathlib import Path
    import foil_task_guard as tg
    with tg.exclusive_state_lock(Path(sys.argv[2])):
        print("LOCKED", flush=True)
        time.sleep(120)
    """
)


class LockReleaseTests(unittest.TestCase):
    """A killed holder must not leave the run permanently unusable."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.state = self.dir / "run.json"
        tg._atomic_save(self.state, tg.start_state(
            task_id="t", prompt="p", condition="C", budgets={"q": 1}))

    def test_lock_is_really_held_and_is_released_when_the_holder_dies(self):
        holder = subprocess.Popen(
            [sys.executable, "-c", HOLDER_SOURCE, str(ROOT / "tools"), str(self.state)],
            stdout=subprocess.PIPE, text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "LOCKED")
            # Positive control: while the holder lives, acquisition must fail.
            # Without this, "acquired after kill" would prove nothing.
            started = time.monotonic()
            with self.assertRaises(tg.LockTimeout):
                with tg.exclusive_state_lock(self.state, timeout=0.0):
                    pass
            # The caller's deadline must actually be honoured. This branch once
            # dropped `timeout` on the floor and always waited the module
            # default, so `timeout=0.0` blocked for the full 30 s.
            self.assertLess(time.monotonic() - started, 5.0,
                            "exclusive_state_lock ignored the caller's timeout")
        finally:
            holder.kill()
            holder.wait(timeout=30)
            if holder.stdout is not None:
                holder.stdout.close()
        # The kernel drops a byte-range lock when the handle closes, including on
        # SIGKILL/TerminateProcess, so no cleanup or TTL heuristic is needed.
        with tg.exclusive_state_lock(self.state, timeout=30.0):
            pass
        with tg.guarded_operation(self.state, task_id="t", prompt="p", condition="C",
                                  operation="q"):
            pass
        self.assertEqual(json.loads(self.state.read_text())["used"]["q"], 1)


if __name__ == "__main__":
    unittest.main()
