#!/usr/bin/env python3
"""Aggregate compatible ProjectionBench atomic-claim alignment counts."""
from __future__ import annotations

import argparse
from collections import defaultdict

from common import mean, read_jsonl, safe_div, write_result

LEVELS = ("L0", "L1", "L2")


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = 0.0 if (precision == 0 or recall == 0) else None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def score(counts_path: str, mode: str) -> dict:
    rows = read_jsonl(counts_path)
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        level = row["disclosure_level"]
        if level not in LEVELS:
            raise ValueError("disclosure_level must be L0/L1/L2")
        for key in ("tp", "fp", "fn"):
            if int(row[key]) < 0:
                raise ValueError(f"{key} must be non-negative")
        grouped[(row["arm"], row.get("domain", "UNKNOWN"), level)].append(row)

    arms = sorted({key[0] for key in grouped})
    result = {}
    for arm in arms:
        by_level = {}
        f1s: list[float] = []
        for level in LEVELS:
            level_rows = [row for (a, _d, l), rs in grouped.items() if a == arm and l == level for row in rs]
            tp = sum(int(r["tp"]) for r in level_rows)
            fp = sum(int(r["fp"]) for r in level_rows)
            fn = sum(int(r["fn"]) for r in level_rows)
            p, r, f = prf(tp, fp, fn)
            by_level[level] = {"N": len(level_rows), "precision": p, "recall": r, "F1": f}
            f1s.append(0.0 if f is None else f)
        auc = (f1s[0] + 2 * f1s[1] + f1s[2]) / 4.0
        domains = {}
        for domain in sorted({key[1] for key in grouped if key[0] == arm}):
            domain_rows = [row for (a, d, _l), rs in grouped.items() if a == arm and d == domain for row in rs]
            domains[domain] = {
                "N": len(domain_rows),
                "mean_row_f1": mean(
                    (lambda q: 0.0 if q[2] is None else q[2])(
                        prf(int(r["tp"]), int(r["fp"]), int(r["fn"]))
                    )
                    for r in domain_rows
                ),
            }
        result[arm] = {"levels": by_level, "normalized_F1_disclosure_AUC": auc, "per_domain": domains}
    return {"benchmark": "ProjectionBench", "evaluation_mode": mode, "arms": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("alignment_counts")
    parser.add_argument(
        "--mode",
        default="PROJECTIONBENCH_COMPATIBLE_ADAPTATION",
        choices=["PROJECTIONBENCH_OFFICIAL", "PROJECTIONBENCH_COMPATIBLE_ADAPTATION"],
    )
    args = parser.parse_args()
    write_result(score(args.alignment_counts, args.mode))


if __name__ == "__main__":
    main()
