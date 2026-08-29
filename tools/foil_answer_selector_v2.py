"""Conservative, evidence-symmetric answer selection for FOIL v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_types import digest
from foil_evidence_contract import CandidateOrigin
from foil_retrieval_claim_comparator import AnswerAssessment


class SelectionOutcomeV2(str, Enum):
    KEEP_A0_NO_CANDIDATE = "KEEP_A0_NO_CANDIDATE"
    KEEP_A0_SUPPORTED = "KEEP_A0_SUPPORTED"
    KEEP_A0_B_UNSUPPORTED = "KEEP_A0_B_UNSUPPORTED"
    KEEP_A0_NO_CRITICAL_CONTRADICTION = "KEEP_A0_NO_CRITICAL_CONTRADICTION"
    KEEP_A0_AUTHORITY_DISABLED = "KEEP_A0_AUTHORITY_DISABLED"
    SELECT_B_ACTIVE_UNADMITTED = "SELECT_B_ACTIVE_UNADMITTED"


@dataclass(frozen=True)
class SelectorPolicyV2:
    answer_change_enabled: bool = False
    require_a0_critical_contradiction: bool = True
    production_authorized: bool = False

    def __post_init__(self) -> None:
        for name in (
            "answer_change_enabled", "require_a0_critical_contradiction",
            "production_authorized",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.production_authorized:
            raise ValueError("FOIL v2 selection is unadmitted and has no production authority")


@dataclass(frozen=True)
class SelectionReceiptV2:
    outcome: SelectionOutcomeV2
    reason: str
    evidence_packet_digest: str
    a0_digest: str
    candidate_digest: str | None
    selected_digest: str
    selected_origin: CandidateOrigin
    answer_changed: bool
    production_authorized: bool = False

    def trace(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "foil.answer-selection.v2",
            "outcome": self.outcome.value,
            "reason": self.reason,
            "evidence_packet_sha256": self.evidence_packet_digest,
            "a0_sha256": self.a0_digest,
            "candidate_sha256": self.candidate_digest,
            "selected_sha256": self.selected_digest,
            "selected_origin": self.selected_origin.value,
            "answer_changed": self.answer_changed,
            "production_authorized": False,
            "same_evidence_required": True,
            "a0_fallback": True,
        }
        body["selection_sha256"] = digest(body)
        return body


def select_answer_v2(
    a0: str,
    a0_assessment: AnswerAssessment,
    b_assessment: AnswerAssessment | None,
    *,
    evidence_packet_digest: str,
    policy: SelectorPolicyV2,
) -> tuple[str, SelectionReceiptV2]:
    if not isinstance(a0, str) or not a0.strip():
        raise ValueError("a0 must be non-empty text")
    if not isinstance(a0_assessment, AnswerAssessment):
        raise TypeError("a0_assessment must be AnswerAssessment")
    if not isinstance(policy, SelectorPolicyV2):
        raise TypeError("policy must be SelectorPolicyV2")
    if not isinstance(evidence_packet_digest, str) or len(evidence_packet_digest) != 64:
        raise ValueError("evidence_packet_digest must be SHA-256 hex")
    a0_digest = digest(a0)
    if a0_assessment.candidate.answer_digest != a0_digest:
        raise ValueError("A0 assessment does not bind A0")
    candidate_digest = None if b_assessment is None else b_assessment.candidate.answer_digest

    if b_assessment is None:
        outcome = SelectionOutcomeV2.KEEP_A0_NO_CANDIDATE
        reason = "no_evidence_constructed_candidate"
        selected = a0
        origin = CandidateOrigin.BASE
    elif a0_assessment.fully_supported and a0_assessment.selection_eligible:
        outcome = SelectionOutcomeV2.KEEP_A0_SUPPORTED
        reason = "a0_fully_supported"
        selected = a0
        origin = CandidateOrigin.BASE
    elif not b_assessment.fully_supported or not b_assessment.selection_eligible:
        outcome = SelectionOutcomeV2.KEEP_A0_B_UNSUPPORTED
        reason = "candidate_b_not_fully_supported_and_eligible"
        selected = a0
        origin = CandidateOrigin.BASE
    elif policy.require_a0_critical_contradiction and not a0_assessment.has_critical_contradiction:
        outcome = SelectionOutcomeV2.KEEP_A0_NO_CRITICAL_CONTRADICTION
        reason = "a0_not_critically_contradicted"
        selected = a0
        origin = CandidateOrigin.BASE
    elif not policy.answer_change_enabled:
        outcome = SelectionOutcomeV2.KEEP_A0_AUTHORITY_DISABLED
        reason = "active_answer_change_disabled"
        selected = a0
        origin = CandidateOrigin.BASE
    else:
        outcome = SelectionOutcomeV2.SELECT_B_ACTIVE_UNADMITTED
        reason = "strict_mechanical_evidence_preference_selected_b"
        selected = b_assessment.candidate.answer
        origin = b_assessment.candidate.origin

    return selected, SelectionReceiptV2(
        outcome,
        reason,
        evidence_packet_digest,
        a0_digest,
        candidate_digest,
        digest(selected),
        origin,
        selected != a0,
    )
