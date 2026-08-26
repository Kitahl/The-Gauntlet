"""Tests for the ProcessBench arithmetic alarm smoke gate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_arithmetic_alarm_gate import (  # noqa: E402
    ADJUDICATIONS,
    RULES,
    _score,
    _summary,
    row_digest,
)
from p0_processbench import ProcessRow  # noqa: E402


def row(
    row_id: str,
    step: str,
    *,
    label: int,
    split: str = "math",
) -> ProcessRow:
    return ProcessRow(
        split=split,
        row_id=row_id,
        generator="Qwen2.5-Math-72B-Instruct",
        problem="synthetic",
        steps=(step,),
        final_answer_correct=label == -1,
        label=label,
    )


class ArithmeticAlarmGateTests(unittest.TestCase):
    def test_each_rule_detects_only_its_closed_language(self):
        rows = (
            row("plain-correct", r"\[2+2=4\]", label=-1),
            row("plain-wrong", r"\[2+2=5\]", label=0),
            row("power-correct", r"\[2^3=8\]", label=-1),
            row("power-wrong", r"\[2^3=9\]", label=0),
            row("raw-correct", "2+2=4", label=-1),
            row("raw-wrong", "2+2=5", label=0),
        )
        detections = {
            language: [item.row.row_id for item in _score(rows, language) if item.detected]
            for language in RULES
        }
        self.assertEqual(detections["certified-v2"], ["plain-wrong"])
        self.assertEqual(
            detections["numeric-power-equality-v1"], ["power-wrong"]
        )
        self.assertEqual(detections["raw-numeric-equality-v1"], ["raw-wrong"])

    def test_clean_false_equality_fails_the_smoke_gate(self):
        scored = _score(
            (row("bad-label", r"\[2+2=5\]", label=-1),), "certified-v2"
        )
        summary = _summary(scored)
        self.assertEqual(summary["labeled_false_fires"], 1)
        self.assertEqual(summary["audited_false_fires"], 1)

    def test_adjudication_is_content_bound(self):
        key = ("omnimath", "omnimath-805")
        self.assertIn(key, ADJUDICATIONS)
        fake = row("omnimath-805", r"\[1404=468\]", label=-1, split="omnimath")
        self.assertNotEqual(row_digest(fake), ADJUDICATIONS[key]["row_sha256"])
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            _summary(_score((fake,), "certified-v2"))


if __name__ == "__main__":
    unittest.main()
