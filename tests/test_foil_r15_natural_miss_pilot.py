from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_r15_natural_miss_pilot import (  # noqa: E402
    PROTOCOL,
    PROTOCOL_SHA256,
    ReplayRecord,
    _association,
    _mutant,
    _scan,
    evaluate_records,
)
from foil_v5_pipeline import PipelineStatus  # noqa: E402

COMMIT = "1" * 40


def gpqa(item_id: str, actual: str, expected: str) -> ReplayRecord:
    return ReplayRecord(
        item_id=item_id,
        domain="GPQA_DIAMOND",
        operator_id="GPQA_CHOICE_SUBSTITUTION",
        verifier_id="builtin.exact_match",
        predicate_kind="EXACT_MATCH",
        claim_kind="EXACT_MATCH",
        actual=actual,
        expected=expected,
    )


def arc(item_id: str, actual: object, expected: object) -> ReplayRecord:
    return ReplayRecord(
        item_id=item_id,
        domain="ARC_AGI_1",
        operator_id="ARC_CELL_SUBSTITUTION",
        verifier_id="builtin.json_exact",
        predicate_kind="JSON",
        claim_kind="JSON",
        actual=actual,
        expected=expected,
    )


class R15NaturalMissPilotTests(unittest.TestCase):
    def test_protocol_freezes_nine_miss_positive_control_and_zero_model_cost(self) -> None:
        self.assertEqual(PROTOCOL["expected_historical"]["natural_misses"], 9)
        self.assertEqual(PROTOCOL["expected_historical"]["pooled_correct"], 27)
        self.assertEqual(PROTOCOL["expected_historical"]["pooled_n"], 36)
        self.assertEqual(PROTOCOL["provider_calls_allowed"], 0)
        self.assertEqual(PROTOCOL["external_bots_allowed"], 0)
        self.assertEqual(PROTOCOL["token_spend_allowed"], 0)
        self.assertEqual(len(PROTOCOL_SHA256), 64)

    def test_real_pipeline_clears_gold_and_detects_wrong_a0_without_mutation(self) -> None:
        record = gpqa("gpqa-test", "B", "A")
        wrong_status, wrong_preserved = _scan(record, record.actual)
        clear_status, clear_preserved = _scan(record, record.expected)
        self.assertIs(wrong_status, PipelineStatus.DEFECT)
        self.assertIs(clear_status, PipelineStatus.CLEARED)
        self.assertTrue(wrong_preserved)
        self.assertTrue(clear_preserved)

    def test_mutants_are_valid_and_non_equivalent(self) -> None:
        gpqa_record = gpqa("gpqa-test", "A", "A")
        arc_record = arc("arc-test", [[1, 2]], [[1, 2]])
        self.assertNotEqual(_mutant(gpqa_record), gpqa_record.expected)
        self.assertNotEqual(_mutant(arc_record), arc_record.expected)

    def test_association_fails_closed_with_two_constant_rate_classes(self) -> None:
        mutation = [
            {"operator_id": "A", "rate": 1.0},
            {"operator_id": "B", "rate": 1.0},
        ]
        natural = [
            {"operator_id": "A", "rate": 1.0},
            {"operator_id": "B", "rate": 1.0},
        ]
        result = _association(mutation, natural)
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        self.assertIn("INSUFFICIENT_COMMON_OPERATOR_CLASSES", result["reason_codes"])
        self.assertIn("ZERO_VARIANCE_MUTATION_RATE", result["reason_codes"])
        self.assertIn("ZERO_VARIANCE_NATURAL_RATE", result["reason_codes"])
        self.assertIsNone(result["pearson"])
        self.assertIsNone(result["spearman"])

    def test_small_synthetic_replay_is_oracle_bound_and_non_promoting(self) -> None:
        records = [
            gpqa("gpqa-good", "A", "A"),
            gpqa("gpqa-bad", "B", "A"),
            arc("arc-bad", [[1]], [[2]]),
        ]
        report = evaluate_records(
            records,
            protocol_commit=COMMIT,
            source_sha256={"arc_archive": "a" * 64, "gpqa_archive": "b" * 64},
            enforce_historical_control=False,
        )
        self.assertEqual(report["classification"], "ORACLE_BOUND_NATURAL_MISS_SMOKE")
        self.assertEqual(report["r15_primary"]["status"], "NOT_IDENTIFIABLE")
        self.assertEqual(
            report["rc4_oracle_bound_replay"]["natural_misses_detected"], 2
        )
        self.assertEqual(
            report["rc4_oracle_bound_replay"]["correct_output_false_fires"], 0
        )
        self.assertFalse(report["boundaries"]["promotion_authorized"])
        self.assertFalse(report["boundaries"]["raw_answers_stored"])
        self.assertFalse(report["boundaries"]["raw_gold_stored"])
        self.assertEqual(report["costs"]["provider_calls"], 0)
        self.assertEqual(report["costs"]["token_spend"], 0)

    def test_historical_control_rejects_a_convenient_wrong_denominator(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "historical positive control failed"):
            evaluate_records(
                [gpqa("only-one", "A", "A")],
                protocol_commit=COMMIT,
                source_sha256={"arc_archive": "a" * 64, "gpqa_archive": "b" * 64},
            )


if __name__ == "__main__":
    unittest.main()
