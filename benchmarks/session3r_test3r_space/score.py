#!/usr/bin/env python3
"""Paired scorer for Session 3R / Test 3R Space."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SEALED = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT" / "gold.jsonl.gz.b64"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def decode_gold():
    payload = base64.b64decode(SEALED.read_text(encoding="ascii").strip())
    raw = gzip.decompress(payload).decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hash(path: Path, hashfile: Path) -> None:
    expected = hashfile.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"receipt hash mismatch for {path.name}: expected {expected}, got {actual}")


def parse_answer(value):
    if isinstance(value, dict):
        return {str(k): str(v).strip() for k, v in value.items()}
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            if isinstance(obj, dict):
                return {str(k): str(v).strip() for k, v in obj.items()}
        except Exception:
            return None
    return None


def evidence_covers_repo(urls, repo: str) -> bool:
    owner, name = repo.split("/", 1)
    for raw in urls or []:
        try:
            p = urlparse(str(raw))
        except Exception:
            continue
        host = p.netloc.lower()
        path = p.path.rstrip("/").lower()
        target = f"/{owner}/{name}/releases".lower()
        api_target = f"/repos/{owner}/{name}/releases".lower()
        if host in {"github.com", "www.github.com"} and path.startswith(target):
            return True
        if host == "api.github.com" and path.startswith(api_target):
            return True
    return False


def score_record(pred: dict, gold: dict):
    answer = parse_answer(pred.get("answer"))
    expected = {str(k): str(v).strip() for k, v in gold["expected"].items()}
    answer_correct = answer == expected
    urls = pred.get("evidence_urls") if isinstance(pred.get("evidence_urls"), list) else []
    source_coverage = all(evidence_covers_repo(urls, repo) for repo in gold["official_repos"])
    searches = int(pred.get("search_queries_used", 0) or 0)
    followups = int(pred.get("followups_used", 0) or 0)
    budget_ok = searches <= 6 and followups <= 8
    return {
        "answer_correct": answer_correct,
        "first_party_source_coverage": source_coverage,
        "verified_success": answer_correct and source_coverage and budget_ok,
        "budget_ok": budget_ok,
        "searches": searches,
        "followups": followups,
        "evidence_url_count": len(urls),
    }


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def paired_summary(base_rows, space_rows, gold_by_id, ids):
    base_score = {}
    space_score = {}
    for item_id in ids:
        base_score[item_id] = score_record(base_rows[item_id], gold_by_id[item_id])
        space_score[item_id] = score_record(space_rows[item_id], gold_by_id[item_id])

    def metric_summary(metric: str):
        bb = sum(base_score[i][metric] for i in ids)
        ss = sum(space_score[i][metric] for i in ids)
        bw_sw = sum((not base_score[i][metric]) and space_score[i][metric] for i in ids)
        br_mw = sum(base_score[i][metric] and (not space_score[i][metric]) for i in ids)
        both = sum(base_score[i][metric] and space_score[i][metric] for i in ids)
        neither = len(ids) - bw_sw - br_mw - both
        return {
            "base": bb,
            "space": ss,
            "n": len(ids),
            "delta_percentage_points": 100.0 * (ss - bb) / len(ids),
            "base_fail_space_pass": bw_sw,
            "base_pass_space_fail": br_mw,
            "both_pass": both,
            "both_fail": neither,
            "exact_mcnemar_p_two_sided": exact_mcnemar(bw_sw, br_mw),
        }

    return {
        "answer_accuracy": metric_summary("answer_correct"),
        "first_party_source_coverage": metric_summary("first_party_source_coverage"),
        "verified_success": metric_summary("verified_success"),
        "budget_violations": {
            "base": sum(not base_score[i]["budget_ok"] for i in ids),
            "space": sum(not space_score[i]["budget_ok"] for i in ids),
        },
        "resource_use": {
            "base_searches": sum(base_score[i]["searches"] for i in ids),
            "space_searches": sum(space_score[i]["searches"] for i in ids),
            "base_followups": sum(base_score[i]["followups"] for i in ids),
            "space_followups": sum(space_score[i]["followups"] for i in ids),
        },
        "discordant_verified_success_ids": [
            i for i in ids if base_score[i]["verified_success"] != space_score[i]["verified_success"]
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--space", required=True)
    ap.add_argument("--base-hash", required=True)
    ap.add_argument("--space-hash", required=True)
    ap.add_argument("--out", default="SESSION3R_SCORE_REPORT.json")
    args = ap.parse_args()

    base_path, space_path = Path(args.base), Path(args.space)
    verify_hash(base_path, Path(args.base_hash))
    verify_hash(space_path, Path(args.space_hash))
    base_list, space_list, gold = read_jsonl(base_path), read_jsonl(space_path), decode_gold()
    if len(base_list) != 100 or len(space_list) != 100 or len(gold) != 100:
        raise SystemExit("expected exactly 100 BASE, 100 SPACE, and 100 gold rows")

    base_rows = {r["id"]: r for r in base_list}
    space_rows = {r["id"]: r for r in space_list}
    gold_by_id = {r["id"]: r for r in gold}
    if len(base_rows) != 100 or len(space_rows) != 100 or len(gold_by_id) != 100:
        raise SystemExit("duplicate IDs detected")
    if set(base_rows) != set(space_rows) or set(base_rows) != set(gold_by_id):
        raise SystemExit("paired task ID sets do not match")

    section_ids = defaultdict(list)
    for row in gold:
        section_ids[row["section"]].append(row["id"])

    report = {
        "experiment_id": "SESSION3R_TEST3R_SPACE",
        "paired_ids_verified": True,
        "receipt_hashes_verified": True,
        "primary": paired_summary(base_rows, space_rows, gold_by_id, section_ids["primary_verified_release_retrieval"]),
        "secondary": paired_summary(base_rows, space_rows, gold_by_id, section_ids["secondary_multi_source_comparison"]),
        "exploratory": paired_summary(base_rows, space_rows, gold_by_id, section_ids["exploratory_release_history_navigation"]),
        "all_100_descriptive": paired_summary(base_rows, space_rows, gold_by_id, [r["id"] for r in gold]),
    }
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["primary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
