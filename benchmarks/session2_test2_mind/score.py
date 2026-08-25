#!/usr/bin/env python3
"""Score committed Session 2 / Test 2 predictions after both arms commit."""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"

try:
    from grader import math_equal as upstream_math_equal
except Exception:
    upstream_math_equal = None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_answer(row: dict[str, Any]) -> str:
    if row.get("answer") is not None:
        return str(row["answer"]).strip()
    response = str(row.get("response") or "").strip()
    matches = re.findall(r"FINAL\s+ANSWER\s*:\s*(.+)", response, flags=re.I)
    if matches:
        return matches[-1].strip()
    return response


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"^\\boxed\{(.*)\}$", r"\1", text)
    text = text.strip("$ ").rstrip(".")
    text = re.sub(r"\s+", " ", text)
    return text


def choice(value: str) -> str | None:
    found = re.findall(r"(?:^|\b|\()([a-k])(?:\b|\)|$)", value.lower())
    return found[-1].upper() if found else None


def bbeh_equal(prediction: str, target: str) -> bool:
    p_choice, t_choice = choice(prediction), choice(target)
    if t_choice and p_choice:
        return p_choice == t_choice
    p = normalize(prediction).strip("<>[]() ")
    t = normalize(target).strip("<>[]() ")
    p = re.sub(r"\s*,\s*", ",", p)
    t = re.sub(r"\s*,\s*", ",", t)
    return p == t


def omni_equal(prediction: str, reference: str) -> tuple[bool, str]:
    if normalize(prediction) == normalize(reference):
        return True, "normalized_exact"
    if upstream_math_equal is not None:
        try:
            if bool(upstream_math_equal(prediction, reference, timeout=True)):
                return True, "omni_math_rule"
        except Exception:
            pass
    return False, "unmatched"


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path, help="JSONL with id, condition, and answer or response")
    parser.add_argument("--out", type=Path, default=ROOT / "score_report.json")
    args = parser.parse_args()

    assignments = json.loads((ROOT / "assignments.json").read_text(encoding="utf-8"))["assignments"]
    assignment_by_id = {row["id"]: row for row in assignments}
    predictions = load_jsonl(args.predictions)
    pred_by_id: dict[str, dict[str, Any]] = {}
    for row in predictions:
        item_id = str(row.get("id") or "")
        if item_id in pred_by_id:
            raise SystemExit(f"duplicate prediction id: {item_id}")
        if item_id not in assignment_by_id:
            raise SystemExit(f"unknown prediction id: {item_id}")
        expected = assignment_by_id[item_id]["condition"]
        if str(row.get("condition") or "").upper() != expected:
            raise SystemExit(f"{item_id}: expected condition {expected}")
        pred_by_id[item_id] = row
    missing = sorted(set(assignment_by_id) - set(pred_by_id))
    if missing:
        raise SystemExit(f"missing {len(missing)} predictions: {missing[:5]}")

    gold_rows = load_jsonl(GOLD / "omni_math_rule_gold.jsonl") + load_jsonl(GOLD / "bbeh_gold.jsonl")
    gold_by_id = {row["id"]: row for row in gold_rows}
    item_results = []
    totals: dict[tuple[str, str], list[bool]] = defaultdict(list)
    unresolved_omni = []

    for assignment in assignments:
        item_id = assignment["id"]
        pred = extract_answer(pred_by_id[item_id])
        gold = gold_by_id[item_id]
        if assignment["benchmark"] == "bbeh":
            correct = bbeh_equal(pred, str(gold["target"]))
            method = "bbeh_normalized_exact"
        else:
            correct, method = omni_equal(pred, str(gold["reference_answer"]))
            if not correct and method == "unmatched":
                unresolved_omni.append(item_id)
        totals[(assignment["condition"], assignment["benchmark"])].append(correct)
        item_results.append({
            "id": item_id,
            "condition": assignment["condition"],
            "benchmark": assignment["benchmark"],
            "correct": correct,
            "scoring_method": method,
            "prediction": pred,
        })

    summary = {}
    for (condition, benchmark), values in sorted(totals.items()):
        k, n = sum(values), len(values)
        low, high = wilson(k, n)
        summary[f"{condition}:{benchmark}"] = {
            "correct": k,
            "n": n,
            "accuracy": k / n,
            "wilson_95": [low, high],
        }

    report = {
        "schema": "gauntlet.session2.test2.score.v1",
        "summary": summary,
        "unresolved_omni_mismatches": unresolved_omni,
        "note": "Omni mismatches require reference-solution adjudication if the optional official rule-evaluator dependencies are unavailable; do not silently count an unresolved equivalence case as an error.",
        "items": item_results,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if unresolved_omni:
        print(f"REVIEW REQUIRED: {len(unresolved_omni)} Omni-MATH mismatches")


if __name__ == "__main__":
    main()
