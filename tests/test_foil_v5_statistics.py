"""Tests for base-item-clustered FOIL v5 Gate-1 descriptive statistics."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_v5_statistics import (  # noqa: E402
    ClusterObservation,
    cluster_base_items,
    residual_rates,
    wilson_interval,
)


def observation(
    item_id: str,
    base_item_id: str,
    *,
    domain: str = "math",
    base_correct: bool,
    flagged: bool,
    status: str = "PASS",
    no_answer_code: str | None = None,
) -> ClusterObservation:
    return ClusterObservation(
        item_id, base_item_id, domain, base_correct, flagged, status, no_answer_code
    )


class GateOneStatisticsTests(unittest.TestCase):
    def test_wilson_interval_declares_confidence_and_handles_zero_denominator(self) -> None:
        empty = wilson_interval(0, 0, confidence=0.9)
        complete = wilson_interval(1, 1, confidence=0.9)
        self.assertEqual(empty.confidence, 0.9)
        self.assertIsNone(empty.estimate)
        self.assertEqual(complete.estimate, 1.0)
        self.assertLess(complete.lower, complete.upper)

    def test_mutants_collapse_to_one_base_item_before_rates(self) -> None:
        rows = (
            observation("wrong-1", "base-wrong", base_correct=False, flagged=False),
            observation("wrong-1-mutant", "base-wrong", base_correct=False, flagged=True),
            observation("right-1", "base-right", base_correct=True, flagged=False),
        )
        clustered = cluster_base_items(rows)
        rates = residual_rates(rows)
        self.assertEqual(len(clustered), 2)
        self.assertEqual(rates.raw_rows, 3)
        self.assertEqual(rates.clusters, 2)
        self.assertEqual(rates.residual_recall.successes, 1)
        self.assertEqual(rates.residual_recall.total, 1)
        self.assertEqual(rates.false_positive_rate.successes, 0)
        self.assertEqual(rates.positive_predictive_value.estimate, 1.0)

    def test_mixed_correctness_or_domain_in_a_cluster_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "share domain and base correctness"):
            cluster_base_items(
                (
                    observation("x1", "base", base_correct=True, flagged=False),
                    observation("x2", "base", base_correct=False, flagged=False),
                )
            )

    def test_unknown_and_no_answer_counts_remain_visible(self) -> None:
        rates = residual_rates(
            (
                observation(
                    "x1",
                    "base",
                    base_correct=True,
                    flagged=False,
                    status="UNKNOWN",
                    no_answer_code="VERIFIER_UNKNOWN",
                ),
            )
        )
        self.assertEqual(dict(rates.status_counts), {"UNKNOWN": 1})
        self.assertEqual(dict(rates.no_answer_counts), {"VERIFIER_UNKNOWN": 1})


if __name__ == "__main__":
    unittest.main()
