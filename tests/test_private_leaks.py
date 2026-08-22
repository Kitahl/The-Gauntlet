from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    r"tombl", r"novelty-harness", r"666purple", r"University of Tribunal",
    r"TRIBUNAL_\d+_HANDOFF", r"\.tribunal_secrets", r"github\.com/Kitahl/Tribunal",
    r"design/BUILD_LEDGER", r"design/build_ledger", r"design/LESSONS",
]


class PrivateLeakTests(unittest.TestCase):
    def test_candidate_runtime_has_no_private_lineage(self):
        files = [p for p in ROOT.rglob("*") if p.is_file() and "tests" not in p.parts and p.suffix in {".py", ".md", ".json", ".txt"}]
        joined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)
        for pattern in FORBIDDEN:
            self.assertIsNone(re.search(pattern, joined, re.I), pattern)


if __name__ == "__main__":
    unittest.main()
