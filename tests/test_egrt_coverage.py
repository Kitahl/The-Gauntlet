from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, PostSolveObligation  # noqa: E402
from egrt_coverage import (  # noqa: E402
    ContributionOutcome,
    CoverageContribution,
    CoverageRequirement,
    summarize_coverage,
)


def requirement(ident: str, weight: int, *, decidability=Decidability.DETERMINISTIC, applicability=Applicability.APPLICABLE):
    return CoverageRequirement(PostSolveObligation(ident, "claim-1", ident, weight), decidability, applicability)


class CoverageTests(unittest.TestCase):
    def test_weighted_decidable_coverage_accounts_for_every_mass(self) -> None:
        rows = (
            requirement("one", 4),
            requirement("two", 3),
            requirement("three", 2),
            requirement("four", 5),
            requirement("five", 7, decidability=Decidability.UNDECIDABLE),
            requirement("six", 11, applicability=Applicability.NOT_APPLICABLE),
        )
        summary = summarize_coverage(
            rows,
            (
                CoverageContribution("one", "a" * 64, ContributionOutcome.PASS, "passed"),
                CoverageContribution("two", "b" * 64, ContributionOutcome.FAIL, "failed"),
                CoverageContribution("three", "c" * 64, ContributionOutcome.UNRESOLVED, "unknown"),
            ),
        )
        self.assertEqual(summary.decidable_mass, 14)
        self.assertEqual(summary.covered_mass, 4)
        self.assertEqual(summary.failed_mass, 3)
        self.assertEqual(summary.unresolved_mass, 2)
        self.assertEqual(summary.omitted_mass, 5)
        self.assertEqual(summary.undecidable_mass, 7)
        self.assertEqual(summary.inapplicable_mass, 11)
        self.assertFalse(summary.complete)

    def test_complete_means_all_decidable_weight_passed(self) -> None:
        summary = summarize_coverage(
            (requirement("one", 2), requirement("two", 3)),
            (
                CoverageContribution("one", "a" * 64, ContributionOutcome.PASS, "passed"),
                CoverageContribution("two", "b" * 64, ContributionOutcome.PASS, "passed"),
            ),
        )
        self.assertTrue(summary.complete)

    def test_external_evidence_digests_must_be_canonical_lowercase_sha256(self) -> None:
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CoverageContribution("one", invalid, ContributionOutcome.PASS, "passed")

    def test_evidence_and_obligation_cannot_be_double_counted(self) -> None:
        rows = (requirement("one", 1), requirement("two", 1))
        with self.assertRaises(ValueError):
            summarize_coverage(
                rows,
                (
                    CoverageContribution("one", "a" * 64, ContributionOutcome.PASS, "passed"),
                    CoverageContribution("two", "a" * 64, ContributionOutcome.PASS, "copied"),
                ),
            )
        with self.assertRaises(ValueError):
            summarize_coverage(
                rows,
                (
                    CoverageContribution("one", "a" * 64, ContributionOutcome.PASS, "passed"),
                    CoverageContribution("one", "b" * 64, ContributionOutcome.PASS, "again"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
