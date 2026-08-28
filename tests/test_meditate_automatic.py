from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import meditate_runtime as meditate  # noqa: E402
from egrt_store import RuntimeStore, new_id, utcnow  # noqa: E402
from egrt_types import (  # noqa: E402
    Obligation,
    ObligationKind,
    RuntimeEvent,
    TaskState,
    Verdict,
    digest,
)


def init_root(path: Path) -> None:
    (path / ".gauntlet.json").write_text(
        json.dumps(
            {
                "state_dir": ".egrt/state",
                "runtime": {"automatic_preflight": True},
            }
        ),
        encoding="utf-8",
    )


def preflight_obligation() -> Obligation:
    return Obligation(
        obligation_id="obl-preflight",
        kind=ObligationKind.PREFLIGHT,
        claim="choose the next bounded action",
        required_module="meditate",
    )


def bound_state(
    root: Path,
    *,
    task_metadata: dict | None = None,
    triggers: meditate.PreflightTriggers | None = None,
) -> tuple[TaskState, Obligation, meditate.DecisionState]:
    obligation = preflight_obligation()
    task = TaskState(
        task_id="task-preflight",
        goal_hash=digest("goal"),
        obligations=[obligation],
        metadata=task_metadata or {},
    )
    RuntimeStore(root).write_task(task)
    state = meditate.DecisionState(
        decision_id="decision-1",
        task_id=task.task_id,
        goal="private goal",
        success_condition="private success condition",
        actions=[
            meditate.CandidateAction(
                action_id="inspect",
                label="private action label",
                info_rank=5,
                progress_rank=4,
                risk_reduction_rank=4,
                cost_rank=1,
            )
        ],
        triggers=triggers or meditate.PreflightTriggers(high_stakes=True),
    )
    return task, obligation, state


def append_event(
    root: Path,
    task_id: str,
    event_type: str,
    *,
    metadata: dict | None = None,
) -> None:
    RuntimeStore(root).append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type=event_type,
            component="test",
            task_id=task_id,
            payload_hash=digest({"event_type": event_type, "metadata": metadata}),
            timestamp=utcnow(),
            metadata=metadata or {},
        )
    )


class MeditateValidationTests(unittest.TestCase):
    def test_trigger_flags_are_strict_booleans(self) -> None:
        with self.assertRaises(TypeError):
            meditate.PreflightTriggers(high_stakes=1)

    def test_quantitative_values_must_be_finite(self) -> None:
        with self.assertRaises(ValueError):
            meditate.QuantitativeOutcome(0.5, math.inf)
        with self.assertRaises(ValueError):
            meditate.CandidateAction("a", "A", cost=math.nan)

    def test_voc_overflow_fails_closed(self) -> None:
        action = meditate.CandidateAction(
            "a",
            "A",
            cost=0.0,
            outcomes=(meditate.QuantitativeOutcome(1.0, 1.79e308),),
        )
        with self.assertRaises(ValueError):
            action.voc(-1.79e308)

    def test_candidate_ids_must_be_unique(self) -> None:
        action = meditate.CandidateAction("a", "A")
        with self.assertRaises(ValueError):
            meditate.DecisionState(
                "d",
                None,
                "goal",
                "success",
                actions=[action, action],
            )

    def test_partial_quantitative_model_never_falls_back_to_ordinal(self) -> None:
        state = meditate.DecisionState(
            "d",
            None,
            "goal",
            "success",
            current_best_eu=0.0,
            actions=[
                meditate.CandidateAction(
                    "a",
                    "A",
                    cost=1.0,
                    info_rank=5,
                    progress_rank=5,
                    risk_reduction_rank=5,
                    cost_rank=1,
                ),
                meditate.CandidateAction(
                    "b",
                    "B",
                    info_rank=1,
                    progress_rank=1,
                    risk_reduction_rank=1,
                    cost_rank=1,
                ),
            ],
            triggers=meditate.PreflightTriggers(high_stakes=True),
        )
        result = meditate.recommend(state)
        self.assertEqual(result["verdict"], Verdict.UNKNOWN.value)
        self.assertEqual(result["mode"], "PARTIAL_QUANTITATIVE_MODEL")

    def test_quantitative_tie_is_unknown_and_order_invariant(self) -> None:
        first = meditate.CandidateAction(
            "a",
            "A",
            cost=0.0,
            outcomes=(meditate.QuantitativeOutcome(1.0, 2.0),),
        )
        second = meditate.CandidateAction(
            "b",
            "B",
            cost=0.0,
            outcomes=(meditate.QuantitativeOutcome(1.0, 2.0),),
        )
        base = meditate.DecisionState(
            "d",
            None,
            "goal",
            "success",
            current_best_eu=0.0,
            actions=[first, second],
            triggers=meditate.PreflightTriggers(high_stakes=True),
        )
        reversed_state = replace(base, actions=[second, first])
        left = meditate.recommend(base)
        right = meditate.recommend(reversed_state)
        self.assertEqual(left, right)
        self.assertEqual(left["mode"], "QUANTITATIVE_TIE")
        self.assertEqual(left["nondominated"], ["a", "b"])

    def test_irreversible_candidate_is_an_automatic_trigger(self) -> None:
        state = meditate.DecisionState(
            "d",
            None,
            "goal",
            "success",
            actions=[
                meditate.CandidateAction(
                    "a",
                    "A",
                    info_rank=1,
                    progress_rank=1,
                    risk_reduction_rank=1,
                    cost_rank=1,
                    reversible=False,
                )
            ],
        )
        result = meditate.recommend(state)
        self.assertNotEqual(result["mode"], "NOT_TRIGGERED")
        self.assertTrue(result["effective_triggers"]["irreversible"])


