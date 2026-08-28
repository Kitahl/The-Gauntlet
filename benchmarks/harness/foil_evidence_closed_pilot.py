"""Sealed zero-provider pilot for FOIL's evidence-closed benchmark path."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from egrt_types import digest  # noqa: E402
from foil_answer_selector import SelectorPolicy  # noqa: E402
from foil_benchmark_budget import BenchmarkTokenLedger  # noqa: E402
from foil_bounded_answer_constructor import ConstructorDraft, ConstructorPolicy  # noqa: E402
from foil_evidence_closed_runtime import EvidenceClosedRuntimePolicy, run_evidence_closed_benchmark  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    AtomicClaim,
    ClaimKind,
    EvidenceDocument,
    EvidencePacket,
    EvidenceSpan,
    QuestionObligation,
    SourceClass,
)
from foil_retrieval_claim_comparator import (  # noqa: E402
    ClaimStatus,
    ComparatorPolicy,
    SemanticComparison,
)
from foil_route_opportunity import (  # noqa: E402
    QUESTION_INPUT_SCHEMA,
    QuestionOnlyTask,
    discover_route_opportunity,
)
from foil_smart_tool_integration import _object, _rows, _write  # noqa: E402
from foil_smart_tool_value import UtilityWeights  # noqa: E402
from foil_tool_contract import ToolFamily, ToolOperation  # noqa: E402
from foil_tool_plan_v2 import (  # noqa: E402
    PlanStep,
    PlanValuePolicy,
    ToolPlanContractV2,
    ToolPlanCost,
)


PREDICTION_SCHEMA = "foil.evidence-closed-pilot-predictions.v1"
REPORT_SCHEMA = "foil.evidence-closed-pilot-report.v1"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _policy() -> EvidenceClosedRuntimePolicy:
    return EvidenceClosedRuntimePolicy(
        enabled=True,
        plan_value=PlanValuePolicy(enabled=True, benchmark_exploration=True),
        weights=UtilityWeights(1_000_000, 2_000_000, 500_000, token_price_microunits=1),
        comparator=ComparatorPolicy(
            semantic_enabled=True,
            allow_unadmitted_benchmark_selection=True,
            minimum_semantic_confidence_ppm=1_000_000,
            allowed_source_classes=(SourceClass.PRIMARY, SourceClass.SCHOLARLY),
        ),
        constructor=ConstructorPolicy(enabled=True, maximum_output_tokens=1),
        selector=SelectorPolicy(benchmark_selection_enabled=True),
    )


def run_predictions(
    items_document: Mapping[str, object],
    retrieval_document: Mapping[str, object],
    *,
    maximum_total_tokens: int,
) -> dict[str, object]:
    items = [
        row
        for row in _rows(items_document, "foil.smart-tool-integration-items.v1")
        if str(row["id"]).startswith("retrieval-")
    ]
    retrieval_rows = _rows(
        retrieval_document,
        "foil.smart-tool-integration-retrieval-corpus.v1",
    )
    retrieval_by_id = {str(row["id"]): row for row in retrieval_rows}
    if {str(row["id"]) for row in items} != set(retrieval_by_id):
        raise ValueError("retrieval fixture universe mismatch")
    ledger = BenchmarkTokenLedger(maximum_total_tokens)
    predictions: list[dict[str, object]] = []

    for source in items:
        item_id = str(source["id"])
        question = str(source["question"])
        a0 = str(source["a0"])
        raw_task = {
            "schema": QUESTION_INPUT_SCHEMA,
            "task_id": item_id,
            "question": question,
        }
        capabilities = {
            candidate.capability
            for candidate in discover_route_opportunity(raw_task).candidates
        }
        if "WEB_SEARCH" in capabilities:
            operation = ToolOperation.WEB_RETRIEVAL
            source_class = SourceClass.PRIMARY
        elif "SCHOLARLY_SEARCH" in capabilities:
            operation = ToolOperation.SCHOLARLY_RETRIEVAL
            source_class = SourceClass.SCHOLARLY
        else:
            raise ValueError("retrieval pilot item has no question-only retrieval route")
        plan = ToolPlanContractV2(
            item_id,
            digest(question),
            digest(a0),
            f"plan-{item_id}",
            "pilot-1",
            (
                PlanStep(
                    "retrieve",
                    ToolFamily.RETRIEVAL,
                    operation,
                    digest(question),
                ),
            ),
            ToolPlanCost(
                maximum_output_tokens=1,
                maximum_tool_calls=2,
                maximum_search_calls=1,
                maximum_fetch_calls=1,
                maximum_sources=1,
                maximum_evidence_characters=128,
                maximum_model_passes=2,
                maximum_latency_ms=100,
            ),
            True,
        )
        retrieval = retrieval_by_id[item_id]

        def plan_runner(
            selected_plan: ToolPlanContractV2,
            task: QuestionOnlyTask,
            *,
            row: Mapping[str, object] = retrieval,
            row_source_class: SourceClass = source_class,
        ) -> EvidencePacket:
            if selected_plan.plan_id != f"plan-{task.task_id}":
                raise ValueError("plan runner received the wrong bound plan")
            evidence = str(row["evidence"])
            candidate = str(row["candidate"])
            start = evidence.index(candidate)
            document = EvidenceDocument(
                f"doc-{task.task_id}",
                str(row["source_url"]),
                f"Synthetic source {task.task_id}",
                evidence,
                "2026-08-28T00:00:00Z",
                row_source_class,
                f"synthetic-{task.task_id}",
            )
            span = EvidenceSpan(
                f"span-{task.task_id}",
                document.document_id,
                start,
                start + len(candidate),
                candidate,
            )
            return EvidencePacket(
                task.question_digest,
                (document,),
                (span,),
                tool_calls=2,
                search_calls=1,
                fetch_calls=1,
                latency_ms=1,
            )

        def compare(
            claim: AtomicClaim,
            spans: tuple[EvidenceSpan, ...],
        ) -> SemanticComparison:
            matches = tuple(
                span.span_id
                for span in spans
                if _normalized(span.text) == _normalized(claim.normalized_value)
            )
            return SemanticComparison(
                ClaimStatus.SUPPORTED if matches else ClaimStatus.CONTRADICTED,
                1_000_000,
                matches or tuple(span.span_id for span in spans),
                "synthetic_exact_value_comparison",
            )

        def construct(
            task_question: str,
            obligation: QuestionObligation,
            packet: EvidencePacket,
            output_cap: int,
        ) -> ConstructorDraft:
            del task_question
            if output_cap != 1 or obligation.question_digest != packet.question_digest:
                raise ValueError("constructor envelope drift")
            if len(packet.spans) != 1:
                raise ValueError("pilot constructor requires one bounded span")
            span = packet.spans[0]
            claim = AtomicClaim(
                f"claim-{item_id}",
                span.text,
                ClaimKind.ANSWER,
                span.text,
                evidence_span_ids=(span.span_id,),
            )
            return ConstructorDraft(
                span.text,
                (claim,),
                0,
                0,
                0,
                "deterministic_single_span_constructor",
            )

        final, receipt = run_evidence_closed_benchmark(
            raw_task,
            a0,
            QuestionObligation(item_id, digest(question), AnswerKind.EXACT_TEXT),
            plans=(plan,),
            plan_evidence={},
            ledger=ledger,
            policy=_policy(),
            plan_runner=plan_runner,
            constructor_runner=construct,
            semantic_comparator=compare,
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
        "items_digest": digest(items_document),
        "retrieval_corpus_digest": digest(retrieval_document),
        "predictions": predictions,
        "ledger": ledger.trace(),
        "actual_provider_calls": 0,
        "actual_model_calls": 0,
        "actual_network_calls": 0,
        "promotion_authorized": False,
        "non_claims": [
            "not a natural-language efficacy benchmark",
            "not HLE performance",
            "not production calibration",
            "fixture retrieval is not factual-retrieval validation",
            "deterministic callbacks simulate logical model-pass boundaries",
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
    gold = {
        str(row["id"]): str(row["gold"])
        for row in _rows(gold_document, "foil.smart-tool-integration-gold.v1")
        if str(row["id"]).startswith("retrieval-")
    }
    rows = predictions.get("predictions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("predictions must contain rows")
    if {str(row["task_id"]) for row in rows if isinstance(row, Mapping)} != set(gold):
        raise ValueError("gold universe mismatch")

    baseline = final = rescues = damages = tool_calls = logical_passes = 0
    selections: dict[str, int] = {}
    scored: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("prediction rows must be objects")
        task_id = str(row["task_id"])
        base_ok = str(row["a0"]) == gold[task_id]
        final_ok = str(row["final"]) == gold[task_id]
        run = row.get("run")
        if not isinstance(run, Mapping):
            raise TypeError("prediction row lacks run receipt")
        packet = run.get("evidence_packet")
        if isinstance(packet, Mapping):
            tool_calls += int(packet["tool_calls"])
        for key in ("a0_assessment", "b_assessment"):
            assessment = run.get(key)
            if isinstance(assessment, Mapping):
                logical_passes += int(assessment["model_passes"])
        constructor = run.get("constructor")
        if isinstance(constructor, Mapping):
            logical_passes += int(constructor["model_passes"])
        selection = run.get("selection")
        outcome = "NONE" if not isinstance(selection, Mapping) else str(selection["outcome"])
        selections[outcome] = selections.get(outcome, 0) + 1
        baseline += int(base_ok)
        final += int(final_ok)
        rescues += int(not base_ok and final_ok)
        damages += int(base_ok and not final_ok)
        scored.append(
            {
                "task_id": task_id,
                "base_correct": base_ok,
                "final_correct": final_ok,
                "rescued": not base_ok and final_ok,
                "damaged": base_ok and not final_ok,
                "selection_outcome": outcome,
                "cost_accounting_complete": bool(run["cost_accounting_complete"]),
            }
        )
    ledger = predictions.get("ledger")
    if not isinstance(ledger, Mapping) or int(ledger["spent_total_tokens"]) != 0:
        raise AssertionError("zero-provider pilot token conservation failed")
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "classification": "SYNTHETIC_INTEGRATION_ONLY",
        "prediction_sha256": supplied,
        "gold_sha256": digest(gold_document),
        "items": len(rows),
        "baseline_correct": baseline,
        "final_correct": final,
        "rescues": rescues,
        "damages": damages,
        "tool_calls": tool_calls,
        "logical_model_passes_simulated": logical_passes,
        "actual_provider_tokens": int(ledger["spent_total_tokens"]),
        "actual_provider_calls": predictions["actual_provider_calls"],
        "actual_model_calls": predictions["actual_model_calls"],
        "actual_network_calls": predictions["actual_network_calls"],
        "selection_counts": selections,
        "rows": scored,
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
