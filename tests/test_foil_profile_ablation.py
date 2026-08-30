"""Contract tests for the offline P0 profile-routing reproducibility layer."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_profile_ablation as ablation  # noqa: E402

FIXTURE = ROOT / "benchmarks" / "fixtures" / "p0_routing_ablation_fixture.json"


class RoutingProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.items = ablation.validate_fixture(cls.fixture)

    def test_three_arms_are_isolated_and_router_only(self) -> None:
        manifest = ablation.build_manifest(self.items)
        self.assertEqual(ablation.CONDITIONS, ("CORRECT_PROFILE", "WRONG_PROFILE", "NO_PROFILE"))
        self.assertTrue(manifest["profile_visible_to"] == "router_only")
        self.assertFalse(manifest["solver_profile_access"])
        sessions = [unit["isolation_session_id"] for unit in manifest["units"]]
        self.assertEqual(len(sessions), len(set(sessions)))
        for item in self.items:
            units = [unit for unit in manifest["units"] if unit["item_id"] == item["item_id"]]
            self.assertEqual({unit["condition"] for unit in units}, set(ablation.CONDITIONS))
            self.assertEqual(len({unit["requirement_sha256"] for unit in units}), 1)

    def test_fixture_is_strict_structural_smoke_only(self) -> None:
        self.assertEqual(self.fixture["fixture_kind"], ablation.FIXTURE_KIND)
        malformed = copy.deepcopy(self.fixture)
        malformed["unexpected"] = True
        with self.assertRaises(ValueError):
            ablation.validate_fixture(malformed)
        malformed = copy.deepcopy(self.fixture)
        malformed["items"][0]["profiles"]["CORRECT_PROFILE"]["causal_reasoning"]["leak"] = "raw"
        with self.assertRaises(ValueError):
            ablation.validate_fixture(malformed)

    def test_proxy_seals_profile_payloads_and_cannot_claim_efficacy(self) -> None:
        report = ablation.run_routing_proxy(self.items, seed=7)
        encoded = json.dumps(report)
        self.assertNotIn('"observations"', encoded)
        self.assertNotIn("task_success", encoded)
        self.assertEqual(report["promotion_status"], "P0_NOT_PROMOTED")
        self.assertFalse(report["behavioral_efficacy_measured"])
        self.assertFalse(report["p1_release_allowed"])
        self.assertIn('"profile_payload_sha256"', encoded)
        self.assertEqual(report, ablation.run_routing_proxy(self.items, seed=7))

    def test_proxy_profiles_change_only_router_control_behavior(self) -> None:
        report = ablation.run_routing_proxy(self.items)
        self.assertGreater(report["profile_value"], 0.0)
        self.assertGreater(report["wrong_profile_excess_harm"], 0.0)
        self.assertEqual(report["metrics"]["NO_PROFILE"]["complement_hit_rate"], 0.0)


class BehavioralRecordTests(unittest.TestCase):
    def records(self) -> list[dict]:
        profiles = {"CORRECT_PROFILE": "b" * 64, "WRONG_PROFILE": "c" * 64, "NO_PROFILE": None}
        effects = {
            "CORRECT_PROFILE": (True, "useful_complement"),
            "WRONG_PROFILE": (False, "harmful_assistance"),
            "NO_PROFILE": (False, "missed_gap"),
        }
        return [
            {
                "item_id": "i1",
                "condition": condition,
                "task_success": success,
                "effect": effect,
                "model": "externally-recorded-model",
                "allowed_tools": [],
                "budget": {"model_calls": 1, "tool_calls": 0},
                "usage": {"model_calls": 1, "tool_calls": 0, "latency_ms": 10, "tokens": 100},
                "run_cost_receipt": {
                    "schema": "egrt.foil-run-cost.v1",
                    "task_id": "i1",
                    "condition": condition,
                    "prompt_sha256": "a" * 64,
                    "profile_payload_sha256": profiles[condition],
                    "profile_lookup_count": 0 if condition == "NO_PROFILE" else 1,
                    "routing_decision_count": 1,
                    "model_calls": 1,
                    "tool_calls": 0,
                    "verification_calls": 0,
                    "retry_count": 0,
                    "branch_count": 1,
                    "revision_count": 0,
                    "tokens_in": 60,
                    "tokens_out": 40,
                    "wall_time_ms": 10,
                    "raw_prompt_stored": False,
                },
                "prompt_sha256": "a" * 64,
                "scorer_sha256": "d" * 64,
                "profile_visible_to": "router_only",
                "solver_profile_access": False,
                "prediction_frozen": True,
                "gold_access_before_freeze": False,
                "isolation_session_id": f"session-{index}",
            }
            for index, (condition, (success, effect)) in enumerate(effects.items())
        ]

    def test_external_records_remain_descriptive_and_not_promoted(self) -> None:
        report = ablation.score_behavioral_records(self.records())
        self.assertEqual(report["promotion_status"], "P0_NOT_PROMOTED")
        self.assertFalse(report["behavioral_efficacy_measured"])
        self.assertFalse(report["actual_cost_matched"])

    def test_record_matching_and_receipts_fail_closed(self) -> None:
        for mutate in (
            lambda rows: rows[0].update(model="different-model"),
            lambda rows: rows[0].update(isolation_session_id=rows[1]["isolation_session_id"]),
            lambda rows: rows[0]["run_cost_receipt"].update(model_calls=2),
            lambda rows: rows[2]["run_cost_receipt"].update(profile_lookup_count=1),
            lambda rows: rows[0].update(raw_profile="forbidden"),
        ):
            rows = self.records()
            mutate(rows)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                ablation.score_behavioral_records(rows)

    def test_module_has_no_provider_or_execution_path(self) -> None:
        source = inspect.getsource(ablation)
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = {
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "openai",
            "openrouter",
            "foil_tool_broker",
        }
        self.assertFalse(imported & forbidden)
        self.assertNotIn("def execute", source)
        self.assertNotIn("def call_provider", source)


if __name__ == "__main__":
    unittest.main()
