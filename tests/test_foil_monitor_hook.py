"""Hook integration tests for the event-driven Mirror/FOIL activation monitor."""

from __future__ import annotations

import ast
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import foil_hook as hook  # noqa: E402
import foil_profile as profile_runtime  # noqa: E402


class FoilMonitorHookTests(unittest.TestCase):
    def _run_prompt(self, payload: dict[str, object], mode: str) -> str:
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"FOIL_AUTO_MODE": mode}, clear=False),
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            redirect_stdout(output),
        ):
            self.assertEqual(hook.prompt(), 0)
        return output.getvalue()

    def test_legacy_remains_the_default_and_preserves_current_task_emission(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            environment = {
                "EGR_FOIL_PROFILE_DIR": directory,
                "CLAUDE_PROJECT_DIR": directory,
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch(
                    "sys.stdin",
                    io.StringIO(json.dumps({"prompt": "a causal inference task"})),
                ),
                redirect_stdout(output),
            ):
                self.assertEqual(hook.prompt(), 0)
            self.assertIn("FOIL_CURRENT_TASK", output.getvalue())

    def test_off_and_invalid_modes_emit_nothing_and_never_load_a_profile(self):
        for mode in ("off", "not-a-mode"):
            with self.subTest(mode=mode):
                with (
                    patch.object(profile_runtime, "load") as load,
                    patch.object(profile_runtime, "bootstrap_active") as bootstrap,
                ):
                    output = self._run_prompt({"prompt": "/foil"}, mode)
                self.assertEqual(output, "")
                load.assert_not_called()
                bootstrap.assert_not_called()

    def test_smart_inactive_and_session_paths_do_no_profile_io(self):
        with (
            patch.object(profile_runtime, "load") as load,
            patch.object(hook, "_monitored") as monitored,
        ):
            self.assertEqual(self._run_prompt({"prompt": "ordinary request"}, "smart"), "")
            with patch.dict(os.environ, {"FOIL_AUTO_MODE": "smart"}, clear=False):
                self.assertEqual(hook.session(), 0)
        load.assert_not_called()
        monitored.assert_not_called()

    def test_observe_computes_but_emits_and_writes_nothing(self):
        profile = profile_runtime.new_profile("subject")
        with (
            patch.object(profile_runtime, "load", return_value=profile) as load,
            patch.object(profile_runtime, "save") as save,
        ):
            output = self._run_prompt({"prompt": "please use foil"}, "observe")
        self.assertEqual(output, "")
        load.assert_called_once()
        save.assert_not_called()

    def test_smart_explicit_activation_is_bounded_and_read_only(self):
        profile = profile_runtime.new_profile("subject")
        profile["goals"] = ["G" * 50_000]
        with (
            patch.object(profile_runtime, "load", return_value=profile) as load,
            patch.object(profile_runtime, "save") as save,
        ):
            output = self._run_prompt({"prompt": "please use foil"}, "smart")
        self.assertTrue(output)
        self.assertLessEqual(len(output.strip()), hook.SMART_CONTEXT_BUDGET)
        self.assertEqual(output.count("</FOIL_PROFILE>"), 1)
        load.assert_called_once()
        save.assert_not_called()

    def test_smart_task_relevance_uses_canonical_requirement_and_profile_gap(self):
        profile = profile_runtime.new_profile("subject")
        for _ in range(4):
            profile_runtime.observe(
                profile,
                "causal_reasoning",
                "incorrect",
                "A0_INDEPENDENT",
                verified=True,
                verifier="rubric",
            )
        row = profile["domains"]["causal_reasoning"]
        row["transfer_confirmations"] = 1
        self.assertEqual(row["classification"], "POSSIBLE_GAP")
        payload = {
            "prompt": "review this claim",
            "foil_task_requirements": [
                {
                    "requirement_id": "R1",
                    "capability": "causal_reasoning",
                    "importance": "HIGH",
                    "required_level": "STRONG",
                }
            ],
        }
        with patch.object(profile_runtime, "load", return_value=profile) as load:
            output = self._run_prompt(payload, "smart")
        self.assertIn("<FOIL_PROFILE", output)
        load.assert_called_once()

    def test_malformed_requirement_stands_down_before_profile_load(self):
        payload = {
            "prompt": "ordinary request",
            "foil_task_requirements": [{"capability": "causal_reasoning"}],
        }
        with patch.object(profile_runtime, "load") as load:
            self.assertEqual(self._run_prompt(payload, "smart"), "")
        load.assert_not_called()

    def test_hook_has_no_gauntlet_or_mastermind_runtime_import(self):
        source = Path(hook.__file__).read_text(encoding="utf-8")
        imports = {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(any(name.startswith(("gauntlet", "mastermind")) for name in imports))


if __name__ == "__main__":
    unittest.main()
