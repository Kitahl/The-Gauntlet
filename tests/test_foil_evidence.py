"""Regression tests for the shared FOIL evidence estimator.

Where the input domain is small enough these tests enumerate it exhaustively
rather than sampling: for a finite domain, exhaustive enumeration is a proof.
"""
from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_evidence as ev  # noqa: E402


def obs(correct: int, incorrect: int, tier: ev.EvidenceTier = ev.EvidenceTier.REAL_WORK):
    return [ev.Observation(True, tier)] * correct + [ev.Observation(False, tier)] * incorrect


class EvidenceEstimatorTests(unittest.TestCase):
    """D1, D2 - the classifier."""

    def test_incomplete_beta_matches_closed_form(self):
        # I_x(2, 3) = x^2 (6 - 8x + 3x^2); an independent closed form.
        for x in (0.05, 0.25, 0.5, 0.75, 0.95):
            expected = x ** 2 * (6 - 8 * x + 3 * x ** 2)
            self.assertAlmostEqual(ev.regularized_incomplete_beta(2, 3, x), expected, places=10)

    def test_posterior_tail_is_monotone_exhaustively(self):
        """P(theta > theta_hi) rises with every correct observation and falls with
        every incorrect one, over the full 0..24 x 0..24 grid."""
        tail = {
            (c, i): ev.summarize(obs(c, i)).p_above_hi
            for c in range(25)
            for i in range(25)
        }
        for c in range(24):
            for i in range(25):
                self.assertGreaterEqual(tail[(c + 1, i)], tail[(c, i)] - 1e-12,
                                        f"a correct observation lowered P(theta>hi) at c={c}, i={i}")
        for c in range(25):
            for i in range(24):
                self.assertLessEqual(tail[(c, i + 1)], tail[(c, i)] + 1e-12,
                                     f"an incorrect observation raised P(theta>hi) at c={c}, i={i}")

    def test_classification_direction_is_monotone_exhaustively(self):
        """No correct observation can create or preserve a gap verdict where the
        verdict was a strength, and no incorrect observation can create a strength.

        Deliberately not asserted: that adding an observation cannot move
        INSUFFICIENT_EVIDENCE to a decided state in either direction. Crossing
        the evidence threshold is what licenses a verdict at all, so evidence
        sufficiency and competence direction are separate axes.
        """
        C = ev.Classification
        for c in range(25):
            for i in range(25):
                here = ev.classify(obs(c, i))
                if here is C.PROMISING_STRENGTH:
                    self.assertIsNot(ev.classify(obs(c + 1, i)), C.POSSIBLE_GAP,
                                     f"a correct observation flipped strength to gap at c={c}, i={i}")
                if here is C.POSSIBLE_GAP:
                    self.assertIsNot(ev.classify(obs(c, i + 1)), C.PROMISING_STRENGTH,
                                     f"an incorrect observation flipped gap to strength at c={c}, i={i}")
                if here is not C.PROMISING_STRENGTH:
                    self.assertIsNot(ev.classify(obs(c, i + 1)), C.PROMISING_STRENGTH,
                                     f"an incorrect observation created a strength at c={c}, i={i}")

    def test_v1_counterexample_now_classifies_as_strength(self):
        """v1 returned UNCERTAIN for 20 correct and 1 incorrect."""
        self.assertEqual(ev.classify(obs(20, 1)), ev.Classification.PROMISING_STRENGTH)
        self.assertEqual(ev.classify(obs(40, 2)), ev.Classification.PROMISING_STRENGTH)

    def test_screen_evidence_alone_is_never_load_bearing(self):
        for k in range(1, 21):
            self.assertFalse(
                ev.classify(obs(k, 0, ev.EvidenceTier.SCREEN)).is_load_bearing,
                f"{k} all-correct screen items produced a load-bearing state",
            )
            self.assertFalse(ev.classify(obs(0, k, ev.EvidenceTier.SCREEN)).is_load_bearing)

    def test_assisted_and_unverified_evidence_carry_zero_weight(self):
        for tier in (ev.EvidenceTier.ASSISTED, ev.EvidenceTier.UNVERIFIED):
            summary = ev.summarize(obs(50, 0, tier))
            self.assertEqual(summary.effective_n, 0.0)
            self.assertEqual(summary.classification, ev.Classification.INSUFFICIENT_EVIDENCE)

    def test_two_observations_cannot_reach_a_load_bearing_state(self):
        """D2: the v1 two-observation gate is closed."""
        for c, i in ((2, 0), (0, 2), (1, 1)):
            self.assertFalse(ev.classify(obs(c, i)).is_load_bearing)

    def test_four_fresh_observations_decide_deterministically(self):
        """The sufficiency gate must not be decided by sub-microsecond timing.

        Fresh observations decay by an epsilon against `now`, so exactly
        `min_effective_n` of them weigh a ULP under the threshold. Repeat the
        call to show the verdict does not flicker.
        """
        now = datetime.now(timezone.utc)
        rows = [ev.Observation(True, time=now - timedelta(microseconds=1)) for _ in range(4)]
        for _ in range(25):
            self.assertEqual(
                ev.classify(rows, now=datetime.now(timezone.utc)),
                ev.Classification.PROMISING_STRENGTH,
            )

    def test_false_rates_are_reported_and_bounded(self):
        rates = ev.false_classification_rates(8, 0.90)
        self.assertLess(rates["false_gap"], 0.01)
        self.assertLess(ev.false_classification_rates(8, 0.30)["false_strength"], 0.01)

    def test_item_calculator_requires_detection_power(self):
        """A classifier that never decides is never wrong; the calculator must not
        reward that with k = 1."""
        result = ev.items_for_target_error(0.02, 0.95, 0.20, detection_power=0.80, max_k=40)
        self.assertIsNotNone(result["k"])
        self.assertGreater(result["k"], 1)
        self.assertIsNone(result["reason"])

    def test_item_calculator_reports_non_convergence_instead_of_faking_it(self):
        """With the module's own defaults no admissible k exists.

        The honest answer is `k: None` plus what was actually achieved, not a
        number that would license a screen length nothing supports.
        """
        for target in (0.02, 0.05):
            result = ev.items_for_target_error(target)
            self.assertIsNone(result["k"], target)
            for key in ("reason", "best_achieved_power", "best_k_for_power"):
                self.assertIn(key, result)
            self.assertIn("no k in 1..60", result["reason"])
            self.assertLess(result["best_achieved_power"], 0.80)
            self.assertIsInstance(result["best_k_for_power"], int)


