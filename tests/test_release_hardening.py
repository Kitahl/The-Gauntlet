from __future__ import annotations

import hashlib
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
LOCK_SHA256 = "c691104c36101259f69f27d4e09ede3dc64b08c326b0ca8fa2021a1c2cacfd12"


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

    def test_release_workflows_are_read_only(self) -> None:
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            self.assertNotIn("contents: write", text, workflow.name)

    def test_secret_gate_scans_full_history_with_digest_pinned_image(self) -> None:
        security = (ROOT / ".github" / "workflows" / "security.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("fetch-depth: 0", security)
        self.assertIn(GITLEAKS_IMAGE, security)
        self.assertIn('--log-opts="--full-history --all"', security)
        self.assertNotIn("gitleaks/gitleaks-action@", security)

    def test_hash_lock_is_exact_and_enforced(self) -> None:
        lock = ROOT / "requirements-lock.txt"
        self.assertTrue(lock.is_file())
        # Text-mode reads normalize CRLF to LF on Windows. The release identity is
        # the canonical LF form enforced by .gitattributes, not platform checkout bytes.
        canonical = lock.read_text(encoding="utf-8").encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), LOCK_SHA256)
        text = canonical.decode("utf-8")
        for pin in [
            "requests==2.34.2",
            "rapidfuzz==3.14.5",
            "playwright==1.62.0",
            "ruff==0.16.3",
        ]:
            self.assertIn(pin, text)
        self.assertIn("--hash=sha256:", text)

        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("requirements-lock.txt text eol=lf", attributes)
        self.assertIn("requirements-lock.in text eol=lf", attributes)

        security = (ROOT / ".github" / "workflows" / "security.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("git diff --exit-code -- requirements-lock.txt", security)
        self.assertIn(LOCK_SHA256, security)
        self.assertIn("--require-hashes -r requirements-lock.txt", security)

        for name in ["validate.yml", "portability.yml"]:
            workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("--require-hashes -r requirements-lock.txt", workflow)

    def test_portability_has_stable_required_gate(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "portability.yml").read_text(encoding="utf-8")
        self.assertNotIn("    paths:\n", workflow)
        self.assertIn("name: Runtime portability gate", workflow)
        self.assertIn("needs: [runtime]", workflow)
        self.assertIn("if: ${{ always() }}", workflow)

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
