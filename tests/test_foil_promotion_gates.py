"""Tests for deterministic external FOIL gate evaluation."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_candidate_state import CandidateBinding, Gate, GateStatus  # noqa: E402
from foil_promotion_gates import (  # noqa: E402
    EvidencePartition,
    GateEvaluationPlan,
    GateEvaluationStatus,
    GateEvidence,
    GateMetricObservation,
    MetricDirection,
    MetricRule,
    clopper_pearson_upper_ppm,
    evaluate_gate,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def plan(
    partitions: tuple[EvidencePartition, ...] = (
        EvidencePartition.LOCK,
        EvidencePartition.PROSPECTIVE,
    ),
) -> GateEvaluationPlan:
    return GateEvaluationPlan(
        plan_id="gate1-small-contract",
        gate=Gate.GATE1,
        candidate_binding_digest=binding().digest(),
        required_partitions=partitions,
        required_domains=("math", "code"),
        metric_rules=(
            MetricRule(
                "residual_recall",
                MetricDirection.AT_LEAST,
                800_000,
                800_000,
                10,
            ),
            MetricRule(
                "false_activation",
                MetricDirection.AT_MOST,
                200_000,
                800_000,
                10,
            ),
        ),
        protocol_sha256=d("frozen-gate1-protocol"),
    )


def evidence(
    item_plan: GateEvaluationPlan,
    *,
    recall_successes: int = 10,
    omit_last: bool = False,
) -> GateEvidence:
    rows = []
    for partition in item_plan.required_partitions:
        for domain in item_plan.required_domains:
            rows.extend(
                (
                    GateMetricObservation(
                        partition,
                        domain,
                        "residual_recall",
                        recall_successes,
                        10,
                        d(f"{partition.value}:{domain}:recall"),
                    ),
                    GateMetricObservation(
                        partition,
                        domain,
                        "false_activation",
                        0,
                        10,
                        d(f"{partition.value}:{domain}:false"),
                    ),
                )
            )
    if omit_last:
        rows.pop()
    return GateEvidence(
        observations=tuple(rows),
        cost_ledger_sha256=d("complete-cost-ledger"),
        source_bundle_sha256=d("sealed-source-bundle"),
        forbidden_calls=0,
        cost_complete=True,
        exact_a0_preserved=True,
        negative_controls_passed=True,
    )


def binding(candidate_id: str = "candidate") -> CandidateBinding:
    return CandidateBinding(
        candidate_id=candidate_id,
        task_digest=d("task"),
        base_answer_digest=d("a0"),
        protocol_digest=d("protocol"),
        config_digest=d("config"),
        partition_digest=d("partition"),
        budget_ceiling_digest=d("budget"),
    )


class PromotionGateTests(unittest.TestCase):
    def test_exact_upper_zero_failure_bound(self) -> None:
        self.assertLessEqual(clopper_pearson_upper_ppm(0, 10, 800_000), 200_000)
        self.assertGreater(clopper_pearson_upper_ppm(1, 10, 800_000), 200_000)

    def test_complete_lock_and_prospective_matrix_issues_qualifying_receipt(self) -> None:
        item_plan = plan()
        item_evidence = evidence(item_plan)
        result = evaluate_gate(item_plan, item_evidence)
        self.assertEqual(result.status, GateEvaluationStatus.PASS)
        self.assertTrue(result.promotion_eligible)
        receipt = result.gate_receipt(binding())
        self.assertEqual(receipt.status, GateStatus.PASS)
        self.assertEqual(receipt.cost_ledger_digest, item_evidence.cost_ledger_sha256)
        self.assertTrue(receipt.qualifies(binding()))
        with self.assertRaisesRegex(ValueError, "frozen gate plan"):
            result.gate_receipt(binding("other-candidate"))

    def test_development_result_is_reportable_but_never_promotes(self) -> None:
        item_plan = plan((EvidencePartition.DEVELOPMENT,))
        result = evaluate_gate(item_plan, evidence(item_plan))
        self.assertEqual(result.status, GateEvaluationStatus.PASS)
        self.assertEqual(result.reason_code, "development_evidence_only")
        self.assertFalse(result.promotion_eligible)
        self.assertEqual(result.gate_receipt(binding()).status, GateStatus.UNKNOWN)

    def test_missing_cell_is_unknown_and_failed_bound_is_fail(self) -> None:
        item_plan = plan()
        missing = evaluate_gate(item_plan, evidence(item_plan, omit_last=True))
        self.assertEqual(missing.status, GateEvaluationStatus.UNKNOWN)
        self.assertTrue(missing.missing_cells)
        failed = evaluate_gate(
            item_plan,
            evidence(item_plan, recall_successes=5),
        )
        self.assertEqual(failed.status, GateEvaluationStatus.FAIL)
        self.assertFalse(failed.promotion_eligible)


if __name__ == "__main__":
    unittest.main()
