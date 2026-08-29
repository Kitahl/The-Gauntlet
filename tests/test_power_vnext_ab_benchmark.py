from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from bench_power_vnext_ab import run_benchmark  # noqa: E402


class PowerVNextABBenchmarkTests(unittest.TestCase):
    def test_old_vs_new_mechanism_benchmark(self) -> None:
        result = run_benchmark()
        summary = {
            "old_shared": result["old"]["shared"],
            "new_shared": result["new"]["shared"],
            "old_vnext": result["old"]["vnext"],
            "new_vnext": result["new"]["vnext"],
            "old_total": result["old"]["total"],
            "new_total": result["new"]["total"],
            "delta_passes": result["delta_passes"],
        }
        print("POWER_AB_SUMMARY=" + json.dumps(summary, sort_keys=True))
        print("POWER_AB_RESULT=" + json.dumps(result, sort_keys=True))
        self.assertEqual(
            result["old"]["runtime_blob"], "5b2c0e6f06df99bac77973f70485cd3c465729e4"
        )
        self.assertEqual(
            result["new"]["runtime_blob"], "99f5b955b782b61ccaa5fa481ecd347963c3a35a"
        )
        self.assertEqual(result["new"]["shared"]["passed"], result["new"]["shared"]["total"])
        self.assertEqual(result["new"]["vnext"]["passed"], result["new"]["vnext"]["total"])
        self.assertGreater(result["new"]["total"]["passed"], result["old"]["total"]["passed"])
        precedence = next(
            c for c in result["cases"] if c["case"] == "shared.unavailable_dominates_unknown"
        )
        self.assertFalse(precedence["old"]["pass"])
        self.assertTrue(precedence["new"]["pass"])


if __name__ == "__main__":
    unittest.main()
