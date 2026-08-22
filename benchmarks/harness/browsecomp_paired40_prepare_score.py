from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import random
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-22"
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
SELECTION_SEED = 20260831
REPLACEMENT_SEED = 20260901
TARGET = 40
SEARCH_CEILING = 12
FOLLOWUP_CEILING = 12

BROWSECOMP_PROFILE_FREEZE_COMMIT = "013a728bfd6f57a8592fc3fc6e098ea52da357d5"
GENERAL_PROFILE_FREEZE_COMMIT = "124c06b173ba6eff2fe0d23660a1ced8b7b975c2"

CONDITIONS = (
    "BASE",
    "FOIL",
    "FOIL_BROWSECOMP_PROFILE",
    "FOIL_GENERAL_PROFILE",
    "FOIL_MM",
)

# All BrowseComp rows previously sampled by the repository are excluded from
# this prospective sample, not only rows that were ultimately scored. The
# reconstruction below mirrors the exact historical selectors and therefore
# excludes 20 legacy rows plus 40 rows generated during the four-way pilot.
LEGACY_SEED = 20260824
FOUR_WAY_INITIAL_SEED = 20260826
FOUR_WAY_REPLACEMENT_SEED = 20260827
FOUR_WAY_CONTAMINATION_SEED = 20260828
FOUR_WAY_SECOND_CONTAMINATION_SEED = 20260829
FOUR_WAY_INTEGRITY_SEED = 20260830

FAILURE_CODES = {
    "DISCOVERY_FAILURE",
    "WRONG_CANDIDATE",
    "REASONING_ERROR",
    "STATE_TRACKING_ERROR",
    "VERIFICATION_FAILURE",
    "BUDGET_EXHAUSTED",
    "OVERCAUTIOUS_ABSTENTION",
    "EXACT_OUTPUT_ERROR",
    "TOOL_EXECUTION_ERROR",
    "CONTAMINATED",
    "OTHER",
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "The-Gauntlet-benchmark/2.0"},
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


def row_fingerprint(row: dict[str, str]) -> str:
    return hashlib.sha256(row["problem"].encode()).hexdigest()


def previous_exposed_fingerprints(rows: list[dict[str, str]]) -> set[str]:
    legacy = random.Random(LEGACY_SEED).sample(rows, 20)
    seen = {row_fingerprint(row) for row in legacy}

    fresh_pool = [row for row in rows if row_fingerprint(row) not in seen]
    initial = random.Random(FOUR_WAY_INITIAL_SEED).sample(fresh_pool, 20)
    initial_fp = {row_fingerprint(row) for row in initial}
    seen |= initial_fp

    replacement_pool = [row for row in fresh_pool if row_fingerprint(row) not in initial_fp]
    replacement = random.Random(FOUR_WAY_REPLACEMENT_SEED).sample(replacement_pool, 8)
    replacement_fp = {row_fingerprint(row) for row in replacement}
    seen |= replacement_fp

    contamination_pool = [
        row for row in replacement_pool if row_fingerprint(row) not in replacement_fp
    ]
    contamination = random.Random(FOUR_WAY_CONTAMINATION_SEED).sample(contamination_pool, 4)
    contamination_fp = {row_fingerprint(row) for row in contamination}
    seen |= contamination_fp

    second_pool = [
        row for row in contamination_pool if row_fingerprint(row) not in contamination_fp
    ]
    second = random.Random(FOUR_WAY_SECOND_CONTAMINATION_SEED).sample(second_pool, 4)
    second_fp = {row_fingerprint(row) for row in second}
    seen |= second_fp

    integrity_pool = [row for row in second_pool if row_fingerprint(row) not in second_fp]
    integrity = random.Random(FOUR_WAY_INTEGRITY_SEED).sample(integrity_pool, 4)
    seen |= {row_fingerprint(row) for row in integrity}

    if len(seen) != 60:
        raise RuntimeError(f"historical BrowseComp exclusion reconstruction expected 60 rows, got {len(seen)}")
    return seen


