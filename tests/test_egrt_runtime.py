from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import council_runtime as council  # noqa: E402
import egrt_hook  # noqa: E402
import gauntlet_runtime as gauntlet  # noqa: E402
import meditate_runtime as meditate  # noqa: E402
import mind_runtime as mind  # noqa: E402
import power_runtime as power  # noqa: E402
import reality_runtime as reality  # noqa: E402
import soul_runtime as soul  # noqa: E402
import space_runtime as space  # noqa: E402
import time_runtime as time_rt  # noqa: E402
import verify_ledger  # noqa: E402
from egrt_store import RuntimeStore  # noqa: E402
from egrt_types import (  # noqa: E402
    ArtifactRef,
    ObligationKind,
    Receipt,
    Verdict,
    digest,
)


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


class TypedRuntimeTests(unittest.TestCase):
    def test_store_is_private_and_receipt_hash_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            store = RuntimeStore(root)
            receipt = Receipt(
                receipt_id="rcpt-test",
                module="mind",
                obligation_id="obl-test",
                verdict=Verdict.CLEARED,
                action="unit",
                input_hash=digest({"x": 1}),
                output_hash=digest({"y": 2}),
            )
            path = store.write_receipt(receipt)
            body = json.loads(path.read_text(encoding="utf-8"))
            expected = body.pop("content_hash")
            self.assertEqual(digest(body), expected)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_store_honors_configured_state_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gauntlet.json").write_text(json.dumps({"state_dir": ".private/custom"}), encoding="utf-8")
            store = RuntimeStore(root)
            self.assertEqual(store.base, root.resolve() / ".private/custom/runtime")

    def test_soul_release_gate_requires_correct_module_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "prove a thing")
            obligation = soul.add_obligation(root, task.task_id, ObligationKind.PROOF, "1+1=2")
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            store = RuntimeStore(root)
            store.write_receipt(Receipt(
                receipt_id="wrong", module="space", obligation_id=obligation.obligation_id,
                verdict=Verdict.CLEARED, action="wrong", input_hash="x"
            ))
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.UNKNOWN)
            store.write_receipt(Receipt(
                receipt_id="right", module="mind", obligation_id=obligation.obligation_id,
                verdict=Verdict.CLEARED, action="right", input_hash="x"
            ))
            verdict, _ = soul.release_gate(root, task.task_id)
            self.assertEqual(verdict, Verdict.CLEARED)
            self.assertEqual((store.base / "active_task").read_text(encoding="utf-8").strip(), task.task_id)
            released, _ = soul.release_task(root, task.task_id)
            self.assertEqual(released, Verdict.CLEARED)
            self.assertFalse((store.base / "active_task").exists())
            self.assertTrue(store.read_task(task.task_id)["released"])

    def test_soul_ignores_tampered_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "prove")
            obligation = soul.add_obligation(root, task.task_id, ObligationKind.PROOF, "claim")
            store = RuntimeStore(root)
            path = store.write_receipt(Receipt("r", "mind", obligation.obligation_id, Verdict.CLEARED, "proof", "x"))
            body = json.loads(path.read_text(encoding="utf-8"))
            body["verdict"] = Verdict.ISSUE.value
            path.write_text(json.dumps(body), encoding="utf-8")
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.UNKNOWN)

    def test_soul_latest_valid_receipt_is_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "verify")
            obligation = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "works")
            store = RuntimeStore(root)
            store.write_receipt(Receipt("old", "power", obligation.obligation_id, Verdict.CLEARED, "old", "x"))
            store.write_receipt(Receipt("new", "power", obligation.obligation_id, Verdict.UNKNOWN, "new", "y"))
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.UNKNOWN)

    def test_soul_issue_dominates_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task = soul.start_task(root, "verify")
            obligation = soul.add_obligation(root, task.task_id, ObligationKind.ENGINEERING, "works")
            store = RuntimeStore(root)
            store.write_receipt(Receipt("a", "power", obligation.obligation_id, Verdict.CLEARED, "check", "x"))
            store.write_receipt(Receipt("b", "power", obligation.obligation_id, Verdict.ISSUE, "check", "x"))
            self.assertEqual(soul.release_gate(root, task.task_id)[0], Verdict.ISSUE)

    def test_hook_persists_prompt_hash_not_raw_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            raw = "secret-marker-9911 /mind"
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}), patch("sys.stdin", io.StringIO(json.dumps({"prompt": raw}))):
                self.assertEqual(egrt_hook.prompt(), 0)
            serialized = "\n".join(p.read_text(encoding="utf-8") for p in (root / ".egrt/state/runtime/events").glob("*.json"))
            self.assertNotIn(raw, serialized)
            self.assertIn("mind", serialized)

    def test_hook_alias_match_does_not_match_word_prefix(self) -> None:
        self.assertEqual(egrt_hook._explicit_aliases("/mindfulness and /mind"), ["mind"])

    def test_stop_hook_blocks_unresolved_typed_task_and_releases_clear_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}, clear=False):
                task = soul.start_task(root, "prove")
                obligation = soul.add_obligation(root, task.task_id, ObligationKind.PROOF, "claim")
                output = io.StringIO()
                with patch("sys.stdin", io.StringIO("{}")), patch("sys.stdout", output):
                    self.assertEqual(egrt_hook.stop(), 0)
                self.assertIn('"decision": "block"', output.getvalue())
                RuntimeStore(root).write_receipt(Receipt("clear", "mind", obligation.obligation_id, Verdict.CLEARED, "proof", "x"))
                output2 = io.StringIO()
                with patch("sys.stdin", io.StringIO("{}")), patch("sys.stdout", output2):
                    self.assertEqual(egrt_hook.stop(), 0)
                self.assertEqual(output2.getvalue(), "")
                self.assertFalse((RuntimeStore(root).base / "active_task").exists())



