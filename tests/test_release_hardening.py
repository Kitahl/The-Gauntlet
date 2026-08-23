from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*-\s+uses:\s+([^\s#]+)", re.MULTILINE)
GITLEAKS_IMAGE = (
    "ghcr.io/gitleaks/gitleaks@"
    "sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)


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

    def test_secret_gate_scans_full_history_with_digest_pinned_image(self) -> None:
        security = (ROOT / ".github" / "workflows" / "security.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("fetch-depth: 0", security)
        self.assertIn(GITLEAKS_IMAGE, security)
        self.assertIn('--log-opts="--full-history --all"', security)
        self.assertNotIn("gitleaks/gitleaks-action@", security)

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
