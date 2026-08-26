"""Deterministic FOIL assistance-rung selection.

The evidence estimator decides what can be claimed about demonstrated
competence. This module consumes only that typed classification plus explicit
task intent/demand flags. It never reads answer text, never writes a profile,
and never turns assisted work into competence evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from foil_assistance import Assistance, parse_assistance
from foil_evidence import Classification, PosteriorSummary

SCHEMA = "egrt.foil-assistance-decision.v1"

__all__ = [
    "SCHEMA",
    "AssistanceDecision",
    "AssistanceIntent",
    "AssistanceReason",
    "TaskDemand",
    "advance_assistance_floor",
    "select_assistance",
]


class AssistanceIntent(str, Enum):
    """The user's explicit interaction mode."""

    ADAPTIVE = "ADAPTIVE"
    TEACH = "TEACH"
    SOLVE = "SOLVE"


class TaskDemand(str, Enum):
    """A host-supplied task-demand band; never inferred from the answer."""

    ROUTINE = "ROUTINE"
    CHALLENGING = "CHALLENGING"
    HARD = "HARD"


class AssistanceReason(str, Enum):
    DIRECT_SOLVE_REQUESTED = "DIRECT_SOLVE_REQUESTED"
    DEADLINE_OR_DELIVERABLE = "DEADLINE_OR_DELIVERABLE"
    OWNERSHIP_PROBE_DUE = "OWNERSHIP_PROBE_DUE"
    STRENGTH_FADE_TO_INDEPENDENT = "STRENGTH_FADE_TO_INDEPENDENT"
    GAP_SCAFFOLD = "GAP_SCAFFOLD"
    COLD_START_MINIMUM = "COLD_START_MINIMUM"
    ESCALATION_FLOOR = "ESCALATION_FLOOR"


@dataclass(frozen=True)
class AssistanceDecision:
    assistance: Assistance
    reason: AssistanceReason
    classification: Classification
    intent: AssistanceIntent
    demand: TaskDemand
    deadline: bool
    deliverable: bool
    ownership_probe_due: bool
    minimum_assistance: Assistance

    def trace(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "assistance": self.assistance.value,
            "reason": self.reason.value,
            "classification": self.classification.value,
            "intent": self.intent.value,
            "demand": self.demand.value,
            "deadline": self.deadline,
            "deliverable": self.deliverable,
            "ownership_probe_due": self.ownership_probe_due,
            "minimum_assistance": self.minimum_assistance.value,
        }


def _enum(value: object, kind: type[Enum], label: str):
    if isinstance(value, kind):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{label} must be {kind.__name__} or str")
    try:
        return kind(value.strip().upper())
    except ValueError as exc:
        raise ValueError(f"unknown {label}: {value!r}") from exc


def _classification(value: Classification | PosteriorSummary | str) -> Classification:
    if isinstance(value, PosteriorSummary):
        return value.classification
    return _enum(value, Classification, "classification")


def select_assistance(
    *,
    classification: Classification | PosteriorSummary | str,
    intent: AssistanceIntent | str = AssistanceIntent.ADAPTIVE,
    demand: TaskDemand | str = TaskDemand.CHALLENGING,
    deadline: bool = False,
    deliverable: bool = False,
    ownership_probe_due: bool = False,
    minimum_assistance: Assistance | str | None = None,
) -> AssistanceDecision:
    """Choose exactly one rung using explicit, answer-independent state.

    Direct-solve, deadline, and deliverable requests are never converted into
    compulsory tutoring. Teaching/adaptive modes start at A1, escalate only
    through a host-supplied floor earned by an observed failure, periodically
    permit an A0 ownership probe without erasing that floor, and fade to A0
    after the estimator has earned a strength classification.
    """

    for label, value in (
        ("deadline", deadline),
        ("deliverable", deliverable),
        ("ownership_probe_due", ownership_probe_due),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"{label} must be bool")
    resolved_classification = _classification(classification)
    resolved_intent = _enum(intent, AssistanceIntent, "intent")
    resolved_demand = _enum(demand, TaskDemand, "demand")
    resolved_floor = (
        Assistance.A0_INDEPENDENT
        if minimum_assistance is None
        else parse_assistance(minimum_assistance)
    )

    if resolved_intent is AssistanceIntent.SOLVE:
        rung, reason = Assistance.A4_DIRECT_SOLVE, AssistanceReason.DIRECT_SOLVE_REQUESTED
    elif deadline or deliverable:
        rung, reason = Assistance.A4_DIRECT_SOLVE, AssistanceReason.DEADLINE_OR_DELIVERABLE
    elif ownership_probe_due:
        rung, reason = Assistance.A0_INDEPENDENT, AssistanceReason.OWNERSHIP_PROBE_DUE
    elif resolved_classification is Classification.PROMISING_STRENGTH:
        rung, reason = (
            Assistance.A0_INDEPENDENT,
            AssistanceReason.STRENGTH_FADE_TO_INDEPENDENT,
        )
    elif resolved_classification is Classification.POSSIBLE_GAP:
        rung, reason = Assistance.A2_SCAFFOLD, AssistanceReason.GAP_SCAFFOLD
    else:
        rung, reason = Assistance.A1_MICRO_HINT, AssistanceReason.COLD_START_MINIMUM

    if (
        rung not in {Assistance.A0_INDEPENDENT, Assistance.A4_DIRECT_SOLVE}
        and resolved_floor.rung > rung.rung
    ):
        rung, reason = resolved_floor, AssistanceReason.ESCALATION_FLOOR

    return AssistanceDecision(
        assistance=rung,
        reason=reason,
        classification=resolved_classification,
        intent=resolved_intent,
        demand=resolved_demand,
        deadline=deadline,
        deliverable=deliverable,
        ownership_probe_due=ownership_probe_due,
        minimum_assistance=resolved_floor,
    )


def _next_assistance(current: Assistance) -> Assistance:
    ladder = list(Assistance)
    return ladder[min(current.rung + 1, Assistance.A4_DIRECT_SOLVE.rung)]


def advance_assistance_floor(
    *,
    current: Assistance | str,
    decision: AssistanceDecision,
    observed_outcome: bool,
) -> Assistance:
    """Advance the persistent floor from an observed attempt, never from prose.

    Ownership probes and explicit direct-solve/deadline requests leave the
    existing floor unchanged. A normal successful rung becomes the new floor;
    a failed normal rung moves exactly one step upward. The decision must carry
    the same prior floor so a caller cannot splice unrelated state.
    """

    resolved = parse_assistance(current)
    if not isinstance(decision, AssistanceDecision):
        raise TypeError("decision must be AssistanceDecision")
    if not isinstance(observed_outcome, bool):
        raise TypeError("observed_outcome must be bool")
    if decision.minimum_assistance is not resolved:
        raise ValueError("decision minimum_assistance does not match current floor")
    if decision.reason in {
        AssistanceReason.DIRECT_SOLVE_REQUESTED,
        AssistanceReason.DEADLINE_OR_DELIVERABLE,
        AssistanceReason.OWNERSHIP_PROBE_DUE,
        AssistanceReason.STRENGTH_FADE_TO_INDEPENDENT,
    }:
        return resolved
    if observed_outcome:
        return (
            decision.assistance
            if decision.assistance.rung > resolved.rung
            else resolved
        )
    return _next_assistance(decision.assistance)
