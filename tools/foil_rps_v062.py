"""Host-verifier-first RPS v0.6.2 shadow controller.

The deterministic host verifier is the only risk gate.  A blind rival may be
requested only when that verifier is not applicable or cannot decide.  The
rival envelope has no field for the incumbent answer, and agreement is labelled
as correlated evidence rather than proof.

This module performs no provider, network, tool, profile, execution, promotion,
or answer-mutation work.  Temporal precommitment must be established by the
host's append-only benchmark/run receipts; the content commitment here proves
only that the frozen check specification is candidate-independent.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from foil_rps import CheckKind


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHECK_SCHEMA = "foil.rps-v062-precommitted-check.v1"


class HostVerifierOutcome(str, Enum):
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class RPSV062Recommendation(str, Enum):
    STAND_DOWN = "STAND_DOWN"
    REQUEST_BLIND_RIVAL = "REQUEST_BLIND_RIVAL"
    CORRELATED_AGREEMENT = "CORRELATED_AGREEMENT"
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


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def check_commitment_digest(
    *,
    task_digest: str,
    answer_form_digest: str,
    check_id: str,
    kind: CheckKind,
    check_spec_digest: str,
) -> str:
    """Bind a check specification to a task without binding a candidate."""

    _require_digest("task_digest", task_digest)
    _require_text("check_id", check_id)
    if not isinstance(kind, CheckKind):
        raise TypeError("kind must be CheckKind")
    _require_digest("answer_form_digest", answer_form_digest)
    _require_digest("check_spec_digest", check_spec_digest)
    body = "\n".join(
        (_CHECK_SCHEMA, task_digest, answer_form_digest, check_id, kind.value, check_spec_digest)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PrecommittedHostCheck:
    """Candidate-independent identity for one host-computable check."""

    task_digest: str
    answer_form_digest: str
    check_id: str
    kind: CheckKind
    check_spec_digest: str
    commitment_digest: str

    def __post_init__(self) -> None:
        _require_digest("task_digest", self.task_digest)
        _require_digest("answer_form_digest", self.answer_form_digest)
        _require_text("check_id", self.check_id)
        if not isinstance(self.kind, CheckKind):
            raise TypeError("kind must be CheckKind")
        _require_digest("check_spec_digest", self.check_spec_digest)
        _require_digest("commitment_digest", self.commitment_digest)
        expected = check_commitment_digest(
            task_digest=self.task_digest,
            answer_form_digest=self.answer_form_digest,
            check_id=self.check_id,
            kind=self.kind,
            check_spec_digest=self.check_spec_digest,
        )
        if self.commitment_digest != expected:
            raise ValueError("commitment_digest does not bind the supplied check")


@dataclass(frozen=True)
class HostVerifierReceipt:
    """Result produced by a host verifier, never by the answer generator."""

    task_digest: str
    check_commitment_digest: str
    candidate_digest: str
    outcome: HostVerifierOutcome
    observation_digest: str | None
    provider_calls: int = 0
    model_tokens: int = 0
    answer_mutations: int = 0

    def __post_init__(self) -> None:
        _require_digest("task_digest", self.task_digest)
        _require_digest("check_commitment_digest", self.check_commitment_digest)
        _require_digest("candidate_digest", self.candidate_digest)
        if not isinstance(self.outcome, HostVerifierOutcome):
            raise TypeError("outcome must be HostVerifierOutcome")
        _optional_digest("observation_digest", self.observation_digest)
        for name in ("provider_calls", "model_tokens", "answer_mutations"):
            _require_nonnegative_int(name, getattr(self, name))
        if self.provider_calls or self.model_tokens or self.answer_mutations:
            raise ValueError("a host-verifier receipt must record zero model/action cost")
        if self.outcome in {
            HostVerifierOutcome.CONFIRMED,
            HostVerifierOutcome.CONTRADICTED,
        } and self.observation_digest is None:
            raise ValueError("decisive host outcomes require an observation digest")
        if self.outcome is HostVerifierOutcome.NOT_APPLICABLE and self.observation_digest:
            raise ValueError("not-applicable host checks cannot carry an observation")


@dataclass(frozen=True)
class BlindRivalReceipt:
    """A rival generated from the task without an incumbent-answer field."""

    task_digest: str
    answer_form_digest: str
    rival_digest: str
    request_digest: str
    model_route_digest: str
    incumbent_withheld: bool
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        for name in (
            "task_digest",
            "answer_form_digest",
            "rival_digest",
            "request_digest",
            "model_route_digest",
        ):
            _require_digest(name, getattr(self, name))
        if self.incumbent_withheld is not True:
            raise ValueError("blind-rival receipts require incumbent_withheld=true")
        _require_nonnegative_int("input_tokens", self.input_tokens)
        _require_nonnegative_int("output_tokens", self.output_tokens)


@dataclass(frozen=True)
class RPSV062Policy:
    enabled: bool = False
    observe_only: bool = True
    max_blind_rivals: int = 1
    max_answer_mutations: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.observe_only, bool):
            raise TypeError("enabled and observe_only must be bool")
        if self.observe_only is not True:
            raise ValueError("RPS v0.6.2 is shadow-only")
        _require_nonnegative_int("max_blind_rivals", self.max_blind_rivals)
        _require_nonnegative_int("max_answer_mutations", self.max_answer_mutations)
        if self.max_blind_rivals != 1 or self.max_answer_mutations != 0:
            raise ValueError("RPS v0.6.2 ceilings are frozen")


@dataclass(frozen=True)
class RPSV062Decision:
    recommendation: RPSV062Recommendation
    reason: str
    candidate_digest: str
    host_outcome: HostVerifierOutcome | None
    rival_requested: bool
    rival_used: bool
    base_answer_preserved: bool = True
    execution_authorized: bool = False
    answer_mutated: bool = False
    promotion_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.recommendation, RPSV062Recommendation):
            raise TypeError("recommendation must be RPSV062Recommendation")
        _require_text("reason", self.reason)
        _require_digest("candidate_digest", self.candidate_digest)
        if self.host_outcome is not None and not isinstance(
            self.host_outcome, HostVerifierOutcome
        ):
            raise TypeError("host_outcome must be HostVerifierOutcome or None")
        if not isinstance(self.rival_requested, bool) or not isinstance(
            self.rival_used, bool
        ):
            raise TypeError("rival_requested and rival_used must be bool")
        if self.rival_used and not self.rival_requested:
            raise ValueError("a rival cannot be used unless it was requested")
        if (
            self.base_answer_preserved is not True
            or self.execution_authorized is not False
            or self.answer_mutated is not False
            or self.promotion_authorized is not False
        ):
            raise ValueError("shadow RPS cannot mutate, execute, or promote")

    @property
    def abstained(self) -> bool:
        return self.recommendation is RPSV062Recommendation.ABSTAIN

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.rps-v062-shadow-decision.v1",
            "recommendation": self.recommendation.value,
            "reason": self.reason,
            "candidate_digest": self.candidate_digest,
            "host_outcome": self.host_outcome.value if self.host_outcome else None,
            "rival_requested": self.rival_requested,
            "rival_used": self.rival_used,
            "abstained": self.abstained,
            "base_answer_preserved": True,
            "execution_authorized": False,
            "answer_mutated": False,
            "promotion_authorized": False,
        }


def evaluate_rps_v062_shadow(
    check: PrecommittedHostCheck,
    host: HostVerifierReceipt,
    *,
    policy: RPSV062Policy = RPSV062Policy(),
    rival: BlindRivalReceipt | None = None,
) -> RPSV062Decision:
    """Derive one shadow recommendation from host coverage and a blind rival."""

    if not isinstance(check, PrecommittedHostCheck):
        raise TypeError("check must be PrecommittedHostCheck")
    if not isinstance(host, HostVerifierReceipt):
        raise TypeError("host must be HostVerifierReceipt")
    if rival is not None and not isinstance(rival, BlindRivalReceipt):
        raise TypeError("rival must be BlindRivalReceipt or None")
    if not isinstance(policy, RPSV062Policy):
        raise TypeError("policy must be RPSV062Policy")
    if host.task_digest != check.task_digest:
        raise ValueError("host receipt task binding mismatch")
    if host.check_commitment_digest != check.commitment_digest:
        raise ValueError("host receipt check binding mismatch")

    if not policy.enabled:
        if rival is not None:
            raise ValueError("disabled RPS cannot consume a rival")
        return RPSV062Decision(
            RPSV062Recommendation.STAND_DOWN,
            "rps_v062_shadow_disabled",
            host.candidate_digest,
            None,
            False,
            False,
        )

    if host.outcome is HostVerifierOutcome.CONFIRMED:
        if rival is not None:
            raise ValueError("resolved host checks must not consume a rival")
        return RPSV062Decision(
            RPSV062Recommendation.STAND_DOWN,
            "host_verifier_confirmed_candidate",
            host.candidate_digest,
            host.outcome,
            False,
            False,
        )

    if host.outcome is HostVerifierOutcome.CONTRADICTED:
        if rival is not None:
            raise ValueError("resolved host checks must not consume a rival")
        return RPSV062Decision(
            RPSV062Recommendation.ABSTAIN,
            "host_verifier_contradicted_candidate",
            host.candidate_digest,
            host.outcome,
            False,
            False,
        )

    if rival is None:
        return RPSV062Decision(
            RPSV062Recommendation.REQUEST_BLIND_RIVAL,
            "host_verifier_unresolved",
            host.candidate_digest,
            host.outcome,
            True,
            False,
        )

    if rival.task_digest != check.task_digest:
        raise ValueError("blind rival task binding mismatch")
    if rival.answer_form_digest != check.answer_form_digest:
        raise ValueError("blind rival answer-form binding mismatch")
    if rival.rival_digest == host.candidate_digest:
        return RPSV062Decision(
            RPSV062Recommendation.CORRELATED_AGREEMENT,
            "blind_rival_matches_incumbent_without_proving_correctness",
            host.candidate_digest,
            host.outcome,
            True,
            True,
        )
    return RPSV062Decision(
        RPSV062Recommendation.ABSTAIN,
        "blind_rival_disagrees_with_incumbent",
        host.candidate_digest,
        host.outcome,
        True,
        True,
    )
