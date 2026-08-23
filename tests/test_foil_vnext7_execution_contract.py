import unittest

from experiments.foil_vnext.runtime_policy import (
    ClaimKind,
    LoadBearingUncertainty,
    TaskContext,
    VerifierKind,
)
from experiments.foil_vnext6.execution_contract import (
    ClaimResolution,
    EvidenceBasis,
    EvidencePacket,
    EvidenceVerdict,
    OperatorOutcome,
    OutcomeStatus,
)
from experiments.foil_vnext6.runtime_policy import (
    EvidenceAuthority,
    StrategyBudget,
    StrategyOperator,
    StrategyTaskContext,
)
from experiments.foil_vnext7.execution_contract import (
    CachedEvidenceRecord,
    QualificationKind,
    build_request,
    qualify_cached_evidence,
    validate_outcome,
)
from experiments.foil_vnext7.runtime_policy import (
    CachedEvidenceHint,
    EvidenceTypedDecision,
    EvidenceTypedRuntimePolicy,
    EvidenceTypedTaskContext,
)

POLICY = EvidenceTypedRuntimePolicy()
BUDGET = StrategyBudget()
TASK_ID = "v7-test-task"
HASH = "a" * 64


def source_decision(*, cached=False, current=False):
    kind = ClaimKind.FRESH_FACT if current else ClaimKind.EXTERNAL_FACT
    verifier = (
        VerifierKind.CURRENT_SOURCE
        if current
        else VerifierKind.SOURCE_EVIDENCE
    )
    task = TaskContext(
        has_viable_candidate=True,
        freshness_sensitive=current,
        uncertainties=(LoadBearingUncertainty("C1", kind),),
    )
    hints = (
        CachedEvidenceHint(
            TASK_ID,
            "C1",
            verifier,
            freshness_checked=current,
        ),
    ) if cached else ()
    return POLICY.decide(
        EvidenceTypedTaskContext(
            StrategyTaskContext(task),
            task_instance_id=TASK_ID,
            cached_evidence=hints,
        ),
        BUDGET,
    )


def cached_record(
    *,
    verifier=VerifierKind.SOURCE_EVIDENCE,
    basis=EvidenceBasis.PRIMARY_SOURCE,
    target_id="C1",
    task_instance_id=TASK_ID,
    qualification=QualificationKind.CLAIM_NATIVE_CHECK,
    stale=False,
    freshness=False,
):
    return CachedEvidenceRecord(
        evidence_id="E1",
        task_instance_id=task_instance_id,
        target_id=target_id,
        verifier=verifier,
        basis=basis,
        reference="receipt://cached/source-1",
        content_sha256=HASH,
        verdict=EvidenceVerdict.SUPPORTS,
        qualification=qualification,
        qualification_receipt="receipt://qualification/1",
        stale=stale,
        freshness_checked=freshness,
    )


