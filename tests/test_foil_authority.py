"""Adversarial tests for FOIL's shadow-only authority/admission kernel.

These tests pin mechanism and safety invariants. They do not establish that a
sensor detects real defects or that a proposed repair improves an answer.
"""
from __future__ import annotations

import dataclasses
import inspect
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import EvidenceClass  # noqa: E402
from foil_authority import (  # noqa: E402
    AdmissionDecision,
    AdmissionState,
    Applicability,
    AuthorityAction,
    AuthorityCeiling,
    AuthorityContext,
    AuthorityDecision,
    CandidateRepair,
    CheckStatus,
    EvidenceSurface,
    PatchCertificate,
    SemanticVerification,
    SensorOutcome,
    SensorRegistration,
    SensorReport,
    decide_admission,
    decide_authority,
)

BASE = "a" * 64
CANDIDATE = "b" * 64
SCOPE = "c" * 64
OBLIGATIONS = "d" * 64
ENVIRONMENT = "e" * 64


def registration(
    *,
    evidence_class: EvidenceClass = EvidenceClass.MEASURED,
    surface: EvidenceSurface = EvidenceSurface.ANSWER,
    ceiling: AuthorityCeiling = AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
) -> SensorRegistration:
    return SensorRegistration(
        sensor_id="sensor.syntax",
        evidence_class=evidence_class,
        surface=surface,
        authority_ceiling=ceiling,
        claim_scope="answer.code",
        producer="foil.sensor.syntax",
        version="1.0.0",
    )


def report(
    *,
    sensor_id: str = "sensor.syntax",
    target_scope: str = "answer.code",
    applicability: Applicability = Applicability.APPLICABLE,
    outcome: SensorOutcome = SensorOutcome.DEFECT,
) -> SensorReport:
    return SensorReport(
        sensor_id=sensor_id,
        input_digest=BASE,
        applicability=applicability,
        outcome=outcome,
        target_scope=target_scope,
    )


def candidate() -> CandidateRepair:
    return CandidateRepair(
        candidate_id="candidate-1",
        base_digest=BASE,
        candidate_digest=CANDIDATE,
        scope_digest=SCOPE,
        obligation_set_digest=OBLIGATIONS,
        repair_producer="foil.repair",
        repair_producer_version="1.0.0",
    )


def certificate(
    *,
    status: CheckStatus = CheckStatus.PASS,
    verifier_id: str = "foil.structural-verifier",
    provenance_group: str = "foil.structural",
    base_digest: str = BASE,
    candidate_digest: str = CANDIDATE,
    scope_digest: str = SCOPE,
    obligation_set_digest: str = OBLIGATIONS,
) -> PatchCertificate:
    return PatchCertificate(
        base_digest=base_digest,
        candidate_digest=candidate_digest,
        scope_digest=scope_digest,
        obligation_set_digest=obligation_set_digest,
        verifier_id=verifier_id,
        verifier_version="1.0.0",
        provenance_group=provenance_group,
        environment_digest=ENVIRONMENT,
        status=status,
    )


def semantic(
    *,
    status: CheckStatus = CheckStatus.PASS,
    verifier_id: str = "foil.semantic-verifier",
    provenance_group: str = "foil.semantic",
    base_digest: str = BASE,
    candidate_digest: str = CANDIDATE,
    scope_digest: str = SCOPE,
    obligation_set_digest: str = OBLIGATIONS,
) -> SemanticVerification:
    return SemanticVerification(
        base_digest=base_digest,
        candidate_digest=candidate_digest,
        scope_digest=scope_digest,
        obligation_set_digest=obligation_set_digest,
        verifier_id=verifier_id,
        verifier_version="1.0.0",
        provenance_group=provenance_group,
        environment_digest=ENVIRONMENT,
        status=status,
    )


