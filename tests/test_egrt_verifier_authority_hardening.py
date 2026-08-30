"""Adversarial regressions for verifier identity and evidence replay."""
from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_verifier_authority import (  # noqa: E402
    DEFAULT_AUTHORITY_REGISTRY,
    VerifierEvidenceManifest,
    VerifierRole,
    issue_verifier_evidence,
    validate_verifier_evidence,
)
import egrt_verifiers  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus  # noqa: E402
from foil_authority import (  # noqa: E402
    AdmissionState,
    CandidateRepair,
    PatchCertificate,
    SemanticVerification,
    decide_admission,
)


BASE, CANDIDATE, SCOPE, OBLIGATIONS = (char * 64 for char in "abcd")
EXPECTED = (BASE, CANDIDATE, SCOPE, OBLIGATIONS)


def issued() -> VerifierEvidenceManifest:
    return issue_verifier_evidence(
        verifier_id="builtin.exact_match",
        role=VerifierRole.STRUCTURAL_VERIFIER,
        base_digest=BASE,
        candidate_digest=CANDIDATE,
        scope_digest=SCOPE,
        obligation_set_digest=OBLIGATIONS,
        input_data={"actual": "x", "expected": "x"},
        input_artifact_digests=("8" * 64,),
    )


def rehashed(manifest: VerifierEvidenceManifest, **changes: object) -> VerifierEvidenceManifest:
    changed = dataclasses.replace(manifest, **changes)
    return dataclasses.replace(
        changed, evidence_sha256=changed.computed_evidence_sha256
    )


class VerifierAuthorityRegistryTests(unittest.TestCase):
    def test_closed_registration_resolves_content_bound_identity(self) -> None:
        registration = DEFAULT_AUTHORITY_REGISTRY.resolve("builtin.exact_match")
        self.assertIn(VerifierRole.STRUCTURAL_VERIFIER, registration.authorized_roles)
        self.assertEqual(len(registration.implementation_digest), 64)
        self.assertEqual(len(registration.registration_digest), 64)
        with self.assertRaises(TypeError):
            DEFAULT_AUTHORITY_REGISTRY.register("fake")

    def test_host_issued_structural_evidence_replays(self) -> None:
        valid, reason = validate_verifier_evidence(
            issued(),
            required_role=VerifierRole.STRUCTURAL_VERIFIER,
            expected_bindings=EXPECTED,
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "registered_verifier_evidence_replayed")

    def test_implementation_identity_does_not_change_under_an_alias(self) -> None:
        original = egrt_verifiers._BUILTINS["builtin.exact_match"]
        alias = "test.alias.same-executable"
        egrt_verifiers._BUILTINS[alias] = original
        try:
            self.assertEqual(
                DEFAULT_REGISTRY.implementation_digest("builtin.exact_match"),
                DEFAULT_REGISTRY.implementation_digest(alias),
            )
        finally:
            del egrt_verifiers._BUILTINS[alias]

    def test_unregistered_and_wrong_role_fail_closed(self) -> None:
        fake = rehashed(issued(), verifier_id="fake.semantic")
        self.assertEqual(
            validate_verifier_evidence(
                fake,
                required_role=VerifierRole.STRUCTURAL_VERIFIER,
                expected_bindings=EXPECTED,
            ),
            (False, "verifier_unregistered"),
        )
        wrong_role = rehashed(issued(), role=VerifierRole.SEMANTIC_VERIFIER)
        self.assertEqual(
            validate_verifier_evidence(
                wrong_role,
                required_role=VerifierRole.SEMANTIC_VERIFIER,
                expected_bindings=EXPECTED,
            ),
            (False, "verifier_role_unauthorized"),
        )

    def test_version_implementation_authority_and_scope_aliases_fail(self) -> None:
        cases = (
            ("verifier_version", "999", "verifier_version_mismatch"),
            ("implementation_digest", "1" * 64, "verifier_implementation_mismatch"),
            ("authority_id", "fake.authority", "verifier_authority_mismatch"),
            ("authorized_scope", "OTHER_SCOPE", "verifier_scope_unauthorized"),
        )
        for field, value, expected_reason in cases:
            with self.subTest(field=field):
                forged = rehashed(issued(), **{field: value})
                self.assertEqual(
                    validate_verifier_evidence(
                        forged,
                        required_role=VerifierRole.STRUCTURAL_VERIFIER,
                        expected_bindings=EXPECTED,
                    ),
                    (False, expected_reason),
                )

    def test_stale_registration_and_environment_fail(self) -> None:
        cases = (
            ("registration_digest", "2" * 64, "verifier_registration_stale_or_forged"),
            ("environment_digest", "3" * 64, "verifier_environment_stale_or_forged"),
        )
        for field, value, expected_reason in cases:
            with self.subTest(field=field):
                forged = rehashed(issued(), **{field: value})
                self.assertEqual(
                    validate_verifier_evidence(
                        forged,
                        required_role=VerifierRole.STRUCTURAL_VERIFIER,
                        expected_bindings=EXPECTED,
                    ),
                    (False, expected_reason),
                )


