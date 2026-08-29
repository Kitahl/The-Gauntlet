#!/usr/bin/env python3
"""Aggregate LiveIdeaBench judge outputs without overstating leaderboard comparability."""
from __future__ import annotations

import argparse
from collections import defaultdict

from common import mean, read_jsonl, write_result

DIMS = ("originality", "feasibility", "fluency", "flexibility", "clarity")


def score(judged_path: str, mode: str) -> dict:
    rows = read_jsonl(judged_path)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        for dim in DIMS:
            if dim not in row:
                raise ValueError(f"missing judge dimension {dim}")
            value = float(row[dim])
            if not 0 <= value <= 10:
                raise ValueError(f"{dim} must be in [0,10]")
        grouped[row["arm"]].append(row)
    arms = {}
    for arm, arm_rows in sorted(grouped.items()):
        arms[arm] = {"N": len(arm_rows)}
        for dim in DIMS:
            arms[arm][f"mean_{dim}"] = mean(float(row[dim]) for row in arm_rows)
        arms[arm]["mean_five_dimension_score"] = mean(
            mean(float(row[dim]) for dim in DIMS) or 0.0 for row in arm_rows
        )
    return {"benchmark": "LiveIdeaBench-v2", "evaluation_mode": mode, "arms": arms}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("judged_scores")
    parser.add_argument(
        "--mode",
        default="LIVEIDEABENCH_SINGLE_JUDGE_ADAPTATION",
        choices=["LIVEIDEABENCH_OFFICIAL_V2_PANEL", "LIVEIDEABENCH_SINGLE_JUDGE_ADAPTATION"],
    )
    args = parser.parse_args()
    write_result(score(args.judged_scores, args.mode))


if __name__ == "__main__":
    main()
