"""Evidence-bound calibration for FOIL's no-tools interjection routes.

Host verification and model interjection are different mechanisms.  A
precommitted deterministic host check may retain benchmark correction authority
because it supplies mechanical evidence at zero model cost.  Same-context review
and blind-rival generation need empirical value evidence and remain disabled
when their conservative route decisions do not execute.
"""

from __future__ import annotations

from dataclasses import dataclass

from foil_rps_v063 import RPSV063Policy
from foil_smart_tool_calibration import CalibrationStatus, HistoricalRouteDecision


@dataclass(frozen=True)
class Stage1DiagnosticEvidence:
    rows: int
    rescues: int
    damages: int
    added_total_tokens: int
    source_classification: str

    def __post_init__(self) -> None:
        for name in ("rows", "rescues", "damages", "added_total_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.rescues + self.damages > self.rows:
            raise ValueError("rescues plus damages cannot exceed rows")
        if not isinstance(
            self.source_classification, str
        ) or not self.source_classification.strip():
            raise ValueError("source_classification must be non-empty text")


@dataclass(frozen=True)
class RPSInterjectionCalibration:
    same_context_review: HistoricalRouteDecision
    blind_rival: HistoricalRouteDecision
    stage1: Stage1DiagnosticEvidence
    runtime_policy: RPSV063Policy
    host_verified_selection_enabled: bool
    same_context_review_enabled: bool
    blind_rival_enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.same_context_review, HistoricalRouteDecision):
            raise TypeError("same_context_review must be HistoricalRouteDecision")
        if not isinstance(self.blind_rival, HistoricalRouteDecision):
            raise TypeError("blind_rival must be HistoricalRouteDecision")
        if not isinstance(self.stage1, Stage1DiagnosticEvidence):
            raise TypeError("stage1 must be Stage1DiagnosticEvidence")
        if not isinstance(self.runtime_policy, RPSV063Policy):
            raise TypeError("runtime_policy must be RPSV063Policy")
        for name in (
            "host_verified_selection_enabled",
            "same_context_review_enabled",
            "blind_rival_enabled",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.runtime_policy.max_blind_rivals != int(self.blind_rival_enabled):
            raise ValueError("runtime rival ceiling must match calibration")
        if self.runtime_policy.enabled is not self.host_verified_selection_enabled:
            raise ValueError("runtime enabled state must match host-verifier selection")

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.rps-interjection-calibration.v1",
            "host_verified_selection_enabled": self.host_verified_selection_enabled,
            "same_context_review_enabled": self.same_context_review_enabled,
            "blind_rival_enabled": self.blind_rival_enabled,
            "runtime_policy": {
                "enabled": self.runtime_policy.enabled,
                "benchmark_only": self.runtime_policy.benchmark_only,
                "max_blind_rivals": self.runtime_policy.max_blind_rivals,
                "max_answer_changes": self.runtime_policy.max_answer_changes,
                "production_authorized": False,
            },
            "same_context_review_evidence": self.same_context_review.trace(),
            "blind_rival_evidence": self.blind_rival.trace(),
            "stage1_diagnostic": {
                "rows": self.stage1.rows,
                "rescues": self.stage1.rescues,
                "damages": self.stage1.damages,
                "added_total_tokens": self.stage1.added_total_tokens,
                "source_classification": self.stage1.source_classification,
                "promotion_evidence": False,
            },
            "host_decline_action": (
                "REQUEST_BLIND_RIVAL" if self.blind_rival_enabled else "KEEP_BASE"
            ),
            "host_contradiction_without_unique_result": "ABSTAIN",
        }


def calibrate_rps_interjection(
    *,
    same_context_review: HistoricalRouteDecision,
    blind_rival: HistoricalRouteDecision,
    stage1: Stage1DiagnosticEvidence,
) -> RPSInterjectionCalibration:
    """Build the active benchmark policy from already-scored route evidence."""

    if not isinstance(same_context_review, HistoricalRouteDecision):
        raise TypeError("same_context_review must be HistoricalRouteDecision")
    if not isinstance(blind_rival, HistoricalRouteDecision):
        raise TypeError("blind_rival must be HistoricalRouteDecision")
    if not isinstance(stage1, Stage1DiagnosticEvidence):
        raise TypeError("stage1 must be Stage1DiagnosticEvidence")
    same_context_enabled = same_context_review.status is CalibrationStatus.EXECUTE
    blind_rival_enabled = blind_rival.status is CalibrationStatus.EXECUTE
    return RPSInterjectionCalibration(
        same_context_review=same_context_review,
        blind_rival=blind_rival,
        stage1=stage1,
        runtime_policy=RPSV063Policy(
            enabled=True,
            benchmark_only=True,
            max_blind_rivals=int(blind_rival_enabled),
            max_answer_changes=1,
        ),
        host_verified_selection_enabled=True,
        same_context_review_enabled=same_context_enabled,
        blind_rival_enabled=blind_rival_enabled,
    )