class MeditateTests(unittest.TestCase):
    def test_skip_without_trigger(self) -> None:
        state = meditate.DecisionState("d", None, "goal", "done")
        self.assertEqual(meditate.recommend(state)["decision"], "SKIP")

    def test_quantitative_voc_selects_positive_action(self) -> None:
        state = meditate.DecisionState(
            "d", None, "goal", "done",
            triggers=meditate.PreflightTriggers(high_stakes=True),
            current_best_eu=5,
            actions=[
                meditate.CandidateAction("a", "search", cost=1, outcomes=(meditate.QuantitativeOutcome(1.0, 8),)),
                meditate.CandidateAction("b", "stop", cost=0, outcomes=(meditate.QuantitativeOutcome(1.0, 5),)),
            ],
        )
        result = meditate.recommend(state)
        self.assertEqual(result["decision"], "ACT")
        self.assertEqual(result["action_id"], "a")
        self.assertEqual(result["max_voc"], 2)

    def test_quantitative_voc_releases_when_nonpositive(self) -> None:
        state = meditate.DecisionState(
            "d", None, "goal", "done",
            triggers=meditate.PreflightTriggers(irreversible=True),
            current_best_eu=5,
            actions=[meditate.CandidateAction("a", "more", cost=2, outcomes=(meditate.QuantitativeOutcome(1.0, 6),))],
        )
        self.assertEqual(meditate.recommend(state)["decision"], "RELEASE")

    def test_invalid_probabilities_rejected(self) -> None:
        action = meditate.CandidateAction("a", "bad", cost=0, outcomes=(meditate.QuantitativeOutcome(0.8, 1),))
        with self.assertRaises(ValueError):
            action.voc(0)

    def test_ordinal_tie_stays_unknown(self) -> None:
        state = meditate.DecisionState(
            "d", None, "goal", "done",
            triggers=meditate.PreflightTriggers(repeated_failure=True),
            actions=[
                meditate.CandidateAction("a", "A", info_rank=3, progress_rank=1, risk_reduction_rank=1, cost_rank=2),
                meditate.CandidateAction("b", "B", info_rank=1, progress_rank=3, risk_reduction_rank=1, cost_rank=2),
            ],
        )
        self.assertEqual(meditate.recommend(state)["verdict"], Verdict.UNKNOWN.value)