class EvidenceBindingTests(unittest.TestCase):
    def test_forged_digest_and_changed_content_fail(self) -> None:
        forged_digest = dataclasses.replace(issued(), evidence_sha256="4" * 64)
        changed_content = dataclasses.replace(
            issued(), canonical_input_json='{"actual":"x","expected":"y"}'
        )
        for manifest in (forged_digest, changed_content):
            with self.subTest(manifest=manifest):
                valid, reason = validate_verifier_evidence(
                    manifest,
                    required_role=VerifierRole.STRUCTURAL_VERIFIER,
                    expected_bindings=EXPECTED,
                )
                self.assertFalse(valid)
                self.assertEqual(reason, "evidence_digest_forged")

    def test_candidate_scope_and_obligation_swaps_fail(self) -> None:
        for index in range(4):
            expected = list(EXPECTED)
            expected[index] = "9" * 64
            with self.subTest(binding=index):
                self.assertEqual(
                    validate_verifier_evidence(
                        issued(),
                        required_role=VerifierRole.STRUCTURAL_VERIFIER,
                        expected_bindings=tuple(expected),
                    ),
                    (False, "evidence_candidate_scope_or_obligation_binding_mismatch"),
                )

    def test_caller_selected_pass_cannot_override_observed_fail(self) -> None:
        manifest = issued()
        forged_result = dataclasses.replace(
            manifest.observed_result,
            status=VerificationStatus.FAIL,
            reason="caller selected fail body",
        )
        forged = rehashed(manifest, observed_result=forged_result)
        self.assertEqual(
            validate_verifier_evidence(
                forged,
                required_role=VerifierRole.STRUCTURAL_VERIFIER,
                expected_bindings=EXPECTED,
            ),
            (False, "verifier_observation_replay_mismatch"),
        )

    def test_pass_copied_from_another_verifier_fails(self) -> None:
        copied = rehashed(issued(), verifier_id="builtin.json_exact")
        valid, reason = validate_verifier_evidence(
            copied,
            required_role=VerifierRole.STRUCTURAL_VERIFIER,
            expected_bindings=EXPECTED,
        )
        self.assertFalse(valid)
        self.assertIn(reason, {"verifier_version_mismatch", "verifier_implementation_mismatch"})

    def test_duplicate_artifacts_and_missing_manifest_fail_at_construction(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            dataclasses.replace(
                issued(), input_artifact_digests=("8" * 64, "8" * 64)
            )
        with self.assertRaises(TypeError):
            PatchCertificate(BASE, CANDIDATE, SCOPE, OBLIGATIONS, None)  # type: ignore[arg-type]


class AdmissionExploitRegressionTests(unittest.TestCase):
    def test_producer_implementation_collision_is_rejected(self) -> None:
        evidence = issued()
        repair = CandidateRepair(
            "candidate-1",
            BASE,
            CANDIDATE,
            SCOPE,
            OBLIGATIONS,
            "different.producer.name",
            "999",
            evidence.implementation_digest,
        )
        decision = decide_admission(
            repair,
            PatchCertificate(BASE, CANDIDATE, SCOPE, OBLIGATIONS, evidence),
        )
        self.assertEqual(decision.state, AdmissionState.REJECTED)
        self.assertEqual(
            decision.reason, "repair_producer_implementation_self_certified"
        )

    def test_old_fake_semantic_result_cannot_become_committable(self) -> None:
        structural = issued()
        semantic_evidence = rehashed(
            structural,
            role=VerifierRole.SEMANTIC_VERIFIER,
            verifier_id="fake.semantic",
            verifier_version="999",
            authority_id="fake.authority",
        )
        repair = CandidateRepair(
            "candidate-1",
            BASE,
            CANDIDATE,
            SCOPE,
            OBLIGATIONS,
            "repair.producer",
            "1",
            "7" * 64,
        )
        decision = decide_admission(
            repair,
            PatchCertificate(BASE, CANDIDATE, SCOPE, OBLIGATIONS, structural),
            SemanticVerification(
                BASE, CANDIDATE, SCOPE, OBLIGATIONS, semantic_evidence
            ),
        )
        self.assertEqual(decision.state, AdmissionState.REJECTED)
        self.assertFalse(decision.candidate_committable)
        self.assertTrue(decision.base_answer_preserved)
        self.assertTrue(decision.host_commit_required)
        self.assertFalse(decision.execution_authorized)


if __name__ == "__main__":
    unittest.main()
