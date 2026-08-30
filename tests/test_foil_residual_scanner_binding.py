from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, scan  # noqa: E402
from foil_v5_metrics import ResidualDiagnosticNeed  # noqa: E402


class ScannerBindingTests(unittest.TestCase):
    def test_receipt_digest_changes_when_verifier_input_changes(self):
        bindings = ImmutableBindings(*[char * 64 for char in "abcde"])
        need = ResidualDiagnosticNeed(
            "need",
            "claim",
            "exact value",
            "builtin.exact_match",
            1,
            Decidability.DETERMINISTIC,
            Applicability.APPLICABLE,
            bindings,
        )
        plan = ResidualScanPlan("claim", bindings.a0_digest, bindings, (need,))
        first = scan(
            plan,
            bindings.a0_digest,
            (DiagnosticCase("need", {"actual": "x", "expected": "x"}, {}),),
        )
        second = scan(
            plan,
            bindings.a0_digest,
            (DiagnosticCase("need", {"actual": "x", "expected": "y"}, {}),),
        )
        self.assertNotEqual(first.input_digest, second.input_digest)


if __name__ == "__main__":
    unittest.main()
