#!/usr/bin/env python3
"""Aggregate externally produced official/compatible ResearchBench judge scores.

This scorer does not pretend to reproduce the model-based official judge by itself.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from common import mean, read_jsonl, write_result


def score(judged_path: str, mode: str) -> dict:
    rows = read_jsonl(judged_path)
    by_arm: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = float(row["matched_score_0_5"])
        if not 0 <= value <= 5:
            raise ValueError("matched_score_0_5 must be in [0,5]")
        by_arm[row["arm"]].append(value)
    return {
        "benchmark": "ResearchBench-Hypothesis-Composition",
        "evaluation_mode": mode,
        "arms": {
            arm: {
                "N": len(values),
                "mean_matched_score_0_5": mean(values),
                "normalized_accuracy": mean(v / 5.0 for v in values),
            }
            for arm, values in sorted(by_arm.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("judged_scores")
    parser.add_argument(
        "--mode",
        default="RESEARCHBENCH_COMPATIBLE_JUDGE_ADAPTATION",
        choices=["RESEARCHBENCH_OFFICIAL_JUDGE", "RESEARCHBENCH_COMPATIBLE_JUDGE_ADAPTATION"],
    )
    args = parser.parse_args()
    write_result(score(args.judged_scores, args.mode))


if __name__ == "__main__":
    main()
