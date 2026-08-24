"""Contract and integration tests for the completed FOIL v5 seams."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_bridge import HostActionRequest  # noqa: E402
from egrt_host_finalizer import answer_digest  # noqa: E402
from foil_adaptive_route import (  # noqa: E402
    AdaptiveRoutePolicy,
    FrozenEVModel,
    RiskClass,
    Route,
)
from foil_formalization_admission import (  # noqa: E402
    FormalizationAdmissionStatus,
    FormalizationCalibration,
    FormalizationFidelityPolicy,
    FormalizationInstanceChecks,
    FormalizationRouteBinding,
    TranslationDistance,
    admit_formalization,
    clopper_pearson_lower_ppm,
    compile_admitted_task_spec,
)
from foil_formalization_routing import (  # noqa: E402
    AdmittedShadowRouteDecision,
    decide_admitted_shadow_route,
)
from foil_obligation_compiler import COMPILER_VERSION, TASK_SPEC_SCHEMA  # noqa: E402
from foil_shadow_route_ledger import ShadowRouteVectorLedger  # noqa: E402
from foil_v5_pipeline import (  # noqa: E402
    PipelineStatus,
    finalize_external_candidate,
    run_structured_shadow,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task_spec(base: str, *, expected: str = "4") -> dict[str, object]:
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d("pipeline-task"),
        "a0_digest": answer_digest(base),
        "config_digest": d("pipeline-config"),
        "claims": [
            {
                "claim_key": "arithmetic",
                "statement_digest": d("2 + 2 exact result"),
                "claim_kind": "EXACT_ARITHMETIC",
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "host or admitted exact predicate",
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


def route_binding() -> FormalizationRouteBinding:
    return FormalizationRouteBinding(
        route_id="nl-arithmetic-v1",
        route_version="1",
        translation_distance=TranslationDistance.TRANSLATION,
        formalizer_fingerprints_sha256=(d("formalizer-a"), d("formalizer-b")),
        task_regime_sha256=d("short-arithmetic"),
        target_schema=TASK_SPEC_SCHEMA,
    )


def calibration(binding: FormalizationRouteBinding) -> FormalizationCalibration:
    return FormalizationCalibration(
        route_binding_digest=binding.binding_digest,
        audited_faithful=60,
        audited_unfaithful=0,
        extracted_load_bearing_claims=60,
        source_load_bearing_claims=60,
        mutation_classes_expected=("scope", "number", "operator"),
        mutation_classes_caught=("scope", "number", "operator"),
        error_correlation_ppm=300_000,
        auditor_provenance_sha256=d("independent-auditor"),
        evidence_sha256=d("calibration-evidence"),
        observed_at="2026-08-24T00:00:00+00:00",
        expires_at="2026-09-24T00:00:00+00:00",
    )


def checks(
    binding: FormalizationRouteBinding,
    spec: object,
) -> FormalizationInstanceChecks:
    return FormalizationInstanceChecks(
        route_binding_digest=binding.binding_digest,
        source_text_sha256=d("What is 2 + 2?"),
        generated_spec_sha256=digest_for(spec),
        round_trip_passed=True,
        forward_entailment_passed=True,
        reverse_entailment_passed=True,
        dual_formalization_agreed=True,
        mechanical_equivalence_sha256=d("mechanical-equivalence"),
        extraction_review_passed=True,
        check_evidence_sha256=(d("round-trip"), d("dual-formalization")),
    )


def digest_for(value: object) -> str:
    from egrt_types import digest

    return digest(value)


def policy() -> FormalizationFidelityPolicy:
    return FormalizationFidelityPolicy(
        enabled=True,
        confidence_ppm=950_000,
        fidelity_floor_ppm=950_000,
        extraction_recall_floor_ppm=950_000,
        min_audited_transforms=3,
        max_error_correlation_ppm=600_000,
    )


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
        evidence_digest=d("pipeline-ev"),
    )


class FormalizationAdmissionTests(unittest.TestCase):
    def test_exact_zero_failure_boundaries(self) -> None:
        self.assertGreaterEqual(clopper_pearson_lower_ppm(29, 29, 950_000), 900_000)
        self.assertLess(clopper_pearson_lower_ppm(28, 28, 950_000), 900_000)
        self.assertGreaterEqual(clopper_pearson_lower_ppm(59, 59, 950_000), 950_000)
        self.assertLess(clopper_pearson_lower_ppm(58, 58, 950_000), 950_000)

    def test_translation_route_admits_only_complete_bound_evidence(self) -> None:
        base = "2 + 2 = 5"
        spec = task_spec(base)
        binding = route_binding()
        receipt = admit_formalization(
            binding,
            calibration(binding),
            checks(binding, spec),
            policy(),
            now="2026-08-24T12:00:00+00:00",
        )
        self.assertEqual(receipt.status, FormalizationAdmissionStatus.ADMITTED)
        admitted = compile_admitted_task_spec(
            spec,
            observed_a0_digest=answer_digest(base),
            admission=receipt,
        )
        self.assertEqual(admitted.compiled.source_spec_digest, receipt.generated_spec_sha256)
        self.assertFalse(receipt.execution_authorized)

    def test_route_for_another_compiler_schema_stands_down(self) -> None:
        base = "2 + 2 = 5"
        spec = task_spec(base)
        source = route_binding()
        wrong = FormalizationRouteBinding(
            **{
                **source.__dict__,
                "target_schema": "egrt.unsupported-task-spec.v9",
            }
        )
        receipt = admit_formalization(
            wrong,
            calibration(wrong),
            checks(wrong, spec),
            policy(),
            now="2026-08-24T12:00:00+00:00",
        )
        self.assertEqual(receipt.status, FormalizationAdmissionStatus.STAND_DOWN)
        self.assertEqual(receipt.reason_code, "unsupported_target_schema")

    def test_mutation_omission_and_correlation_fail_closed(self) -> None:
        base = "2 + 2 = 5"
        spec = task_spec(base)
        binding = route_binding()
        source = calibration(binding)
        cases = (
            (
                FormalizationCalibration(
                    **{
                        **source.__dict__,
                        "mutation_classes_caught": ("scope", "number"),
                    }
                ),
                "mutation_suite_incomplete",
            ),
            (
                FormalizationCalibration(
                    **{
                        **source.__dict__,
                        "extracted_load_bearing_claims": 59,
                    }
                ),
                "extraction_recall_lower_bound_below_floor",
            ),
            (
                FormalizationCalibration(
                    **{
                        **source.__dict__,
                        "error_correlation_ppm": 900_000,
                    }
                ),
                "formalizer_error_correlation_above_limit",
            ),
        )
        for item, reason in cases:
            with self.subTest(reason=reason):
                receipt = admit_formalization(
                    binding,
                    item,
                    checks(binding, spec),
                    policy(),
                    now="2026-08-24T12:00:00+00:00",
                )
                self.assertEqual(receipt.status, FormalizationAdmissionStatus.STAND_DOWN)
                self.assertEqual(receipt.reason_code, reason)


class IntegratedPipelineTests(unittest.TestCase):
    def test_host_spec_runs_compiler_scanner_controller_and_ledger(self) -> None:
        base = "2 + 2 = 5"
        ledger = ShadowRouteVectorLedger(enabled=True)
        result = run_structured_shadow(
            base_answer=base,
            task_spec=task_spec(base, expected="5"),
            route_policy=AdaptiveRoutePolicy(enabled=True),
            ev=ev_model(),
            route_ledger=ledger,
            model_fingerprint_sha256=d("model"),
            contract_fingerprint_sha256=d("contract"),
        )
        self.assertEqual(result.status, PipelineStatus.DEFECT)
        self.assertEqual(result.decision.route, Route.FULL)
        self.assertIs(result.base_answer, base)
        self.assertTrue(result.route_observation_recorded)
        self.assertEqual(ledger.seal()["record_count"], 1)
        self.assertFalse(result.trace()["execution_authorized"])

    def test_admitted_generated_spec_keeps_origin_visible(self) -> None:
        base = "2 + 2 = 5"
        spec = task_spec(base, expected="5")
        binding = route_binding()
        receipt = admit_formalization(
            binding,
            calibration(binding),
            checks(binding, spec),
            policy(),
            now="2026-08-24T12:00:00+00:00",
        )
        admitted = compile_admitted_task_spec(
            spec,
            observed_a0_digest=answer_digest(base),
            admission=receipt,
        )
        result = run_structured_shadow(
            base_answer=base,
            admitted=admitted,
            route_policy=AdaptiveRoutePolicy(enabled=True),
            ev=ev_model(),
            model_fingerprint_sha256=d("model"),
            contract_fingerprint_sha256=d("contract"),
        )
        self.assertIsInstance(result.route, AdmittedShadowRouteDecision)
        self.assertEqual(result.route.origin, "ADMITTED_GENERATED")
        self.assertEqual(result.decision.route, Route.FULL)

    def test_admitted_route_wrapper_selects_exact_compiler_obligation(self) -> None:
        base = "2 + 2 = 5"
        spec = task_spec(base, expected="5")
        binding = route_binding()
        receipt = admit_formalization(
            binding,
            calibration(binding),
            checks(binding, spec),
            policy(),
            now="2026-08-24T12:00:00+00:00",
        )
        admitted = compile_admitted_task_spec(
            spec,
            observed_a0_digest=answer_digest(base),
            admission=receipt,
        )
        obligation_id = admitted.compiled.claims[0].obligations[0].obligation.obligation_id
        decision = decide_admitted_shadow_route(
            admitted,
            risk=RiskClass.ONE_FALSIFIABLE,
            policy=AdaptiveRoutePolicy(enabled=True),
            ev=ev_model(),
            obligation_ids=(obligation_id,),
        )
        self.assertEqual(decision.decision.route, Route.VERIFY)
        self.assertEqual(decision.origin, "ADMITTED_GENERATED")

    def test_clear_answer_stands_down_and_preserves_exact_object(self) -> None:
        base = "2 + 2 = 4"
        result = run_structured_shadow(
            base_answer=base,
            task_spec=task_spec(base),
            route_policy=AdaptiveRoutePolicy(enabled=True),
            ev=ev_model(),
            model_fingerprint_sha256=d("model"),
            contract_fingerprint_sha256=d("contract"),
        )
        self.assertEqual(result.status, PipelineStatus.CLEARED)
        self.assertEqual(result.decision.route, Route.DIRECT)
        self.assertIs(result.base_answer, base)

    def test_finalizer_wrapper_rejects_request_for_other_a0(self) -> None:
        base = "2 + 2 = 4"
        result = run_structured_shadow(
            base_answer=base,
            task_spec=task_spec(base),
            model_fingerprint_sha256=d("model"),
            contract_fingerprint_sha256=d("contract"),
        )
        request = HostActionRequest(
            candidate_id="candidate",
            base_digest=d("other-base"),
            candidate_digest=answer_digest("candidate"),
            scope_digest=d("scope"),
            obligation_set_digest=d("obligations"),
            artifact_locator="host://candidate",
            artifact_sha256=answer_digest("candidate"),
            proposal_digest=d("proposal"),
            structural_certificate_digest=d("structural"),
            semantic_certificate_digest=d("semantic"),
        )
        with self.assertRaisesRegex(ValueError, "pipeline A0"):
            finalize_external_candidate(
                result,
                request,
                candidate_answer="candidate",
            )


if __name__ == "__main__":
    unittest.main()
