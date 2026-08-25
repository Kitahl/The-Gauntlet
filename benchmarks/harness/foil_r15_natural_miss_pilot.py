#!/usr/bin/env python3
"""Run the preregistered FOIL R1.5 nine-natural-miss smoke pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import digest  # noqa: E402
from foil_obligation_compiler import COMPILER_VERSION, TASK_SPEC_SCHEMA  # noqa: E402
from foil_v5_pipeline import PipelineStatus, run_structured_shadow  # noqa: E402

RUNTIME_BASE_COMMIT = "4ca0e72c5cdc5fd852fe680efeeeef561aea3e84"
ARC_PREDICTION_SHA256 = "745f05b5d7b077c5245dea1d3fa3965a1db7eeabe3145a935dc9c190ad26d3a8"
GPQA_PREDICTION_SHA256 = "f7fd58b0ab2cf5393940d8360e37418a47ce135093fc7d10396dbc7319d5cc3d"
ARC_PREDICTIONS = ROOT / "benchmark_runs" / "2026-08-22" / "predictions.json"
GPQA_PREDICTIONS = ROOT / "benchmark_runs" / "2026-08-22" / "gpqa_predictions.json"

ARC_URL = (
    "https://github.com/fchollet/ARC-AGI/archive/"
    "399030444e0ab0cc8b4e199870fb20b863846f34.zip"
)
GPQA_URL = "https://raw.githubusercontent.com/idavidrein/gpqa/main/dataset.zip"
GPQA_ZIP_PASSWORD = b"deserted-untie-orchid"
ARC_SEED = 20260822
GPQA_SEED = 20260825
LETTERS = "ABCD"

PROTOCOL = {
    "schema": "foil.r15-natural-miss-pilot.v1",
    "runtime_base_commit": RUNTIME_BASE_COMMIT,
    "prediction_sha256": {
        "arc_hle": ARC_PREDICTION_SHA256,
        "gpqa": GPQA_PREDICTION_SHA256,
    },
    "expected_historical": {
        "arc_correct": 9,
        "arc_n": 12,
        "gpqa_correct": 18,
        "gpqa_n": 24,
        "pooled_correct": 27,
        "pooled_n": 36,
        "natural_misses": 9,
    },
    "minimum_common_operator_classes": 3,
    "provider_calls_allowed": 0,
    "external_bots_allowed": 0,
    "token_spend_allowed": 0,
    "candidate_generation_allowed": False,
    "answer_mutation_allowed": False,
    "source_network_calls": 2,
}
PROTOCOL_SHA256 = digest(PROTOCOL)


@dataclass(frozen=True)
class ReplayRecord:
    item_id: str
    domain: str
    operator_id: str
    verifier_id: str
    predicate_kind: str
    claim_kind: str
    actual: object
    expected: object

    @property
    def correct(self) -> bool:
        return self.actual == self.expected


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _require_commit(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("protocol_commit must be a lowercase 40-hex Git commit")
    return value


def _prediction_map(path: Path, expected_sha256: str) -> dict[str, object]:
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"prediction digest mismatch: {path.name}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("predictions")
    if not isinstance(rows, list):
        raise RuntimeError(f"prediction rows missing: {path.name}")
    result: dict[str, object] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "answer"}:
            raise RuntimeError(f"invalid prediction row: {path.name}")
        item_id = row["id"]
        if not isinstance(item_id, str) or not item_id or item_id in result:
            raise RuntimeError(f"invalid or duplicate prediction id: {path.name}")
        result[item_id] = row["answer"]
    return result


def _normalize_choice(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def _gpqa_records(source: bytes, predictions: Mapping[str, object]) -> list[ReplayRecord]:
    archive = zipfile.ZipFile(io.BytesIO(source))
    names = sorted(
        name
        for name in archive.namelist()
        if name.lower().endswith(".csv") and "diamond" in name.lower()
    )
    if not names:
        raise RuntimeError("GPQA archive contains no Diamond CSV")
    raw = archive.read(names[0], pwd=GPQA_ZIP_PASSWORD).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    required = {
        "Question",
        "Correct Answer",
        "Incorrect Answer 1",
        "Incorrect Answer 2",
        "Incorrect Answer 3",
    }
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError("unexpected GPQA dataset columns")

    indices = list(range(len(rows)))
    random.Random(GPQA_SEED).shuffle(indices)
    records: list[ReplayRecord] = []
    for source_index in indices[:24]:
        row = rows[source_index]
        options = [
            (str(row["Correct Answer"]), True),
            (str(row["Incorrect Answer 1"]), False),
            (str(row["Incorrect Answer 2"]), False),
            (str(row["Incorrect Answer 3"]), False),
        ]
        random.Random(GPQA_SEED * 1000 + source_index).shuffle(options)
        correct_index = next(i for i, (_, correct) in enumerate(options) if correct)
        item_id = f"gpqa-diamond-{source_index:03d}"
        if item_id not in predictions:
            raise RuntimeError(f"missing historical GPQA prediction: {item_id}")
        records.append(
            ReplayRecord(
                item_id=item_id,
                domain="GPQA_DIAMOND",
                operator_id="GPQA_CHOICE_SUBSTITUTION",
                verifier_id="builtin.exact_match",
                predicate_kind="EXACT_MATCH",
                claim_kind="EXACT_MATCH",
                actual=_normalize_choice(predictions[item_id]),
                expected=LETTERS[correct_index],
            )
        )
    return records


def _arc_records(source: bytes, predictions: Mapping[str, object]) -> list[ReplayRecord]:
    archive = zipfile.ZipFile(io.BytesIO(source))
    candidates: list[tuple[str, dict[str, object]]] = []
    for name in archive.namelist():
        if "/data/evaluation/" not in name or not name.endswith(".json"):
            continue
        raw = archive.read(name)
        if len(raw) > 7000:
            continue
        task = json.loads(raw)
        tests = task.get("test", [])
        if len(tests) != 1 or "output" not in tests[0]:
            continue
        test_input = tests[0]["input"]
        if len(test_input) > 20:
            continue
        if max((len(row) for row in test_input), default=0) > 20:
            continue
        candidates.append((Path(name).stem, task))

    random.Random(ARC_SEED + 1).shuffle(candidates)
    records: list[ReplayRecord] = []
    for task_id, task in candidates[:12]:
        item_id = f"arc-{task_id}"
        if item_id not in predictions:
            raise RuntimeError(f"missing historical ARC prediction: {item_id}")
        expected = task["test"][0]["output"]
        records.append(
            ReplayRecord(
                item_id=item_id,
                domain="ARC_AGI_1",
                operator_id="ARC_CELL_SUBSTITUTION",
                verifier_id="builtin.json_exact",
                predicate_kind="JSON",
                claim_kind="JSON",
                actual=predictions[item_id],
                expected=expected,
            )
        )
    return records


def _canonical_answer(record: ReplayRecord, value: object) -> str:
    if record.verifier_id == "builtin.json_exact":
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _task_spec(record: ReplayRecord, actual: object) -> dict[str, object]:
    base_answer = _canonical_answer(record, actual)
    if record.verifier_id == "builtin.json_exact":
        verifier_input = {
            "actual": base_answer,
            "expected": _canonical_answer(record, record.expected),
        }
    else:
        verifier_input = {"actual": actual, "expected": record.expected}
    return {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": sha256_bytes(f"r15-task:{record.item_id}".encode()),
        "a0_digest": answer_digest(base_answer),
        "config_digest": sha256_bytes(b"r15-oracle-bound-config-v1"),
        "claims": [
            {
                "claim_key": "final-output",
                "statement_digest": sha256_bytes(
                    f"r15-statement:{record.item_id}".encode()
                ),
                "claim_kind": record.claim_kind,
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "Frozen oracle-bound R1.5 replay predicate",
                "obligations": [
                    {
                        "obligation_key": "expected-output",
                        "description": "The final output must match the hidden benchmark oracle",
                        "weight_range": {"start": 1, "end": 1},
                        "predicate_kind": record.predicate_kind,
                        "verifier_id": record.verifier_id,
                        "verifier_version": "1",
                        "verifier_input": verifier_input,
                    }
                ],
            }
        ],
    }


def _scan(record: ReplayRecord, actual: object) -> tuple[PipelineStatus, bool]:
    base_answer = _canonical_answer(record, actual)
    result = run_structured_shadow(
        base_answer=base_answer,
        task_spec=_task_spec(record, actual),
        model_fingerprint_sha256=sha256_bytes(b"r15-historical-gpt-5.6-sol"),
        contract_fingerprint_sha256=PROTOCOL_SHA256,
    )
    return result.status, result.base_answer is base_answer


def _mutant(record: ReplayRecord) -> object:
    if record.operator_id == "GPQA_CHOICE_SUBSTITUTION":
        expected = str(record.expected)
        return next(letter for letter in LETTERS if letter != expected)
    if record.operator_id == "ARC_CELL_SUBSTITUTION":
        value = json.loads(json.dumps(record.expected))
        if not value or not value[0] or not isinstance(value[0][0], int):
            raise RuntimeError(f"ARC output cannot be mutated: {record.item_id}")
        value[0][0] = (value[0][0] + 1) % 10
        if value == record.expected:
            raise RuntimeError(f"ARC mutant is equivalent: {record.item_id}")
        return value
    raise RuntimeError(f"unknown operator: {record.operator_id}")


def _rate_row(operator_id: str, values: Sequence[bool]) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "detected": sum(values),
        "n": len(values),
        "rate": sum(values) / len(values) if values else None,
    }


def _association(
    mutation_rows: Sequence[Mapping[str, object]],
    natural_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    mutation = {str(row["operator_id"]): row for row in mutation_rows}
    natural = {str(row["operator_id"]): row for row in natural_rows}
    common = sorted(set(mutation) & set(natural))
    reasons: list[str] = []
    if len(common) < int(PROTOCOL["minimum_common_operator_classes"]):
        reasons.append("INSUFFICIENT_COMMON_OPERATOR_CLASSES")
    x = [float(mutation[key]["rate"]) for key in common]
    y = [float(natural[key]["rate"]) for key in common]
    if len(set(x)) < 2:
        reasons.append("ZERO_VARIANCE_MUTATION_RATE")
    if len(set(y)) < 2:
        reasons.append("ZERO_VARIANCE_NATURAL_RATE")
    return {
        "status": "NOT_IDENTIFIABLE" if reasons else "ESTIMABLE_NOT_IMPLEMENTED",
        "common_operator_classes": common,
        "reason_codes": reasons,
        "pearson": None,
        "spearman": None,
    }


def evaluate_records(
    records: Sequence[ReplayRecord],
    *,
    protocol_commit: str,
    source_sha256: Mapping[str, str],
    enforce_historical_control: bool = True,
) -> dict[str, object]:
    """Evaluate already reconstructed records with no network or provider I/O."""

    _require_commit(protocol_commit)
    if len({record.item_id for record in records}) != len(records):
        raise RuntimeError("replay item ids must be unique")
    by_domain: dict[str, list[ReplayRecord]] = defaultdict(list)
    for record in records:
        by_domain[record.domain].append(record)

    historical = {
        "arc_correct": sum(record.correct for record in by_domain["ARC_AGI_1"]),
        "arc_n": len(by_domain["ARC_AGI_1"]),
        "gpqa_correct": sum(record.correct for record in by_domain["GPQA_DIAMOND"]),
        "gpqa_n": len(by_domain["GPQA_DIAMOND"]),
    }
    historical["pooled_correct"] = historical["arc_correct"] + historical["gpqa_correct"]
    historical["pooled_n"] = historical["arc_n"] + historical["gpqa_n"]
    historical["natural_misses"] = historical["pooled_n"] - historical["pooled_correct"]
    if enforce_historical_control and historical != PROTOCOL["expected_historical"]:
        raise RuntimeError(f"historical positive control failed: {historical}")

    natural_item_rows: list[dict[str, object]] = []
    natural_by_operator: dict[str, list[bool]] = defaultdict(list)
    correct_false_fires = 0
    for record in records:
        status, identity_preserved = _scan(record, record.actual)
        detected = status is PipelineStatus.DEFECT
        expected_status = PipelineStatus.CLEARED if record.correct else PipelineStatus.DEFECT
        if status is not expected_status or not identity_preserved:
            raise RuntimeError(f"RC4 replay control failed: {record.item_id}")
        if record.correct:
            correct_false_fires += int(detected)
        else:
            natural_by_operator[record.operator_id].append(detected)
        natural_item_rows.append(
            {
                "item_id": record.item_id,
                "domain": record.domain,
                "historical_correct": record.correct,
                "pipeline_status": status.value,
                "operator_id": record.operator_id,
                "a0_preserved": identity_preserved,
            }
        )

    mutation_item_rows: list[dict[str, object]] = []
    mutation_by_operator: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        mutant = _mutant(record)
        if mutant == record.expected:
            raise RuntimeError(f"equivalent mutant: {record.item_id}")
        status, identity_preserved = _scan(record, mutant)
        killed = status is PipelineStatus.DEFECT
        if not killed or not identity_preserved:
            raise RuntimeError(f"RC4 mutation control failed: {record.item_id}")
        mutation_by_operator[record.operator_id].append(killed)
        mutation_item_rows.append(
            {
                "item_id": record.item_id,
                "operator_id": record.operator_id,
                "pipeline_status": status.value,
                "valid_non_equivalent": True,
                "killed": killed,
                "a0_preserved": identity_preserved,
            }
        )

    natural_rows = [
        _rate_row(operator_id, values)
        for operator_id, values in sorted(natural_by_operator.items())
    ]
    mutation_rows = [
        _rate_row(operator_id, values)
        for operator_id, values in sorted(mutation_by_operator.items())
    ]
    association = _association(mutation_rows, natural_rows)
    natural_misses = int(historical["natural_misses"])
    natural_detected = sum(int(row["detected"]) for row in natural_rows)

    report: dict[str, object] = {
        "schema": PROTOCOL["schema"],
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_commit": protocol_commit,
        "runtime_base_commit": RUNTIME_BASE_COMMIT,
        "classification": "ORACLE_BOUND_NATURAL_MISS_SMOKE",
        "source_sha256": dict(sorted(source_sha256.items())),
        "prediction_sha256": PROTOCOL["prediction_sha256"],
        "historical_positive_control": historical,
        "r15_primary": {
            "status": "NOT_IDENTIFIABLE",
            "reason_codes": [
                "LEGACY_RAW_SCANNER_MUTATION_ROWS_ABSENT",
                "INDEPENDENT_NATURAL_OPERATOR_LABELS_ABSENT",
                *association["reason_codes"],
            ],
            "association": association,
        },
        "rc4_oracle_bound_replay": {
            "natural_misses_detected": natural_detected,
            "natural_misses": natural_misses,
            "correct_output_false_fires": correct_false_fires,
            "correct_outputs": int(historical["pooled_correct"]),
            "natural_by_operator": natural_rows,
            "mutation_by_operator": mutation_rows,
            "natural_items": natural_item_rows,
            "mutation_items": mutation_item_rows,
        },
        "costs": {
            "provider_calls": 0,
            "external_bots": 0,
            "token_spend": 0,
            "source_network_calls": 2,
            "candidate_generations": 0,
            "answer_mutations": 0,
        },
        "boundaries": {
            "oracle_specs_used": True,
            "raw_answers_stored": False,
            "raw_gold_stored": False,
            "promotion_authorized": False,
        },
        "non_claims": [
            "This does not test natural-language obligation extraction or defect discovery.",
            "This does not validate the unavailable legacy S1-S4 scanner bank or v4.1 aggregates.",
            "Two oracle-bound operator classes with zero rate variance cannot estimate correlation.",
            "Nine natural misses cannot calibrate or promote a production route.",
        ],
    }
    report["report_sha256"] = digest(report)
    return report


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "FOIL-R1.5-pilot/0.6"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def run_with_network(protocol_commit: str) -> dict[str, object]:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        arc_future = pool.submit(_fetch, ARC_URL)
        gpqa_future = pool.submit(_fetch, GPQA_URL)
        arc_source = arc_future.result()
        gpqa_source = gpqa_future.result()
    arc_predictions = _prediction_map(ARC_PREDICTIONS, ARC_PREDICTION_SHA256)
    gpqa_predictions = _prediction_map(GPQA_PREDICTIONS, GPQA_PREDICTION_SHA256)
    records = [
        *_arc_records(arc_source, arc_predictions),
        *_gpqa_records(gpqa_source, gpqa_predictions),
    ]
    report = evaluate_records(
        records,
        protocol_commit=protocol_commit,
        source_sha256={
            "arc_archive": sha256_bytes(arc_source),
            "gpqa_archive": sha256_bytes(gpqa_source),
        },
    )
    report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    report["report_sha256"] = digest(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-source-network", action="store_true")
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--protocol-sha256", default=PROTOCOL_SHA256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.allow_source_network:
        parser.error("source network is disabled unless --allow-source-network is explicit")
    if args.protocol_sha256 != PROTOCOL_SHA256:
        parser.error("protocol digest mismatch")
    try:
        report = run_with_network(_require_commit(args.protocol_commit))
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"R1.5 pilot failed closed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.output),
                "classification": report["classification"],
                "r15_status": report["r15_primary"]["status"],
                "natural_misses": report["historical_positive_control"]["natural_misses"],
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
