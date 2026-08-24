from __future__ import annotations

import dataclasses
import hashlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateState,
    Gate,
    GateReceipt,
    GateStatus,
    decide_candidate_state,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class CandidateStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        self.binding = CandidateBinding(
            candidate_id="foil-v5-candidate-1",
            task_digest=d("task"),
            base_answer_digest=d("answer"),
            protocol_digest=d("protocol"),
            config_digest=d("config"),
            partition_digest=d("partition"),
            budget_ceiling_digest=d("budget"),
        )
        self.issuer = AuthorityIssuer("host.gate-verifier", b"x" * 32)

    def receipt(self, gate: Gate, status: GateStatus = GateStatus.PASS) -> GateReceipt:
        return GateReceipt(
            gate=gate,
            status=status,
            binding_digest=self.binding.digest(),
            evidence_digest=d(gate.value + " evidence"),
            solve_equivalence_digest=self.binding.base_answer_digest,
            cost_ledger_digest=d(gate.value + " ledger"),
            reason="pre-registered gate result",
            forbidden_calls=0,
            required_domains_passed=True,
            cost_complete=True,
            conditional_validity_passed=True,
        )

    def token(self, state: CandidateState, evidence: str):
        return self.issuer.mint(
            self.binding,
            state,
            evidence,
            issued_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=5)).isoformat(),
            nonce=state.value.lower(),
        )

    def test_disabled_is_dormant_and_missing_gate_is_shadow(self):
        dormant = decide_candidate_state(
            self.binding, enabled=False, issuer=self.issuer, now=self.now.isoformat()
        )
        shadow = decide_candidate_state(
            self.binding, enabled=True, issuer=self.issuer, now=self.now.isoformat()
        )
        self.assertEqual(dormant.state, CandidateState.DORMANT)
        self.assertEqual(shadow.state, CandidateState.SHADOW)
        self.assertFalse(dormant.execution_authorized)
        self.assertTrue(dormant.base_answer_preserved)

    def test_gate1_requires_matching_locked_authority(self):
        gate1 = self.receipt(Gate.GATE1)
        absent = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=(gate1,),
        )
        locked = self.token(CandidateState.LOCKED, gate1.digest())
        present = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=(gate1,),
            locked_token=locked,
        )
        self.assertEqual(absent.state, CandidateState.SHADOW)
        self.assertEqual(present.state, CandidateState.LOCKED)

    def test_active_requires_gate2_gate3_host_and_matching_token(self):
        gates = tuple(self.receipt(gate) for gate in Gate)
        combined = hashlib.sha256(
            "".join(row.digest() for row in gates).encode("ascii")
        ).hexdigest()
        locked = self.token(CandidateState.LOCKED, gates[0].digest())
        active = self.token(CandidateState.ACTIVE, combined)
        decision = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=gates,
            locked_token=locked,
            active_token=active,
            host_activation_approved=True,
        )
        self.assertEqual(decision.state, CandidateState.ACTIVE)
        self.assertFalse(decision.execution_authorized)
        self.assertTrue(decision.host_action_required)

    def test_fail_unknown_duplicate_or_wrong_binding_never_promotes(self):
        for status in (GateStatus.FAIL, GateStatus.UNKNOWN, GateStatus.NOT_RUN):
            with self.subTest(status=status):
                gate1 = self.receipt(Gate.GATE1, status)
                token = self.token(CandidateState.LOCKED, gate1.digest())
                decision = decide_candidate_state(
                    self.binding,
                    enabled=True,
                    issuer=self.issuer,
                    now=self.now.isoformat(),
                    gate_receipts=(gate1,),
                    locked_token=token,
                )
                self.assertEqual(decision.state, CandidateState.SHADOW)
        good = self.receipt(Gate.GATE1)
        duplicate = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=(good, good),
        )
        self.assertEqual(duplicate.state, CandidateState.SHADOW)

    def test_tampered_expired_and_wrong_candidate_tokens_fail_closed(self):
        gate1 = self.receipt(Gate.GATE1)
        valid = self.token(CandidateState.LOCKED, gate1.digest())
        tampered = dataclasses.replace(valid, evidence_digest=d("tampered"))
        expired = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=(self.now + timedelta(minutes=6)).isoformat(),
            gate_receipts=(gate1,),
            locked_token=valid,
        )
        changed = dataclasses.replace(self.binding, candidate_id="foil-v5-candidate-2")
        wrong_candidate = decide_candidate_state(
            changed,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=(gate1,),
            locked_token=valid,
        )
        tamper_result = decide_candidate_state(
            self.binding,
            enabled=True,
            issuer=self.issuer,
            now=self.now.isoformat(),
            gate_receipts=(gate1,),
            locked_token=tampered,
        )
        self.assertEqual(expired.state, CandidateState.SHADOW)
        self.assertEqual(wrong_candidate.state, CandidateState.SHADOW)
        self.assertEqual(tamper_result.state, CandidateState.SHADOW)

    def test_strict_digest_and_boolean_types(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(self.binding, config_digest="not-a-digest")
        with self.assertRaises(ValueError):
            dataclasses.replace(self.receipt(Gate.GATE1), forbidden_calls=True)


if __name__ == "__main__":
    unittest.main()
