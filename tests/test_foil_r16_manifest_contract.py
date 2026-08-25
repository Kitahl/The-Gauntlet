from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_r16_no_oracle_discovery_pilot as protocol  # noqa: E402


def d(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record(index: int) -> protocol.SourceResponse:
    return protocol.SourceResponse(
        question_sha256=d(f"q-{index}"),
        response_sha256=d(f"a-{index}"),
        question=f"Question {index}",
        ground_truth="A: 1",
        model_variant=protocol.MODEL_VARIANTS[index % 4],
        solution="A: 2",
        is_correct=False,
    )


def manifest(rows: list[protocol.SourceResponse]) -> dict[str, object]:
    return {
        "schema": protocol.LABEL_SCHEMA,
        "source_sha256": protocol.SOURCE_SHA256,
        "selection_seed": protocol.SELECTION_SEED,
        "rows": [
            {
                "question_sha256": row.question_sha256,
                "model_variant": row.model_variant,
                "response_sha256": row.response_sha256,
                "primary_label": "UNMAPPED",
            }
            for row in rows
        ],
    }


class ManifestContractTests(unittest.TestCase):
    def test_only_the_exact_candidate_order_prefix_is_accepted(self) -> None:
        candidates = [record(index) for index in range(3)]
        accepted = protocol.load_label_manifest(manifest(candidates[:2]), candidates)
        self.assertEqual(list(accepted), [item.identity for item in candidates[:2]])
        with self.assertRaisesRegex(RuntimeError, "exact candidate-order prefix"):
            protocol.load_label_manifest(
                manifest([candidates[1], candidates[0]]), candidates
            )


if __name__ == "__main__":
    unittest.main()
