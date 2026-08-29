from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_formal_decidability import (  # noqa: E402
    derive_formal_decidability_proof,
    validate_formal_decidability_payload,
)


K_QUESTION = """Fix any primitive recursive programming language P and consider the following function:

K(n) is the length of the shortest P-program that outputs n.

Is K(n) computable? """


class FormalDecidabilityTests(unittest.TestCase):
    def test_real_k_question_gets_closed_yes_proof(self) -> None:
        proof = derive_formal_decidability_proof(K_QUESTION)
        self.assertIsNotNone(proof)
        assert proof is not None
        self.assertEqual(proof.conclusion, "Yes")
        self.assertEqual(
            validate_formal_decidability_payload(K_QUESTION, "Yes", proof.payload),
            proof,
        )

    def test_generalized_total_language_wording(self) -> None:
        question = (
            "In a total programming language where every valid program terminates, "
            "let D(x) be the minimum length program that returns x. Is D computable?"
        )
        self.assertIsNotNone(derive_formal_decidability_proof(question))

    def test_partial_or_unstated_totality_declines(self) -> None:
        partial = (
            "In a Turing-complete programming language, let K(n) be the length of "
            "the shortest program that outputs n. Is K computable?"
        )
        unstated = "Let K(n) be the shortest program that outputs n. Is K computable?"
        self.assertIsNone(derive_formal_decidability_proof(partial))
        self.assertIsNone(derive_formal_decidability_proof(unstated))

    def test_payload_tampering_and_unknown_fields_fail_closed(self) -> None:
        proof = derive_formal_decidability_proof(K_QUESTION)
        assert proof is not None
        raw = proof.body()
        raw["conclusion"] = "No"
        tampered = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        with self.assertRaises(ValueError):
            validate_formal_decidability_payload(K_QUESTION, "Yes", tampered)
        raw = proof.body()
        raw["extra"] = True
        unknown = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        with self.assertRaises(ValueError):
            validate_formal_decidability_payload(K_QUESTION, "Yes", unknown)


if __name__ == "__main__":
    unittest.main()
