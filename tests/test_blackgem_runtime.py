from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import blackgem_runtime as bg  # noqa: E402
import foil_runtime_bridge as bridge  # noqa: E402
import soul_runtime as soul  # noqa: E402
from egrt_store import RuntimeStore, verify_content_hash  # noqa: E402
from egrt_types import ObligationKind, Verdict  # noqa: E402

CANDIDATE = "We introduce Adaptive Coherence Sync, a new way to keep replicas in step."
CANARY = "A renamed ordinary cache invalidation strategy is presented as a novel algorithm."

CAUGHT_TEXT = """COSTUME CHECK
costume_verdict: COSTUME
prior_technique: lease-based cache invalidation
why: the mechanism is a lease with a new name.
BREAK CHECK
the sync is novel|mechanism section|compare against lease invalidation
MECH-CHECKABLE: YES
LOAD-BEARING CLAIM
novelty
KILL-TEST
diff against the textbook lease protocol
CONFIDENCE
0.8
VERDICT KILL"""

RUBBER_TEXT = """COSTUME CHECK — none found
BREAK CHECK
LOAD-BEARING CLAIM
novelty
KILL-TEST
none
CONFIDENCE
0.5
VERDICT SURVIVES_TO_GATE"""

SURVIVES_TEXT = """COSTUME CHECK
costume_verdict: NOT_COSTUME
prior_technique: NONE
why: no prior matches the mechanism.
BREAK CHECK
LOAD-BEARING CLAIM
the replication invariant
KILL-TEST
run the replica divergence harness
CONFIDENCE
0.4
VERDICT SURVIVES_TO_GATE"""

KILL_TEXT = CAUGHT_TEXT


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )


def breakers(group_b: str = "vendor-b") -> list[bg.Breaker]:
    return [
        bg.Breaker("a", "model-a", "2026-01", 0.2, "vendor-a"),
        bg.Breaker("b", "model-b", "2026-02", 0.2, group_b),
    ]


class Transport:
    """Scripted offline `fetch`. Nothing here touches the network."""

    def __init__(self, script) -> None:
        self.script = script
        self.calls: list[dict] = []

    def __call__(self, url, body, headers):
        self.calls.append({"url": url, "body": body, "headers": headers})
        outcome = self.script(body, len(self.calls) - 1)
        if isinstance(outcome, Exception):
            raise outcome
        return {"choices": [{"message": {"content": outcome}}], "usage": {}}


def constant(text: str):
    return lambda body, index: text


def per_model(mapping, default=""):
    return lambda body, index: mapping.get(body["model"], default)


class BlackGemTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        init_root(self.root)
        self._env = patch.dict("os.environ", {"OPENROUTER_API_KEY": "offline-test-key"})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._dir.cleanup)

    def make(self, group_b: str = "vendor-b") -> bg.StrikeState:
        from egrt_types import text_digest

        return bg.create_strike(
            self.root,
            breakers(group_b),
            candidate_hash=text_digest(CANDIDATE),
            budget_hash="budget-1",
        )


class CanaryTests(BlackGemTestCase):
    def test_structured_costume_answer_is_caught_and_trusts_the_probe(self) -> None:
        state = self.make()
        probe = bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
        self.assertEqual(set(probe.per_seat.values()), {bg.CAUGHT})
        self.assertTrue(probe.probe_trusted)
        self.assertEqual(probe.temperature, 0.2)

    def test_costume_check_none_found_is_a_rubber_stamp(self) -> None:
        state = self.make()
        probe = bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(RUBBER_TEXT)))
        self.assertEqual(set(probe.per_seat.values()), {bg.RUBBER_STAMP})
        self.assertFalse(probe.probe_trusted)

        bg.run_strike(self.root, state.strike_id, CANDIDATE, fetch=Transport(constant(SURVIVES_TEXT)))
        loaded = bg._load(self.root, state.strike_id)
        trusted, unresolved = bg._trusted(loaded)
        self.assertFalse(trusted)
        self.assertIn("canary-rubber-stamped", unresolved)
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-1", synthesis=SURVIVES_TEXT, break_triples=[]
        )
        self.assertEqual(receipt.verdict, Verdict.UNKNOWN)

    def test_probe_passes_then_seat_goes_silent(self) -> None:
        state = self.make()
        probe = bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
        self.assertTrue(probe.probe_trusted)
        # Seat b answers the probe and then returns nothing at all for the work.
        bg.run_strike(
            self.root,
            state.strike_id,
            CANDIDATE,
            fetch=Transport(per_model({"model-a": SURVIVES_TEXT, "model-b": ""})),
        )
        loaded = bg._load(self.root, state.strike_id)
        self.assertTrue(loaded.canary["probe_trusted"])
        trusted, _ = bg._trusted(loaded)
        self.assertFalse(trusted)

    def test_empty_two_hundred_is_counted_absent_not_live(self) -> None:
        state = self.make()
        probe = bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(per_model({"model-a": CAUGHT_TEXT, "model-b": "   "})))
        self.assertEqual(probe.per_seat["b"], bg.ABSENT)
        self.assertFalse(probe.probe_trusted)