class CouncilTests(unittest.TestCase):
    def _seats(self) -> list[council.CouncilSeat]:
        return [
            council.CouncilSeat("s1", "formal correctness", "Is it valid?", "proof"),
            council.CouncilSeat("s2", "empirical validity", "Is it measured?", "experiment"),
            council.CouncilSeat("s3", "skeptic", "What breaks it?", "adversarial"),
        ]

    def _critiques(self, root: Path, council_id: str) -> None:
        council.record_cross_critique(root, council_id, council.CrossCritique("s1", "s2", challenged_findings=("f2",)))
        council.record_cross_critique(root, council_id, council.CrossCritique("s2", "s3", surviving_findings=("f3",)))
        council.record_cross_critique(root, council_id, council.CrossCritique("s3", "s1", challenged_findings=("f1",)))

    def test_requires_skeptic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            seats = [council.CouncilSeat("a", "formal", "q1", "m1"), council.CouncilSeat("b", "empirical", "q2", "m2"), council.CouncilSeat("c", "ops", "q3", "m3")]
            with self.assertRaises(ValueError):
                council.create_council(root, "artifact", "budget", seats)

    def test_commit_reveal_detects_tampering_and_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget", self._seats())
            subs = {
                "s1": council.SeatSubmission("h1", ("c1",), ("e1", "shared"), ("p1",), 0.7, ("f1",)),
                "s2": council.SeatSubmission("h2", ("c2",), ("e2", "shared"), ("p2",), 0.6, ("f2",)),
                "s3": council.SeatSubmission("h3", ("c3",), ("e3",), ("p3",), 0.8, ("f3",)),
            }
            for sid, sub in subs.items():
                council.commit(root, state.council_id, sid, sub)
            tampered = council.SeatSubmission("changed", ("c1",), ("e1",), ("p1",), 0.7, ("f1",))
            self.assertFalse(council.reveal(root, state.council_id, "s1", tampered))
            for sid, sub in subs.items():
                self.assertTrue(council.reveal(root, state.council_id, sid, sub))
            loaded = council._load(root, state.council_id)
            matrix = council.overlap_matrix(loaded)
            self.assertEqual(len(matrix["pairs"]), 3)
            self.assertTrue(any(p["evidence_overlap"] > 0 for p in matrix["pairs"]))

    def test_finalize_requires_real_direct_control_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget", self._seats())
            sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
            for seat in self._seats():
                council.commit(root, state.council_id, seat.seat_id, sub)
            for seat in self._seats():
                council.reveal(root, state.council_id, seat.seat_id, sub)
            self._critiques(root, state.council_id)
            r = council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"], direct_control_receipt="missing")
            self.assertEqual(r.verdict, Verdict.UNKNOWN)

    def test_finalize_clears_with_matched_direct_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget-1", self._seats())
            sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
            for seat in self._seats():
                council.commit(root, state.council_id, seat.seat_id, sub)
            for seat in self._seats():
                council.reveal(root, state.council_id, seat.seat_id, sub)
            self._critiques(root, state.council_id)
            direct = council.record_control(
                root, "control", artifact_hash="artifact", budget_hash="budget-1",
                kind="DIRECT", output_hash="direct-output", verdict=Verdict.CLEARED, verifier="direct",
            )
            r = council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"], direct_control_receipt=direct.receipt_id)
            self.assertEqual(r.verdict, Verdict.CLEARED)

    def test_finalize_requires_cross_critique_and_same_artifact_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = council.create_council(root, "artifact", "budget", self._seats())
            sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
            for seat in self._seats():
                council.commit(root, state.council_id, seat.seat_id, sub)
            for seat in self._seats():
                council.reveal(root, state.council_id, seat.seat_id, sub)
            wrong = council.record_control(
                root, "control", artifact_hash="other-artifact", budget_hash="budget",
                kind="DIRECT", output_hash="x", verdict=Verdict.CLEARED, verifier="direct",
            )
            r = council.finalize(root, state.council_id, "obl", synthesis_hash="s", supported_findings=["f"], direct_control_receipt=wrong.receipt_id)
            self.assertEqual(r.verdict, Verdict.UNKNOWN)
            self.assertTrue(any("cross-critique" in item for item in r.unresolved))
            self.assertTrue(any("same-artifact" in item for item in r.unresolved))


class GauntletTests(unittest.TestCase):
    def test_all_ten_operations_registered_with_explicit_modes(self) -> None:
        expected = {"frame", "audit", "costume", "derive", "self", "redirect", "refresh", "boundary", "explain", "oob"}
        self.assertEqual(set(gauntlet.OPERATIONS), expected)
        self.assertTrue(all(row["mode"] in {"AUTOMATIC", "ASSISTED", "MANUAL", "UNAVAILABLE"} for row in gauntlet.coverage_registry()))

    def test_self_monitor_finds_shared_producer_verifier(self) -> None:
        events = [{"event_type": "evidence.attached", "metadata": {"producer": "x", "verifier": "x"}}]
        self.assertEqual(gauntlet.monitor_structured("self", events, [])[0], Verdict.ISSUE)

    def test_redirect_finds_unchanged_blocker(self) -> None:
        events = [{"event_type": "action.attempted", "metadata": {"blocker_hash": "b", "progress_hash": "p"}} for _ in range(3)]
        self.assertEqual(gauntlet.monitor_structured("redirect", events, [])[0], Verdict.ISSUE)

    def test_semantic_monitor_unavailable_is_not_clear(self) -> None:
        self.assertEqual(gauntlet.monitor_structured("explain", [], [])[0], Verdict.UNAVAILABLE)


