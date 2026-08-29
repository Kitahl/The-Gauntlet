#!/usr/bin/env python3
"""Fail-closed local materializers for Reality External Benchmark Suite v1.

This tool writes blind inputs and readable gold to a caller-selected directory.
The directory MUST remain local until upstream redistribution rights are verified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SEED = "REALITY-EXT-BENCH-V1-2026-08-29"


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row))
            handle.write("\n")


def load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] == "[":
        value = json.loads(text)
        if not isinstance(value, list):
            raise ValueError("expected top-level JSON list")
        return [dict(x) for x in value]
    if stripped[0] == "{":
        value = json.loads(text)
        if isinstance(value, dict):
            for key in ("data", "records", "items", "test", "examples"):
                if isinstance(value.get(key), list):
                    return [dict(x) for x in value[key]]
            return [dict(value)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def id_key() -> bytes:
    raw = os.environ.get("REALITY_BENCH_ID_KEY_HEX", "")
    if not raw:
        raise SystemExit("REALITY_BENCH_ID_KEY_HEX is required; generate 32 random bytes locally")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise SystemExit("REALITY_BENCH_ID_KEY_HEX must be hexadecimal") from exc
    if len(key) < 32:
        raise SystemExit("REALITY_BENCH_ID_KEY_HEX must encode at least 32 bytes")
    return key


def opaque_id(prefix: str, source_identifier: str, key: bytes) -> str:
    digest = hmac.new(key, source_identifier.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}_{digest[:24]}"


def selection_rank(namespace: str, source_identifier: str) -> bytes:
    material = f"{SEED}|{namespace}|{source_identifier}".encode("utf-8")
    return hashlib.sha256(material).digest()


def require_fields(row: dict[str, Any], fields: Iterable[str], context: str) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError(f"{context}: missing required fields {missing}")


def source_identifier(row: dict[str, Any], index: int, preferred: Iterable[str]) -> str:
    for field in preferred:
        value = row.get(field)
        if value is not None and str(value).strip():
            return f"{field}:{value}"
    # Fallback is local-only and never emitted into blind payloads.
    digest = hashlib.sha256(canonical_json(row).encode("utf-8")).hexdigest()
    return f"row:{index}:{digest}"


def balanced_pick(
    grouped: dict[str, list[tuple[str, dict[str, Any]]]],
    target_total: int,
    namespace: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Deterministically balance a target across groups, then fill spare slots."""
    groups = sorted(grouped)
    if not groups or target_total <= 0:
        return []
    ordered: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for group in groups:
        ordered[group] = sorted(
            grouped[group], key=lambda item: selection_rank(f"{namespace}:{group}", item[0])
        )
    picked: list[tuple[str, dict[str, Any]]] = []
    cursor = {group: 0 for group in groups}
    while len(picked) < target_total:
        progressed = False
        for group in groups:
            idx = cursor[group]
            if idx < len(ordered[group]) and len(picked) < target_total:
                picked.append(ordered[group][idx])
                cursor[group] += 1
                progressed = True
        if not progressed:
            break
    return picked


def materialize_rinobench(args: argparse.Namespace) -> None:
    records = load_json_or_jsonl(Path(args.input))
    if not records:
        raise SystemExit("RINoBench input is empty")
    key = id_key()
    blind: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    for index, row in enumerate(records):
        require_fields(
            row,
            ("research_idea", "related_works", "novelty_score"),
            f"RINoBench row {index}",
        )
        src = source_identifier(row, index, ("sample_id", "id", "source", "paper_id"))
        sample_id = opaque_id("rino", src, key)
        blind_row = {
            "sample_id": sample_id,
            "research_idea": row["research_idea"],
            "related_works": row["related_works"],
        }
        gold_row = {
            "sample_id": sample_id,
            "source_identifier": src,
            "novelty_score": row["novelty_score"],
            "novelty_reasoning": row.get("novelty_reasoning"),
        }
        blind.append(blind_row)
        gold.append(gold_row)
        grouped[str(row["novelty_score"])].append((src, blind_row))

    expected_labels = {"1", "2", "3", "4", "5"}
    if set(grouped) != expected_labels:
        raise SystemExit(f"RINoBench gold labels mismatch: observed {sorted(grouped)}")
    pilot_pairs = balanced_pick(grouped, args.pilot_size, "rinobench-pilot")
    if len(pilot_pairs) != args.pilot_size:
        raise SystemExit(f"could only select {len(pilot_pairs)} RINoBench pilot items")
    pilot_ids = {row["sample_id"] for _, row in pilot_pairs}
    pilot = [row for row in blind if row["sample_id"] in pilot_ids]

    out = Path(args.out_dir)
    write_jsonl(out / "inputs" / "rinobench_full_blind.jsonl", blind)
    write_jsonl(out / "inputs" / "rinobench_pilot_blind.jsonl", pilot)
    write_jsonl(out / "local_gold" / "rinobench_gold.jsonl", gold)
    print(f"RINOBENCH_FULL={len(blind)}")
    print(f"RINOBENCH_PILOT={len(pilot)}")


