"""Pure symmetric A0/B selection for evidence-closed FOIL benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_types import digest
from foil_retrieval_claim_comparator import AnswerAssessment


class SelectionOutcome(str, Enum):
    KEEP_A0_NO_CANDIDATE = "KEEP_A0_NO_CANDIDATE"
    KEEP_A0_SUPPORTED = "KEEP_A0_SUPPORTED"
    KEEP_A0_B_UNSUPPORTED = "KEEP_A0_B_UNSUPPORTED"
    KEEP_A0_NO_CONTRADICTION = "KEEP_A0_NO_CONTRADICTION"
    KEEP_A0_AUTHORITY_DISABLED = "KEEP_A0_AUTHORITY_DISABLED"
    SELECT_B_BENCHMARK_UNADMITTED = "SELECT_B_BENCHMARK_UNADMITTED"


@dataclass(frozen=True)
class SelectorPolicy:
    benchmark_selection_enabled: bool = False
    require_a0_critical_contradiction: bool = True
    production_authorized: bool = False

    def __post_init__(self) -> None:
        for name in (
            "benchmark_selection_enabled",
            "require_a0_critical_contradiction",
            "production_authorized",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.production_authorized:
            raise ValueError("evidence-closed v1 selector has no production authority")


@dataclass(frozen=True)
class SelectionReceipt:
    outcome: SelectionOutcome
    reason: str
    a0_digest: str
    candidate_digest: str | None
    selected_digest: str
    answer_changed: bool
    benchmark_only: bool = True
    production_authorized: bool = False
    promotion_authorized: bool = False

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "foil.evidence-closed-selection.v1",
            "outcome": self.outcome.value,
            "reason": self.reason,
            "a0_digest": self.a0_digest,
            "candidate_digest": self.candidate_digest,
            "selected_digest": self.selected_digest,
            "answer_changed": self.answer_changed,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "a0_fallback": True,
            "raw_answer_stored": False,
        }
        body["selection_sha256"] = digest(body)
        return body


def select_answer(
    a0: str,
    a0_assessment: AnswerAssessment,
    b_assessment: AnswerAssessment | None,
    *,
    policy: SelectorPolicy,
) -> tuple[str, SelectionReceipt]:
    """Select B only after a strict, symmetric evidence preference."""

    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(a0_assessment, AnswerAssessment):
        raise TypeError("a0_assessment must be AnswerAssessment")
    if not isinstance(policy, SelectorPolicy):
        raise TypeError("policy must be SelectorPolicy")
    a0_digest = digest(a0)
    if a0_assessment.candidate.answer_digest != a0_digest:
        raise ValueError("A0 assessment does not bind A0")
    candidate_digest = None if b_assessment is None else b_assessment.candidate.answer_digest

    if b_assessment is None:
        outcome = SelectionOutcome.KEEP_A0_NO_CANDIDATE
        reason = "constructor_produced_no_candidate"
        selected = a0
    elif a0_assessment.fully_supported and a0_assessment.selection_eligible:
        outcome = SelectionOutcome.KEEP_A0_SUPPORTED
        reason = "a0_fully_supported"
        selected = a0
    elif not b_assessment.fully_supported or not b_assessment.selection_eligible:
        outcome = SelectionOutcome.KEEP_A0_B_UNSUPPORTED
        reason = "candidate_b_not_fully_supported_and_eligible"
        selected = a0
    elif policy.require_a0_critical_contradiction and not a0_assessment.has_critical_contradiction:
        outcome = SelectionOutcome.KEEP_A0_NO_CONTRADICTION
        reason = "a0_not_critically_contradicted"
        selected = a0
    elif not policy.benchmark_selection_enabled:
        outcome = SelectionOutcome.KEEP_A0_AUTHORITY_DISABLED
        reason = "benchmark_answer_change_disabled"
        selected = a0
    else:
        outcome = SelectionOutcome.SELECT_B_BENCHMARK_UNADMITTED
        reason = "strict_evidence_preference_selected_b_in_benchmark"
        selected = b_assessment.candidate.answer

    return selected, SelectionReceipt(
        outcome,
        reason,
        a0_digest,
        candidate_digest,
        digest(selected),
        selected != a0,
    )
