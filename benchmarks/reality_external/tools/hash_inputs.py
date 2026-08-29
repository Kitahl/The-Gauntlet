#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs_dir")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.inputs_dir)
    rows: list[str] = []
    for path in sorted(root.glob("*.jsonl")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path.name}")
    if not rows:
        raise SystemExit("no JSONL inputs found")
    Path(args.output).write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    print(f"HASHED_INPUTS={len(rows)}")


if __name__ == "__main__":
    main()
