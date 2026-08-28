from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from foil_benchmark_budget import (  # noqa: E402
    BenchmarkBudgetError,
    BenchmarkTokenLedger,
)


class BenchmarkTokenLedgerTests(unittest.TestCase):
    def test_cap_is_caller_supplied(self) -> None:
        ledger = BenchmarkTokenLedger(123)
        self.assertEqual(ledger.maximum_total_tokens, 123)
        with self.assertRaises(TypeError):
            BenchmarkTokenLedger()

    def test_reserve_settle_and_conservation(self) -> None:
        ledger = BenchmarkTokenLedger(100)
        ledger.reserve("a", 60, provider_cap_enforced=True)
        self.assertEqual(ledger.remaining_unreserved_tokens, 40)
        ledger.settle("a", 45)
        self.assertEqual(ledger.spent_total_tokens, 45)
        self.assertEqual(ledger.remaining_unreserved_tokens, 55)
        self.assertEqual(
            ledger.spent_total_tokens
            + ledger.reserved_total_tokens
            + ledger.remaining_unreserved_tokens,
            ledger.maximum_total_tokens,
        )

    def test_refuses_unenforced_or_oversized_call(self) -> None:
        ledger = BenchmarkTokenLedger(100)
        with self.assertRaisesRegex(BenchmarkBudgetError, "cannot enforce"):
            ledger.reserve("a", 10, provider_cap_enforced=False)
        with self.assertRaisesRegex(BenchmarkBudgetError, "exceed"):
            ledger.reserve("b", 101, provider_cap_enforced=True)
        self.assertEqual(ledger.spent_total_tokens, 0)

    def test_duplicate_and_overrun_fail_closed(self) -> None:
        ledger = BenchmarkTokenLedger(100)
        ledger.reserve("a", 50, provider_cap_enforced=True)
        with self.assertRaisesRegex(BenchmarkBudgetError, "already reserved"):
            ledger.reserve("a", 1, provider_cap_enforced=True)
        with self.assertRaisesRegex(BenchmarkBudgetError, "exceeded"):
            ledger.settle("a", 51)


if __name__ == "__main__":
    unittest.main()