def prepare() -> tuple[list[dict], dict[str, str], list[dict]]:
    source_bytes = fetch(URL)
    rows = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8-sig"))))
    excluded_fingerprints = previous_exposed_fingerprints(rows)
    fresh = [row for row in rows if row_fingerprint(row) not in excluded_fingerprints]
    if len(fresh) < TARGET:
        raise RuntimeError(f"need at least {TARGET} fresh BrowseComp rows, found {len(fresh)}")

    selected = random.Random(SELECTION_SEED).sample(fresh, TARGET)
    questions: list[dict] = []
    gold: dict[str, str] = {}
    units: list[dict] = []

    for index, row in enumerate(selected):
        fingerprint = row_fingerprint(row)
        qid = f"bcp40-{index:02d}-{fingerprint[:8]}"
        questions.append(
            {
                "id": qid,
                "benchmark": "BrowseComp-official-test-paired40",
                "question": decrypt(row["problem"], row["canary"]),
                "instruction": "Use web browsing. Return one succinct exact answer.",
                "budget": {
                    "max_search_queries": SEARCH_CEILING,
                    "max_source_followups": FOLLOWUP_CEILING,
                },
            }
        )
        gold[qid] = decrypt(row["answer"], row["canary"])
        for condition in CONDITIONS:
            units.append(
                {
                    "unit_id": f"{qid}::{condition}",
                    "item_id": qid,
                    "condition": condition,
                    "requires_fresh_isolated_context": True,
                    "sibling_condition_outputs_must_be_hidden": True,
                }
            )

    payload = {
        "schema": "foil-browsecomp-paired40-questions/v1",
        "selection_seed": SELECTION_SEED,
        "replacement_seed": REPLACEMENT_SEED,
        "source": URL,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "prior_exposed_rows_excluded": len(excluded_fingerprints),
        "sample_n": len(questions),
        "execution_units_n": len(units),
        "conditions": {
            "BASE": "same model and web tools; direct browsing without FOIL/profile/Mastermind protocol",
            "FOIL": "generic FOIL evidence-routing protocol",
            "FOIL_BROWSECOMP_PROFILE": "FOIL plus the historical frozen BrowseComp-specific profile",
            "FOIL_GENERAL_PROFILE": "FOIL plus the prospectively frozen general routing profile",
            "FOIL_MM": "FOIL plus Mastermind final audit; no profile",
        },
        "profile_freezes": {
            "BROWSECOMP": BROWSECOMP_PROFILE_FREEZE_COMMIT,
            "GENERAL": GENERAL_PROFILE_FREEZE_COMMIT,
        },
        "isolation_rule": (
            "Every unit must execute in a fresh context with no sibling-condition output or prior prospective-suite output visible."
        ),
        "questions": questions,
        "execution_units": units,
    }
    (OUT / "browsecomp_paired40_questions.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return questions, gold, units


def expected_unit_keys(units: list[dict]) -> set[tuple[str, str]]:
    return {(str(unit["item_id"]), str(unit["condition"])) for unit in units}


def validate_predictions(units: list[dict], predictions_path: Path) -> list[dict]:
    raw = json.loads(predictions_path.read_text(encoding="utf-8"))
    rows = list(raw.get("predictions", []))
    expected = expected_unit_keys(units)
    seen: dict[tuple[str, str], dict] = {}
    session_ids: set[str] = set()

    for row in rows:
        item_id = str(row.get("id", ""))
        condition = str(row.get("condition", ""))
        key = (item_id, condition)
        if key not in expected:
            raise RuntimeError(f"unexpected prediction unit: {key}")
        if key in seen:
            raise RuntimeError(f"duplicate prediction unit: {key}")

        trace = row.get("trace")
        if not isinstance(trace, dict):
            raise RuntimeError(f"missing trace object for {key}")
        session_id = str(trace.get("isolation_session_id", "")).strip()
        if not session_id:
            raise RuntimeError(f"missing isolation_session_id for {key}")
        if session_id in session_ids:
            raise RuntimeError(f"reused isolation_session_id {session_id!r}; paired isolation violated")
        session_ids.add(session_id)
        if trace.get("sibling_outputs_visible") is not False:
            raise RuntimeError(f"sibling_outputs_visible must be false for {key}")

        search_queries = int(trace.get("search_queries", -1))
        source_followups = int(trace.get("source_followups", -1))
        if not 0 <= search_queries <= SEARCH_CEILING:
            raise RuntimeError(f"search-query budget invalid for {key}: {search_queries}")
        if not 0 <= source_followups <= FOLLOWUP_CEILING:
            raise RuntimeError(f"source-followup budget invalid for {key}: {source_followups}")

        phases = trace.get("phase_allocation")
        if not isinstance(phases, dict):
            raise RuntimeError(f"missing phase_allocation for {key}")
        for phase in ("discovery", "candidate_testing", "verification", "disconfirmation", "final_audit"):
            if phase not in phases:
                raise RuntimeError(f"phase_allocation missing {phase!r} for {key}")

        if "viable_candidate_before_verification" not in trace:
            raise RuntimeError(f"missing viable_candidate_before_verification for {key}")
        confidence = trace.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise RuntimeError(f"confidence must be in [0,1] for {key}")

        failure_code = trace.get("failure_code")
        if failure_code is not None and str(failure_code) not in FAILURE_CODES:
            raise RuntimeError(f"unknown failure_code {failure_code!r} for {key}")

        seen[key] = row

    missing = expected - set(seen)
    if missing:
        raise RuntimeError(
            f"refusing partial score: expected {len(expected)} isolated predictions, got {len(seen)}; "
            f"missing {len(missing)} units"
        )
    if len(rows) != len(expected):
        raise RuntimeError(f"prediction matrix must contain exactly {len(expected)} rows")
    return rows


def wilson_interval(correct: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (math.nan, math.nan)
    p = correct / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    lower = sum(math.comb(n, i) for i in range(0, k + 1)) / (2**n)
    return min(1.0, 2 * lower)


def score(questions: list[dict], gold: dict[str, str], units: list[dict]) -> None:
    predictions_path = OUT / "browsecomp_paired40_predictions.json"
    if not predictions_path.exists():
        return
    prediction_rows = validate_predictions(units, predictions_path)

    question_ids = {str(question["id"]) for question in questions}
    correctness: dict[tuple[str, str], bool] = {}
    trace_by_key: dict[tuple[str, str], dict] = {}
    items: list[dict] = []
    aggregate: dict[str, list[int]] = defaultdict(list)

    for row in prediction_rows:
        qid = str(row["id"])
        condition = str(row["condition"])
        if qid not in question_ids:
            raise RuntimeError(f"unknown item id in predictions: {qid}")
        prediction = str(row.get("answer", "")).strip()
        exact = normalize(prediction) == normalize(gold[qid])
        key = (qid, condition)
        correctness[key] = exact
        trace_by_key[key] = dict(row["trace"])
        aggregate[condition].append(int(exact))
        items.append(
            {
                "id": qid,
                "condition": condition,
                "exact_normalized_match": bool(exact),
                "search_queries": int(row["trace"]["search_queries"]),
                "source_followups": int(row["trace"]["source_followups"]),
                "failure_code": row["trace"].get("failure_code"),
            }
        )

    summary: list[dict] = []
    for condition in CONDITIONS:
        values = aggregate[condition]
        correct = sum(values)
        low, high = wilson_interval(correct, len(values))
        summary.append(
            {
                "condition": condition,
                "correct_exact": correct,
                "n": len(values),
                "accuracy_exact": correct / len(values),
                "wilson95": [low, high],
                "mean_search_queries": sum(
                    int(trace_by_key[(qid, condition)]["search_queries"]) for qid in question_ids
                ) / len(question_ids),
                "mean_source_followups": sum(
                    int(trace_by_key[(qid, condition)]["source_followups"]) for qid in question_ids
                ) / len(question_ids),
            }
        )

    pairwise: list[dict] = []
    for reference in ("BASE", "FOIL"):
        for condition in CONDITIONS:
            if condition == reference:
                continue
            ref_wins = 0
            cond_wins = 0
            both_correct = 0
            both_wrong = 0
            for qid in question_ids:
                ref_ok = correctness[(qid, reference)]
                cond_ok = correctness[(qid, condition)]
                if ref_ok and cond_ok:
                    both_correct += 1
                elif ref_ok and not cond_ok:
                    ref_wins += 1
                elif cond_ok and not ref_ok:
                    cond_wins += 1
                else:
                    both_wrong += 1
            pairwise.append(
                {
                    "reference": reference,
                    "condition": condition,
                    "condition_only_correct": cond_wins,
                    "reference_only_correct": ref_wins,
                    "both_correct": both_correct,
                    "both_wrong": both_wrong,
                    "paired_accuracy_delta": (cond_wins - ref_wins) / len(question_ids),
                    "exact_mcnemar_p_two_sided": exact_mcnemar_p(ref_wins, cond_wins),
                }
            )

    result = {
        "schema": "foil-browsecomp-paired40-results/v1",
        "selection_seed": SELECTION_SEED,
        "replacement_seed": REPLACEMENT_SEED,
        "sample_n": len(questions),
        "execution_units_n": len(units),
        "profile_freezes": {
            "BROWSECOMP": BROWSECOMP_PROFILE_FREEZE_COMMIT,
            "GENERAL": GENERAL_PROFILE_FREEZE_COMMIT,
        },
        "summary": summary,
        "pairwise": pairwise,
        "items": sorted(items, key=lambda item: (item["id"], CONDITIONS.index(item["condition"]))),
        "validity_boundary": (
            "Prospective same-item paired BrowseComp-40 ablation requiring unique isolated execution contexts and identical 12/12 web ceilings. "
            "Normalized exact match is a deterministic audit metric and is not the official BrowseComp LLM judge. No general-efficacy claim follows from this sample alone."
        ),
    }
    (OUT / "browsecomp_paired40_results.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


def main() -> int:
    questions, gold, units = prepare()
    score(questions, gold, units)
    print(
        f"prepared {len(questions)} fresh paired BrowseComp items and {len(units)} isolated execution units; "
        f"excluded 60 historically sampled rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
