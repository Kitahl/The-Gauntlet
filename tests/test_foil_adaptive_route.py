from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_verifiers import DEFAULT_REGISTRY  # noqa: E402
from foil_adaptive_route import (  # noqa: E402
    AdaptiveRoutePolicy,
    CapabilityPosterior,
    DecisionReason,
    FrozenEVModel,
    ObligationOrigin,
    ProbeModel,
    RiskClass,
    Route,
    decide_shadow_route,
    host_verifier_routes,
    make_host_verifier_route,
)
from foil_obligation_compiler import (  # noqa: E402
    COMPILER_VERSION,
    TASK_SPEC_SCHEMA,
    compile_task_spec,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task_spec(*, two: bool = False, failing: bool = False) -> dict[str, object]:
    claims: list[dict[str, object]] = [
        {
            "claim_key": "arithmetic-claim",
            "statement_digest": d("arithmetic statement"),
            "claim_kind": "EXACT_ARITHMETIC",
            "decidability": "DETERMINISTIC",
            "applicability": "APPLICABLE",
            "reason": "Host declared an exact arithmetic predicate.",
            "obligations": [
                {
                    "obligation_key": "sum",
                    "description": "Declared exact arithmetic check",
                    "weight_range": {"start": 1, "end": 1},
                    "predicate_kind": "EXACT_ARITHMETIC",
                    "verifier_id": "builtin.exact_arithmetic",
                    "verifier_version": "1",
                    "verifier_input": {
                        "expression": "2 + 3",
                        "expected": "6" if failing else "5",
                    },
                }
            ],
        }
    ]
    if two:
        claims.append(
            {
                "claim_key": "match-claim",
                "statement_digest": d("match statement"),
                "claim_kind": "EXACT_MATCH",
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "Host declared an exact match predicate.",
                "obligations": [
                    {
                        "obligation_key": "match",
                        "description": "Declared exact match check",
                        "weight_range": {"start": 2, "end": 2},
                        "predicate_kind": "EXACT_MATCH",
                        "verifier_id": "builtin.exact_match",
                        "verifier_version": "1",
                        "verifier_input": {"actual": "x", "expected": "x"},
                    }
                ],
            }
        )
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": d("task"),
        "a0_digest": d("a0"),
        "config_digest": d("config"),
        "claims": claims,
    }

def compiled(*, two: bool = False, failing: bool = False):
    value = task_spec(two=two, failing=failing)
    return compile_task_spec(value, observed_a0_digest=value["a0_digest"])


def ev(**overrides) -> FrozenEVModel:
    values = {
        "base_correct_ppm": 500_000,
        "verify_rescue_ppm": 700_000,
        "verify_damage_ppm": 50_000,
        "full_rescue_ppm": 800_000,
        "full_damage_ppm": 100_000,
        "rescue_utility_micro": 1_000_000,
        "damage_disutility_micro": 1_000_000,
        "cost_penalty_micro_per_unit": 10_000,
        "verify_incremental_cost_units": 1,
        "full_incremental_cost_units": 2,
        "evidence_digest": d("ev"),
    }
    values.update(overrides)
    return FrozenEVModel(**values)


class HostDeclaredRouteTests(unittest.TestCase):
    def test_adapter_exposes_only_compiler_created_deterministic_routes(self) -> None:
        result = compiled(two=True)
        routes = host_verifier_routes(result)
        self.assertEqual(len(routes), 2)
        self.assertEqual({route.verifier_id for route in routes}, {
            "builtin.exact_arithmetic",
            "builtin.exact_match",
        })
        self.assertTrue(all(route.origin is ObligationOrigin.HOST_DECLARED for route in routes))
        self.assertTrue(all(route.bindings == result.bindings for route in routes))

    def test_unknown_claim_or_obligation_fails_closed(self) -> None:
        result = compiled()
        with self.assertRaises(KeyError):
            make_host_verifier_route(result, claim_id="missing", obligation_id="missing")


class AdaptiveRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compiled = compiled(two=True)
        self.bindings = self.compiled.bindings
        self.routes = host_verifier_routes(self.compiled)
        self.policy = AdaptiveRoutePolicy(enabled=True)

    def decide(self, **overrides):
        values = {
            "bindings": self.bindings,
            "risk": RiskClass.ONE_FALSIFIABLE,
            "policy": self.policy,
            "ev": ev(),
            "compiled_spec": self.compiled,
            "obligation_ids": (self.routes[0].obligation_id,),
            "verifier_routes": (self.routes[0],),
        }
        values.update(overrides)
        return decide_shadow_route(**values)

    def test_default_off_is_direct_and_never_authorizes_execution(self) -> None:
        decision = self.decide(policy=AdaptiveRoutePolicy())
        self.assertEqual((decision.route, decision.reason), (
            Route.DIRECT,
            DecisionReason.CONTROLLER_DISABLED,
        ))
        self.assertFalse(decision.execution_authorized)
        self.assertTrue(decision.base_answer_preserved)
        self.assertTrue(decision.host_action_required)

    def test_one_declared_falsifiable_risk_recommends_verify_only_when_ev_positive(self) -> None:
        decision = self.decide()
        self.assertEqual(decision.route, Route.VERIFY)
        self.assertGreater(decision.expected_value_numerator, 0)
        negative = self.decide(
            ev=ev(
                base_correct_ppm=999_000,
                verify_rescue_ppm=1_000,
                verify_damage_ppm=900_000,
            )
        )
        self.assertEqual(negative.route, Route.DIRECT)
        self.assertLessEqual(negative.expected_value_numerator, 0)

    def test_multiple_declared_risks_recommend_full_and_budget_can_block_it(self) -> None:
        ids = tuple(route.obligation_id for route in self.routes)
        decision = self.decide(
            risk=RiskClass.MULTIPLE_OR_CONTRADICTORY,
            obligation_ids=ids,
            verifier_routes=self.routes,
        )
        self.assertEqual(decision.route, Route.FULL)
        blocked = self.decide(
            risk=RiskClass.MULTIPLE_OR_CONTRADICTORY,
            obligation_ids=ids,
            verifier_routes=self.routes,
            remaining_cost_units=1,
        )
        self.assertEqual(blocked.reason, DecisionReason.COST_CAP_EXHAUSTED)
        self.assertEqual(blocked.route, Route.DIRECT)

    def test_model_generated_or_mismatched_routes_are_ineligible(self) -> None:
        generated = replace(self.routes[0], origin=ObligationOrigin.MODEL_GENERATED)
        decision = self.decide(verifier_routes=(generated,))
        self.assertEqual(decision.reason, DecisionReason.GENERATED_OBLIGATION_INELIGIBLE)
        mismatched = self.decide(obligation_ids=("other",))
        self.assertEqual(mismatched.reason, DecisionReason.HOST_ROUTE_UNAVAILABLE)

    def test_fabricated_host_route_is_not_compiler_provenance(self) -> None:
        fabricated = replace(self.routes[0], verifier_id="not.in.registry")
        decision = self.decide(verifier_routes=(fabricated,))
        self.assertEqual(decision.route, Route.DIRECT)
        self.assertEqual(decision.reason, DecisionReason.HOST_ROUTE_UNAVAILABLE)
        missing_compiled_spec = self.decide(compiled_spec=None)
        self.assertEqual(missing_compiled_spec.reason, DecisionReason.HOST_ROUTE_UNAVAILABLE)

    def test_verified_defect_requires_exact_matching_closed_verifier_failure(self) -> None:
        bad_compiled = compiled(failing=True)
        route = host_verifier_routes(bad_compiled)[0]
        case = bad_compiled.deterministic_cases(route.claim_id)[0]
        result = DEFAULT_REGISTRY.run(route.verifier_id, case.verifier_input)
        decision = decide_shadow_route(
            bindings=bad_compiled.bindings,
            risk=RiskClass.VERIFIED_DEFECT,
            policy=self.policy,
            ev=ev(),
            compiled_spec=bad_compiled,
            obligation_ids=(route.obligation_id,),
            verifier_routes=(route,),
            verification=result,
        )
        self.assertEqual(decision.route, Route.FULL)
        passing_case = self.compiled.deterministic_cases(self.routes[0].claim_id)[0]
        passing = DEFAULT_REGISTRY.run(self.routes[0].verifier_id, passing_case.verifier_input)
        stood_down = self.decide(risk=RiskClass.VERIFIED_DEFECT, verification=passing)
        self.assertEqual(stood_down.reason, DecisionReason.VERIFIER_RESULT_NOT_A_DEFECT)

    def test_conditional_k2_is_a_nonfinal_host_request_not_a_model_call(self) -> None:
        probe = ProbeModel(30_000, 1, 10_000, d("probe"))
        decision = self.decide(
            risk=RiskClass.NONE,
            policy=AdaptiveRoutePolicy(enabled=True, probe_enabled=True),
            ev=None,
            obligation_ids=(),
            verifier_routes=(),
            borderline=True,
            probe=probe,
        )
        self.assertEqual(decision.reason, DecisionReason.CONDITIONAL_K2_PROBE)
        self.assertEqual(decision.probe_resamples, 2)
        self.assertFalse(decision.final)
        self.assertFalse(decision.execution_authorized)

    def test_stand_down_requires_fresh_count_backed_matching_posterior(self) -> None:
        model, contract = d("model"), d("contract")
        posterior = CapabilityPosterior(
            correct=100,
            incorrect=0,
            model_fingerprint=model,
            contract_fingerprint=contract,
            task_regime="closed_book",
            evidence_digest=d("posterior"),
            fresh=True,
        )
        policy = AdaptiveRoutePolicy(
            enabled=True,
            stand_down_enabled=True,
            stand_down_accuracy_ppm=900_000,
            stand_down_confidence_ppm=950_000,
            stand_down_min_observations=20,
        )
        decision = self.decide(
            risk=RiskClass.NONE,
            policy=policy,
            ev=None,
            obligation_ids=(),
            verifier_routes=(),
            posterior=posterior,
            model_fingerprint=model,
            contract_fingerprint=contract,
            task_regime="closed_book",
        )
        self.assertEqual(decision.reason, DecisionReason.POSTERIOR_STAND_DOWN)
        mismatch = self.decide(
            risk=RiskClass.NONE,
            policy=policy,
            ev=None,
            obligation_ids=(),
            verifier_routes=(),
            posterior=posterior,
            model_fingerprint=d("other-model"),
            contract_fingerprint=contract,
            task_regime="closed_book",
        )
        self.assertEqual(mismatch.reason, DecisionReason.NO_POSITIVE_VALUE_COMPLEMENT)

    def test_stand_down_policy_rejects_vacuous_evidence_gates(self) -> None:
        for values in (
            {"stand_down_accuracy_ppm": 0},
            {"stand_down_accuracy_ppm": 1_000_000},
            {"stand_down_confidence_ppm": 0},
            {"stand_down_confidence_ppm": 1_000_000},
            {"stand_down_min_observations": 0},
        ):
            policy = {
                "enabled": True,
                "stand_down_enabled": True,
                "stand_down_accuracy_ppm": 900_000,
                "stand_down_confidence_ppm": 950_000,
                "stand_down_min_observations": 1,
                **values,
            }
            with self.subTest(values=values), self.assertRaises(ValueError):
                AdaptiveRoutePolicy(**policy)

    def test_ev_monotonicity_and_digest_only_trace(self) -> None:
        values = []
        for q in range(0, 1_000_001, 10_000):
            values.append(ev(base_correct_ppm=q).expected_value_numerator(Route.VERIFY))
        self.assertTrue(all(left >= right for left, right in zip(values, values[1:])))
        trace = self.decide().trace()
        self.assertEqual(trace["expected_value_denominator"], 1_000_000_000_000)
        self.assertNotIn("Declared exact arithmetic", json.dumps(trace))
        self.assertFalse(trace["raw_answer_stored"])
        self.assertFalse(trace["raw_obligation_stored"])


if __name__ == "__main__":
    unittest.main()