class RegistrationBoundaryTests(unittest.TestCase):
    def test_sensor_report_cannot_self_declare_authority(self):
        names = {item.name for item in dataclasses.fields(SensorReport)}
        self.assertNotIn("authority", names)
        self.assertNotIn("authority_ceiling", names)

    def test_prompt_and_person_surfaces_reject_elevated_authority(self):
        for surface in (EvidenceSurface.PROMPT, EvidenceSurface.PERSON):
            for ceiling in (
                AuthorityCeiling.ESCALATION_RECOMMENDED,
                AuthorityCeiling.REPAIR_PROPOSAL_ALLOWED,
            ):
                with self.subTest(surface=surface, ceiling=ceiling):
                    with self.assertRaises(ValueError):
                        registration(surface=surface, ceiling=ceiling)

    def test_answer_surface_accepts_each_registered_ceiling(self):
        for ceiling in AuthorityCeiling:
            with self.subTest(ceiling=ceiling):
                self.assertEqual(registration(ceiling=ceiling).authority_ceiling, ceiling)

    def test_candidate_must_be_a_real_delta(self):
        with self.assertRaises(ValueError):
            CandidateRepair(
                candidate_id="no-op",
                base_digest=BASE,
                candidate_digest=BASE,
                scope_digest=SCOPE,
                obligation_set_digest=OBLIGATIONS,
                repair_producer="foil.repair",
                repair_producer_version="1.0.0",
            )

    def test_strict_types_block_string_and_truthiness_bypasses(self):
        with self.assertRaises(TypeError):
            AuthorityContext(repair_proposals_enabled="false")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            report(applicability="UNKNOWN")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            certificate(status="FAIL")  # type: ignore[arg-type]

    def test_safety_invariants_are_not_constructor_arguments(self):
        authority_params = inspect.signature(AuthorityDecision).parameters
        admission_params = inspect.signature(AdmissionDecision).parameters
        for name in ("shadow_mode", "execution_authorized", "base_answer_preserved"):
            self.assertNotIn(name, authority_params)
        for name in ("base_answer_preserved", "host_commit_required", "execution_authorized"):
            self.assertNotIn(name, admission_params)

    def test_module_has_no_process_control_imports(self):
        source = (ROOT / "tools" / "foil_authority.py").read_text(encoding="utf-8").lower()
        for forbidden in (
            "import gauntlet",
            "from gauntlet",
            "import mastermind",
            "from mastermind",
        ):
            self.assertNotIn(forbidden, source)


class AuthorityDecisionTests(unittest.TestCase):
    def test_all_valid_state_combinations_preserve_shadow_invariants(self):
        surface_ceilings = {
            EvidenceSurface.PROMPT: (
                AuthorityCeiling.OBSERVE_ONLY,
                AuthorityCeiling.FLAG_ONLY,
                AuthorityCeiling.ASK_OR_ABSTAIN,
            ),
            EvidenceSurface.ANSWER: tuple(AuthorityCeiling),
            EvidenceSurface.PERSON: (
                AuthorityCeiling.OBSERVE_ONLY,
                AuthorityCeiling.FLAG_ONLY,
                AuthorityCeiling.ASK_OR_ABSTAIN,
            ),
        }
        contexts = [
            AuthorityContext(*values)
            for values in itertools.product((False, True), repeat=3)
        ]
        checked = 0
        for surface, ceilings in surface_ceilings.items():
            combinations = itertools.product(
                ceilings,
                Applicability,
                SensorOutcome,
                (False, True),
                (False, True),
                contexts,
            )
            for (
                ceiling,
                applicability,
                outcome,
                sensor_matches,
                scope_matches,
                context,
            ) in combinations:
                decision = decide_authority(
                    registration(surface=surface, ceiling=ceiling),
                    report(
                        sensor_id="sensor.syntax" if sensor_matches else "sensor.other",
                        target_scope="answer.code" if scope_matches else "answer.prose",
                        applicability=applicability,
                        outcome=outcome,
                    ),
                    context,
                )
                self.assertTrue(decision.shadow_mode)
                self.assertFalse(decision.execution_authorized)
                self.assertTrue(decision.base_answer_preserved)
                checked += 1
        self.assertEqual(checked, 3168)

    def test_flag_only_sensor_never_proposes_repair(self):
        decision = decide_authority(
            registration(ceiling=AuthorityCeiling.FLAG_ONLY),
            report(),
            AuthorityContext(True, True, True),
        )
        self.assertEqual(decision.action, AuthorityAction.FLAG)

    def test_repair_proposal_requires_all_three_explicit_prerequisites(self):
        for values in itertools.product((False, True), repeat=3):
            with self.subTest(values=values):
                decision = decide_authority(
                    registration(),
                    report(),
                    AuthorityContext(*values),
                )
                expected = (
                    AuthorityAction.PROPOSE_REPAIR_SHADOW
                    if all(values)
                    else AuthorityAction.STAND_DOWN
                )
                self.assertEqual(decision.action, expected)

    def test_evidence_strength_does_not_change_registered_authority(self):
        actions = {
            decide_authority(
                registration(
                    evidence_class=evidence_class,
                    ceiling=AuthorityCeiling.FLAG_ONLY,
                ),
                report(),
                AuthorityContext(True, True, True),
            ).action
            for evidence_class in EvidenceClass
        }
        self.assertEqual(actions, {AuthorityAction.FLAG})

    def test_identity_scope_unknown_and_clear_states_fail_closed(self):
        cases = (
            report(sensor_id="sensor.other"),
            report(target_scope="answer.prose"),
            report(applicability=Applicability.UNKNOWN),
            report(applicability=Applicability.NOT_APPLICABLE),
            report(outcome=SensorOutcome.UNKNOWN),
            report(outcome=SensorOutcome.CLEAR),
        )
        for item in cases:
            with self.subTest(report=item):
                decision = decide_authority(
                    registration(),
                    item,
                    AuthorityContext(True, True, True),
                )
                self.assertEqual(decision.action, AuthorityAction.STAND_DOWN)

    def test_action_vocabulary_contains_no_apply_or_commit_operation(self):
        for action in AuthorityAction:
            self.assertNotIn("APPLY", action.value)
            self.assertNotIn("COMMIT", action.value)


