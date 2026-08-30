"""TOKEN-200/300/500 compiler, sparse selection, and JIT isolation gates."""

from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

from gauntlet_host import gauntlet_plugin
from gauntlet_host.constants import GAUNTLET_ACTIVE_TOOLS
from gauntlet_host.lean_context import (
    LeanContextError,
    build_sparse_context_plan,
    status_tool_definitions,
    validate_sparse_context_plan,
)
from gauntlet_host.tool_surface import (
    ToolSurfaceError,
    build_tool_surface_plan,
    compile_live_tool_surface,
)

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "hermes-agent"


def _route() -> dict[str, object]:
    return {
        "content_hash": "a" * 64,
        "minimum_capability_bundle": ["REASONING"],
        "missing_capabilities": [],
    }


def _snippet(content: str = "Use the bounded selected procedure.") -> dict[str, str]:
    return {
        "snippet_id": "skill-selected-procedure",
        "kind": "skill",
        "provenance": "fixture://selected-skill/v1",
        "source_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "authority": "CONTEXT_ONLY",
    }


class ToolSurfaceCompilerTests(unittest.TestCase):
    def test_fresh_compiler_uses_exact_required_catalog_and_ignores_extras(self) -> None:
        definitions = status_tool_definitions()
        plan = build_tool_surface_plan(definitions, _route())
        live = list(definitions)
        live.append(
            {
                "type": "function",
                "function": {
                    "name": "unauthorized_extra",
                    "description": "must not widen the active manifest",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )

        compiled = compile_live_tool_surface(
            plan,
            live,
            requested_toolsets=("gauntlet",),
        )

        self.assertEqual(set(compiled.tool_names), set(GAUNTLET_ACTIVE_TOOLS))
        self.assertEqual(compiled.ignored_available_names, ("unauthorized_extra",))
        self.assertFalse(compiled.silent_widening_performed)
        self.assertEqual(compiled.active_manifest_hash, plan["planned_manifest_hash"])

    def test_missing_required_tool_and_uncompiled_toolset_fail_closed(self) -> None:
        definitions = status_tool_definitions()
        plan = build_tool_surface_plan(definitions, _route())
        with self.assertRaisesRegex(ToolSurfaceError, "fresh availability omitted"):
            compile_live_tool_surface(
                plan,
                definitions[:-1],
                requested_toolsets=("gauntlet",),
            )
        with self.assertRaisesRegex(ToolSurfaceError, "exceeded"):
            compile_live_tool_surface(
                plan,
                definitions,
                requested_toolsets=("gauntlet", "terminal"),
            )


class SparseContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._inserted = str(VENDOR) not in sys.path
        if cls._inserted:
            sys.path.insert(0, str(VENDOR))

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._inserted and sys.path and sys.path[0] == str(VENDOR):
            sys.path.pop(0)

    def test_long_history_selects_relevant_units_and_preserves_active_closure(self) -> None:
        plan = build_sparse_context_plan(
            session_binding_id="gauntlet-session-binding-test",
            profile_name="gauntlet-lean.v1",
            selected_snippets=[_snippet()],
        )
        engine = gauntlet_plugin._build_sparse_context_engine()
        engine.configure_gauntlet_context(plan)

        messages: list[dict[str, object]] = [{"role": "system", "content": "stable-system-prefix"}]
        for index in range(8):
            topic = "needle-capability " if index == 1 else f"filler{index} "
            messages.extend(
                [
                    {"role": "user", "content": topic + ("x" * 1_200)},
                    {"role": "assistant", "content": f"answer-{index}"},
                ]
            )
        messages.extend(
            [
                {"role": "user", "content": "Use needle-capability now."},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-active",
                            "type": "function",
                            "function": {
                                "name": "gauntlet_task_status_compact",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-active",
                    "content": "bounded-result",
                },
            ]
        )
        original = copy.deepcopy(messages)

        selected = engine.select_context(messages)

        self.assertIsInstance(selected, list)
        assert selected is not None
        rendered = "\n".join(str(message.get("content", "")) for message in selected)
        self.assertEqual(messages, original)
        self.assertEqual(selected[0], messages[0])
        self.assertIn("needle-capability", rendered)
        self.assertIn("filler7", rendered)
        self.assertNotIn("filler0", rendered)
        self.assertIn("Use the bounded selected procedure.", rendered)
        self.assertIn("CONTEXT_ONLY", rendered)
        self.assertEqual(selected[-2]["tool_calls"][0]["id"], "call-active")
        self.assertEqual(selected[-1]["tool_call_id"], "call-active")
        self.assertTrue(engine.last_selection["activated"])
        self.assertTrue(engine.last_selection["tool_closure_preserved"])
        self.assertFalse(engine.last_selection["persisted_transcript_mutated"])
        self.assertLess(
            engine.last_selection["selected_chars"], engine.last_selection["input_chars"]
        )

    def test_short_history_is_byte_shape_preserving_without_jit(self) -> None:
        plan = build_sparse_context_plan(
            session_binding_id="gauntlet-session-binding-short",
            profile_name="gauntlet-lean.v1",
        )
        engine = gauntlet_plugin._build_sparse_context_engine()
        engine.configure_gauntlet_context(plan)
        messages = [
            {"role": "system", "content": "stable"},
            {"role": "user", "content": "short turn"},
        ]
        self.assertIsNone(engine.select_context(messages))
        self.assertEqual(engine.last_selection["reason"], "below_activation_threshold")

    def test_jit_plan_is_task_profile_bound_and_non_authoritative(self) -> None:
        plan = build_sparse_context_plan(
            session_binding_id="gauntlet-session-binding-isolated",
            profile_name="gauntlet-lean.v1",
            selected_snippets=[_snippet()],
        )
        validated = validate_sparse_context_plan(
            plan,
            session_binding_id="gauntlet-session-binding-isolated",
            profile_name="gauntlet-lean.v1",
        )
        self.assertFalse(validated["snippet_authority_allowed"])
        with self.assertRaisesRegex(LeanContextError, "task binding"):
            validate_sparse_context_plan(
                plan,
                session_binding_id="different-session-binding",
                profile_name="gauntlet-lean.v1",
            )


if __name__ == "__main__":
    unittest.main()
