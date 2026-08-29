from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class MaterializeTests(unittest.TestCase):
    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["REALITY_BENCH_ID_KEY_HEX"] = "11" * 32
        return env

    def test_liveidea_hides_domain_and_balances(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            kws = td / "kws.csv"
            cls = td / "cls.csv"
            with kws.open("w", encoding="utf-8", newline="") as h:
                w = csv.writer(h)
                w.writerow(["", "Keyword"])
                for i, keyword in enumerate(["a1", "a2", "a3", "b1", "b2", "b3"]):
                    w.writerow([i, keyword])
            with cls.open("w", encoding="utf-8", newline="") as h:
                w = csv.writer(h)
                w.writerow(["keyword", "category", "similarity_score"])
                for keyword in ["a1", "a2", "a3"]:
                    w.writerow([keyword, "A", 1])
                for keyword in ["b1", "b2", "b3"]:
                    w.writerow([keyword, "B", 1])
            out = td / "out"
            cmd = [
                sys.executable,
                str(TOOLS / "materialize.py"),
                "liveidea",
                "--keywords",
                str(kws),
                "--classifications",
                str(cls),
                "--out-dir",
                str(out),
                "--expected-domains",
                "2",
                "--per-domain",
                "2",
            ]
            first = subprocess.run(cmd, env=self.env(), check=True, text=True, capture_output=True)
            pilot = read_jsonl(out / "inputs" / "liveideabench_v2_pilot_blind.jsonl")
            self.assertEqual(len(pilot), 4)
            self.assertTrue(all(set(row) == {"sample_id", "keyword"} for row in pilot))
            before = (out / "inputs" / "liveideabench_v2_pilot_blind.jsonl").read_bytes()
            second = subprocess.run(cmd, env=self.env(), check=True, text=True, capture_output=True)
            after = (out / "inputs" / "liveideabench_v2_pilot_blind.jsonl").read_bytes()
            self.assertEqual(before, after)
            self.assertIn("LIVEIDEABENCH_PILOT=4", first.stdout)
            self.assertIn("LIVEIDEABENCH_PILOT=4", second.stdout)

    def test_rinobench_hides_gold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            rows = []
            for label in range(1, 6):
                for i in range(2):
                    rows.append(
                        {
                            "id": f"{label}-{i}",
                            "research_idea": {"idea": f"idea {label}-{i}"},
                            "related_works": [{"title": "prior"}],
                            "novelty_score": label,
                            "novelty_reasoning": "hidden",
                        }
                    )
            source = td / "rino.json"
            source.write_text(json.dumps(rows), encoding="utf-8")
            out = td / "out"
            cmd = [
                sys.executable,
                str(TOOLS / "materialize.py"),
                "rinobench",
                "--input",
                str(source),
                "--out-dir",
                str(out),
                "--pilot-size",
                "10",
            ]
            subprocess.run(cmd, env=self.env(), check=True, text=True, capture_output=True)
            blind = read_jsonl(out / "inputs" / "rinobench_full_blind.jsonl")
            self.assertEqual(len(blind), 10)
            self.assertTrue(all("novelty_score" not in row and "novelty_reasoning" not in row for row in blind))
            self.assertEqual(len({row["sample_id"] for row in blind}), 10)


if __name__ == "__main__":
    unittest.main()
