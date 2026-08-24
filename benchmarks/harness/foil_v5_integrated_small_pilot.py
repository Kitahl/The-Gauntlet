#!/usr/bin/env python3
"""Run the preregistered, zero-provider FOIL v5 integration pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import digest  # noqa: E402
from foil_adaptive_route import AdaptiveRoutePolicy, FrozenEVModel, Route  # noqa: E402
from foil_formalization_admission import (  # noqa: E402
    FormalizationAdmissionStatus,
    FormalizationCalibration,
    FormalizationFidelityPolicy,
    FormalizationInstanceChecks,
    FormalizationRouteBinding,
    TranslationDistance,
    admit_formalization,
    compile_admitted_task_spec,
)
from foil_later_studies import (  # noqa: E402
    StudyContractStatus,
    StudyKind,
    StudyPlan,
    StudyRunCell,
    StudyRunInventory,
    StudySafeguards,
    validate_study_contract,
)
from foil_obligation_compiler import COMPILER_VERSION, TASK_SPEC_SCHEMA  # noqa: E402
from foil_promotion_gates import (  # noqa: E402
    EvidencePartition,
    GateEvaluationPlan,
    GateEvaluationStatus,
    GateEvidence,
    GateMetricObservation,
    MetricDirection,
    MetricRule,
    evaluate_gate,
)
from foil_shadow_route_ledger import ShadowRouteVectorLedger  # noqa: E402
from foil_v5_pipeline import PipelineStatus, run_structured_shadow  # noqa: E402
from foil_candidate_state import Gate  # noqa: E402


PROTOCOL = {
    "schema": "foil.v5-integrated-small-pilot.v1",
    "case_ids": (
        "host-defect-full",
        "host-clear-direct",
        "admitted-generated-visible",
        "incomplete-formalization-stands-down",
        "development-gate-nonpromoting",
        "development-study-nonpromoting",
    ),
    "provider_calls_allowed": 0,
    "network_calls_allowed": 0,
    "token_spend_allowed": 0,
    "candidate_generation_allowed": False,
    "efficacy_claim_allowed": False,
}
PROTOCOL_SHA256 = digest(PROTOCOL)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task_spec(base: str, expected: str) -> dict[str, object]:
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d("integrated-small-pilot-task"),
        "a0_digest": answer_digest(base),
        "config_digest": d("integrated-small-pilot-config"),
        "claims": [
            {
                "claim_key": "arithmetic",
                "statement_digest": d("2 + 2 exact result"),
                "claim_kind": "EXACT_ARITHMETIC",
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "Frozen synthetic integration predicate",
                "obligations": [
                    {
                        "obligation_key": "sum",
                        "description": "The arithmetic result must be exact",
                        "weight_range": {"start": 1, "end": 1},
                        "predicate_kind": "EXACT_ARITHMETIC",
                        "verifier_id": "builtin.exact_arithmetic",
                        "verifier_version": "1",
                        "verifier_input": {
                            "expression": "2 + 2",
                            "expected": expected,
                        },
                    }
                ],
            }
        ],
    }


def ev_model() -> FrozenEVModel:
    return FrozenEVModel(
        base_correct_ppm=500_000,
        verify_rescue_ppm=700_000,
        verify_damage_ppm=50_000,
        full_rescue_ppm=800_000,
        full_damage_ppm=100_000,
        rescue_utility_micro=1_000_000,
        damage_disutility_micro=1_000_000,
        cost_penalty_micro_per_unit=10_000,
        verify_incremental_cost_units=1,
        full_incremental_cost_units=2,
        evidence_digest=d("integrated-small-pilot-ev"),
    )


def route_binding() -> FormalizationRouteBinding:
    return FormalizationRouteBinding(
        route_id="synthetic-arithmetic-v1",
        route_version="1",
        translation_distance=TranslationDistance.TRANSLATION,
        formalizer_fingerprints_sha256=(d("formalizer-a"), d("formalizer-b")),
        task_regime_sha256=d("synthetic-short-arithmetic"),
        target_schema=TASK_SPEC_SCHEMA,
    )


def calibration(
    binding: FormalizationRouteBinding,
    *,
    mutation_complete: bool,
) -> FormalizationCalibration:
    return FormalizationCalibration(
        route_binding_digest=binding.binding_digest,
        audited_faithful=3,
        audited_unfaithful=0,
        extracted_load_bearing_claims=3,
        source_load_bearing_claims=3,
        mutation_classes_expected=("number", "operator"),
        mutation_classes_caught=("number", "operator") if mutation_complete else ("number",),
        error_correlation_ppm=300_000,
        auditor_provenance_sha256=d("synthetic-independent-auditor"),
        evidence_sha256=d("synthetic-development-calibration"),
        observed_at="2026-08-24T00:00:00+00:00",
        expires_at="2026-09-24T00:00:00+00:00",
    )


def instance_checks(
    binding: FormalizationRouteBinding,
    spec: object,
) -> FormalizationInstanceChecks:
    return FormalizationInstanceChecks(
        route_binding_digest=binding.binding_digest,
        source_text_sha256=d("What is 2 + 2?"),
        generated_spec_sha256=digest(spec),
        round_trip_passed=True,
        forward_entailment_passed=True,
        reverse_entailment_passed=True,
        dual_formalization_agreed=True,
        mechanical_equivalence_sha256=d("mechanical-equivalence"),
        extraction_review_passed=True,
        check_evidence_sha256=(d("round-trip"), d("dual-formalization")),
    )


def formalization_policy() -> FormalizationFidelityPolicy:
    return FormalizationFidelityPolicy(
        enabled=True,
        confidence_ppm=800_000,
        fidelity_floor_ppm=500_000,
        extraction_recall_floor_ppm=500_000,
        min_audited_transforms=3,
        max_error_correlation_ppm=600_000,
    )


def development_gate_result():
    plan = GateEvaluationPlan(
        plan_id="synthetic-development-gate",
        gate=Gate.GATE1,
        candidate_binding_digest=d("synthetic-gate-candidate-binding"),
        required_partitions=(EvidencePartition.DEVELOPMENT,),
        required_domains=("arithmetic",),
        metric_rules=(
            MetricRule(
                "wiring_recall",
                MetricDirection.AT_LEAST,
                500_000,
                800_000,
                3,
            ),
        ),
        protocol_sha256=d("synthetic-development-gate-protocol"),
    )
    evidence = GateEvidence(
        observations=(
            GateMetricObservation(
                EvidencePartition.DEVELOPMENT,
                "arithmetic",
                "wiring_recall",
                3,
                3,
                d("synthetic-development-gate-source"),
            ),
        ),
        cost_ledger_sha256=d("zero-cost-ledger"),
        source_bundle_sha256=d("synthetic-development-source-bundle"),
        forbidden_calls=0,
        cost_complete=True,
        exact_a0_preserved=True,
        negative_controls_passed=True,
    )
    return evaluate_gate(plan, evidence)


def development_study_result():
    arms = ("RAW", "CHECKLIST", "FOIL", "ORACLE")
    plan = StudyPlan(
        study_id="synthetic-development-rq26",
        kind=StudyKind.RQ26_COMPLEMENT,
        arms=arms,
        domains=("arithmetic",),
        metrics=("contract_completeness",),
        partitions=(EvidencePartition.DEVELOPMENT,),
        minimum_replicates=1,
        protocol_sha256=d("synthetic-development-rq26-protocol"),
        environment_sha256=d("synthetic-environment"),
        frozen=True,
    )
    inventory = StudyRunInventory(
        cells=tuple(
            StudyRunCell(
                EvidencePartition.DEVELOPMENT,
                "arithmetic",
                arm,
                1,
                d(f"synthetic-source:{arm}"),
                d("matched-zero-budget"),
            )
            for arm in arms
        ),
        safeguards=StudySafeguards(
            cost_complete=True,
            contamination_free=True,
            negative_controls_passed=True,
        ),
        cost_ledger_sha256=d("zero-cost-ledger"),
        source_bundle_sha256=d("synthetic-development-rq26-source-bundle"),
    )
    return validate_study_contract(plan, inventory)


def run_pilot() -> dict[str, object]:
    started = time.perf_counter()
    policy = AdaptiveRoutePolicy(enabled=True)
    fingerprint = d("integrated-small-pilot-model")
    contract = d("integrated-small-pilot-contract")
    rows: list[dict[str, object]] = []

    bad = "2 + 2 = 5"
    ledger = ShadowRouteVectorLedger(enabled=True)
    defect = run_structured_shadow(
        base_answer=bad,
        task_spec=task_spec(bad, "5"),
        route_policy=policy,
        ev=ev_model(),
        route_ledger=ledger,
        model_fingerprint_sha256=fingerprint,
        contract_fingerprint_sha256=contract,
    )
    rows.append(
        _row(
            "host-defect-full",
            f"{defect.status.value}/{defect.decision.route.value}",
            "DEFECT/FULL",
            defect.base_answer is bad and defect.route_observation_recorded,
        )
    )

    good = "2 + 2 = 4"
    cleared = run_structured_shadow(
        base_answer=good,
        task_spec=task_spec(good, "4"),
        route_policy=policy,
        ev=ev_model(),
        model_fingerprint_sha256=fingerprint,
        contract_fingerprint_sha256=contract,
    )
    rows.append(
        _row(
            "host-clear-direct",
            f"{cleared.status.value}/{cleared.decision.route.value}",
            "CLEARED/DIRECT",
            cleared.base_answer is good,
        )
    )

    generated_spec = task_spec(bad, "5")
    binding = route_binding()
    admitted_receipt = admit_formalization(
        binding,
        calibration(binding, mutation_complete=True),
        instance_checks(binding, generated_spec),
        formalization_policy(),
        now="2026-08-24T12:00:00+00:00",
    )
    admitted = compile_admitted_task_spec(
        generated_spec,
        observed_a0_digest=answer_digest(bad),
        admission=admitted_receipt,
    )
    generated = run_structured_shadow(
        base_answer=bad,
        admitted=admitted,
        route_policy=policy,
        ev=ev_model(),
        model_fingerprint_sha256=fingerprint,
        contract_fingerprint_sha256=contract,
    )
    observed_generated = (
        f"{admitted_receipt.status.value}/{generated.route.origin}/"
        f"{generated.decision.route.value}"
    )
    rows.append(
        _row(
            "admitted-generated-visible",
            observed_generated,
            "ADMITTED/ADMITTED_GENERATED/FULL",
            generated.base_answer is bad,
        )
    )

    rejected = admit_formalization(
        binding,
        calibration(binding, mutation_complete=False),
        instance_checks(binding, generated_spec),
        formalization_policy(),
        now="2026-08-24T12:00:00+00:00",
    )
    rows.append(
        _row(
            "incomplete-formalization-stands-down",
            f"{rejected.status.value}/{rejected.reason_code}",
            "STAND_DOWN/mutation_suite_incomplete",
            rejected.status is FormalizationAdmissionStatus.STAND_DOWN,
        )
    )

    gate = development_gate_result()
    rows.append(
        _row(
            "development-gate-nonpromoting",
            f"{gate.status.value}/promotion={gate.promotion_eligible}",
            "PASS/promotion=False",
            gate.status is GateEvaluationStatus.PASS and not gate.promotion_eligible,
        )
    )

    study = development_study_result()
    rows.append(
        _row(
            "development-study-nonpromoting",
            f"{study.status.value}/promotion={study.promotion_authorized}",
            "DEVELOPMENT_ONLY/promotion=False",
            study.status is StudyContractStatus.DEVELOPMENT_ONLY
            and not study.promotion_authorized,
        )
    )

    passed = sum(bool(row["passed"]) for row in rows)
    return {
        "schema": PROTOCOL["schema"],
        "protocol_sha256": PROTOCOL_SHA256,
        "classification": "SYNTHETIC_INTEGRATION_ONLY",
        "cases": rows,
        "summary": {
            "passed": passed,
            "total": len(rows),
            "all_passed": passed == len(rows),
            "provider_calls": 0,
            "network_calls": 0,
            "token_spend": 0,
            "candidate_generations": 0,
            "answer_mutations": 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        "non_claims": (
            "No external efficacy or promotion evidence was collected.",
            "The three-item formalization row is synthetic wiring data.",
            "Development-only PASS cannot promote a candidate.",
        ),
    }


def _row(case_id: str, observed: str, expected: str, invariant: bool) -> dict[str, object]:
    return {
        "case_id": case_id,
        "observed": observed,
        "expected": expected,
        "invariant_passed": invariant,
        "passed": observed == expected and invariant,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--protocol-sha256", default=PROTOCOL_SHA256)
    args = parser.parse_args()
    if args.protocol_sha256 != PROTOCOL_SHA256:
        parser.error("protocol digest mismatch")
    report = run_pilot()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
