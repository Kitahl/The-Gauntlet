"""Controls for the prospectively frozen TOKEN-700 evaluator."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "token700_verify.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("token700_verify", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load TOKEN-700 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t700 = _load()


class FrozenManifestTests(unittest.TestCase):
    def test_manifest_hash_and_case_cardinality_are_frozen(self) -> None:
        manifest = t700.load_manifest()
        cases = t700.expand_cases(manifest)
        self.assertEqual(manifest["protocol_revision"], 3)
        self.assertEqual(len(cases), 30)
        self.assertEqual(len({case["case_id"] for case in cases}), 30)
        self.assertEqual(
            [case["case_id"] for case in cases[:4]],
            ["W01-S01", "W01-S02", "W01-S03", "W02-S01"],
        )

    def test_all_ten_audit_workload_names_are_present(self) -> None:
        manifest = t700.load_manifest()
        self.assertEqual(
            [workload["name"] for workload in manifest["workloads"]],
            [
                "no-tool one-shot",
                "one status call",
                "web research",
                "coding/edit/verification",
                "browser interaction",
                "small MCP catalog",
                "large MCP catalog",
                "ten-turn chat",
                "resumed long session",
                "mixed multi-obligation task",
            ],
        )

    def test_long_session_anchor_occurs_only_on_turn_one(self) -> None:
        cases = t700.expand_cases(t700.load_manifest())
        for workload_id, marker in (("W08", "FIRST_"), ("W09", "ANCHOR_")):
            case = next(case for case in cases if case["workload"]["id"] == workload_id)
            turns = t700.expand_turns(case)
            self.assertIn(marker, turns[0]["prompt"])
            self.assertTrue(all(marker not in turn["prompt"] for turn in turns[1:]))
            required = t700._required_history_markers(case)
            self.assertTrue(any(marker in item for item in required))

    def test_every_expanded_turn_has_exact_marker_and_w10_fallback(self) -> None:
        cases = t700.expand_cases(t700.load_manifest())
        turn_count = 0
        for case in cases:
            turns = t700.expand_turns(case)
            turn_count += len(turns)
            for turn in turns:
                marker = f"TOKEN700|{case['case_id']}|{turn['turn_id']}|"
                self.assertIn(marker, turn["prompt"])
        self.assertEqual(turn_count, 102)
        w10 = next(case for case in cases if case["case_id"] == "W10-S01")
        self.assertIn("MIXED_W10-S01 obligation pass 1", t700.expand_turns(w10)[0]["prompt"])
        self.assertNotEqual(t700.expand_turns(w10)[0]["prompt"], "None")

    def test_expanded_turn_without_exact_marker_is_rejected(self) -> None:
        bad = {
            "case_id": "W99-S01",
            "workload": {
                "turns": [
                    {
                        "turn_id": "T01",
                        "provider_action": "FINAL",
                        "prompt_template": "missing marker",
                    }
                ]
            },
        }
        with self.assertRaisesRegex(ValueError, "lacks its exact provider marker"):
            t700.expand_turns(bad)

    def test_fixture_actions_are_single_and_frozen_per_case(self) -> None:
        cases = t700.expand_cases(t700.load_manifest())
        actions = t700._actions(cases)
        self.assertEqual(len(actions), 30)
        self.assertEqual(actions["W01-S01"], "FINAL")
        self.assertEqual(actions["W02-S01"], "STATUS_THEN_FINAL")
        self.assertEqual(actions["W07-S03"], "UNAVAILABLE_FINAL")


class FrozenAnalysisTests(unittest.TestCase):
    def test_finite_suite_noninferiority_is_strict(self) -> None:
        passing = t700.finite_suite_noninferiority([(True, True)] * 30)
        self.assertTrue(passing["passed"])
        self.assertEqual(passing["margin_percentage_points"], 0)
        self.assertFalse(passing["population_inference"])

        regression = t700.finite_suite_noninferiority([(True, True)] * 29 + [(True, False)])
        self.assertFalse(regression["passed"])
        self.assertEqual(regression["regressions"], 1)

    def test_improvement_does_not_hide_a_regression(self) -> None:
        report = t700.finite_suite_noninferiority(
            [(True, False), (False, True)] + [(True, True)] * 28
        )
        self.assertEqual(report["improvements"], 1)
        self.assertEqual(report["regressions"], 1)
        self.assertFalse(report["passed"])

    def test_paired_reduction_uses_case_baseline(self) -> None:
        self.assertEqual(t700.paired_reduction(100, 60), 0.4)
        self.assertEqual(t700.median([0.2, 0.4, 0.8]), 0.4)
        with self.assertRaises(ValueError):
            t700.paired_reduction(0, 0)

    def test_invalid_pair_suppresses_reduction_fields(self) -> None:
        cases = [
            {
                "case_id": "W01-S01",
                "workload": {"id": "W01", "name": "one", "scope": "FULL_LOCAL"},
            }
        ]
        results = {
            "W01-S01": {
                "arm_order": ["baseline", "candidate"],
                "baseline": {
                    "correct": False,
                    "local_estimated_input_tokens": 100,
                    "complete_token_units": 120,
                },
                "candidate": {
                    "correct": True,
                    "local_estimated_input_tokens": 50,
                    "complete_token_units": 60,
                },
            }
        }
        pair = t700._pair_results(cases, results)[0]
        self.assertIsNone(pair["input_reduction"])
        self.assertIsNone(pair["complete_token_reduction"])

    def test_request_classifier_separates_conversation_title_and_unknown(self) -> None:
        conversation = {
            "stream": True,
            "messages": [{"role": "user", "content": "TOKEN700|W01-S01|T01| current"}],
        }
        title = {
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "session_title"},
            },
            "messages": [{"role": "user", "content": "TOKEN700|W01-S01|T01| title"}],
        }
        self.assertEqual(t700._server_request_kind(conversation), "conversation")
        self.assertEqual(t700._server_request_kind(title), "title_generation")
        self.assertEqual(t700._server_request_kind({"stream": False}), "unknown")

    def test_auxiliary_policy_is_arm_and_session_scoped(self) -> None:
        title = {"auxiliary_task": "title_generation"}
        self.assertTrue(t700._auxiliary_policy_satisfied("baseline", 1, [title]))
        self.assertTrue(t700._auxiliary_policy_satisfied("baseline", 0, []))
        self.assertTrue(t700._auxiliary_policy_satisfied("baseline", 1, [title]))
        self.assertFalse(t700._auxiliary_policy_satisfied("candidate", 1, [title]))
        self.assertTrue(t700._auxiliary_policy_satisfied("candidate", 0, []))
        self.assertFalse(
            t700._auxiliary_policy_satisfied("baseline", 1, [{"auxiliary_task": "compression"}])
        )
        no_aux = {"auxiliary_provider_dispatches": 0}
        one_aux = {"auxiliary_provider_dispatches": 1}
        self.assertTrue(t700._case_auxiliary_policy_satisfied("baseline", [no_aux, one_aux]))
        self.assertFalse(t700._case_auxiliary_policy_satisfied("baseline", [one_aux, one_aux]))
        self.assertTrue(t700._case_auxiliary_policy_satisfied("candidate", [no_aux, no_aux]))
        self.assertFalse(t700._case_auxiliary_policy_satisfied("candidate", [no_aux, one_aux]))

    def test_nested_capsule_metrics_and_complete_cost_are_explicit(self) -> None:
        self.assertEqual(
            t700._capsule_metrics(
                {"lean_context": {"capsule_metrics": {"route_estimated_tokens": 12}}}
            ),
            {"route_estimated_tokens": 12},
        )
        self.assertIsNone(t700._capsule_metrics({"capsule_metrics": {"wrong": True}}))
        documents = [
            {
                "request_composition": {"local_estimated_tokens": 100},
                "provider_usage": {
                    "output_tokens": 10,
                    "reasoning_tokens": 3,
                    "cache_write_tokens": 5,
                    "cache_read_tokens": 7,
                },
            },
            {
                "request_composition": {"local_estimated_tokens": 20},
                "provider_usage": {"output_tokens": 2},
            },
        ]
        self.assertEqual(
            t700._measurement_totals(documents),
            {
                "local_input_tokens": 120,
                "provider_output_tokens": 12,
                "reasoning_tokens": 3,
                "cache_write_tokens": 5,
                "cache_read_tokens": 7,
                "complete_token_units": 140,
            },
        )

    def test_case_marker_parser_uses_latest_user_protocol(self) -> None:
        body = {
            "messages": [
                {"role": "user", "content": "TOKEN700|W01-S01|T01| first"},
                {"role": "assistant", "content": "done"},
                {"role": "user", "content": "TOKEN700|W08-S03|T10| current"},
            ]
        }
        self.assertEqual(
            t700.CASE_PATTERN.search(t700._latest_user_text(body)).groups(),
            ("W08-S03", "T10"),
        )


if __name__ == "__main__":
    unittest.main()