class StrikeTests(BlackGemTestCase):
    def _trusted_run(self, text_a=SURVIVES_TEXT, text_b=SURVIVES_TEXT, group_b="vendor-b"):
        state = self.make(group_b)
        bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
        result = bg.run_strike(
            self.root,
            state.strike_id,
            CANDIDATE,
            fetch=Transport(per_model({"model-a": text_a, "model-b": text_b})),
        )
        return state, result

    def test_one_seat_erroring_on_every_call_is_unavailable(self) -> None:
        state = self.make()
        bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))

        def script(body, index):
            if body["model"] == "model-b":
                return RuntimeError("HTTP 402 payment required")
            return SURVIVES_TEXT

        bg.run_strike(self.root, state.strike_id, CANDIDATE, fetch=Transport(script))
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-1", synthesis=SURVIVES_TEXT, break_triples=[]
        )
        self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)
        self.assertIn("fewer-than-two-contributing-seats-or-no-transport", receipt.unresolved)

    def test_kill_yields_issue_and_survives_yields_unknown(self) -> None:
        state, result = self._trusted_run(KILL_TEXT, KILL_TEXT)
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-kill",
            synthesis=KILL_TEXT, break_triples=result["break_triples"],
        )
        self.assertEqual(receipt.verdict, Verdict.ISSUE)
        self.assertTrue(result["break_triples"])

        state2, result2 = self._trusted_run()
        receipt2 = bg.finalize(
            self.root, state2.strike_id, "obl-survives",
            synthesis=SURVIVES_TEXT, break_triples=result2["break_triples"],
        )
        self.assertEqual(receipt2.verdict, Verdict.UNKNOWN)
        self.assertEqual(result2["break_triples"], [])

    def test_amend_is_an_issue_with_amend_required(self) -> None:
        amend = SURVIVES_TEXT.replace("VERDICT SURVIVES_TO_GATE", "VERDICT AMEND")
        state, result = self._trusted_run(amend, amend)
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-amend",
            synthesis=amend, break_triples=result["break_triples"],
        )
        self.assertEqual(receipt.verdict, Verdict.ISSUE)
        self.assertIn("amend-required", receipt.unresolved)

    def test_identical_provenance_group_is_not_independence(self) -> None:
        state, result = self._trusted_run(group_b="vendor-a")
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-1",
            synthesis=SURVIVES_TEXT, break_triples=result["break_triples"],
        )
        self.assertIn("independence-not-established", receipt.unresolved)
        self.assertEqual(receipt.verdict, Verdict.UNKNOWN)

    def test_no_path_yields_cleared(self) -> None:
        source = (ROOT / "tools" / "blackgem_runtime.py").read_text(encoding="utf-8")
        hits = [line.strip() for line in source.splitlines() if "Verdict.CLEARED" in line]
        self.assertEqual(len(hits), 1, hits)
        self.assertTrue(hits[0].startswith("assert verdict != Verdict.CLEARED"), hits[0])

    def test_injection_canary_success_marks_the_run_untrusted(self) -> None:
        state = self.make()
        bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
        result = bg.run_strike(
            self.root, state.strike_id, CANDIDATE,
            fetch=Transport(per_model({"model-a": SURVIVES_TEXT, "model-b": "OK"})),
        )
        self.assertEqual(result["injection_canary_hits"], ["b"])
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-1",
            synthesis=SURVIVES_TEXT, break_triples=result["break_triples"],
        )
        self.assertIn("injection-canary-succeeded", receipt.unresolved)
        self.assertNotEqual(receipt.verdict, Verdict.CLEARED)

    def test_system_message_is_the_frozen_rubric_and_the_brief_does_not_move_it(self) -> None:
        state = self.make()
        transport = Transport(constant(SURVIVES_TEXT))
        bg.run_strike(self.root, state.strike_id, CANDIDATE, fetch=transport)
        self.assertTrue(transport.calls)
        for call in transport.calls:
            messages = call["body"]["messages"]
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(messages[0]["content"], bg.BLACKGEM_SYSTEM)
            self.assertEqual(messages[1]["role"], "user")
            self.assertIn(bg.CANDIDATE_BEGIN, messages[1]["content"])
            self.assertIn(bg.INJECTION_CANARY, messages[1]["content"])
        loaded = bg._load(self.root, state.strike_id)
        self.assertEqual(loaded.rubric_hash, bg.RUBRIC_HASH)

    def test_cross_critique_is_off_diagonal(self) -> None:
        state = self.make()
        transport = Transport(constant(SURVIVES_TEXT))
        bg.run_strike(self.root, state.strike_id, CANDIDATE, fetch=transport)
        loaded = bg._load(self.root, state.strike_id)
        artifact = json.loads((RuntimeStore(self.root).base / "blackgem" / f"{state.strike_id}.json").read_text(encoding="utf-8"))
        cross = [row for row in artifact["strike"]["records"] if row.get("phase") == "phase2"]
        self.assertTrue(cross)
        for row in cross:
            self.assertNotEqual(row["seat_id"], row["target_seat_id"])
        self.assertEqual(loaded.phase, "SYNTHESIZED")


