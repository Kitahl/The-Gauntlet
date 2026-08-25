#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    fq = read_jsonl(ROOT / "questions" / "freshqa_questions.jsonl")
    ab = read_jsonl(ROOT / "questions" / "assistantbench_questions.jsonl")
    fg = read_jsonl(GOLD / "freshqa_gold.jsonl")
    ag = read_jsonl(GOLD / "assistantbench_gold.jsonl")
    assignments = json.loads((ROOT / "assignments.json").read_text(encoding="utf-8"))["assignments"]
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))

    assert len(fq) == 20 and len(ab) == 20
    assert len(fg) == 20 and len(ag) == 20
    assert len(assignments) == 40
    assert len({x["id"] for x in fq + ab}) == 40
    assert {x["id"] for x in fq} == {x["id"] for x in fg}
    assert {x["id"] for x in ab} == {x["id"] for x in ag}

    prohibited = ("answer", "gold", "explanation", "reference", "solution")
    for rec in fq + ab:
        bad = [k for k in rec if any(p in k.lower() for p in prohibited)]
        assert not bad, (rec["id"], bad)

    for cond in ["BASE", "SPACE"]:
        rows = [x for x in assignments if x["condition"] == cond]
        assert len(rows) == 20
        assert len([x for x in rows if x["benchmark"] == "FreshQA"]) == 10
        assert len([x for x in rows if x["benchmark"] == "AssistantBench"]) == 10

    for bench in ["FreshQA", "AssistantBench"]:
        pairs = {}
        for x in [a for a in assignments if a["benchmark"] == bench]:
            pairs.setdefault(x["pair_id"], set()).add(x["condition"])
        assert len(pairs) == 10
        assert all(v == {"BASE", "SPACE"} for v in pairs.values())

    assert manifest["counts"] == {"assistantbench_total":20,"base_total":20,"freshqa_total":20,"space_total":20}
    print("VALID: 40 question-only tasks, 20 BASE, 20 SPACE, sealed gold boundary intact")

if __name__ == "__main__":
    main()
