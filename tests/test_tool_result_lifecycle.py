"""TOKEN-400 private artifact and request-only tool-result lifecycle gates."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from gauntlet_host import gauntlet_plugin
from gauntlet_host.lean_context import build_sparse_context_plan
from gauntlet_host.tool_results import (
    CURRENT_CALL_SCHEMA,
    PAGE_SCHEMA,
    REFERENCE_SCHEMA,
    OperationalArtifactStore,
    ToolResultLifecycleError,
    parse_reference,
)


def _large_result(marker: str = "TOKEN400-RAW-MARKER") -> str:
    return f"status=OK\ntoken=super-secret-value\n{marker}\n" + ("payload-data\n" * 800)


class OperationalArtifactStoreTests(unittest.TestCase):
    def test_small_results_remain_inline_and_large_results_are_private_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
            )
            self.assertIsNone(
                store.externalize("small result", tool_name="tool-a", tool_call_id="call-small")
            )

            result = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-large",
            )
            self.assertIsNotNone(result)
            assert result is not None
            reference = parse_reference(result.reference)
            self.assertIsNotNone(reference)
            assert reference is not None
            self.assertEqual(reference["schema"], REFERENCE_SCHEMA)
            self.assertEqual(reference["artifact_id"], result.artifact_id)
            self.assertNotIn("super-secret-value", result.content)
            self.assertIn("token=<redacted>", result.content)
            self.assertLess(len(result.reference), len(result.content))

            path = store.root / f"{result.artifact_id}.json"
            self.assertTrue(path.is_file())
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["authority"], "OPERATIONAL_ONLY")
            self.assertFalse(document["canonical_evidence"])
            self.assertEqual(document["content"], result.content)

    def test_rehydration_is_bounded_content_checked_and_binding_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
            )
            result = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-large",
            )
            assert result is not None
            page = json.loads(store.retrieve(result.artifact_id, offset=5, limit=256))
            self.assertEqual(page["schema"], PAGE_SCHEMA)
            self.assertEqual(page["returned_chars"], 256)
            self.assertTrue(page["has_more"])
            self.assertEqual(page["content"], result.content[5:261])
            self.assertFalse(page["mutation_performed"])

            other_task = OperationalArtifactStore(
                directory,
                task_id="task-b",
                session_id="session-a",
            )
            with self.assertRaisesRegex(ToolResultLifecycleError, "not found"):
                other_task.retrieve(result.artifact_id)
            other_session = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-b",
            )
            with self.assertRaisesRegex(ToolResultLifecycleError, "not found"):
                other_session.retrieve(result.artifact_id)

    def test_expiry_and_corruption_fail_closed(self) -> None:
        now = [1_000.0]
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
                clock=lambda: now[0],
                ttl_seconds=10,
            )
            result = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-large",
            )
            assert result is not None
            now[0] = 1_005.0
            repeated = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-repeat",
            )
            assert repeated is not None
            self.assertEqual(repeated.expires_at, result.expires_at)
            now[0] = 1_011.0
            with self.assertRaisesRegex(ToolResultLifecycleError, "expired"):
                store.retrieve(result.artifact_id)

            replacement = store.externalize(
                _large_result("TOKEN400-SECOND"),
                tool_name="tool-a",
                tool_call_id="call-second",
            )
            assert replacement is not None
            path = store.root / f"{replacement.artifact_id}.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["content"] += "tampered"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ToolResultLifecycleError, "content is invalid"):
                store.retrieve(replacement.artifact_id)

    def test_plugin_artifact_tool_uses_environment_binding_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
            )
            result = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-large",
            )
            assert result is not None
            with patch.dict(
                os.environ,
                {
                    "HERMES_HOME": directory,
                    "GAUNTLET_TASK_ID": "task-a",
                    "GAUNTLET_SESSION_ID": "session-a",
                },
                clear=False,
            ):
                page = json.loads(
                    gauntlet_plugin._artifact_get(
                        {"artifact_id": result.artifact_id, "offset": 0, "limit": 128}
                    )
                )
            self.assertEqual(page["schema"], PAGE_SCHEMA)
            self.assertEqual(page["returned_chars"], 128)
            self.assertEqual(page["authority"], "OPERATIONAL_ONLY")

    def test_json_escaped_secrets_are_redacted_without_breaking_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
            )
            source = json.dumps(
                {
                    "claim": "start\ntoken=json-escaped-secret\nend",
                    "payload": "x" * 9_000,
                }
            )
            result = store.externalize(
                source,
                tool_name="tool-a",
                tool_call_id="call-json-secret",
            )
            assert result is not None
            sanitized = json.loads(result.content)
            self.assertNotIn("json-escaped-secret", result.content)
            self.assertIn("token=<redacted>", sanitized["claim"])

    def test_result_above_hard_storage_bound_is_rejected_without_raw_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
                max_artifact_chars=9_000,
            )
            with self.assertRaisesRegex(ToolResultLifecycleError, "artifact bound"):
                store.externalize(
                    "z" * 9_001,
                    tool_name="tool-a",
                    tool_call_id="call-too-large",
                )
            self.assertEqual(list(store.root.glob("art_*.json")), [])
            self.assertEqual(store.metrics()["rejected_results"], 1)


class FirstVisibilityTests(unittest.TestCase):
    def test_raw_content_is_request_only_for_first_provider_call(self) -> None:
        plan = build_sparse_context_plan(
            session_binding_id="session-a",
            profile_name="gauntlet-lean.v1",
        )
        engine = gauntlet_plugin._GauntletSparseEngineBase()
        engine.configure_gauntlet_context(plan)
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalArtifactStore(
                directory,
                task_id="task-a",
                session_id="session-a",
            )
            result = store.externalize(
                _large_result(),
                tool_name="tool-a",
                tool_call_id="call-large",
            )
            assert result is not None
            messages = [
                {"role": "system", "content": "stable"},
                {"role": "user", "content": "inspect the result"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-large",
                            "type": "function",
                            "function": {"name": "tool-a", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-large",
                    "content": result.reference,
                },
            ]
            original_reference = messages[-1]["content"]
            engine.register_externalized_result(result.artifact_id, result.content)

            selected = engine.select_context(messages)
            self.assertIsNotNone(selected)
            assert selected is not None
            current = json.loads(selected[-1]["content"])
            self.assertEqual(current["schema"], CURRENT_CALL_SCHEMA)
            self.assertIn("TOKEN400-RAW-MARKER", current["content"])
            self.assertEqual(current["artifact"]["artifact_id"], result.artifact_id)
            self.assertEqual(messages[-1]["content"], original_reference)
            self.assertTrue(engine.last_selection["tool_result_first_visibility"])
            self.assertFalse(engine.last_selection["persisted_transcript_mutated"])

            engine.acknowledge_provider_response()
            self.assertIsNone(engine.select_context(messages))
            self.assertEqual(messages[-1]["content"], original_reference)


if __name__ == "__main__":
    unittest.main()
