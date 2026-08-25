#!/usr/bin/env python3
"""Score the preregistered FOIL R1.7 provenance-repair pilot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (HERE, ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import foil_r16_no_oracle_discovery_runner as stats  # noqa: E402
import foil_r16_no_oracle_operators as operators  # noqa: E402
import foil_r17_provenance_repair_pilot as protocol  # noqa: E402

from egrt_host_finalizer import answer_digest  # noqa: E402
from egrt_types import canonical_json  # noqa: E402
from foil_obligation_compiler import compile_task_spec  # noqa: E402
from foil_obligation_discovery import DiscoveryPolicy, DiscoveryStatus  # noqa: E402
from foil_obligation_discovery_v2 import discover_obligations_v2  # noqa: E402
from foil_residual_scanner import scan  # noqa: E402
from foil_v5_metrics import ScanStatus  # noqa: E402


def evaluate_answer(question: str, base_answer: str) -> protocol.Prediction:
    """Run v2 with question and A0 only; gold and labels are impossible inputs."""

    if not isinstance(question, str) or not isinstance(base_answer, str):
        raise TypeError("question and base_answer must be strings")
    request = {
        "task_text": question,
        "a0_text": base_answer,
        "task_digest": protocol.sha256_text(question),
        "a0_digest": answer_digest(base_answer),
    }
    envelope = discover_obligations_v2(request, policy=DiscoveryPolicy(enabled=True))
    preserved = envelope.base_answer is base_answer and envelope.a0_digest == answer_digest(base_answer)
    item_sha256 = protocol.sha256_text("\0".join((request["task_digest"], request["a0_digest"])))
    if envelope.status is not DiscoveryStatus.FOUND:
        return protocol.Prediction(
            item_sha256,
            False,
            envelope.status.value,
            envelope.envelope_digest,
            preserved,
            envelope.reason,
        )
    # Benchmark-only. No admission receipt, production route, or action authority
    # is constructed by this local compilation.
    compiled = compile_task_spec(envelope.task_spec, observed_a0_digest=envelope.a0_digest)
    reports = [
        scan(plan, envelope.a0_digest, compiled.deterministic_cases(plan.claim_id))
        for plan in compiled.deterministic_scanner_plans()
    ]
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
    records: Sequence[protocol.SourceResponse], excluded_questions: set[str]
) -> tuple[tuple[protocol.SourceResponse, ...], tuple[protocol.MutationAttempt, ...]]:
    unique: dict[str, protocol.SourceResponse] = {}
    for record in records:
        if record.question_sha256 not in excluded_questions:
            unique.setdefault(record.question_sha256, record)
    ordered = sorted(
        unique.values(), key=lambda item: protocol._rank_key("mutation-base", item.question_sha256)
    )
    selected: list[protocol.SourceResponse] = []
    attempts: list[protocol.MutationAttempt] = []
    for record in ordered:
        try:
            if len(protocol.r16.parse_annotations(record.ground_truth)) < 3:
                continue
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        candidate_attempts = operators.attempt_all(
            record.question_sha256, record.question, record.ground_truth
        )
        if all(item.status == "EXECUTED" for item in candidate_attempts):
            selected.append(record)
            attempts.extend(candidate_attempts)
        if len(selected) == int(protocol.PROTOCOL["mutation_base_rows"]):
            break
    expected = int(protocol.PROTOCOL["mutation_base_rows"])
    if len(selected) != expected or len(attempts) != expected * len(protocol.OPERATORS):
        raise RuntimeError("fresh R1.7 mutation-base denominator is incomplete")
    return tuple(selected), tuple(attempts)


def frozen_candidate_rows(
    records: Sequence[protocol.SourceResponse], r16_exclusions: set[str]
) -> tuple[tuple[protocol.SourceResponse, ...], tuple[protocol.MutationAttempt, ...], list[protocol.SourceResponse]]:
    bases, attempts = select_mutation_bases(records, r16_exclusions)
    excluded = set(r16_exclusions) | {row.question_sha256 for row in bases}
    return bases, attempts, protocol.candidate_rows(records, excluded)


def _rate_rows(rows: Sequence[tuple[str, bool]]) -> dict[str, dict[str, float | int | str | None]]:
    return {
        label: stats.wilson_95(
            sum(row_label == label and detected for row_label, detected in rows),
            sum(row_label == label for row_label, _ in rows),
        )
        for label in protocol.NATURAL_LABELS
    }


def _decision(false_fires: int, natural_detected: int, natural_total: int) -> str:
    if false_fires >= 4:
        return "FAIL_NOISY"
    if natural_total >= 5 and natural_detected / natural_total <= 0.5:
        return "FAIL_RECALL"
    if false_fires <= 1 and natural_total >= 5 and natural_total - natural_detected <= 1:
        return "SMOKE_PROMISING"
    return "INCONCLUSIVE"


def _positive_controls() -> dict[str, object]:
    question = "A crate has 2 rows with 3 jars each, then 1 jar is added."
    clear = "First <<2*3=6>>6. Then <<6+1=7>>7. Finally <<7*1=7>>7.\nA: 7"
    defect = "First <<2*3=5>>5. Then <<5+1=6>>6. Finally <<6*1=6>>6.\nA: 6"
    clear_prediction, defect_prediction = evaluate_answer(question, clear), evaluate_answer(question, defect)
    if clear_prediction.detected or not defect_prediction.detected:
        raise RuntimeError("required R1.7 scanner positive controls failed")
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
    r16_exclusions: set[str],
    *,
    protocol_commit: str,
) -> dict[str, object]:
    protocol_commit = protocol.r16._require_commit(protocol_commit)
    bases, attempts, candidates = frozen_candidate_rows(records, r16_exclusions)
    natural = protocol.select_natural_misses(candidates, labels)
    excluded = set(r16_exclusions) | {row.question_sha256 for row in bases}
    excluded.update(row.question_sha256 for row, _ in natural)
    controls = protocol.select_correct_controls(records, excluded)
    base_questions = {row.question_sha256 for row in bases}
    natural_questions = {row.question_sha256 for row, _ in natural}
    control_questions = {row.question_sha256 for row in controls}
    if base_questions & natural_questions or base_questions & control_questions or natural_questions & control_questions:
        raise RuntimeError("R1.7 evaluation question sets overlap")
    if (base_questions | natural_questions | control_questions) & r16_exclusions:
        raise RuntimeError("R1.7 reused an R1.6 development question")

    conservation = operators.conservation(attempts)
    if not conservation["conserved"] or any(
        not bool(row["conserved"]) for row in conservation["by_operator"].values()
    ):
        raise RuntimeError("R1.7 mutation denominator conservation failed")
    executed = [attempt for attempt in attempts if attempt.status == "EXECUTED"]
    mutant_predictions = [
        evaluate_answer(
            next(row.question for row in bases if row.question_sha256 == attempt.question_sha256),
            str(attempt.mutant),
        )
        for attempt in executed
    ]
    # Freeze all scanner outputs before joining any scorer-side labels.
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
    mutation_rates, natural_rates = _rate_rows(mutation_join), _rate_rows(natural_join)
    false_fires = sum(item.detected for item in control_predictions)
    natural_detected = sum(item.detected for item in natural_predictions)
    control_rate = stats.wilson_95(false_fires, len(control_predictions))
    natural_overall = stats.wilson_95(natural_detected, len(natural_predictions))
    estimate = stats.association(mutation_rates, natural_rates)

    raw_rows: list[dict[str, object]] = []
    for attempt, prediction in zip(executed, mutant_predictions, strict=True):
        raw_rows.append(
            {
                "kind": "MUTANT",
                "question_sha256": attempt.question_sha256,
                "answer_sha256": attempt.mutant_answer_sha256,
                "operator_id": attempt.operator_id,
                "class": attempt.natural_label,
                "attempt_status": attempt.status,
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
        "classification": "FRESH_HISTORICAL_MODEL_PROVENANCE_REPAIR_SMOKE",
        "decision": _decision(false_fires, natural_detected, len(natural_predictions)),
        "protocol_commit": protocol_commit,
        "protocol_sha256": protocol.PROTOCOL_SHA256,
        "route_id": protocol.PROTOCOL["route_id"],
        "source": {
            "repository": "openai/grade-school-math",
            "commit": protocol.SOURCE_COMMIT,
            "file_sha256": protocol.SOURCE_SHA256,
            "row_count": len(records) // len(protocol.MODEL_VARIANTS),
            "response_count": len(records),
        },
        "selection": {
            "seed": protocol.SELECTION_SEED,
            "r16_excluded_questions": len(r16_exclusions),
            "reviewed_candidates": len(labels),
            "mapped_natural_misses": len(natural),
            "unmapped_reviewed": sum(label == "UNMAPPED" for label in labels.values()),
            "correct_controls": len(controls),
            "mutation_base_questions": len(bases),
            "all_question_sets_disjoint": True,
        },
        "mutation_conservation": conservation,
        "mutation_detection_by_class": mutation_rates,
        "natural_detection_by_class": natural_rates,
        "natural_detection_overall": natural_overall,
        "correct_control_false_fires": control_rate,
        "association": estimate,
        "positive_controls": _positive_controls(),
        "cost_and_authority": {
            "fixed_source_downloads": 0,
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
            "not an independent replication of the implementation team",
        ],
        "raw_rows": raw_rows,
    }
    report["report_sha256"] = protocol.r16.digest(report)
    return report


def independently_verify_report(report: Mapping[str, object]) -> None:
    if not isinstance(report, Mapping) or report.get("schema") != protocol.REPORT_SCHEMA:
        raise RuntimeError("unexpected R1.7 report schema")
    clone = dict(report)
    reported_digest = clone.pop("report_sha256", None)
    if reported_digest != protocol.r16.digest(clone):
        raise RuntimeError("R1.7 report digest mismatch")
    raw = report.get("raw_rows")
    if not isinstance(raw, list):
        raise RuntimeError("R1.7 raw rows are absent")
    mutation = [row for row in raw if row.get("kind") == "MUTANT"]
    natural = [row for row in raw if row.get("kind") == "NATURAL_MISS"]
    controls = [row for row in raw if row.get("kind") == "CORRECT_CONTROL"]
    expected_counts = Counter({operator: int(protocol.PROTOCOL["mutation_base_rows"]) for operator in protocol.OPERATORS})
    if Counter(str(row.get("operator_id")) for row in mutation) != expected_counts:
        raise RuntimeError("R1.7 mutation denominators are incomplete")
    mutation_rates = _rate_rows([(str(row["class"]), bool(row["detected"])) for row in mutation])
    natural_rates = _rate_rows([(str(row["class"]), bool(row["detected"])) for row in natural])
    if mutation_rates != report.get("mutation_detection_by_class"):
        raise RuntimeError("R1.7 mutation rates do not rederive")
    if natural_rates != report.get("natural_detection_by_class"):
        raise RuntimeError("R1.7 natural rates do not rederive")
    false_fires = sum(bool(row["detected"]) for row in controls)
    natural_detected = sum(bool(row["detected"]) for row in natural)
    if stats.wilson_95(false_fires, len(controls)) != report.get("correct_control_false_fires"):
        raise RuntimeError("R1.7 false-fire interval does not rederive")
    if stats.wilson_95(natural_detected, len(natural)) != report.get("natural_detection_overall"):
        raise RuntimeError("R1.7 natural interval does not rederive")
    if stats.association(mutation_rates, natural_rates) != report.get("association"):
        raise RuntimeError("R1.7 association does not rederive")
    if _decision(false_fires, natural_detected, len(natural)) != report.get("decision"):
        raise RuntimeError("R1.7 decision does not rederive")
    question_sets = [
        {str(row["question_sha256"]) for row in mutation},
        {str(row["question_sha256"]) for row in natural},
        {str(row["question_sha256"]) for row in controls},
    ]
    if any(question_sets[i] & question_sets[j] for i in range(3) for j in range(i + 1, 3)):
        raise RuntimeError("R1.7 report question sets overlap")
    if not all(bool(row.get("a0_preserved")) for row in raw):
        raise RuntimeError("R1.7 failed A0 preservation")
    costs = report.get("cost_and_authority")
    if not isinstance(costs, Mapping) or any(
        costs.get(key) != 0
        for key in (
            "provider_calls", "external_bot_calls", "runtime_model_calls", "token_spend",
            "answer_mutations_by_foil", "profile_writes", "execution_authorizations", "promotion_changes",
        )
    ):
        raise RuntimeError("R1.7 zero-cost or authority invariant failed")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("candidates", "run"):
        command = sub.add_parser(name)
        command.add_argument("--source-cache", type=Path, required=True)
        command.add_argument("--r16-labels", type=Path, required=True)
        command.add_argument("--r16-report", type=Path, required=True)
        if name == "candidates":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--labels", type=Path, required=True)
            command.add_argument("--report", type=Path, required=True)
            command.add_argument("--protocol-commit", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        independently_verify_report(report)
        print(canonical_json({"verified": True, "report_sha256": report["report_sha256"]}))
        return 0
    source = args.source_cache.read_bytes()
    records = protocol.load_source(source)
    exclusions = protocol.load_r16_exclusions(
        args.r16_labels.read_bytes(), args.r16_report.read_bytes()
    )
    bases, _, candidates = frozen_candidate_rows(records, exclusions)
    if args.command == "candidates":
        pack = protocol.candidate_pack(
            records, exclusions | {row.question_sha256 for row in bases}
        )
        if [row.identity for row in candidates] != [
            (row["question_sha256"], row["model_variant"], row["response_sha256"])
            for row in pack["rows"]
        ]:
            raise RuntimeError("R1.7 candidate construction paths disagree")
        _write_json(args.output, pack)
        print(canonical_json({"candidate_rows": len(candidates), "excluded_questions": len(exclusions)}))
        return 0
    labels_raw = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = protocol.load_label_manifest(labels_raw, candidates)
    report = build_report(records, labels, exclusions, protocol_commit=args.protocol_commit)
    independently_verify_report(report)
    _write_json(args.report, report)
    print(canonical_json({"decision": report["decision"], "report_sha256": report["report_sha256"], "raw_rows": len(report["raw_rows"]), "verified": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
