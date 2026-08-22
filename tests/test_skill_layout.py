from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkillLayoutTests(unittest.TestCase):
    def test_every_skill_directory_contains_only_skill_md(self):
        root = ROOT / "skills"
        dirs = [p for p in root.iterdir() if p.is_dir()]
        self.assertGreaterEqual(len(dirs), 1)
        for directory in dirs:
            names = sorted(p.name for p in directory.iterdir() if not p.name.startswith("."))
            self.assertEqual(names, ["SKILL.md"], f"{directory}: skill directories must contain SKILL.md only")

    def test_skill_specs_reference_runtime_outside_skill_dirs(self):
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text)
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotIn(".tribunal_secrets", text)


if __name__ == "__main__":
    unittest.main()
