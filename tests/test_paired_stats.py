"""Checks for `benchmarks/harness/paired_stats.py` against hand computation.

Every expected value here is derivable with a calculator from Binomial(n, 1/2),
so the tests are a control on the implementation rather than a snapshot of it.
Where a value would be tedious to write out (Wilson), the test carries the
closed-form arithmetic alongside the literal, so a future edit cannot make both
agree by accident.
"""
from __future__ import annotations

import sys
import unittest
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import paired_stats as ps  # noqa: E402


def point_method_p(b: int, c: int) -> float:
    """The other standard two-sided exact construction, for cross-checking.

    "Sum the probability of every outcome at most as probable as the observed
    one." Under a symmetric null this must equal the doubling construction the
    module uses; if it ever does not, one of the two is wrong.
    """
    n = b + c
    if n == 0:
        return 1.0
    observed = comb(n, min(b, c)) * 0.5 ** n
    return min(1.0, sum(comb(n, i) * 0.5 ** n for i in range(n + 1)
                        if comb(n, i) * 0.5 ** n <= observed + 1e-15))


class ExactMcNemarTests(unittest.TestCase):
    def test_known_values(self) -> None:
        # n = 7 discordant, k = 1: 2 * (C(7,0) + C(7,1)) / 2^7 = 16/128
        self.assertEqual(ps.exact_mcnemar(6, 1), 0.125)
        # n = 8 discordant, k = 0: 2 * C(8,0) / 2^8 = 2/256
        self.assertEqual(ps.exact_mcnemar(8, 0), 0.0078125)

    def test_is_symmetric_in_its_arguments(self) -> None:
        for b in range(0, 9):
            for c in range(0, 9):
                self.assertEqual(ps.exact_mcnemar(b, c), ps.exact_mcnemar(c, b), (b, c))

    def test_matches_the_point_probability_construction(self) -> None:
        for b in range(0, 11):
            for c in range(0, 11):
                self.assertAlmostEqual(ps.exact_mcnemar(b, c), point_method_p(b, c),
                                       places=12, msg=f"b={b} c={c}")

    def test_equal_counts_and_no_discordance_return_one(self) -> None:
        self.assertEqual(ps.exact_mcnemar(0, 0), 1.0)
        for k in range(1, 6):
            self.assertEqual(ps.exact_mcnemar(k, k), 1.0)

    def test_five_discordant_pairs_cannot_reach_alpha(self) -> None:
        # The resolvability floor the protocol cites: at n = 5 the best attainable
        # two-sided p is 0.0625, so no split of five pairs can reject at 0.05.
        self.assertEqual(ps.exact_mcnemar(5, 0), 0.0625)
        self.assertEqual(ps.exact_mcnemar(6, 0), 0.03125)

    def test_negative_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ps.exact_mcnemar(-1, 3)


class MidPMcNemarTests(unittest.TestCase):
    def test_known_values_from_the_binomial(self) -> None:
        # n = 7, k = 1: 2 * (P(X=0) + 0.5 * P(X=1)) = 2 * (1/128 + 3.5/128) = 9/128
        self.assertEqual(ps.midp_mcnemar(6, 1), 9 / 128)
        # n = 8, k = 0: 2 * (0 + 0.5 * 1/256) = 1/256
        self.assertEqual(ps.midp_mcnemar(8, 0), 1 / 256)

    def test_equals_the_binomial_definition(self) -> None:
        """`2 * (P(X < k) + 0.5 * P(X = k))`, recomputed here from first principles.

        The identity "mid-p = exact - point mass" only holds on the *uncapped*
        exact value, so the control is built from the binomial rather than from
        `exact_mcnemar`, which caps at 1.
        """
        for b in range(0, 11):
            for c in range(0, 11):
                n, k = b + c, min(b, c)
                if n == 0:
                    continue
                below = sum(comb(n, i) * 0.5 ** n for i in range(k))
                expected = min(1.0, 2.0 * (below + 0.5 * comb(n, k) * 0.5 ** n))
                self.assertAlmostEqual(ps.midp_mcnemar(b, c), expected, places=12,
                                       msg=f"b={b} c={c}")

    def test_is_never_more_conservative_than_exact(self) -> None:
        for b in range(0, 13):
            for c in range(0, 13):
                self.assertLessEqual(ps.midp_mcnemar(b, c), ps.exact_mcnemar(b, c) + 1e-15,
                                     f"b={b} c={c}")

    def test_balanced_and_empty_tables_return_one(self) -> None:
        self.assertEqual(ps.midp_mcnemar(0, 0), 1.0)
        self.assertEqual(ps.midp_mcnemar(4, 4), 1.0)


