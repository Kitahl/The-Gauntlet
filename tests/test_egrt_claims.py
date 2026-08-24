from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_claims import (  # noqa: E402
    Applicability,
    ClaimKind,
    ClaimOutcome,
    Decidability,
    ImmutableBindings,
    PostSolveObligation,
    compile_claim,
)


def bindings() -> ImmutableBindings:
    return ImmutableBindings(*[char * 64 for char in "abcde"])


class ClaimCompilerTests(unittest.TestCase):
    def test_compiles_only_when_axes_are_applicable_and_decidable(self) -> None:
        result = compile_claim(
            statement="1 + 1 = 2",
            kind=ClaimKind.EXACT_ARITHMETIC,
            decidability=Decidability.DETERMINISTIC,
            applicability=Applicability.APPLICABLE,
            bindings=bindings(),
            required_verifiers=("builtin.exact_arithmetic",),
            reason="the expression has a deterministic exact predicate",
        )
        self.assertEqual(result.outcome, ClaimOutcome.COMPILED)
        self.assertIsNotNone(result.claim)
        self.assertEqual(result.claim.namespace, "egr.post-solve.claim.v1")  # type: ignore[union-attr]
        self.assertEqual(result.claim.bindings.binding_digest, bindings().binding_digest)  # type: ignore[union-attr]

    def test_axes_are_orthogonal_and_every_noncompiled_outcome_has_reason(self) -> None:
        cases = (
            (Decidability.UNDECIDABLE, Applicability.APPLICABLE, ClaimOutcome.UNDECIDABLE),
            (Decidability.DETERMINISTIC, Applicability.NOT_APPLICABLE, ClaimOutcome.NOT_APPLICABLE),
            (Decidability.UNKNOWN, Applicability.APPLICABLE, ClaimOutcome.UNKNOWN),
            (Decidability.DETERMINISTIC, Applicability.UNKNOWN, ClaimOutcome.UNKNOWN),
        )
        for decidability, applicability, expected in cases:
            with self.subTest(decidability=decidability, applicability=applicability):
                result = compile_claim(
                    statement="claim",
                    kind=ClaimKind.OTHER,
                    decidability=decidability,
                    applicability=applicability,
                    bindings=bindings(),
                    reason="explicit classification reason",
                )
                self.assertEqual(result.outcome, expected)
                self.assertIsNone(result.claim)
                self.assertTrue(result.reason)

    def test_bindings_are_immutable_and_obligation_namespace_is_separate(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            bindings().a0_digest = "f" * 64  # type: ignore[misc]
        obligation = PostSolveObligation("obl-1", "claim-1", "exact result", 3)
        self.assertEqual(obligation.namespace, "egr.post-solve.obligation.v1")

    def test_external_binding_digests_must_be_canonical_lowercase_sha256(self) -> None:
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ImmutableBindings(invalid, *["b" * 64 for _ in range(4)])

    def test_empty_reason_and_noninteger_weight_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compile_claim(
                statement="claim",
                kind=ClaimKind.OTHER,
                decidability=Decidability.UNKNOWN,
                applicability=Applicability.APPLICABLE,
                bindings=bindings(),
                reason="",
            )
        with self.assertRaises(TypeError):
            PostSolveObligation("obl-1", "claim-1", "requirement", True)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