class MindTests(unittest.TestCase):
    def test_exact_arithmetic(self) -> None:
        self.assertEqual(mind.exact_arithmetic("1/3 + 1/6"), "1/2")
        self.assertEqual(mind.exact_arithmetic("2**5 - 1"), "31")

    def test_arithmetic_rejects_calls(self) -> None:
        with self.assertRaises(ValueError):
            mind.exact_arithmetic("__import__('os').system('echo x')")

    def test_arithmetic_enforces_resource_bound(self) -> None:
        with self.assertRaises(ValueError):
            mind.exact_arithmetic("2**1001")

    def test_missing_z3_encoding_is_unavailable_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = mind.run_z3_smt2(Path(directory) / "missing.smt2")
            self.assertEqual(result["verdict"], Verdict.UNAVAILABLE.value)


class SpaceTests(unittest.TestCase):
    def test_dedup_and_saturation_with_fake_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            def fake_a(query: str, limit: int):
                return [{"title": "Paper A", "doi": "10/a", "source_index": "openalex", "year": 2024}]
            def fake_b(query: str, limit: int):
                return [{"title": "Paper A duplicate", "doi": "10/a", "source_index": "crossref", "year": 2024}]
            plan = space.SearchPlan("p", "obl", "q", ("query", "query-2"), ("a", "b"), max_queries=3, saturation_queries=1)
            with patch.dict(space.ADAPTERS, {"a": fake_a, "b": fake_b}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(result["scope_status"], "CANDIDATES_RETRIEVED_REVIEW_REQUIRED")
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(set(result["results"][0]["source_indexes"]), {"openalex", "crossref"})
            self.assertEqual(result["rounds"][-1]["novel"], 0)

    def test_no_results_is_scoped_not_absence_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            plan = space.SearchPlan("p", "obl", "q", ("query",), ("a",), max_queries=1, saturation_queries=1)
            with patch.dict(space.ADAPTERS, {"a": lambda q, limit: []}, clear=True):
                receipt, result = space.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(result["scope_status"], "NOT_FOUND_WITHIN_SCOPE")

    def test_retrieval_does_not_clear_until_source_is_assessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            plan = space.SearchPlan("p", "obl", "claim", ("query",), ("a",))
            with patch.dict(space.ADAPTERS, {"a": lambda q, limit: [{"title": "Primary", "doi": "10/x", "source_index": "a"}]}, clear=True):
                retrieval, _ = space.run_plan(root, plan)
            self.assertEqual(retrieval.verdict, Verdict.UNKNOWN)
            assessed = space.assess_sources(
                root, "obl", retrieval.receipt_id,
                [space.SourceAssessment(
                    "sa1", ArtifactRef("local/source.pdf", sha256="abc123"),
                    "SUPPORTS", "human-or-tool-verifier", "exact scoped claim", "primary-source",
                )],
            )
            self.assertEqual(assessed.verdict, Verdict.CLEARED)
            self.assertIn('"claim_outcome": "SUPPORTED"', assessed.notes or "")


class RealityTests(unittest.TestCase):
    def _candidate(self) -> reality.MethodCandidate:
        return reality.MethodCandidate(
            "c", "obl-real", "gap", "constraint", "assumption", "mechanism", ("prior",), "delta",
            ("in",), ("out",), ("inv",), (), ("failure",), "neg", "transfer", "ablate", "verify", ("tag",)
        )

    def test_requires_stored_space_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            r = reality.record_candidate(root, self._candidate(), ["not-real"])
            self.assertEqual(r.verdict, Verdict.UNKNOWN)
            plan = space.SearchPlan("sp", "obl-space", "nearest prior art", ("query",), ("a",))
            with patch.dict(space.ADAPTERS, {"a": lambda q, limit: [{"title": "Prior", "doi": "10/prior", "source_index": "a"}]}, clear=True):
                retrieval, _ = space.run_plan(root, plan)
            assessed = space.assess_sources(
                root, "obl-space", retrieval.receipt_id,
                [space.SourceAssessment("pa", ArtifactRef("prior.pdf", sha256="beef"), "SUPPORTS", "reviewer", "nearest prior art exists")],
            )
            r2 = reality.record_candidate(root, self._candidate(), [assessed.receipt_id])
            self.assertEqual(r2.verdict, Verdict.CLEARED)


class PowerTests(unittest.TestCase):
    def test_explicit_command_plan_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            target = root / "sample.py"
            target.write_text("x = 1\n", encoding="utf-8")
            check = power.VerificationCheck("ok", "compileall", (sys.executable, "-m", "compileall", "-q", str(target)), defect_classes=("syntax-regression",))
            plan = power.VerificationPlan("p", "obl", "system", "claim", ("inv",), (check,))
            receipt, result = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            self.assertEqual(result["coverage"]["ok"], ["syntax-regression"])
            self.assertNotIn("ok\n", json.dumps(result))

    def test_missing_mandatory_tool_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            check = power.VerificationCheck("missing", "z3", ("z3",), mandatory=True)
            plan = power.VerificationPlan("p", "obl", "system", "claim", (), (check,))
            receipt, _ = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)

    def test_custom_command_requires_outer_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            check = power.VerificationCheck("custom", "custom", (sys.executable, "--version"))
            plan = power.VerificationPlan("p", "obl", "system", "claim", (), (check,))
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EGR_POWER_ALLOW_CUSTOM_COMMANDS", None)
                receipt, _ = power.run_plan(root, plan)
            self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)


