"""Regression gate tests for the P0 typed-runtime repairs.

Each test's docstring records whether it FAILS against the pre-fix code (and the
source line it catches) or is a GUARD for an existing invariant that the fixes must
not regress. Grouped by the defect it exercises.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import council_runtime as council  # noqa: E402
import egrt_hook  # noqa: E402
import egrt_store  # noqa: E402
import foil_runtime_bridge as bridge  # noqa: E402
import gauntlet_runtime as gauntlet  # noqa: E402
import meditate_runtime as meditate  # noqa: E402
import mind_runtime as mind  # noqa: E402
import power_runtime as power  # noqa: E402
import reality_runtime as reality  # noqa: E402
import soul_runtime as soul  # noqa: E402
import space_runtime as space  # noqa: E402
import time_runtime as time_rt  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import ObligationKind, Receipt, Verdict  # noqa: E402


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def _write_receipt(root: Path, obligation, verdict: Verdict, *, task_id: str | None, receipt_id: str | None = None) -> str:
    store = RuntimeStore(root)
    receipt = Receipt(
        receipt_id=receipt_id or f"rcpt-{uuid.uuid4().hex[:8]}",
        module=obligation.required_module,
        obligation_id=obligation.obligation_id,
        verdict=verdict,
        action="test-receipt",
        input_hash="ih",
        task_id=task_id,
    )
    store.write_receipt(receipt)
    return receipt.receipt_id


# ---------------------------------------------------------------------------
# P0-1 / P0-2  store ordering, task integrity, receipt task-id filtering
# ---------------------------------------------------------------------------
class StoreAndGateTests(unittest.TestCase):
    def test_stored_at_tie_newer_receipt_wins(self) -> None:
        """FIX (egrt_store.receipts_for sort + seq): with equal stored_at the last
        WRITTEN receipt must be authoritative. Pre-fix ordered by stored_at string with
        a stable sort, so the glob/UUID order decided ties and an older CLEARED could
        beat a newer ISSUE (egrt_store.py old line 201)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            obl = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "c")
            with patch.object(egrt_store, "utcnow", lambda: "2026-08-23T00:00:00+00:00"):
                # CLEARED written first but with a lexicographically LARGER id; ISSUE
                # written second with a smaller id. Only the seq counter recovers the
                # true write order.
                _write_receipt(root, obl, Verdict.CLEARED, task_id=task.task_id, receipt_id="rcpt-zzzz")
                _write_receipt(root, obl, Verdict.ISSUE, task_id=task.task_id, receipt_id="rcpt-aaaa")
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.ISSUE)
            ordered = RuntimeStore(root).receipts_for(obl.obligation_id)
            self.assertEqual(ordered[-1]["verdict"], Verdict.ISSUE.value)

    def test_tampered_task_file_makes_gate_unknown(self) -> None:
        """FIX (egrt_store.read_task require_integrity): a task whose stored body no
        longer matches its content_hash must not be trusted. Pre-fix read_task did no
        integrity check, so a tampered task still cleared (egrt_store.py read_task)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            obl = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "c")
            _write_receipt(root, obl, Verdict.CLEARED, task_id=task.task_id)
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.CLEARED)
            path = RuntimeStore(root).tasks / f"{task.task_id}.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            body["goal_hash"] = "tampered"  # content_hash now stale
            path.write_text(json.dumps(body), encoding="utf-8")
            verdict, detail = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertEqual(detail.get("reason"), "task-not-found")

    def test_receipt_for_other_task_is_ignored(self) -> None:
        """FIX (soul.release_gate task_id filter): a receipt naming a different task
        must not clear this task's obligation. Pre-fix the filter ignored task_id
        (soul_runtime.py old line 90)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            obl = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "c")
            _write_receipt(root, obl, Verdict.CLEARED, task_id="task-someone-else")
            verdict, detail = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            self.assertEqual(detail["obligations"][0]["reason"], "missing-receipt")

    def test_unavailable_outranks_unknown_and_is_not_masked(self) -> None:
        """FIX (soul.release_gate severity order): UNAVAILABLE must outrank UNKNOWN and
        CLEARED. Pre-fix the elif chain let a later UNKNOWN mask an UNAVAILABLE, and
        UNAVAILABLE only demoted CLEARED (soul_runtime.py old aggregation)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            unavail = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "c1")
            unknown = soul.add_obligation(root, task.task_id, ObligationKind.EVALUATION, "c2")
            _write_receipt(root, unavail, Verdict.UNAVAILABLE, task_id=task.task_id)
            _write_receipt(root, unknown, Verdict.UNKNOWN, task_id=task.task_id)
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.UNAVAILABLE)

    def test_concurrent_add_obligation_persists_all(self) -> None:
        """FIX (P0-8 file_lock read-modify-write): 12 concurrent add_obligation calls
        must all persist. Pre-fix each thread wrote a stale copy and updates were lost
        (soul_runtime.add_obligation had no lock; private_io had no advisory lock)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            errors: list[str] = []

            def worker(i: int) -> None:
                try:
                    soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, f"claim-{i}")
                except Exception as exc:  # noqa: BLE001 - collected and asserted below
                    errors.append(repr(exc))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            raw = RuntimeStore(root).read_task(task.task_id, require_integrity=True)
            self.assertIsNotNone(raw)
            claims = sorted(o["claim"] for o in raw["obligations"])
            self.assertEqual(claims, sorted(f"claim-{i}" for i in range(12)))

    def test_cleared_plus_unavailable_demotes_to_unavailable(self) -> None:
        """GUARD (aggregation): a lone UNAVAILABLE beside a CLEARED yields UNAVAILABLE."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            cleared = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "c1")
            unavail = soul.add_obligation(root, task.task_id, ObligationKind.EVALUATION, "c2")
            _write_receipt(root, cleared, Verdict.CLEARED, task_id=task.task_id)
            _write_receipt(root, unavail, Verdict.UNAVAILABLE, task_id=task.task_id)
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.UNAVAILABLE)


# ---------------------------------------------------------------------------
# P0-3  monitor "trigger absent" -> UNKNOWN(not-applicable)
# ---------------------------------------------------------------------------
class MonitorAbsenceTests(unittest.TestCase):
    def test_empty_trace_is_unknown_not_cleared(self) -> None:
        """FIX (gauntlet.monitor_structured): an empty trace is not-applicable, not a
        green result. Pre-fix these branches returned CLEARED (gauntlet_runtime.py)."""
        for op in ("audit", "frame", "boundary", "derive", "redirect", "oob"):
            verdict, reason = gauntlet.monitor_structured(op, [], [])
            self.assertEqual(verdict, Verdict.UNKNOWN, op)
            self.assertTrue(reason.startswith("not-applicable: "), reason)

    def test_real_evidence_branches_are_untouched(self) -> None:
        """GUARD: a genuine violation still reports ISSUE, not UNKNOWN."""
        events = [{"event_type": "evidence.attached", "metadata": {"producer": "x", "verifier": "x"}}]
        self.assertEqual(gauntlet.monitor_structured("self", events, [])[0], Verdict.ISSUE)


# ---------------------------------------------------------------------------
# P0-4  Time: verdict rule, exact McNemar, frozen manifest
# ---------------------------------------------------------------------------
class TimeGateTests(unittest.TestCase):
    def _run(self, root: Path, base, cand, **kw):
        plan = time_rt.PairedBinaryPlan("p", "obl", **kw)
        obs = [time_rt.PairedBinaryObservation(f"i{n}", b, c) for n, (b, c) in enumerate(zip(base, cand))]
        return time_rt.record_paired_observations(root, plan, obs)

    def test_worse_candidate_is_issue(self) -> None:
        """FIX (time.record_paired_observations verdict): a significantly worse
        candidate is ISSUE, never CLEARED (time_runtime.py old unconditional CLEARED)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            r = self._run(root, [True] * 10, [False] * 10)
            self.assertEqual(r.verdict, Verdict.ISSUE)

    def test_inconclusive_candidate_is_unknown(self) -> None:
        """FIX: a better-but-not-significant result is UNKNOWN(inconclusive), not CLEARED."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            r = self._run(root, [True, False, False], [True, True, True])
            self.assertEqual(r.verdict, Verdict.UNKNOWN)
            self.assertIn("inconclusive", (r.notes or "") + " ".join(r.unresolved))

    def test_better_and_significant_is_cleared(self) -> None:
        """GUARD: a significantly better candidate still clears."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            r = self._run(root, [False] * 10, [True] * 10)
            self.assertEqual(r.verdict, Verdict.CLEARED)

    def test_mcnemar_large_n_no_crash_and_p_in_unit_interval(self) -> None:
        """FIX (time.mcnemar_exact Fraction rewrite): exact for large n, no OverflowError,
        p never 0.0 (time_runtime.py old float _binom_pmf overflowed near n>=1030)."""
        p_balanced = time_rt.mcnemar_exact(600, 600)
        self.assertTrue(0.0 < p_balanced <= 1.0)
        p_tail = time_rt.mcnemar_exact(1200, 0)  # underflows float64
        self.assertGreater(p_tail, 0.0)
        self.assertEqual(p_tail, time_rt.MIN_POSITIVE_P)

    def test_frozen_manifest_mismatch_raises(self) -> None:
        """FIX (time.apply_exclusions frozen item_ids): the denominator must be the
        frozen manifest minus frozen exclusions, nothing else."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            plan = time_rt.PairedBinaryPlan("p", "obl", item_ids=("a", "b", "c"))
            obs = [time_rt.PairedBinaryObservation("a", True, True), time_rt.PairedBinaryObservation("b", True, True)]
            with self.assertRaises(ValueError):
                time_rt.apply_exclusions(plan, obs)  # missing c
            off = obs + [time_rt.PairedBinaryObservation("z", True, True)]
            with self.assertRaises(ValueError):
                time_rt.apply_exclusions(plan, off)  # z off-list

    def test_duplicate_and_offlist_exclusions_raise(self) -> None:
        """FIX (PairedBinaryPlan.__post_init__): duplicate or off-manifest exclusion ids
        are rejected at construction."""
        with self.assertRaises(ValueError):
            time_rt.PairedBinaryPlan("p", "obl", exclusions=(time_rt.Exclusion("x", "r"), time_rt.Exclusion("x", "r2")))
        with self.assertRaises(ValueError):
            time_rt.PairedBinaryPlan("p", "obl", item_ids=("a", "b"), exclusions=(time_rt.Exclusion("z", "r"),))


# ---------------------------------------------------------------------------
# P0-5  Council commit/reveal hiding, control obligation, finalize re-call
# ---------------------------------------------------------------------------
class CouncilGateTests(unittest.TestCase):
    def _seats(self):
        return [
            council.CouncilSeat("s1", "formal", "Is it valid?", "proof"),
            council.CouncilSeat("s2", "empirical", "Is it measured?", "experiment"),
            council.CouncilSeat("s3", "skeptic", "What breaks it?", "adversarial"),
        ]

    def _critiques(self, root, cid):
        council.record_cross_critique(root, cid, council.CrossCritique("s1", "s2", challenged_findings=("f2",)))
        council.record_cross_critique(root, cid, council.CrossCritique("s2", "s3", surviving_findings=("f3",)))
        council.record_cross_critique(root, cid, council.CrossCritique("s3", "s1", challenged_findings=("f1",)))

    def test_commitment_hides_submission_until_reveal(self) -> None:
        """FIX (council.commit): only the commitment is stored at commit time; the
        submission text must not be readable before reveal (council_runtime.py old
        state.sealed[seat]=submission)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget", self._seats())
            secret = council.SeatSubmission("secret-hypothesis-marker", ("c",), ("e",), ("p",), 0.5, ("f",))
            nonces = {}
            for sid in ("s1", "s2", "s3"):
                _, nonces[sid] = council.commit(root, state.council_id, sid, secret)
            # All commitments recorded, but no submission is stored until reveal.
            stored = (RuntimeStore(root).base / "councils" / f"{state.council_id}.json").read_text(encoding="utf-8")
            self.assertNotIn("secret-hypothesis-marker", stored)
            self.assertFalse(council.reveal(root, state.council_id, "s1", secret, "bad-nonce"))
            self.assertTrue(council.reveal(root, state.council_id, "s1", secret, nonces["s1"]))

    def test_control_with_wrong_obligation_does_not_clear(self) -> None:
        """FIX (council._matched_control obligation_id): a control recorded under a
        different obligation must not satisfy this obligation (council_runtime.py old
        _matched_control ignored obligation_id)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget-1", self._seats())
            sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
            nonces = {}
            for seat in self._seats():
                _, nonces[seat.seat_id] = council.commit(root, state.council_id, seat.seat_id, sub)
            for seat in self._seats():
                council.reveal(root, state.council_id, seat.seat_id, sub, nonces[seat.seat_id])
            self._critiques(root, state.council_id)
            wrong = council.record_control(
                root, "different-obligation", artifact_hash="artifact", budget_hash="budget-1",
                kind="DIRECT", output_hash="x", verdict=Verdict.CLEARED, verifier="direct",
            )
            r = council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"], direct_control_receipt=wrong.receipt_id)
            self.assertEqual(r.verdict, Verdict.UNKNOWN)

    def test_finalize_is_not_recallable_after_close(self) -> None:
        """FIX (council.finalize CLOSED guard): finalize must raise once the council is
        CLOSED (council_runtime.py old finalize re-callable)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget", self._seats())
            sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
            nonces = {}
            for seat in self._seats():
                _, nonces[seat.seat_id] = council.commit(root, state.council_id, seat.seat_id, sub)
            for seat in self._seats():
                council.reveal(root, state.council_id, seat.seat_id, sub, nonces[seat.seat_id])
            self._critiques(root, state.council_id)
            council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"])
            with self.assertRaises(ValueError):
                council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"])


