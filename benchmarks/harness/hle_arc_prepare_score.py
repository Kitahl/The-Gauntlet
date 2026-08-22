from __future__ import annotations

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

SEED = 20260822
HLE_URL = (
    "https://raw.githubusercontent.com/ustc-ai4science/Science-Star/"
    "4abe1db2d6d0920aa0a6236ee2f81de872adafa5/"
    "data/HLE/subset/hle_subset_50.jsonl"
)
ARC_URL = (
    "https://github.com/fchollet/ARC-AGI/archive/"
    "399030444e0ab0cc8b4e199870fb20b863846f34.zip"
)

# One HLE item was exposed with its gold answer earlier in the benchmark session.
# The second exclusion is a deterministic opposite-condition balancing drop.
HLE_EXCLUDED_IDS = {
    "hle-673a76559e89466aa6433f66",
    "hle-67383288f2df805520bc86b5",
}

IMAGE_MARKERS = (
    "attached image",
    "image above",
    "image below",
    "following image",
    "this image",
    "shown in the image",
    "shown in this image",
    "pictured",
    "figure above",
    "figure below",
    "attached figure",
    "this knot",
    "guess the music",
    "small part of the flag",
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "The-Gauntlet-benchmark/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def select_hle() -> tuple[list[dict], dict[str, object]]:
    rows = [
        json.loads(line)
        for line in fetch(HLE_URL).decode("utf-8").splitlines()
        if line.strip()
    ]
    eligible: list[dict] = []
    for row in rows:
        question = str(row.get("question", ""))
        low = question.casefold()
        if row.get("answer_type") != "multipleChoice":
            continue
        if any(marker in low for marker in IMAGE_MARKERS):
            continue
        if len(question) > 6500:
            continue
        eligible.append(row)

    if len(eligible) < 10:
        raise RuntimeError(f"need >=10 eligible HLE items, found {len(eligible)}")

    rng = random.Random(SEED)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        by_category[str(row.get("category") or "Other")].append(row)
    for rows_in_category in by_category.values():
        rng.shuffle(rows_in_category)

    selected: list[dict] = []
    while any(by_category.values()):
        for category in sorted(by_category):
            if by_category[category]:
                selected.append(by_category[category].pop())
    rng.shuffle(selected)

    questions: list[dict] = []
    gold: dict[str, object] = {}
    for index, row in enumerate(selected):
        qid = f"hle-{row['id']}"
        questions.append(
            {
                "id": qid,
                "benchmark": "HLE-public-subset",
                "condition": "BASE" if index % 2 == 0 else "FOIL_MM",
                "category": row.get("category"),
                "answer_type": "multipleChoice",
                "question": row["question"],
            }
        )
        gold[qid] = row["answer"]

    questions = [q for q in questions if q["id"] not in HLE_EXCLUDED_IDS]
    gold = {qid: value for qid, value in gold.items() if qid not in HLE_EXCLUDED_IDS}
    return questions, gold


def select_arc() -> tuple[list[dict], dict[str, object]]:
    archive = zipfile.ZipFile(io.BytesIO(fetch(ARC_URL)))
    candidates: list[tuple[str, dict]] = []
    for name in archive.namelist():
        if "/data/evaluation/" not in name or not name.endswith(".json"):
            continue
        raw = archive.read(name)
        if len(raw) > 7000:
            continue
        task = json.loads(raw)
        if len(task.get("test", [])) != 1 or "output" not in task["test"][0]:
            continue
        test_input = task["test"][0]["input"]
        if len(test_input) > 20:
            continue
        if max((len(row) for row in test_input), default=0) > 20:
            continue
        candidates.append((Path(name).stem, task))

    rng = random.Random(SEED + 1)
    rng.shuffle(candidates)
    selected = candidates[:12]

    questions: list[dict] = []
    gold: dict[str, object] = {}
    for index, (task_id, task) in enumerate(selected):
        qid = f"arc-{task_id}"
        test = task["test"][0]
        questions.append(
            {
                "id": qid,
                "benchmark": "ARC-AGI-1-evaluation",
                "condition": "BASE" if index % 2 == 0 else "FOIL_MM",
                "train": task["train"],
                "test_input": test["input"],
                "instruction": "Infer the transformation and return only the output grid.",
            }
        )
        gold[qid] = test["output"]
    return questions, gold


def prepare() -> tuple[list[dict], dict[str, object]]:
    hle_questions, hle_gold = select_hle()
    arc_questions, arc_gold = select_arc()
    questions = hle_questions + arc_questions
    gold = {**hle_gold, **arc_gold}

    payload = {
        "schema": "foil-benchmark-questions/v2",
        "selection_seed": SEED,
        "sources": {"HLE": HLE_URL, "ARC-AGI-1": ARC_URL},
        "excluded_hle_ids": sorted(HLE_EXCLUDED_IDS),
        "conditions": {
            "BASE": "direct answer; no FOIL/Mastermind",
            "FOIL_MM": "frozen Frontier-Exam FOIL + Mastermind final defect pass; no gold",
        },
        "questions": questions,
    }
    (OUT / "benchmark_questions.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return questions, gold


def score(questions: list[dict], gold: dict[str, object]) -> None:
    predictions_path = OUT / "predictions.json"
    if not predictions_path.exists():
        return

    predictions_data = json.loads(predictions_path.read_text(encoding="utf-8"))
    predictions = {
        row["id"]: row.get("answer") for row in predictions_data.get("predictions", [])
    }
    items: list[dict] = []
    aggregate: dict[tuple[str, str], list[int]] = defaultdict(list)

    for question in questions:
        qid = question["id"]
        if question["benchmark"].startswith("HLE"):
            correct = normalize(predictions.get(qid)) == normalize(gold[qid])
        else:
            correct = predictions.get(qid) == gold[qid]
        items.append(
            {
                "id": qid,
                "benchmark": question["benchmark"],
                "condition": question["condition"],
                "correct": bool(correct),
            }
        )
        aggregate[(question["benchmark"], question["condition"])].append(int(correct))

    summary = [
        {
            "benchmark": benchmark,
            "condition": condition,
            "correct": sum(values),
            "n": len(values),
            "accuracy": sum(values) / len(values),
        }
        for (benchmark, condition), values in sorted(aggregate.items())
    ]
    result = {
        "schema": "foil-benchmark-results/v2",
        "selection_seed": SEED,
        "summary": summary,
        "items": items,
        "validity_boundary": (
            "Exploratory in-session disjoint-subset pilot; not an official submission. "
            "Same-item causal A/B requires isolated executions."
        ),
    }
    (OUT / "benchmark_results.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    hle_n = sum(q["benchmark"].startswith("HLE") for q in questions)
    arc_n = sum(q["benchmark"].startswith("ARC") for q in questions)
    print(f"prepared {len(questions)} blinded questions: HLE={hle_n}, ARC={arc_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
