#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict

from common import index_unique, read_jsonl, safe_div, write_result


def score(relations_path: str, predictions_path: str) -> dict:
    relations = read_jsonl(relations_path)
    preds = index_unique(read_jsonl(predictions_path), ("arm", "sample_id", "pool_id"))
    counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_axiom: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    per_family: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    arms = sorted({key[0] for key in preds})
    for arm in arms:
        for rel in relations:
            sid = rel["sample_id"]
            lhs = preds[(arm, sid, rel["lhs_pool_id"])]["novelty_score_0_100"]
            rhs = preds[(arm, sid, rel["rhs_pool_id"])]["novelty_score_0_100"]
            relation = rel["expected_relation"]
            if relation not in {"<", ">"}:
                raise ValueError("expected_relation must be '<' or '>'")
            if lhs == rhs:
                outcome = "tie"
            elif (relation == "<" and lhs < rhs) or (relation == ">" and lhs > rhs):
                outcome = "pass"
            else:
                outcome = "wrong_way"
            counters[arm][outcome] += 1
            per_axiom[arm][rel["axiom"]][outcome] += 1
            per_family[arm][rel["probe_family"]][outcome] += 1

    def summarize(counts: dict[str, int]) -> dict:
        total = sum(counts.values())
        return {
            "N": total,
            "pass_rate": safe_div(counts.get("pass", 0), total),
            "tie_rate": safe_div(counts.get("tie", 0), total),
            "wrong_way_rate": safe_div(counts.get("wrong_way", 0), total),
        }

    return {
        "benchmark": "AXIOMATIC_ADAPTATION_V1",
        "arms": {
            arm: {
                "aggregate": summarize(counters[arm]),
                "per_axiom": {name: summarize(counts) for name, counts in sorted(per_axiom[arm].items())},
                "per_probe_family": {
                    name: summarize(counts) for name, counts in sorted(per_family[arm].items())
                },
            }
            for arm in arms
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold_relations")
    parser.add_argument("predictions")
    args = parser.parse_args()
    write_result(score(args.gold_relations, args.predictions))


if __name__ == "__main__":
    main()
