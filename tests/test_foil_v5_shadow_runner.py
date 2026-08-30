"""Offline Gate-1 harness tests using only tiny structural smoke fixtures."""

from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))
sys.path.insert(0, str(ROOT / "tools"))

from foil_v5_shadow_runner import (  # noqa: E402
    AtlasError,
    assert_disjoint_partitions,
    load_atlas,
    run_shadow_atlas,
)

DEV = ROOT / "benchmarks" / "fixtures" / "foil_v5_obligation_atlas.dev.jsonl"
LOCK = ROOT / "benchmarks" / "fixtures" / "foil_v5_obligation_atlas.lock.jsonl"


class ShadowRunnerTests(unittest.TestCase):
    def test_dev_lock_are_disjoint_and_lock_smoke_run_clusters_mutants(self) -> None:
        development = load_atlas(DEV, partition="development")
        locked = load_atlas(LOCK, partition="lock")
        assert_disjoint_partitions(development, locked)
        result = run_shadow_atlas(
            locked,
            partition="lock",
            candidate_sha256="a" * 64,
            protocol_sha256="b" * 64,
        )
        self.assertEqual(len(result.records), 3)
        self.assertEqual(result.overall.rates.raw_rows, 3)
        self.assertEqual(result.overall.rates.clusters, 2)
        self.assertEqual(result.overall.rates.residual_recall.estimate, 1.0)
        self.assertEqual(result.overall.rates.false_positive_rate.estimate, 0.0)
        self.assertEqual(result.overall.rates.positive_predictive_value.estimate, 1.0)
        self.assertEqual(result.worst_domain, "arithmetic")
        self.assertTrue(all(row.a0_preserved for row in result.records))
        self.assertIn("Tiny structural smoke", result.validity_boundary)
        self.assertEqual(
            result.ledger_receipt["category_coverage"]["network"]["reason"],
            "forbidden_offline_effect_not_observed",
        )

    def test_scanner_input_rejects_labels_and_offline_effect_violations(self) -> None:
        row = copy.deepcopy(load_atlas(DEV, partition="development")[0])
        row["scanner"]["gold_label"] = "hidden"
        with self.assertRaisesRegex(AtlasError, "must not contain outcome labels"):
            run_shadow_atlas((row,), partition="development")
        clean = load_atlas(DEV, partition="development")
        with self.assertRaisesRegex(AtlasError, "forbidden effect"):
            run_shadow_atlas(clean, partition="development", observed_effects=("local", "model"))

    def test_partition_overlap_and_typed_unknown_not_applicable_are_visible(self) -> None:
        development = load_atlas(DEV, partition="development")
        overlapping = copy.deepcopy(development)
        overlapping[0]["partition"] = "lock"
        with self.assertRaisesRegex(AtlasError, "overlap"):
            assert_disjoint_partitions(development, overlapping)
        unknown = copy.deepcopy(development[0])
        unknown["scanner"]["needs"][0]["applicability"] = "UNKNOWN"
        result = run_shadow_atlas((unknown,), partition="development")
        self.assertEqual(result.records[0].status, "UNKNOWN")
        self.assertEqual(result.records[0].no_answer_code, "APPLICABILITY_UNKNOWN")
        not_applicable = copy.deepcopy(development[0])
        not_applicable["scanner"]["needs"][0]["applicability"] = "NOT_APPLICABLE"
        result = run_shadow_atlas((not_applicable,), partition="development")
        self.assertEqual(result.records[0].status, "NOT_APPLICABLE")

    def test_cli_entrypoint_resolves_repository_modules(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "benchmarks" / "harness" / "foil_v5_shadow_runner.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run a local FOIL v5 shadow atlas", result.stdout)

    def test_runner_source_has_no_provider_or_network_surface(self) -> None:
        source = (
            (ROOT / "benchmarks" / "harness" / "foil_v5_shadow_runner.py")
            .read_text(encoding="utf-8")
            .lower()
        )
        for forbidden in ("urllib", "requests", "socket", "subprocess", "foil_models"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
