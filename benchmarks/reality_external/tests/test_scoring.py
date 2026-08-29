from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCORING = ROOT / "scoring"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(SCORING))

from score_axiomatic import score as score_axiomatic  # noqa: E402
from score_liveideabench import score as score_liveidea  # noqa: E402
from score_projectionbench import score as score_projection  # noqa: E402
from score_researchbench import score as score_research  # noqa: E402
from score_rinobench import score as score_rino  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


class ScoringTests(unittest.TestCase):
    def test_rinobench_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            gold = td / "gold.jsonl"
            pred = td / "pred.jsonl"
            write_jsonl(gold, [{"sample_id": f"s{i}", "novelty_score": i} for i in range(1, 6)])
            write_jsonl(
                pred,
                [
                    {"sample_id": "s1", "arm": "BASELINE", "predicted_novelty_score": 1},
                    {"sample_id": "s2", "arm": "BASELINE", "predicted_novelty_score": 3},
                    {"sample_id": "s3", "arm": "BASELINE", "predicted_novelty_score": 3},
                    {"sample_id": "s4", "arm": "BASELINE", "predicted_novelty_score": 3},
                    {"sample_id": "s5", "arm": "BASELINE", "predicted_novelty_score": 5},
                ],
            )
            result = score_rino(str(gold), str(pred))["arms"]["BASELINE"]
            self.assertEqual(result["N"], 5)
            self.assertAlmostEqual(result["MAE"], 0.4)
            self.assertAlmostEqual(result["exact_score_accuracy"], 0.6)
            self.assertEqual(sum(map(sum, result["confusion_matrix_gold_rows_pred_columns"])), 5)

    def test_researchbench_aggregation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "judged.jsonl"
            write_jsonl(
                path,
                [
                    {"sample_id": "a", "arm": "REALITY", "matched_score_0_5": 5},
                    {"sample_id": "b", "arm": "REALITY", "matched_score_0_5": 3},
                ],
            )
            result = score_research(str(path), "RESEARCHBENCH_COMPATIBLE_JUDGE_ADAPTATION")
            self.assertAlmostEqual(result["arms"]["REALITY"]["normalized_accuracy"], 0.8)

    def test_liveidea_five_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "judge.jsonl"
            write_jsonl(
                path,
                [{"arm": "BASELINE", "originality": 8, "feasibility": 6, "fluency": 7, "flexibility": 5, "clarity": 9}],
            )
            result = score_liveidea(str(path), "LIVEIDEABENCH_SINGLE_JUDGE_ADAPTATION")
            self.assertAlmostEqual(result["arms"]["BASELINE"]["mean_five_dimension_score"], 7.0)

    def test_axiomatic_tie_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            rel = td / "relations.jsonl"
            pred = td / "pred.jsonl"
            write_jsonl(
                rel,
                [{"sample_id": "s", "lhs_pool_id": "p1", "rhs_pool_id": "p2", "expected_relation": ">", "axiom": "R", "probe_family": "R-exact"}],
            )
            write_jsonl(
                pred,
                [
                    {"sample_id": "s", "pool_id": "p1", "arm": "REALITY", "novelty_score_0_100": 50},
                    {"sample_id": "s", "pool_id": "p2", "arm": "REALITY", "novelty_score_0_100": 50},
                ],
            )
            aggregate = score_axiomatic(str(rel), str(pred))["arms"]["REALITY"]["aggregate"]
            self.assertEqual(aggregate["pass_rate"], 0.0)
            self.assertEqual(aggregate["tie_rate"], 1.0)

    def test_projection_auc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "counts.jsonl"
            write_jsonl(
                path,
                [
                    {"arm": "REALITY", "domain": "nano", "disclosure_level": "L0", "tp": 1, "fp": 1, "fn": 1},
                    {"arm": "REALITY", "domain": "nano", "disclosure_level": "L1", "tp": 2, "fp": 0, "fn": 0},
                    {"arm": "REALITY", "domain": "nano", "disclosure_level": "L2", "tp": 1, "fp": 1, "fn": 1},
                ],
            )
            result = score_projection(str(path), "PROJECTIONBENCH_COMPATIBLE_ADAPTATION")
            self.assertAlmostEqual(result["arms"]["REALITY"]["normalized_F1_disclosure_AUC"], 0.75)

    def test_seal_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            gold_dir = td / "gold"
            gold_dir.mkdir()
            write_jsonl(gold_dir / "a.jsonl", [{"sample_id": "opaque", "gold": 1}])
            cmd = [
                sys.executable,
                str(TOOLS / "seal_gold.py"),
                "--gold-dir",
                str(gold_dir),
                "--ciphertext",
                str(td / "gold.enc"),
                "--plaintext-hash",
                str(td / "plain.sha256"),
                "--ciphertext-hash",
                str(td / "cipher.sha256"),
                "--key-out",
                str(td / "key.txt"),
            ]
            run = subprocess.run(cmd, check=True, text=True, capture_output=True)
            self.assertIn("ROUND_TRIP=PASS", run.stdout)
            self.assertEqual((td / "key.txt").stat().st_size, 65)
            self.assertGreater((td / "gold.enc").stat().st_size, 20)


if __name__ == "__main__":
    unittest.main()
