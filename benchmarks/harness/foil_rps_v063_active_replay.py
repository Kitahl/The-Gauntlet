"""Replay frozen ProcessBench A0 outputs through the active RPS v0.6.3 gate.

The replay performs no model or provider calls. It measures only whether the
new deterministic authority path would rescue or damage the already-frozen A0
answers. Stage 2 is deliberately not simulated: rows on which Stage 1 declines
retain A0 and are counted as ``stage2_not_run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from foil_rps_host_verifier import (
    HostTaskDescriptor,
    HostTaskType,
    Stage1Outcome,
    select_check,
    verify_answer,
)
from foil_rps_v063 import (
    RPSV063Action,
    RPSV063Policy,
    evaluate_unique_host_result,
)


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _sha256(value: object) -> str:
    if isinstance(value, bytes):
        body = value
    else:
        body = _canonical(value).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _read_json(path: Path) -> object:
    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate)


def _answer(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"answer", "abstain"}:
        raise ValueError(f"{name} must be a closed answer object")
    if not isinstance(value["answer"], str) or not isinstance(value["abstain"], bool):
        raise ValueError(f"{name} fields have invalid types")
    return {"answer": value["answer"].strip(), "abstain": value["abstain"]}


def _correct(answer: Mapping[str, object], gold: str) -> bool:
    return answer["abstain"] is False and answer["answer"] == gold.strip()


def build_report(
    items_document: object,
    results_document: object,
    *,
    source_hashes: Mapping[str, str],
) -> dict[str, object]:
    if not isinstance(items_document, dict) or not isinstance(
        items_document.get("items"), list
    ):
        raise ValueError("items document must contain an items list")
    if not isinstance(results_document, dict) or not isinstance(
        results_document.get("rows"), list
    ):
        raise ValueError("results document must contain a rows list")
    items: dict[str, dict[str, object]] = {}
    for raw in items_document["items"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise ValueError("invalid item row")
        if raw["id"] in items:
            raise ValueError(f"duplicate item id: {raw['id']}")
        items[raw["id"]] = raw

    seen_units: set[str] = set()
    output_rows: list[dict[str, object]] = []
    for raw in results_document["rows"]:
        if not isinstance(raw, dict) or raw.get("benchmark") != "PROCESSBENCH_GSM8K":
            continue
        unit_id = raw.get("unit_id")
        item_id = raw.get("item_id")
        if not isinstance(unit_id, str) or not isinstance(item_id, str):
            raise ValueError("ProcessBench row lacks string ids")
        if unit_id in seen_units:
            raise ValueError(f"duplicate unit id: {unit_id}")
        seen_units.add(unit_id)
        if item_id not in items:
            raise ValueError(f"missing item: {item_id}")
        item = items[item_id]
        steps = item.get("steps")
        if not isinstance(steps, list) or not steps or not all(
            isinstance(step, str) and step.strip() for step in steps
        ):
            raise ValueError(f"{item_id} has invalid steps")
        gold = raw.get("gold")
        config_id = raw.get("config_id")
        if not isinstance(gold, str) or not isinstance(config_id, str):
            raise ValueError(f"{unit_id} lacks gold/config")
        base = _answer(raw.get("base"), f"{unit_id}.base")
        previous_final = _answer(raw.get("final"), f"{unit_id}.final")
        base_correct = _correct(base, gold)
        previous_correct = _correct(previous_final, gold)
        if raw.get("base_correct") is not base_correct:
            raise ValueError(f"{unit_id} base correctness mismatch")
        if raw.get("final_correct") is not previous_correct:
            raise ValueError(f"{unit_id} final correctness mismatch")

        task_payload = {"problem": item.get("problem"), "steps": steps}
        selected = select_check(
            HostTaskDescriptor(
                task_digest=_sha256(task_payload),
                answer_form_digest=_sha256(
                    {"answer": "STRING", "abstain": "BOOLEAN"}
                ),
                task_type=HostTaskType.PROCESSBENCH_FIRST_ERROR,
                source_steps=tuple(steps),
            )
        )
        base_result = verify_answer(selected, base)
        expected = selected.spec.get("expected_answer")
        host_candidate = (
            {"answer": expected, "abstain": False}
            if isinstance(expected, str)
            else None
        )
        decision = evaluate_unique_host_result(
            selected,
            base_result,
            host_candidate,
            policy=RPSV063Policy(enabled=True, max_blind_rivals=1),
        )
        if decision.action is RPSV063Action.SELECT_HOST_RESULT:
            assert host_candidate is not None
            active_final = host_candidate
        else:
            active_final = base
        active_correct = _correct(active_final, gold)
        output_rows.append(
            {
                "unit_id": unit_id,
                "item_id": item_id,
                "config_id": config_id,
                "gold": gold,
                "base": base,
                "base_correct": base_correct,
                "previous_final": previous_final,
                "previous_final_correct": previous_correct,
                "active_final": active_final,
                "active_final_correct": active_correct,
                "rescued": (not base_correct and active_correct),
                "damaged": (base_correct and not active_correct),
                "stage1_outcome": base_result.outcome.value,
                "stage1_reason": base_result.reason,
                "stage1_expected_answer": expected,
                "stage2_not_run": (
                    decision.action is RPSV063Action.REQUEST_BLIND_RIVAL
                ),
                "decision": decision.trace(),
                "added_input_tokens": 0,
                "added_output_tokens": 0,
                "provider_calls": 0,
                "answer_mutations": int(decision.answer_change_authorized),
            }
        )

    if not output_rows:
        raise ValueError("no ProcessBench rows found")
    summary = {
        "rows": len(output_rows),
        "questions": len({row["item_id"] for row in output_rows}),
        "configs": len({row["config_id"] for row in output_rows}),
        "base_correct": sum(bool(row["base_correct"]) for row in output_rows),
        "previous_final_correct": sum(
            bool(row["previous_final_correct"]) for row in output_rows
        ),
        "active_final_correct": sum(
            bool(row["active_final_correct"]) for row in output_rows
        ),
        "rescues": sum(bool(row["rescued"]) for row in output_rows),
        "damages": sum(bool(row["damaged"]) for row in output_rows),
        "answer_mutations": sum(int(row["answer_mutations"]) for row in output_rows),
        "stage1_resolved": sum(
            row["stage1_outcome"] in {Stage1Outcome.PASS.value, Stage1Outcome.FAIL.value}
            for row in output_rows
        ),
        "stage2_not_run": sum(bool(row["stage2_not_run"]) for row in output_rows),
        "provider_calls": 0,
        "added_input_tokens": 0,
        "added_output_tokens": 0,
        "total_token_multiplier": 1.0,
    }
    report: dict[str, object] = {
        "schema": "foil.rps-v063-frozen-active-replay.v1",
        "classification": "FROZEN_OUTPUT_DIAGNOSTIC_REPLAY_ONLY",
        "source_hashes": dict(sorted(source_hashes.items())),
        "summary": summary,
        "rows": sorted(output_rows, key=lambda row: str(row["unit_id"])),
        "production_authorized": False,
        "promotion_authorized": False,
        "non_claims": [
            "This two-question replay is not a calibration or promotion benchmark.",
            "It does not run Stage 2 or measure blind-rival behavior.",
            "It reuses frozen model outputs and makes no frontier efficacy claim.",
            "The active rule was developed using ProcessBench evidence.",
        ],
    }
    report["report_sha256"] = _sha256(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_hashes = {
        "items_sha256": _sha256(args.items.read_bytes()),
        "results_sha256": _sha256(args.results.read_bytes()),
    }
    report = build_report(
        _read_json(args.items),
        _read_json(args.results),
        source_hashes=source_hashes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_canonical(report) + "\n", encoding="utf-8")
    print(_canonical(report["summary"]))
    print(f"report_sha256={report['report_sha256']}")


if __name__ == "__main__":
    main()
