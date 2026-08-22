from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import random
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-22"
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
OLD_SEED = 20260824
SEED = 20260826
TARGET = 20
CONDITIONS = ("BASE", "FOIL", "FOIL_PROFILE", "FOIL_MM")
PROFILE_FREEZE_COMMIT = "013a728bfd6f57a8592fc3fc6e098ea52da357d5"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "The-Gauntlet-benchmark/1.1"})
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


def row_fingerprint(row: dict[str, str]) -> str:
    return hashlib.sha256(row["problem"].encode()).hexdigest()


def prepare() -> tuple[list[dict], dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(fetch(URL).decode("utf-8-sig"))))

    # Exclude all 20 rows used by the earlier BrowseComp sampling frame, not only
    # the rows that survived its later contamination exclusions.
    old_rows = random.Random(OLD_SEED).sample(rows, 20)
    old_fingerprints = {row_fingerprint(row) for row in old_rows}
    fresh_pool = [row for row in rows if row_fingerprint(row) not in old_fingerprints]
    if len(fresh_pool) < TARGET:
        raise RuntimeError(f"need {TARGET} fresh BrowseComp rows, found {len(fresh_pool)}")

    selected = random.Random(SEED).sample(fresh_pool, TARGET)
    questions: list[dict] = []
    gold: dict[str, str] = {}

    for index, row in enumerate(selected):
        fingerprint = row_fingerprint(row)
        qid = f"bc4-{index:02d}-{fingerprint[:8]}"
        condition = CONDITIONS[index % len(CONDITIONS)]
        problem = decrypt(row["problem"], row["canary"])
        answer = decrypt(row["answer"], row["canary"])
        questions.append(
            {
                "id": qid,
                "benchmark": "BrowseComp-official-test-four-way",
                "condition": condition,
                "question": problem,
                "instruction": "Use web browsing. Return one succinct exact answer.",
                "budget": {
                    "max_search_queries": 12,
                    "max_source_followups": 12,
                },
            }
        )
        gold[qid] = answer

    payload = {
        "schema": "foil-browsecomp-four-way-questions/v1",
        "selection_seed": SEED,
        "source": URL,
        "sample_n": TARGET,
        "prior_sample_excluded_n": 20,
        "profile_freeze_commit": PROFILE_FREEZE_COMMIT,
        "profile_path": "benchmarks/profiles/BROWSECOMP_BENCHMARK_PROFILE.json",
        "protocol_path": "benchmarks/BROWSECOMP_FOUR_WAY_PROTOCOL.md",
        "conditions": {
            "BASE": "same model/web capability; no FOIL protocol",
            "FOIL": "generic FOIL evidence-routing protocol",
            "FOIL_PROFILE": "FOIL plus frozen benchmark-blind profile",
            "FOIL_MM": "FOIL plus Mastermind final audit; no profile",
        },
        "questions": questions,
    }
    (OUT / "browsecomp_four_way_questions.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return questions, gold


def score(questions: list[dict], gold: dict[str, str]) -> None:
    predictions_path = OUT / "browsecomp_four_way_predictions.json"
    if not predictions_path.exists():
        return

    raw = json.loads(predictions_path.read_text(encoding="utf-8"))
    predictions = {str(row["id"]): row.get("answer") for row in raw.get("predictions", [])}

    summary: dict[str, list[int]] = {condition: [0, 0] for condition in CONDITIONS}
    items: list[dict] = []
    for question in questions:
        qid = question["id"]
        condition = question["condition"]
        prediction = str(predictions.get(qid, "")).strip()
        reference = str(gold[qid]).strip()
        exact = normalize(prediction) == normalize(reference)
        summary[condition][0] += int(exact)
        summary[condition][1] += 1
        items.append(
            {
                "id": qid,
                "condition": condition,
                "exact_normalized_match": bool(exact),
            }
        )

    result = {
        "schema": "foil-browsecomp-four-way-results/v1",
        "selection_seed": SEED,
        "profile_freeze_commit": PROFILE_FREEZE_COMMIT,
        "summary": [
            {
                "condition": condition,
                "correct_exact": summary[condition][0],
                "n": summary[condition][1],
                "accuracy_exact": summary[condition][0] / summary[condition][1],
            }
            for condition in CONDITIONS
        ],
        "items": items,
        "validity_boundary": (
            "Official BrowseComp questions; exploratory four-condition disjoint-subset in-session ablation. "
            "All conditions have the same web-search budget. Exact-normalized scoring is not the official BrowseComp LLM judge. "
            "A stronger causal test requires isolated same-item randomized executions."
        ),
    }
    (OUT / "browsecomp_four_way_results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    counts = defaultdict(int)
    for question in questions:
        counts[question["condition"]] += 1
    print(f"prepared {len(questions)} fresh BrowseComp questions: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
