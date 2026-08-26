from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_assistance_replay as replay  # noqa: E402


class AssistanceReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "benchmarks" / "fixtures" / "foil_assistance_replay_v1.json"
        cls.document = json.loads(path.read_text(encoding="utf-8"))

    def test_all_frozen_traces_pass(self) -> None:
        report = replay.replay(self.document)
        self.assertEqual(report["cases"], 4)
        self.assertEqual(report["passed"], 4)
        self.assertEqual(report["failed"], 0)
        self.assertTrue(all(value == 0 for value in report["cost_and_authority"].values()))

    def test_copy_paste_ownership_stays_non_load_bearing(self) -> None:
        report = replay.replay(self.document)
        row = next(item for item in report["rows"] if item["id"].startswith("copy-pasted"))
        self.assertEqual(row["observed"]["load_bearing_n"], 0.0)
        self.assertEqual(row["observed"]["classification"], "INSUFFICIENT_EVIDENCE")

    def test_unknown_fixture_fields_fail_closed(self) -> None:
        malformed = copy.deepcopy(self.document)
        malformed["cases"][0]["answer"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            replay.replay(malformed)

    def test_expected_result_tampering_is_visible(self) -> None:
        malformed = copy.deepcopy(self.document)
        malformed["cases"][0]["expected_assistance"] = "A0_INDEPENDENT"
        report = replay.replay(malformed)
        self.assertEqual(report["failed"], 1)


if __name__ == "__main__":
    unittest.main()
