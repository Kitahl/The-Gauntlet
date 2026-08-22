from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".yml", ".yaml"}
FORBIDDEN = [
    r"\bTRIBUNAL\b",
    r"tombl",
    r"novelty-harness",
    r"666purple",
    r"openalexmailto@gmail\.com",
    r"University of Tribunal",
    r"TRIBUNAL_\d+_HANDOFF",
    r"\.tribunal_secrets",
    r"github\.com/Kitahl/Tribunal",
    r"design/BUILD_LEDGER",
    r"design/build_ledger",
    r"design/LESSONS",
    r"C:\\Users\\tom",
    r"/Users/tom",
]


class PrivateLeakTests(unittest.TestCase):
    def test_candidate_has_no_private_project_lineage(self) -> None:
        files = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "tests" not in path.parts
            and path.suffix.lower() in TEXT_SUFFIXES
        ]
        joined = "\n".join(
            path.read_text(encoding="utf-8", errors="replace") for path in files
        )
        for pattern in FORBIDDEN:
            self.assertIsNone(re.search(pattern, joined, re.IGNORECASE), pattern)


if __name__ == "__main__":
    unittest.main()
