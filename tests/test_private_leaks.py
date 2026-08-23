from __future__ import annotations

import re
import subprocess
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


def tracked_paths() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0:
        return [item for item in result.stdout.split("\0") if item]
    return [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts
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

    def test_mastermind_runtime_is_not_tracked(self) -> None:
        tracked = [path.lower() for path in tracked_paths()]
        forbidden_prefixes = (
            "mastermind/",
            ".mastermind/",
            "skills/mastermind/",
            "tools/mastermind",
        )
        for path in tracked:
            self.assertFalse(
                path == "mastermind" or any(path.startswith(prefix) for prefix in forbidden_prefixes),
                f"Mastermind runtime/control material is tracked: {path}",
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
