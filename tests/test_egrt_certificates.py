from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_certificates import (  # noqa: E402
    CertificateClass,
    EvidenceCertificate,
    to_patch_certificate,
    to_semantic_verification,
    validate_certificate,
)
from egrt_claims import (  # noqa: E402
    Applicability,
    Decidability,
    ImmutableBindings,
    PostSolveObligation,
)
from egrt_coverage import (  # noqa: E402
    ContributionOutcome,
    CoverageContribution,
    CoverageRequirement,
    summarize_coverage,
)  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY  # noqa: E402
from foil_authority import CandidateRepair, CheckStatus, decide_admission  # noqa: E402

BASE, CANDIDATE, SCOPE, OBLIGATIONS, ENV = (char * 64 for char in "abcde")


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "f0123"])


def coverage():
    req = CoverageRequirement(
        PostSolveObligation("obl-1", "claim-1", "must match", 1),
        Decidability.DETERMINISTIC,
        Applicability.APPLICABLE,
    )
    return summarize_coverage(
        (req,), (CoverageContribution("obl-1", "9" * 64, ContributionOutcome.PASS, "passed"),)
    )


def certificate(
    kind: CertificateClass, verifier_id: str = "builtin.exact_match"
) -> EvidenceCertificate:
    payload = (
        {"actual": '{"x": 1}', "expected": '{"x": 1}'}
        if verifier_id == "builtin.json_exact"
        else {"actual": "x", "expected": "x"}
    )
    result = DEFAULT_REGISTRY.run(verifier_id, payload)
    return EvidenceCertificate(
        certificate_id="cert-1",
        certificate_class=kind,
        claim_id="claim-1",
        base_digest=BASE,
        candidate_digest=CANDIDATE,
        scope_digest=SCOPE,
        obligation_set_digest=OBLIGATIONS,
        bindings=bindings(),
        verifier=result,
        environment_digest=ENV,
        evidence_digests=("8" * 64,),
        coverage=coverage(),
    )


class EvidenceCertificateTests(unittest.TestCase):
    def test_classes_bind_full_context_and_validate_complete_scope(self) -> None:
        for kind in CertificateClass:
            with self.subTest(kind=kind):
                valid, reason = validate_certificate(certificate(kind))
                self.assertEqual(valid, kind is not CertificateClass.INCOMPLETE_SCOPE)
                self.assertTrue(reason)

    def test_adapters_preserve_structural_semantic_separation(self) -> None:
        structural = certificate(CertificateClass.STRUCTURAL_ONLY)
        semantic = certificate(CertificateClass.INDEPENDENT_SEMANTIC, "builtin.json_exact")
        patch = to_patch_certificate(structural)
        meaning = to_semantic_verification(semantic)
        self.assertEqual(patch.status, CheckStatus.PASS)
        self.assertEqual(meaning.status, CheckStatus.PASS)
        candidate = CandidateRepair(
            "candidate-1", BASE, CANDIDATE, SCOPE, OBLIGATIONS, "foil.repair", "1"
        )
        decision = decide_admission(candidate, patch, meaning)
        self.assertTrue(decision.candidate_committable)
        with self.assertRaises(ValueError):
            to_patch_certificate(semantic)
        with self.assertRaises(ValueError):
            to_semantic_verification(structural)

    def test_certificate_digests_must_be_canonical_lowercase_sha256(self) -> None:
        valid = certificate(CertificateClass.STRUCTURAL_ONLY)
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(field="environment", invalid=invalid), self.assertRaises(ValueError):
                dataclasses.replace(valid, environment_digest=invalid)
            with self.subTest(field="evidence", invalid=invalid), self.assertRaises(ValueError):
                dataclasses.replace(valid, evidence_digests=(invalid,))

    def test_incomplete_scope_never_adapts_to_a_passing_certificate(self) -> None:
        incomplete = certificate(CertificateClass.INCOMPLETE_SCOPE)
        valid, reason = validate_certificate(incomplete)
        self.assertFalse(valid)
        self.assertEqual(reason, "incomplete_scope")
        with self.assertRaises(ValueError):
            to_patch_certificate(incomplete)


if __name__ == "__main__":
    unittest.main()
