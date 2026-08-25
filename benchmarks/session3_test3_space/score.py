#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
sys.path.insert(0, str(ROOT / "scoring"))
from assistantbench.evaluator import question_scorer


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--freshqa-adjudication", help="optional JSON object {id: true/false} for non-exact FreshQA cases")
    args = ap.parse_args()
    preds = {r["id"]: r for r in read_jsonl(args.predictions)}
    assigns = json.loads((ROOT / "assignments.json").read_text(encoding="utf-8"))["assignments"]
    fg = {r["id"]: r for r in read_jsonl(GOLD / "freshqa_gold.jsonl")}
    ag = {r["id"]: r for r in read_jsonl(GOLD / "assistantbench_gold.jsonl")}
    adjud = {}
    if args.freshqa_adjudication:
        adjud = json.loads(Path(args.freshqa_adjudication).read_text(encoding="utf-8"))

    rows=[]
    for a in assigns:
        p = preds.get(a["id"], {})
        answer = p.get("answer", "")
        if a["benchmark"] == "AssistantBench":
            score, has_ans = question_scorer(answer, ag[a["id"]]["answer"])
            status = "SCORED"
        else:
            exact = any(norm(answer) == norm(g) for g in fg[a["id"]]["answers"])
            if exact:
                score, status = 1.0, "EXACT"
            elif a["id"] in adjud:
                score, status = (1.0 if adjud[a["id"]] else 0.0), "ADJUDICATED"
            else:
                score, status = None, "REVIEW_REQUIRED"
            has_ans = 1.0 if str(answer).strip() else 0.0
        rows.append({**a, "answer": answer, "score": score, "has_answer": has_ans, "status": status})

    for bench in ["FreshQA", "AssistantBench"]:
        print(f"\n{bench}")
        for cond in ["BASE", "SPACE"]:
            rr=[r for r in rows if r["benchmark"]==bench and r["condition"]==cond]
            scored=[r for r in rr if r["score"] is not None]
            mean=sum(r["score"] for r in scored)/len(scored) if scored else None
            print(cond, {"scored":len(scored), "n":len(rr), "mean":mean, "review_required":sum(r["score"] is None for r in rr)})
    print("\nTASK RESULTS")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))

if __name__ == "__main__":
    main()
