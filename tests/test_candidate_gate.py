from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_candidate_gate import (  # noqa: E402
    AdmissionState,
    CandidateBinding,
    CandidateRepair,
    CheckStatus,
    PatchCertificate,
    SemanticVerification,
    StructuralCertificate,
    decide_admission,
)

BASE = "a" * 64
CANDIDATE = "b" * 64
SCOPE = "c" * 64
OBLIGATIONS = "d" * 64
ENVIRONMENT = "e" * 64


def binding() -> CandidateBinding:
    return CandidateBinding("candidate", BASE, CANDIDATE, SCOPE, OBLIGATIONS, "producer", "1")


def structural(verifier: str = "structural", environment: str = ENVIRONMENT) -> StructuralCertificate:
    return StructuralCertificate(BASE, CANDIDATE, SCOPE, OBLIGATIONS, verifier, "1", environment, CheckStatus.PASS)


def semantic(verifier: str = "semantic", environment: str = ENVIRONMENT) -> SemanticVerification:
    return SemanticVerification(BASE, CANDIDATE, SCOPE, OBLIGATIONS, verifier, "1", environment, CheckStatus.PASS)


class CandidateGateTests(unittest.TestCase):
    def test_bound_distinct_passes_are_committable_but_not_executable(self) -> None:
        decision = decide_admission(binding(), structural(), semantic())
        self.assertEqual(decision.state, AdmissionState.COMMITTABLE)
        self.assertTrue(decision.host_commit_required)
        self.assertFalse(decision.execution_authorized)

    def test_producer_and_verifiers_must_be_distinct(self) -> None:
        self.assertEqual(decide_admission(binding(), structural("producer"), semantic()).state, AdmissionState.REJECTED)
        self.assertEqual(decide_admission(binding(), structural("same"), semantic("same")).state, AdmissionState.REJECTED)

    def test_environment_binding_mismatch_rejected(self) -> None:
        self.assertEqual(decide_admission(binding(), structural(), semantic(environment="f" * 64)).state, AdmissionState.REJECTED)

    def test_legacy_foil_shapes_are_compatible(self) -> None:
        candidate = CandidateRepair(
            candidate_id="candidate",
            base_digest=BASE,
            candidate_digest=CANDIDATE,
            scope_digest=SCOPE,
            obligation_set_digest=OBLIGATIONS,
            repair_producer="producer",
            repair_producer_version="1",
        )
        certificate = PatchCertificate(BASE, CANDIDATE, SCOPE, OBLIGATIONS, "structural", "1", ENVIRONMENT, CheckStatus.PASS)
        self.assertEqual(decide_admission(candidate, certificate, semantic()).state, AdmissionState.COMMITTABLE)


if __name__ == "__main__":
    unittest.main()
