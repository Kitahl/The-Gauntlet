from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_assistance import Assistance  # noqa: E402
from foil_assistance_policy import (  # noqa: E402
    AssistanceIntent,
    AssistanceReason,
    TaskDemand,
    advance_assistance_floor,
    select_assistance,
)
from foil_evidence import Classification, EvidenceTier, Observation, summarize  # noqa: E402


class AssistancePolicyTests(unittest.TestCase):
    def test_solve_deadline_and_deliverable_never_force_tutoring(self) -> None:
        cases = (
            dict(intent=AssistanceIntent.SOLVE),
            dict(deadline=True),
            dict(deliverable=True),
        )
        for case in cases:
            with self.subTest(case=case):
                decision = select_assistance(
                    classification=Classification.POSSIBLE_GAP,
                    demand=TaskDemand.HARD,
                    **case,
                )
                self.assertIs(decision.assistance, Assistance.A4_DIRECT_SOLVE)

    def test_teach_starts_low_for_every_task_demand(self) -> None:
        for demand in TaskDemand:
            with self.subTest(demand=demand):
                decision = select_assistance(
                    classification=Classification.INSUFFICIENT_EVIDENCE,
                    intent=AssistanceIntent.TEACH,
                    demand=demand,
                )
                self.assertIs(decision.assistance, Assistance.A1_MICRO_HINT)
                self.assertIs(decision.reason, AssistanceReason.COLD_START_MINIMUM)

    def test_four_real_work_successes_fade_to_independent(self) -> None:
        summary = summarize([Observation(True, EvidenceTier.REAL_WORK) for _ in range(4)])
        self.assertIs(summary.classification, Classification.PROMISING_STRENGTH)
        decision = select_assistance(
            classification=summary,
            intent=AssistanceIntent.TEACH,
            demand=TaskDemand.HARD,
            minimum_assistance=Assistance.A4_DIRECT_SOLVE,
        )
        self.assertIs(decision.assistance, Assistance.A0_INDEPENDENT)
        self.assertIs(decision.reason, AssistanceReason.STRENGTH_FADE_TO_INDEPENDENT)

    def test_assisted_successes_never_trigger_fade_or_preemptive_escalation(self) -> None:
        summary = summarize([Observation(True, EvidenceTier.ASSISTED) for _ in range(100)])
        decision = select_assistance(
            classification=summary,
            intent=AssistanceIntent.TEACH,
            demand=TaskDemand.HARD,
        )
        self.assertIs(summary.classification, Classification.INSUFFICIENT_EVIDENCE)
        self.assertIs(decision.assistance, Assistance.A1_MICRO_HINT)

    def test_observed_failure_can_raise_persistent_floor_one_rung(self) -> None:
        decision = select_assistance(
            classification=Classification.INSUFFICIENT_EVIDENCE,
            intent=AssistanceIntent.TEACH,
            demand=TaskDemand.HARD,
            minimum_assistance=Assistance.A2_SCAFFOLD,
        )
        self.assertIs(decision.assistance, Assistance.A2_SCAFFOLD)
        self.assertIs(decision.reason, AssistanceReason.ESCALATION_FLOOR)
        probe = select_assistance(
            classification=Classification.INSUFFICIENT_EVIDENCE,
            ownership_probe_due=True,
            minimum_assistance=Assistance.A2_SCAFFOLD,
        )
        self.assertIs(probe.assistance, Assistance.A0_INDEPENDENT)
        self.assertIs(probe.minimum_assistance, Assistance.A2_SCAFFOLD)

    def test_floor_transition_is_production_owned_and_one_rung_at_a_time(self) -> None:
        first = select_assistance(
            classification=Classification.INSUFFICIENT_EVIDENCE,
            minimum_assistance=Assistance.A0_INDEPENDENT,
        )
        floor = advance_assistance_floor(
            current=Assistance.A0_INDEPENDENT,
            decision=first,
            observed_outcome=False,
        )
        self.assertIs(floor, Assistance.A2_SCAFFOLD)
        second = select_assistance(
            classification=Classification.INSUFFICIENT_EVIDENCE,
            minimum_assistance=floor,
        )
        self.assertIs(second.assistance, Assistance.A2_SCAFFOLD)
        self.assertIs(
            advance_assistance_floor(current=floor, decision=second, observed_outcome=True),
            Assistance.A2_SCAFFOLD,
        )

    def test_probe_and_direct_solve_preserve_existing_floor(self) -> None:
        for decision in (
            select_assistance(
                classification=Classification.INSUFFICIENT_EVIDENCE,
                minimum_assistance=Assistance.A3_PARTIAL_WORKED,
                ownership_probe_due=True,
            ),
            select_assistance(
                classification=Classification.INSUFFICIENT_EVIDENCE,
                minimum_assistance=Assistance.A3_PARTIAL_WORKED,
                intent=AssistanceIntent.SOLVE,
            ),
        ):
            with self.subTest(reason=decision.reason):
                self.assertIs(
                    advance_assistance_floor(
                        current=Assistance.A3_PARTIAL_WORKED,
                        decision=decision,
                        observed_outcome=False,
                    ),
                    Assistance.A3_PARTIAL_WORKED,
                )

    def test_floor_transition_rejects_spliced_state(self) -> None:
        decision = select_assistance(
            classification=Classification.INSUFFICIENT_EVIDENCE,
            minimum_assistance=Assistance.A2_SCAFFOLD,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            advance_assistance_floor(
                current=Assistance.A1_MICRO_HINT,
                decision=decision,
                observed_outcome=False,
            )

    def test_due_ownership_probe_temporarily_reduces_assistance(self) -> None:
        decision = select_assistance(
            classification=Classification.POSSIBLE_GAP,
            intent=AssistanceIntent.TEACH,
            demand=TaskDemand.HARD,
            ownership_probe_due=True,
        )
        self.assertIs(decision.assistance, Assistance.A0_INDEPENDENT)
        self.assertIs(decision.reason, AssistanceReason.OWNERSHIP_PROBE_DUE)

    def test_trace_is_closed_and_answer_free(self) -> None:
        trace = select_assistance(
            classification="UNCERTAIN", intent="TEACH", demand="ROUTINE"
        ).trace()
        self.assertEqual(
            set(trace),
            {
                "schema", "assistance", "reason", "classification", "intent",
                "demand", "deadline", "deliverable", "ownership_probe_due",
                "minimum_assistance",
            },
        )
        self.assertNotIn("answer", trace)

    def test_unknown_inputs_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            select_assistance(classification="EXPERT")
        with self.assertRaises(ValueError):
            select_assistance(classification="UNCERTAIN", demand="EXTREME")
        with self.assertRaises(ValueError):
            select_assistance(classification="UNCERTAIN", minimum_assistance="A9")
        with self.assertRaises(TypeError):
            select_assistance(classification="UNCERTAIN", deadline=1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
