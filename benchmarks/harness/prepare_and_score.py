from __future__ import annotations

import csv
import io
import json
import random
import re
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
GPQA_URL = "https://raw.githubusercontent.com/idavidrein/gpqa/main/dataset.zip"
SEED = 20260822
HLE_TARGET = 14
GPQA_TARGET = 24

IMAGE_MARKERS = (
    "attached image", "image above", "image below", "following image", "this image",
    "shown in the image", "shown in this image", "pictured", "figure above", "figure below",
    "attached figure", "this knot", "guess the music", "small part of the flag",
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "The-Gauntlet-benchmark/0.2"})
    with urllib.request.urlopen(req, timeout=90) as r:
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
    if len(eligible) < HLE_TARGET:
        raise RuntimeError(f"need >={HLE_TARGET} eligible HLE rows, found {len(eligible)}")

    rng = random.Random(SEED)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        by_cat[str(row.get("category") or "Other")].append(row)
    for rows_ in by_cat.values():
        rng.shuffle(rows_)

    selected: list[dict] = []
    cats = sorted(by_cat)
    while len(selected) < HLE_TARGET:
        progressed = False
        for cat in cats:
            if by_cat[cat] and len(selected) < HLE_TARGET:
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
            "benchmark": "HLE-public-text-subset",
            "condition": condition,
            "category": row.get("category"),
            "answer_type": row.get("answer_type"),
            "question": row["question"],
        })
        gold[bid] = str(row["answer"]).strip()
    return questions, gold


def _gpqa_csv_from_zip(blob: bytes) -> tuple[str, bytes]:
    zf = zipfile.ZipFile(io.BytesIO(blob))
    names = [n for n in zf.namelist() if n.lower().endswith(".csv") and "diamond" in n.lower()]
    if not names:
        raise RuntimeError(f"GPQA archive contains no diamond CSV; names={zf.namelist()[:50]}")
    name = sorted(names)[0]
    return name, zf.read(name)


def select_gpqa() -> tuple[list[dict], dict[str, object]]:
    source_name, raw = _gpqa_csv_from_zip(fetch(GPQA_URL))
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"Question", "Correct Answer", "Incorrect Answer 1", "Incorrect Answer 2", "Incorrect Answer 3"}
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError(f"unexpected GPQA columns in {source_name}: {list(rows[0]) if rows else []}")
    if len(rows) < GPQA_TARGET:
        raise RuntimeError(f"need >={GPQA_TARGET} GPQA-Diamond rows, found {len(rows)}")

    rng = random.Random(SEED + 1)
    order = list(range(len(rows)))
    rng.shuffle(order)
    selected = [(idx, rows[idx]) for idx in order[:GPQA_TARGET]]

    questions: list[dict] = []
    gold: dict[str, object] = {}
    letters = "ABCD"
    for i, (source_idx, row) in enumerate(selected):
        options = [
            (str(row["Correct Answer"]), True),
            (str(row["Incorrect Answer 1"]), False),
            (str(row["Incorrect Answer 2"]), False),
            (str(row["Incorrect Answer 3"]), False),
        ]
        item_rng = random.Random(SEED * 100000 + source_idx)
        item_rng.shuffle(options)
        correct_pos = next(j for j, (_, is_correct) in enumerate(options) if is_correct)
        bid = f"gpqa-diamond-{source_idx}"
        condition = "BASE" if i % 2 == 0 else "FOIL_MM"
        prompt = str(row["Question"]).strip() + "\n\n" + "\n".join(
            f"{letters[j]}. {answer}" for j, (answer, _) in enumerate(options)
        )
        questions.append({
            "id": bid,
            "benchmark": "GPQA-Diamond",
            "condition": condition,
            "category": str(row.get("High-level domain") or row.get("Subdomain") or "unknown"),
            "answer_type": "multipleChoice",
            "question": prompt,
            "instruction": "Return one option letter A-D.",
        })
        gold[bid] = letters[correct_pos]
    return questions, gold


def prepare() -> tuple[list[dict], dict[str, object]]:
    hq, hg = select_hle()
    gq, gg = select_gpqa()
    questions = hq + gq
    gold = {**hg, **gg}
    (OUT / "benchmark_questions.json").write_text(
        json.dumps({
            "schema": "foil-benchmark-questions/v2",
            "selection_seed": SEED,
            "conditions": {
                "BASE": "direct GPT-5.6 Sol answer; closed-book; no FOIL/Mastermind protocol",
                "FOIL_MM": "Frontier-Exam FOIL + Mastermind defect pass; closed-book; no benchmark gold",
            },
            "protocol": {
                "HLE": f"all {HLE_TARGET} eligible text-only multiple-choice rows from pinned public HLE subset; alternating disjoint assignment",
                "GPQA": f"{GPQA_TARGET} deterministically sampled GPQA-Diamond rows; options independently shuffled; alternating disjoint assignment",
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
        ok = norm_text(pred) == norm_text(gold[qid])
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
        "schema": "foil-benchmark-results/v2",
        "selection_seed": SEED,
        "summary": summary,
        "items": rows,
        "validity_boundary": (
            "Exploratory in-session disjoint-subset pilot using the same underlying model. "
            "Not an official HLE or GPQA submission. Same-item causal A/B requires isolated model executions."
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
