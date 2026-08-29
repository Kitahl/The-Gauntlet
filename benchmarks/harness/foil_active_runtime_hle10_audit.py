"""Independent raw-row/hash recomputation for the active FOIL HLE-10 run."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "benchmarks" / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from foil_active_runtime_hle10_common import EXPECTED, PREDICTIONS, RECEIPTS, RESULTS, ProtocolError, read_json, sha256_file  # noqa: E402


def _norm(value: str) -> str:
    text = " ".join(value.strip().casefold().split())
    return re.sub(r"\s*([,;:()\[\]{}])\s*", r"\1", text)


def _bounded(prediction: object, gold: object) -> bool:
    if not isinstance(prediction, str) or not isinstance(gold, str) or len(prediction) > 400:
        return False
    if _norm(prediction) == _norm(gold):
        return True
    cues = re.findall(r"(?i)(?:final\s+answer|answer)\s*(?:is|:)\s*([^\n]+?)(?:[.!]\s*$|$)", prediction.strip())
    if len(cues) != 1 or _norm(cues[0]) != _norm(gold):
        return False
    tuples = {_norm(value) for value in re.findall(r"[\[(][^\])]{1,100}[\])]", prediction)}
    return len(tuples) <= 1 and (not tuples or _norm(gold) in tuples)


def audit() -> None:
    predictions = read_json(PREDICTIONS)
    results = read_json(RESULTS)
    raw = list(predictions.get("rows") or [])
    scored = list(results.get("rows") or [])
    if len(raw) != EXPECTED or len(scored) != EXPECTED or results.get("classification") != "DIAGNOSTIC_UNADMITTED_N10":
        raise ProtocolError("row/classification conservation failed")
    by_id = {str(row["task_id"]): row for row in raw}
    recomputed = {
        "a0_raw_correct": 0, "final_raw_correct": 0,
        "a0_normalized_correct": 0, "final_normalized_correct": 0,
        "raw_rescues": 0, "raw_damages": 0,
        "normalized_rescues": 0, "normalized_damages": 0,
        "answer_changes": 0, "abstentions": 0, "invalid_rows": 0,
        "accounting_invalid_rows": 0, "coverage_gaps": 0, "stage1_verify_resolved": 0,
    }
    for row in scored:
        task_id = str(row["task_id"])
        source = by_id[task_id]
        receipt = RECEIPTS / f"{task_id}.json"
        if sha256_file(receipt) != source["receipt_sha256"]:
            raise ProtocolError(f"receipt hash mismatch: {task_id}")
        gold = row["gold"]
        a0_raw = isinstance(source.get("original_answer"), str) and source["original_answer"] == gold
        final_raw = isinstance(source.get("final_answer"), str) and source["final_answer"] == gold
        a0_norm = _bounded(source.get("original_answer"), gold)
        final_norm = _bounded(source.get("final_answer"), gold)
        values = {
            "a0_raw_correct": a0_raw, "final_raw_correct": final_raw,
            "a0_normalized_correct": a0_norm, "final_normalized_correct": final_norm,
            "raw_rescues": (not a0_raw and final_raw), "raw_damages": (a0_raw and not final_raw),
            "normalized_rescues": (not a0_norm and final_norm), "normalized_damages": (a0_norm and not final_norm),
            "answer_changes": bool(source.get("answer_changed")), "abstentions": bool(source.get("abstention")),
            "invalid_rows": not bool(source.get("row_valid")),
            "accounting_invalid_rows": source.get("accounting_status") != "VALID",
            "coverage_gaps": source.get("row_outcome") == "COVERAGE_GAP",
            "stage1_verify_resolved": source.get("row_outcome") == "VERIFY_RESOLVED",
        }
        for key, value in values.items():
            recomputed[key] += int(bool(value))
    summary = results["summary"]
    mismatch = {key: (summary.get(key), value) for key, value in recomputed.items() if summary.get(key) != value}
    if mismatch:
        raise ProtocolError(f"independent score mismatch: {mismatch}")
    if results.get("production_authorized") or results.get("promotion_authorized"):
        raise ProtocolError("authority unexpectedly enabled")
    print(json.dumps({"audit": "PASS", "rows": len(raw), "predictions_sha256": sha256_file(PREDICTIONS), "recomputed": recomputed}, indent=2, sort_keys=True))


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    audit()
