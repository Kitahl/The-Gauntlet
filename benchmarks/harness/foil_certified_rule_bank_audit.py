"""Independent arithmetic/conservation audit for the frozen small pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = (
    "tools/foil_certified_arithmetic.py",
    "tools/foil_arithmetic_rule_bank.py",
    "tools/egrt_verifiers.py",
    "tools/foil_obligation_compiler.py",
    "tools/foil_obligation_discovery_admission.py",
    "benchmarks/FOIL_CERTIFIED_ARITHMETIC_RULE_BANK_SMALL_PILOT.md",
    "benchmarks/harness/foil_certified_rule_bank_pilot.py",
    "benchmarks/harness/foil_certified_rule_bank_audit.py",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(relative_path: str) -> str:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = report["raw_rows"]
    if not isinstance(rows, list) or len(rows) != 12:
        raise AssertionError("raw-row count is not the frozen 12")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise AssertionError("case ids are not unique")
    executed = sum(row["discovery_status"] == "FOUND" for row in rows)
    stood_down = sum(
        row["discovery_status"] in {"PARTIAL", "ABSTAIN", "UNSUPPORTED"}
        for row in rows
    )
    if len(rows) != executed + stood_down:
        raise AssertionError("attempt conservation failed")
    controls = [row for row in rows if row["class"] == "CORRECT"]
    defects = [row for row in rows if row["class"] == "DEFECT"]
    unsupported = [row for row in rows if row["class"] == "UNSUPPORTED"]
    expected_counts = {
        "attempted": len(rows),
        "executed": executed,
        "unsupported_or_partial": stood_down,
        "matched": sum(bool(row["matched"]) for row in rows),
        "controls": len(controls),
        "control_false_fires": sum(row["observed"] == "FAIL" for row in controls),
        "defects": len(defects),
        "defects_detected": sum(row["observed"] == "FAIL" for row in defects),
        "unsupported_cases": len(unsupported),
        "unsupported_stood_down": sum(
            row["observed"] in {"PARTIAL", "ABSTAIN", "UNSUPPORTED"}
            for row in unsupported
        ),
    }
    if report["counts"] != expected_counts:
        raise AssertionError("summary counts do not rederive from raw rows")
    if any(row["default_off_status"] != "ABSTAIN" for row in rows):
        raise AssertionError("default-off route did not always abstain")
    if any(row["origin"] != "GENERATED_UNADMITTED" for row in rows):
        raise AssertionError("generated origin was hidden")
    if any(not row["a0_preserved"] for row in rows):
        raise AssertionError("A0 identity was not preserved")
    expected_files = {
        path: _file_sha256(path)
        for path in IMPLEMENTATION_FILES
    }
    if report["implementation_sha256"] != expected_files:
        raise AssertionError("implementation/protocol file binding does not match")
    cost = report["cost_and_authority"]
    if any(value != 0 for value in cost.values()):
        raise AssertionError("cost/authority conservation is nonzero")
    unhashed = dict(report)
    observed_digest = unhashed.pop("report_sha256")
    if _digest(unhashed) != observed_digest:
        raise AssertionError("report hash does not match content")
    return {
        "verified_rows": len(rows),
        "verified_executed": executed,
        "verified_stand_down": stood_down,
        "report_sha256": observed_digest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    args = parser.parse_args(argv)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    print(json.dumps(verify(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
