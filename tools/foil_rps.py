"""Default-off shadow controller for FOIL Residual Parity Search.

RPS v0.6.0 was a prompt-only experiment. This module makes one load-bearing
part deterministic: a parity PASS may recommend fast acceptance only when the
check covers the fragile decision hinge and can distinguish the provisional
candidate from a live challenger (or is an exact relation).

The module consumes host/model-supplied digests. It does not generate checks,
call a model/tool/network, mutate an answer, or grant execution authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CheckKind(str, Enum):
    EXACT_RELATION = "EXACT_RELATION"
    INVARIANT = "INVARIANT"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    NECESSARY_CONSEQUENCE = "NECESSARY_CONSEQUENCE"
    PAIRWISE_DISCRIMINATOR = "PAIRWISE_DISCRIMINATOR"
    REPRESENTATION_CONSISTENCY = "REPRESENTATION_CONSISTENCY"


class CheckOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HingeCoverage(str, Enum):
    NONE = "NONE"
    SUPPORTING = "SUPPORTING"
    DECISIVE = "DECISIVE"


class RPSRecommendation(str, Enum):
    STAND_DOWN = "STAND_DOWN"
    FAST_ACCEPT = "FAST_ACCEPT"
    RUN_P2 = "RUN_P2"
    LOCAL_REPAIR = "LOCAL_REPAIR"
    ABSTAIN = "ABSTAIN"


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _optional_digest(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_digest(name, value)


@dataclass(frozen=True)
class RPSShadowPolicy:
    """Feature gate for measurement-only RPS routing."""

    enabled: bool = False
    observe_only: bool = True
    max_primary_checks: int = 1
    max_secondary_checks: int = 1
    max_local_repairs: int = 1
    max_full_restarts: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.observe_only, bool):
            raise TypeError("enabled and observe_only must be bool")
        if self.observe_only is not True:
            raise ValueError("RPS v0.6.1 is shadow-only until prospective promotion")
        ceilings = (
            ("max_primary_checks", self.max_primary_checks, 1),
            ("max_secondary_checks", self.max_secondary_checks, 1),
            ("max_local_repairs", self.max_local_repairs, 1),
            ("max_full_restarts", self.max_full_restarts, 0),
        )
        for name, value, _expected in ceilings:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
        if (
            self.max_primary_checks != 1
            or self.max_secondary_checks != 1
            or self.max_local_repairs != 1
            or self.max_full_restarts != 0
        ):
            raise ValueError("RPS v0.6.1 stop-law ceilings are frozen")


@dataclass(frozen=True)
class ReasoningCapsule:
    """Digest-only public identity for a provisional answer and its hinges."""

    candidate_digest: str
    hinge_digests: tuple[str, ...]
    fragile_hinge: int
    answer_form_digest: str

    def __post_init__(self) -> None:
        _require_digest("candidate_digest", self.candidate_digest)
        _require_digest("answer_form_digest", self.answer_form_digest)
        if not isinstance(self.hinge_digests, tuple):
            raise TypeError("hinge_digests must be a tuple")
        if not 1 <= len(self.hinge_digests) <= 3:
            raise ValueError("a reasoning capsule must contain one to three hinges")
        for value in self.hinge_digests:
            _require_digest("hinge_digest", value)
        if len(set(self.hinge_digests)) != len(self.hinge_digests):
            raise ValueError("hinge digests must be unique")
        if isinstance(self.fragile_hinge, bool) or not isinstance(self.fragile_hinge, int):
            raise TypeError("fragile_hinge must be int")
        if not 0 <= self.fragile_hinge < len(self.hinge_digests):
            raise ValueError("fragile_hinge is outside the capsule")


@dataclass(frozen=True)
class ParityObservation:
    """Structured result of one already-performed parity check.

    Expected and observed values are content digests. Equal candidate and
    challenger predictions prove that a check is non-discriminating, even when
    the observed value matches both.
    """

    check_id: str
    kind: CheckKind
    hinge_index: int
    candidate_expected_digest: str | None
    challenger_expected_digest: str | None
    observed_digest: str | None
    applicable: bool = True

    def __post_init__(self) -> None:
        _require_text("check_id", self.check_id)
        if not isinstance(self.kind, CheckKind):
            raise TypeError("kind must be CheckKind")
        if isinstance(self.hinge_index, bool) or not isinstance(self.hinge_index, int):
            raise TypeError("hinge_index must be int")
        if self.hinge_index < 0:
            raise ValueError("hinge_index must be non-negative")
        if not isinstance(self.applicable, bool):
            raise TypeError("applicable must be bool")
        for name in (
            "candidate_expected_digest",
            "challenger_expected_digest",
            "observed_digest",
        ):
            _optional_digest(name, getattr(self, name))
        if not self.applicable:
            if any(
                value is not None
                for value in (
                    self.candidate_expected_digest,
                    self.challenger_expected_digest,
                    self.observed_digest,
                )
            ):
                raise ValueError("not-applicable checks cannot carry predictions or observations")
        elif self.candidate_expected_digest is None:
            raise ValueError("applicable checks require a candidate prediction")


@dataclass(frozen=True)
class CheckAssessment:
    check_id: str
    kind: CheckKind
    outcome: CheckOutcome
    coverage: HingeCoverage
    hinge_index: int
    reason: str

    def __post_init__(self) -> None:
        _require_text("check_id", self.check_id)
        if not isinstance(self.kind, CheckKind):
            raise TypeError("kind must be CheckKind")
        if not isinstance(self.outcome, CheckOutcome):
            raise TypeError("outcome must be CheckOutcome")
        if not isinstance(self.coverage, HingeCoverage):
            raise TypeError("coverage must be HingeCoverage")
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class RPSShadowDecision:
    recommendation: RPSRecommendation
    reason: str
    candidate_digest: str
    primary: CheckAssessment | None
    secondary: CheckAssessment | None
    base_answer_preserved: bool = True
    execution_authorized: bool = False
    answer_mutated: bool = False
    host_action_required: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.recommendation, RPSRecommendation):
            raise TypeError("recommendation must be RPSRecommendation")
        _require_text("reason", self.reason)
        _require_digest("candidate_digest", self.candidate_digest)
        if self.primary is not None and not isinstance(self.primary, CheckAssessment):
            raise TypeError("primary must be CheckAssessment or None")
        if self.secondary is not None and not isinstance(self.secondary, CheckAssessment):
            raise TypeError("secondary must be CheckAssessment or None")
        if (
            self.base_answer_preserved is not True
            or self.execution_authorized is not False
            or self.answer_mutated is not False
            or self.host_action_required is not True
        ):
            raise ValueError("shadow RPS cannot mutate or authorize the candidate")

    def trace(self) -> dict[str, object]:
        def public(row: CheckAssessment | None) -> dict[str, object] | None:
            if row is None:
                return None
            return {
                "check_id": row.check_id,
                "kind": row.kind.value,
                "outcome": row.outcome.value,
                "coverage": row.coverage.value,
                "hinge_index": row.hinge_index,
                "reason": row.reason,
            }

        return {
            "schema": "foil.rps-shadow-decision.v1",
            "recommendation": self.recommendation.value,
            "reason": self.reason,
            "candidate_digest": self.candidate_digest,
            "primary": public(self.primary),
            "secondary": public(self.secondary),
            "base_answer_preserved": True,
            "execution_authorized": False,
            "answer_mutated": False,
            "host_action_required": True,
        }


def assess_check(capsule: ReasoningCapsule, check: ParityObservation) -> CheckAssessment:
    """Derive outcome and hinge coverage without trusting a PASS label."""

    if not isinstance(capsule, ReasoningCapsule):
        raise TypeError("capsule must be ReasoningCapsule")
    if not isinstance(check, ParityObservation):
        raise TypeError("check must be ParityObservation")
    if check.hinge_index >= len(capsule.hinge_digests):
        raise ValueError("check hinge_index is outside the capsule")
    if not check.applicable:
        return CheckAssessment(
            check.check_id,
            check.kind,
            CheckOutcome.NOT_APPLICABLE,
            HingeCoverage.NONE,
            check.hinge_index,
            "check_not_applicable",
        )

    targets_fragile = check.hinge_index == capsule.fragile_hinge
    predictions_differ = (
        check.challenger_expected_digest is not None
        and check.candidate_expected_digest != check.challenger_expected_digest
    )
    exact_candidate_relation = (
        check.kind is CheckKind.EXACT_RELATION
        and check.challenger_expected_digest is None
    )
    coverage = (
        HingeCoverage.DECISIVE
        if targets_fragile and (predictions_differ or exact_candidate_relation)
        else HingeCoverage.SUPPORTING
    )

    if check.observed_digest is None:
        outcome = CheckOutcome.UNCERTAIN
        reason = "observation_missing"
    elif check.observed_digest == check.candidate_expected_digest:
        outcome = CheckOutcome.PASS
        reason = (
            "candidate_prediction_matched"
            if coverage is HingeCoverage.DECISIVE
            else "non_discriminating_prediction_matched"
        )
    elif (
        check.challenger_expected_digest is not None
        and check.observed_digest == check.challenger_expected_digest
    ):
        outcome = CheckOutcome.FAIL
        reason = "challenger_prediction_matched"
    elif exact_candidate_relation:
        outcome = CheckOutcome.FAIL
        reason = "exact_candidate_relation_failed"
    else:
        outcome = CheckOutcome.UNCERTAIN
        reason = "observation_matches_neither_prediction"

    return CheckAssessment(
        check.check_id,
        check.kind,
        outcome,
        coverage,
        check.hinge_index,
        reason,
    )


def _terminal_recommendation(assessment: CheckAssessment) -> RPSRecommendation | None:
    if assessment.coverage is not HingeCoverage.DECISIVE:
        return None
    if assessment.outcome is CheckOutcome.PASS:
        return RPSRecommendation.FAST_ACCEPT
    if assessment.outcome is CheckOutcome.FAIL:
        return RPSRecommendation.LOCAL_REPAIR
    return None


def evaluate_rps_shadow(
    capsule: ReasoningCapsule,
    primary: ParityObservation,
    *,
    policy: RPSShadowPolicy = RPSShadowPolicy(),
    secondary: ParityObservation | None = None,
) -> RPSShadowDecision:
    """Return one typed, non-authoritative recommendation."""

    if not isinstance(capsule, ReasoningCapsule):
        raise TypeError("capsule must be ReasoningCapsule")
    if not isinstance(primary, ParityObservation):
        raise TypeError("primary must be ParityObservation")
    if secondary is not None and not isinstance(secondary, ParityObservation):
        raise TypeError("secondary must be ParityObservation or None")
    if not isinstance(policy, RPSShadowPolicy):
        raise TypeError("policy must be RPSShadowPolicy")
    if not policy.enabled:
        return RPSShadowDecision(
            RPSRecommendation.STAND_DOWN,
            "rps_shadow_disabled",
            capsule.candidate_digest,
            None,
            None,
        )

    p1 = assess_check(capsule, primary)
    terminal = _terminal_recommendation(p1)
    if terminal is not None:
        return RPSShadowDecision(
            terminal,
            (
                "p1_decisive_pass"
                if terminal is RPSRecommendation.FAST_ACCEPT
                else "p1_decisive_failure"
            ),
            capsule.candidate_digest,
            p1,
            None,
        )
    if secondary is None:
        return RPSShadowDecision(
            RPSRecommendation.RUN_P2,
            "p1_did_not_decisively_test_fragile_hinge",
            capsule.candidate_digest,
            p1,
            None,
        )

    p2 = assess_check(capsule, secondary)
    if p2.kind is p1.kind:
        return RPSShadowDecision(
            RPSRecommendation.ABSTAIN,
            "p2_not_orthogonal",
            capsule.candidate_digest,
            p1,
            p2,
        )
    terminal = _terminal_recommendation(p2)
    if terminal is not None:
        return RPSShadowDecision(
            terminal,
            (
                "p2_decisive_pass"
                if terminal is RPSRecommendation.FAST_ACCEPT
                else "p2_decisive_failure"
            ),
            capsule.candidate_digest,
            p1,
            p2,
        )
    return RPSShadowDecision(
        RPSRecommendation.ABSTAIN,
        "two_checks_without_decisive_resolution",
        capsule.candidate_digest,
        p1,
        p2,
    )
