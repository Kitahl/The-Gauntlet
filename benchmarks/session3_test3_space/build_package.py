#!/usr/bin/env python3
"""Build a question-only + sealed-gold package for Session 3 / Test 3.

Raw source records are fetched inside CI. Only sanitized question projections and a
separate sealed scoring pack are committed to the benchmark branch.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEED = 2026082503
ROOT = Path(__file__).resolve().parent
QUESTIONS = ROOT / "questions"
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
SCORING = ROOT / "scoring" / "assistantbench"

SPACE_BLOB_SHA = "a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d"
FRESHQA_REPO_COMMIT = "7d2d3683991916f3633e480548a6aa5c9a62e3db"
FRESHQA_SHEET_ID = "1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM"
FRESHQA_CSV = f"https://docs.google.com/spreadsheets/d/{FRESHQA_SHEET_ID}/export?format=csv&gid=0"
ASSISTANTBENCH_REV = "482cbbc0400f6d048438c4021727f21a10cbff49"
ASSISTANTBENCH_DEV = (
    "https://huggingface.co/datasets/AssistantBench/AssistantBench/resolve/"
    f"{ASSISTANTBENCH_REV}/assistant_bench_v1.0_dev.jsonl"
)
BROWSERGYM_COMMIT = "9e779f087de9a65668b6974d11f9ce9816026e96"
BROWSERGYM_RAW = (
    "https://raw.githubusercontent.com/ServiceNow/BrowserGym/"
    f"{BROWSERGYM_COMMIT}/browsergym/assistantbench/src/browsergym/assistantbench/evaluation"
)

# Historical AssistantBench tasks used in the earlier Soul smoke test. They are
# excluded even though most are from the test split rather than dev.
ASSISTANT_EXCLUDE = {
    "093801d638247024e59893033aa8761f45804796a16c91e3cf0209cf083ca13e",
    "09e4811ec2b99f402f990b4156e50d1406cd5357d9f6e53b5608ebe0054033c8",
    "0badf85df8ca5522b2c456ac0a49752ae19e161881780a1187a4cb1e4a498d2f",
    "295c401c9dd5fa1de8a967d2b96eb9c5507985185e0733637f53c2e9cf255e59",
    "2bedecc055920566a97e6f049dc9c722d7a8d46adff62bcb096904e7e3783c04",
    "2f6a86fe1241c77ed3ea77056cf63868bb7f9dbe7794b36d62d9fa4d8c680328",
    "3940b9ef19e15c72b9f833ad4121c789ae07bf2bdc49bc2197894cc7af6a43d2",
}


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GauntletBenchmark/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def norm_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def first_col(fields: list[str], candidates: list[str]) -> str | None:
    lookup = {norm_header(f): f for f in fields}
    for candidate in candidates:
        if norm_header(candidate) in lookup:
            return lookup[norm_header(candidate)]
    return None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def make_pairs(records: list[dict[str, Any]], stratum_keys: list[str], rng: random.Random, n_pairs: int = 10) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        key = tuple(str(rec.get(k, "")) for k in stratum_keys)
        groups[key].append(rec)
    for values in groups.values():
        rng.shuffle(values)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    leftovers: list[dict[str, Any]] = []
    keys = list(groups)
    rng.shuffle(keys)
    # First pass: at most one pair from each stratum, maximizing diversity.
    for key in keys:
        vals = groups[key]
        if len(vals) >= 2 and len(pairs) < n_pairs:
            pairs.append((vals.pop(), vals.pop()))
        leftovers.extend(vals)
    # Second pass: use remaining within-stratum pairs when possible.
    if len(pairs) < n_pairs:
        for key in keys:
            vals = groups[key]
            while len(vals) >= 2 and len(pairs) < n_pairs:
                pairs.append((vals.pop(), vals.pop()))
    # Final deterministic fallback if metadata strata are too sparse.
    if len(pairs) < n_pairs:
        used_ids = {id(x) for p in pairs for x in p}
        pool = [r for r in records if id(r) not in used_ids]
        rng.shuffle(pool)
        while len(pool) >= 2 and len(pairs) < n_pairs:
            pairs.append((pool.pop(), pool.pop()))
    if len(pairs) != n_pairs:
        raise RuntimeError(f"could only construct {len(pairs)} matched pairs")
    return pairs


def load_freshqa(rng: random.Random):
    raw = fetch_bytes(FRESHQA_CSV)
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = list(reader.fieldnames or [])
    if not fields:
        raise RuntimeError("FreshQA CSV has no header")

    qcol = first_col(fields, ["question", "query", "prompt"])
    splitcol = first_col(fields, ["split", "dataset_split", "set"])
    idcol = first_col(fields, ["id", "question_id", "qid"])
    factcol = first_col(fields, ["fact_type", "fact type", "facttype"])
    hopcol = first_col(fields, ["num_hops", "num hops", "hops", "numhops"])
    falsecol = first_col(fields, ["false_premise", "false premise", "falsepremise"])

    answer_cols = [
        f for f in fields
        if re.fullmatch(r"answer(?:[_\s-]*\d+)?", f.strip(), flags=re.IGNORECASE)
    ]
    if not answer_cols:
        answer_cols = [f for f in fields if "answer" in norm_header(f) and "source" not in norm_header(f)]
    if not qcol or not answer_cols:
        raise RuntimeError(f"FreshQA schema unsupported; columns={fields}")

    rows = list(reader)
    if splitcol:
        test_rows = [r for r in rows if str(r.get(splitcol, "")).strip().upper() == "TEST"]
        if len(test_rows) >= 20:
            rows = test_rows

    records = []
    for idx, row in enumerate(rows):
        question = str(row.get(qcol, "")).strip()
        answers = [str(row.get(c, "")).strip() for c in answer_cols if str(row.get(c, "")).strip()]
        if not question or not answers:
            continue
        source_id = str(row.get(idcol, "")).strip() if idcol else ""
        stable = source_id or hashlib.sha256(question.encode("utf-8")).hexdigest()[:24]
        rec = {
            "id": f"freshqa:{stable}",
            "question": question,
            "fact_type": str(row.get(factcol, "unknown")).strip() if factcol else "unknown",
            "num_hops": str(row.get(hopcol, "unknown")).strip() if hopcol else "unknown",
            "false_premise": str(row.get(falsecol, "unknown")).strip() if falsecol else "unknown",
            "answers": answers,
            "source_row": idx,
        }
        records.append(rec)
    if len(records) < 20:
        raise RuntimeError(f"FreshQA yielded only {len(records)} usable rows")

    pairs = make_pairs(records, ["fact_type", "num_hops", "false_premise"], rng, 10)
    questions, gold, assignments = [], [], []
    condition_counts = {"BASE": 0, "SPACE": 0}
    for pair_index, pair in enumerate(pairs, 1):
        pair = list(pair)
        rng.shuffle(pair)
        for j, rec in enumerate(pair):
            condition = "BASE" if j == 0 else "SPACE"
            condition_counts[condition] += 1
            item_id = rec["id"]
            questions.append({
                "id": item_id,
                "benchmark": "FreshQA",
                "question": rec["question"],
                "fact_type": rec["fact_type"],
                "num_hops": rec["num_hops"],
                "false_premise": rec["false_premise"],
            })
            gold.append({
                "id": item_id,
                "benchmark": "FreshQA",
                "answers": rec["answers"],
                "source_row": rec["source_row"],
                "snapshot_sha256": sha256_bytes(raw),
            })
            assignments.append({
                "id": item_id,
                "benchmark": "FreshQA",
                "condition": condition,
                "pair_id": f"freshqa-pair-{pair_index:02d}",
                "condition_order": condition_counts[condition],
                "fact_type": rec["fact_type"],
                "num_hops": rec["num_hops"],
                "false_premise": rec["false_premise"],
            })
    return questions, gold, assignments, sha256_bytes(raw), fields


def load_assistantbench(rng: random.Random):
    raw = fetch_bytes(ASSISTANTBENCH_DEV)
    records = [r for r in load_jsonl_bytes(raw) if r.get("id") not in ASSISTANT_EXCLUDE]
    usable = [r for r in records if r.get("id") and r.get("task") and r.get("answer") not in (None, "")]
    if len(usable) < 20:
        raise RuntimeError(f"AssistantBench yielded only {len(usable)} usable dev rows")

    pairs = make_pairs(usable, ["difficulty"], rng, 10)
    questions, gold, assignments = [], [], []
    condition_counts = {"BASE": 0, "SPACE": 0}
    for pair_index, pair in enumerate(pairs, 1):
        pair = list(pair)
        rng.shuffle(pair)
        for j, rec in enumerate(pair):
            condition = "BASE" if j == 0 else "SPACE"
            condition_counts[condition] += 1
            item_id = f"assistantbench:{rec['id']}"
            questions.append({
                "id": item_id,
                "benchmark": "AssistantBench",
                "task": rec["task"],
                "difficulty": rec.get("difficulty"),
            })
            gold.append({
                "id": item_id,
                "benchmark": "AssistantBench",
                "answer": rec["answer"],
                "gold_url": rec.get("gold_url"),
                "explanation": rec.get("explanation"),
                "difficulty": rec.get("difficulty"),
                "source_id": rec["id"],
            })
            assignments.append({
                "id": item_id,
                "benchmark": "AssistantBench",
                "condition": condition,
                "pair_id": f"assistantbench-pair-{pair_index:02d}",
                "condition_order": condition_counts[condition],
                "difficulty": rec.get("difficulty"),
            })
    return questions, gold, assignments, sha256_bytes(raw)


def vendor_assistantbench_evaluator() -> None:
    files = {
        "evaluator.py": f"{BROWSERGYM_RAW}/evaluator.py",
        "evaluate_utils/evaluate_factory.py": f"{BROWSERGYM_RAW}/evaluate_utils/evaluate_factory.py",
        "evaluate_utils/evaluate_dicts.py": f"{BROWSERGYM_RAW}/evaluate_utils/evaluate_dicts.py",
        "evaluate_utils/evaluate_numbers.py": f"{BROWSERGYM_RAW}/evaluate_utils/evaluate_numbers.py",
        "evaluate_utils/evaluate_strings.py": f"{BROWSERGYM_RAW}/evaluate_utils/evaluate_strings.py",
        "evaluate_utils/utils.py": f"{BROWSERGYM_RAW}/evaluate_utils/utils.py",
    }
    (SCORING / "evaluate_utils").mkdir(parents=True, exist_ok=True)
    (SCORING / "__init__.py").write_text("", encoding="utf-8")
    (SCORING / "evaluate_utils" / "__init__.py").write_text("", encoding="utf-8")
    for rel, url in files.items():
        path = SCORING / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch_bytes(url))


def write_score_script() -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
sys.path.insert(0, str(ROOT / "scoring"))
from assistantbench.evaluator import question_scorer


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--freshqa-adjudication", help="optional JSON object {id: true/false} for non-exact FreshQA cases")
    args = ap.parse_args()
    preds = {r["id"]: r for r in read_jsonl(args.predictions)}
    assigns = json.loads((ROOT / "assignments.json").read_text(encoding="utf-8"))["assignments"]
    fg = {r["id"]: r for r in read_jsonl(GOLD / "freshqa_gold.jsonl")}
    ag = {r["id"]: r for r in read_jsonl(GOLD / "assistantbench_gold.jsonl")}
    adjud = {}
    if args.freshqa_adjudication:
        adjud = json.loads(Path(args.freshqa_adjudication).read_text(encoding="utf-8"))

    rows=[]
    for a in assigns:
        p = preds.get(a["id"], {})
        answer = p.get("answer", "")
        if a["benchmark"] == "AssistantBench":
            score, has_ans = question_scorer(answer, ag[a["id"]]["answer"])
            status = "SCORED"
        else:
            exact = any(norm(answer) == norm(g) for g in fg[a["id"]]["answers"])
            if exact:
                score, status = 1.0, "EXACT"
            elif a["id"] in adjud:
                score, status = (1.0 if adjud[a["id"]] else 0.0), "ADJUDICATED"
            else:
                score, status = None, "REVIEW_REQUIRED"
            has_ans = 1.0 if str(answer).strip() else 0.0
        rows.append({**a, "answer": answer, "score": score, "has_answer": has_ans, "status": status})

    for bench in ["FreshQA", "AssistantBench"]:
        print(f"\n{bench}")
        for cond in ["BASE", "SPACE"]:
            rr=[r for r in rows if r["benchmark"]==bench and r["condition"]==cond]
            scored=[r for r in rr if r["score"] is not None]
            mean=sum(r["score"] for r in scored)/len(scored) if scored else None
            print(cond, {"scored":len(scored), "n":len(rr), "mean":mean, "review_required":sum(r["score"] is None for r in rr)})
    print("\nTASK RESULTS")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''
    (ROOT / "score.py").write_text(script, encoding="utf-8")
    (ROOT / "requirements-score.txt").write_text("numpy\nscipy\n", encoding="utf-8")


def main() -> None:
    rng = random.Random(SEED)
    QUESTIONS.mkdir(parents=True, exist_ok=True)
    GOLD.mkdir(parents=True, exist_ok=True)

    fq_q, fq_g, fq_a, fresh_sha, fresh_cols = load_freshqa(rng)
    ab_q, ab_g, ab_a, assistant_sha = load_assistantbench(rng)
    write_jsonl(QUESTIONS / "freshqa_questions.jsonl", fq_q)
    write_jsonl(GOLD / "freshqa_gold.jsonl", fq_g)
    write_jsonl(QUESTIONS / "assistantbench_questions.jsonl", ab_q)
    write_jsonl(GOLD / "assistantbench_gold.jsonl", ab_g)

    assignments = fq_a + ab_a
    assignments.sort(key=lambda x: (0 if x["condition"] == "BASE" else 1, 0 if x["benchmark"] == "FreshQA" else 1, x["condition_order"]))
    (ROOT / "assignments.json").write_text(json.dumps({"schema":"gauntlet.session3.test3.space.assignments.v1","seed":SEED,"assignments":assignments}, indent=2, ensure_ascii=False, sort_keys=True)+"\n", encoding="utf-8")

    vendor_assistantbench_evaluator()
    write_score_script()
    (GOLD / "README.md").write_text("SEALED. Do not access any file in this directory until both BASE and SPACE prediction receipts are committed.\n", encoding="utf-8")

    generated = [
        ROOT / "assignments.json",
        QUESTIONS / "freshqa_questions.jsonl",
        QUESTIONS / "assistantbench_questions.jsonl",
        GOLD / "freshqa_gold.jsonl",
        GOLD / "assistantbench_gold.jsonl",
        GOLD / "README.md",
        ROOT / "score.py",
        ROOT / "requirements-score.txt",
        SCORING / "evaluator.py",
        SCORING / "evaluate_utils" / "evaluate_factory.py",
        SCORING / "evaluate_utils" / "evaluate_dicts.py",
        SCORING / "evaluate_utils" / "evaluate_numbers.py",
        SCORING / "evaluate_utils" / "evaluate_strings.py",
        SCORING / "evaluate_utils" / "utils.py",
    ]
    manifest = {
        "schema": "gauntlet.session3.test3.space-package.v1",
        "experiment_id": "SESSION3_TEST3_SPACE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "counts": {"freshqa_total":20,"assistantbench_total":20,"base_total":20,"space_total":20},
        "space": {"repository":"Kitahl/The-Gauntlet","path":"skills/scoutbot/SKILL.md","blob_sha":SPACE_BLOB_SHA},
        "sources": {
            "freshqa": {"repository":"freshllms/freshqa","repo_commit":FRESHQA_REPO_COMMIT,"sheet_id":FRESHQA_SHEET_ID,"snapshot_sha256":fresh_sha,"detected_columns":fresh_cols},
            "assistantbench": {"dataset":"AssistantBench/AssistantBench","revision":ASSISTANTBENCH_REV,"file":"assistant_bench_v1.0_dev.jsonl","download_sha256":assistant_sha},
            "assistantbench_scorer": {"repository":"ServiceNow/BrowserGym","commit":BROWSERGYM_COMMIT},
        },
        "budgets": {"search_queries_per_task":8,"source_followups_per_task":12},
        "files": {str(p.relative_to(ROOT)): {"sha256":sha256_file(p),"bytes":p.stat().st_size} for p in generated},
    }
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"ok":True,"freshqa":20,"assistantbench":20,"base":20,"space":20,"freshqa_columns":fresh_cols}))

if __name__ == "__main__":
    main()
