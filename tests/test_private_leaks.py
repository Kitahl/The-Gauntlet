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
    # Local Windows path segments. Scratch directories and personal cloud
    # folders are where an absolute developer path leaks in, and both are
    # path-shaped: `...\AppData\Local\Temp\...`, `...\OneDrive\Desktop\...`.
    # `AppData` is matched only between separators so that the legitimate
    # `%APPDATA%` environment reference stays available to the cross-platform
    # profile code - `test_appdata_is_only_ever_a_windows_environment_reference`
    # below enumerates every remaining occurrence rather than trusting that.
    r"[\\/]AppData[\\/]",
    r"OneDrive",
]

#: The only spellings of APPDATA that are a Windows environment-variable
#: reference rather than somebody's home directory. Case-sensitive on purpose:
#: the variable is `APPDATA`, the path segment a leak would carry is `AppData`.
APPDATA_ENV_REFERENCE = re.compile(r"%APPDATA%|[\"']APPDATA[\"']")
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


def scanned_text_files() -> list[tuple[str, str]]:
    """(relative path, text) for every tracked text file outside the suite.

    Scoped to what git tracks on purpose. `ROOT.rglob` also descends into
    `.venv/`, `.ruff_cache/` and the rest of the gitignored build tree, and a
    vendored dependency's docstring saying `%USERPROFILE%\\AppData\\Local` is
    not this repository leaking anything. Publication is what the check is
    about, and everything published is tracked.
    """
    rows: list[tuple[str, str]] = []
    for relative in tracked_paths():
        if "tests" in Path(relative).parts:
            continue
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        rows.append((relative, path.read_text(encoding="utf-8", errors="replace")))
    return rows


class PrivateLeakTests(unittest.TestCase):
    def test_candidate_has_no_private_project_lineage(self) -> None:
        rows = scanned_text_files()
        self.assertTrue(rows, "nothing was scanned; an empty scan matches no pattern")
        for pattern in FORBIDDEN:
            expression = re.compile(pattern, re.IGNORECASE)
            for relative, text in rows:
                found = expression.search(text)
                self.assertIsNone(
                    found,
                    f"{pattern} matched {found.group(0)!r} in {relative}"
                    if found
                    else pattern,
                )

    def test_the_scan_catches_a_planted_local_path(self) -> None:
        """Positive control for the two path patterns added for D1.

        A pattern that never matches anything and a repository with no leaks
        produce the same green. These samples use a fabricated user name, and
        live under `tests/`, which the scan above excludes.
        """
        planted = {
            r"[\\/]AppData[\\/]": r"C:\Users\example\AppData\Local\Temp\scratch\log.txt",
            r"OneDrive": r"C:\Users\example\OneDrive\Desktop\workspace",
        }
        for pattern, sample in planted.items():
            self.assertIn(pattern, FORBIDDEN, f"{pattern} is not in FORBIDDEN")
            self.assertIsNotNone(
                re.search(pattern, sample, re.IGNORECASE),
                f"{pattern} failed to match {sample!r}",
            )

    def test_appdata_is_only_ever_a_windows_environment_reference(self) -> None:
        """Every literal `appdata` in the tree, enumerated rather than assumed.

        The path pattern above deliberately requires separators so the
        cross-platform profile code can keep reading `%APPDATA%`. That exemption
        is only safe if the remaining occurrences are actually environment
        references, so this lists them and checks each one.
        """
        offenders = []
        for relative, text in scanned_text_files():
            for number, line in enumerate(text.splitlines(), 1):
                if "appdata" not in line.lower():
                    continue
                if APPDATA_ENV_REFERENCE.search(line):
                    continue
                offenders.append(f"{relative}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "appdata appears outside an environment reference")

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