def materialize_researchbench(args: argparse.Namespace) -> None:
    records = load_json_or_jsonl(Path(args.input))
    if not records:
        raise SystemExit("ResearchBench input is empty")
    key = id_key()
    blind: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    for index, row in enumerate(records):
        require_fields(row, ("research_question", "gold_hypothesis"), f"ResearchBench row {index}")
        src = source_identifier(row, index, ("sample_id", "doi", "id"))
        sample_id = opaque_id("rbhc", src, key)
        blind_row: dict[str, Any] = {
            "sample_id": sample_id,
            "research_question": row["research_question"],
        }
        for field in ("background_survey", "gold_inspirations"):
            if field in row:
                blind_row[field] = row[field]
        if args.expose_discipline and "discipline" in row:
            blind_row["discipline"] = row["discipline"]
        discipline = str(row.get("discipline", "UNKNOWN"))
        gold_row = {
            "sample_id": sample_id,
            "source_identifier": src,
            "discipline": row.get("discipline"),
            "doi": row.get("doi"),
            "gold_hypothesis": row["gold_hypothesis"],
            "fine_grained_hypothesis": row.get("fine_grained_hypothesis"),
            "experiments_details": row.get("experiments_details"),
        }
        blind.append(blind_row)
        gold.append(gold_row)
        grouped[discipline].append((src, blind_row))

    pilot_pairs = balanced_pick(grouped, args.pilot_size, "researchbench-composition-pilot")
    if len(pilot_pairs) != args.pilot_size:
        raise SystemExit(f"could only select {len(pilot_pairs)} ResearchBench pilot items")
    pilot_ids = {row["sample_id"] for _, row in pilot_pairs}
    pilot = [row for row in blind if row["sample_id"] in pilot_ids]

    out = Path(args.out_dir)
    write_jsonl(out / "inputs" / "researchbench_composition_full_blind.jsonl", blind)
    write_jsonl(out / "inputs" / "researchbench_composition_pilot_blind.jsonl", pilot)
    write_jsonl(out / "local_gold" / "researchbench_composition_gold.jsonl", gold)
    print(f"RESEARCHBENCH_FULL={len(blind)}")
    print(f"RESEARCHBENCH_PILOT={len(pilot)}")
    print(f"RESEARCHBENCH_DISCIPLINES={len(grouped)}")


def read_keywords(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        keyword_field = "Keyword" if "Keyword" in (reader.fieldnames or []) else "keyword"
        for index, row in enumerate(reader):
            keyword = (row.get(keyword_field) or "").strip()
            if keyword:
                source_idx = (row.get("") or row.get("index") or str(index)).strip()
                rows.append((source_idx, keyword))
    return rows


def read_classifications(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            keyword = (row.get("keyword") or "").strip()
            category = (row.get("category") or "").strip()
            if keyword and category:
                if keyword in result and result[keyword] != category:
                    raise ValueError(f"keyword has conflicting categories: {keyword}")
                result[keyword] = category
    return result


def materialize_liveidea(args: argparse.Namespace) -> None:
    keywords = read_keywords(Path(args.keywords))
    classes = read_classifications(Path(args.classifications))
    if not keywords:
        raise SystemExit("LiveIdeaBench keyword CSV is empty")
    key = id_key()
    blind: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    for source_idx, keyword in keywords:
        if keyword not in classes:
            raise SystemExit(f"classification missing for keyword: {keyword}")
        category = classes[keyword]
        src = f"keyword-index:{source_idx}|keyword:{keyword}"
        sample_id = opaque_id("libv2", src, key)
        blind_row = {"sample_id": sample_id, "keyword": keyword}
        gold_row = {
            "sample_id": sample_id,
            "source_identifier": src,
            "keyword": keyword,
            "domain": category,
        }
        blind.append(blind_row)
        gold.append(gold_row)
        grouped[category].append((src, blind_row))

    if args.expected_domains is not None and len(grouped) != args.expected_domains:
        raise SystemExit(
            f"LiveIdeaBench domain count mismatch: expected {args.expected_domains}, observed {len(grouped)}"
        )
    pilot_pairs: list[tuple[str, dict[str, Any]]] = []
    for category in sorted(grouped):
        ranked = sorted(
            grouped[category],
            key=lambda item: selection_rank(f"liveideabench-v2:{category}", item[0]),
        )
        if len(ranked) < args.per_domain:
            raise SystemExit(f"domain {category!r} has fewer than {args.per_domain} keywords")
        pilot_pairs.extend(ranked[: args.per_domain])
    pilot_ids = {row["sample_id"] for _, row in pilot_pairs}
    pilot = [row for row in blind if row["sample_id"] in pilot_ids]

    out = Path(args.out_dir)
    write_jsonl(out / "inputs" / "liveideabench_v2_full_blind.jsonl", blind)
    write_jsonl(out / "inputs" / "liveideabench_v2_pilot_blind.jsonl", pilot)
    write_jsonl(out / "local_gold" / "liveideabench_v2_gold.jsonl", gold)
    print(f"LIVEIDEABENCH_FULL={len(blind)}")
    print(f"LIVEIDEABENCH_DOMAINS={len(grouped)}")
    print(f"LIVEIDEABENCH_PILOT={len(pilot)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="benchmark", required=True)

    rino = sub.add_parser("rinobench")
    rino.add_argument("--input", required=True)
    rino.add_argument("--out-dir", required=True)
    rino.add_argument("--pilot-size", type=int, default=100)
    rino.set_defaults(func=materialize_rinobench)

    research = sub.add_parser("researchbench")
    research.add_argument("--input", required=True)
    research.add_argument("--out-dir", required=True)
    research.add_argument("--pilot-size", type=int, default=100)
    research.add_argument("--expose-discipline", action="store_true")
    research.set_defaults(func=materialize_researchbench)

    live = sub.add_parser("liveidea")
    live.add_argument("--keywords", required=True)
    live.add_argument("--classifications", required=True)
    live.add_argument("--out-dir", required=True)
    live.add_argument("--expected-domains", type=int, default=22)
    live.add_argument("--per-domain", type=int, default=2)
    live.set_defaults(func=materialize_liveidea)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