class SprtCrossCheckTests(unittest.TestCase):
    """The SPRT is a diagnostic second opinion, never the routed classifier."""

    def test_log_likelihood_ratio_matches_the_closed_form(self):
        llr = ev.sprt_log_likelihood_ratio(20, 1)
        expected = 20 * math.log(0.8 / 0.4) + 1 * math.log(0.2 / 0.6)
        self.assertAlmostEqual(llr, expected, places=12)
        self.assertAlmostEqual(llr, 12.764331, places=6)

    def test_boundaries_are_walds(self):
        upper, lower = ev.sprt_boundaries()
        self.assertAlmostEqual(upper, math.log(19.0), places=12)
        self.assertAlmostEqual(lower, math.log(0.05 / 0.95), places=12)

    def test_v1_counterexample_crosses_the_upper_boundary(self):
        upper, _ = ev.sprt_boundaries()
        self.assertGreaterEqual(ev.sprt_log_likelihood_ratio(20, 1), upper)
        self.assertEqual(ev.sprt_decision(20, 1), "PROMISING_STRENGTH")

    def test_undecided_and_gap_directions(self):
        self.assertEqual(ev.sprt_decision(0, 0), "UNCERTAIN")
        self.assertEqual(ev.sprt_decision(1, 1), "UNCERTAIN")
        self.assertEqual(ev.sprt_decision(0, 8), "POSSIBLE_GAP")

    def test_it_is_not_the_classifier(self):
        """Two verified passes satisfy no evidence gate, yet the SPRT alone would
        already be leaning. That divergence is the point: the diagnostic is not
        allowed to decide."""
        self.assertEqual(ev.classify(obs(2, 0)), ev.Classification.INSUFFICIENT_EVIDENCE)
        self.assertGreater(ev.sprt_log_likelihood_ratio(2, 0), 0.0)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            ev.sprt_log_likelihood_ratio(-1, 0)
        with self.assertRaises(ValueError):
            ev.sprt_log_likelihood_ratio(1, 0, p_lo=0.0)
        with self.assertRaises(ValueError):
            ev.sprt_boundaries(alpha=0.0)


