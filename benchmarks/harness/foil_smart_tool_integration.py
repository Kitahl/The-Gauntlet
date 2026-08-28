"""Sealed zero-provider integration benchmark for active smart-tool VERIFY."""

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
    CallbackRetrievalAdapter,
    ExactArithmeticAdapter,
    RestrictedPythonOutputAdapter,
    RetrievalResult,
    SmartToolRuntimePolicy,
    run_smart_verify,
)
from foil_smart_tool_value import DifficultyBand, UtilityWeights, ValueGatePolicy  # noqa: E402
from foil_tool_contract import ToolCost  # noqa: E402


PREDICTION_SCHEMA = "foil.smart-tool-integration-predictions.v1"
REPORT_SCHEMA = "foil.smart-tool-integration-report.v1"


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _rows(document: Mapping[str, object], schema: str) -> list[Mapping[str, object]]:
    if document.get("schema") != schema or not isinstance(document.get("items"), list):
        raise ValueError(f"expected {schema}")
    rows = document["items"]
    assert isinstance(rows, list)
    if not rows or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("items must be a non-empty object list")
    ids = [row.get("id") for row in rows]
    if not all(isinstance(item_id, str) and item_id for item_id in ids):
        raise ValueError("every item requires a text id")
    if len(ids) != len(set(ids)):
        raise ValueError("item ids must be unique")
    return rows  # type: ignore[return-value]


def run_predictions(
    items_document: Mapping[str, object],
    retrieval_document: Mapping[str, object],
    *,
    maximum_total_tokens: int,
) -> dict[str, object]:
    items = _rows(items_document, "foil.smart-tool-integration-items.v1")
    retrieval_rows = _rows(
        retrieval_document,
        "foil.smart-tool-integration-retrieval-corpus.v1",
    )
    retrieval_by_id = {str(row["id"]): row for row in retrieval_rows}
    question_to_id = {str(row["question"]): str(row["id"]) for row in items}

    def retrieve(question: str, maximum_tokens: int) -> RetrievalResult:
        item_id = question_to_id.get(question)
        if item_id is None or item_id not in retrieval_by_id:
            raise ValueError("retrieval corpus has no bound row")
        row = retrieval_by_id[item_id]
        if maximum_tokens != 15:
            raise ValueError("retrieval reservation drift")
        return RetrievalResult(
            candidate_answer=str(row["candidate"]),
            evidence_text=str(row["evidence"]),
            source_urls=(str(row["source_url"]),),
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            latency_ms=1,
        )

    web = CallbackRetrievalAdapter(
        capability="WEB_SEARCH",
        runner=retrieve,
        maximum_cost=ToolCost(
            maximum_input_tokens=10,
            maximum_output_tokens=5,
            maximum_latency_ms=100,
        ),
        difficulty=DifficultyBand.HARD,
        provider_cap_enforced=True,
        tool_id="fixture.web",
        tool_version="1",
    )
    scholarly = CallbackRetrievalAdapter(
        capability="SCHOLARLY_SEARCH",
        runner=retrieve,
        maximum_cost=ToolCost(
            maximum_input_tokens=10,
            maximum_output_tokens=5,
            maximum_latency_ms=100,
        ),
        difficulty=DifficultyBand.EXPERT,
        provider_cap_enforced=True,
        tool_id="fixture.scholarly",
        tool_version="1",
    )
    adapters = {
        "SYMBOLIC_COMPUTATION": ExactArithmeticAdapter(),
        "CODE_EXECUTION": RestrictedPythonOutputAdapter(),
        "WEB_SEARCH": web,
        "SCHOLARLY_SEARCH": scholarly,
    }
    policy = SmartToolRuntimePolicy(
        enabled=True,
        value_gate=ValueGatePolicy(enabled=True, benchmark_exploration=True),
        weights=UtilityWeights(
            rescue_value_microunits=1_000_000,
            damage_loss_microunits=2_000_000,
            invalid_loss_microunits=500_000,
            token_price_microunits=1,
        ),
        allow_unadmitted_benchmark_selection=True,
    )
    ledger = BenchmarkTokenLedger(maximum_total_tokens)
    predictions: list[dict[str, object]] = []
    for row in items:
        item_id = str(row["id"])
        question = str(row["question"])
        a0 = str(row["a0"])
        final, receipt = run_smart_verify(
            {"schema": QUESTION_INPUT_SCHEMA, "task_id": item_id, "question": question},
            a0,
            adapters=adapters,
            evidence={},
            ledger=ledger,
            policy=policy,
        )
        predictions.append(
            {
                "task_id": item_id,
                "question_digest": digest(question),
                "a0": a0,
                "final": final,
                "run": receipt.trace(),
            }
        )
    body: dict[str, object] = {
        "schema": PREDICTION_SCHEMA,
        "classification": "SYNTHETIC_INTEGRATION_ONLY",
        "frozen_before_gold": True,
        "private_answers_present_for_scoring": True,
        "items_digest": digest(items_document),
        "retrieval_corpus_digest": digest(retrieval_document),
        "predictions": predictions,
        "ledger": ledger.trace(),
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "promotion_authorized": False,
        "non_claims": [
            "not a natural-language efficacy benchmark",
            "not HLE performance",
            "not production calibration",
            "fixture retrieval is not factual-retrieval validation",
        ],
    }
    body["prediction_sha256"] = digest(body)
    return body


