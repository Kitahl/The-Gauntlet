from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from bench_reality_runtime import run_benchmark  # noqa: E402


class RealityBenchmarkTests(unittest.TestCase):
    def test_offline_correctness_and_runtime_benchmark(self) -> None:
        result = run_benchmark()
        print("REALITY_BENCHMARK_JSON=" + json.dumps(result, sort_keys=True))
        self.assertEqual(
            result["correctness"]["passed"],
            result["correctness"]["total"],
        )
        self.assertEqual(result["correctness"]["total"], 8)
        self.assertTrue(result["scope"]["offline"])
        self.assertFalse(result["scope"]["scientific_efficacy_measured"])
        self.assertFalse(result["scope"]["global_novelty_measured"])


if __name__ == "__main__":
    unittest.main()
