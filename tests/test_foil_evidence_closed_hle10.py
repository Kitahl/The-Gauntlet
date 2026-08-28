from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "benchmarks" / "harness" / "foil_evidence_closed_hle10.py"
SPEC = importlib.util.spec_from_file_location("foil_evidence_closed_hle10", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EvidenceClosedHLE10HarnessTests(unittest.TestCase):
    def test_constructor_prompt_is_blind_to_a0_and_gold(self) -> None:
        prompt = MODULE.constructor_prompt([
            {"task_id": "x", "question": "What is X?", "a0": "SECRET_A0", "gold": "SECRET_GOLD"}
        ])
        self.assertIn("What is X?", prompt)
        self.assertNotIn("SECRET_A0", prompt)
        self.assertNotIn("SECRET_GOLD", prompt)

    def test_compare_prompt_has_one_unlabelled_claim(self) -> None:
        prompt = MODULE.compare_prompt([
            {"task_id": "x", "question": "Q", "claim": "C", "evidence_quote": "E"}
        ])
        self.assertIn('"claim":"C"', prompt)
        self.assertNotIn('"origin":', prompt)
        self.assertNotIn('"counterpart":', prompt)

    def test_closed_batch_rejects_duplicate_or_missing_ids(self) -> None:
        row = {"task_id": "x", "status": "ABSTAIN", "answer": "", "evidence_url": "", "evidence_quote": ""}
        with self.assertRaises(MODULE.ProtocolError):
            MODULE._closed_items(json.dumps({"items": [row, row]}), {"x", "y"}, constructor=True)

    def test_private_url_rejected_before_fetch(self) -> None:
        with self.assertRaises(MODULE.ProtocolError):
            MODULE._validate_public_https("https://127.0.0.1/private")
        with self.assertRaises(MODULE.ProtocolError):
            MODULE._validate_public_https("http://example.com/")

    def test_session_ceiling_is_caller_supplied(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        self.assertIn("--session-token-ceiling", source)
        self.assertNotIn("SESSION_TOKEN_CEILING = 250000", source)

    def test_batch_usage_apportionment_conserves_tokens(self) -> None:
        shares = MODULE.apportion_usage({"input_tokens": 5, "output_tokens": 2}, ["b", "a"])
        self.assertEqual(sum(row["input_tokens"] for row in shares.values()), 5)
        self.assertEqual(sum(row["output_tokens"] for row in shares.values()), 2)


if __name__ == "__main__":
    unittest.main()
