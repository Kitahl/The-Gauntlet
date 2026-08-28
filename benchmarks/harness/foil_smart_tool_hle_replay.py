"""Zero-token active replay of mechanical smart-tool routes on historical HLE rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_benchmark_budget import BenchmarkTokenLedger  # noqa: E402
from foil_route_opportunity import QUESTION_INPUT_SCHEMA  # noqa: E402
from foil_smart_tool_runtime import (  # noqa: E402
    ExactArithmeticAdapter,
    RestrictedPythonOutputAdapter,
    SmartToolRuntimePolicy,
    run_smart_verify,
)
from foil_smart_tool_value import UtilityWeights, ValueGatePolicy  # noqa: E402


PREDICTION_SCHEMA = "foil.smart-tool-hle-replay-predictions.v1"
REPORT_SCHEMA = "foil.smart-tool-hle-replay-report.v1"


def _answer(value: object) -> str:
    if not isinstance(value, Mapping) or not isinstance(value.get("answer"), str):
        raise ValueError("base_answer must be an object with text answer")
    answer = value["answer"].strip()
    if not answer:
        raise ValueError("base answer must not be empty")
    return answer


def build_predictions(
    items_document: Mapping[str, object], results_document: Mapping[str, object]
) -> dict[str, object]:
    items = items_document.get("items")
    rows = results_document.get("rows")
    if not isinstance(items, list) or not isinstance(rows, list):
        raise ValueError("items and results must contain lists")
    by_id = {
        str(row["id"]): str(row["question"])
        for row in items
        if isinstance(row, Mapping)
    }
    if len(by_id) != len(items):
        raise ValueError("item universe is invalid or duplicated")
    projected: list[dict[str, str]] = []
    omitted: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("result rows must be objects")
        unit_id, item_id = row.get("unit_id"), row.get("item_id")
        if not isinstance(unit_id, str) or not isinstance(item_id, str) or item_id not in by_id:
            raise ValueError("result row does not bind the item universe")
        base_value = row.get("base_answer")
        if not isinstance(base_value, Mapping) or not isinstance(base_value.get("answer"), str):
            omitted.append({"unit_id": unit_id, "reason": "base_answer_unavailable"})
            continue
        projected.append(
            {"unit_id": unit_id, "item_id": item_id, "a0": _answer(base_value)}
        )
    if len({row["unit_id"] for row in projected}) != len(projected):
        raise ValueError("result unit ids must be unique")

    policy = SmartToolRuntimePolicy(
        enabled=True,
        value_gate=ValueGatePolicy(enabled=True, benchmark_exploration=True),
        weights=UtilityWeights(
            rescue_value_microunits=1_000_000,
            damage_loss_microunits=2_000_000,
            invalid_loss_microunits=500_000,
        ),
        allow_unadmitted_benchmark_selection=True,
    )
    adapters = {
        "SYMBOLIC_COMPUTATION": ExactArithmeticAdapter(),
        "CODE_EXECUTION": RestrictedPythonOutputAdapter(),
    }
    ledger = BenchmarkTokenLedger(0)
    predictions: list[dict[str, object]] = []
    for row in sorted(projected, key=lambda value: value["unit_id"]):
        question = by_id[row["item_id"]]
        final, receipt = run_smart_verify(
            {
                "schema": QUESTION_INPUT_SCHEMA,
                "task_id": row["unit_id"],
                "question": question,
            },
            row["a0"],
            adapters=adapters,
            evidence={},
            ledger=ledger,
            policy=policy,
        )
        predictions.append(
            {
                "unit_id": row["unit_id"],
                "item_id": row["item_id"],
                "question_digest": digest(question),
                "a0": row["a0"],
                "final": final,
                "run": receipt.trace(),
            }
        )
    body: dict[str, object] = {
        "schema": PREDICTION_SCHEMA,
        "classification": "HISTORICAL_DEVELOPMENT_REPLAY",
        "frozen_before_gold": True,
        "input_fields_used_from_results": ["unit_id", "item_id", "base_answer.answer"],
        "source_rows": len(rows),
        "eligible_rows": len(projected),
        "omitted_rows": omitted,
        "predictions": predictions,
        "ledger": ledger.trace(),
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "retrieval_adapter_available": False,
        "non_claims": [
            "not a new holdout",
            "not a retrieval test",
            "not an HLE score forecast",
            "repeated configurations are not independent questions",
        ],
    }
    body["prediction_sha256"] = digest(body)
    return body


def score_predictions(
    predictions: Mapping[str, object], results_document: Mapping[str, object]
) -> dict[str, object]:
    if predictions.get("schema") != PREDICTION_SCHEMA or predictions.get("frozen_before_gold") is not True:
        raise ValueError("predictions are not frozen replay predictions")
    supplied = predictions.get("prediction_sha256")
    unhashed = dict(predictions)
    unhashed.pop("prediction_sha256", None)
    if supplied != digest(unhashed):
        raise ValueError("prediction hash mismatch")
    rows = results_document.get("rows")
    if not isinstance(rows, list):
        raise ValueError("results must contain rows")
    gold = {
        str(row["unit_id"]): str(row["gold"])
        for row in rows
        if isinstance(row, Mapping)
    }
    prediction_rows = predictions.get("predictions")
    if not isinstance(prediction_rows, list):
        raise ValueError("prediction universe must be a list")
    predicted_ids = [
        str(row["unit_id"]) for row in prediction_rows if isinstance(row, Mapping)
    ]
    if len(predicted_ids) != len(prediction_rows) or len(predicted_ids) != len(
        set(predicted_ids)
    ) or not set(predicted_ids).issubset(gold):
        raise ValueError("prediction universe is invalid or not covered by gold")
    baseline = final = rescues = damages = active = 0
    capabilities: dict[str, int] = {}
    scored: list[dict[str, object]] = []
    for row in prediction_rows:
        assert isinstance(row, Mapping)
        unit_id = str(row["unit_id"])
        base_ok = str(row["a0"]) == gold[unit_id]
        final_ok = str(row["final"]) == gold[unit_id]
        run = row["run"]
        assert isinstance(run, Mapping)
        capability = str(run["selected_capability"] or "NONE")
        capabilities[capability] = capabilities.get(capability, 0) + 1
        baseline += int(base_ok)
        final += int(final_ok)
        rescues += int(not base_ok and final_ok)
        damages += int(base_ok and not final_ok)
        active += int(bool(run["active_verify_executed"]))
        scored.append(
            {
                "unit_id": unit_id,
                "item_id": row["item_id"],
                "base_correct": base_ok,
                "final_correct": final_ok,
                "rescued": not base_ok and final_ok,
                "damaged": base_ok and not final_ok,
                "active_verify_executed": bool(run["active_verify_executed"]),
                "selected_capability": run["selected_capability"],
            }
        )
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "HISTORICAL_DEVELOPMENT_REPLAY",
        "prediction_sha256": supplied,
        "source_rows": predictions["source_rows"],
        "omitted_rows": predictions["omitted_rows"],
        "rows": len(scored),
        "distinct_questions": len({row["item_id"] for row in scored}),
        "baseline_correct": baseline,
        "final_correct": final,
        "rescues": rescues,
        "damages": damages,
        "active_verify_calls": active,
        "capability_counts": capabilities,
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "token_spend": predictions["ledger"]["spent_total_tokens"],
        "scored_rows": scored,
        "non_claims": predictions["non_claims"],
    }
    report["report_sha256"] = digest(report)
    return report


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input must be JSON object")
    return value


def _write(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    predict = sub.add_parser("predict")
    predict.add_argument("items", type=Path)
    predict.add_argument("results", type=Path)
    predict.add_argument("output", type=Path)
    score = sub.add_parser("score")
    score.add_argument("predictions", type=Path)
    score.add_argument("results", type=Path)
    score.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "predict":
        value = build_predictions(_read(args.items), _read(args.results))
    else:
        value = score_predictions(_read(args.predictions), _read(args.results))
    _write(args.output, value)
    print(value["prediction_sha256" if args.command == "predict" else "report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
