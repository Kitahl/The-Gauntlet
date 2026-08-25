#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
QUESTIONS = ROOT / "questions"
GOLD = ROOT / "gold" / "SEALED_UNTIL_BOTH_ARMS_COMMIT"
FORBIDDEN_KEYS = {"answer", "answers", "target", "targets", "solution", "solutions", "gold", "reference_answer", "reference_solution"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise AssertionError(f"{path}:{line_no}: not an object")
            rows.append(obj)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise AssertionError(f"gold-like key {key!r} present in question projection at {path}")
            scan_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_keys(child, f"{path}[{index}]")


def main() -> None:
    required = [
        ROOT / "assignments.json",
        ROOT / "MANIFEST.json",
        QUESTIONS / "omni_math_rule_questions.jsonl",
        QUESTIONS / "bbeh_questions.jsonl",
        GOLD / "omni_math_rule_gold.jsonl",
        GOLD / "bbeh_gold.jsonl",
        GOLD / "README.md",
    ]
    for path in required:
        if not path.is_file():
            raise AssertionError(f"missing {path.relative_to(ROOT)}")

    omni_q = load_jsonl(QUESTIONS / "omni_math_rule_questions.jsonl")
    bbeh_q = load_jsonl(QUESTIONS / "bbeh_questions.jsonl")
    omni_g = load_jsonl(GOLD / "omni_math_rule_gold.jsonl")
    bbeh_g = load_jsonl(GOLD / "bbeh_gold.jsonl")
    assert len(omni_q) == 20, len(omni_q)
    assert len(bbeh_q) == 20, len(bbeh_q)
    assert len(omni_g) == 20, len(omni_g)
    assert len(bbeh_g) == 20, len(bbeh_g)

    for row in omni_q + bbeh_q:
        scan_keys(row)

    question_ids = {row["id"] for row in omni_q + bbeh_q}
    gold_ids = {row["id"] for row in omni_g + bbeh_g}
    assert len(question_ids) == 40
    assert question_ids == gold_ids

    assignments_doc = json.loads((ROOT / "assignments.json").read_text(encoding="utf-8"))
    assignments = assignments_doc["assignments"]
    assert len(assignments) == 40
    assigned_ids = {row["id"] for row in assignments}
    assert assigned_ids == question_ids
    base = [row for row in assignments if row["condition"] == "BASE"]
    mind = [row for row in assignments if row["condition"] == "MIND"]
    assert len(base) == 20 and len(mind) == 20
    for condition_rows in (base, mind):
        assert sum(row["benchmark"] == "omni_math_rule" for row in condition_rows) == 10
        assert sum(row["benchmark"] == "bbeh" for row in condition_rows) == 10

    pairs: dict[str, list[dict[str, Any]]] = {}
    for row in assignments:
        pairs.setdefault(row["pair_id"], []).append(row)
    assert len(pairs) == 20
    for pair_id, rows in pairs.items():
        assert len(rows) == 2, pair_id
        assert {row["condition"] for row in rows} == {"BASE", "MIND"}, pair_id
        assert len({row["benchmark"] for row in rows}) == 1, pair_id

    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["mind"]["blob_sha"] == "8c27111809e390910a74b1380b9fbce12b016999"
    assert manifest["sources"]["omni_math_rule"]["commit"] == "4793415ef37d31c9cdb4e5b82dbe172f76f8cf08"
    assert manifest["sources"]["bbeh"]["commit"] == "80d12ca916b7158f22293fcf3144f4d3d854d4be"
    for relative, metadata in manifest["files"].items():
        file_path = ROOT / relative
        assert file_path.is_file(), relative
        assert sha256(file_path) == metadata["sha256"], relative
        assert file_path.stat().st_size == metadata["bytes"], relative

    print("PASS: 40 question-only records, 40 sealed-gold records, matched 20/20 allocation")


if __name__ == "__main__":
    main()
