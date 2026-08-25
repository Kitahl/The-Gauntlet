#!/usr/bin/env python3
"""CI adapter for FreshQA's public Google Sheet CSV endpoint."""
from __future__ import annotations

import csv
import hashlib
import io
import random
import re

import build_package as bp

bp.FRESHQA_CSV = (
    f"https://docs.google.com/spreadsheets/d/{bp.FRESHQA_SHEET_ID}/gviz/tq?tqx=out:csv"
)


def load_freshqa(rng: random.Random):
    raw = bp.fetch_bytes(bp.FRESHQA_CSV)
    text = raw.decode("utf-8-sig")
    matrix = list(csv.reader(io.StringIO(text)))

    header_idx = None
    fields = None
    for i, row in enumerate(matrix):
        candidate = list(row)
        norms = [bp.norm_header(x) for x in candidate]
        # FreshQA currently prefixes a warning sentence onto the first header
        # cell, yielding "... models. id" rather than a bare "id".
        if "split" in norms and "question" in norms and "answer0" in norms:
            id_positions = [j for j, value in enumerate(norms) if value == "id" or value.endswith("id")]
            if id_positions:
                candidate[id_positions[0]] = "id"
                header_idx = i
                fields = candidate
                break
    if header_idx is None or not fields:
        preview_headers = [row[:5] for row in matrix[:5]]
        raise RuntimeError(f"FreshQA header row not found; preview={preview_headers!r}")

    dict_rows = []
    for row in matrix[header_idx + 1 :]:
        padded = row + [""] * max(0, len(fields) - len(row))
        dict_rows.append({fields[j]: padded[j] if j < len(padded) else "" for j in range(len(fields))})

    qcol = bp.first_col(fields, ["question", "query", "prompt"])
    splitcol = bp.first_col(fields, ["split", "dataset_split", "set"])
    idcol = bp.first_col(fields, ["id", "question_id", "qid"])
    factcol = bp.first_col(fields, ["fact_type", "fact type", "facttype"])
    hopcol = bp.first_col(fields, ["num_hops", "num hops", "hops", "numhops"])
    falsecol = bp.first_col(fields, ["false_premise", "false premise", "falsepremise"])
    answer_cols = [f for f in fields if re.fullmatch(r"answer(?:[_\s-]*\d+)?", f.strip(), flags=re.I)]
    if not qcol or not answer_cols:
        raise RuntimeError(f"FreshQA schema unsupported; columns={fields}")

    rows = dict_rows
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
        records.append({
            "id": f"freshqa:{stable}",
            "question": question,
            "fact_type": str(row.get(factcol, "unknown")).strip() if factcol else "unknown",
            "num_hops": str(row.get(hopcol, "unknown")).strip() if hopcol else "unknown",
            "false_premise": str(row.get(falsecol, "unknown")).strip() if falsecol else "unknown",
            "answers": answers,
            "source_row": idx,
        })
    if len(records) < 20:
        raise RuntimeError(f"FreshQA yielded only {len(records)} usable rows")

    pairs = bp.make_pairs(records, ["fact_type", "num_hops", "false_premise"], rng, 10)
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
                "snapshot_sha256": bp.sha256_bytes(raw),
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
    return questions, gold, assignments, bp.sha256_bytes(raw), fields


bp.load_freshqa = load_freshqa

if __name__ == "__main__":
    bp.main()
