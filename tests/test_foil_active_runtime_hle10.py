from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_active_runtime_hle10 as harness  # noqa: E402
from foil_active_runtime_hle10_common import A0_SCHEMA, usage_from  # noqa: E402
from foil_active_runtime_hle10_score import bounded_normalized_correct  # noqa: E402


class ActiveRuntimeHLE10Tests(unittest.TestCase):
    def test_prepare_question_projection_cannot_read_gold_columns(self) -> None:
        source = inspect.getsource(harness._question_rows)
        self.assertIn('["id", "Verified_Classes", "category", "question"]', source)
        self.assertNotIn('"answer"', source)
        self.assertNotIn('"json"', source)

    def test_exposure_id_regex_is_bounded(self) -> None:
        self.assertEqual(harness._ids_in_bytes(b'x 66eaa401c7a3252f0f3fe535 y'), {"66eaa401c7a3252f0f3fe535"})
        self.assertEqual(harness._ids_in_bytes(b'a' + b'1' * 64 + b'z'), set())

    def test_a0_schema_has_no_artificial_length_cap(self) -> None:
        schema = json.loads(A0_SCHEMA.read_text(encoding="utf-8"))
        self.assertNotIn("maxLength", schema["properties"]["answer"])

    def test_missing_usage_is_none_not_zero(self) -> None:
        self.assertIsNone(usage_from(None))
        self.assertIsNone(usage_from({"input_tokens": 1, "output_tokens": 2}))
        self.assertEqual(
            usage_from({"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}),
            {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )

    def test_policy_keeps_semantic_authority_unadmitted(self) -> None:
        policy = harness._route_policy()
        self.assertTrue(policy.answer_change_enabled)
        self.assertFalse(policy.comparator.semantic_enabled)
        self.assertFalse(policy.comparator.semantic_route_admitted)
        self.assertIsNone(policy.constructor.maximum_output_tokens)

    def test_bounded_normalization_accepts_formatting_only(self) -> None:
        self.assertTrue(bounded_normalized_correct("(1, 2)", "(1,2)"))
        self.assertTrue(bounded_normalized_correct("The final answer is (1, 2).", "(1,2)"))
        self.assertTrue(bounded_normalized_correct("The answer is B.", "B"))

    def test_bounded_normalization_rejects_contradictory_answers(self) -> None:
        self.assertFalse(bounded_normalized_correct("The answer is A or B.", "B"))
        self.assertFalse(bounded_normalized_correct("Answer: (1, 2), but also (3, 4).", "(1,2)"))
        self.assertFalse(bounded_normalized_correct("The final answer is 3, not 4.", "3"))


if __name__ == "__main__":
    unittest.main()