class TimeTests(unittest.TestCase):
    def test_mcnemar_and_wilson(self) -> None:
        self.assertEqual(time_rt.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(time_rt.mcnemar_exact(0, 4), 0.125)
        lo, hi = time_rt.wilson_interval(5, 10)
        self.assertTrue(0 <= lo < 0.5 < hi <= 1)

    def test_paired_binary(self) -> None:
        result = time_rt.paired_binary([True, True, False, False], [True, False, True, True])
        self.assertEqual(result["base_only"], 1)
        self.assertEqual(result["candidate_only"], 2)
        self.assertEqual(result["delta"], 0.25)

    def test_item_addressed_exclusions_and_contamination(self) -> None:
        plan = time_rt.PairedBinaryPlan(
            "p", "obl", exclusions=(time_rt.Exclusion("b", "contaminated", contamination=True),)
        )
        observations = [
            time_rt.PairedBinaryObservation("a", True, True),
            time_rt.PairedBinaryObservation("b", False, True, contaminated=True),
        ]
        included, applied = time_rt.apply_exclusions(plan, observations)
        self.assertEqual([row.item_id for row in included], ["a"])
        self.assertEqual(applied[0]["item_id"], "b")
        bad_plan = time_rt.PairedBinaryPlan("p2", "obl")
        with self.assertRaises(ValueError):
            time_rt.apply_exclusions(bad_plan, observations)

    def test_record_paired_refuses_silent_exclusion_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            plan = time_rt.PairedBinaryPlan("p", "obl", exclusions=(time_rt.Exclusion("x", "reason"),))
            with self.assertRaises(ValueError):
                time_rt.record_paired(root, plan, [True], [True])


class LedgerTests(unittest.TestCase):
    def test_runtime_receipt_integrity_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gauntlet.json").write_text(json.dumps({
                "state_dir": ".egrt/state",
                "ledger": {"enabled": True, "path": "ledger.json", "accept_runtime_receipts": True}
            }), encoding="utf-8")
            store = RuntimeStore(root)
            store.write_receipt(Receipt("r", "mind", "o", Verdict.CLEARED, "a", "x"))
            (root / "ledger.json").write_text(json.dumps({"claims": [{"id": "c", "status": "supported", "evidence": [{"receipt_id": "r"}]}]}), encoding="utf-8")
            self.assertEqual(verify_ledger.check(root), [])
            receipt_path = root / ".egrt/state/runtime/receipts/r.json"
            body = json.loads(receipt_path.read_text(encoding="utf-8"))
            body["notes"] = "tampered"
            receipt_path.write_text(json.dumps(body), encoding="utf-8")
            errors = verify_ledger.check(root)
            self.assertTrue(any("content hash mismatch" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