# ---------------------------------------------------------------------------
# P0-6  Power verifier-family resolution
# ---------------------------------------------------------------------------
class PowerGateTests(unittest.TestCase):
    def test_fake_z3_in_temp_dir_is_refused(self) -> None:
        """FIX (power._resolve_executable): a binary named z3 supplied by an out-of-PATH
        path must not run (power_runtime.py old Path(executable).exists())."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            fake = root / "z3"
            fake.write_text("#!/bin/sh\necho sat\n", encoding="utf-8")
            os.chmod(fake, 0o755)
            check = power.VerificationCheck("z", "z3", (str(fake),), mandatory=True)
            plan = power.VerificationPlan("p", "obl", "sys", "claim", (), (check,))
            receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
            self.assertNotIn("sat", json.dumps(result))

    def test_python_m_unittest_arbitrary_module_is_refused(self) -> None:
        """FIX (power._module_args_allowed): `python -m unittest <module>` must be refused
        without the env gate (power_runtime.py old shape check allowed any module)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            check = power.VerificationCheck("u", "python-unittest", (sys.executable, "-m", "unittest", "evil_module"))
            plan = power.VerificationPlan("p", "obl", "sys", "claim", (), (check,))
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
                receipt, _ = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)

    def test_failing_mandatory_check_is_issue(self) -> None:
        """GUARD: a genuinely failing python-family check reports ISSUE."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            bad = root / "broken.py"
            bad.write_text("def (:\n", encoding="utf-8")  # syntax error
            check = power.VerificationCheck("c", "compileall", (sys.executable, "-m", "compileall", "-q", str(bad)))
            plan = power.VerificationPlan("p", "obl", "sys", "claim", (), (check,))
            receipt, _ = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.ISSUE)


# ---------------------------------------------------------------------------
# P0-7  Hooks
# ---------------------------------------------------------------------------
class HookGateTests(unittest.TestCase):
    def _call(self, mode: str, payload, root: Path) -> int:
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}, clear=False), patch("sys.stdin", stdin), redirect_stdout(io.StringIO()):
            return egrt_hook.main([mode])

    def test_post_tool_failure_mode_emits_action_failed(self) -> None:
        """FIX (egrt_hook post-tool-failure mode): PostToolUseFailure must record
        action.failed even when the payload has no is_error (egrt_hook.py new mode)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            self.assertEqual(self._call("post-tool-failure", {"tool_name": "Bash"}, root), 0)
            events = RuntimeStore(root).iter_events()
            self.assertTrue(any(e.get("event_type") == "action.failed" for e in events))

    def test_post_tool_success_without_error_emits_no_failure(self) -> None:
        """GUARD: a clean PostToolUse does not fabricate an action.failed event."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            self.assertEqual(self._call("post-tool", {"tool_name": "Bash"}, root), 0)
            events = RuntimeStore(root).iter_events()
            self.assertFalse(any(e.get("event_type") == "action.failed" for e in events))

    def test_tool_response_is_error_is_read(self) -> None:
        """FIX (egrt_hook._is_error): a nested tool_response.is_error is a failure."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            self._call("post-tool", {"tool_name": "Bash", "tool_response": {"is_error": True}}, root)
            events = RuntimeStore(root).iter_events()
            self.assertTrue(any(e.get("event_type") == "action.failed" for e in events))

    def test_non_dict_stdin_exits_zero(self) -> None:
        """FIX (egrt_hook._payload): valid non-object JSON must not crash the hook
        (egrt_hook.py old _payload returned the list/None and .get raised)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            self.assertEqual(self._call("post-tool", "[]", root), 0)
            self.assertEqual(self._call("prompt", "null", root), 0)


# ---------------------------------------------------------------------------
# P0-7c / FOIL bridge adaptation gating
# ---------------------------------------------------------------------------
class FoilBridgeGateTests(unittest.TestCase):
    def _profile(self) -> dict:
        return {"id": "u", "schema": "s", "domains": {}, "privacy": {"raw_prompts_stored": False}}

    def _adaptation_task(self, root: Path):
        task = soul.start_task(root, "goal")
        obl = soul.add_obligation(root, task.task_id, ObligationKind.ADAPTATION, "adapt to my domain")
        return task, obl

    def test_plain_prompt_does_not_clear_adaptation(self) -> None:
        """FIX (foil_runtime_bridge.record_prompt_adaptation): a prompt that does not name
        the obligation or carry /foil records routing metadata but leaves the load-bearing
        ADAPTATION obligation UNKNOWN (bridge old unconditional CLEARED)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            _, obl = self._adaptation_task(root)
            receipts = bridge.record_prompt_adaptation(root, self._profile(), ["physics"], ["facet"], prompt_text="please help me", foil_alias=False)
            self.assertEqual([r.verdict for r in receipts], [Verdict.UNKNOWN])
            self.assertEqual(RuntimeStore(root).receipts_for(obl.obligation_id)[-1]["verdict"], Verdict.UNKNOWN.value)

    def test_explicit_foil_alias_clears_adaptation(self) -> None:
        """GUARD (positive control): an explicit /foil request does clear ADAPTATION."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            _, obl = self._adaptation_task(root)
            receipts = bridge.record_prompt_adaptation(root, self._profile(), ["physics"], ["facet"], prompt_text="/foil please adapt", foil_alias=True)
            self.assertEqual([r.verdict for r in receipts], [Verdict.CLEARED])

    def test_bridge_never_clears_a_proof_obligation(self) -> None:
        """GUARD: FOIL adaptation cannot produce a receipt for a non-foil (PROOF) obligation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "goal")
            proof = soul.add_obligation(root, task.task_id, ObligationKind.PROOF, "prove it")
            bridge.record_prompt_adaptation(root, self._profile(), ["physics"], [], prompt_text=proof.obligation_id, foil_alias=True)
            self.assertEqual(RuntimeStore(root).receipts_for(proof.obligation_id), [])


