from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_verifiers import (  # noqa: E402
    DEFAULT_REGISTRY,
    VerificationStatus,
    VerifierResult,
)


class DeterministicVerifierTests(unittest.TestCase):
    def test_safe_builtins_cover_exact_predicates(self) -> None:
        cases = (
            ("builtin.exact_arithmetic", {"expression": "1/3 + 1/6", "expected": "1/2"}),
            ("builtin.json_exact", {"actual": '{"a": 1, "b": [2]}', "expected": '{"b": [2], "a": 1}'}),
            ("builtin.digest_exact", {"value": "x", "expected_digest": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"}),
            ("builtin.exact_match", {"actual": [1, 2], "expected": [1, 2]}),
            ("builtin.numeric_tolerance", {"actual": "1.005", "expected": "1.0", "tolerance": "0.005"}),
        )
        for verifier, payload in cases:
            with self.subTest(verifier=verifier):
                self.assertEqual(DEFAULT_REGISTRY.run(verifier, payload).status, VerificationStatus.PASS)

    def test_fail_unknown_and_closed_registry(self) -> None:
        self.assertEqual(
            DEFAULT_REGISTRY.run("builtin.numeric_tolerance", {"actual": "1.1", "expected": "1.0", "tolerance": "0"}).status,
            VerificationStatus.FAIL,
        )
        self.assertEqual(DEFAULT_REGISTRY.run("builtin.json_exact", {"actual": "not json", "expected": "{}"}).status, VerificationStatus.UNKNOWN)
        with self.assertRaises(KeyError):
            DEFAULT_REGISTRY.resolve("custom.shell")
        with self.assertRaises(TypeError):
            DEFAULT_REGISTRY.register("custom.shell")

    def test_digest_exact_rejects_noncanonical_expected_digest_as_unknown(self) -> None:
        valid = "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
        for invalid in (valid.upper(), "g" * 64, valid[:-1]):
            with self.subTest(invalid=invalid):
                result = DEFAULT_REGISTRY.run(
                    "builtin.digest_exact", {"value": "x", "expected_digest": invalid}
                )
                self.assertEqual(result.status, VerificationStatus.UNKNOWN)
                self.assertTrue(result.reason)

    def test_verifier_result_digests_must_be_canonical_lowercase_sha256(self) -> None:
        for invalid in ("A" * 64, "g" * 64, "a" * 63):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                VerifierResult(
                    "builtin.exact_match",
                    "1",
                    "egrt.builtin",
                    VerificationStatus.PASS,
                    "matched",
                    invalid,
                    "a" * 64,
                )

    def test_module_has_no_process_or_network_execution_imports(self) -> None:
        source = inspect.getsource(sys.modules["egrt_verifiers"]).lower()
        for forbidden in ("import subprocess", "import socket", "import urllib", "import requests", "import os"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
