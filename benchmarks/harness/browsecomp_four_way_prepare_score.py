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
INITIAL_TARGET = 20
REPLACEMENT_SEED = 20260827
REPLACEMENT_TARGET = 8
CONTAMINATION_REPLACEMENT_SEED = 20260828
CONTAMINATION_REPLACEMENT_TARGET = 4
SECOND_CONTAMINATION_REPLACEMENT_SEED = 20260829
SECOND_CONTAMINATION_REPLACEMENT_TARGET = 4
EXECUTION_INTEGRITY_REPLACEMENT_SEED = 20260830
EXECUTION_INTEGRITY_REPLACEMENT_TARGET = 4
CONDITIONS = ("BASE", "FOIL", "FOIL_PROFILE", "FOIL_MM")
PROFILE_FREEZE_COMMIT = "013a728bfd6f57a8592fc3fc6e098ea52da357d5"

# Public search results exposed published BrowseComp traces/answers after blinded
# item generation. To preserve equal condition sizes, every contaminated item's
# complete four-condition ordinal block is excluded without consulting hidden gold.
POST_EXPOSURE_EXCLUDED_IDS = {
    "bc4-00-475d4888", "bc4-01-08197e10", "bc4-02-a8ed2df4", "bc4-03-27616be2",
    "bc4-04-852241e2", "bc4-05-0c3aa825", "bc4-06-03619bed", "bc4-07-9f2ba19f",
    "bc4-16-963255ff", "bc4-17-15efdcb3", "bc4-18-5577c78b", "bc4-19-37b46515",
    "bc4-20-3e558e7b", "bc4-21-2381769c", "bc4-22-386231f8", "bc4-23-1aaddc9b",
    "bc4-24-9aa8e190", "bc4-25-8afc7681", "bc4-26-2d5931c0", "bc4-27-64feb6aa",
}

# During pre-commit execution of the two remaining original four-condition
# blocks, the operator exceeded the frozen <=12-search-query ceiling on bc4-09
# and bc4-12. No benchmark gold or published BrowseComp answer/trace was
# consulted. Rather than score unequal-budget executions or delete only the
# affected conditions, retire both complete exposed blocks before gold access.
EXECUTION_BUDGET_EXCLUDED_IDS = {
    "bc4-08-00218e89", "bc4-09-66fe5438", "bc4-10-8de4e78a", "bc4-11-0de64524",
    "bc4-12-1b3f837e", "bc4-13-51ac9523", "bc4-14-f0048c50", "bc4-15-84601b6f",
}

