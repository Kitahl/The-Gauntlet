import json
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
    ProgressStatus,
    ToolEffect,
    build_request,
    validate_outcome,
)
from experiments.foil_vnext6.runtime_policy import (
    ComposableRuntimePolicy,
    EvidenceAuthority,
    StrategyBudget,
    StrategyOperator,
    StrategyTaskContext,
)

POLICY = ComposableRuntimePolicy()
BUDGET = StrategyBudget()
TASK_ID = "test-task"


def source_decision(current=False):
    kind = ClaimKind.FRESH_FACT if current else ClaimKind.EXTERNAL_FACT
    task = TaskContext(
        has_viable_candidate=True,
        freshness_sensitive=current,
        uncertainties=(LoadBearingUncertainty("C1", kind),),
    )
    return POLICY.decide(StrategyTaskContext(task), BUDGET)


def build(decision, **kwargs):
    return build_request(decision, task_instance_id=TASK_ID, **kwargs)


def source_packet(
    *,
    authority=EvidenceAuthority.CLAIM_NATIVE,
    verifier=VerifierKind.SOURCE_EVIDENCE,
    basis=EvidenceBasis.PRIMARY_SOURCE,
    verdict=EvidenceVerdict.SUPPORTS,
    stale=False,
    freshness=False,
):
    return EvidencePacket(
        evidence_id="E1",
        claim_id="C1",
        authority=authority,
        verifier=verifier,
        basis=basis,
        reference="receipt://source-1",
        verdict=verdict,
        stale=stale,
        freshness_checked=freshness,
    )


def resolution(verdict=EvidenceVerdict.SUPPORTS):
    return ClaimResolution("C1", verdict)