class ReceiptHygieneTests(BlackGemTestCase):
    def test_receipt_verifies_and_holds_no_raw_model_text(self) -> None:
        state = self.make()
        bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
        result = bg.run_strike(
            self.root, state.strike_id, CANDIDATE,
            fetch=Transport(constant(SURVIVES_TEXT)),
            checkers=(len_checker,),
        )
        receipt = bg.finalize(
            self.root, state.strike_id, "obl-1",
            synthesis=result["synthesis"], break_triples=result["break_triples"],
        )
        store = RuntimeStore(self.root)
        body = store.read_receipt(receipt.receipt_id)
        self.assertIsNotNone(body)
        self.assertTrue(verify_content_hash(body))

        needle = "run the replica divergence harness"
        declared = store.base / "blackgem" / f"{state.strike_id}.json"
        self.assertIn(needle, declared.read_text(encoding="utf-8"))
        for path in store.base.rglob("*"):
            if not path.is_file() or path == declared:
                continue
            self.assertNotIn(needle, path.read_text(encoding="utf-8", errors="replace"), str(path))

        derived = [e for e in body["evidence"] if e["evidence_class"] == "DERIVED"][0]
        self.assertEqual(derived["artifact"]["locator"], f"blackgem/{state.strike_id}.json")
        self.assertEqual([row["name"] for row in derived["metadata"]["checkers"]], ["len_checker"])
        observed = [e for e in body["evidence"] if e["evidence_class"] == "OBSERVED"]
        self.assertEqual(len(observed), 2)
        for row in observed:
            for key in ("model_id", "model_version", "temperature", "provenance_group", "answered", "expected", "empty_count"):
                self.assertIn(key, row["metadata"])

    def test_replay_with_an_adaptation_event_is_byte_identical(self) -> None:
        from egrt_store import new_id, utcnow
        from egrt_types import RuntimeEvent, digest

        outputs = []
        for inject in (False, True):
            state = self.make()
            bg.probe_canary(self.root, state.strike_id, CANARY, fetch=Transport(constant(CAUGHT_TEXT)))
            if inject:
                RuntimeStore(self.root).append_event(RuntimeEvent(
                    event_id=new_id("evt"), event_type="adaptation.applied", component="foil",
                    task_id=None, payload_hash=digest({"maximal": True}), timestamp=utcnow(),
                    metadata={"domain_count": 999, "facet_count": 999},
                ))
            result = bg.run_strike(
                self.root, state.strike_id, CANDIDATE, fetch=Transport(constant(SURVIVES_TEXT))
            )
            receipt = bg.finalize(
                self.root, state.strike_id, "obl-1",
                synthesis=result["synthesis"], break_triples=result["break_triples"],
            )
            outputs.append((receipt.verdict, receipt.output_hash, receipt.input_hash))
        self.assertEqual(outputs[0], outputs[1])


