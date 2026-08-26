"""Independent raw-row audit for the RPS v0.6.3 active replay report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from foil_certified_arithmetic import (  # noqa: E402
    CERTIFIED_LANGUAGE,
    POWER_LANGUAGE,
    extract_steps,
)


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: object) -> str:
    return digest_bytes(canonical(value).encode("utf-8"))


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def correct(answer: dict[str, object], gold: str) -> bool:
    return answer["abstain"] is False and answer["answer"] == gold


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    items_doc = load(args.items)
    results_doc = load(args.results)
    report = load(args.report)
    expected_hashes = {
        "items_sha256": digest_bytes(args.items.read_bytes()),
        "results_sha256": digest_bytes(args.results.read_bytes()),
    }
    if report["source_hashes"] != expected_hashes:
        raise ValueError("source hash mismatch")
    claimed_report_hash = report["report_sha256"]
    unhashed = dict(report)
    unhashed.pop("report_sha256")
    if claimed_report_hash != digest_json(unhashed):
        raise ValueError("report hash mismatch")

    items = {row["id"]: row for row in items_doc["items"]}
    raw_rows = {
        row["unit_id"]: row
        for row in results_doc["rows"]
        if row["benchmark"] == "PROCESSBENCH_GSM8K"
    }
    if len(raw_rows) != len(report["rows"]):
        raise ValueError("row count mismatch")
    rescues = damages = active_correct = base_correct = previous_correct = 0
    stage1_resolved = stage2_not_run = mutations = 0
    for row in report["rows"]:
        raw = raw_rows[row["unit_id"]]
        item = items[row["item_id"]]
        if row["base"] != raw["base"] or row["gold"] != raw["gold"]:
            raise ValueError(f"raw binding mismatch: {row['unit_id']}")
        findings = [
            finding
            for language in (CERTIFIED_LANGUAGE, POWER_LANGUAGE)
            for finding in extract_steps(item["steps"], language=language)
            if finding.violating
        ]
        earliest = min((finding.step_index for finding in findings), default=None)
        expected = None if earliest is None else str(earliest)
        if row["stage1_expected_answer"] != expected:
            raise ValueError(f"expected-answer mismatch: {row['unit_id']}")
        base = raw["base"]
        if expected is None:
            action = "REQUEST_BLIND_RIVAL"
            final = base
            expected_stage2 = True
        elif base["abstain"] is False and base["answer"].strip() == expected:
            action = "KEEP_BASE"
            final = base
            expected_stage2 = False
        else:
            action = "SELECT_HOST_RESULT"
            final = {"answer": expected, "abstain": False}
            expected_stage2 = False
        if row["decision"]["action"] != action or row["active_final"] != final:
            raise ValueError(f"decision mismatch: {row['unit_id']}")
        if row["stage2_not_run"] is not expected_stage2:
            raise ValueError(f"Stage-2 count mismatch: {row['unit_id']}")
        base_ok = correct(base, raw["gold"])
        previous_ok = correct(raw["final"], raw["gold"])
        active_ok = correct(final, raw["gold"])
        if row["base_correct"] is not base_ok:
            raise ValueError(f"base score mismatch: {row['unit_id']}")
        if row["previous_final_correct"] is not previous_ok:
            raise ValueError(f"previous score mismatch: {row['unit_id']}")
        if row["active_final_correct"] is not active_ok:
            raise ValueError(f"active score mismatch: {row['unit_id']}")
        base_correct += int(base_ok)
        previous_correct += int(previous_ok)
        active_correct += int(active_ok)
        rescues += int(not base_ok and active_ok)
        damages += int(base_ok and not active_ok)
        stage1_resolved += int(expected is not None)
        stage2_not_run += int(expected_stage2)
        mutations += int(action == "SELECT_HOST_RESULT")
    recomputed = {
        "rows": len(raw_rows),
        "questions": len({row["item_id"] for row in report["rows"]}),
        "configs": len({row["config_id"] for row in report["rows"]}),
        "base_correct": base_correct,
        "previous_final_correct": previous_correct,
        "active_final_correct": active_correct,
        "rescues": rescues,
        "damages": damages,
        "answer_mutations": mutations,
        "stage1_resolved": stage1_resolved,
        "stage2_not_run": stage2_not_run,
        "provider_calls": 0,
        "added_input_tokens": 0,
        "added_output_tokens": 0,
        "total_token_multiplier": 1.0,
    }
    if report["summary"] != recomputed:
        raise ValueError("summary mismatch")
    print(f"verified_rows={len(raw_rows)}")
    print(f"base_correct={base_correct}")
    print(f"active_final_correct={active_correct}")
    print(f"rescues={rescues}")
    print(f"damages={damages}")
    print(f"report_sha256={claimed_report_hash}")


if __name__ == "__main__":
    main()
