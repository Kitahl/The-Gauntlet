#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict

from common import index_unique, mean, read_jsonl, safe_div, spearman, write_result


def score(gold_path: str, pred_path: str) -> dict:
    gold = index_unique(read_jsonl(gold_path), ("sample_id",))
    predictions = read_jsonl(pred_path)
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for pred in predictions:
        sample_id = pred["sample_id"]
        if (sample_id,) not in gold:
            raise ValueError(f"prediction references unknown sample_id {sample_id}")
        by_arm[pred["arm"]].append(pred)

    result: dict[str, dict] = {}
    for arm, rows in sorted(by_arm.items()):
        seen: set[str] = set()
        ys: list[float] = []
        ps: list[float] = []
        confusion = [[0 for _ in range(5)] for _ in range(5)]
        per_label: dict[str, list[tuple[int, int]]] = defaultdict(list)
        high_fp_num = high_fp_den = low_fn_num = low_fn_den = 0
        for pred in rows:
            sid = pred["sample_id"]
            if sid in seen:
                raise ValueError(f"duplicate prediction for {sid} in arm {arm}")
            seen.add(sid)
            y = int(gold[(sid,)]["novelty_score"])
            p = int(pred["predicted_novelty_score"])
            if not (1 <= y <= 5 and 1 <= p <= 5):
                raise ValueError("novelty scores must be 1..5")
            ys.append(float(y))
            ps.append(float(p))
            confusion[y - 1][p - 1] += 1
            per_label[str(y)].append((y, p))
            if y <= 2:
                high_fp_den += 1
                high_fp_num += int(p >= 4)
            if y >= 4:
                low_fn_den += 1
                low_fn_num += int(p <= 2)
        n = len(rows)
        label_result = {}
        for label in map(str, range(1, 6)):
            pairs = per_label.get(label, [])
            label_result[label] = {
                "N": len(pairs),
                "MAE": mean(abs(y - p) for y, p in pairs),
                "exact_accuracy": mean(float(y == p) for y, p in pairs),
            }
        result[arm] = {
            "N": n,
            "MAE": mean(abs(y - p) for y, p in zip(ys, ps)),
            "exact_score_accuracy": mean(float(y == p) for y, p in zip(ys, ps)),
            "within_1_accuracy": mean(float(abs(y - p) <= 1) for y, p in zip(ys, ps)),
            "spearman_rho": spearman(ys, ps),
            "confusion_matrix_gold_rows_pred_columns": confusion,
            "high_novelty_false_positive_rate": safe_div(high_fp_num, high_fp_den),
            "low_novelty_false_negative_rate": safe_div(low_fn_num, low_fn_den),
            "per_gold_label": label_result,
        }
    return {"benchmark": "RINoBench", "arms": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold")
    parser.add_argument("predictions")
    args = parser.parse_args()
    write_result(score(args.gold, args.predictions))


if __name__ == "__main__":
    main()
