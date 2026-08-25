#!/usr/bin/env python3
"""Generate question-only and sealed-gold packs from pinned public sources."""
from __future__ import annotations

import hashlib
import json
import random
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SEED = 2026082502
ROOT = Path(__file__).resolve().parent
QUESTIONS = ROOT / "questions"
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
MIND_BLOB_SHA = "8c27111809e390910a74b1380b9fbce12b016999"
OMNI_COMMIT = "4793415ef37d31c9cdb4e5b82dbe172f76f8cf08"
BBEH_COMMIT = "80d12ca916b7158f22293fcf3144f4d3d854d4be"
OMNI_URL = f"https://raw.githubusercontent.com/KbsdJames/omni-math-rule/{OMNI_COMMIT}/omni_math_rule.jsonl"
OMNI_GRADER_URL = f"https://raw.githubusercontent.com/KbsdJames/omni-math-rule/{OMNI_COMMIT}/evaluation/grader.py"
BBEH_URL = f"https://raw.githubusercontent.com/google-deepmind/bbeh/{BBEH_COMMIT}/bbeh/benchmark_tasks/{{family}}/task.json"
BBEH_FAMILIES = [
    "bbeh_boolean_expressions",
    "bbeh_causal_understanding",
    "bbeh_disambiguation_qa",
    "bbeh_dyck_languages",
    "bbeh_multistep_arithmetic",
    "bbeh_object_properties",
    "bbeh_shuffled_objects",
    "bbeh_temporal_sequences",
    "bbeh_time_arithmetic",
    "bbeh_web_of_lies",
]
DIFFICULTY_BANDS = [(6.0, 6.49), (6.5, 6.99), (7.0, 7.49), (7.5, 7.99), (8.0, 8.5)]
IMAGE_MARKERS = ("\\includegraphics", "[asy]", "the figure below", "shown in the figure", "refer to the figure")


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Gauntlet-Test2-Builder/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_no}: expected object")
            row["_source_index"] = line_no
            rows.append(row)
    return rows


def domain_text(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(x).strip() for x in value if str(x).strip()) or "unknown"
    return str(value or "unknown").strip() or "unknown"


def band_for(value: float) -> tuple[float, float] | None:
    return next(((low, high) for low, high in DIFFICULTY_BANDS if low <= value <= high), None)