class MeditateAutomaticTests(unittest.TestCase):
    def test_stale_authority_and_repeated_failure_are_derived_from_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task, _, state = bound_state(root)
            append_event(root, task.task_id, "authority.snapshot")
            append_event(root, task.task_id, "authority.changed")
            append_event(
                root,
                task.task_id,
                "action.failed",
                metadata={"failure_signature": "same"},
            )
            append_event(
                root,
                task.task_id,
                "action.failed",
                metadata={"failure_signature": "same"},
            )
            triggers = meditate.derive_triggers(root, task.task_id, state)
            self.assertTrue(triggers.stale_authority)
            self.assertTrue(triggers.repeated_failure)

    def test_earlier_major_disagreement_is_not_erased_by_later_minor_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task, _, state = bound_state(root)
            append_event(
                root,
                task.task_id,
                "review.disagreement",
                metadata={"major": True},
            )
            append_event(
                root,
                task.task_id,
                "review.disagreement",
                metadata={"major": False},
            )
            triggers = meditate.derive_triggers(root, task.task_id, state)
            self.assertTrue(triggers.major_disagreement)

    def test_bound_run_cannot_bypass_automatic_task_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            _, obligation, state = bound_state(
                root,
                task_metadata={"high_stakes": True},
                triggers=meditate.PreflightTriggers(),
            )
            receipt = meditate.run_preflight(root, state, obligation.obligation_id)
            detail = json.loads(receipt.notes)
            self.assertTrue(detail["effective_triggers"]["high_stakes"])
            self.assertEqual(detail["decision"], "ACT")

    def test_bound_receipt_has_preflight_only_authority_and_task_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            task, obligation, state = bound_state(root)
            receipt = meditate.run_automatic_preflight(
                root,
                state,
                obligation.obligation_id,
            )
            self.assertEqual(receipt.task_id, task.task_id)
            self.assertEqual(receipt.verdict, Verdict.CLEARED)
            detail = json.loads(receipt.notes)
            self.assertEqual(detail["authority"], "PREFLIGHT_ONLY")
            self.assertFalse(detail["execution_authorized"])
            self.assertFalse(detail["target_domain_clearance_authorized"])
            evidence = receipt.evidence[0].metadata
            self.assertRegex(evidence["task_content_hash"], r"^[0-9a-f]{64}$")
            self.assertRegex(evidence["obligation_binding_hash"], r"^[0-9a-f]{64}$")

    def test_wrong_obligation_kind_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = Obligation(
                "obl-proof",
                ObligationKind.PROOF,
                "prove",
                required_module="mind",
            )
            task = TaskState("task", digest("goal"), obligations=[obligation])
            RuntimeStore(root).write_task(task)
            state = meditate.DecisionState(
                "d",
                task.task_id,
                "goal",
                "success",
                actions=[
                    meditate.CandidateAction(
                        "a",
                        "A",
                        info_rank=1,
                        progress_rank=1,
                        risk_reduction_rank=1,
                        cost_rank=1,
                    )
                ],
                triggers=meditate.PreflightTriggers(high_stakes=True),
            )
            with self.assertRaises(meditate.MeditateAuthorityError):
                meditate.run_preflight(root, state, obligation.obligation_id)

    def test_inactive_or_released_task_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = preflight_obligation()
            task = TaskState(
                "task-closed",
                digest("goal"),
                obligations=[obligation],
                active=False,
            )
            RuntimeStore(root).write_task(task)
            state = meditate.DecisionState(
                "d",
                task.task_id,
                "goal",
                "success",
                actions=[
                    meditate.CandidateAction(
                        "a",
                        "A",
                        info_rank=1,
                        progress_rank=1,
                        risk_reduction_rank=1,
                        cost_rank=1,
                    )
                ],
                triggers=meditate.PreflightTriggers(high_stakes=True),
            )
            with self.assertRaises(meditate.MeditateAuthorityError):
                meditate.run_preflight(root, state, obligation.obligation_id)

    def test_inference_selects_the_unique_active_successor_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            obligation = preflight_obligation()
            predecessor = TaskState(
                "task-old",
                digest("goal"),
                obligations=[obligation],
                active=False,
            )
            successor = TaskState(
                "task-current",
                digest("goal"),
                obligations=[obligation],
            )
            store = RuntimeStore(root)
            store.write_task(predecessor)
            store.write_task(successor)
            state = meditate.DecisionState(
                "d",
                None,
                "goal",
                "success",
                actions=[
                    meditate.CandidateAction(
                        "a",
                        "A",
                        info_rank=1,
                        progress_rank=1,
                        risk_reduction_rank=1,
                        cost_rank=1,
                    )
                ],
                triggers=meditate.PreflightTriggers(high_stakes=True),
            )
            receipt = meditate.run_automatic_preflight(
                root,
                state,
                obligation.obligation_id,
            )
            self.assertEqual(receipt.task_id, successor.task_id)

    def test_unbound_clearing_result_is_demoted_to_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            state = meditate.DecisionState(
                "d",
                None,
                "goal",
                "success",
                actions=[
                    meditate.CandidateAction(
                        "a",
                        "A",
                        info_rank=1,
                        progress_rank=1,
                        risk_reduction_rank=1,
                        cost_rank=1,
                    )
                ],
                triggers=meditate.PreflightTriggers(high_stakes=True),
            )
            receipt = meditate.run_preflight(root, state, "unbound")
            self.assertEqual(receipt.verdict, Verdict.UNKNOWN)
            self.assertEqual(json.loads(receipt.notes)["mode"], "UNBOUND_PREFLIGHT")

    def test_private_state_persists_hashes_not_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_root(root)
            _, obligation, state = bound_state(root)
            meditate.run_preflight(root, state, obligation.obligation_id)
            raw = (
                RuntimeStore(root).base / "meditate" / f"{state.decision_id}.json"
            ).read_text(encoding="utf-8")
            self.assertNotIn(state.goal, raw)
            self.assertNotIn(state.success_condition, raw)
            self.assertNotIn(state.actions[0].label, raw)
            self.assertIn("raw_goal_persisted", raw)
            self.assertIn("task_content_hash", raw)
            self.assertIn("obligation_binding_hash", raw)


if __name__ == "__main__":
    unittest.main()
