#!/usr/bin/env python3
"""Deterministic ProcessBench alarm gate for FOIL's repair-tier arithmetic rules.

This is a development smoke gate, not a production certificate. It scores each
versioned rule separately and their union on all four ProcessBench splits. A
pre-existing, content-bound adjudication may correct a demonstrably wrong corpus
label, but is reported separately and never hidden in the denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from foil_certified_arithmetic import (  # noqa: E402
    CERTIFIED_LANGUAGE,
    POWER_LANGUAGE,
    RAW_NUMERIC_LANGUAGE,
    extract_steps,
)
from p0_processbench import (  # noqa: E402
    SPLITS,
    ProcessRow,
    ScoredRow,
    load_rows,
    wilson_95,
)

SCHEMA = "foil.arithmetic-alarm-gate.v1"
RULES = (CERTIFIED_LANGUAGE, POWER_LANGUAGE, RAW_NUMERIC_LANGUAGE)

# This row was named as a corpus label error in the sealed P0.5 audit before
# this gate was implemented. Its displayed assertion is mechanically false:
# 1404 != 2^2 * 3^2 * 13 (1404 = 2^2 * 3^3 * 13). The final answer remains
# correct, but ProcessBench label=-1 incorrectly marks every step as correct.
ADJUDICATIONS: Mapping[tuple[str, str], Mapping[str, str]] = {
    ("omnimath", "omnimath-805"): {
        "row_sha256": "6dbb51b67fc49f3b1a10a2b2163f18fb74afc1f02f103688e6c9990b7454f497",
        "classification": "CORPUS_LABEL_FALSE_NEGATIVE_GENUINE_ERROR",
        "first_error_step": "5",
        "proof": "1404 != 2^2 * 3^2 * 13; right side equals 468",
    }
}


def _canonical_digest(value: object) -> str:
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def row_digest(row: ProcessRow) -> str:
    return _canonical_digest(
        {
            "split": row.split,
            "id": row.row_id,
            "generator": row.generator,
            "problem": row.problem,
            "steps": list(row.steps),
            "label": row.label,
            "final_answer_correct": row.final_answer_correct,
        }
    )


def _adjudication(row: ProcessRow) -> Mapping[str, str] | None:
    result = ADJUDICATIONS.get((row.split, row.row_id))
    if result is None:
        return None
    if row_digest(row) != result["row_sha256"]:
        raise ValueError(f"adjudicated row digest mismatch: {row.split}/{row.row_id}")
    if row.label != -1:
        raise ValueError("adjudication no longer targets a corpus-clean row")
    return result


def _score(rows: Sequence[ProcessRow], language: str) -> tuple[ScoredRow, ...]:
    if language not in RULES:
        raise ValueError("unknown repair-tier rule")
    return tuple(
        ScoredRow(row, extract_steps(row.steps, language=language)) for row in rows
    )


def _summary(scored: Sequence[ScoredRow]) -> dict[str, object]:
    corpus_clean = [item for item in scored if item.row.clean]
    corpus_errors = [item for item in scored if not item.row.clean]
    labeled_false_fires = [item for item in corpus_clean if item.detected]
    adjudicated = [
        item for item in labeled_false_fires if _adjudication(item.row) is not None
    ]
    audited_false_fires = [
        item for item in labeled_false_fires if _adjudication(item.row) is None
    ]
    audited_controls = [
        item for item in corpus_clean if _adjudication(item.row) is None
    ]
    detected_errors = [item for item in corpus_errors if item.detected]
    genuine_detected = len(detected_errors) + len(adjudicated)
    genuine_errors = len(corpus_errors) + sum(
        _adjudication(item.row) is not None for item in corpus_clean
    )
    return {
        "rows": len(scored),
        "corpus_clean_rows": len(corpus_clean),
        "corpus_error_rows": len(corpus_errors),
        "applicable_rows": sum(item.applicable for item in scored),
        "labeled_false_fires": len(labeled_false_fires),
        "adjudicated_label_errors": len(adjudicated),
        "audited_false_fires": len(audited_false_fires),
        "audited_control_rows": len(audited_controls),
        "audited_alpha": wilson_95(len(audited_false_fires), len(audited_controls)),
        "genuine_error_detections": genuine_detected,
        "genuine_error_rows": genuine_errors,
        "genuine_recall": wilson_95(genuine_detected, genuine_errors),
        "labeled_false_fire_rows": [
            {
                "split": item.row.split,
                "id": item.row.row_id,
                "row_sha256": row_digest(item.row),
                "adjudication": dict(_adjudication(item.row) or {}),
                "findings": [finding.to_dict() for finding in item.violating],
            }
            for item in labeled_false_fires
        ],
    }


def _source_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    portable: dict[str, object] = {}
    for split in SPLITS:
        source = manifest[split]
        if not isinstance(source, Mapping):
            raise TypeError("source manifest entry must be an object")
        portable[split] = {
            "filename": Path(str(source["path"])).name,
            "sha256": source["sha256"],
            "rows": source["rows"],
        }
    return portable


def build_report(
    rows: Sequence[ProcessRow], source_manifest: Mapping[str, object]
) -> dict[str, object]:
    by_rule = {language: _score(rows, language) for language in RULES}
    rule_reports: dict[str, object] = {}
    for language, scored in by_rule.items():
        rule_reports[language] = {
            split: _summary(tuple(item for item in scored if item.row.split == split))
            for split in SPLITS
        }
        rule_reports[language]["all_splits_descriptive_only"] = _summary(scored)

    union: list[ScoredRow] = []
    for index, row in enumerate(rows):
        findings = tuple(
            finding for language in RULES for finding in by_rule[language][index].findings
        )
        union.append(ScoredRow(row, findings))
    union_report = {
        split: _summary(tuple(item for item in union if item.row.split == split))
        for split in SPLITS
    }
    union_report["all_splits_descriptive_only"] = _summary(tuple(union))

    all_summary = union_report["all_splits_descriptive_only"]
    assert isinstance(all_summary, Mapping)
    smoke_pass = (
        all_summary["audited_false_fires"] == 0
        and int(all_summary["audited_control_rows"]) >= 20
        and int(all_summary["genuine_error_detections"]) > 0
    )
    report: dict[str, object] = {
        "schema": SCHEMA,
        "classification": "DEVELOPMENT_SMOKE_ONLY",
        "source_manifest": _source_manifest(source_manifest),
        "rules": list(RULES),
        "rule_reports": rule_reports,
        "union_report": union_report,
        "adjudications": [
            {"split": key[0], "id": key[1], **dict(value)}
            for key, value in sorted(ADJUDICATIONS.items())
        ],
        "gate": {
            "decision": "SMOKE_GATE_PASS" if smoke_pass else "SMOKE_GATE_FAIL",
            "rule": "zero audited false fires, >=20 audited controls, >=1 genuine detection",
            "production_admission": False,
            "answer_change_authority": "BENCHMARK_ONLY_IF_SEPARATELY_ENABLED",
        },
        "cost_and_authority": {
            "provider_calls": 0,
            "model_tokens": 0,
            "answer_mutations": 0,
            "execution_authorizations": 0,
            "promotion_authorizations": 0,
        },
        "non_claims": [
            "not fresh calibration because rules and adjudication were developed on ProcessBench",
            "not production admission or promotion evidence",
            "not frontier-model evidence",
            "not permission to pool subsets for a confidence certificate",
        ],
    }
    report["report_sha256"] = _canonical_digest(report)
    return report


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, manifest = load_rows(args.data_dir)
    report = build_report(rows, manifest)
    _write(args.output, report)
    overall = report["union_report"]["all_splits_descriptive_only"]
    print(f"rows={len(rows)}")
    print(f"audited_controls={overall['audited_control_rows']}")
    print(f"audited_false_fires={overall['audited_false_fires']}")
    print(f"genuine_error_detections={overall['genuine_error_detections']}")
    print(f"decision={report['gate']['decision']}")
    print(f"report_sha256={report['report_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