def eligible_omni(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        problem = str(row.get("problem") or row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()
        try:
            difficulty = float(row.get("difficulty"))
        except (TypeError, ValueError):
            continue
        if not problem or not answer or band_for(difficulty) is None:
            continue
        if len(problem) > 7000 or len(answer) > 700:
            continue
        lower = problem.lower()
        if any(marker.lower() in lower for marker in IMAGE_MARKERS):
            continue
        item = dict(row)
        item.update(problem=problem, answer=answer, difficulty=difficulty, domain_text=domain_text(row.get("domain")))
        output.append(item)
    return output


def choose_omni(rows: list[dict[str, Any]], rng: random.Random):
    pairs = []
    used: set[int] = set()
    for low, high in DIFFICULTY_BANDS:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            idx = int(row["_source_index"])
            if idx not in used and low <= row["difficulty"] <= high:
                grouped[row["domain_text"]].append(row)
        domains = [name for name, items in grouped.items() if len(items) >= 2]
        rng.shuffle(domains)
        count = 0
        for name in domains:
            items = list(grouped[name])
            rng.shuffle(items)
            a, b = items[:2]
            pairs.append((a, b, f"omni_{low:g}_{high:g}_{count + 1}"))
            used.update((int(a["_source_index"]), int(b["_source_index"])))
            count += 1
            if count == 2:
                break
        if count < 2:
            pool = [row for row in rows if int(row["_source_index"]) not in used and low <= row["difficulty"] <= high]
            pool.sort(key=lambda row: (row["domain_text"], len(row["problem"]), int(row["_source_index"])))
            while count < 2 and len(pool) >= 2:
                a = pool.pop(0)
                pos = min(range(len(pool)), key=lambda i: (abs(len(pool[i]["problem"]) - len(a["problem"])), int(pool[i]["_source_index"])))
                b = pool.pop(pos)
                pairs.append((a, b, f"omni_{low:g}_{high:g}_{count + 1}"))
                used.update((int(a["_source_index"]), int(b["_source_index"])))
                count += 1
        if count != 2:
            raise RuntimeError(f"could not form two Omni pairs in {low}-{high}")

    questions, gold, assignments = [], [], []
    for order, (a, b, pair_id) in enumerate(pairs, 1):
        if rng.random() >= 0.5:
            a, b = b, a
        for condition, row in (("BASE", a), ("MIND", b)):
            index = int(row["_source_index"])
            item_id = f"omni_rule_{index:04d}"
            questions.append({"id": item_id, "benchmark": "omni_math_rule", "prompt": row["problem"], "difficulty": row["difficulty"], "domain": row["domain_text"], "source": row.get("source"), "pair_id": pair_id})
            gold.append({"id": item_id, "benchmark": "omni_math_rule", "reference_answer": row["answer"], "reference_solution": row.get("solution"), "difficulty": row["difficulty"], "domain": row["domain_text"], "source_index": index})
            assignments.append({"id": item_id, "benchmark": "omni_math_rule", "condition": condition, "pair_id": pair_id, "order_within_benchmark": order})
    return questions, gold, assignments


def choose_bbeh(rng: random.Random):
    questions, gold, assignments = [], [], []
    for order, family in enumerate(BBEH_FAMILIES, 1):
        payload = json.loads(fetch_bytes(BBEH_URL.format(family=family)).decode("utf-8"))
        examples = payload.get("examples")
        if not isinstance(examples, list):
            raise ValueError(f"{family}: missing examples")
        candidates = [(idx, ex) for idx, ex in enumerate(examples) if isinstance(ex, dict) and str(ex.get("input") or "").strip() and str(ex.get("target") or "").strip() and len(str(ex.get("input"))) <= 30000]
        if len(candidates) < 2:
            raise RuntimeError(f"{family}: fewer than two eligible examples")
        rng.shuffle(candidates)
        picked = candidates[:2]
        if rng.random() >= 0.5:
            picked.reverse()
        pair_id = f"bbeh_{order:02d}_{family}"
        for condition, (index, ex) in zip(("BASE", "MIND"), picked, strict=True):
            item_id = f"bbeh_{family.removeprefix('bbeh_')}_{index:04d}"
            questions.append({"id": item_id, "benchmark": "bbeh", "family": family, "prompt": str(ex["input"]).strip(), "pair_id": pair_id})
            gold.append({"id": item_id, "benchmark": "bbeh", "family": family, "target": str(ex["target"]).strip(), "source_index": index})
            assignments.append({"id": item_id, "benchmark": "bbeh", "condition": condition, "pair_id": pair_id, "order_within_benchmark": order})
    return questions, gold, assignments


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    rng = random.Random(SEED)
    QUESTIONS.mkdir(parents=True, exist_ok=True)
    GOLD.mkdir(parents=True, exist_ok=True)
    omni_raw = fetch_bytes(OMNI_URL)
    omni_q, omni_g, omni_a = choose_omni(eligible_omni(load_jsonl(omni_raw)), rng)
    bbeh_q, bbeh_g, bbeh_a = choose_bbeh(rng)
    write_jsonl(QUESTIONS / "omni_math_rule_questions.jsonl", omni_q)
    write_jsonl(QUESTIONS / "bbeh_questions.jsonl", bbeh_q)
    write_jsonl(GOLD / "omni_math_rule_gold.jsonl", omni_g)
    write_jsonl(GOLD / "bbeh_gold.jsonl", bbeh_g)
    (GOLD / "README.md").write_text("# Sealed gold — do not open during inference\n\nOpening this directory before both `BASE COMMITTED` and `MIND COMMITTED` receipts exist invalidates the run.\n", encoding="utf-8")
    (ROOT / "grader.py").write_bytes(fetch_bytes(OMNI_GRADER_URL))
    assignments = omni_a + bbeh_a
    write_json(ROOT / "assignments.json", {"experiment_id": "SESSION2_TEST2_MIND", "seed": SEED, "policy": "disjoint matched pairs; BASE completed before Mind exposure", "assignments": sorted(assignments, key=lambda row: (0 if row["condition"] == "BASE" else 1, 0 if row["benchmark"] == "omni_math_rule" else 1, row["order_within_benchmark"]))})
    generated = [QUESTIONS / "omni_math_rule_questions.jsonl", QUESTIONS / "bbeh_questions.jsonl", GOLD / "omni_math_rule_gold.jsonl", GOLD / "bbeh_gold.jsonl", GOLD / "README.md", ROOT / "assignments.json", ROOT / "grader.py"]
    manifest = {
        "schema": "gauntlet.session2.test2.mind-package.v1",
        "experiment_id": "SESSION2_TEST2_MIND",
        "seed": SEED,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mind": {"repository": "Kitahl/The-Gauntlet", "path": "skills/mathbot/SKILL.md", "blob_sha": MIND_BLOB_SHA},
        "sources": {
            "omni_math_rule": {"repository": "KbsdJames/omni-math-rule", "commit": OMNI_COMMIT, "path": "omni_math_rule.jsonl", "download_sha256": hashlib.sha256(omni_raw).hexdigest()},
            "bbeh": {"repository": "google-deepmind/bbeh", "commit": BBEH_COMMIT, "families": BBEH_FAMILIES},
        },
        "counts": {"omni_total": len(omni_q), "bbeh_total": len(bbeh_q), "base_total": sum(row["condition"] == "BASE" for row in assignments), "mind_total": sum(row["condition"] == "MIND" for row in assignments)},
        "files": {str(path.relative_to(ROOT)): {"sha256": sha256(path), "bytes": path.stat().st_size} for path in generated},
    }
    write_json(ROOT / "MANIFEST.json", manifest)
    print(json.dumps(manifest["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