class WilsonIntervalTests(unittest.TestCase):
    def test_twenty_of_twentyfour(self) -> None:
        low, high = ps.wilson_interval(20, 24)
        self.assertAlmostEqual(low, 0.6414692935030095, places=12)
        self.assertAlmostEqual(high, 0.9332132367136705, places=12)

    def test_matches_the_closed_form(self) -> None:
        from statistics import NormalDist

        z = NormalDist().inv_cdf(0.975)
        for successes, n in ((0, 12), (7, 12), (12, 12), (20, 24), (1, 100)):
            p, c = successes / n, z * z / n
            centre = (p + c / 2) / (1 + c)
            half = (z / (1 + c)) * ((p * (1 - p) / n + c / (4 * n)) ** 0.5)
            low, high = ps.wilson_interval(successes, n)
            self.assertAlmostEqual(low, max(0.0, centre - half), places=12)
            self.assertAlmostEqual(high, min(1.0, centre + half), places=12)

    def test_boundary_cells_do_not_collapse(self) -> None:
        # The reason Wilson is used rather than Wald: Wald gives a zero-width
        # interval at 0/n and n/n, which a small benchmark reaches routinely.
        for successes, n in ((0, 12), (12, 12), (0, 24), (24, 24)):
            low, high = ps.wilson_interval(successes, n)
            self.assertGreater(high - low, 0.0, (successes, n))
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 1.0)

    def test_zero_denominator_is_the_whole_unit_interval(self) -> None:
        self.assertEqual(ps.wilson_interval(0, 0), (0.0, 1.0))

    def test_impossible_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ps.wilson_interval(5, 4)


class HolmTests(unittest.TestCase):
    def test_known_family_of_four(self) -> None:
        self.assertEqual(ps.holm_adjust([0.01, 0.04, 0.03, 0.5]), [0.04, 0.09, 0.09, 0.5])

    def test_adjusted_values_are_monotone_in_the_raw_order(self) -> None:
        raw = [0.001, 0.2, 0.02, 0.049]
        adjusted = ps.holm_adjust(raw)
        by_rank = [adjusted[i] for i in sorted(range(len(raw)), key=lambda i: raw[i])]
        self.assertEqual(by_rank, sorted(by_rank))

    def test_never_reduces_a_p_value_and_never_exceeds_one(self) -> None:
        raw = [0.4, 0.6, 0.9, 0.95]
        for original, adjusted in zip(raw, ps.holm_adjust(raw)):
            self.assertGreaterEqual(adjusted, original)
            self.assertLessEqual(adjusted, 1.0)

    def test_single_hypothesis_is_unchanged_and_empty_is_empty(self) -> None:
        self.assertEqual(ps.holm_adjust([0.031]), [0.031])
        self.assertEqual(ps.holm_adjust([]), [])

    def test_out_of_range_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ps.holm_adjust([0.5, 1.5])


class DiscordanceAndReportTests(unittest.TestCase):
    def test_table_counts_all_four_cells(self) -> None:
        table = ps.discordance([(True, True), (True, False), (False, True), (False, False),
                                (True, False)])
        self.assertEqual(table, {"both_correct": 1, "first_only": 2, "second_only": 1,
                                 "both_wrong": 1, "n": 5, "discordant": 3})

    def test_report_names_primary_and_sensitivity_and_matches_the_functions(self) -> None:
        pairs = [(True, False)] * 6 + [(False, True)] * 1 + [(True, True)] * 10
        report = ps.paired_report(pairs, first_label="BASE", second_label="FOIL")
        self.assertEqual(report["arms"], {"first": "BASE", "second": "FOIL"})
        self.assertEqual(report["discordance"]["first_only"], 6)
        self.assertEqual(report["discordance"]["second_only"], 1)
        self.assertEqual(report["sensitivity_test"]["p_value"], 0.125)
        self.assertEqual(report["primary_test"]["p_value"], 9 / 128)
        self.assertIn("mid-p", report["primary_test"]["name"])
        self.assertIn("exact", report["sensitivity_test"]["name"])
        self.assertEqual(report["arm_accuracy"]["BASE"]["correct"], 16)
        self.assertEqual(report["arm_accuracy"]["FOIL"]["correct"], 11)

    def test_no_discordance_reports_one_and_says_why_that_is_not_equivalence(self) -> None:
        report = ps.paired_report([(True, True), (False, False)])
        self.assertEqual(report["primary_test"]["p_value"], 1.0)
        self.assertIn("absence of evidence", report["interpretation_limit"])


if __name__ == "__main__":
    unittest.main()
