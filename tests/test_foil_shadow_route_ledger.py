from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_adaptive_route import Route  # noqa: E402
from foil_shadow_route_ledger import (  # noqa: E402
    AssignmentDesign,
    EligibilityReason,
    EligibilityTrace,
    OutcomeKind,
    RouteLedgerError,
    RouteVector,
    ShadowRouteObservation,
    ShadowRouteVectorLedger,
    verify_shadow_route_receipt,
)


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def vector(mode: Route = Route.VERIFY, provider: str = "terra") -> RouteVector:
    return RouteVector(mode, (d(provider),), "builtin.exact_match", "1", 0)


def eligibility(route: RouteVector | None = None, *, contract: str = "contract"):
    route = vector() if route is None else route
    return EligibilityTrace(d("task"), d("model"), d(contract), route, True, EligibilityReason.ELIGIBLE)


def observation(
    *,
    route: RouteVector | None = None,
    success: bool | None = True,
    design: AssignmentDesign = AssignmentDesign.OBSERVATIONAL,
) -> ShadowRouteObservation:
    route = vector() if route is None else route
    return ShadowRouteObservation(
        eligibility=eligibility(route),
        proposed=route,
        observed=route,
        outcome_kind=OutcomeKind.RESCUE if success else OutcomeKind.UNKNOWN,
        verified=True if success is not None else None,
        final_success=success,
        source_receipt_digest=d("source"),
        assignment_design=design,
        assignment_digest=d("assignment") if design is not AssignmentDesign.OBSERVATIONAL else None,
    )


class ShadowRouteLedgerTests(unittest.TestCase):
    def test_default_off_records_nothing(self) -> None:
        ledger = ShadowRouteVectorLedger()
        self.assertFalse(ledger.append(observation()))
        receipt = ledger.seal()
        self.assertEqual(receipt["record_count"], 0)
        self.assertFalse(receipt["enabled"])
        self.assertFalse(receipt["execution_authorized"])

    def test_exact_route_predictive_summary_never_claims_causality(self) -> None:
        route = vector()
        ledger = ShadowRouteVectorLedger(enabled=True)
        self.assertTrue(ledger.append(observation(route=route, success=True)))
        self.assertTrue(ledger.append(observation(route=route, success=False)))
        other = vector(Route.FULL, "sol")
        self.assertTrue(ledger.append(observation(route=other, success=True)))
        summary = ledger.predictive_summary(eligibility(route), route)
        self.assertEqual((summary["observed_count"], summary["success_count"]), (2, 1))
        self.assertFalse(summary["causal_claim_authorized"])
        self.assertFalse(summary["controller_update_authorized"])
        self.assertFalse(summary["component_credit_allocated"])

    def test_contract_and_route_versions_do_not_pool(self) -> None:
        route = vector()
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation(route=route))
        changed_contract = eligibility(route, contract="new-contract")
        self.assertEqual(ledger.records_for(changed_contract, route), ())
        changed_route = RouteVector(
            Route.VERIFY,
            (d("sol"),),
            "builtin.exact_match",
            "1",
            0,
        )
        self.assertEqual(ledger.records_for(eligibility(changed_route), changed_route), ())

    def test_assignment_design_is_recorded_but_does_not_authorize_learning(self) -> None:
        row = observation(design=AssignmentDesign.RANDOMIZED)
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(row)
        summary = ledger.predictive_summary(row.eligibility, row.proposed)
        self.assertFalse(summary["causal_claim_authorized"])
        with self.assertRaises(RouteLedgerError):
            ShadowRouteObservation(
                eligibility=row.eligibility,
                proposed=row.proposed,
                observed=row.observed,
                outcome_kind=row.outcome_kind,
                verified=row.verified,
                final_success=row.final_success,
                source_receipt_digest=row.source_receipt_digest,
                assignment_design=AssignmentDesign.MATCHED,
            )

    def test_component_credit_and_authority_fail_closed(self) -> None:
        base = observation()
        values = dict(base.__dict__)
        values["component_credit"] = 1
        with self.assertRaises(RouteLedgerError):
            ShadowRouteObservation(**values)
        values = dict(base.__dict__)
        values["execution_authorized"] = True
        with self.assertRaises(RouteLedgerError):
            ShadowRouteObservation(**values)
        values = dict(base.__dict__)
        values["controller_update_authorized"] = True
        with self.assertRaises(RouteLedgerError):
            ShadowRouteObservation(**values)

    def test_seal_verifies_and_tampering_is_detected(self) -> None:
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation())
        receipt = ledger.seal()
        verify_shadow_route_receipt(receipt)
        tampered = copy.deepcopy(receipt)
        tampered["records"][0]["final_success"] = False
        with self.assertRaises(RouteLedgerError):
            verify_shadow_route_receipt(tampered)

    def test_self_rehashed_unknown_or_raw_field_is_rejected(self) -> None:
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation())
        receipt = ledger.seal()
        tampered = copy.deepcopy(receipt)
        row = tampered["records"][0]
        row["raw_obligation"] = "secret claim"
        body = {key: value for key, value in row.items() if key != "observation_digest"}
        from egrt_types import digest

        row["observation_digest"] = digest(body)
        unsigned = {
            key: value for key, value in tampered.items() if key != "receipt_sha256"
        }
        tampered["receipt_sha256"] = digest(unsigned)
        with self.assertRaises(RouteLedgerError):
            verify_shadow_route_receipt(tampered)

    def test_disabled_receipt_cannot_be_rehashed_with_records(self) -> None:
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation())
        receipt = ledger.seal()
        receipt["enabled"] = False
        from egrt_types import digest

        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        receipt["receipt_sha256"] = digest(unsigned)
        with self.assertRaises(RouteLedgerError):
            verify_shadow_route_receipt(receipt)

    def test_provider_identifiers_are_digest_only_and_reason_is_closed(self) -> None:
        with self.assertRaises(RouteLedgerError):
            RouteVector(
                Route.VERIFY,
                ("raw answer: blue finch",),
                "builtin.exact_match",
                "1",
                0,
            )
        with self.assertRaises(ValueError):
            EligibilityTrace(
                d("task"),
                d("model"),
                d("contract"),
                vector(),
                True,
                "raw obligation: secret claim",
            )

    def test_exact_eligibility_state_does_not_pool(self) -> None:
        route = vector()
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation(route=route))
        ineligible = EligibilityTrace(
            d("task"),
            d("model"),
            d("contract"),
            route,
            False,
            EligibilityReason.BINDING_MISMATCH,
        )
        self.assertEqual(ledger.records_for(ineligible, route), ())

    def test_seal_is_idempotent_and_makes_ledger_immutable(self) -> None:
        ledger = ShadowRouteVectorLedger(enabled=True)
        ledger.append(observation())
        first = ledger.seal()
        self.assertEqual(first, ledger.seal())
        with self.assertRaises(RouteLedgerError):
            ledger.append(observation())


if __name__ == "__main__":
    unittest.main()
