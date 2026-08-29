#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

FORBIDDEN_FILENAMES = {
    "REALITY_BENCHMARK_GOLD_KEY.txt",
    "REALITY_BENCHMARK_ID_KEY.txt",
    "gold_plaintext.json",
    "gold_plaintext.jsonl",
}
SUSPICIOUS_PATTERNS = [
    re.compile(r"REALITY_BENCH_ID_KEY_HEX\s*=\s*[0-9a-fA-F]{64,}"),
    re.compile(r"BEGIN (?:PGP )?PRIVATE KEY"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    args = parser.parse_args()
    root = Path(args.root)
    findings: list[str] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        scanned += 1
        rel = path.relative_to(root).as_posix()
        if path.name in FORBIDDEN_FILENAMES:
            findings.append(f"forbidden filename: {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                findings.append(f"secret-like content: {rel}: {pattern.pattern}")
        if rel.startswith("inputs/") and rel.endswith(".jsonl"):
            lowered = text.lower()
            for token in (
                '"novelty_score"',
                '"novelty_reasoning"',
                '"gold_hypothesis"',
                '"expected_relation"',
                '"probe_family"',
                '"doi"',
            ):
                if token in lowered:
                    findings.append(f"answer-bearing field in blind input: {rel}: {token}")
    if findings:
        print("LEAKAGE_AUDIT=FAIL")
        for finding in findings:
            print(f"- {finding}")
        raise SystemExit(1)
    print("LEAKAGE_AUDIT=PASS")
    print(f"FILES_SCANNED={scanned}")


if __name__ == "__main__":
    main()
