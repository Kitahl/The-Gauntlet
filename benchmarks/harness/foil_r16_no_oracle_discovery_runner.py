#!/usr/bin/env python3
"""Score the preregistered FOIL R1.6 no-oracle discovery pilot."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import foil_r16_no_oracle_discovery_pilot as protocol  # noqa: E402
import foil_r16_no_oracle_operators as operators  # noqa: E402

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import canonical_json  # noqa: E402
from foil_obligation_compiler import compile_task_spec  # noqa: E402
from foil_obligation_discovery import (  # noqa: E402
    DiscoveryPolicy,
    DiscoveryStatus,
    discover_obligations,
)
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402


def evaluate_answer(question: str, base_answer: str) -> protocol.Prediction:
    """Run scanner-blind discovery with exactly question and A0-visible inputs."""

    if not isinstance(question, str) or not isinstance(base_answer, str):
        raise TypeError("question and base_answer must be strings")
    request = {
        "task_text": question,
        "a0_text": base_answer,
        "task_digest": protocol.sha256_text(question),
        "a0_digest": answer_digest(base_answer),
    }
    envelope = discover_obligations(request, policy=DiscoveryPolicy(enabled=True))
    preserved = envelope.base_answer is base_answer and envelope.a0_digest == answer_digest(
        base_answer
    )
    item_sha256 = protocol.sha256_text(
        "\0".join((request["task_digest"], request["a0_digest"]))
    )
    if envelope.status is not DiscoveryStatus.FOUND:
        return protocol.Prediction(
            item_sha256,
            False,
            envelope.status.value,
            envelope.envelope_digest,
            preserved,
            envelope.reason,
        )

    # Explicitly benchmark-only: production routing accepts only an
    # AdmittedCompiledTaskSpec for generated origin.  This local compile cannot
    # create an admission receipt or route/action authority.
    compiled = compile_task_spec(
        envelope.task_spec, observed_a0_digest=envelope.a0_digest
    )
    reports = []
    for plan in compiled.deterministic_scanner_plans():
        reports.append(
            scan(plan, envelope.a0_digest, compiled.deterministic_cases(plan.claim_id))
        )
    detected = any(report.status is ScanStatus.FAIL for report in reports)
    statuses = ",".join(report.status.value for report in reports)
    return protocol.Prediction(
        item_sha256,
        detected,
        envelope.status.value,
        envelope.envelope_digest,
        preserved,
        f"UNADMITTED_DISCOVERY_BENCHMARK_ONLY:{statuses or 'NO_PLAN'}",
    )


def select_mutation_bases(
    records: Sequence[protocol.SourceResponse],
) -> tuple[
    tuple[protocol.SourceResponse, ...],
    tuple[protocol.MutationAttempt, ...],
]:
    """Freeze eight hash-ranked gold rows that support every operator."""

    unique: dict[str, protocol.SourceResponse] = {}
    for record in records:
        unique.setdefault(record.question_sha256, record)
    ordered = sorted(
        unique.values(),
        key=lambda item: protocol._rank_key("mutation-base", item.question_sha256),
    )
    selected: list[protocol.SourceResponse] = []
    all_attempts: list[protocol.MutationAttempt] = []
    for record in ordered:
        try:
            if len(protocol.parse_annotations(record.ground_truth)) < 3:
                continue
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        attempts = operators.attempt_all(
            record.question_sha256, record.question, record.ground_truth
        )
        if all(item.status == "EXECUTED" for item in attempts):
            selected.append(record)
            all_attempts.extend(attempts)
        if len(selected) == int(protocol.PROTOCOL["mutation_base_rows"]):
            break
    expected = int(protocol.PROTOCOL["mutation_base_rows"])
    if len(selected) != expected:
        raise RuntimeError(
            f"only {len(selected)} of {expected} hash-ranked rows support all operators"
        )
    if len(all_attempts) != expected * len(protocol.OPERATORS):
        raise AssertionError("mutation attempt denominator was not conserved")
    return tuple(selected), tuple(all_attempts)


def wilson_95(successes: int, total: int) -> dict[str, float | int | str | None]:
    if isinstance(successes, bool) or isinstance(total, bool):
        raise TypeError("counts must be integers")
    if not isinstance(successes, int) or not isinstance(total, int):
        raise TypeError("counts must be integers")
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes must be within the non-negative denominator")
    if total == 0:
        return {
            "successes": successes,
            "total": total,
            "rate": None,
            "interval_name": "Wilson two-sided 95%",
            "lower": None,
            "upper": None,
        }
    z = NormalDist().inv_cdf(0.975)
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        rate * (1 - rate) / total + z * z / (4 * total * total)
    ) / denominator
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "interval_name": "Wilson two-sided 95%",
        "lower": max(0.0, center - radius),
        "upper": min(1.0, center + radius),
    }


def _average_ranks(values: Sequence[float]) -> tuple[float, ...]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average = (position + 1 + end) / 2
        for index in order[position:end]:
            ranks[index] = average
        position = end
    return tuple(ranks)


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation vectors must have equal length of at least two")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True)
    )
    left_mass = sum((item - left_mean) ** 2 for item in left)
    right_mass = sum((item - right_mean) ** 2 for item in right)
    if left_mass == 0 or right_mass == 0:
        raise ValueError("correlation is undefined for a constant vector")
    return numerator / math.sqrt(left_mass * right_mass)


def association(
    mutation: Mapping[str, Mapping[str, float | int | str | None]],
    natural: Mapping[str, Mapping[str, float | int | str | None]],
) -> dict[str, object]:
    common = [
        label
        for label in protocol.NATURAL_LABELS
        if int(mutation[label]["total"] or 0) > 0
        and int(natural[label]["total"] or 0) > 0
    ]
    reasons: list[str] = []
    if len(common) < int(protocol.PROTOCOL["minimum_common_classes"]):
        reasons.append("FEWER_THAN_THREE_COMMON_CLASSES")
    x = [float(mutation[label]["rate"]) for label in common]
    y = [float(natural[label]["rate"]) for label in common]
    if x and len(set(x)) < 2:
        reasons.append("MUTATION_RATE_VECTOR_ZERO_VARIANCE")
    if y and len(set(y)) < 2:
        reasons.append("NATURAL_RATE_VECTOR_ZERO_VARIANCE")
    if reasons:
        return {
            "status": "NOT_IDENTIFIABLE",
            "reason_codes": reasons,
            "common_classes": common,
            "spearman": None,
            "exact_permutation_two_sided_p": None,
            "pearson_descriptive": None,
        }
    spearman = _pearson(_average_ranks(x), _average_ranks(y))
    permutations = list(itertools.permutations(y))
    extreme = sum(
        abs(_pearson(_average_ranks(x), _average_ranks(candidate)))
        >= abs(spearman) - 1e-15
        for candidate in permutations
    )
    return {
        "status": "ESTIMABLE_SMOKE_ONLY",
        "reason_codes": [],
        "common_classes": common,
        "spearman": spearman,
        "exact_permutation_two_sided_p": extreme / len(permutations),
        "exact_permutation_count": len(permutations),
        "pearson_descriptive": _pearson(x, y),
    }


def _rate_rows(
    rows: Sequence[tuple[str, bool]],
) -> dict[str, dict[str, float | int | str | None]]:
    return {
        label: wilson_95(
            sum(item_label == label and detected for item_label, detected in rows),
            sum(item_label == label for item_label, _ in rows),
        )
        for label in protocol.NATURAL_LABELS
    }


def _positive_controls() -> dict[str, object]:
    question = "A crate has 2 rows with 3 jars each, then 1 jar is added."
    clear = "First <<2*3=6>>6. Then <<6+1=7>>7. Finally <<7*1=7>>7.\nA: 7"
    defect = "First <<2*3=5>>5. Then <<5+1=6>>6. Finally <<6*1=6>>6.\nA: 6"
    clear_prediction = evaluate_answer(question, clear)
    defect_prediction = evaluate_answer(question, defect)
    passed = (
        not clear_prediction.detected
        and defect_prediction.detected
        and clear_prediction.a0_preserved
        and defect_prediction.a0_preserved
    )
    if not passed:
        raise RuntimeError("required R1.6 scanner positive controls failed")
    return {
        "passed": True,
        "clear_stood_down": True,
        "known_mismatch_detected": True,
        "clear_envelope_sha256": clear_prediction.envelope_sha256,
        "defect_envelope_sha256": defect_prediction.envelope_sha256,
    }


def build_report(
    records: Sequence[protocol.SourceResponse],
    labels: Mapping[tuple[str, str, str], str],
    *,
    protocol_commit: str,
) -> dict[str, object]:
    protocol_commit = protocol._require_commit(protocol_commit)
    candidates = protocol.candidate_rows(records)
    natural = protocol.select_natural_misses(candidates, labels)
    excluded = {row.question_sha256 for row, _ in natural}
    controls = protocol.select_correct_controls(records, excluded)
    mutation_bases, attempts = select_mutation_bases(records)
    conservation = operators.conservation(attempts)
    if not conservation["conserved"] or any(
        not bool(item["conserved"])
        for item in conservation["by_operator"].values()
    ):
        raise RuntimeError("mutation denominator conservation failed")

    executed = [item for item in attempts if item.status == "EXECUTED"]
    mutant_predictions = [
        evaluate_answer(
            next(
                row.question
                for row in mutation_bases
                if row.question_sha256 == attempt.question_sha256
            ),
            str(attempt.mutant),
        )
        for attempt in executed
    ]
    # Freeze all blind predictions before joining scorer-side natural labels.
    natural_predictions = [evaluate_answer(row.question, row.solution) for row, _ in natural]
    control_predictions = [evaluate_answer(row.question, row.solution) for row in controls]

    mutation_join = [
        (attempt.natural_label, prediction.detected)
        for attempt, prediction in zip(executed, mutant_predictions, strict=True)
    ]
    natural_join = [
        (label, prediction.detected)
        for (_, label), prediction in zip(natural, natural_predictions, strict=True)
    ]
    mutation_rates = _rate_rows(mutation_join)
    natural_rates = _rate_rows(natural_join)
    control_rate = wilson_95(
        sum(item.detected for item in control_predictions), len(control_predictions)
    )
    estimate = association(mutation_rates, natural_rates)
    positive_controls = _positive_controls()

    raw_rows: list[dict[str, object]] = []
    for attempt, prediction in zip(executed, mutant_predictions, strict=True):
        raw_rows.append(
            {
                "kind": "MUTANT",
                "question_sha256": attempt.question_sha256,
                "answer_sha256": attempt.mutant_answer_sha256,
                "operator_id": attempt.operator_id,
                "class": attempt.natural_label,
                "detected": prediction.detected,
                "discovery_status": prediction.discovery_status,
                "envelope_sha256": prediction.envelope_sha256,
                "a0_preserved": prediction.a0_preserved,
            }
        )
    for (row, label), prediction in zip(natural, natural_predictions, strict=True):
        raw_rows.append(
            {
                "kind": "NATURAL_MISS",
                "question_sha256": row.question_sha256,
                "answer_sha256": row.response_sha256,
                "model_variant": row.model_variant,
                "class": label,
                "detected": prediction.detected,
                "discovery_status": prediction.discovery_status,
                "envelope_sha256": prediction.envelope_sha256,
                "a0_preserved": prediction.a0_preserved,
            }
        )
    for row, prediction in zip(controls, control_predictions, strict=True):
        raw_rows.append(
            {
                "kind": "CORRECT_CONTROL",
                "question_sha256": row.question_sha256,
                "answer_sha256": row.response_sha256,
                "model_variant": row.model_variant,
                "detected": prediction.detected,
                "discovery_status": prediction.discovery_status,
                "envelope_sha256": prediction.envelope_sha256,
                "a0_preserved": prediction.a0_preserved,
            }
        )

    report: dict[str, object] = {
        "schema": protocol.REPORT_SCHEMA,
        "classification": "HISTORICAL_MODEL_NO_ORACLE_SMOKE",
        "protocol_commit": protocol_commit,
        "protocol_sha256": protocol.PROTOCOL_SHA256,
        "source": {
            "repository": "openai/grade-school-math",
            "commit": protocol.SOURCE_COMMIT,
            "file_sha256": protocol.SOURCE_SHA256,
            "row_count": len(records) // len(protocol.MODEL_VARIANTS),
            "response_count": len(records),
        },
        "selection": {
            "seed": protocol.SELECTION_SEED,
            "reviewed_candidates": len(labels),
            "mapped_natural_misses": len(natural),
            "unmapped_reviewed": sum(label == "UNMAPPED" for label in labels.values()),
            "natural_target": len(protocol.NATURAL_LABELS)
            * int(protocol.PROTOCOL["natural_per_class"]),
            "correct_controls": len(controls),
            "mutation_base_questions": len(mutation_bases),
        },
        "mutation_conservation": conservation,
        "mutation_detection_by_class": mutation_rates,
        "natural_detection_by_class": natural_rates,
        "correct_control_false_fires": control_rate,
        "association": estimate,
        "positive_controls": positive_controls,
        "cost_and_authority": {
            "fixed_source_downloads": 1,
            "provider_calls": 0,
            "external_bot_calls": 0,
            "runtime_model_calls": 0,
            "token_spend": 0,
            "answer_mutations_by_foil": 0,
            "profile_writes": 0,
            "execution_authorizations": 0,
            "promotion_changes": 0,
        },
        "non_claims": [
            "not calibration or promotion evidence",
            "not frontier-model recall",
            "not general prose-to-obligation formalization",
            "not natural class prevalence",
        ],
        "raw_rows": raw_rows,
    }
    report["report_sha256"] = protocol.digest(report)
    return report


def independently_verify_report(report: Mapping[str, object]) -> None:
    """Re-derive public counts and rates from persisted hash-only raw rows."""

    if not isinstance(report, Mapping) or report.get("schema") != protocol.REPORT_SCHEMA:
        raise RuntimeError("unexpected R1.6 report schema")
    raw = report.get("raw_rows")
    if not isinstance(raw, list):
        raise RuntimeError("report raw_rows are absent")
    clone = dict(report)
    reported_digest = clone.pop("report_sha256", None)
    if reported_digest != protocol.digest(clone):
        raise RuntimeError("report digest mismatch")
    mutation = [row for row in raw if row.get("kind") == "MUTANT"]
    natural = [row for row in raw if row.get("kind") == "NATURAL_MISS"]
    controls = [row for row in raw if row.get("kind") == "CORRECT_CONTROL"]
    expected_mutation = _rate_rows(
        [(str(row["class"]), bool(row["detected"])) for row in mutation]
    )
    expected_natural = _rate_rows(
        [(str(row["class"]), bool(row["detected"])) for row in natural]
    )
    if expected_mutation != report.get("mutation_detection_by_class"):
        raise RuntimeError("mutation rates do not rederive from raw rows")
    if expected_natural != report.get("natural_detection_by_class"):
        raise RuntimeError("natural rates do not rederive from raw rows")
    expected_control = wilson_95(
        sum(bool(row["detected"]) for row in controls), len(controls)
    )
    if expected_control != report.get("correct_control_false_fires"):
        raise RuntimeError("control false-fire rate does not rederive")
    if association(expected_mutation, expected_natural) != report.get("association"):
        raise RuntimeError("association does not rederive")
    if not all(bool(row.get("a0_preserved")) for row in raw):
        raise RuntimeError("at least one evaluation failed A0 preservation")


def _source_bytes(cache: Path) -> bytes:
    if cache.exists():
        return cache.read_bytes()
    source = protocol.fetch_source()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(source)
    return source


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    candidates = subparsers.add_parser(
        "candidates", help="materialize the scanner-blind curation pack"
    )
    candidates.add_argument("--source-cache", type=Path, required=True)
    candidates.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run", help="run the frozen no-oracle smoke pilot")
    run.add_argument("--source-cache", type=Path, required=True)
    run.add_argument("--labels", type=Path, required=True)
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--protocol-commit", required=True)
    verify = subparsers.add_parser("verify", help="rederive a persisted report")
    verify.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        independently_verify_report(report)
        print(canonical_json({"verified": True, "report_sha256": report["report_sha256"]}))
        return 0
    source = _source_bytes(args.source_cache)
    records = protocol.load_source(source)
    if args.command == "candidates":
        pack = protocol.candidate_pack(records)
        _write_json(args.output, pack)
        print(
            canonical_json(
                {
                    "candidate_rows": len(pack["rows"]),
                    "source_sha256": protocol.SOURCE_SHA256,
                }
            )
        )
        return 0
    candidates = protocol.candidate_rows(records)
    label_data = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = protocol.load_label_manifest(label_data, candidates)
    report = build_report(records, labels, protocol_commit=args.protocol_commit)
    independently_verify_report(report)
    _write_json(args.report, report)
    print(
        canonical_json(
            {
                "association_status": report["association"]["status"],
                "report_sha256": report["report_sha256"],
                "raw_rows": len(report["raw_rows"]),
                "verified": True,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
