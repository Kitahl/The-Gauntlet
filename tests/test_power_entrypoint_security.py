from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import power_runtime as power  # noqa: E402
from egrt_types import Verdict  # noqa: E402


class PowerEntrypointSecurityTests(unittest.TestCase):
    def test_python_script_outside_root_is_unavailable_and_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "repo"
            root.mkdir()
            marker = parent / "executed.txt"
            outside = parent / "outside.py"
            outside.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
                encoding="utf-8",
            )
            check = power.VerificationCheck(
                "outside-entrypoint",
                "python-script",
                (sys.executable, str(outside)),
            )

            result = power.run_check(root, check)

            self.assertEqual(result["verdict"], Verdict.UNAVAILABLE.value)
            self.assertEqual(result["check_status"], "UNAVAILABLE")
            self.assertIn("outside the repository root", result["reason"])
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