# ---------------------------------------------------------------------------
# Space / Reality / Mind / Meditate existing-invariant guards
# ---------------------------------------------------------------------------
class ModuleInvariantGuards(unittest.TestCase):
    def _retrieval(self, root: Path):
        plan = space.SearchPlan("sp", "obl", "claim", ("query",), ("a",))
        with patch.dict(space.ADAPTERS, {"a": lambda q, limit: [{"title": "P", "doi": "10/x", "source_index": "a"}]}, clear=True):
            retrieval, _ = space.run_plan(root, plan)
        return retrieval

    def test_space_zero_assessments_is_unknown(self) -> None:
        """GUARD: assess_sources with no assessments is UNKNOWN, never CLEARED."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            retrieval = self._retrieval(root)
            assessed = space.assess_sources(root, "obl", retrieval.receipt_id, [])
            self.assertEqual(assessed.verdict, Verdict.UNKNOWN)

    def test_reality_refuses_non_cleared_space_receipt(self) -> None:
        """GUARD: a non-CLEARED (retrieval) Space receipt cannot admit a candidate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            retrieval = self._retrieval(root)  # verdict UNKNOWN, action multi-index-retrieval
            candidate = reality.MethodCandidate(
                "c", "obl-real", "gap", "constraint", "assumption", "mechanism", ("prior",), "delta",
                ("in",), ("out",), ("inv",), (), ("failure",), "neg", "transfer", "ablate", "verify", ("tag",),
            )
            r = reality.record_candidate(root, candidate, [retrieval.receipt_id])
            self.assertEqual(r.verdict, Verdict.UNKNOWN)

    def test_mind_z3_absent_is_unavailable(self) -> None:
        """GUARD: with z3 not on PATH, an SMT2 check is UNAVAILABLE."""
        with tempfile.TemporaryDirectory() as directory:
            smt = Path(directory) / "x.smt2"
            smt.write_text("(check-sat)\n", encoding="utf-8")
            with patch.object(mind.shutil, "which", lambda _name: None):
                result = mind.run_z3_smt2(smt)
            self.assertEqual(result["verdict"], Verdict.UNAVAILABLE.value)

    def test_meditate_incomplete_model_is_insufficient(self) -> None:
        """GUARD: a triggered decision with neither VOC nor complete ordinal ranks is
        UNKNOWN/INSUFFICIENT_MODEL."""
        state = meditate.DecisionState(
            "d", None, "goal", "done",
            triggers=meditate.PreflightTriggers(high_stakes=True),
            actions=[meditate.CandidateAction("a", "act")],
        )
        result = meditate.recommend(state)
        self.assertEqual(result["mode"], "INSUFFICIENT_MODEL")
        self.assertEqual(result["verdict"], Verdict.UNKNOWN.value)


if __name__ == "__main__":
    unittest.main()