class ReleaseGateTests(BlackGemTestCase):
    def test_a_cleared_review_receipt_does_not_release_an_open_adversary_obligation(self) -> None:
        import council_runtime as council

        task = soul.start_task(self.root, "ship a claim")
        review = soul.add_obligation(self.root, task.task_id, ObligationKind.REVIEW, "reviewed")
        soul.add_obligation(self.root, task.task_id, ObligationKind.ADVERSARY, "attacked")
        seats = [
            council.CouncilSeat("s1", "formal correctness", "Is it valid?", "proof"),
            council.CouncilSeat("s2", "empirical validity", "Is it measured?", "experiment"),
            council.CouncilSeat("s3", "skeptic", "What breaks it?", "adversarial"),
        ]
        state = council.create_council(self.root, "artifact", "budget", seats, task_id=task.task_id)
        sub = council.SeatSubmission("h", ("c",), ("e",), ("p",), 0.5, ("f",))
        for seat in seats:
            council.commit(self.root, state.council_id, seat.seat_id, sub)
        for seat in seats:
            council.reveal(self.root, state.council_id, seat.seat_id, sub)
        council.record_cross_critique(self.root, state.council_id, council.CrossCritique("s1", "s2", challenged_findings=("f2",)))
        council.record_cross_critique(self.root, state.council_id, council.CrossCritique("s2", "s3", surviving_findings=("f3",)))
        council.record_cross_critique(self.root, state.council_id, council.CrossCritique("s3", "s1", challenged_findings=("f1",)))
        direct = council.record_control(
            self.root, review.obligation_id, artifact_hash="artifact", budget_hash="budget",
            kind="DIRECT", output_hash="o", verdict=Verdict.CLEARED, verifier="control",
        )
        cleared = council.finalize(
            self.root, state.council_id, review.obligation_id, synthesis_hash="s",
            supported_findings=["f"], direct_control_receipt=direct.receipt_id,
        )
        self.assertEqual(cleared.verdict, Verdict.CLEARED)

        verdict, detail = soul.release_gate(self.root, task.task_id)
        self.assertEqual(verdict, Verdict.UNKNOWN)
        missing = [row for row in detail["obligations"] if row.get("reason") == "missing-receipt"]
        self.assertEqual(len(missing), 1)


class FoilRoutingTests(BlackGemTestCase):
    def test_routing_is_always_a_superset_of_the_baseline_axes(self) -> None:
        for domains, facets in (([], []), (["math", "systems", "policy"], ["speed", "rigor"])):
            decision = bridge.select_redteam_profile(domains, facets)
            self.assertTrue(set(bridge.BASELINE_AXES).issubset(set(decision.axes)))
            self.assertEqual(
                sorted(decision.seat_a_axes + decision.seat_b_axes), sorted(decision.axes)
            )

    def test_decision_hash_is_deterministic_and_order_insensitive(self) -> None:
        one = bridge.select_redteam_profile(["b", "a"], ["y", "x"])
        two = bridge.select_redteam_profile(["a", "b"], ["x", "y"])
        self.assertEqual(one.decision_hash, two.decision_hash)
        self.assertEqual(one.seat_a_axes, two.seat_a_axes)

    def test_routing_metadata_carries_no_profile_free_text(self) -> None:
        bank = {"canary-1": "a renamed lease", "canary-2": "a renamed quorum"}
        decision = bridge.select_redteam_profile(["math"], ["rigor"], canary_bank=bank, profile={"profile_status": "ACTIVE"})
        metadata = bridge.routing_metadata(decision)
        blob = json.dumps(metadata)
        for axis in decision.axes:
            self.assertNotIn(axis, blob)
        for text in bank.values():
            self.assertNotIn(text, blob)
        self.assertTrue(metadata["baseline_axes_included"])

    def test_missing_profile_is_unavailable_never_cleared(self) -> None:
        decision = bridge.select_redteam_profile(["math"], [])
        self.assertFalse(decision.available)
        receipt = bridge.record_redteam_routing(self.root, decision)
        self.assertEqual(receipt.verdict, Verdict.UNAVAILABLE)

    def test_routing_never_clears_a_proof_obligation(self) -> None:
        task = soul.start_task(self.root, "prove a thing")
        proof = soul.add_obligation(self.root, task.task_id, ObligationKind.PROOF, "1+1=2")
        decision = bridge.select_redteam_profile(["math"], [], profile={"profile_status": "ACTIVE"})
        receipt = bridge.record_redteam_routing(self.root, decision, proof.obligation_id)
        self.assertNotEqual(receipt.verdict, Verdict.CLEARED)
        self.assertIn("obligation-not-owned-by-foil", receipt.unresolved)

    def test_routing_clears_only_an_adaptation_obligation(self) -> None:
        task = soul.start_task(self.root, "adapt")
        adaptation = soul.add_obligation(self.root, task.task_id, ObligationKind.ADAPTATION, "routed")
        decision = bridge.select_redteam_profile(["math"], [], profile={"profile_status": "ACTIVE"})
        receipt = bridge.record_redteam_routing(self.root, decision, adaptation.obligation_id)
        self.assertEqual(receipt.verdict, Verdict.CLEARED)


def len_checker(text: str) -> str:
    return str(len(text))


if __name__ == "__main__":
    unittest.main()
