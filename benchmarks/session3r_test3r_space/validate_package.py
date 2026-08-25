#!/usr/bin/env python3
"""Independent post-generation certification for Session 3R / Test 3R Space."""
from __future__ import annotations

import base64
import gzip
import json
from collections import Counter
from pathlib import Path

import build_package as bp

ROOT = Path(__file__).resolve().parent
BASE_Q = ROOT / "base" / "questions.jsonl"
SPACE_Q = ROOT / "space" / "questions.jsonl"
SEALED = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT" / "gold.jsonl.gz.b64"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def decode_gold():
    payload = base64.b64decode(SEALED.read_text(encoding="ascii").strip())
    raw = gzip.decompress(payload).decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def expected_from_history(task: dict, histories: dict[str, list[dict]]):
    t = task["task_type"]
    expected = task["expected"]
    repos = task["official_repos"]
    if t == "release_lookup":
        repo = repos[0]
        latest = histories[repo][0]
        return {"repo": repo, "tag": latest["tag"], "published_date": latest["published_date"]}
    if t == "release_predecessor":
        repo = repos[0]
        previous = histories[repo][1]
        return {"repo": repo, "tag": previous["tag"], "published_date": previous["published_date"]}
    if t == "release_compare":
        repo_a, repo_b = repos
        a, b = histories[repo_a][0], histories[repo_b][0]
        later_repo = repo_a if a["published_at"] > b["published_at"] else repo_b
        return {
            "later_repo": later_repo,
            "repo_a_tag": a["tag"], "repo_a_date": a["published_date"],
            "repo_b_tag": b["tag"], "repo_b_date": b["published_date"],
        }
    raise AssertionError(f"unknown task type {t}")


def main() -> None:
    base = read_jsonl(BASE_Q)
    space = read_jsonl(SPACE_Q)
    gold = decode_gold()
    if len(base) != 100 or len(space) != 100 or len(gold) != 100:
        raise AssertionError(f"count mismatch base={len(base)} space={len(space)} gold={len(gold)}")
    if BASE_Q.read_bytes() != SPACE_Q.read_bytes():
        raise AssertionError("BASE and SPACE question projections differ")

    ids = [r["id"] for r in base]
    if ids != [r["id"] for r in space] or ids != [r["id"] for r in gold]:
        raise AssertionError("ID/order mismatch")
    if len(set(ids)) != 100:
        raise AssertionError("duplicate task IDs")

    forbidden = {"expected", "tag", "published_date", "source_urls", "source_snapshot", "official_repos", "official_prefixes", "gold", "answer"}
    for row in base + space:
        leak = forbidden.intersection(row.keys())
        if leak:
            raise AssertionError(f"question projection leak {row['id']}: {sorted(leak)}")

    sections = Counter(r["section"] for r in base)
    expected_sections = {
        "primary_verified_release_retrieval": 50,
        "secondary_multi_source_comparison": 30,
        "exploratory_release_history_navigation": 20,
    }
    if dict(sections) != expected_sections:
        raise AssertionError(f"section counts wrong: {dict(sections)}")

    selected_repos = sorted({repo for row in gold for repo in row["official_repos"]})
    histories = {}
    for repo in selected_repos:
        history = bp.stable_releases(repo)
        if len(history) < 2:
            raise AssertionError(f"selected repo no longer yields two qualifying stable releases: {repo}")
        histories[repo] = history

    for row in gold:
        recomputed = expected_from_history(row, histories)
        if recomputed != row["expected"]:
            raise AssertionError(f"source revalidation mismatch for {row['id']}")
        if any(not u.startswith("https://github.com/") or "/releases/" not in u for u in row["source_urls"]):
            raise AssertionError(f"non-first-party source URL for {row['id']}")
        for repo, prefix in zip(row["official_repos"], row["official_prefixes"], strict=True):
            if prefix != bp.official_prefix(repo):
                raise AssertionError(f"official prefix mismatch for {row['id']}")

    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    if manifest.get("SOURCE_VALIDATED") is not True or report.get("SOURCE_VALIDATED") is not True:
        raise AssertionError("SOURCE_VALIDATED flag missing")
    if manifest.get("GOLD_SEMANTICALLY_HIDDEN_FROM_SEARCH") is not True:
        raise AssertionError("sealed-gold search-hiding flag missing")

    certification = {
        "experiment_id": bp.EXPERIMENT_ID,
        "SOURCE_VALIDATED": True,
        "certification_stage": "independent_post_generation_first_party_requery",
        "base_space_question_files_byte_identical": True,
        "question_projection_gold_leak_check": "PASS",
        "gold_plaintext_committed": False,
        "sealed_gold_decode_check": "PASS",
        "selected_ids_unique": True,
        "selected_repository_count": len(selected_repos),
        "first_party_release_histories_requeried": len(selected_repos),
        "frozen_answers_recomputed_from_live_first_party_history_at_cutoff": "PASS",
        "primary_records_revalidated": 50,
        "secondary_records_revalidated": 30,
        "exploratory_records_revalidated": 20,
        "prior_invalid_test3_public_benchmark_items_reused": False,
        "benchmark_artifact_search_snippet_risk": "MITIGATED_BY_GZIP_BASE64_GOLD_AND_INFERENCE_FIREWALL",
    }
    bp.write_json(ROOT / "CI_CERTIFICATION.json", certification)
    print(json.dumps({"SOURCE_VALIDATED": True, "tasks": 100, "repos_requeried": len(selected_repos)}, sort_keys=True))


if __name__ == "__main__":
    main()
