"""Safety contracts for externally supplied FOIL shadow repair references."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_certificates import CertificateClass, EvidenceCertificate  # noqa: E402
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
)
from egrt_types import ArtifactRef  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY  # noqa: E402
from foil_authority import (  # noqa: E402
    AdmissionState,
    AuthorityAction,
    AuthorityCeiling,
    AuthorityDecision,
    EvidenceClass,
)
from foil_shadow_repair import (  # noqa: E402
    ExternalRepairCandidate,
    admit_shadow_repair,
    propose_shadow_repair,
)

BASE, CANDIDATE, SCOPE, OBLIGATIONS, ENV = (char * 64 for char in "abcde")


def authority(action: AuthorityAction = AuthorityAction.PROPOSE_REPAIR_SHADOW) -> AuthorityDecision:
    return AuthorityDecision(
        action=action,
        reason="frozen shadow authority",
        sensor_id="residual.scanner",
        evidence_class=EvidenceClass.MEASURED,
        authority_ceiling=AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
    )


def external(producer: str = "external.producer") -> ExternalRepairCandidate:
    return ExternalRepairCandidate(
        candidate_id="candidate-1",
        base_digest=BASE,
        candidate_digest=CANDIDATE,
        scope_digest=SCOPE,
        obligation_set_digest=OBLIGATIONS,
        producer_id=producer,
        producer_version="1",
        artifact=ArtifactRef(locator="host://artifact/candidate-1", sha256=CANDIDATE),
    )


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "f0123"])


def coverage():
    requirement = CoverageRequirement(
        PostSolveObligation("obl-1", "claim-1", "frozen predicate", 1),
        Decidability.DETERMINISTIC,
        Applicability.APPLICABLE,
    )
    return summarize_coverage(
        (requirement,), (CoverageContribution("obl-1", "9" * 64, ContributionOutcome.PASS, "pass"),)
    )


def certificate(kind: CertificateClass, verifier_id: str) -> EvidenceCertificate:
    payload = (
        {"actual": '{"x": 1}', "expected": '{"x": 1}'}
        if verifier_id == "builtin.json_exact"
        else {"actual": "x", "expected": "x"}
    )
    return EvidenceCertificate(
        certificate_id=f"cert-{kind.value}",
        certificate_class=kind,
        claim_id="claim-1",
        base_digest=BASE,
        candidate_digest=CANDIDATE,
        scope_digest=SCOPE,
        obligation_set_digest=OBLIGATIONS,
        bindings=bindings(),
        verifier=DEFAULT_REGISTRY.run(verifier_id, payload),
        environment_digest=ENV,
        evidence_digests=("8" * 64,),
        coverage=coverage(),
    )


class ShadowRepairTests(unittest.TestCase):
    def test_only_exact_shadow_authority_can_form_a_proposal(self) -> None:
        with self.assertRaisesRegex(ValueError, "PROPOSE_REPAIR_SHADOW"):
            propose_shadow_repair(authority(AuthorityAction.FLAG), external())
        proposal = propose_shadow_repair(authority(), external())
        self.assertEqual(proposal.candidate.base_digest, BASE)
        self.assertEqual(proposal.artifact.sha256, CANDIDATE)
        self.assertTrue(proposal.base_answer_preserved)
        self.assertFalse(proposal.execution_authorized)

    def test_external_candidate_must_be_content_addressed_delta(self) -> None:
        with self.assertRaisesRegex(ValueError, "differ from A0"):
            ExternalRepairCandidate(
                "candidate-1",
                BASE,
                BASE,
                SCOPE,
                OBLIGATIONS,
                "producer",
                "1",
                ArtifactRef(locator="host://artifact", sha256=BASE),
            )
        with self.assertRaisesRegex(ValueError, "artifact.sha256"):
            ExternalRepairCandidate(
                "candidate-1",
                BASE,
                CANDIDATE,
                SCOPE,
                OBLIGATIONS,
                "producer",
                "1",
                ArtifactRef(locator="host://artifact", sha256=None),
            )

    def test_admission_requires_separate_valid_structural_and_semantic_certificates(self) -> None:
        proposal = propose_shadow_repair(authority(), external())
        structural = certificate(CertificateClass.STRUCTURAL_ONLY, "builtin.exact_match")
        semantic = certificate(CertificateClass.INDEPENDENT_SEMANTIC, "builtin.json_exact")
        admitted = admit_shadow_repair(
            proposal, structural_certificate=structural, semantic_certificate=semantic
        )
        self.assertEqual(admitted.decision.state, AdmissionState.COMMITTABLE)
        self.assertTrue(admitted.base_answer_preserved)
        self.assertFalse(admitted.execution_authorized)
        self.assertEqual(
            admit_shadow_repair(proposal, structural_certificate=structural).decision.state,
            AdmissionState.SEMANTIC_VERIFICATION_REQUIRED,
        )

    def test_producer_and_verifiers_must_all_be_distinct(self) -> None:
        proposal = propose_shadow_repair(authority(), external("builtin.exact_match"))
        structural = certificate(CertificateClass.STRUCTURAL_ONLY, "builtin.exact_match")
        semantic = certificate(CertificateClass.INDEPENDENT_SEMANTIC, "builtin.json_exact")
        self.assertEqual(
            admit_shadow_repair(
                proposal, structural_certificate=structural, semantic_certificate=semantic
            ).decision.state,
            AdmissionState.REJECTED,
        )
        proposal = propose_shadow_repair(authority(), external())
        structural = certificate(CertificateClass.STRUCTURAL_ONLY, "builtin.exact_match")
        same_semantic = certificate(CertificateClass.INDEPENDENT_SEMANTIC, "builtin.exact_match")
        self.assertEqual(
            admit_shadow_repair(
                proposal, structural_certificate=structural, semantic_certificate=same_semantic
            ).decision.state,
            AdmissionState.REJECTED,
        )

    def test_only_certificate_classes_in_their_separate_lanes_are_accepted(self) -> None:
        proposal = propose_shadow_repair(authority(), external())
        semantic = certificate(CertificateClass.INDEPENDENT_SEMANTIC, "builtin.json_exact")
        with self.assertRaisesRegex(ValueError, "structural or predicate"):
            admit_shadow_repair(proposal, structural_certificate=semantic)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_SEMANTIC"):
            admit_shadow_repair(
                proposal,
                semantic_certificate=certificate(
                    CertificateClass.PREDICATE_SCOPED, "builtin.exact_match"
                ),
            )

    def test_module_offers_no_generation_or_execution_surface(self) -> None:
        names = set(vars(__import__("foil_shadow_repair")).keys())
        for forbidden in ("generate", "execute", "network", "subprocess", "model"):
            self.assertFalse(any(forbidden in name.lower() for name in names))
        self.assertNotIn("payload", inspect.signature(propose_shadow_repair).parameters)


if __name__ == "__main__":
    unittest.main()
