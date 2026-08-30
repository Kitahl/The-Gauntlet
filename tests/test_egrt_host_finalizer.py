"""Tests for the explicit, fail-closed host finalization boundary."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import sys
import unittest
from datetime import datetime, timedelta, timezone
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
from egrt_host_bridge import HostActionRequest, create_host_action_request  # noqa: E402
from egrt_host_finalizer import (  # noqa: E402
    FinalizationState,
    HostCommitApproval,
    answer_digest,
    finalize_host_answer,
    host_request_digest,
)
from egrt_types import ArtifactRef  # noqa: E402
from egrt_verifier_authority import VerifierRole, issue_verifier_evidence  # noqa: E402
from foil_authority import (  # noqa: E402
    AuthorityAction,
    AuthorityCeiling,
    AuthorityDecision,
    EvidenceClass,
)
from foil_authority_replay import AuthorityReplayGuard  # noqa: E402
from foil_candidate_state import (  # noqa: E402
    AuthorityIssuer,
    CandidateBinding,
    CandidateState,
    Gate,
    GateReceipt,
    GateStatus,
    decide_candidate_state,
)
from foil_shadow_repair import (  # noqa: E402
    ExternalRepairCandidate,
    admit_shadow_repair,
    propose_shadow_repair,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def direct_request(base: str, candidate: str, *, artifact_digest: str | None = None):
    return HostActionRequest(
        candidate_id="candidate-1",
        base_digest=answer_digest(base),
        candidate_digest=answer_digest(candidate),
        scope_digest=d("scope"),
        obligation_set_digest=d("obligations"),
        artifact_locator="host://candidate-1",
        artifact_sha256=artifact_digest or answer_digest(candidate),
        proposal_digest=d("proposal"),
        structural_certificate_digest=d("structural"),
        semantic_certificate_digest=d("semantic"),
    )


def approval(
    request: HostActionRequest,
    *,
    request_hash: str | None = None,
    candidate_hash: str | None = None,
):
    return HostCommitApproval(
        request_digest=request_hash or host_request_digest(request),
        candidate_digest=candidate_hash or request.candidate_digest,
        approver_id="host.owner",
        approved_at="2026-08-24T12:00:00+00:00",
        reason="explicit test approval",
    )


def complete_coverage():
    requirement = CoverageRequirement(
        PostSolveObligation("obl-1", "claim-1", "exact result must match", 1),
        Decidability.DETERMINISTIC,
        Applicability.APPLICABLE,
    )
    contribution = CoverageContribution(
        "obl-1",
        d("evidence"),
        ContributionOutcome.PASS,
        "verified",
    )
    return summarize_coverage((requirement,), (contribution,))


def evidence_certificate(
    kind: CertificateClass,
    *,
    base_digest: str,
    candidate_digest: str,
    verifier_id: str,
    provenance_group: str,
) -> EvidenceCertificate:
    payload = (
        {"expression": "2+2", "expected": "4"}
        if verifier_id == "builtin.exact_arithmetic"
        else {"actual": "The exact result is 4.", "expected": "The exact result is 4."}
    )
    verifier = issue_verifier_evidence(
        verifier_id=verifier_id,
        role=VerifierRole.STRUCTURAL_VERIFIER,
        base_digest=base_digest,
        candidate_digest=candidate_digest,
        scope_digest=d("scope"),
        obligation_set_digest=d("obligations"),
        input_data=payload,
    )
    if kind is CertificateClass.INDEPENDENT_SEMANTIC:
        verifier = dataclasses.replace(
            verifier, role=VerifierRole.SEMANTIC_VERIFIER
        )
    if provenance_group != verifier.observed_result.provenance_group:
        verifier = dataclasses.replace(
            verifier,
            observed_result=dataclasses.replace(
                verifier.observed_result,
                provenance_group=provenance_group,
            ),
        )
    verifier = dataclasses.replace(
        verifier, evidence_sha256=verifier.computed_evidence_sha256
    )
    return EvidenceCertificate(
        certificate_id=f"cert-{kind.value.lower()}",
        certificate_class=kind,
        claim_id="claim-1",
        base_digest=base_digest,
        candidate_digest=candidate_digest,
        scope_digest=d("scope"),
        obligation_set_digest=d("obligations"),
        bindings=ImmutableBindings(
            base_digest,
            d("task"),
            d("spec"),
            d("compiler"),
            d("config"),
        ),
        evidence=verifier,
        coverage=complete_coverage(),
    )


def full_pipeline_request(base: str, candidate: str) -> HostActionRequest:
    base_digest = answer_digest(base)
    candidate_digest = answer_digest(candidate)
    authority = AuthorityDecision(
        action=AuthorityAction.PROPOSE_REPAIR_SHADOW,
        reason="explicitly enabled calibrated test route",
        sensor_id="pilot.exact-arithmetic",
        evidence_class=EvidenceClass.PROVEN,
        authority_ceiling=AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
    )
    external = ExternalRepairCandidate(
        candidate_id="candidate-1",
        base_digest=base_digest,
        candidate_digest=candidate_digest,
        scope_digest=d("scope"),
        obligation_set_digest=d("obligations"),
        producer_id="host.fixture-producer",
        producer_version="1",
        producer_implementation_digest=d("host.fixture-producer.impl"),
        artifact=ArtifactRef(locator="host://candidate-1", sha256=candidate_digest),
    )
    proposal = propose_shadow_repair(authority, external)
    admission = admit_shadow_repair(
        proposal,
        structural_certificate=evidence_certificate(
            CertificateClass.PREDICATE_SCOPED,
            base_digest=base_digest,
            candidate_digest=candidate_digest,
            verifier_id="builtin.exact_arithmetic",
            provenance_group="egrt.builtin",
        ),
        semantic_certificate=evidence_certificate(
            CertificateClass.INDEPENDENT_SEMANTIC,
            base_digest=base_digest,
            candidate_digest=candidate_digest,
            verifier_id="builtin.exact_match",
            provenance_group="host.independent-semantic",
        ),
    )

    binding = CandidateBinding(
        candidate_id="candidate-1",
        task_digest=d("task"),
        base_answer_digest=base_digest,
        protocol_digest=d("protocol"),
        config_digest=d("config"),
        partition_digest=d("partition"),
        budget_ceiling_digest=d("budget"),
    )
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    issuer = AuthorityIssuer("host.finalization", b"h" * 32)

    def gate_receipt(gate: Gate) -> GateReceipt:
        return GateReceipt(
            gate=gate,
            status=GateStatus.PASS,
            binding_digest=binding.digest(),
            evidence_digest=d(f"{gate.value}-evidence"),
            solve_equivalence_digest=base_digest,
            cost_ledger_digest=d(f"{gate.value}-cost"),
            reason="synthetic contract-pilot gate",
            forbidden_calls=0,
            required_domains_passed=True,
            cost_complete=True,
            conditional_validity_passed=True,
        )

    gates = tuple(gate_receipt(gate) for gate in Gate)
    locked = issuer.mint(
        binding,
        CandidateState.LOCKED,
        gates[0].digest(),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        nonce="locked-finalization",
    )
    combined = hashlib.sha256("".join(row.digest() for row in gates).encode("ascii")).hexdigest()
    active = issuer.mint(
        binding,
        CandidateState.ACTIVE,
        combined,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        nonce="active-finalization",
    )
    decision = decide_candidate_state(
        binding,
        enabled=True,
        issuer=issuer,
        now=now.isoformat(),
        gate_receipts=gates,
        locked_token=locked,
        active_token=active,
        host_activation_approved=True,
    )
    return create_host_action_request(
        admission,
        decision=decision,
        binding=binding,
        issuer=issuer,
        now=now.isoformat(),
        replay_guard=AuthorityReplayGuard(),
    )


class HostFinalizerTests(unittest.TestCase):
    def test_full_chain_rejects_unregistered_semantic_evidence_before_host_request(self) -> None:
        base = "The exact result is 5."
        candidate = "The exact result is 4."
        with self.assertRaises(ValueError):
            full_pipeline_request(base, candidate)

    def test_missing_approval_returns_the_identical_base_object(self) -> None:
        base = "The exact result is 5."
        candidate = "The exact result is 4."
        result = finalize_host_answer(
            direct_request(base, candidate),
            base_answer=base,
            candidate_answer=candidate,
        )
        self.assertEqual(result.state, FinalizationState.BASE_PRESERVED)
        self.assertIs(result.answer, base)
        self.assertEqual(result.reason, "host_approval_missing")

    def test_all_content_or_approval_mismatches_preserve_a0(self) -> None:
        base = "correct A0"
        candidate = "candidate A1"
        request = direct_request(base, candidate)
        cases = (
            (
                direct_request(base, candidate, artifact_digest=d("other artifact")),
                base,
                candidate,
                None,
                "artifact_binding_mismatch",
            ),
            (request, base, "tampered candidate", approval(request), "candidate_digest_mismatch"),
            (request, "different base", candidate, approval(request), "base_digest_mismatch"),
            (request, base, candidate.encode("utf-8"), approval(request), "answer_type_mismatch"),
            (
                request,
                base,
                candidate,
                approval(request, request_hash=d("other request")),
                "approval_request_mismatch",
            ),
            (
                request,
                base,
                candidate,
                approval(request, candidate_hash=d("other candidate")),
                "approval_candidate_mismatch",
            ),
        )
        for item_request, item_base, item_candidate, item_approval, expected in cases:
            with self.subTest(reason=expected):
                result = finalize_host_answer(
                    item_request,
                    base_answer=item_base,
                    candidate_answer=item_candidate,
                    approval=item_approval,
                )
                self.assertEqual(result.state, FinalizationState.BASE_PRESERVED)
                self.assertIs(result.answer, item_base)
                self.assertEqual(result.reason, expected)

    def test_trace_contains_digests_but_never_raw_answers(self) -> None:
        base = "private base answer"
        candidate = "private candidate answer"
        request = direct_request(base, candidate)
        result = finalize_host_answer(
            request,
            base_answer=base,
            candidate_answer=candidate,
            approval=approval(request),
        )
        trace = result.trace()
        self.assertFalse(trace["raw_answer_stored"])
        self.assertNotIn(base, str(trace))
        self.assertNotIn(candidate, str(trace))
        self.assertEqual(len(trace["finalization_digest"]), 64)

    def test_approval_is_explicit_and_module_has_no_execution_or_io_surface(self) -> None:
        request = direct_request("A0", "A1")
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            dataclasses.replace(approval(request), approved=False)
        source = inspect.getsource(sys.modules["egrt_host_finalizer"]).lower()
        for forbidden in ("subprocess", "requests", "openrouter", "socket", "pathlib"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
