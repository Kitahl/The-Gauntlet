#!/usr/bin/env python3
"""Independent post-score audit for the FOIL HLE active-route pilot.

This file deliberately does not import the benchmark runner or its scorer.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-26" / "hle_active_20"
SOURCE_URL = (
    "https://raw.githubusercontent.com/ustc-ai4science/Science-Star/"
    "4abe1db2d6d0920aa0a6236ee2f81de872adafa5/"
    "data/HLE/subset/hle_subset_50.jsonl"
)
SOURCE_SHA256 = "7e6deb84eafffaea128823ae53f9d7ee9ebfa7aaf77ff465f5d7df595606a361"
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


class AuditError(RuntimeError):
    pass


def load(path: Path) -> Any:
    def closed(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AuditError(f"duplicate JSON key: {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=closed)


def dump(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def usage(value: object) -> dict[str, int]:
    raw = value if isinstance(value, dict) else {}
    result: dict[str, int] = {}
    for key in USAGE_KEYS:
        item = raw.get(key, 0)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise AuditError(f"invalid usage field: {key}={item!r}")
        result[key] = item
    return result


def total_tokens(value: dict[str, int]) -> int:
    return value["input_tokens"] + value["output_tokens"]


def fetch_gold(items: list[dict[str, Any]]) -> dict[str, object]:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "FOIL-HLE-independent-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    if sha256_bytes(payload) != SOURCE_SHA256:
        raise AuditError("independent source hash mismatch")
    source = {
        str(row["id"]): row
        for row in (
            json.loads(line)
            for line in payload.decode("utf-8").splitlines()
            if line.strip()
        )
    }
    return {str(item["id"]): source[str(item["source_id"])]["answer"] for item in items}


def summarize(rows: list[dict[str, Any]]) -> dict[str, object]:
    multipliers = [row["combined_tokens"] / row["base_tokens"] for row in rows if row["base_tokens"]]
    tool_counts = [row["tool_calls"] for row in rows if row["arm"] == "FOIL_TOOLS"]
    return {
        "n": len(rows),
        "base_valid": sum(row["base_valid"] for row in rows),
        "base_correct": sum(row["base_correct"] for row in rows),
        "base_accuracy_all": sum(row["base_correct"] for row in rows) / len(rows),
        "final_valid": sum(row["final_valid"] for row in rows),
        "final_correct": sum(row["final_correct"] for row in rows),
        "final_accuracy_all": sum(row["final_correct"] for row in rows) / len(rows),
        "rescues": sum(row["rescued"] for row in rows),
        "published_damages": sum(row["damaged"] for row in rows),
        "correct_a0_withheld_by_invalid_final": sum(row["withheld_correct"] for row in rows),
        "answer_changes_on_valid": sum(row["answer_changed"] for row in rows),
        "provider_calls": sum(row["provider_calls"] for row in rows),
        "tool_rows": sum(row["tool_calls"] > 0 for row in rows),
        "tool_calls": sum(row["tool_calls"] for row in rows),
        "web_search_calls": sum(row["web_search_calls"] for row in rows),
        "command_calls": sum(row["command_calls"] for row in rows),
        "tool_calls_per_tool_arm_row": {
            "min": None if not tool_counts else min(tool_counts),
            "median": None if not tool_counts else statistics.median(tool_counts),
            "mean": None if not tool_counts else statistics.mean(tool_counts),
            "max": None if not tool_counts else max(tool_counts),
        },
        "base_tokens": sum(row["base_tokens"] for row in rows),
        "base_input_tokens": sum(row["base_input_tokens"] for row in rows),
        "base_output_tokens": sum(row["base_output_tokens"] for row in rows),
        "route_tokens": sum(row["route_tokens"] for row in rows),
        "route_input_tokens": sum(row["route_input_tokens"] for row in rows),
        "route_output_tokens": sum(row["route_output_tokens"] for row in rows),
        "combined_tokens": sum(row["combined_tokens"] for row in rows),
        "route_cached_input_tokens": sum(row["route_cached_input_tokens"] for row in rows),
        "mean_total_multiplier_vs_a0": statistics.mean(multipliers),
        "median_total_multiplier_vs_a0": statistics.median(multipliers),
        "tool_output_characters": sum(row["tool_output_characters"] for row in rows),
        "tool_status_counts": dict(sorted(Counter(status for row in rows for status in row["tool_statuses"]).items())),
        "tool_command_kind_counts": dict(
            sorted(Counter(kind for row in rows for kind in row["command_kinds"]).items())
        ),
        "first_tool_event_counts": dict(sorted(Counter(str(row["first_tool_event"]) for row in rows if row["first_tool_event"] is not None).items())),
    }


def private_skill_read_counts() -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in sorted((OUT / "private").glob("*/route/events.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") if isinstance(event, dict) else None
            if (
                event.get("type") != "item.completed"
                or not isinstance(item, dict)
                or item.get("type") != "command_execution"
            ):
                continue
            command = item.get("command")
            if not isinstance(command, str):
                continue
            normalized = command.replace("\\", "/")
            while "//" in normalized:
                normalized = normalized.replace("//", "/")
            match = re.search(r"/skills/([^/]+)/SKILL\.md", normalized, re.IGNORECASE)
            if match:
                counts[match.group(1).casefold()] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    items = load(OUT / "items.json")["items"]
    predictions = load(OUT / "predictions.json")["predictions"]
    results = load(OUT / "results.json")["rows"]
    if len(items) != 20 or len(predictions) != 60 or len(results) != 60:
        raise AuditError("row conservation failed")
    gold = fetch_gold(items)
    prediction_map = {str(row["unit_id"]): row for row in predictions}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audited: list[dict[str, Any]] = []
    for result in results:
        unit_id = str(result["unit_id"])
        prediction = prediction_map[unit_id]
        receipt_path = OUT / "receipts" / f"{unit_id}.json"
        if sha256_file(receipt_path) != prediction["receipt_sha256"]:
            raise AuditError(f"receipt hash mismatch: {unit_id}")
        receipt = load(receipt_path)
        if receipt["artificial_token_cap"] is not None:
            raise AuditError(f"token cap present: {unit_id}")
        if receipt["host_route"] != "FULL":
            raise AuditError(f"inactive route: {unit_id}")
        tools = receipt["tools"]
        if receipt["actual_tool_calls"] != len(tools):
            raise AuditError(f"tool conservation failed: {unit_id}")
        if receipt["arm"] == "FOIL" and tools:
            raise AuditError(f"tool in no-tools arm: {unit_id}")
        for tool in tools:
            if tool["tool_type"] not in {"web_search", "command_execution"}:
                raise AuditError(f"unsupported tool: {unit_id}")
            if tool["first_event_index"] > tool["last_event_index"]:
                raise AuditError(f"tool event order reversed: {unit_id}")
        expected = gold[str(result["item_id"])]
        if normalize(result["gold"]) != normalize(expected):
            raise AuditError(f"gold mismatch: {unit_id}")
        base_answer = receipt.get("base_answer")
        base_call = receipt.get("base_call")
        base_valid = bool(
            isinstance(base_answer, dict)
            and isinstance(base_call, dict)
            and base_call.get("returncode") == 0
            and base_call.get("timed_out") is False
            and not any(str(reason).startswith("base_") or str(reason).startswith("base ") for reason in receipt["invalid_reasons"])
        )
        base_text = base_answer.get("answer") if isinstance(base_answer, dict) else None
        answer = receipt.get("answer")
        final_text = answer.get("answer") if isinstance(answer, dict) else None
        final_valid = bool(receipt["valid"])
        base_correct = bool(base_valid and normalize(base_text) == normalize(expected))
        final_correct = bool(final_valid and normalize(final_text) == normalize(expected))
        if final_correct != bool(result["correct"]):
            raise AuditError(f"final score mismatch: {unit_id}")
        base_usage = usage(receipt.get("base_usage"))
        route_usage = usage(receipt.get("route_usage"))
        base_tokens = total_tokens(base_usage)
        route_tokens = total_tokens(route_usage)
        row = {
            "unit_id": unit_id,
            "config_id": str(receipt["config_id"]),
            "arm": str(receipt["arm"]),
            "base_valid": base_valid,
            "base_correct": base_correct,
            "final_valid": final_valid,
            "final_correct": final_correct,
            "rescued": bool(final_valid and not base_correct and final_correct),
            "damaged": bool(final_valid and base_correct and not final_correct),
            "withheld_correct": bool(base_correct and not final_valid),
            "answer_changed": bool(final_valid and normalize(base_text) != normalize(final_text)),
            "provider_calls": int(receipt["provider_calls"]),
            "tool_calls": len(tools),
            "web_search_calls": sum(tool["tool_type"] == "web_search" for tool in tools),
            "command_calls": sum(tool["tool_type"] == "command_execution" for tool in tools),
            "first_tool_event": None if not tools else min(tool["first_event_index"] for tool in tools),
            "last_tool_event": None if not tools else max(tool["last_event_index"] for tool in tools),
            "tool_output_characters": sum(tool["output_characters"] for tool in tools),
            "tool_statuses": [str(tool.get("status") or "UNSPECIFIED") for tool in tools],
            "command_kinds": [str(tool.get("command_kind") or "NONE") for tool in tools],
            "base_tokens": base_tokens,
            "base_input_tokens": base_usage["input_tokens"],
            "base_output_tokens": base_usage["output_tokens"],
            "route_tokens": route_tokens,
            "route_input_tokens": route_usage["input_tokens"],
            "route_output_tokens": route_usage["output_tokens"],
            "combined_tokens": base_tokens + route_tokens,
            "route_cached_input_tokens": route_usage["cached_input_tokens"],
        }
        audited.append(row)
        grouped[f"{row['config_id']}::{row['arm']}"] .append(row)
    summaries = {key: summarize(value) for key, value in sorted(grouped.items())}
    summaries["FOIL"] = summarize([row for row in audited if row["arm"] == "FOIL"])
    summaries["FOIL_TOOLS"] = summarize([row for row in audited if row["arm"] == "FOIL_TOOLS"])
    summaries["OVERALL"] = summarize(audited)
    skill_reads = private_skill_read_counts()
    report = {
        "schema": "foil.hle-active-20-independent-audit.v1",
        "classification": "POSTHOC_INDEPENDENT_RAW_ROW_AUDIT",
        "source_sha256": SOURCE_SHA256,
        "results_sha256": sha256_file(OUT / "results.json"),
        "summaries": summaries,
        "rows": audited,
        "confounds": {
            "local_skill_read_calls": sum(skill_reads.values()),
            "local_skill_read_breakdown": skill_reads,
            "effect": (
                "Tool-arm accuracy is not a pure FOIL-plus-generic-tools estimate; "
                "local skill instructions may have influenced search and computation."
            ),
            "external_or_free_bot_tool_events": 0,
        },
        "correction": (
            "The frozen scorer's base_correct summary excluded invalid final rows. "
            "This audit retains valid A0 calls, treats invalid finals as wrong, and "
            "reports correct A0s withheld by invalid final contracts separately."
        ),
        "non_claims": [
            "same-item causal tool benefit",
            "HLE population accuracy",
            "production promotion",
            "10-percent token target",
        ],
    }
    dump(OUT / "independent_audit.json", report)
    overall = summaries["OVERALL"]
    lines = [
        "# FOIL HLE active-route independent audit",
        "",
        f"Rows: {overall['n']}; provider calls: {overall['provider_calls']}; tools: {overall['tool_calls']}.",
        f"A0: {overall['base_correct']}/{overall['n']}; final: {overall['final_correct']}/{overall['n']}.",
        f"Rescues: {overall['rescues']}; published damages: {overall['published_damages']}; correct A0 withheld by invalid final: {overall['correct_a0_withheld_by_invalid_final']}.",
        f"Tokens: A0 {overall['base_tokens']}; route {overall['route_tokens']}; total {overall['combined_tokens']}.",
        f"Confound: {sum(skill_reads.values())} local skill reads ({skill_reads}); external/free bot events: 0.",
        "",
        "| Slice | A0 correct | Final correct | Rescues | Damages | Withheld | Tools | Total tokens | Mean multiplier |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in (
        "LUNA_LOW::FOIL",
        "LUNA_LOW::FOIL_TOOLS",
        "LUNA_HIGH::FOIL",
        "LUNA_HIGH::FOIL_TOOLS",
        "TERRA_HIGH::FOIL",
        "TERRA_HIGH::FOIL_TOOLS",
        "FOIL",
        "FOIL_TOOLS",
        "OVERALL",
    ):
        row = summaries[key]
        lines.append(
            f"| {key} | {row['base_correct']}/{row['n']} | {row['final_correct']}/{row['n']} | "
            f"{row['rescues']} | {row['published_damages']} | "
            f"{row['correct_a0_withheld_by_invalid_final']} | {row['tool_calls']} | "
            f"{row['combined_tokens']} | {row['mean_total_multiplier_vs_a0']:.3f}x |"
        )
    lines.extend([
        "",
        "The two arms contain disjoint questions. Arm differences are descriptive, not causal.",
        "The tool arm is local-skill-confounded and is not a pure FOIL-plus-generic-tools estimate.",
        "Invalid final rows count as wrong. A valid A0 remains in the A0 denominator.",
    ])
    (OUT / "independent_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summaries, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
