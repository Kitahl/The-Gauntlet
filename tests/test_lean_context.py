"""TOKEN-100/600 lean profile, compact context, and parent prefetch contracts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gauntlet_host import gauntlet_plugin
from gauntlet_host.lean_context import (
    ACTIVE_MANIFEST_REVISION,
    LeanContext,
    drop_stale_lean_context_sidecars,
    prefetch_lean_context,
    status_tool_definitions,
)
from gauntlet_host.runtime_profile import prepare_runtime_profile

ROOT = Path(__file__).resolve().parents[1]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fixture_root(base: Path, *, obligations: int = 1) -> tuple[Path, str, str]:
    root = base / "fixture"
    (root / "gauntlet_host").mkdir(parents=True)
    shutil.copy2(
        ROOT / "gauntlet_host" / "module_cli.py",
        root / "gauntlet_host" / "module_cli.py",
    )
    shutil.copytree(ROOT / "tools", root / "tools")
    (root / ".gauntlet.json").write_text(
        json.dumps({"state_dir": ".egrt/state", "runtime": {"enabled": True}}),
        encoding="utf-8",
    )
    task_id = "task-token-lean"
    claim = "exact claim must stay out of compact status"
    rows = [
        {
            "obligation_id": f"obl-token-{index:02d}",
            "kind": "DISCOVERY",
            "claim": f"{claim} {index}",
            "load_bearing": True,
            "required_module": "space",
            "metadata": {},
        }
        for index in range(obligations)
    ]
    task = {
        "schema": "egrt.runtime.v1",
        "task_id": task_id,
        "goal_hash": _canonical_hash("lean fixture"),
        "active": True,
        "released": False,
        "obligations": rows,
        "metadata": {},
    }
    task["content_hash"] = _canonical_hash(task)
    tasks = root / ".egrt" / "state" / "runtime" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / f"{task_id}.json").write_text(
        json.dumps(task, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return root, task_id, rows[0]["obligation_id"]


def _state_digest(root: Path) -> str:
    records: list[tuple[str, str]] = []
    state = root / ".egrt"
    for path in sorted(item for item in state.rglob("*") if item.is_file()):
        records.append(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return _canonical_hash(records)


class LeanContextTests(unittest.TestCase):
    def test_status_manifest_matches_registered_plugin_contract(self) -> None:
        definitions = status_tool_definitions()
        plugin = [
            (
                "gauntlet_task_status_compact",
                gauntlet_plugin._TASK_COMPACT_SCHEMA,
            ),
            ("gauntlet_obligation_get", gauntlet_plugin._OBLIGATION_SCHEMA),
            ("gauntlet_release_status", gauntlet_plugin._RELEASE_SCHEMA),
        ]
        self.assertEqual(len(definitions), len(plugin))
        for definition, (name, schema) in zip(definitions, plugin, strict=True):
            function = definition["function"]
            self.assertEqual(function["name"], name)
            self.assertEqual(function["description"], schema["description"])
            self.assertEqual(function["parameters"], schema["parameters"])

    def test_only_exact_historical_lean_sidecars_are_dropped(self) -> None:
        clean = "clean turn"
        injected = (
            clean
            + "\n\n[GAUNTLET LEAN VOLATILE CONTEXT]\ncurrent\n"
            + "[/GAUNTLET LEAN VOLATILE CONTEXT]"
        )
        history = [
            {"role": "user", "content": clean, "api_content": injected},
            {
                "role": "user",
                "content": "other",
                "api_content": "other\n\nunrelated sidecar",
            },
            {"role": "assistant", "content": "ok", "api_content": injected},
        ]
        self.assertEqual(drop_stale_lean_context_sidecars(history), 1)
        self.assertNotIn("api_content", history[0])
        self.assertIn("api_content", history[1])
        self.assertIn("api_content", history[2])

    def test_explicit_isolated_lean_profile_disables_ambient_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = prepare_runtime_profile(Path(directory) / "runtime")
            config = Path(profile.config_path).read_text(encoding="utf-8")
            self.assertEqual(profile.profile_name, "gauntlet-lean.v1")
            self.assertFalse(profile.memory_enabled)
            self.assertFalse(profile.user_profile_enabled)
            self.assertFalse(profile.skills_project_discovery)
            self.assertFalse(profile.execution_guidance_enabled)
            self.assertFalse(profile.task_completion_guidance_enabled)
            self.assertTrue(profile.parallel_tool_call_guidance_enabled)
            self.assertFalse(profile.coding_context_enabled)
            self.assertIn("memory_enabled: false", config)
            self.assertIn("user_profile_enabled: false", config)
            self.assertIn("project_discovery: false", config)
            self.assertIn("execution_guidance: false", config)
            self.assertIn("parallel_tool_call_guidance: true", config)
            self.assertIn("coding_context: 'off'", config)

    def test_parent_prefetch_is_compact_content_addressed_and_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, task_id, obligation_id = _fixture_root(base, obligations=32)
            runtime = base / "runtime"
            before = _state_digest(root)
            context = prefetch_lean_context(
                task_id=task_id,
                repository_root=root,
                runtime_home=runtime,
            )
            after = _state_digest(root)

            self.assertEqual(before, after)
            self.assertEqual(context.active_manifest_revision, ACTIVE_MANIFEST_REVISION)
            self.assertEqual(
                set(context.route_capsule()),
                {
                    "route_hash",
                    "route_revision",
                    "primary_mode",
                    "selected_capability_ids",
                    "required_verifier_ids",
                    "missing_capability_ids",
                    "should_stop",
                },
            )
            metrics = context.capsule_metrics()
            self.assertLessEqual(metrics["route_estimated_tokens"], 512)
            self.assertLessEqual(metrics["status_estimated_tokens"], 1024)
            self.assertEqual(len(context.compact_status["obligations"]), 32)
            self.assertNotIn(
                "exact claim must stay out",
                json.dumps(context.compact_status),
            )
            record = Path(context.route_record_path)
            self.assertTrue(record.is_file())
            self.assertEqual(record.stem, context.foil_route["content_hash"])
            self.assertEqual(json.loads(record.read_text()), context.foil_route)

            restored = LeanContext.from_metadata(task_id, context.to_metadata())
            self.assertEqual(restored.route_capsule(), context.route_capsule())
            injected = restored.inject("work the current task")
            self.assertTrue(injected.startswith("work the current task\n\n"))
            self.assertIn("Parent-prefetched canonical status", injected)

            environment = dict(os.environ)
            environment["GAUNTLET_TASK_ID"] = task_id
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "gauntlet_host" / "module_cli.py"),
                    "--root",
                    str(root),
                    "obligation-get",
                    "--obligation-id",
                    obligation_id,
                ],
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            detail = json.loads(completed.stdout)
            self.assertEqual(detail["obligation"]["obligation_id"], obligation_id)
            self.assertIn("exact claim must stay out", detail["obligation"]["claim"])
            self.assertEqual(len(detail["obligation"]["claim_hash"]), 64)
            self.assertEqual(before, _state_digest(root))

            with patch.dict(
                os.environ,
                {
                    "GAUNTLET_TASK_ID": task_id,
                    "GAUNTLET_REPO_ROOT": str(root),
                    "GAUNTLET_MODULE_CLI": str(root / "gauntlet_host" / "module_cli.py"),
                },
                clear=False,
            ):
                compact_tool = json.loads(gauntlet_plugin._task_status_compact({}))
                detail_tool = json.loads(
                    gauntlet_plugin._obligation_get({"obligation_id": obligation_id})
                )
            self.assertEqual(compact_tool["status"], "OK")
            self.assertEqual(
                compact_tool["compact_status"]["task_id"],
                task_id,
            )
            self.assertEqual(detail_tool["status"], "OK")
            self.assertEqual(
                detail_tool["obligation"]["obligation_id"],
                obligation_id,
            )
            self.assertEqual(before, _state_digest(root))


if __name__ == "__main__":
    unittest.main()
