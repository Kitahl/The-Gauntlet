"""Adversarial contract tests for the FOIL v5 sealed run ledger."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_v5_run_ledger import (  # noqa: E402
    EFFECT_CATEGORIES,
    LedgerError,
    RunLedger,
    verify_receipt,
)

CANDIDATE = "a" * 64
PROTOCOL = "b" * 64


def complete_ledger() -> RunLedger:
    ledger = RunLedger(candidate_sha256=CANDIDATE, protocol_sha256=PROTOCOL)
    ledger.begin(100)
    for category in sorted(EFFECT_CATEGORIES):
        ledger.record_category(category, observation={"tokens": None, "billed_usd": None})
    ledger.start_span("local-main", category="local", started_ns=110)
    ledger.start_span("parser-child", category="parser", started_ns=120, parent_span_id="local-main")
    ledger.end_span("parser-child", ended_ns=130)
    ledger.end_span("local-main", ended_ns=150)
    ledger.close(200)
    return ledger


class RunLedgerTests(unittest.TestCase):
    def test_complete_receipt_preserves_none_and_distinguishes_top_level_wall_time(self) -> None:
        receipt = complete_ledger().seal()
        self.assertEqual(receipt["top_level"]["wall_time_ns"], 100)
        spans = {row["span_id"]: row for row in receipt["spans"]}
        self.assertEqual(spans["local-main"]["duration_ns"], 40)
        self.assertEqual(spans["parser-child"]["duration_ns"], 10)
        self.assertIsNone(receipt["category_coverage"]["network"]["observation"]["billed_usd"])
        verify_receipt(receipt)

    def test_all_registered_categories_must_be_covered(self) -> None:
        ledger = RunLedger(candidate_sha256=CANDIDATE, protocol_sha256=PROTOCOL)
        ledger.begin(1)
        ledger.close(2)
        with self.assertRaisesRegex(LedgerError, "uncovered"):
            ledger.seal()

    def test_unknown_and_unregistered_effectors_are_rejected(self) -> None:
        ledger = RunLedger(
            candidate_sha256=CANDIDATE,
            protocol_sha256=PROTOCOL,
            required_categories=frozenset({"local"}),
        )
        ledger.begin(1)
        with self.assertRaisesRegex(LedgerError, "unknown effector"):
            ledger.record_category("invented")
        with self.assertRaisesRegex(LedgerError, "unregistered effector"):
            ledger.record_category("network")

    def test_unclosed_and_invalid_child_spans_fail_closed(self) -> None:
        ledger = RunLedger(
            candidate_sha256=CANDIDATE,
            protocol_sha256=PROTOCOL,
            required_categories=frozenset({"local"}),
        )
        ledger.begin(10)
        with self.assertRaisesRegex(LedgerError, "parent span is unknown"):
            ledger.start_span("child", category="local", started_ns=11, parent_span_id="absent")
        ledger.start_span("open", category="local", started_ns=11)
        with self.assertRaisesRegex(LedgerError, "all spans must close"):
            ledger.close(12)

    def test_receipt_tampering_is_detected_and_seal_is_immutable(self) -> None:
        ledger = complete_ledger()
        receipt = ledger.seal()
        changed = copy.deepcopy(receipt)
        changed["top_level"]["wall_time_ns"] = 0
        with self.assertRaisesRegex(LedgerError, "does not match"):
            verify_receipt(changed)
        with self.assertRaisesRegex(LedgerError, "immutable"):
            ledger.record_category("local")

    def test_bad_timing_is_rejected(self) -> None:
        ledger = RunLedger(
            candidate_sha256=CANDIDATE,
            protocol_sha256=PROTOCOL,
            required_categories=frozenset({"local"}),
        )
        ledger.begin(10)
        ledger.start_span("local", category="local", started_ns=11)
        with self.assertRaisesRegex(LedgerError, "cannot end before"):
            ledger.end_span("local", ended_ns=10)


if __name__ == "__main__":
    unittest.main()
