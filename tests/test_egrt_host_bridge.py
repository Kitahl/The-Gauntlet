"""Tests for the digest-only explicit host-action request bridge."""

from __future__ import annotations

import dataclasses
import hashlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_certificates import CertificateClass  # noqa: E402
from egrt_host_bridge import HostActionRequest, create_host_action_request  # noqa: E402
from foil_authority_replay import AuthorityReplayGuard  # noqa: E402
from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateDecision,
    CandidateState,
)
from foil_shadow_repair import admit_shadow_repair, propose_shadow_repair  # noqa: E402

from tests.test_foil_shadow_repair import authority, certificate, external  # noqa: E402


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class HostBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    def admitted(self):
        proposal = propose_shadow_repair(authority(), external())
        return admit_shadow_repair(
            proposal,
            structural_certificate=certificate(
                CertificateClass.STRUCTURAL_ONLY, "builtin.exact_match"
            ),
            semantic_certificate=certificate(
                CertificateClass.INDEPENDENT_SEMANTIC, "builtin.json_exact"
            ),
        )

    def authority_inputs(
        self,
        admission,
        *,
        state: CandidateState = CandidateState.ACTIVE,
        token_binding: CandidateBinding | None = None,
    ) -> tuple[
        CandidateDecision,
        CandidateBinding,
        AuthorityIssuer,
        AuthorityReplayGuard,
    ]:
        candidate = admission.proposal.candidate
        binding = CandidateBinding(
            candidate_id=candidate.candidate_id,
            task_digest=d("task"),
            base_answer_digest=candidate.base_digest,
            protocol_digest=d("protocol"),
            config_digest=d("config"),
            partition_digest=d("partition"),
            budget_ceiling_digest=d("budget"),
        )
        issuer = AuthorityIssuer("host.bridge", b"b" * 32)
        token = issuer.mint(
            token_binding or binding,
            state,
            d("active evidence"),
            issued_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=5)).isoformat(),
            nonce=f"bridge-{state.value.lower()}",
        )
        return (
            CandidateDecision(state, "host activation decision", token),
            binding,
            issuer,
            AuthorityReplayGuard(),
        )

    def create_with_active_authority(self, admission):
        decision, binding, issuer, replay_guard = self.authority_inputs(admission)
        return create_host_action_request(
            admission,
            decision=decision,
            binding=binding,
            issuer=issuer,
            now=self.now.isoformat(),
            replay_guard=replay_guard,
        )

    def test_request_contains_only_candidate_digests_and_locator(self) -> None:
        request = self.create_with_active_authority(self.admitted())
        self.assertIsInstance(request, HostActionRequest)
        self.assertEqual(request.artifact_locator, "host://artifact/candidate-1")
        self.assertTrue(request.requires_explicit_host_action)
        self.assertFalse(request.execution_authorized)
        self.assertTrue(request.base_answer_preserved)
        self.assertNotIn("producer", vars(request))
        self.assertNotIn("payload", vars(request))

    def test_request_requires_a_committable_admission(self) -> None:
        proposal = propose_shadow_repair(authority(), external())
        incomplete = admit_shadow_repair(
            proposal,
            structural_certificate=certificate(
                CertificateClass.STRUCTURAL_ONLY, "builtin.exact_match"
            ),
        )
        decision, binding, issuer, replay_guard = self.authority_inputs(incomplete)
        with self.assertRaisesRegex(ValueError, "COMMITTABLE"):
            create_host_action_request(
                incomplete,
                decision=decision,
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )

    def test_raw_active_or_locked_decision_never_creates_a_request(self) -> None:
        admission = self.admitted()
        _, binding, issuer, replay_guard = self.authority_inputs(admission)
        with self.assertRaisesRegex(ValueError, "ACTIVE candidate decision token"):
            create_host_action_request(
                admission,
                decision=CandidateDecision(CandidateState.ACTIVE, "raw active"),
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )
        locked, binding, issuer, replay_guard = self.authority_inputs(
            admission, state=CandidateState.LOCKED
        )
        with self.assertRaisesRegex(ValueError, "ACTIVE candidate decision token"):
            create_host_action_request(
                admission,
                decision=locked,
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )

    def test_forged_expired_wrong_binding_and_replayed_tokens_fail_closed(self) -> None:
        admission = self.admitted()
        decision, binding, issuer, replay_guard = self.authority_inputs(admission)
        forged = dataclasses.replace(decision.token, evidence_digest=d("forged"))
        with self.assertRaisesRegex(ValueError, "current, matching, unused"):
            create_host_action_request(
                admission,
                decision=CandidateDecision(CandidateState.ACTIVE, "forged", forged),
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )
        with self.assertRaisesRegex(ValueError, "current, matching, unused"):
            create_host_action_request(
                admission,
                decision=decision,
                binding=binding,
                issuer=issuer,
                now=(self.now + timedelta(minutes=6)).isoformat(),
                replay_guard=AuthorityReplayGuard(),
            )
        wrong_token_binding = dataclasses.replace(binding, config_digest=d("other config"))
        wrong_token = issuer.mint(
            wrong_token_binding,
            CandidateState.ACTIVE,
            d("active evidence"),
            issued_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=5)).isoformat(),
            nonce="wrong-binding",
        )
        with self.assertRaisesRegex(ValueError, "current, matching, unused"):
            create_host_action_request(
                admission,
                decision=CandidateDecision(CandidateState.ACTIVE, "wrong binding", wrong_token),
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=AuthorityReplayGuard(),
            )
        create_host_action_request(
            admission,
            decision=decision,
            binding=binding,
            issuer=issuer,
            now=self.now.isoformat(),
            replay_guard=replay_guard,
        )
        with self.assertRaisesRegex(ValueError, "current, matching, unused"):
            create_host_action_request(
                admission,
                decision=decision,
                binding=binding,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )

    def test_binding_must_match_the_repair_candidate_and_a0(self) -> None:
        admission = self.admitted()
        decision, binding, issuer, replay_guard = self.authority_inputs(admission)
        mismatch = dataclasses.replace(binding, candidate_id="candidate-2")
        with self.assertRaisesRegex(ValueError, "match the repair candidate and A0"):
            create_host_action_request(
                admission,
                decision=decision,
                binding=mismatch,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )
        mismatch = dataclasses.replace(binding, base_answer_digest=d("other A0"))
        with self.assertRaisesRegex(ValueError, "match the repair candidate and A0"):
            create_host_action_request(
                admission,
                decision=decision,
                binding=mismatch,
                issuer=issuer,
                now=self.now.isoformat(),
                replay_guard=replay_guard,
            )

    def test_request_invariants_cannot_be_overridden(self) -> None:
        request = self.create_with_active_authority(self.admitted())
        with self.assertRaises(ValueError):
            HostActionRequest(
                candidate_id=request.candidate_id,
                base_digest=request.base_digest,
                candidate_digest=request.candidate_digest,
                scope_digest=request.scope_digest,
                obligation_set_digest=request.obligation_set_digest,
                artifact_locator=request.artifact_locator,
                artifact_sha256=request.artifact_sha256,
                proposal_digest=request.proposal_digest,
                structural_certificate_digest=request.structural_certificate_digest,
                semantic_certificate_digest=request.semantic_certificate_digest,
                execution_authorized=True,
            )


if __name__ == "__main__":
    unittest.main()