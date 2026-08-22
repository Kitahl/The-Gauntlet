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

GPQA_URL = "https://raw.githubusercontent.com/idavidrein/gpqa/main/dataset.zip"
SEED = 20260825
TARGET = 24
LETTERS = "ABCD"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "The-Gauntlet-benchmark/0.4"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def load_diamond() -> list[dict[str, str]]:
    archive = zipfile.ZipFile(io.BytesIO(fetch(GPQA_URL)))
    names = [name for name in archive.namelist() if name.lower().endswith(".csv") and "diamond" in name.lower()]
    if not names:
        raise RuntimeError(f"GPQA archive contains no Diamond CSV: {archive.namelist()[:50]}")
    raw = archive.read(sorted(names)[0]).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    required = {"Question", "Correct Answer", "Incorrect Answer 1", "Incorrect Answer 2", "Incorrect Answer 3"}
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError(f"unexpected GPQA columns: {list(rows[0]) if rows else []}")
    return rows


def prepare() -> tuple[list[dict], dict[str, str]]:
    rows = load_diamond()
    if len(rows) < TARGET:
        raise RuntimeError(f"need >= {TARGET} GPQA-Diamond rows, found {len(rows)}")

    rng = random.Random(SEED)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    selected = indices[:TARGET]

    questions: list[dict] = []
    gold: dict[str, str] = {}
    for ordinal, source_index in enumerate(selected):
        row = rows[source_index]
        options = [
            (str(row["Correct Answer"]), True),
            (str(row["Incorrect Answer 1"]), False),
            (str(row["Incorrect Answer 2"]), False),
            (str(row["Incorrect Answer 3"]), False),
        ]
        random.Random(SEED * 1000 + source_index).shuffle(options)
        correct_index = next(i for i, (_, correct) in enumerate(options) if correct)
        qid = f"gpqa-diamond-{source_index:03d}"
        condition = "BASE" if ordinal % 2 == 0 else "FOIL_MM"
        questions.append({
            "id": qid,
            "benchmark": "GPQA-Diamond",
            "condition": condition,
            "category": row.get("High-level domain") or row.get("Subdomain") or "unknown",
            "question": str(row["Question"]).strip(),
            "choices": {LETTERS[i]: answer for i, (answer, _) in enumerate(options)},
            "instruction": "Closed book. Return only one option letter A-D.",
        })
        gold[qid] = LETTERS[correct_index]

    payload = {
        "schema": "foil-gpqa-questions/v1",
        "selection_seed": SEED,
        "source": GPQA_URL,
        "sample_n": TARGET,
        "conditions": {
            "BASE": "direct GPT-5.6 Sol answer; closed-book; no FOIL/Mastermind protocol",
            "FOIL_MM": "same underlying model with frozen Frontier-Exam FOIL + Mastermind final defect pass; closed-book; no gold",
        },
        "questions": questions,
    }
    (OUT / "gpqa_questions.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return questions, gold


def score(questions: list[dict], gold: dict[str, str]) -> None:
    pred_path = OUT / "gpqa_predictions.json"
    if not pred_path.exists():
        return
    raw = json.loads(pred_path.read_text(encoding="utf-8"))
    predictions = {str(row["id"]): row.get("answer") for row in raw.get("predictions", [])}

    items: list[dict] = []
    agg: dict[str, list[int]] = defaultdict(list)
    for question in questions:
        qid = question["id"]
        predicted = predictions.get(qid)
        correct = norm(predicted) == norm(gold[qid])
        items.append({"id": qid, "condition": question["condition"], "correct": correct})
        agg[question["condition"]].append(int(correct))

    summary = []
    for condition in ("BASE", "FOIL_MM"):
        values = agg[condition]
        summary.append({
            "benchmark": "GPQA-Diamond",
            "condition": condition,
            "correct": sum(values),
            "n": len(values),
            "accuracy": sum(values) / len(values) if values else None,
        })

    result = {
        "schema": "foil-gpqa-results/v1",
        "selection_seed": SEED,
        "summary": summary,
        "items": items,
        "validity_boundary": (
            "Exploratory in-session disjoint-subset pilot using the same underlying model. "
            "Not an official GPQA submission; same-item causal A/B requires isolated executions."
        ),
    }
    (OUT / "gpqa_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    print(f"prepared {len(questions)} GPQA-Diamond questions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
