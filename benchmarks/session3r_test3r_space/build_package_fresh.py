#!/usr/bin/env python3
"""Fresh rebuild adapter: exclude every exact task signature from the discarded first sample."""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

import build_package_ci as bci

bp = bci.bp
bp.SEED = 2026082504
OLD_QUESTIONS = bp.ROOT / "base" / "questions.jsonl"


def old_signatures():
    lookup, predecessor, comparisons = set(), set(), set()
    if not OLD_QUESTIONS.exists():
        raise RuntimeError("discarded sample question projection is required to exclude its exact task signatures")
    for line in OLD_QUESTIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        repos = re.findall(r"`([^`]+/[^`]+)`", row.get("prompt", ""))
        task_type = row.get("task_type")
        if task_type == "release_lookup" and repos:
            lookup.add(repos[0])
        elif task_type == "release_predecessor" and repos:
            predecessor.add(repos[0])
        elif task_type == "release_compare" and len(repos) >= 2:
            comparisons.add(tuple(sorted((repos[0], repos[1]))))
    if len(lookup) != 50 or len(predecessor) != 20 or len(comparisons) != 30:
        raise RuntimeError(f"discarded signature parse mismatch lookup={len(lookup)} predecessor={len(predecessor)} compare={len(comparisons)}")
    return lookup, predecessor, comparisons


OLD_LOOKUP, OLD_PREDECESSOR, OLD_COMPARISONS = old_signatures()


def fresh_pairs(repos, rng, n):
    pairs = []
    seen = set(OLD_COMPARISONS)
    usage = Counter()
    attempts = 0
    while len(pairs) < n and attempts < 20000:
        attempts += 1
        a, b = rng.sample(repos, 2)
        key = tuple(sorted((a, b)))
        if key in seen or usage[a] >= 3 or usage[b] >= 3:
            continue
        seen.add(key)
        usage[a] += 1
        usage[b] += 1
        pairs.append((a, b))
    if len(pairs) != n:
        raise RuntimeError(f"could only construct {len(pairs)} fresh comparison pairs")
    return pairs


def fresh_build_tasks(histories, rng):
    repos = sorted(histories)
    lookup_pool = [r for r in repos if r not in OLD_LOOKUP]
    predecessor_pool = [r for r in repos if r not in OLD_PREDECESSOR]
    if len(lookup_pool) < 50:
        raise RuntimeError(f"fresh lookup pool too small: {len(lookup_pool)}")
    if len(predecessor_pool) < 20:
        raise RuntimeError(f"fresh predecessor pool too small: {len(predecessor_pool)}")

    primary_repos = rng.sample(lookup_pool, 50)
    comparison_pairs = fresh_pairs(repos, rng, 30)
    predecessor_repos = rng.sample(predecessor_pool, 20)
    questions, gold = [], []

    for i, repo in enumerate(primary_repos, 1):
        latest = histories[repo][0]
        item_id = f"space_release_lookup_{i:03d}"
        prompt = (
            f"Find and verify the most recent stable GitHub Release for `{repo}` that was neither a draft nor a prerelease "
            f"and was published on or before {bp.CUTOFF}. Return exactly one JSON object with keys `repo`, `tag`, and "
            "`published_date` (YYYY-MM-DD). Also retain the first-party evidence URL you used in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "primary_verified_release_retrieval", "task_type": "release_lookup", "prompt": prompt})
        gold.append({"id": item_id, "section": "primary_verified_release_retrieval", "task_type": "release_lookup", "expected": {"repo": repo, "tag": latest["tag"], "published_date": latest["published_date"]}, "official_repos": [repo], "official_prefixes": [bp.official_prefix(repo)], "source_urls": [latest["html_url"]], "source_snapshot": {"latest": latest, "previous": histories[repo][1]}})

    for i, (repo_a, repo_b) in enumerate(comparison_pairs, 1):
        a, b = histories[repo_a][0], histories[repo_b][0]
        later_repo = repo_a if a["published_at"] > b["published_at"] else repo_b
        item_id = f"space_release_compare_{i:03d}"
        prompt = (
            f"For `{repo_a}` and `{repo_b}`, find and verify each repository's most recent stable GitHub Release "
            f"published on or before {bp.CUTOFF}. Return exactly one JSON object with keys `later_repo`, `repo_a_tag`, "
            "`repo_a_date`, `repo_b_tag`, and `repo_b_date`. `later_repo` must be the repository whose qualifying release "
            "was published later. Retain first-party evidence URLs for both repositories in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "secondary_multi_source_comparison", "task_type": "release_compare", "prompt": prompt})
        gold.append({"id": item_id, "section": "secondary_multi_source_comparison", "task_type": "release_compare", "expected": {"later_repo": later_repo, "repo_a_tag": a["tag"], "repo_a_date": a["published_date"], "repo_b_tag": b["tag"], "repo_b_date": b["published_date"]}, "official_repos": [repo_a, repo_b], "official_prefixes": [bp.official_prefix(repo_a), bp.official_prefix(repo_b)], "source_urls": [a["html_url"], b["html_url"]], "source_snapshot": {"repo_a": repo_a, "repo_a_latest": a, "repo_b": repo_b, "repo_b_latest": b}})

    for i, repo in enumerate(predecessor_repos, 1):
        latest, previous = histories[repo][0], histories[repo][1]
        item_id = f"space_release_predecessor_{i:03d}"
        prompt = (
            f"For `{repo}`, identify and verify the stable GitHub Release immediately preceding its most recent stable "
            f"release published on or before {bp.CUTOFF}. Ignore drafts and prereleases. Return exactly one JSON object with "
            "keys `repo`, `tag`, and `published_date` (YYYY-MM-DD). Retain a first-party evidence URL in your prediction receipt."
        )
        questions.append({"id": item_id, "section": "exploratory_release_history_navigation", "task_type": "release_predecessor", "prompt": prompt})
        gold.append({"id": item_id, "section": "exploratory_release_history_navigation", "task_type": "release_predecessor", "expected": {"repo": repo, "tag": previous["tag"], "published_date": previous["published_date"]}, "official_repos": [repo], "official_prefixes": [bp.official_prefix(repo)], "source_urls": [previous["html_url"]], "source_snapshot": {"latest": latest, "previous": previous}})

    if len(questions) != 100:
        raise RuntimeError("fresh build did not produce 100 tasks")
    return questions, gold


bp.build_tasks = fresh_build_tasks


def main():
    bp.main()
    report_path = bp.ROOT / "VALIDATION_REPORT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["discarded_first_sample_exact_lookup_signatures_excluded"] = True
    report["discarded_first_sample_exact_predecessor_signatures_excluded"] = True
    report["discarded_first_sample_exact_comparison_pairs_excluded"] = True
    report["fresh_rebuild_seed"] = bp.SEED
    bp.write_json(report_path, report)

    manifest_path = bp.ROOT / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed"] = bp.SEED
    manifest["discarded_first_sample_exact_task_signatures_excluded"] = True
    manifest["files"]["VALIDATION_REPORT.json"] = {"sha256": bp.sha256_file(report_path), "bytes": report_path.stat().st_size}
    bp.write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
