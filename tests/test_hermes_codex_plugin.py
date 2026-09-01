from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "hermes-gauntlet"
SCRIPT = PLUGIN / "scripts" / "hermes_gauntlet.py"


def run_helper(*arguments: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


class HermesCodexPluginTests(unittest.TestCase):
    def test_manifest_exposes_governed_hermes_and_foil(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "hermes-gauntlet")
        self.assertRegex(manifest["version"], re.compile(r"^0\.2\.0(?:\+codex\.\d+)?$"))
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertIn("foil", manifest["keywords"])
        self.assertTrue(
            any("FOIL" in prompt for prompt in manifest["interface"]["defaultPrompt"])
        )
        self.assertTrue(
            (PLUGIN / "skills" / "governed-hermes" / "SKILL.md").is_file()
        )
        foil_skill = (PLUGIN / "skills" / "hermes-foil" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: hermes-foil", foil_skill)
        self.assertIn("ADAPTATION", foil_skill)

    def test_repository_plugin_has_no_private_workstation_path(self) -> None:
        plugin_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PLUGIN.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        self.assertNotIn(r"C:\Users", plugin_text)
        self.assertNotIn("tombl", plugin_text.casefold())

    def test_foil_dry_run_forces_adaptation_kind_and_alias(self) -> None:
        result = run_helper(
            "foil",
            "--dry-run",
            "--model",
            "test/model",
            "--provider",
            "test-provider",
            "--prompt",
            "adapt to the evidence",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--profile governed", result.stdout)
        self.assertIn("--kind ADAPTATION", result.stdout)
        self.assertIn('"/foil adapt to the evidence"', result.stdout)

    def test_normal_start_does_not_invent_adaptation_kind(self) -> None:
        result = run_helper(
            "start",
            "--dry-run",
            "--model",
            "test/model",
            "--provider",
            "test-provider",
            "--prompt",
            "ordinary governed work",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--kind ADAPTATION", result.stdout)
        self.assertNotIn("/foil", result.stdout)

    def test_foil_command_does_not_treat_a_longer_word_as_the_alias(self) -> None:
        result = run_helper(
            "foil",
            "--dry-run",
            "--model",
            "test/model",
            "--provider",
            "test-provider",
            "--prompt",
            "/foiled is not the alias",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"/foil /foiled is not the alias"', result.stdout)

    def test_continue_uses_only_public_task_handle(self) -> None:
        result = run_helper(
            "continue",
            "--dry-run",
            "--task-id",
            "task-example",
            "--model",
            "test/model",
            "--provider",
            "test-provider",
            "--prompt",
            "/foil continue",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--task-id task-example", result.stdout)
        self.assertNotIn("--kind", result.stdout)
        self.assertNotIn("session-id", result.stdout)

    def test_release_requires_explicit_confirmation(self) -> None:
        result = run_helper("release", "--task-id", "task-example", "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit canonical mutation", result.stderr)
        self.assertNotIn("soul_runtime.py", result.stdout)

    def test_doctor_reports_credential_name_but_not_value(self) -> None:
        secret = "SECRET_CANARY_DO_NOT_PRINT"
        result = run_helper(
            "doctor", "--json", extra_env={"OPENAI_API_KEY": secret}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertNotIn(secret, output)
        report = json.loads(result.stdout)
        self.assertIn(
            "OPENAI_API_KEY", report["provider_environment_variables_present"]
        )


if __name__ == "__main__":
    unittest.main()