class EvidenceTypedExecutionTests(unittest.TestCase):
    def test_01_request_targets_are_controller_derived(self):
        decision = source_decision()
        request = build_request(decision, task_instance_id=TASK_ID)
        self.assertEqual(request.target_claim_ids, ("C1",))
        self.assertEqual(request.task_instance_id, TASK_ID)

    def test_02_regime_level_obligation_is_executable(self):
        decision = POLICY.decide(
            EvidenceTypedTaskContext(
                StrategyTaskContext(
                    TaskContext(
                        benchmark="FreshQA",
                        has_viable_candidate=True,
                        freshness_sensitive=True,
                    )
                ),
                task_instance_id=TASK_ID,
            ),
            BUDGET,
        )
        request = build_request(decision, task_instance_id=TASK_ID)
        self.assertEqual(
            request.target_claim_ids,
            ("O:current_source",),
        )

    def test_03_cached_record_requires_valid_sha256(self):
        with self.assertRaises(ValueError):
            CachedEvidenceRecord(
                evidence_id="E1",
                task_instance_id=TASK_ID,
                target_id="C1",
                verifier=VerifierKind.SOURCE_EVIDENCE,
                basis=EvidenceBasis.PRIMARY_SOURCE,
                reference="receipt://source",
                content_sha256="not-a-sha",
                verdict=EvidenceVerdict.SUPPORTS,
                qualification=QualificationKind.CLAIM_NATIVE_CHECK,
                qualification_receipt="receipt://q",
            )

    def test_04_raw_stale_cached_evidence_is_rejected(self):
        decision = source_decision(cached=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(stale=True),
            )

    def test_05_cached_current_source_requires_freshness(self):
        decision = source_decision(cached=True, current=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(
                    verifier=VerifierKind.CURRENT_SOURCE,
                    basis=EvidenceBasis.OFFICIAL_SOURCE,
                    freshness=False,
                ),
            )

    def test_06_wrong_basis_is_rejected(self):
        decision = source_decision(cached=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(basis=EvidenceBasis.CALCULATION),
            )

    def test_07_claim_native_cached_record_becomes_evidence_packet(self):
        decision = source_decision(cached=True)
        packet = qualify_cached_evidence(decision, cached_record())
        self.assertIs(packet.authority, EvidenceAuthority.CLAIM_NATIVE)
        self.assertIs(packet.verifier, VerifierKind.SOURCE_EVIDENCE)
        self.assertEqual(packet.claim_id, "C1")

    def test_08_cached_evidence_cannot_target_another_claim(self):
        decision = source_decision(cached=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(target_id="C2"),
            )

    def test_09_independent_requirement_rejects_native_qualification(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
            completed_verifiers=frozenset(
                {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
            ),
        )
        base = POLICY.decide(
            EvidenceTypedTaskContext(
                StrategyTaskContext(
                    task,
                    high_impact=True,
                    independent_reviewer_available=True,
                ),
                task_instance_id=TASK_ID,
            ),
            StrategyBudget(independent_reviews_remaining=1),
        )
        self.assertIs(base.operator, StrategyOperator.INDEPENDENT_REVIEW)
        forced = EvidenceTypedDecision(
            controller_version=base.controller_version,
            task_instance_id=TASK_ID,
            strategy=base.strategy,
            verification_targets=base.verification_targets,
            reuse_cached_evidence=True,
        )
        record = cached_record(
            verifier=VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
            basis=EvidenceBasis.PROOF_OR_COUNTEREXAMPLE,
            qualification=QualificationKind.CLAIM_NATIVE_CHECK,
        )
        with self.assertRaises(ValueError):
            qualify_cached_evidence(forced, record)

    def test_10_independent_qualification_satisfies_independent_requirement(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
            completed_verifiers=frozenset(
                {VerifierKind.CONTRADICTION_COUNTEREXAMPLE}
            ),
        )
        base = POLICY.decide(
            EvidenceTypedTaskContext(
                StrategyTaskContext(
                    task,
                    high_impact=True,
                    independent_reviewer_available=True,
                ),
                task_instance_id=TASK_ID,
            ),
            StrategyBudget(independent_reviews_remaining=1),
        )
        forced = EvidenceTypedDecision(
            controller_version=base.controller_version,
            task_instance_id=TASK_ID,
            strategy=base.strategy,
            verification_targets=base.verification_targets,
            reuse_cached_evidence=True,
        )
        packet = qualify_cached_evidence(
            forced,
            cached_record(
                verifier=VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
                basis=EvidenceBasis.PROOF_OR_COUNTEREXAMPLE,
                qualification=QualificationKind.INDEPENDENT_CHECK,
            ),
        )
        self.assertIs(packet.authority, EvidenceAuthority.INDEPENDENT_REVIEW)

    def test_11_cached_packet_can_complete_parent_verifier(self):
        decision = source_decision(cached=True)
        request = build_request(decision, task_instance_id=TASK_ID)
        packet = qualify_cached_evidence(decision, cached_record())
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
            completed_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
            claim_resolutions=(
                ClaimResolution("C1", EvidenceVerdict.SUPPORTS),
            ),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(
            validation.admitted_claim_resolutions,
            (ClaimResolution("C1", EvidenceVerdict.SUPPORTS),),
        )

    def test_12_mechanical_check_cannot_certify_source_entailment(self):
        decision = source_decision(cached=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(
                    qualification=QualificationKind.MECHANICAL_CHECK,
                ),
            )

    def test_13_mechanical_check_can_certify_exact_calculation(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.NUMERIC),),
        )
        decision = POLICY.decide(
            EvidenceTypedTaskContext(
                StrategyTaskContext(task),
                task_instance_id=TASK_ID,
                cached_evidence=(
                    CachedEvidenceHint(
                        TASK_ID,
                        "C1",
                        VerifierKind.EXACT_CALCULATION,
                    ),
                ),
            ),
            BUDGET,
        )
        packet = qualify_cached_evidence(
            decision,
            cached_record(
                verifier=VerifierKind.EXACT_CALCULATION,
                basis=EvidenceBasis.CALCULATION,
                qualification=QualificationKind.MECHANICAL_CHECK,
            ),
        )
        self.assertIs(packet.authority, EvidenceAuthority.CLAIM_NATIVE)

    def test_14_outside_target_evidence_is_rejected(self):
        decision = source_decision()
        request = build_request(decision, task_instance_id=TASK_ID)
        packet = EvidencePacket(
            evidence_id="E2",
            claim_id="C2",
            authority=EvidenceAuthority.CLAIM_NATIVE,
            verifier=VerifierKind.SOURCE_EVIDENCE,
            basis=EvidenceBasis.PRIMARY_SOURCE,
            reference="receipt://other",
            verdict=EvidenceVerdict.SUPPORTS,
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("evidence_target_outside_decision", validation.errors)

    def test_15_cached_evidence_from_another_task_is_rejected(self):
        decision = source_decision(cached=True)
        with self.assertRaises(ValueError):
            qualify_cached_evidence(
                decision,
                cached_record(task_instance_id="other-task"),
            )

    def test_16_request_scope_cannot_override_decision_scope(self):
        decision = source_decision()
        with self.assertRaises(ValueError):
            build_request(decision, task_instance_id="other-task")


if __name__ == "__main__":
    unittest.main()