class RecencyTests(unittest.TestCase):
    """D4 - later verified evidence outranks stale evidence."""

    def test_recent_failures_supersede_old_passes(self):
        now = datetime.now(timezone.utc)
        old = [ev.Observation(True, time=now - timedelta(days=900))] * 8
        recent = [ev.Observation(False, time=now - timedelta(days=1))] * 6
        self.assertEqual(ev.classify(old + recent, now=now), ev.Classification.POSSIBLE_GAP)

    def test_history_is_never_erased_only_downweighted(self):
        now = datetime.now(timezone.utc)
        old = [ev.Observation(True, time=now - timedelta(days=3650))] * 10
        summary = ev.summarize(old, now=now)
        self.assertGreater(summary.effective_correct, 0.0)
        self.assertLess(summary.effective_correct, 10.0)


class DecayFloorTests(unittest.TestCase):
    """Evidence at the decay floor cannot decide, in either direction.

    Boundary, stated rather than hidden: `min_weight` is a floor, not a cutoff,
    so `min_weight * N` still crosses `min_effective_n` once N >= 80 at the
    defaults. These tests therefore cap N at 20, which is the regime the claim
    "fully decayed evidence cannot decide" actually holds in. The estimator
    docstring names the same boundary.
    """

    HALF_LIVES = 10
    N = 20

    def _aged(self, correct: bool):
        now = datetime.now(timezone.utc)
        policy = ev.EvidencePolicy()
        age = timedelta(days=policy.half_life_days * self.HALF_LIVES)
        rows = [ev.Observation(correct, time=now - age) for _ in range(self.N)]
        return rows, now, policy

    def test_weight_is_actually_at_the_floor(self):
        rows, now, policy = self._aged(True)
        summary = ev.summarize(rows, policy, now=now)
        self.assertAlmostEqual(summary.effective_correct, policy.min_weight * self.N, places=9)
        self.assertLess(policy.min_weight * self.N, policy.min_effective_n)

    def test_all_old_passes_are_insufficient_not_a_strength(self):
        rows, now, policy = self._aged(True)
        self.assertEqual(ev.classify(rows, policy, now=now),
                         ev.Classification.INSUFFICIENT_EVIDENCE)

    def test_all_old_failures_are_insufficient_not_a_gap(self):
        rows, now, policy = self._aged(False)
        self.assertEqual(ev.classify(rows, policy, now=now),
                         ev.Classification.INSUFFICIENT_EVIDENCE)


class PolicyValidationTests(unittest.TestCase):
    def test_incoherent_policies_are_rejected(self):
        for kwargs in (
            {"theta_lo": 0.9, "theta_hi": 0.5},
            {"confidence": 0.2},
            {"prior_a": 0.0},
            {"half_life_days": -1.0},
            {"min_weight": 1.5},
        ):
            with self.assertRaises(ValueError, msg=kwargs):
                ev.EvidencePolicy(**kwargs)

    def test_naive_observation_times_are_rejected(self):
        with self.assertRaises(ValueError):
            ev.Observation(True, time=datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
