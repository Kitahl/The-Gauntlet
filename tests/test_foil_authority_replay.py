from __future__ import annotations

import hashlib
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
    CandidateState,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class ReplayGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        self.binding = CandidateBinding(
            "candidate-1",
            d("task"),
            d("answer"),
            d("protocol"),
            d("config"),
            d("partition"),
            d("budget"),
        )
        self.issuer = AuthorityIssuer("host", b"z" * 32)
        self.token = self.issuer.mint(
            self.binding,
            CandidateState.ACTIVE,
            d("evidence"),
            issued_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=1)).isoformat(),
            nonce="one-use",
        )

    def test_valid_token_is_consumed_exactly_once(self):
        guard = AuthorityReplayGuard()
        self.assertTrue(
            guard.consume(
                self.token,
                self.issuer,
                self.binding,
                now=self.now.isoformat(),
                expected_state=CandidateState.ACTIVE,
            )
        )
        self.assertTrue(guard.consumed(self.token))
        self.assertFalse(
            guard.consume(
                self.token,
                self.issuer,
                self.binding,
                now=self.now.isoformat(),
                expected_state=CandidateState.ACTIVE,
            )
        )

    def test_wrong_state_or_expired_token_is_not_consumed(self):
        guard = AuthorityReplayGuard()
        wrong_state = guard.consume(
            self.token,
            self.issuer,
            self.binding,
            now=self.now.isoformat(),
            expected_state=CandidateState.LOCKED,
        )
        expired = guard.consume(
            self.token,
            self.issuer,
            self.binding,
            now=(self.now + timedelta(minutes=2)).isoformat(),
            expected_state=CandidateState.ACTIVE,
        )
        self.assertFalse(wrong_state)
        self.assertFalse(expired)
        self.assertFalse(guard.consumed(self.token))


if __name__ == "__main__":
    unittest.main()
