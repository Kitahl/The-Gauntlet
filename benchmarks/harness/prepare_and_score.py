from __future__ import annotations

import io
import json
import random
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-22"
OUT.mkdir(parents=True, exist_ok=True)

HLE_URL = (
    "https://raw.githubusercontent.com/ustc-ai4science/Science-Star/"
    "4abe1db2d6d0920aa0a6236ee2f81de872adafa5/data/HLE/subset/hle_subset_50.jsonl"
)
ARC_URL = "https://github.com/fchollet/ARC-AGI/archive/refs/heads/master.zip"
SEED = 20260822

IMAGE_MARKERS = (
    "attached image", "image above", "image below", "following image", "this image",
    "shown in the image", "shown in this image", "pictured", "figure above", "figure below",
    "attached figure", "this knot", "guess the music", "small part of the flag",
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "The-Gauntlet-benchmark/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm_text(x: object) -> str:
    return re.sub(r"\s+", " ", str(x).strip()).casefold()


def select_hle() -> tuple[list[dict], dict[str, object]]:
    rows = [json.loads(line) for line in fetch(HLE_URL).decode("utf-8").splitlines() if line.strip()]
    eligible = []
    for row in rows:
        q = str(row.get("question", ""))
        low = q.casefold()
        if row.get("answer_type") != "multipleChoice":
            continue
        if any(marker in low for marker in IMAGE_MARKERS):
            continue
        if len(q) > 6500:
            continue
        eligible.append(row)
    if len(eligible) < 20:
        raise RuntimeError(f"need >=20 eligible HLE rows, found {len(eligible)}")

    rng = random.Random(SEED)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        by_cat[str(row.get("category") or "Other")].append(row)
    for rows_ in by_cat.values():
        rng.shuffle(rows_)

    selected: list[dict] = []
    cats = sorted(by_cat)
    while len(selected) < 20:
        progressed = False
        for cat in cats:
            if by_cat[cat] and len(selected) < 20:
                selected.append(by_cat[cat].pop())
                progressed = True
        if not progressed:
            break
    rng.shuffle(selected)

    questions: list[dict] = []
    gold: dict[str, object] = {}
    for i, row in enumerate(selected):
        bid = f"hle-{row['id']}"
        condition = "BASE" if i % 2 == 0 else "FOIL_MM"
        questions.append({
            "id": bid,
            "benchmark": "HLE-public-subset",
            "condition": condition,
            "category": row.get("category"),
            "answer_type": row.get("answer_type"),
            "question": row["question"],
        })
        gold[bid] = row["answer"]
    return questions, gold


def select_arc() -> tuple[list[dict], dict[str, object]]:
    blob = fetch(ARC_URL)
    zf = zipfile.ZipFile(io.BytesIO(blob))
    candidates = []
    for name in zf.namelist():
        if "/data/evaluation/" not in name or not name.endswith(".json"):
            continue
        raw = zf.read(name)
        if len(raw) > 7000:
            continue
        task = json.loads(raw)
        if len(task.get("test", [])) != 1:
            continue
        test = task["test"][0]
        if "output" not in test:
            continue
        inp = test["input"]
        if len(inp) > 20 or max((len(r) for r in inp), default=0) > 20:
            continue
        candidates.append((Path(name).stem, task))
    if len(candidates) < 12:
        raise RuntimeError(f"need >=12 eligible ARC rows, found {len(candidates)}")
    rng = random.Random(SEED + 1)
    rng.shuffle(candidates)
    selected = candidates[:12]

    questions: list[dict] = []
    gold: dict[str, object] = {}
    for i, (task_id, task) in enumerate(selected):
        bid = f"arc-{task_id}"
        condition = "BASE" if i % 2 == 0 else "FOIL_MM"
        train = task["train"]
        test = task["test"][0]
        questions.append({
            "id": bid,
            "benchmark": "ARC-AGI-1-evaluation",
            "condition": condition,
            "train": train,
            "test_input": test["input"],
            "instruction": "Infer the transformation from training pairs and return only the output grid for test_input.",
        })
        gold[bid] = test["output"]
    return questions, gold


def prepare() -> tuple[list[dict], dict[str, object]]:
    hq, hg = select_hle()
    aq, ag = select_arc()
    questions = hq + aq
    gold = {**hg, **ag}
    (OUT / "benchmark_questions.json").write_text(
        json.dumps({
            "schema": "foil-benchmark-questions/v1",
            "selection_seed": SEED,
            "conditions": {
                "BASE": "direct underlying-model answer; no FOIL/Mastermind protocol",
                "FOIL_MM": "Frontier-Exam FOIL + Mastermind final defect pass; no benchmark gold",
            },
            "questions": questions,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return questions, gold


def score(questions: list[dict], gold: dict[str, object]) -> None:
    pred_path = OUT / "predictions.json"
    if not pred_path.exists():
        return
    data = json.loads(pred_path.read_text(encoding="utf-8"))
    preds = {str(x["id"]): x.get("answer") for x in data.get("predictions", [])}
    rows = []
    agg: dict[tuple[str, str], list[int]] = defaultdict(list)
    for q in questions:
        qid = q["id"]
        pred = preds.get(qid)
        if q["benchmark"].startswith("HLE"):
            ok = norm_text(pred) == norm_text(gold[qid])
        else:
            ok = pred == gold[qid]
        rows.append({"id": qid, "benchmark": q["benchmark"], "condition": q["condition"], "correct": bool(ok)})
        agg[(q["benchmark"], q["condition"])].append(int(ok))

    summary = []
    for (benchmark, condition), vals in sorted(agg.items()):
        summary.append({
            "benchmark": benchmark,
            "condition": condition,
            "correct": sum(vals),
            "n": len(vals),
            "accuracy": sum(vals) / len(vals) if vals else None,
        })
    result = {
        "schema": "foil-benchmark-results/v1",
        "selection_seed": SEED,
        "summary": summary,
        "items": rows,
        "validity_boundary": (
            "Exploratory in-session disjoint-subset pilot; not an official benchmark submission. "
            "Same-item causal A/B requires isolated model executions."
        ),
    }
    (OUT / "benchmark_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    print(f"prepared {len(questions)} blinded questions at {OUT / 'benchmark_questions.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