class ExecutionContractTests(unittest.TestCase):
    def test_01_evidence_bearing_request_requires_claim_targets(self):
        decision = source_decision()
        with self.assertRaises(ValueError):
            build(decision)

    def test_02_internal_operator_cannot_resolve_claim(self):
        decision = POLICY.decide(StrategyTaskContext(TaskContext()), BUDGET)
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=StrategyOperator.DIRECT,
            status=OutcomeStatus.COMPLETED,
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("non_verifying_operator_resolved_claim", validation.errors)

    def test_03_react_observation_does_not_gain_verifier_authority(self):
        task = TaskContext(
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.EXTERNAL_FACT),)
        )
        decision = POLICY.decide(StrategyTaskContext(task), BUDGET)
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=StrategyOperator.REACT,
            status=OutcomeStatus.COMPLETED,
            evidence=(source_packet(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("react_discovery_claimed_verifier_authority", validation.errors)

    def test_04_matching_claim_native_packet_admits_resolution(self):
        decision = source_decision()
        request = build(decision, target_claim_ids=("C1",))
        packet = source_packet()
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
            completed_verifiers=frozenset({VerifierKind.SOURCE_EVIDENCE}),
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertTrue(validation.valid, validation.errors)
        self.assertEqual(validation.admitted_claim_resolutions, (resolution(),))
        self.assertEqual(validation.progress, ProgressStatus.PROGRESSED)

    def test_05_wrong_verifier_cannot_support_resolution(self):
        decision = source_decision()
        request = build(decision, target_claim_ids=("C1",))
        packet = source_packet(
            verifier=VerifierKind.EXACT_CALCULATION,
            basis=EvidenceBasis.CALCULATION,
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("unsupported_claim_resolution:C1", validation.errors)

    def test_06_stale_evidence_cannot_support_resolution(self):
        decision = source_decision()
        request = build(decision, target_claim_ids=("C1",))
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(source_packet(stale=True),),
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)

    def test_07_current_source_requires_freshness_check(self):
        decision = source_decision(current=True)
        request = build(decision, target_claim_ids=("C1",))
        packet = source_packet(
            verifier=VerifierKind.CURRENT_SOURCE,
            basis=EvidenceBasis.OFFICIAL_SOURCE,
            freshness=False,
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("unsupported_claim_resolution:C1", validation.errors)

    def test_08_official_guideline_can_ground_current_source(self):
        decision = source_decision(current=True)
        request = build(decision, target_claim_ids=("C1",))
        packet = source_packet(
            verifier=VerifierKind.CURRENT_SOURCE,
            basis=EvidenceBasis.OFFICIAL_GUIDELINE,
            freshness=True,
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(packet,),
            completed_verifiers=frozenset({VerifierKind.CURRENT_SOURCE}),
            claim_resolutions=(resolution(),),
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertTrue(validation.valid, validation.errors)

    def test_09_side_effecting_request_requires_idempotency_key(self):
        decision = POLICY.decide(StrategyTaskContext(TaskContext()), BUDGET)
        with self.assertRaises(ValueError):
            build(decision, tool_effect=ToolEffect.SIDE_EFFECTING)

    def test_10_side_effecting_retry_requires_verify_before_retry(self):
        decision = POLICY.decide(StrategyTaskContext(TaskContext()), BUDGET)
        with self.assertRaises(ValueError):
            build(
                decision,
                tool_effect=ToolEffect.SIDE_EFFECTING,
                idempotency_key="op-1",
                retry_attempt=1,
            )

    def test_11_side_effecting_completion_requires_postcondition(self):
        decision = POLICY.decide(StrategyTaskContext(TaskContext()), BUDGET)
        request = build(
            decision,
            tool_effect=ToolEffect.SIDE_EFFECTING,
            idempotency_key="op-1",
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("side_effect_postcondition_unverified", validation.errors)

    def test_12_verified_side_effect_counts_as_progress(self):
        decision = POLICY.decide(StrategyTaskContext(TaskContext()), BUDGET)
        request = build(
            decision,
            tool_effect=ToolEffect.SIDE_EFFECTING,
            idempotency_key="op-1",
        )
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            postcondition_verified=True,
            observed_state_fingerprint="sha256:state",
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertTrue(validation.valid, validation.errors)
        self.assertIs(validation.progress, ProgressStatus.PROGRESSED)

    def test_13_mastermind_requires_distinct_defect(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
            completed_verifiers=frozenset({VerifierKind.CONTRADICTION_COUNTEREXAMPLE}),
        )
        decision = POLICY.decide(
            StrategyTaskContext(
                task,
                high_impact=True,
                causal_or_process_defect=True,
                repeated_route_failures=2,
            ),
            BUDGET,
        )
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("mastermind_completed_without_distinct_defect", validation.errors)

    def test_14_mastermind_defect_is_progress_but_not_claim_resolution(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
            completed_verifiers=frozenset({VerifierKind.CONTRADICTION_COUNTEREXAMPLE}),
        )
        decision = POLICY.decide(
            StrategyTaskContext(
                task,
                high_impact=True,
                causal_or_process_defect=True,
                repeated_route_failures=2,
            ),
            BUDGET,
        )
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            defect_id="D-001",
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertTrue(validation.valid, validation.errors)
        self.assertIs(validation.progress, ProgressStatus.PROGRESSED)
        self.assertEqual(validation.admitted_claim_resolutions, ())

    def test_15_reflection_requires_candidate_change(self):
        task = TaskContext(
            has_viable_candidate=True,
            uncertainties=(LoadBearingUncertainty("C1", ClaimKind.LOGICAL),),
            completed_verifiers=frozenset({VerifierKind.CONTRADICTION_COUNTEREXAMPLE}),
        )
        decision = POLICY.decide(
            StrategyTaskContext(
                task,
                demonstrated_failure=True,
                failure_target_identified=True,
            ),
            BUDGET,
        )
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("reflection_completed_without_candidate_change", validation.errors)

    def test_16_terminal_operator_cannot_report_state_change(self):
        task = TaskContext(has_viable_candidate=True)
        decision = POLICY.decide(StrategyTaskContext(task), BUDGET)
        self.assertIs(decision.operator, StrategyOperator.STOP)
        request = build(decision)
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            candidate_revised=True,
        )
        validation = validate_outcome(decision, request, outcome)
        self.assertFalse(validation.valid)
        self.assertIn("terminal_operator_reported_state_change", validation.errors)

    def test_17_trace_contains_no_private_reasoning(self):
        decision = source_decision()
        request = build(decision, target_claim_ids=("C1",))
        outcome = OperatorOutcome(
            request_id=request.request_id,
            operator=decision.operator,
            status=OutcomeStatus.COMPLETED,
            evidence=(source_packet(),),
        )
        validation = validate_outcome(decision, request, outcome)
        for trace in (request.trace(), outcome.trace(), validation.trace()):
            json.dumps(trace)
            self.assertNotIn("chain_of_thought", trace)
            self.assertNotIn("scratchpad", trace)
            self.assertNotIn("private_reasoning", trace)


if __name__ == "__main__":
    unittest.main()
