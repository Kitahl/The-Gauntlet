from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from egrt_coverage import ContributionOutcome, CoverageContribution  # noqa: E402
from foil_v5_metrics import ResidualDiagnosticNeed, summarize_metrics  # noqa: E402
from foil_v5_score import (  # noqa: E402
    ActionOutcome,
    AdjudicatedObligation,
    UniverseEvidence,
    score_action_conditioned,
    score_adjudicated_compiler,
    score_declared_coverage,
)


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "abcde"])


class V5ScoreTests(unittest.TestCase):
    def test_declared_score_distinguishes_decidable_from_cleared_and_residual(self):
        needs = (
            ResidualDiagnosticNeed("a", "c", "a", "builtin.exact_match", 3, Decidability.DETERMINISTIC, Applicability.APPLICABLE, bindings()),
            ResidualDiagnosticNeed("b", "c", "b", "builtin.exact_match", 2, Decidability.SEMANTIC, Applicability.APPLICABLE, bindings()),
        )
        metrics = summarize_metrics(
            needs,
            (CoverageContribution("a", "f" * 64, ContributionOutcome.PASS, "pass"),),
        )
        score = score_declared_coverage(metrics)
        self.assertEqual(score.evidence, UniverseEvidence.DECLARED_ONLY)
        self.assertEqual(score.decidable_coverage, 0.6)
        self.assertEqual(score.mechanically_cleared_coverage, 0.6)
        # SEMANTIC evidence is material but outside deterministic claim coverage.
        self.assertEqual(score.material_weight, 5)

    def test_adjudicated_compiler_score_exposes_omission_and_false_extraction(self):
        score = score_adjudicated_compiler(
            (
                AdjudicatedObligation("a", 4, True, True, True),
                AdjudicatedObligation("b", 3, False, False, False),
                AdjudicatedObligation("c", 3, True, False, False),
            )
        )
        self.assertEqual(score.compiler_coverage, 0.4)
        self.assertEqual(score.compiler_precision, 4 / 7)
        self.assertEqual(score.weighted_decidable_coverage, 0.4)

    def test_flag_and_action_denominators_remain_separate(self):
        score = score_action_conditioned(
            (
                ActionOutcome(False, True, True, True),
                ActionOutcome(False, True, False, False),
                ActionOutcome(True, True, True, False),
                ActionOutcome(True, False, False, True),
            )
        )
        self.assertEqual(score.r_flag, 1.0)
        self.assertEqual(score.alpha_flag, 0.5)
        self.assertEqual(score.r_act, 0.5)
        self.assertEqual(score.alpha_act, 0.5)
        self.assertEqual(score.u_act, 1.0)
        self.assertEqual(score.d_act, 1.0)


if __name__ == "__main__":
    unittest.main()
