from __future__ import annotations

import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "benchmarks" / "harness" / "foil_hle_active_20.py"
SPEC = importlib.util.spec_from_file_location("foil_hle_active_20", HARNESS_PATH)
assert SPEC is not None and SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class HLEActiveHarnessTests(unittest.TestCase):
    def test_matrix_has_requested_configs_and_balanced_arms(self) -> None:
        rows = [
            {
                "id": f"fresh-{index:02d}",
                "question": "q" * (1000 - index),
                "answer_type": "exactMatch",
                "answer": str(index),
                "category": "Math",
            }
            for index in range(23)
        ]
        items = HARNESS.select_items(rows)
        self.assertEqual(len(items), 20)
        self.assertEqual(Counter(row["arm"] for row in items), Counter({"FOIL": 10, "FOIL_TOOLS": 10}))
        self.assertEqual(set(HARNESS.CONFIGS), {"TERRA_HIGH", "LUNA_LOW", "LUNA_HIGH"})
        self.assertEqual(len(HARNESS.build_units(items)), 60)

    def test_route_is_full_for_both_arms_but_only_tools_arm_gets_retrieval(self) -> None:
        plain = HARNESS.policy_document("FOIL")
        tooled = HARNESS.policy_document("FOIL_TOOLS")
        self.assertEqual(plain["host_route"], "FULL")
        self.assertEqual(tooled["host_route"], "FULL")
        self.assertFalse(plain["retrieval_allowed"])
        self.assertTrue(tooled["retrieval_allowed"])

    def test_search_is_route_only_and_no_token_limit_is_passed(self) -> None:
        with patch.object(HARNESS, "codex_executable", return_value="codex"):
            base = HARNESS.build_argv("LUNA_LOW", "FOIL_TOOLS", "base", Path("w"), Path("o"))
            plain = HARNESS.build_argv("LUNA_HIGH", "FOIL", "route", Path("w"), Path("o"))
            tooled = HARNESS.build_argv("TERRA_HIGH", "FOIL_TOOLS", "route", Path("w"), Path("o"))
        self.assertNotIn("--search", base)
        self.assertNotIn("--search", plain)
        self.assertIn("--search", tooled)
        self.assertFalse(any("token" in part.casefold() for part in tooled))

    def test_stream_preserves_tool_start_completion_and_usage(self) -> None:
        stream = HARNESS.parse_stream(
            "\n".join(
                [
                    json.dumps({"type": "item.started", "item": {"id": "w", "type": "web_search"}}),
                    json.dumps({"type": "item.completed", "item": {"id": "w", "type": "web_search", "query": "evidence"}}),
                    json.dumps({"type": "turn.completed", "usage": {"input_tokens": 11, "cached_input_tokens": 3, "output_tokens": 5, "reasoning_output_tokens": 2}}),
                ]
            )
        )
        self.assertEqual(stream["tools"][0]["first_event_index"], 0)
        self.assertEqual(stream["tools"][0]["last_event_index"], 1)
        self.assertTrue(stream["tools"][0]["started"])
        self.assertTrue(stream["tools"][0]["completed"])
        self.assertEqual(stream["usage"]["reasoning_output_tokens"], 2)

    def test_oracle_and_tool_claim_boundaries_fail_closed(self) -> None:
        self.assertIsNotNone(HARNESS.parse_base_answer('{"answer":"A","gold":"B"}')[1])
        answer = {
            "answer": "A",
            "route": "FULL",
            "gap_kind": "EVIDENCE_GAP",
            "tool_decision": "USED_WEB_SEARCH",
            "tool_use_rationale": "source checked",
            "evidence_urls": ["https://example.test"],
            "confidence": 70,
        }
        tool = {"tool_type": "web_search"}
        self.assertFalse(HARNESS._validate_tool_claim("FOIL_TOOLS", answer, [tool]))
        self.assertIn("tools_used_in_no_tools_arm", HARNESS._validate_tool_claim("FOIL", answer, [tool]))


if __name__ == "__main__":
    unittest.main()
