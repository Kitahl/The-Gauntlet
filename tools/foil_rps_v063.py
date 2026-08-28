"""Benchmark-active, host-verified correction selection for FOIL RPS v0.6.3.

This module is the smallest active bridge beyond the v0.6.2 shadow controller.
It may change a benchmark answer only when a precommitted deterministic host
check either supplies and confirms a unique task-side result, or contradicts A
and confirms a distinct blind rival B. It has no production or promotion
authority and stores only digests in its decision receipt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from foil_rps_host_verifier import (
    SelectedHostCheck,
    Stage1Outcome,
    Stage1Result,
    verify_answer,
)
from foil_rps_v062 import (
    BlindRivalReceipt,
    HostVerifierOutcome,
    HostVerifierReceipt,
    PrecommittedHostCheck,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RPSV063Action(str, Enum):
    KEEP_BASE = "KEEP_BASE"
    REQUEST_BLIND_RIVAL = "REQUEST_BLIND_RIVAL"
    SELECT_HOST_RESULT = "SELECT_HOST_RESULT"
    SELECT_VERIFIED_RIVAL = "SELECT_VERIFIED_RIVAL"
    ABSTAIN = "ABSTAIN"


def _digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class RPSV063Policy:
    enabled: bool = False
    benchmark_only: bool = True
    max_blind_rivals: int = 0
    max_answer_changes: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(
            self.benchmark_only, bool
        ):
            raise TypeError("enabled and benchmark_only must be bool")
        if self.benchmark_only is not True:
            raise ValueError("RPS v0.6.3 has no production authority")
        for name in ("max_blind_rivals", "max_answer_changes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
        if self.max_blind_rivals not in {0, 1}:
            raise ValueError("RPS v0.6.3 allows zero or one blind rival")
        if self.max_answer_changes != 1:
            raise ValueError("RPS v0.6.3 answer-change ceiling is frozen at one")


@dataclass(frozen=True)
class RPSV063Decision:
    action: RPSV063Action
    reason: str
    base_digest: str
    selected_digest: str | None
    rival_digest: str | None
    base_host_outcome: HostVerifierOutcome
    rival_host_outcome: HostVerifierOutcome | None
    answer_change_authorized: bool
    benchmark_only: bool = True
    production_authorized: bool = False
    promotion_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.action, RPSV063Action):
            raise TypeError("action must be RPSV063Action")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text")
        _digest("base_digest", self.base_digest)
        if self.selected_digest is not None:
            _digest("selected_digest", self.selected_digest)
        if self.rival_digest is not None:
            _digest("rival_digest", self.rival_digest)
        if not isinstance(self.base_host_outcome, HostVerifierOutcome):
            raise TypeError("base_host_outcome must be HostVerifierOutcome")
        if self.rival_host_outcome is not None and not isinstance(
            self.rival_host_outcome, HostVerifierOutcome
        ):
            raise TypeError("rival_host_outcome must be HostVerifierOutcome or None")
        if not isinstance(self.answer_change_authorized, bool):
            raise TypeError("answer_change_authorized must be bool")
        if (
            self.benchmark_only is not True
            or self.production_authorized is not False
            or self.promotion_authorized is not False
        ):
            raise ValueError("v0.6.3 may act only inside a benchmark")
        selects = self.action in {
            RPSV063Action.SELECT_HOST_RESULT,
            RPSV063Action.SELECT_VERIFIED_RIVAL,
        }
        if self.answer_change_authorized != selects:
            raise ValueError("only a host-verified selection may authorize a change")
        if self.action is RPSV063Action.SELECT_VERIFIED_RIVAL and (
            self.selected_digest != self.rival_digest
            or self.selected_digest == self.base_digest
            or self.base_host_outcome is not HostVerifierOutcome.CONTRADICTED
            or self.rival_host_outcome is not HostVerifierOutcome.CONFIRMED
        ):
            raise ValueError("verified-rival selection invariant violated")
        if self.action is RPSV063Action.SELECT_HOST_RESULT and (
            self.selected_digest is None
            or self.selected_digest == self.base_digest
            or self.rival_digest is not None
            or self.base_host_outcome is not HostVerifierOutcome.CONTRADICTED
            or self.rival_host_outcome is not None
        ):
            raise ValueError("host-result selection invariant violated")
        if (
            self.action is RPSV063Action.KEEP_BASE
            and self.selected_digest != self.base_digest
        ):
            raise ValueError("KEEP_BASE must select the base digest")
        if self.action in {
            RPSV063Action.ABSTAIN,
            RPSV063Action.REQUEST_BLIND_RIVAL,
        } and self.selected_digest is not None:
            raise ValueError("abstention/request cannot select an answer")

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.rps-v063-benchmark-active-decision.v1",
            "action": self.action.value,
            "reason": self.reason,
            "base_digest": self.base_digest,
            "selected_digest": self.selected_digest,
            "rival_digest": self.rival_digest,
            "base_host_outcome": self.base_host_outcome.value,
            "rival_host_outcome": (
                self.rival_host_outcome.value if self.rival_host_outcome else None
            ),
            "answer_change_authorized": self.answer_change_authorized,
            "benchmark_only": True,
            "production_authorized": False,
            "promotion_authorized": False,
            "raw_answer_stored": False,
        }


def _validate_host_binding(
    check: PrecommittedHostCheck, receipt: HostVerifierReceipt
) -> None:
    if receipt.task_digest != check.task_digest:
        raise ValueError("host receipt task binding mismatch")
    if receipt.check_commitment_digest != check.commitment_digest:
        raise ValueError("host receipt check binding mismatch")


def evaluate_unique_host_result(
    selected: SelectedHostCheck,
    base_result: Stage1Result,
    host_candidate: object | None = None,
    *,
    policy: RPSV063Policy = RPSV063Policy(),
) -> RPSV063Decision:
    """Select a unique task-side result only after the host confirms it."""

    if not isinstance(selected, SelectedHostCheck):
        raise TypeError("selected must be SelectedHostCheck")
    if not isinstance(base_result, Stage1Result):
        raise TypeError("base_result must be Stage1Result")
    if not isinstance(policy, RPSV063Policy):
        raise TypeError("policy must be RPSV063Policy")
    if selected.precommit is None or base_result.receipt is None:
        raise ValueError("host correction requires a committed check and receipt")
    _validate_host_binding(selected.precommit, base_result.receipt)

    base_digest = base_result.candidate_digest
    if not policy.enabled or base_result.outcome is Stage1Outcome.PASS:
        return RPSV063Decision(
            RPSV063Action.KEEP_BASE,
            "rps_v063_disabled" if not policy.enabled else "host_confirmed_base",
            base_digest,
            base_digest,
            None,
            base_result.receipt.outcome,
            None,
            False,
        )
    if base_result.outcome in {
        Stage1Outcome.NOT_APPLICABLE,
        Stage1Outcome.UNCERTAIN,
    }:
        if policy.max_blind_rivals == 0:
            return RPSV063Decision(
                RPSV063Action.KEEP_BASE,
                "blind_rival_disabled_after_host_decline",
                base_digest,
                base_digest,
                None,
                base_result.receipt.outcome,
                None,
                False,
            )
        return RPSV063Decision(
            RPSV063Action.REQUEST_BLIND_RIVAL,
            "host_declined_requires_blind_rival",
            base_digest,
            None,
            None,
            base_result.receipt.outcome,
            None,
            False,
        )
    if not isinstance(selected.spec.get("expected_answer"), str):
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "contradiction_has_no_unique_host_result",
            base_digest,
            None,
            None,
            base_result.receipt.outcome,
            None,
            False,
        )
    if host_candidate is None:
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "unique_host_result_was_not_materialized",
            base_digest,
            None,
            None,
            base_result.receipt.outcome,
            None,
            False,
        )
    candidate_result = verify_answer(selected, host_candidate)
    if candidate_result.outcome is not Stage1Outcome.PASS:
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "materialized_host_result_was_not_confirmed",
            base_digest,
            None,
            None,
            base_result.receipt.outcome,
            candidate_result.receipt.outcome if candidate_result.receipt else None,
            False,
        )
    if candidate_result.candidate_digest == base_digest:
        raise ValueError("contradicted base cannot equal the unique host result")
    return RPSV063Decision(
        RPSV063Action.SELECT_HOST_RESULT,
        "base_contradicted_and_unique_host_result_confirmed",
        base_digest,
        candidate_result.candidate_digest,
        None,
        base_result.receipt.outcome,
        None,
        True,
    )


def evaluate_verified_correction(
    check: PrecommittedHostCheck,
    base_host: HostVerifierReceipt,
    *,
    policy: RPSV063Policy = RPSV063Policy(),
    rival: BlindRivalReceipt | None = None,
    rival_host: HostVerifierReceipt | None = None,
) -> RPSV063Decision:
    """Select B only under contradicted-A/confirmed-B host evidence."""

    if not isinstance(check, PrecommittedHostCheck):
        raise TypeError("check must be PrecommittedHostCheck")
    if not isinstance(base_host, HostVerifierReceipt):
        raise TypeError("base_host must be HostVerifierReceipt")
    if rival is not None and not isinstance(rival, BlindRivalReceipt):
        raise TypeError("rival must be BlindRivalReceipt or None")
    if rival_host is not None and not isinstance(rival_host, HostVerifierReceipt):
        raise TypeError("rival_host must be HostVerifierReceipt or None")
    if not isinstance(policy, RPSV063Policy):
        raise TypeError("policy must be RPSV063Policy")
    if (rival is None) != (rival_host is None):
        raise ValueError("rival and rival_host must be supplied together")
    _validate_host_binding(check, base_host)

    if not policy.enabled:
        if rival is not None:
            raise ValueError("disabled v0.6.3 cannot consume a rival")
        return RPSV063Decision(
            RPSV063Action.KEEP_BASE,
            "rps_v063_disabled",
            base_host.candidate_digest,
            base_host.candidate_digest,
            None,
            base_host.outcome,
            None,
            False,
        )
    if policy.max_blind_rivals == 0 and rival is not None:
        raise ValueError("zero-rival policy cannot consume a rival")
    if base_host.outcome is HostVerifierOutcome.CONFIRMED:
        if rival is not None:
            raise ValueError("confirmed base must not consume a rival")
        return RPSV063Decision(
            RPSV063Action.KEEP_BASE,
            "host_confirmed_base",
            base_host.candidate_digest,
            base_host.candidate_digest,
            None,
            base_host.outcome,
            None,
            False,
        )
    if base_host.outcome is not HostVerifierOutcome.CONTRADICTED:
        if rival is None:
            if policy.max_blind_rivals == 0:
                return RPSV063Decision(
                    RPSV063Action.KEEP_BASE,
                    "blind_rival_disabled_after_host_decline",
                    base_host.candidate_digest,
                    base_host.candidate_digest,
                    None,
                    base_host.outcome,
                    None,
                    False,
                )
            return RPSV063Decision(
                RPSV063Action.REQUEST_BLIND_RIVAL,
                "host_declined_requires_blind_rival",
                base_host.candidate_digest,
                None,
                None,
                base_host.outcome,
                None,
                False,
            )
        _validate_host_binding(check, rival_host)
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "declined_check_cannot_adjudicate_disagreement",
            base_host.candidate_digest,
            None,
            rival.rival_digest,
            base_host.outcome,
            rival_host.outcome,
            False,
        )
    if rival is None:
        if policy.max_blind_rivals == 0:
            return RPSV063Decision(
                RPSV063Action.ABSTAIN,
                "blind_rival_disabled_after_host_contradiction",
                base_host.candidate_digest,
                None,
                None,
                base_host.outcome,
                None,
                False,
            )
        return RPSV063Decision(
            RPSV063Action.REQUEST_BLIND_RIVAL,
            "contradicted_base_requires_blind_rival",
            base_host.candidate_digest,
            None,
            None,
            base_host.outcome,
            None,
            False,
        )

    _validate_host_binding(check, rival_host)
    if rival.task_digest != check.task_digest:
        raise ValueError("blind rival task binding mismatch")
    if rival.answer_form_digest != check.answer_form_digest:
        raise ValueError("blind rival answer-form binding mismatch")
    if rival_host.candidate_digest != rival.rival_digest:
        raise ValueError("rival host receipt does not bind the blind rival")
    if rival.rival_digest == base_host.candidate_digest:
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "rival_did_not_supply_a_distinct_answer",
            base_host.candidate_digest,
            None,
            rival.rival_digest,
            base_host.outcome,
            rival_host.outcome,
            False,
        )
    if rival_host.outcome is not HostVerifierOutcome.CONFIRMED:
        return RPSV063Decision(
            RPSV063Action.ABSTAIN,
            "rival_not_mechanically_confirmed",
            base_host.candidate_digest,
            None,
            rival.rival_digest,
            base_host.outcome,
            rival_host.outcome,
            False,
        )
    return RPSV063Decision(
        RPSV063Action.SELECT_VERIFIED_RIVAL,
        "base_contradicted_and_blind_rival_confirmed",
        base_host.candidate_digest,
        rival.rival_digest,
        rival.rival_digest,
        base_host.outcome,
        rival_host.outcome,
        True,
    )