# A pre-commit audit found that research attributed to bc4-34 had been executed
# against the wrong prompt. No prediction was committed and no hidden gold was
# consulted. Treating bc4-34 as fresh would silently grant that condition a new
# search budget, so the complete bc4-32..35 block is retired and replaced.
EXECUTION_INTEGRITY_EXCLUDED_IDS = {
    "bc4-32-7e8964be", "bc4-33-8f29b330", "bc4-34-b73854b0", "bc4-35-87e09fcb",
}


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
    old_rows = random.Random(OLD_SEED).sample(rows, 20)
    old_fingerprints = {row_fingerprint(row) for row in old_rows}
    fresh_pool = [row for row in rows if row_fingerprint(row) not in old_fingerprints]
    needed = (
        INITIAL_TARGET
        + REPLACEMENT_TARGET
        + CONTAMINATION_REPLACEMENT_TARGET
        + SECOND_CONTAMINATION_REPLACEMENT_TARGET
        + EXECUTION_INTEGRITY_REPLACEMENT_TARGET
    )
    if len(fresh_pool) < needed:
        raise RuntimeError(f"need at least {needed} fresh BrowseComp rows, found {len(fresh_pool)}")

    initial_selected = random.Random(SEED).sample(fresh_pool, INITIAL_TARGET)
    initial_fingerprints = {row_fingerprint(row) for row in initial_selected}

    replacement_pool = [row for row in fresh_pool if row_fingerprint(row) not in initial_fingerprints]
    replacement_selected = random.Random(REPLACEMENT_SEED).sample(replacement_pool, REPLACEMENT_TARGET)
    replacement_fingerprints = {row_fingerprint(row) for row in replacement_selected}

    contamination_replacement_pool = [
        row for row in replacement_pool if row_fingerprint(row) not in replacement_fingerprints
    ]
    contamination_replacement_selected = random.Random(CONTAMINATION_REPLACEMENT_SEED).sample(
        contamination_replacement_pool, CONTAMINATION_REPLACEMENT_TARGET
    )
    contamination_replacement_fingerprints = {
        row_fingerprint(row) for row in contamination_replacement_selected
    }

    second_contamination_replacement_pool = [
        row
        for row in contamination_replacement_pool
        if row_fingerprint(row) not in contamination_replacement_fingerprints
    ]
    second_contamination_replacement_selected = random.Random(
        SECOND_CONTAMINATION_REPLACEMENT_SEED
    ).sample(second_contamination_replacement_pool, SECOND_CONTAMINATION_REPLACEMENT_TARGET)
    second_contamination_replacement_fingerprints = {
        row_fingerprint(row) for row in second_contamination_replacement_selected
    }

    execution_integrity_replacement_pool = [
        row
        for row in second_contamination_replacement_pool
        if row_fingerprint(row) not in second_contamination_replacement_fingerprints
    ]
    execution_integrity_replacement_selected = random.Random(
        EXECUTION_INTEGRITY_REPLACEMENT_SEED
    ).sample(execution_integrity_replacement_pool, EXECUTION_INTEGRITY_REPLACEMENT_TARGET)

    indexed_rows = list(enumerate(initial_selected))
    indexed_rows += [(INITIAL_TARGET + offset, row) for offset, row in enumerate(replacement_selected)]
    indexed_rows += [
        (INITIAL_TARGET + REPLACEMENT_TARGET + offset, row)
        for offset, row in enumerate(contamination_replacement_selected)
    ]
    indexed_rows += [
        (
            INITIAL_TARGET + REPLACEMENT_TARGET + CONTAMINATION_REPLACEMENT_TARGET + offset,
            row,
        )
        for offset, row in enumerate(second_contamination_replacement_selected)
    ]
    indexed_rows += [
        (
            INITIAL_TARGET
            + REPLACEMENT_TARGET
            + CONTAMINATION_REPLACEMENT_TARGET
            + SECOND_CONTAMINATION_REPLACEMENT_TARGET
            + offset,
            row,
        )
        for offset, row in enumerate(execution_integrity_replacement_selected)
    ]

    questions: list[dict] = []
    gold: dict[str, str] = {}
    all_excluded_ids = (
        POST_EXPOSURE_EXCLUDED_IDS
        | EXECUTION_BUDGET_EXCLUDED_IDS
        | EXECUTION_INTEGRITY_EXCLUDED_IDS
    )
    for index, row in indexed_rows:
        fingerprint = row_fingerprint(row)
        qid = f"bc4-{index:02d}-{fingerprint[:8]}"
        condition = CONDITIONS[index % len(CONDITIONS)]
        problem = decrypt(row["problem"], row["canary"])
        answer = decrypt(row["answer"], row["canary"])
        if qid in all_excluded_ids:
            continue
        questions.append({
            "id": qid,
            "benchmark": "BrowseComp-official-test-four-way",
            "condition": condition,
            "question": problem,
            "instruction": "Use web browsing. Return one succinct exact answer.",
            "budget": {"max_search_queries": 12, "max_source_followups": 12},
        })
        gold[qid] = answer

    counts = defaultdict(int)
    for question in questions:
        counts[question["condition"]] += 1
    if len(questions) != 8 or any(counts[c] != 2 for c in CONDITIONS):
        raise RuntimeError(f"replacement balance failure: n={len(questions)}, counts={dict(counts)}")

    payload = {
        "schema": "foil-browsecomp-four-way-questions/v8",
        "selection_seed": SEED,
        "replacement_seed": REPLACEMENT_SEED,
        "contamination_replacement_seed": CONTAMINATION_REPLACEMENT_SEED,
        "second_contamination_replacement_seed": SECOND_CONTAMINATION_REPLACEMENT_SEED,
        "execution_integrity_replacement_seed": EXECUTION_INTEGRITY_REPLACEMENT_SEED,
        "source": URL,
        "initial_sample_n": INITIAL_TARGET,
        "replacement_sample_n": REPLACEMENT_TARGET,
        "contamination_replacement_sample_n": CONTAMINATION_REPLACEMENT_TARGET,
        "second_contamination_replacement_sample_n": SECOND_CONTAMINATION_REPLACEMENT_TARGET,
        "execution_integrity_replacement_sample_n": EXECUTION_INTEGRITY_REPLACEMENT_TARGET,
        "final_sample_n": len(questions),
        "prior_sample_excluded_n": 20,
        "post_exposure_excluded_ids": sorted(POST_EXPOSURE_EXCLUDED_IDS),
        "post_exposure_exclusion_reason": (
            "Published BrowseComp traces/answers were exposed for bc4-01, bc4-04, bc4-16, bc4-21, and later bc4-25 during blinded research. "
            "Each contaminated item's complete four-condition ordinal block was retired without consulting hidden gold."
        ),
        "execution_budget_excluded_ids": sorted(EXECUTION_BUDGET_EXCLUDED_IDS),
        "execution_budget_exclusion_reason": (
            "The frozen <=12-search-query ceiling was exceeded on bc4-09 and bc4-12 during pre-commit research. "
            "No benchmark gold or published BrowseComp answer/trace was consulted. Both complete four-condition ordinal blocks "
            "bc4-08..11 and bc4-12..15 were retired before scoring."
        ),
        "execution_integrity_excluded_ids": sorted(EXECUTION_INTEGRITY_EXCLUDED_IDS),
        "execution_integrity_exclusion_reason": (
            "A pre-commit audit found that research attributed to bc4-34 had been executed against the wrong prompt. "
            "No prediction or hidden benchmark gold was consulted. To avoid silently granting a new search budget to one condition, "
            "the complete four-condition block bc4-32..35 was retired before scoring and replaced with a fresh balanced block."
        ),
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
        items.append({"id": qid, "condition": condition, "exact_normalized_match": bool(exact)})

    result = {
        "schema": "foil-browsecomp-four-way-results/v5",
        "selection_seed": SEED,
        "replacement_seed": REPLACEMENT_SEED,
        "contamination_replacement_seed": CONTAMINATION_REPLACEMENT_SEED,
        "second_contamination_replacement_seed": SECOND_CONTAMINATION_REPLACEMENT_SEED,
        "execution_integrity_replacement_seed": EXECUTION_INTEGRITY_REPLACEMENT_SEED,
        "profile_freeze_commit": PROFILE_FREEZE_COMMIT,
        "post_exposure_excluded_ids": sorted(POST_EXPOSURE_EXCLUDED_IDS),
        "execution_budget_excluded_ids": sorted(EXECUTION_BUDGET_EXCLUDED_IDS),
        "execution_integrity_excluded_ids": sorted(EXECUTION_INTEGRITY_EXCLUDED_IDS),
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
            "Scored replacement items were run under the same frozen web-search ceiling. Exact-normalized scoring is not the official "
            "BrowseComp LLM judge. Original balanced blocks were retired pre-gold after an operator search-budget overrun, any block "
            "whose item exposed a published BrowseComp trace/answer was retired in full, and one block was retired after a pre-commit "
            "wrong-prompt execution was discovered. A stronger causal test requires isolated same-item randomized executions."
        ),
    }
    (OUT / "browsecomp_four_way_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> int:
    questions, gold = prepare()
    score(questions, gold)
    counts = defaultdict(int)
    for question in questions:
        counts[question["condition"]] += 1
    print(f"prepared {len(questions)} final BrowseComp questions: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
