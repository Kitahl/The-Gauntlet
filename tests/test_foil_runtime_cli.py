from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FoilRuntimeCliTests(unittest.TestCase):
    def test_probe_and_active_run_persist_before_print(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "task.json"
            source.write_text(
                json.dumps(
                    {
                        "schema": "foil.question-only-route-input.v2",
                        "task_id": "cli-1",
                        "question": r"Compute \(2 + 3 * 4\)?",
                    }
                ),
                encoding="utf-8",
            )
            probe = root / "probe.json"
            proc = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools" / "foil_runtime_cli.py"),
                    "probe", str(source), "--output", str(probe),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(probe.exists())
            self.assertIn("status=FOUND", proc.stdout)
            output = root / "run.json"
            archive = root / "archive"
            proc = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools" / "foil_runtime_cli.py"),
                    "run", str(source), "--a0", "12", "--answer-kind", "NUMBER",
                    "--archive-dir", str(archive), "--output", str(output),
                    "--active-answer-change",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["final_answer"], "14")
            self.assertEqual(payload["receipt"]["outcome"], "VERIFY_RESOLVED")
            self.assertIn("answer_changed=true", proc.stdout)


if __name__ == "__main__":
    unittest.main()
