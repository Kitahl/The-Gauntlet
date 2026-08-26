"""Structural-pilot tests for RPS v0.6.2."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

from foil_rps_v062_structural_pilot import run  # noqa: E402


class RPSV062StructuralPilotTests(unittest.TestCase):
    def test_transition_matrix_and_hash_are_deterministic(self):
        first = run()
        second = run()
        self.assertEqual(first, second)
        summary = first["summary"]
        self.assertEqual(summary["passed"], 6)
        self.assertEqual(summary["total"], 6)
        self.assertEqual(summary["provider_calls"], 0)
        self.assertEqual(summary["model_tokens"], 0)
        self.assertEqual(summary["answer_mutations"], 0)
        content_hash = first.pop("content_sha256")
        canonical = json.dumps(first, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            content_hash, hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