def score_predictions(
    predictions: Mapping[str, object],
    gold_document: Mapping[str, object],
) -> dict[str, object]:
    if predictions.get("schema") != PREDICTION_SCHEMA or predictions.get("frozen_before_gold") is not True:
        raise ValueError("predictions are not a frozen supported artifact")
    supplied = predictions.get("prediction_sha256")
    unhashed = dict(predictions)
    unhashed.pop("prediction_sha256", None)
    if supplied != digest(unhashed):
        raise ValueError("prediction hash mismatch")
    gold_rows = _rows(gold_document, "foil.smart-tool-integration-gold.v1")
    gold = {str(row["id"]): str(row["gold"]) for row in gold_rows}
    rows = predictions.get("predictions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("predictions must contain rows")
    scored: list[dict[str, object]] = []
    family_counts: dict[str, int] = {}
    baseline_correct = final_correct = rescues = damages = 0
    active_calls = total_tool_calls = total_tokens = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("prediction rows must be objects")
        task_id = str(row["task_id"])
        if task_id not in gold:
            raise ValueError("gold universe mismatch")
        a0_ok = str(row["a0"]) == gold[task_id]
        final_ok = str(row["final"]) == gold[task_id]
        run = row.get("run")
        if not isinstance(run, Mapping):
            raise TypeError("prediction row lacks run receipt")
        baseline_correct += int(a0_ok)
        final_correct += int(final_ok)
        rescues += int(not a0_ok and final_ok)
        damages += int(a0_ok and not final_ok)
        active_calls += int(bool(run["active_verify_executed"]))
        tool = run.get("tool_receipt")
        if isinstance(tool, Mapping):
            total_tool_calls += int(tool["tool_calls"])
            total_tokens += int(tool["actual_total_tokens"])
        contract = run.get("contract")
        family = "NONE" if not isinstance(contract, Mapping) else str(contract["family"])
        family_counts[family] = family_counts.get(family, 0) + 1
        scored.append(
            {
                "task_id": task_id,
                "base_correct": a0_ok,
                "final_correct": final_ok,
                "rescued": not a0_ok and final_ok,
                "damaged": a0_ok and not final_ok,
                "active_verify_executed": bool(run["active_verify_executed"]),
                "selected_capability": run["selected_capability"],
                "family": family,
                "evidence_admission": (
                    None
                    if not isinstance(run.get("evidence"), Mapping)
                    else run["evidence"]["admission"]
                ),
            }
        )
    if len(gold) != len(rows):
        raise ValueError("gold and prediction denominators differ")
    ledger = predictions.get("ledger")
    if not isinstance(ledger, Mapping) or int(ledger["spent_total_tokens"]) != total_tokens:
        raise AssertionError("ledger and row token totals do not conserve")
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "SYNTHETIC_INTEGRATION_ONLY",
        "prediction_sha256": supplied,
        "gold_sha256": digest(gold_document),
        "items": len(rows),
        "baseline_correct": baseline_correct,
        "final_correct": final_correct,
        "rescues": rescues,
        "damages": damages,
        "active_verify_calls": active_calls,
        "tool_calls": total_tool_calls,
        "total_tool_provider_tokens": total_tokens,
        "family_counts": family_counts,
        "rows": scored,
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "promotion_authorized": False,
        "non_claims": predictions["non_claims"],
    }
    report["report_sha256"] = digest(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    predict = sub.add_parser("predict")
    predict.add_argument("items", type=Path)
    predict.add_argument("retrieval", type=Path)
    predict.add_argument("output", type=Path)
    predict.add_argument("--maximum-total-tokens", type=int, required=True)
    score = sub.add_parser("score")
    score.add_argument("predictions", type=Path)
    score.add_argument("gold", type=Path)
    score.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "predict":
        artifact = run_predictions(
            _object(args.items),
            _object(args.retrieval),
            maximum_total_tokens=args.maximum_total_tokens,
        )
        _write(args.output, artifact)
        print(artifact["prediction_sha256"])
        return 0
    report = score_predictions(_object(args.predictions), _object(args.gold))
    _write(args.output, report)
    print(report["report_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
