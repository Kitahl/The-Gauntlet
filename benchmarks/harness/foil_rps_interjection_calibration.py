"""Calibrate RPS Stage 1 and no-tools model interjection from frozen receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_rps_interjection_calibration import (  # noqa: E402
    Stage1DiagnosticEvidence,
    calibrate_rps_interjection,
)
from foil_smart_tool_calibration import (  # noqa: E402
    BenchmarkTarget,
    HistoricalRouteEvidence,
    assess_historical_route,
    calibrate_target,
)


REPORT_SCHEMA = "foil.rps-interjection-calibration-report.v1"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _rows(value: object, name: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        raise ValueError(f"{name} must be an object list")
    return list(value)


def build_report(
    independent_audit: Mapping[str, object],
    stage1_report: Mapping[str, object],
    stage2_predictions: Mapping[str, object],
    stage2_report: Mapping[str, object],
    *,
    target: BenchmarkTarget,
) -> dict[str, object]:
    calibration = calibrate_target(target)
    summaries = _mapping(independent_audit.get("summaries"), "summaries")
    no_tools = _mapping(summaries.get("FOIL"), "FOIL summary")
    same_context = assess_historical_route(
        HistoricalRouteEvidence(
            route_id="RPS_NO_TOOLS_SAME_CONTEXT_REVIEW",
            attempts=int(no_tools["n"]),
            rescues=int(no_tools["rescues"]),
            damages=int(no_tools["published_damages"]),
            invalid_outcomes=int(no_tools["n"]) - int(no_tools["final_valid"]),
            total_extra_tokens=int(no_tools["route_tokens"]),
            auditable=True,
            evidence_reason="frozen_posthoc_independent_raw_row_audit",
        ),
        calibration,
    )

    prediction_rows = _rows(stage2_predictions.get("rows"), "stage2 predictions")
    report_rows = {
        str(row["unit_id"]): row
        for row in _rows(stage2_report.get("rows"), "stage2 report rows")
    }
    triggered = [row for row in prediction_rows if int(row.get("provider_calls", 0)) == 1]
    if len(triggered) != 3 or any(str(row["unit_id"]) not in report_rows for row in triggered):
        raise ValueError("frozen Stage-2 trigger universe drifted")
    stage2_rescues = sum(
        bool(report_rows[str(row["unit_id"])]["rescued"]) for row in triggered
    )
    stage2_losses = sum(
        bool(report_rows[str(row["unit_id"])]["accuracy_loss"]) for row in triggered
    )
    stage2_tokens = sum(
        int(row["added_input_tokens"]) + int(row["added_output_tokens"])
        for row in triggered
    )
    blind_rival = assess_historical_route(
        HistoricalRouteEvidence(
            route_id="RPS_BLIND_RIVAL_STAGE2",
            attempts=len(triggered),
            rescues=stage2_rescues,
            damages=stage2_losses,
            invalid_outcomes=0,
            total_extra_tokens=stage2_tokens,
            auditable=True,
            evidence_reason="frozen_stage2_prediction_and_score_receipts",
        ),
        calibration,
    )

    stage1_summary = _mapping(stage1_report.get("summary"), "stage1 summary")
    stage1 = Stage1DiagnosticEvidence(
        rows=int(stage1_summary["rows"]),
        rescues=int(stage1_summary["rescues"]),
        damages=int(stage1_summary["damages"]),
        added_total_tokens=(
            int(stage1_summary["added_input_tokens"])
            + int(stage1_summary["added_output_tokens"])
        ),
        source_classification=str(stage1_report["classification"]),
    )
    interjection = calibrate_rps_interjection(
        same_context_review=same_context,
        blind_rival=blind_rival,
        stage1=stage1,
    )
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "HISTORICAL_DEVELOPMENT_CALIBRATION",
        "target": calibration.trace(),
        "interjection": interjection.trace(),
        "measured_stage2": {
            "triggers": len(triggered),
            "distinct_questions": len({str(row["item_id"]) for row in triggered}),
            "rescues": stage2_rescues,
            "accuracy_losses": stage2_losses,
            "added_input_tokens": sum(int(row["added_input_tokens"]) for row in triggered),
            "added_output_tokens": sum(int(row["added_output_tokens"]) for row in triggered),
            "added_total_tokens": stage2_tokens,
            "mean_added_tokens_per_trigger": (stage2_tokens + len(triggered) - 1) // len(triggered),
        },
        "hle_ability": {
            "mechanically_checkable_failure": "HOST_CAN_CORRECT_IN_BENCHMARK",
            "host_declines_factual_or_semantic_question": "PRESERVE_A0",
            "blind_no_tools_rival": "DISABLED_BY_CALIBRATION",
            "retrieve_fact_absent_from_context": "REQUIRES_RETRIEVAL_TOOL",
            "production_answer_change": "UNAUTHORIZED",
        },
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "new_token_spend": 0,
        "promotion_authorized": False,
        "non_claims": [
            "not a new HLE score",
            "not a production policy promotion",
            "not evidence that latent model knowledge can be reliably recovered",
            "not evidence that Stage 1 generalizes beyond its certified language",
        ],
    }
    report["report_sha256"] = digest(report)
    return report


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("independent_audit", type=Path)
    parser.add_argument("stage1_report", type=Path)
    parser.add_argument("stage2_predictions", type=Path)
    parser.add_argument("stage2_report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=60)
    parser.add_argument("--baseline-correct", type=int, default=11)
    parser.add_argument("--target-correct", type=int, default=22)
    parser.add_argument("--maximum-total-tokens", type=int, default=250_000)
    args = parser.parse_args()
    report = build_report(
        _read(args.independent_audit),
        _read(args.stage1_report),
        _read(args.stage2_predictions),
        _read(args.stage2_report),
        target=BenchmarkTarget(
            args.rows,
            args.baseline_correct,
            args.target_correct,
            args.maximum_total_tokens,
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
