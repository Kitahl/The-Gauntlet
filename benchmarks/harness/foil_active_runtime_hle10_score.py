"""Scorer-only gold access for the sealed active FOIL HLE-10 diagnostic."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "benchmarks" / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from foil_active_runtime_hle10_common import (  # noqa: E402
    EXPECTED, HLE_SHARDS, ITEMS, PREDICTIONS, RECEIPTS, REPORT, RESULTS,
    ProtocolError, now, read_json, sha256_file, write_json,
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def _canon(value: str) -> str:
    text = " ".join(value.strip().casefold().split())
    return re.sub(r"\s*([,;:()\[\]{}])\s*", r"\1", text)


def bounded_normalized_correct(prediction: str, gold: str) -> bool:
    if not isinstance(prediction, str) or not isinstance(gold, str) or len(prediction) > 400:
        return False
    target = _canon(gold)
    if _canon(prediction) == target:
        return True
    cues = re.findall(r"(?i)(?:final\s+answer|answer)\s*(?:is|:)\s*([^\n]+?)(?:[.!]\s*$|$)", prediction.strip())
    if len(cues) != 1 or _canon(cues[0]) != target:
        return False
    tuples = {_canon(value) for value in re.findall(r"[\[(][^\])]{1,100}[\])]", prediction)}
    if len(tuples) > 1 or (tuples and target not in tuples):
        return False
    if re.fullmatch(r"[A-E]", gold.strip()):
        choices = set(re.findall(r"\b[A-E]\b", prediction))
        if len(choices) > 1 or (choices and gold.strip().upper() not in choices):
            return False
    try:
        float(gold.strip())
    except ValueError:
        pass
    else:
        numbers = {_canon(value) for value in re.findall(r"(?<!\w)[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?!\w)", prediction)}
        if any(value != target for value in numbers):
            return False
    return True


def load_gold(data_dir: Path, selected: set[str]) -> dict[str, str]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ProtocolError("pyarrow is required for scoring") from exc
    gold: dict[str, str] = {}
    for name, expected in HLE_SHARDS.items():
        path = data_dir / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"missing or mismatched scorer shard: {name}")
        table = parquet.read_table(path, columns=["id", "answer"])
        for row in table.to_pylist():
            identity = str(row["id"])
            if identity in selected:
                gold[identity] = str(row["answer"])
    if set(gold) != selected:
        raise ProtocolError("scorer gold conservation failed")
    return gold


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, int((len(ordered) * fraction + 0.999999)) - 1)]


def score(data_dir: Path) -> None:
    relative_predictions = PREDICTIONS.relative_to(ROOT).as_posix()
    if _git("ls-files", "--error-unmatch", relative_predictions).returncode or _git("diff", "--quiet", "HEAD", "--", relative_predictions).returncode:
        raise ProtocolError("predictions must be committed and unchanged before gold access")
    predictions = read_json(PREDICTIONS)
    rows = list(predictions.get("rows") or [])
    items = read_json(ITEMS)
    if len(rows) != EXPECTED or len(items.get("items", [])) != EXPECTED:
        raise ProtocolError("prediction/item conservation failed")
    for row in rows:
        path = RECEIPTS / f"{row['task_id']}.json"
        relative = path.relative_to(ROOT).as_posix()
        if sha256_file(path) != row["receipt_sha256"] or _git("ls-files", "--error-unmatch", relative).returncode or _git("diff", "--quiet", "HEAD", "--", relative).returncode:
            raise ProtocolError(f"receipt not frozen: {row['task_id']}")
    selected = {str(item["source_id"]) for item in items["items"]}
    gold = load_gold(data_dir, selected)
    scored: list[dict[str, object]] = []
    multipliers: list[float] = []
    family_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        expected = gold[str(row["source_id"])]
        a0 = row.get("original_answer")
        final = row.get("final_answer")
        a0_raw = isinstance(a0, str) and a0 == expected
        final_raw = isinstance(final, str) and final == expected
        a0_norm = isinstance(a0, str) and bounded_normalized_correct(a0, expected)
        final_norm = isinstance(final, str) and bounded_normalized_correct(final, expected)
        calls = list(row.get("provider_calls") or [])
        base_usage = calls[0].get("usage") if calls and isinstance(calls[0], Mapping) else None
        total_usage = row.get("provider_usage")
        multiplier = None
        if isinstance(base_usage, Mapping) and isinstance(total_usage, Mapping):
            base_tokens = int(base_usage.get("input_tokens", 0)) + int(base_usage.get("output_tokens", 0))
            total_tokens = int(total_usage.get("input_tokens", 0)) + int(total_usage.get("output_tokens", 0))
            if base_tokens > 0:
                multiplier = total_tokens / base_tokens
                multipliers.append(multiplier)
        item = {
            "task_id": row["task_id"], "source_id": row["source_id"], "gold": expected,
            "original_answer": a0, "final_answer": final,
            "a0_raw_correct": a0_raw, "final_raw_correct": final_raw,
            "a0_normalized_correct": a0_norm, "final_normalized_correct": final_norm,
            "raw_rescue": (not a0_raw and final_raw), "raw_damage": (a0_raw and not final_raw),
            "normalized_rescue": (not a0_norm and final_norm), "normalized_damage": (a0_norm and not final_norm),
            "answer_changed": bool(row.get("answer_changed")), "abstention": bool(row.get("abstention")),
            "row_valid": bool(row.get("row_valid")), "accounting_status": row.get("accounting_status"),
            "route": row.get("row_outcome"), "selected_family": row.get("selected_family"),
            "provider_usage": total_usage, "ledger_after_spent_usage": row.get("ledger_after_spent_usage"),
            "cost_accounting_complete": row.get("cost_accounting_complete"), "token_multiplier": multiplier,
        }
        scored.append(item)
        family_rows[str(row.get("selected_family") or "NONE")].append(item)
    valid_usage = [row["provider_usage"] for row in scored if isinstance(row.get("provider_usage"), Mapping)]
    summary = {
        "n": len(scored),
        "a0_raw_correct": sum(bool(row["a0_raw_correct"]) for row in scored),
        "final_raw_correct": sum(bool(row["final_raw_correct"]) for row in scored),
        "a0_normalized_correct": sum(bool(row["a0_normalized_correct"]) for row in scored),
        "final_normalized_correct": sum(bool(row["final_normalized_correct"]) for row in scored),
        "raw_rescues": sum(bool(row["raw_rescue"]) for row in scored),
        "raw_damages": sum(bool(row["raw_damage"]) for row in scored),
        "normalized_rescues": sum(bool(row["normalized_rescue"]) for row in scored),
        "normalized_damages": sum(bool(row["normalized_damage"]) for row in scored),
        "answer_changes": sum(bool(row["answer_changed"]) for row in scored),
        "abstentions": sum(bool(row["abstention"]) for row in scored),
        "invalid_rows": sum(not bool(row["row_valid"]) for row in scored),
        "accounting_invalid_rows": sum(row["accounting_status"] != "VALID" for row in scored),
        "coverage_gaps": sum(row["route"] == "COVERAGE_GAP" for row in scored),
        "stage1_verify_resolved": sum(row["route"] == "VERIFY_RESOLVED" for row in scored),
        "route_counts": dict(sorted(Counter(str(row["route"]) for row in scored).items())),
        "family_counts": dict(sorted(Counter(str(row["selected_family"] or "NONE") for row in scored).items())),
        "per_tool_yield": {
            family: {"rows": len(group), "normalized_rescues": sum(bool(row["normalized_rescue"]) for row in group), "normalized_damages": sum(bool(row["normalized_damage"]) for row in group)}
            for family, group in sorted(family_rows.items())
        },
        "provider_input_tokens": sum(int(row["input_tokens"]) for row in valid_usage),
        "provider_cached_input_tokens": sum(int(row["cached_input_tokens"]) for row in valid_usage),
        "provider_output_tokens": sum(int(row["output_tokens"]) for row in valid_usage),
        "provider_total_tokens": sum(int(row["total_tokens"]) for row in valid_usage),
        "mean_token_multiplier": None if not multipliers else statistics.mean(multipliers),
        "median_token_multiplier": None if not multipliers else statistics.median(multipliers),
        "p90_token_multiplier": _percentile(multipliers, 0.9),
        "safety_gate_zero_damage": not any(bool(row["normalized_damage"]) for row in scored),
        "promising_gate_rescue": any(bool(row["normalized_rescue"]) for row in scored),
        "efficiency_target_mean_le_1_35": bool(multipliers) and statistics.mean(multipliers) <= 1.35,
    }
    result = {
        "schema": "foil.active-runtime-hle10-results.v1", "classification": "DIAGNOSTIC_UNADMITTED_N10",
        "predictions_sha256": sha256_file(PREDICTIONS), "scored_at": now(),
        "summary": summary, "rows": scored,
        "production_authorized": False, "promotion_authorized": False,
    }
    write_json(RESULTS, result)
    lines = [
        "# FOIL active-runtime HLE-10 diagnostic", "",
        f"- A0 raw / normalized: **{summary['a0_raw_correct']}/10 / {summary['a0_normalized_correct']}/10**",
        f"- FOIL raw / normalized: **{summary['final_raw_correct']}/10 / {summary['final_normalized_correct']}/10**",
        f"- Normalized rescues / damages: **{summary['normalized_rescues']} / {summary['normalized_damages']}**",
        f"- Coverage gaps: **{summary['coverage_gaps']}**; accounting-invalid: **{summary['accounting_invalid_rows']}**",
        f"- New provider tokens: **{summary['provider_total_tokens']}** (cached input reported separately: {summary['provider_cached_input_tokens']})",
        f"- Mean / median / P90 multiplier: **{summary['mean_token_multiplier']} / {summary['median_token_multiplier']} / {summary['p90_token_multiplier']}**",
        "", "Classification: `DIAGNOSTIC_UNADMITTED_N10`. No production or promotion authority.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hle-data", type=Path, required=True)
    args = parser.parse_args()
    score(args.hle_data)


if __name__ == "__main__":
    main()
