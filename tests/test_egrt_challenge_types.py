from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from _challenge_helpers import request  # noqa: E402
from egrt_challenge_types import (  # noqa: E402
    ChallengeResolution,
    ChallengeState,
    ResolutionOutcome,
)


class ChallengeTypeTests(unittest.TestCase):
    def test_request_requires_sha256_binding(self) -> None:
        row = request()
        with self.assertRaises(ValueError):
            type(row)(**{**row.__dict__, "candidate_hash": "not-a-hash"})

    def test_resolved_requires_conclusive_outcome(self) -> None:
        row = request()
        with self.assertRaises(ValueError):
            ChallengeResolution(
                resolution_id="resolution-1",
                challenge_id=row.challenge_id,
                state=ChallengeState.RESOLVED,
                outcome=ResolutionOutcome.INCONCLUSIVE,
                verifier_receipt_id="receipt-1",
                verifier_module="mind",
                evidence_hash=row.candidate_hash,
                candidate_hash=row.candidate_hash,
                scope_hash=row.scope_hash,
                obligation_set_hash=row.obligation_set_hash,
                resolver="mind",
            )

    def test_unavailable_remains_distinct_from_resolved(self) -> None:
        row = request()
        resolution = ChallengeResolution(
            resolution_id="resolution-1",
            challenge_id=row.challenge_id,
            state=ChallengeState.UNAVAILABLE,
            outcome=ResolutionOutcome.INCONCLUSIVE,
            verifier_receipt_id=None,
            verifier_module=None,
            evidence_hash=None,
            candidate_hash=row.candidate_hash,
            scope_hash=row.scope_hash,
            obligation_set_hash=row.obligation_set_hash,
            resolver="mind",
            reason="solver absent",
        )
        self.assertEqual(resolution.state, ChallengeState.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
