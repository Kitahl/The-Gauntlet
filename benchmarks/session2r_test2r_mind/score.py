#!/usr/bin/env python3
"""Score immutable BASE and MIND receipts for Session 2R / Test 2R."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD_PATH = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT" / "gold.jsonl"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return [max(0.0, center - half), min(1.0, center + half)]


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    tail = sum(math.comb(n, i) for i in range(m + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def answer_text(row: dict) -> str:
    ans = row.get("answer")
    if ans is None:
        return ""
    return str(ans).strip()


def response_text(row: dict) -> str:
    response = row.get("response")
    return str(response if response is not None else row.get("answer", ""))


def summarize_binary(rows):
    k = sum(1 for r in rows if r["correct"] is True)
    n = len(rows)
    return {"correct": k, "n": n, "accuracy": k / n if n else None, "wilson95": wilson(k, n)}


def paired_summary(base_rows, mind_rows):
    bmap = {r["id"]: r for r in base_rows}
    mmap = {r["id"]: r for r in mind_rows}
    cells = Counter()
    discordant = []
    for item_id in bmap:
        b = bool(bmap[item_id]["correct"])
        m = bool(mmap[item_id]["correct"])
        if b and m:
            cells["both_correct"] += 1
        elif (not b) and (not m):
            cells["both_wrong"] += 1
        elif (not b) and m:
            cells["base_wrong_mind_right"] += 1
            discordant.append(item_id)
        else:
            cells["base_right_mind_wrong"] += 1
            discordant.append(item_id)
    bw_mr = cells["base_wrong_mind_right"]
    br_mw = cells["base_right_mind_wrong"]
    return {
        **dict(cells),
        "mcnemar_exact_two_sided_p": exact_mcnemar(bw_mr, br_mw),
        "discordant_ids": discordant,
    }


def group_accuracy(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "unknown"))].append(row)
    return {k: summarize_binary(v) for k, v in sorted(groups.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--mind", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    base = read_jsonl(args.base)
    mind = read_jsonl(args.mind)
    gold = read_jsonl(GOLD_PATH)
    gold_by_id = {r["id"]: r for r in gold}
    expected_ids = [r["id"] for r in gold]
    if len(base) != 90 or len(mind) != 90:
        raise SystemExit(f"receipts must each contain exactly 90 predictions: base={len(base)} mind={len(mind)}")
    if [r.get("id") for r in base] != expected_ids or [r.get("id") for r in mind] != expected_ids:
        raise SystemExit("receipt ID/order mismatch against frozen package")

    omni = load_module(ROOT / "scoring" / "omni_grader.py", "omni_grader_score")
    bbeh = load_module(ROOT / "scoring" / "bbeh_evaluate.py", "bbeh_eval_score")

    def score_arm(receipt, condition):
        out = []
        for row in receipt:
            g = gold_by_id[row["id"]]
            answer = answer_text(row)
            try:
                if g["benchmark"] == "omni_math_rule":
                    correct = bool(omni.math_equal(answer, str(g["reference_answer"]), timeout=True))
                else:
                    correct = bool(bbeh.evaluate_correctness(response_text(row), str(g["target"])))
                scorer_error = None
            except Exception as exc:
                correct = False
                scorer_error = f"{type(exc).__name__}: {exc}"
            out.append({
                "id": row["id"],
                "condition": condition,
                "benchmark": g["benchmark"],
                "section": g["section"],
                "family": g.get("family"),
                "difficulty": g.get("difficulty"),
                "domain": g.get("domain"),
                "correct": correct,
                "scorer_error": scorer_error,
                "response_chars": len(response_text(row)),
            })
        return out

    bs = score_arm(base, "BASE")
    ms = score_arm(mind, "MIND")

    report = {
        "experiment_id": "SESSION2R_TEST2R_MIND",
        "primary_omni": {},
        "secondary_bbeh_formal": {},
        "exploratory_bbeh_state_tracking": {},
        "cost": {},
    }
    for section in ("primary_omni", "secondary_bbeh_formal", "exploratory_bbeh_state_tracking"):
        bsec = [r for r in bs if r["section"] == section]
        msec = [r for r in ms if r["section"] == section]
        target = report[section]
        target["BASE"] = summarize_binary(bsec)
        target["MIND"] = summarize_binary(msec)
        target["accuracy_delta_pp"] = 100 * (target["MIND"]["accuracy"] - target["BASE"]["accuracy"])
        target["paired"] = paired_summary(bsec, msec)
        if section == "primary_omni":
            target["BASE_by_difficulty"] = group_accuracy(bsec, "difficulty")
            target["MIND_by_difficulty"] = group_accuracy(msec, "difficulty")
            target["BASE_by_domain"] = group_accuracy(bsec, "domain")
            target["MIND_by_domain"] = group_accuracy(msec, "domain")
        else:
            target["BASE_by_family"] = group_accuracy(bsec, "family")
            target["MIND_by_family"] = group_accuracy(msec, "family")

    for label, rows in (("BASE", bs), ("MIND", ms)):
        chars = [r["response_chars"] for r in rows]
        ordered = sorted(chars)
        report["cost"][label] = {
            "total_response_chars": sum(chars),
            "mean_response_chars": sum(chars) / len(chars),
            "median_response_chars": (ordered[44] + ordered[45]) / 2,
        }

    report["all_scored_rows"] = bs + ms
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
