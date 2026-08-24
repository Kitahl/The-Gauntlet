"""Tests for the fail-closed later-study contracts."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_later_studies import (  # noqa: E402
    StudyContractStatus,
    StudyKind,
    StudyPlan,
    StudyRunCell,
    StudyRunInventory,
    StudySafeguards,
    validate_study_contract,
)
from foil_promotion_gates import EvidencePartition  # noqa: E402


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def plan(
    kind: StudyKind = StudyKind.RQ26_COMPLEMENT,
    partition: EvidencePartition = EvidencePartition.LOCK,
) -> StudyPlan:
    arms = {
        StudyKind.PROFILE_P0: ("CORRECT_PROFILE", "WRONG_PROFILE", "NO_PROFILE"),
        StudyKind.RQ26_COMPLEMENT: ("RAW", "CHECKLIST", "FOIL", "ORACLE"),
        StudyKind.HISTORY_POLICY: (
            "STATIC",
            "SIMPLE_HISTORY",
            "CONTEXTUAL_STATISTICAL",
            "SYNAPSE",
            "HEBBIAN_MUTANT",
        ),
        StudyKind.HUMAN_COMPLEMENT: (
            "USER_ALONE",
            "GENERIC_AI",
            "STATIC_FOIL",
            "ADAPTIVE_FOIL",
        ),
    }
    return StudyPlan(
        study_id=f"small-{kind.value.lower()}",
        kind=kind,
        arms=arms[kind],
        domains=("math", "code"),
        metrics=("utility", "cost"),
        partitions=(partition,),
        minimum_replicates=2,
        protocol_sha256=d("frozen-protocol"),
        environment_sha256=d("environment"),
        frozen=True,
    )


def inventory(
    item_plan: StudyPlan,
    *,
    omit_last: bool = False,
    safeguards: StudySafeguards | None = None,
) -> StudyRunInventory:
    cells = [
        StudyRunCell(
            partition=partition,
            domain=domain,
            arm=arm,
            replicate_count=2,
            source_sha256=d(f"{partition.value}:{domain}:{arm}"),
            budget_sha256=d(f"budget:{partition.value}:{domain}"),
        )
        for partition in item_plan.partitions
        for domain in item_plan.domains
        for arm in item_plan.arms
    ]
    if omit_last:
        cells.pop()
    return StudyRunInventory(
        cells=tuple(cells),
        safeguards=safeguards
        or StudySafeguards(
            cost_complete=True,
            contamination_free=True,
            negative_controls_passed=True,
        ),
        cost_ledger_sha256=d("cost-ledger"),
        source_bundle_sha256=d("source-bundle"),
    )


class LaterStudyContractTests(unittest.TestCase):
    def test_complete_held_out_rq26_contract_is_ready_but_non_promoting(self) -> None:
        item_plan = plan()
        result = validate_study_contract(item_plan, inventory(item_plan))
        self.assertEqual(result.status, StudyContractStatus.READY_FOR_ANALYSIS)
        self.assertFalse(result.efficacy_established)
        self.assertFalse(result.promotion_authorized)
        self.assertFalse(result.execution_authorized)

    def test_development_contract_never_becomes_held_out_evidence(self) -> None:
        item_plan = plan(partition=EvidencePartition.DEVELOPMENT)
        result = validate_study_contract(item_plan, inventory(item_plan))
        self.assertEqual(result.status, StudyContractStatus.DEVELOPMENT_ONLY)

    def test_missing_arm_cell_fails_closed(self) -> None:
        item_plan = plan()
        result = validate_study_contract(
            item_plan,
            inventory(item_plan, omit_last=True),
        )
        self.assertEqual(result.status, StudyContractStatus.INCOMPLETE)
        self.assertIn("incomplete_run_matrix", result.reason_codes)

    def test_model_ladder_requires_factorial_models_and_efforts(self) -> None:
        models = ("provider/model-a@sha256:a", "provider/model-b@sha256:b")
        efforts = ("low", "high")
        arms = tuple(f"{model}@{effort}" for model in models for effort in efforts)
        item_plan = StudyPlan(
            study_id="small-model-ladder",
            kind=StudyKind.MODEL_STRENGTH_LADDER,
            arms=arms,
            domains=("math",),
            metrics=("utility", "cost"),
            partitions=(EvidencePartition.LOCK,),
            minimum_replicates=2,
            protocol_sha256=d("ladder-protocol"),
            environment_sha256=d("ladder-environment"),
            frozen=True,
            model_fingerprints=models,
            effort_levels=efforts,
        )
        result = validate_study_contract(item_plan, inventory(item_plan))
        self.assertEqual(result.status, StudyContractStatus.READY_FOR_ANALYSIS)

    def test_history_and_human_contracts_require_their_specific_safeguards(self) -> None:
        history = plan(StudyKind.HISTORY_POLICY)
        history_result = validate_study_contract(history, inventory(history))
        self.assertIn("history_safeguards_incomplete", history_result.reason_codes)
        human = plan(StudyKind.HUMAN_COMPLEMENT)
        human_result = validate_study_contract(human, inventory(human))
        self.assertIn("delayed_transfer_missing", human_result.reason_codes)


if __name__ == "__main__":
    unittest.main()
