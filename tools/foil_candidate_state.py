"""Fail-closed release state for FOIL residual-complement candidates.

This module models research-candidate promotion separately from FOIL invocation
mode.  It has no answer, tool, file, process, model, provider, Gauntlet, or
Mastermind integration.  A state transition is an authority decision only; even
``ACTIVE`` grants no write or commit capability.

The local HMAC protects tokens against accidental or untrusted in-process
tampering when the issuer secret is kept by the host.  It is not a claim of
protection against a compromised host process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class CandidateState(str, Enum):
    DORMANT = "DORMANT"
    SHADOW = "SHADOW"
    LOCKED = "LOCKED"
    ACTIVE = "ACTIVE"


class Gate(str, Enum):
    GATE1 = "GATE1"
    GATE2 = "GATE2"
    GATE3 = "GATE3"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class CandidateBinding:
    """Identity of one frozen candidate configuration."""

    candidate_id: str
    task_digest: str
    base_answer_digest: str
    protocol_digest: str
    config_digest: str
    partition_digest: str
    budget_ceiling_digest: str

    def __post_init__(self) -> None:
        _require_text("candidate_id", self.candidate_id)
        for name in (
            "task_digest",
            "base_answer_digest",
            "protocol_digest",
            "config_digest",
            "partition_digest",
            "budget_ceiling_digest",
        ):
            _require_digest(name, getattr(self, name))

    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.as_dict())).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "task_digest": self.task_digest,
            "base_answer_digest": self.base_answer_digest,
            "protocol_digest": self.protocol_digest,
            "config_digest": self.config_digest,
            "partition_digest": self.partition_digest,
            "budget_ceiling_digest": self.budget_ceiling_digest,
        }


@dataclass(frozen=True)
class GateReceipt:
    """Content-addressed result for one promotion gate."""

    gate: Gate
    status: GateStatus
    binding_digest: str
    evidence_digest: str
    solve_equivalence_digest: str
    cost_ledger_digest: str
    reason: str
    forbidden_calls: int = 0
    required_domains_passed: bool = False
    cost_complete: bool = False
    conditional_validity_passed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.gate, Gate):
            raise TypeError("gate must be Gate")
        if not isinstance(self.status, GateStatus):
            raise TypeError("status must be GateStatus")
        for name in (
            "binding_digest",
            "evidence_digest",
            "solve_equivalence_digest",
            "cost_ledger_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("reason", self.reason)
        if isinstance(self.forbidden_calls, bool) or self.forbidden_calls < 0:
            raise ValueError("forbidden_calls must be a non-negative integer")
        if not isinstance(self.required_domains_passed, bool):
            raise TypeError("required_domains_passed must be bool")
        if not isinstance(self.cost_complete, bool):
            raise TypeError("cost_complete must be bool")
        if not isinstance(self.conditional_validity_passed, bool):
            raise TypeError("conditional_validity_passed must be bool")

    def qualifies(self, binding: CandidateBinding) -> bool:
        return (
            self.status is GateStatus.PASS
            and self.binding_digest == binding.digest()
            and self.solve_equivalence_digest == binding.base_answer_digest
            and self.forbidden_calls == 0
            and self.required_domains_passed
            and self.cost_complete
            and self.conditional_validity_passed
        )

    def digest(self) -> str:
        body = {
            "gate": self.gate.value,
            "status": self.status.value,
            "binding_digest": self.binding_digest,
            "evidence_digest": self.evidence_digest,
            "solve_equivalence_digest": self.solve_equivalence_digest,
            "cost_ledger_digest": self.cost_ledger_digest,
            "reason": self.reason,
            "forbidden_calls": self.forbidden_calls,
            "required_domains_passed": self.required_domains_passed,
            "cost_complete": self.cost_complete,
            "conditional_validity_passed": self.conditional_validity_passed,
        }
        return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass(frozen=True)
class AuthorityToken:
    """Host-verifiable, expiring, one-candidate authority token."""

    candidate_id: str
    state: CandidateState
    binding_digest: str
    evidence_digest: str
    issued_at: str
    expires_at: str
    nonce: str
    issuer_id: str
    signature: str
    execution_authorized: bool = field(default=False, init=False)
    host_action_required: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        _require_text("candidate_id", self.candidate_id)
        if self.state not in (CandidateState.LOCKED, CandidateState.ACTIVE):
            raise ValueError("authority tokens are only valid for LOCKED or ACTIVE")
        _require_digest("binding_digest", self.binding_digest)
        _require_digest("evidence_digest", self.evidence_digest)
        _timestamp(self.issued_at)
        _timestamp(self.expires_at)
        if _timestamp(self.expires_at) <= _timestamp(self.issued_at):
            raise ValueError("authority token must expire after issue")
        _require_text("nonce", self.nonce)
        _require_text("issuer_id", self.issuer_id)
        _require_digest("signature", self.signature)

    def unsigned(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "state": self.state.value,
            "binding_digest": self.binding_digest,
            "evidence_digest": self.evidence_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "issuer_id": self.issuer_id,
        }


class AuthorityIssuer:
    """Mint and verify candidate-state tokens using a host-owned key."""

    def __init__(self, issuer_id: str, secret: bytes) -> None:
        self.issuer_id = _require_text("issuer_id", issuer_id)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("issuer secret must contain at least 32 bytes")
        self._secret = secret

    def _sign(self, body: dict[str, object]) -> str:
        return hmac.new(self._secret, _canonical(body), hashlib.sha256).hexdigest()

    def mint(
        self,
        binding: CandidateBinding,
        state: CandidateState,
        evidence_digest: str,
        *,
        issued_at: str,
        expires_at: str,
        nonce: str | None = None,
    ) -> AuthorityToken:
        if state not in (CandidateState.LOCKED, CandidateState.ACTIVE):
            raise ValueError("issuer may mint only LOCKED or ACTIVE authority")
        body: dict[str, object] = {
            "candidate_id": binding.candidate_id,
            "state": state,
            "binding_digest": binding.digest(),
            "evidence_digest": _require_digest("evidence_digest", evidence_digest),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": nonce or secrets.token_hex(16),
            "issuer_id": self.issuer_id,
        }
        _timestamp(issued_at)
        _timestamp(expires_at)
        return AuthorityToken(**body, signature=self._sign(body))  # type: ignore[arg-type]

    def verify(
        self,
        token: AuthorityToken,
        binding: CandidateBinding,
        *,
        now: str,
        expected_state: CandidateState,
    ) -> bool:
        if not isinstance(token, AuthorityToken):
            return False
        return (
            token.issuer_id == self.issuer_id
            and token.candidate_id == binding.candidate_id
            and token.binding_digest == binding.digest()
            and token.state is expected_state
            and hmac.compare_digest(token.signature, self._sign(token.unsigned()))
            and _timestamp(token.issued_at) <= _timestamp(now) < _timestamp(token.expires_at)
        )


@dataclass(frozen=True)
class CandidateDecision:
    state: CandidateState
    reason: str
    token: AuthorityToken | None = None
    execution_authorized: bool = field(default=False, init=False)
    base_answer_preserved: bool = field(default=True, init=False)
    host_action_required: bool = field(default=True, init=False)


def decide_candidate_state(
    binding: CandidateBinding,
    *,
    enabled: bool,
    issuer: AuthorityIssuer,
    now: str,
    gate_receipts: Iterable[GateReceipt] = (),
    locked_token: AuthorityToken | None = None,
    active_token: AuthorityToken | None = None,
    host_activation_approved: bool = False,
) -> CandidateDecision:
    """Return a fail-closed state without granting execution authority."""
    if not enabled:
        return CandidateDecision(CandidateState.DORMANT, "candidate_disabled")

    receipts: dict[Gate, GateReceipt] = {}
    for receipt in gate_receipts:
        if not isinstance(receipt, GateReceipt) or receipt.gate in receipts:
            return CandidateDecision(CandidateState.SHADOW, "invalid_or_duplicate_gate_receipt")
        receipts[receipt.gate] = receipt

    gate1 = receipts.get(Gate.GATE1)
    if gate1 is None or not gate1.qualifies(binding):
        return CandidateDecision(CandidateState.SHADOW, "gate1_not_promoted")
    gate1_evidence = gate1.digest()
    if locked_token is None or not issuer.verify(
        locked_token,
        binding,
        now=now,
        expected_state=CandidateState.LOCKED,
    ):
        return CandidateDecision(CandidateState.SHADOW, "locked_authority_missing_or_invalid")
    if locked_token.evidence_digest != gate1_evidence:
        return CandidateDecision(CandidateState.SHADOW, "locked_authority_evidence_mismatch")

    gate2 = receipts.get(Gate.GATE2)
    gate3 = receipts.get(Gate.GATE3)
    if gate2 is None or gate3 is None:
        return CandidateDecision(CandidateState.LOCKED, "later_gates_not_run", locked_token)
    if not gate2.qualifies(binding) or not gate3.qualifies(binding):
        return CandidateDecision(CandidateState.LOCKED, "later_gate_not_promoted", locked_token)
    if not host_activation_approved:
        return CandidateDecision(CandidateState.LOCKED, "host_activation_not_approved", locked_token)
    if active_token is None or not issuer.verify(
        active_token,
        binding,
        now=now,
        expected_state=CandidateState.ACTIVE,
    ):
        return CandidateDecision(CandidateState.LOCKED, "active_authority_missing_or_invalid", locked_token)
    combined = hashlib.sha256(
        (gate1.digest() + gate2.digest() + gate3.digest()).encode("ascii")
    ).hexdigest()
    if active_token.evidence_digest != combined:
        return CandidateDecision(CandidateState.LOCKED, "active_authority_evidence_mismatch", locked_token)
    return CandidateDecision(CandidateState.ACTIVE, "all_gates_and_host_approval_present", active_token)
