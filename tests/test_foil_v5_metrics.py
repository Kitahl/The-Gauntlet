from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from egrt_coverage import ContributionOutcome, CoverageContribution  # noqa: E402
from foil_v5_metrics import (  # noqa: E402
    DIAGNOSTIC_CAPABILITY_REQUIREMENT_NAMESPACE,
    RESIDUAL_DIAGNOSTIC_NEED_NAMESPACE,
    DiagnosticCapabilityRequirement,
    ResidualDiagnosticNeed,
    summarize_metrics,
)


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "abcde"])


def need(
    ident: str,
    weight: int,
    *,
    decidability=Decidability.DETERMINISTIC,
    applicability=Applicability.APPLICABLE,
) -> ResidualDiagnosticNeed:
    return ResidualDiagnosticNeed(
        ident,
        "claim-1",
        ident,
        "builtin.exact_match",
        weight,
        decidability,
        applicability,
        bindings(),
    )


class ResidualMetricTests(unittest.TestCase):
    def test_namespaces_are_separate_and_bindings_are_frozen(self) -> None:
        diagnostic = need("need-1", 2)
        capability = DiagnosticCapabilityRequirement("cap-1", "reasoning", bindings())
        self.assertEqual(diagnostic.namespace, RESIDUAL_DIAGNOSTIC_NEED_NAMESPACE)
        self.assertEqual(capability.namespace, DIAGNOSTIC_CAPABILITY_REQUIREMENT_NAMESPACE)
        self.assertNotEqual(diagnostic.namespace, capability.namespace)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            diagnostic.weight_units = 9  # type: ignore[misc]

    def test_weighted_and_unweighted_mass_are_complete_and_disjoint(self) -> None:
        rows = (
            need("pass", 4),
            need("fail", 3),
            need("unknown", 2),
            need("omitted", 5),
            need("undecidable", 7, decidability=Decidability.UNDECIDABLE),
            need("not-applicable", 11, applicability=Applicability.NOT_APPLICABLE),
        )
        metrics = summarize_metrics(
            rows,
            (
                CoverageContribution("pass", "1" * 64, ContributionOutcome.PASS, "passed"),
                CoverageContribution("fail", "2" * 64, ContributionOutcome.FAIL, "failed"),
                CoverageContribution(
                    "unknown", "3" * 64, ContributionOutcome.UNRESOLVED, "unknown"
                ),
            ),
        )
        self.assertEqual(
            (
                metrics.weighted.covered_mass,
                metrics.weighted.failed_mass,
                metrics.weighted.unresolved_mass,
                metrics.weighted.omitted_mass,
            ),
            (4, 3, 2, 5),
        )
        self.assertEqual(
            (
                metrics.covered_count,
                metrics.failed_count,
                metrics.unresolved_count,
                metrics.omitted_count,
            ),
            (1, 1, 1, 1),
        )
        self.assertEqual((metrics.undecidable_count, metrics.inapplicable_count), (1, 1))

    def test_closed_verifier_ids_and_positive_integer_weights_are_required(self) -> None:
        with self.assertRaises(KeyError):
            ResidualDiagnosticNeed(
                "need-1",
                "claim-1",
                "x",
                "custom.shell",
                1,
                Decidability.DETERMINISTIC,
                Applicability.APPLICABLE,
                bindings(),
            )
        with self.assertRaises(TypeError):
            need("need-1", True)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
