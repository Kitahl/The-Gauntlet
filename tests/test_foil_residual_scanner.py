from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import Applicability, Decidability, ImmutableBindings  # noqa: E402
from foil_residual_scanner import DiagnosticCase, ResidualScanPlan, scan  # noqa: E402
from foil_v5_metrics import NoAnswerCode, ResidualDiagnosticNeed, ScanStatus  # noqa: E402


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "abcde"])


def diagnostic(ident: str = "need-1", *, decidability=Decidability.DETERMINISTIC, applicability=Applicability.APPLICABLE) -> ResidualDiagnosticNeed:
    return ResidualDiagnosticNeed(ident, "claim-1", ident, "builtin.exact_match", 2, decidability, applicability, bindings())


def plan(*needs: ResidualDiagnosticNeed) -> ResidualScanPlan:
    return ResidualScanPlan("claim-1", bindings().a0_digest, bindings(), tuple(needs))


class ResidualScannerTests(unittest.TestCase):
    def test_pass_fail_and_unknown_are_typed_and_reasoned(self) -> None:
        ready = plan(diagnostic())
        passed = scan(ready, bindings().a0_digest, (DiagnosticCase("need-1", {"actual": "x", "expected": "x"}, {}),))
        failed = scan(ready, bindings().a0_digest, (DiagnosticCase("need-1", {"actual": "x", "expected": "y"}, {}),))
        unknown = scan(ready, bindings().a0_digest, ())
        self.assertEqual((passed.status, failed.status, unknown.status), (ScanStatus.PASS, ScanStatus.FAIL, ScanStatus.UNKNOWN))
        self.assertTrue(all(item.reason for item in (passed, failed, unknown)))
        self.assertEqual(unknown.no_answer.code, NoAnswerCode.MISSING_DIAGNOSTIC_CASE)  # type: ignore[union-attr]

    def test_not_applicable_and_undecidable_never_green(self) -> None:
        na = scan(plan(diagnostic(applicability=Applicability.NOT_APPLICABLE)), bindings().a0_digest, ())
        undecidable = scan(plan(diagnostic(decidability=Decidability.UNDECIDABLE)), bindings().a0_digest, ())
        self.assertEqual(na.status, ScanStatus.NOT_APPLICABLE)
        self.assertEqual(undecidable.status, ScanStatus.UNKNOWN)
        self.assertEqual(undecidable.no_answer.code, NoAnswerCode.UNDECIDABLE)  # type: ignore[union-attr]

    def test_scanner_digest_boundaries_require_canonical_lowercase_sha256(self) -> None:
        ready = plan(diagnostic())
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(field="plan", invalid=invalid), self.assertRaises(ValueError):
                ResidualScanPlan("claim-1", invalid, bindings(), (diagnostic(),))
            with self.subTest(field="observed", invalid=invalid), self.assertRaises(ValueError):
                scan(ready, invalid, ())

    def test_a0_and_answer_metadata_fail_closed(self) -> None:
        ready = plan(diagnostic())
        mismatch = scan(ready, "f" * 64, ())
        leaked = scan(ready, bindings().a0_digest, (DiagnosticCase("need-1", {"actual": "x", "expected": "x"}, {"gold_label": "x"}),))
        self.assertEqual(mismatch.no_answer.code, NoAnswerCode.A0_DIGEST_MISMATCH)  # type: ignore[union-attr]
        self.assertEqual(leaked.no_answer.code, NoAnswerCode.FORBIDDEN_METADATA)  # type: ignore[union-attr]
        self.assertEqual((mismatch.status, leaked.status), (ScanStatus.UNKNOWN, ScanStatus.UNKNOWN))


if __name__ == "__main__":
    unittest.main()
