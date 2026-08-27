from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DependencyBoundaryTests(unittest.TestCase):
    def test_nonfoil_runtime_modules_do_not_import_foil_modules(self) -> None:
        violations: list[str] = []
        for path in (ROOT / "tools").glob("*.py"):
            if path.name.startswith("foil_"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name == "foil" or name.startswith("foil_") or name.startswith("foil."):
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
