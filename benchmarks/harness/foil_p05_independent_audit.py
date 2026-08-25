"""Independent arithmetic audit of a frozen FOIL P0.5 raw-row report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPLITS = ("gsm8k", "math", "olympiadbench", "omnimath")


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _assert_equal(actual: object, expected: object, name: str) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected!r}, observed {actual!r}")


def _counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    clean = [row for row in rows if row["clean"] is True]
    error = [row for row in rows if row["clean"] is False]
    return {
        "rows": len(rows),
        "clean_rows": len(clean),
        "error_rows": len(error),
        "applicable": sum(row["applicable"] is True for row in rows),
        "false_fires": sum(row["detected"] is True for row in clean),
        "detected_errors": sum(row["detected"] is True for row in error),
        "firing_rows": sum(row["detected"] is True for row in rows),
        "checkable_equalities": sum(int(row["checkable_equalities"]) for row in rows),
        "violating_findings": sum(int(row["violating_findings"]) for row in rows),
    }


def verify(report: Mapping[str, object]) -> dict[str, object]:
    if report.get("schema") != "foil.p05-certified-arithmetic-report.v1":
        raise AssertionError("unexpected report schema")
    body = dict(report)
    reported_digest = body.pop("report_sha256", None)
    _assert_equal(_canonical_digest(body), reported_digest, "report digest")

    raw_rows = report.get("raw_rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != 3_400:
        raise AssertionError("raw_rows must contain all 3,400 ProcessBench rows")
    ids = [str(row["id"]) for row in raw_rows]
    if len(set(ids)) != len(ids):
        raise AssertionError("raw row ids are not unique")
    for row in raw_rows:
        if row["clean"] is not (int(row["label"]) == -1):
            raise AssertionError(f"clean flag does not follow label for {row['id']}")

    subsets = report["subsets"]
    for split in SPLITS:
        selected = [row for row in raw_rows if row["split"] == split]
        observed = _counts(selected)
        expected = subsets[split]
        for key in (
            "rows",
            "clean_rows",
            "error_rows",
            "firing_rows",
            "checkable_equalities",
            "violating_findings",
        ):
            _assert_equal(observed[key], int(expected[key]), f"{split}.{key}")
        _assert_equal(
            observed["applicable"],
            int(expected["applicability"]["successes"]),
            f"{split}.applicable",
        )
        _assert_equal(
            observed["false_fires"],
            int(expected["alpha"]["successes"]),
            f"{split}.false_fires",
        )
        _assert_equal(
            observed["detected_errors"],
            int(expected["recall"]["successes"]),
            f"{split}.detected_errors",
        )
        localization = Counter({"exact": 0, "earlier": 0, "later": 0})
        for row in selected:
            if row["clean"] or not row["detected"]:
                continue
            firing = int(row["earliest_firing_step"])
            label = int(row["label"])
            localization[
                "exact" if firing == label else "earlier" if firing < label else "later"
            ] += 1
        for key in ("exact", "earlier", "later"):
            _assert_equal(
                localization[key], int(expected["localization"][key]), f"{split}.localization.{key}"
            )

    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in raw_rows:
        grouped[str(row["generator"])].append(row)
    generator_report = report["generator_analysis"]["generators"]
    _assert_equal(set(grouped), set(generator_report), "generator universe")
    for generator, rows in grouped.items():
        observed = _counts(rows)
        expected = generator_report[generator]
        _assert_equal(observed["clean_rows"], int(expected["clean_rows"]), f"{generator}.clean")
        _assert_equal(observed["error_rows"], int(expected["error_rows"]), f"{generator}.error")
        _assert_equal(
            observed["false_fires"], int(expected["alpha"]["successes"]), f"{generator}.alpha"
        )
        _assert_equal(
            observed["detected_errors"],
            int(expected["recall"]["successes"]),
            f"{generator}.recall",
        )

    audit = report["false_fire_audit"]
    audit_rows = audit["rows"]
    audit_total = sum(
        int(report["stage_metrics"]["audit-legacy-v0"][split]["alpha"]["successes"])
        for split in SPLITS
    )
    _assert_equal(len(audit_rows), audit_total, "audit false-fire conservation")
    failure_counts = Counter(str(row["failure_mode"]) for row in audit_rows)
    _assert_equal(
        failure_counts,
        Counter({mode: int(item["count"]) for mode, item in audit["failure_modes"].items()}),
        "failure-mode conservation",
    )

    for split, source in report["source_manifest"].items():
        path = Path(str(source["path"]))
        if not path.is_file():
            raise AssertionError(f"source parquet is missing: {path}")
        _assert_equal(_file_sha256(path), source["sha256"], f"{split}.source_sha256")

    counters = report["cost_and_authority"]
    if any(int(value) != 0 for value in counters.values()):
        raise AssertionError("cost/authority counters must all be zero")
    if report["admission"]["never_pooled"] is not True:
        raise AssertionError("admission must remain per-subset")

    return {
        "verified_rows": len(raw_rows),
        "verified_subsets": len(SPLITS),
        "verified_generators": len(grouped),
        "verified_audit_rows": len(audit_rows),
        "report_sha256": reported_digest,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "benchmark_runs" / "foil_p05_processbench" / "p05_report.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = verify(report)
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
