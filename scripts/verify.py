#!/usr/bin/env python3
"""Single-command verification entrypoint for portfolio/research review."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, *cmd: str) -> None:
    print(f"\n== {label} ==")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    run("Python syntax", sys.executable, "-m", "compileall", "-q", "validation", "scripts")
    run("Public runtime contract", sys.executable, "validation/validate_soul_gauntlet_public.py")
    run("Static showcase + browser checks", sys.executable, "validation/validate_showcase.py")
    print("\nAll portfolio verification gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
