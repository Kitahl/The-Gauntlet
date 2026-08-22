from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import random
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-22"
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
SEED = 20260824

# Frozen without consulting hidden gold. Some items were excluded after public
# benchmark/agent traces surfaced during search; opposite-condition balancing
# exclusions preserve equal sample counts. Full rationale is in docs/BENCHMARKS.md.
EXCLUDED_IDS = {
    "bc-02-842f7932",
    "bc-05-1f3b974a",
    "bc-07-8eb2d427",
    "bc-12-d8f30932",
    "bc-14-6a55785e",
    "bc-15-c746c21f",
    "bc-16-d067f146",
    "bc-17-c9b9a839",
    "bc-18-d5cf07ab",
    "bc-19-a304e964",
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "The-Gauntlet-benchmark/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def derive_key(password: str, length: int) -> bytes:
    digest = hashlib.sha256(password.encode()).digest()
    return digest * (length // len(digest)) + digest[: length % len(digest)]


def decrypt(value: str, password: str) -> str:
    encrypted = base64.b64decode(value)
    key = derive_key(password, len(encrypted))
    return bytes(a ^ b for a, b in zip(encrypted, key)).decode()


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def prepare() -> tuple[list[dict], dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(fetch(URL).decode("utf-8-sig"))))
    selected = random.Random(SEED).sample(rows, 20)

    questions: list[dict] = []
    gold: dict[str, str] = {}
    for index, row in enumerate(selected):
        qid = f"bc-{index:02d}-{hashlib.sha256(row['problem'].encode()).hexdigest()[:8]}"
        problem = decrypt(row["problem"], row["canary"])
        answer = decrypt(row["answer"], row["canary"])
        questions.append(
            {
                "id": qid,
                "benchmark": "BrowseComp-official-test-subset",
                "condition": "BASE" if index % 2 == 0 else "FOIL_MM",
                "question": problem,
                "instruction": "Use web browsing. Return one succinct exact answer.",
            }
        )
        gold[qid] = answer

    questions = [q for q in questions if q["id"] not in EXCLUDED_IDS]
    gold = {qid: value for qid, value in gold.items() if qid not in EXCLUDED_IDS}
    payload = {
        "schema": "foil-browsecomp-questions/v5",
        "selection_seed": SEED,
        "source": URL,
        "excluded_ids": sorted(EXCLUDED_IDS),
        "conditions": {
            "BASE": "straightforward browsing with the same web access",
            "FOIL_MM": "FOIL evidence routing + counterevidence + exact-answer audit with the same web access",
        },
        "questions": questions,
    }
    (OUT / "browsecomp_questions.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return questions, gold


def score(questions: list[dict], gold: dict[str, str]) -> None:
    predictions_path = OUT / "browsecomp_predictions.json"
    if not predictions_path.exists():
        return

    predictions_data = json.loads(predictions_path.read_text(encoding="utf-8"))
    predictions = {
        row["id"]: row.get("answer") for row in predictions_data.get("predictions", [])
    }
    items: list[dict] = []
    review: list[dict] = []
    summary = {"BASE": [0, 0], "FOIL_MM": [0, 0]}

    for question in questions:
        qid = question["id"]
        prediction = str(predictions.get(qid, "")).strip()
        reference = str(gold[qid]).strip()
        exact = normalize(prediction) == normalize(reference)
        condition = question["condition"]
        summary[condition][1] += 1
        summary[condition][0] += int(exact)
        items.append(
            {
                "id": qid,
                "condition": condition,
                "exact_normalized_match": exact,
            }
        )
        review.append(
            {
                "id": qid,
                "condition": condition,
                "prediction": prediction,
                "reference": reference,
                "exact_normalized_match": exact,
            }
        )

    result = {
        "schema": "foil-browsecomp-results/v1",
        "selection_seed": SEED,
        "summary": [
            {
                "condition": condition,
                "correct_exact": values[0],
                "n": values[1],
                "accuracy_exact": values[0] / values[1],
            }
            for condition, values in summary.items()
        ],
        "items": items,
        "validity_boundary": (
            "Official BrowseComp questions, exploratory disjoint-subset in-session A/B. "
            "Exact-normalized scoring is stricter/different from the official LLM judge; "
            "nonmatches require post-commit semantic adjudication."
        ),
    }
    (OUT / "browsecomp_results.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "browsecomp_review_private.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    print(f"prepared {len(questions)} blinded BrowseComp questions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
