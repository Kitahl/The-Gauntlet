from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*-\s+uses:\s+([^\s#]+)", re.MULTILINE)


class ReleaseHardeningTests(unittest.TestCase):
    def test_external_github_actions_are_pinned_to_full_shas(self) -> None:
        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for workflow in workflows:
            text = workflow.read_text(encoding="utf-8")
            for spec in USES.findall(text):
                if spec.startswith("./"):
                    continue
                self.assertIn("@", spec, f"unversioned action in {workflow.name}: {spec}")
                _, ref = spec.rsplit("@", 1)
                self.assertRegex(
                    ref,
                    FULL_SHA,
                    f"action is not pinned by immutable full SHA in {workflow.name}: {spec}",
                )

    def test_generic_secret_and_environment_files_are_ignored(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for required in [
            ".mastermind/",
            "mastermind/",
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            ".venv/",
            ".egrt/",
        ]:
            self.assertIn(required, ignored)

    def test_external_model_egress_is_documented(self) -> None:
        runtime = (ROOT / "docs" / "RUNTIME_SETUP.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        for text in [runtime, security]:
            self.assertIn("OpenRouter", text)
            self.assertRegex(text, re.compile(r"transmit", re.IGNORECASE))

    def test_scout_version_is_derived_from_release_file(self) -> None:
        scout = (ROOT / "tools" / "scout.py").read_text(encoding="utf-8")
        self.assertIn('/ "VERSION"', scout)
        self.assertNotIn("Research-Toolkit/0.2", scout)


if __name__ == "__main__":
    unittest.main()
