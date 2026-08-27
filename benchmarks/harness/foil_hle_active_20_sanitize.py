#!/usr/bin/env python3
"""Sanitize public HLE receipts without modifying ignored private raw events."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-26" / "hle_active_20"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ""


def command_kind(value: str) -> str:
    lowered = value.casefold()
    if not value:
        return "NONE"
    if "skill.md" in lowered:
        return "LOCAL_SKILL_READ"
    if "python" in lowered:
        return "PYTHON_COMPUTE"
    if "rg " in lowered or "get-content" in lowered:
        return "LOCAL_READ"
    return "SHELL_COMPUTE"


def sanitize_tool(tool: dict[str, Any]) -> dict[str, Any]:
    result = dict(tool)
    raw = command_text(result.pop("command", ""))
    result["command_kind"] = command_kind(raw)
    result["command_characters"] = len(raw)
    result["command_sha256"] = sha_text(raw)
    if result.get("tool_type") != "web_search":
        result["action"] = {}
    return result


def main() -> int:
    receipt_paths = sorted((OUT / "receipts").glob("*.json"))
    if len(receipt_paths) != 60:
        raise RuntimeError("expected exactly 60 receipts")
    original_hashes: dict[str, str] = {}
    for path in receipt_paths:
        receipt = load(path)
        original_hashes[str(receipt["unit_id"])] = sha_file(path)
        receipt["tools"] = [sanitize_tool(dict(tool)) for tool in receipt["tools"]]
        receipt["public_sanitization"] = {
            "schema": "foil.public-tool-sanitization.v1",
            "performed_post_score": True,
            "raw_command_retained_publicly": False,
            "raw_private_events_retained_locally": True,
            "original_receipt_sha256": original_hashes[str(receipt["unit_id"])],
        }
        dump(path, receipt)
    predictions_path = OUT / "predictions.json"
    predictions = load(predictions_path)
    for row in predictions["predictions"]:
        unit_id = str(row["unit_id"])
        row["original_receipt_sha256"] = original_hashes[unit_id]
        row["receipt_sha256"] = sha_file(OUT / "receipts" / f"{unit_id}.json")
    predictions["public_sanitization"] = {
        "schema": "foil.public-tool-sanitization.v1",
        "performed_post_score": True,
        "pre_score_prediction_commit": "102b80e",
    }
    dump(predictions_path, predictions)
    results_path = OUT / "results.json"
    results = load(results_path)
    for row in results["rows"]:
        unit_id = str(row["unit_id"])
        receipt = load(OUT / "receipts" / f"{unit_id}.json")
        row["tools"] = receipt["tools"]
        row["tool_sequence"] = receipt["tool_sequence"]
        row["receipt_sha256"] = sha_file(OUT / "receipts" / f"{unit_id}.json")
    results["public_sanitization"] = {
        "schema": "foil.public-tool-sanitization.v1",
        "performed_post_score": True,
        "metrics_changed": False,
    }
    dump(results_path, results)
    print(f"sanitized receipts={len(receipt_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