class CandidateAdmissionTests(unittest.TestCase):
    def test_missing_certificate_cannot_advance(self):
        decision = decide_admission(candidate())
        self.assertEqual(decision.state, AdmissionState.CERTIFICATE_REQUIRED)
        self.assertFalse(decision.candidate_committable)

    def test_certificate_pass_requires_separate_semantic_verification(self):
        decision = decide_admission(candidate(), certificate())
        self.assertEqual(decision.state, AdmissionState.SEMANTIC_VERIFICATION_REQUIRED)
        self.assertFalse(decision.candidate_committable)

    def test_bound_independent_passes_make_candidate_committable_not_executable(self):
        decision = decide_admission(candidate(), certificate(), semantic())
        self.assertEqual(decision.state, AdmissionState.COMMITTABLE)
        self.assertTrue(decision.candidate_committable)
        self.assertTrue(decision.base_answer_preserved)
        self.assertTrue(decision.host_commit_required)
        self.assertFalse(decision.execution_authorized)

    def test_certificate_and_semantic_checks_bind_the_obligation_set(self):
        wrong = "f" * 64
        certificate_decision = decide_admission(
            candidate(),
            certificate(obligation_set_digest=wrong),
            semantic(),
        )
        semantic_decision = decide_admission(
            candidate(),
            certificate(),
            semantic(obligation_set_digest=wrong),
        )
        self.assertEqual(certificate_decision.state, AdmissionState.REJECTED)
        self.assertEqual(semantic_decision.state, AdmissionState.REJECTED)

    def test_candidate_binding_mismatch_is_rejected(self):
        wrong = "f" * 64
        for structural, meaning in (
            (certificate(candidate_digest=wrong), semantic()),
            (certificate(), semantic(candidate_digest=wrong)),
        ):
            with self.subTest(structural=structural, meaning=meaning):
                decision = decide_admission(candidate(), structural, meaning)
                self.assertEqual(decision.state, AdmissionState.REJECTED)

    def test_repair_producer_cannot_certify_or_semantically_verify_itself(self):
        structural = decide_admission(
            candidate(),
            certificate(verifier_id="foil.repair"),
            semantic(),
        )
        meaning = decide_admission(
            candidate(),
            certificate(),
            semantic(verifier_id="foil.repair"),
        )
        self.assertEqual(structural.state, AdmissionState.REJECTED)
        self.assertEqual(meaning.state, AdmissionState.REJECTED)
        self.assertNotIn("require_independence", inspect.signature(decide_admission).parameters)

    def test_structural_verifier_cannot_reuse_itself_for_semantics(self):
        decision = decide_admission(
            candidate(),
            certificate(verifier_id="shared.verifier"),
            semantic(verifier_id="shared.verifier"),
        )
        self.assertEqual(decision.state, AdmissionState.REJECTED)
        self.assertFalse(decision.candidate_committable)

    def test_distinct_verifier_names_from_one_provenance_group_are_rejected(self):
        decision = decide_admission(
            candidate(),
            certificate(verifier_id="structural.a", provenance_group="shared.family"),
            semantic(verifier_id="semantic.b", provenance_group="shared.family"),
        )
        self.assertEqual(decision.state, AdmissionState.REJECTED)
        self.assertEqual(decision.reason, "structural_semantic_provenance_overlap")

    def test_only_pass_pass_is_committable_across_all_status_pairs(self):
        for structural_status, semantic_status in itertools.product(CheckStatus, repeat=2):
            with self.subTest(structural=structural_status, semantic=semantic_status):
                decision = decide_admission(
                    candidate(),
                    certificate(status=structural_status),
                    semantic(status=semantic_status),
                )
                expected = (
                    structural_status is CheckStatus.PASS
                    and semantic_status is CheckStatus.PASS
                )
                self.assertEqual(decision.candidate_committable, expected)

    def test_unknown_checks_never_become_committable(self):
        decisions = (
            decide_admission(candidate(), certificate(status=CheckStatus.UNKNOWN)),
            decide_admission(
                candidate(),
                certificate(),
                semantic(status=CheckStatus.UNKNOWN),
            ),
        )
        for decision in decisions:
            self.assertEqual(decision.state, AdmissionState.UNKNOWN)
            self.assertFalse(decision.candidate_committable)


if __name__ == "__main__":
    unittest.main()
