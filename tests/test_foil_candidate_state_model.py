from __future__ import annotations

import dataclasses
import hashlib
import itertools
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_authority_replay import AuthorityReplayGuard  # noqa: E402
from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateDecision,
    CandidateState,
    Gate,
    GateReceipt,
    GateStatus,
    decide_candidate_state,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CandidateStateModelTests(unittest.TestCase):
    """Exhaustive small-model checks for the pure promotion transition."""

    def setUp(self) -> None:
        self.now = datetime(2026, 8, 24, tzinfo=timezone.utc)
        self.binding = CandidateBinding(
            candidate_id="foil-v5-candidate-model",
            task_digest=digest("task"),
            base_answer_digest=digest("a0-base-answer"),
            protocol_digest=digest("protocol"),
            config_digest=digest("config"),
            partition_digest=digest("partition"),
            budget_ceiling_digest=digest("budget"),
        )
        self.issuer = AuthorityIssuer("host.model-check", b"m" * 32)

    def receipt(
        self,
        gate: Gate,
        *,
        status: GateStatus = GateStatus.PASS,
        conditional_validity_passed: bool = True,
    ) -> GateReceipt:
        return GateReceipt(
            gate=gate,
            status=status,
            binding_digest=self.binding.digest(),
            evidence_digest=digest(f"{gate.value}:evidence"),
            solve_equivalence_digest=self.binding.base_answer_digest,
            cost_ledger_digest=digest(f"{gate.value}:ledger"),
            reason="typed gate evidence",
            required_domains_passed=True,
            cost_complete=True,
            conditional_validity_passed=conditional_validity_passed,
        )

    def token(
        self, state: CandidateState, evidence_digest: str, *, nonce: str | None = None
    ):
        return self.issuer.mint(
            self.binding,
            state,
            evidence_digest,
            issued_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=5)).isoformat(),
            nonce=nonce,
        )

    def active_inputs(
        self,
        *,
        statuses: tuple[GateStatus, GateStatus, GateStatus] | None = None,
        conditional: tuple[bool, bool, bool] = (True, True, True),
    ) -> tuple[tuple[GateReceipt, ...], object, object]:
        statuses = statuses or (GateStatus.PASS, GateStatus.PASS, GateStatus.PASS)
        receipts = tuple(
            self.receipt(gate, status=status, conditional_validity_passed=condition)
            for gate, status, condition in zip(Gate, statuses, conditional, strict=True)
        )
        locked = self.token(CandidateState.LOCKED, receipts[0].digest(), nonce="locked")
        combined = hashlib.sha256("".join(row.digest() for row in receipts).encode("ascii")).hexdigest()
        active = self.token(CandidateState.ACTIVE, combined, nonce="active")
        return receipts, locked, active

    def decide(
        self, receipts: tuple[GateReceipt, ...], locked: object, active: object
    ) -> CandidateDecision:
        return decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=receipts,
            locked_token=locked,
            active_token=active,
            host_activation_approved=True,
        )

    def test_exhaustive_gate_status_and_conditional_evidence_never_over_promote(self):
        statuses = tuple(GateStatus)
        for status_values in itertools.product(statuses, repeat=3):
            for conditional_values in itertools.product((False, True), repeat=3):
                with self.subTest(statuses=status_values, conditional=conditional_values):
                    receipts, locked, active = self.active_inputs(
                        statuses=status_values,
                        conditional=conditional_values,
                    )
                    decision = self.decide(receipts, locked, active)
                    expected_active = (
                        status_values == (GateStatus.PASS,) * 3
                        and conditional_values == (True,) * 3
                    )
                    self.assertEqual(decision.state is CandidateState.ACTIVE, expected_active)
                    self.assertFalse(decision.execution_authorized)
                    self.assertTrue(decision.base_answer_preserved)

    def test_every_binding_component_mismatch_fails_closed(self):
        receipts, locked, active = self.active_inputs()
        baseline = self.decide(receipts, locked, active)
        self.assertEqual(baseline.state, CandidateState.ACTIVE)
        for field_name in (
            "candidate_id",
            "task_digest",
            "base_answer_digest",
            "protocol_digest",
            "config_digest",
            "partition_digest",
            "budget_ceiling_digest",
        ):
            with self.subTest(field=field_name):
                replacement = (
                    "different-candidate"
                    if field_name == "candidate_id"
                    else digest(f"different:{field_name}")
                )
                changed = dataclasses.replace(self.binding, **{field_name: replacement})
                decision = decide_candidate_state(
                    changed,
                    enabled=True,
                    issuer=self.issuer,
                    now=self.now.isoformat(),
                    gate_receipts=receipts,
                    locked_token=locked,
                    active_token=active,
                    host_activation_approved=True,
                )
                self.assertIsNot(decision.state, CandidateState.ACTIVE)
                self.assertFalse(decision.execution_authorized)
                self.assertTrue(decision.base_answer_preserved)

    def test_conditionally_null_gate1_cannot_lock_or_activate(self):
        receipts, locked, active = self.active_inputs(conditional=(False, True, True))
        decision = self.decide(receipts, locked, active)
        self.assertEqual(decision.state, CandidateState.SHADOW)
        self.assertEqual(decision.reason, "gate1_not_promoted")

    def test_authority_expiry_staleness_and_replay_fail_closed(self):
        receipts, locked, active = self.active_inputs()
        stale = self.issuer.mint(
            self.binding,
            CandidateState.ACTIVE,
            active.evidence_digest,
            issued_at=(self.now + timedelta(minutes=1)).isoformat(),
            expires_at=(self.now + timedelta(minutes=2)).isoformat(),
            nonce="future",
        )
        expired = self.issuer.mint(
            self.binding,
            CandidateState.ACTIVE,
            active.evidence_digest,
            issued_at=(self.now - timedelta(minutes=2)).isoformat(),
            expires_at=(self.now - timedelta(minutes=1)).isoformat(),
            nonce="expired",
        )
        self.assertIsNot(self.decide(receipts, locked, stale).state, CandidateState.ACTIVE)
        self.assertIsNot(self.decide(receipts, locked, expired).state, CandidateState.ACTIVE)

        guard = AuthorityReplayGuard()
        self.assertTrue(
            guard.consume(
                active,
                self.issuer,
                self.binding,
                now=self.now.isoformat(),
                expected_state=CandidateState.ACTIVE,
            )
        )
        self.assertFalse(
            guard.consume(
                active,
                self.issuer,
                self.binding,
                now=self.now.isoformat(),
                expected_state=CandidateState.ACTIVE,
            )
        )

    def test_decisions_and_embedded_tokens_cannot_authorize_execution_or_mutate(self):
        receipts, locked, active = self.active_inputs()
        decision = self.decide(receipts, locked, active)
        self.assertEqual(decision.state, CandidateState.ACTIVE)
        self.assertFalse(decision.execution_authorized)
        self.assertFalse(decision.token.execution_authorized)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision.execution_authorized = True
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision.token.execution_authorized = True

    def test_conditional_validity_is_typed_and_default_fail_closed(self):
        with self.assertRaises(TypeError):
            self.receipt(Gate.GATE1, conditional_validity_passed="yes")  # type: ignore[arg-type]
        receipt = GateReceipt(
            gate=Gate.GATE1,
            status=GateStatus.PASS,
            binding_digest=self.binding.digest(),
            evidence_digest=digest("default-conditional-evidence"),
            solve_equivalence_digest=self.binding.base_answer_digest,
            cost_ledger_digest=digest("default-conditional-ledger"),
            reason="conditional validity intentionally unspecified",
            required_domains_passed=True,
            cost_complete=True,
        )
        self.assertFalse(receipt.qualifies(self.binding))


if __name__ == "__main__":
    unittest.main()
