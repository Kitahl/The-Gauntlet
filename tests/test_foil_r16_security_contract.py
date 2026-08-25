from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "benchmarks" / "harness"))

import foil_r16_no_oracle_discovery_runner as runner  # noqa: E402


class R16SecurityContractTests(unittest.TestCase):
    def test_production_discovery_modules_have_no_io_or_dynamic_execution_surface(self) -> None:
        forbidden_import_roots = {
            "http",
            "httpx",
            "openai",
            "os",
            "pathlib",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        forbidden_calls = {"eval", "exec", "compile", "__import__"}
        paths = (
            ROOT / "tools" / "foil_obligation_discovery.py",
            ROOT / "tools" / "foil_obligation_discovery_admission.py",
        )
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports: set[str] = set()
            calls: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(item.name.split(".")[0] for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
            with self.subTest(path=path.name):
                self.assertFalse(imports & forbidden_import_roots)
                self.assertFalse(calls & forbidden_calls)

    def test_scanner_blind_evaluator_accepts_no_scorer_fields(self) -> None:
        signature = inspect.signature(runner.evaluate_answer)
        self.assertEqual(tuple(signature.parameters), ("question", "base_answer"))
        self.assertNotIn("gold", inspect.getsource(runner.evaluate_answer).lower())
        self.assertNotIn("is_correct", inspect.getsource(runner.evaluate_answer))


if __name__ == "__main__":
    unittest.main()
