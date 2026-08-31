"""Governed full-Hermes profile capability and isolation contracts."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gauntlet_host.constants import (
    GAUNTLET_ACTIVE_TOOLS,
    GOVERNED_PROFILE_NAME,
    HERMES_CLI_TOOLSET,
    LEAN_PROFILE_NAME,
    REPO_ROOT,
)
from gauntlet_host.finalizer import finalize_worker_result
from gauntlet_host.ipc import (
    IPCContractError,
    RuntimeRequest,
    RuntimeResult,
    WorkerOperation,
    WorkerStatus,
    decode_request,
    encode_request,
)
from gauntlet_host.launcher import _profile_toolsets
from gauntlet_host.lean_context import (
    build_sparse_context_plan,
    validate_sparse_context_plan,
)
from gauntlet_host.phase7_worker import _tool_definition_names
from gauntlet_host.runtime_profile import _read_config, prepare_runtime_profile

sys.path.insert(0, str(REPO_ROOT / "tools"))

from egrt_types import ObligationKind  # noqa: E402
from foil_runtime_bridge import record_prompt_adaptation  # noqa: E402
from soul_runtime import add_obligation, start_task  # noqa: E402


class GovernedRuntimeTests(unittest.TestCase):
    def test_governed_profile_inherits_normal_config_and_forces_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {}, clear=False
        ):
            base = Path(directory)
            inherited = base / "normal-config.yaml"
            inherited.write_text(
                json.dumps(
                    {
                        "model": {"default": "test/model", "provider": "test"},
                        "mcp_servers": {
                            "local-docs": {
                                "command": "docs-server",
                                "args": ["--stdio"],
                            }
                        },
                        "plugins": {
                            "enabled": ["normal-plugin"],
                            "disabled": ["gauntlet"],
                        },
                        "skills": {
                            "external_dirs": [str(base / "shared-skills")],
                            "trusted_project_dirs": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile = prepare_runtime_profile(
                base / "governed",
                profile_name=GOVERNED_PROFILE_NAME,
                base_config_path=inherited,
            )
            config = _read_config(Path(profile.config_path))

            self.assertEqual(profile.profile_name, GOVERNED_PROFILE_NAME)
            self.assertEqual(profile.context_engine_name, "compressor")
            self.assertTrue(profile.memory_enabled)
            self.assertTrue(profile.user_profile_enabled)
            self.assertTrue(profile.skills_project_discovery)
            self.assertTrue(profile.context_files_enabled)
            self.assertTrue(profile.environment_probe_enabled)
            self.assertTrue(profile.verify_on_stop_enabled)
            self.assertTrue(profile.mcp_discovery_enabled)
            self.assertTrue(profile.delegation_enabled)
            self.assertFalse(profile.auto_release_enabled)
            self.assertEqual(profile.max_iterations, 64)
            self.assertEqual(
                profile.inherited_config_sha256,
                hashlib.sha256(inherited.read_bytes()).hexdigest(),
            )
            self.assertEqual(config["toolsets"], [HERMES_CLI_TOOLSET, "gauntlet"])
            self.assertIn("local-docs", config["mcp_servers"])
            self.assertEqual(config["memory"]["memory_enabled"], True)
            self.assertEqual(config["memory"]["user_profile_enabled"], True)
            self.assertEqual(config["agent"]["coding_context"], "auto")
            self.assertEqual(config["agent"]["environment_probe"], True)
            self.assertEqual(config["agent"]["verify_on_stop"], True)
            self.assertEqual(config["auxiliary"]["free_only"], True)
            self.assertEqual(
                config["auxiliary"]["background_review"]["max_input_tokens"],
                60_000,
            )
            self.assertIn(str(REPO_ROOT / "skills"), config["skills"]["external_dirs"])
            self.assertIn(str(REPO_ROOT), config["skills"]["trusted_project_dirs"])
            self.assertIn("normal-plugin", config["plugins"]["enabled"])
            self.assertIn("gauntlet", config["plugins"]["enabled"])
            self.assertNotIn("gauntlet", config["plugins"]["disabled"])

    def test_lean_profile_remains_the_exact_compatibility_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {}, clear=False
        ):
            profile = prepare_runtime_profile(Path(directory) / "lean")
            self.assertEqual(profile.profile_name, LEAN_PROFILE_NAME)
            self.assertFalse(profile.memory_enabled)
            self.assertFalse(profile.context_files_enabled)
            self.assertFalse(profile.mcp_discovery_enabled)
            self.assertFalse(profile.delegation_enabled)
            self.assertFalse(profile.auto_release_enabled)
            self.assertEqual(profile.max_iterations, 8)
            self.assertEqual(_profile_toolsets((), LEAN_PROFILE_NAME), ("gauntlet",))

    def test_governed_toolsets_add_normal_hermes_and_preserve_requested_dynamic_sets(self) -> None:
        self.assertEqual(
            _profile_toolsets(("project-mcp",), GOVERNED_PROFILE_NAME),
            (HERMES_CLI_TOOLSET, "gauntlet", "project-mcp"),
        )
        definitions = [
            {"type": "function", "function": {"name": name}}
            for name in (*GAUNTLET_ACTIVE_TOOLS, "terminal", "delegate_task", "mcp_lookup")
        ]
        names = _tool_definition_names(definitions)
        self.assertTrue(set(GAUNTLET_ACTIVE_TOOLS).issubset(names))
        self.assertIn("delegate_task", names)
        self.assertIn("mcp_lookup", names)

    def test_ipc_binds_the_runtime_profile_and_rejects_unknown_profiles(self) -> None:
        request = RuntimeRequest(
            request_id="request-governed",
            task_id="task-governed",
            operation=WorkerOperation.RUN,
            runtime_profile=GOVERNED_PROFILE_NAME,
            prompt="work",
        )
        self.assertEqual(
            decode_request(encode_request(request)).runtime_profile,
            GOVERNED_PROFILE_NAME,
        )
        value = json.loads(encode_request(request))
        value["runtime_profile"] = "untrusted-profile"
        with self.assertRaisesRegex(IPCContractError, "runtime_profile"):
            decode_request(json.dumps(value))

    def test_governed_context_plan_is_task_bound_but_uses_native_engine(self) -> None:
        snippet_content = "<FOIL_PROFILE>bounded persistent context</FOIL_PROFILE>"
        snippet = {
            "snippet_id": "foil-profile-test",
            "kind": "profile",
            "provenance": "test",
            "source_hash": hashlib.sha256(snippet_content.encode()).hexdigest(),
            "content": snippet_content,
            "authority": "CONTEXT_ONLY",
        }
        plan = build_sparse_context_plan(
            session_binding_id="gauntlet-session-governed",
            profile_name=GOVERNED_PROFILE_NAME,
            selected_snippets=[snippet],
        )
        self.assertEqual(plan["engine"], "native")
        self.assertEqual(plan["selected_snippets"], [snippet])
        self.assertEqual(
            validate_sparse_context_plan(
                plan,
                session_binding_id="gauntlet-session-governed",
                profile_name=GOVERNED_PROFILE_NAME,
            ),
            plan,
        )
        with self.assertRaisesRegex(Exception, "task binding and runtime profile"):
            validate_sparse_context_plan(
                plan,
                session_binding_id="other-session",
                profile_name=GOVERNED_PROFILE_NAME,
            )

    def test_explicit_foil_task_binding_wins_over_global_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = start_task(root, "first")
            obligation = add_obligation(
                root,
                first.task_id,
                ObligationKind.ADAPTATION,
                "adapt this task",
            )
            second = start_task(root, "second")
            profile = {
                "id": "test-profile",
                "schema": "foil.profile.v1",
                "profile_status": "active",
                "domains": {},
                "calibration": {},
                "privacy": {"raw_prompts_stored": False},
            }
            receipts = record_prompt_adaptation(
                root,
                profile,
                ["software"],
                ["verification"],
                prompt_text="/foil adapt this task",
                foil_alias=True,
                task_id=first.task_id,
            )
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0].task_id, first.task_id)
            self.assertEqual(receipts[0].obligation_id, obligation.obligation_id)
            self.assertNotEqual(receipts[0].task_id, second.task_id)

    def test_cleared_finalization_reports_eligibility_without_releasing_task(self) -> None:
        worker = RuntimeResult(
            request_id="request-clear",
            task_id="task-clear",
            status=WorkerStatus.OK,
            event="worker.turn_completed",
            payload={"final_response": "done"},
        )
        gate = {
            "task_released": False,
            "release": {
                "verdict": "CLEARED",
                "release_eligible": True,
                "detail": {"task_id": "task-clear", "obligations": []},
            },
        }
        with patch("gauntlet_host.finalizer._read_release_gate", return_value=gate):
            result = finalize_worker_result(Path("."), "task-clear", worker)
        self.assertTrue(result.accepted)
        self.assertTrue(result.release_eligible)
        self.assertFalse(result.task_release_performed)
        self.assertFalse(result.canonical_receipt_created)


if __name__ == "__main__":
    unittest.main()
