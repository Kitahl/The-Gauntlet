#!/usr/bin/env python3
"""Independent recomputation audit for the arithmetic alarm smoke gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from foil_arithmetic_alarm_gate import (  # noqa: E402
    RULES,
    SCHEMA,
    build_report,
)
from p0_processbench import load_rows  # noqa: E402


def _digest(value: object) -> str:
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def verify(report: dict[str, object], data_dir: Path) -> dict[str, object]:
    if report.get("schema") != SCHEMA:
        raise AssertionError("unexpected alarm report schema")
    claimed_hash = report.get("report_sha256")
    unhashed = dict(report)
    unhashed.pop("report_sha256", None)
    if claimed_hash != _digest(unhashed):
        raise AssertionError("alarm report hash mismatch")
    rows, manifest = load_rows(data_dir)
    rebuilt = build_report(rows, manifest)
    if rebuilt != report:
        raise AssertionError("alarm report does not match independent recomputation")
    union = report["union_report"]
    if not isinstance(union, dict):
        raise AssertionError("union report must be an object")
    overall = union["all_splits_descriptive_only"]
    if not isinstance(overall, dict):
        raise AssertionError("overall report must be an object")
    return {
        "verified_rows": len(rows),
        "verified_rules": len(RULES),
        "audited_controls": overall["audited_control_rows"],
        "audited_false_fires": overall["audited_false_fires"],
        "genuine_error_detections": overall["genuine_error_detections"],
        "decision": report["gate"]["decision"],
        "report_sha256": claimed_hash,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = verify(report, args.data_dir)
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
