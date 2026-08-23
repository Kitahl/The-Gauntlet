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
MASTERMIN_RUNTIME_PATTERNS = [
    r"\bfrom\s+mastermind\b",
    r"\bimport\s+mastermind\b",
    r"tools[/\\]mastermind",
    r"skills[/\\]mastermind",
    r"curriculum[/\\]REACTBENCH_TASK_ORDER",
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

    def test_mastermind_runtime_is_not_part_of_gauntlet(self) -> None:
        for path in [
            ROOT / "mastermind",
            ROOT / ".mastermind",
            ROOT / "skills" / "mastermind",
        ]:
            self.assertFalse(path.exists(), str(path.relative_to(ROOT)))
        if (ROOT / "tools").exists():
            self.assertFalse(
                any("mastermind" in path.name.lower() for path in (ROOT / "tools").iterdir()),
                "Mastermind runtime/helper found under tools/",
            )

        runtime_files = [
            *(ROOT / "tools").glob("*.py"),
            *(ROOT / "skills").glob("*/SKILL.md"),
            ROOT / ".claude" / "settings.json",
            ROOT / ".gauntlet.json",
        ]
        runtime_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in runtime_files
            if path.is_file()
        )
        for pattern in MASTERMIN_RUNTIME_PATTERNS:
            self.assertIsNone(re.search(pattern, runtime_text, re.IGNORECASE), pattern)


if __name__ == "__main__":
    unittest.main()
