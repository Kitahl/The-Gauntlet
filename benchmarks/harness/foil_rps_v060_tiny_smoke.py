"""Frozen four-item BASE-vs-RPS Terra Low/High smoke.

Commands: prepare, self-test, check, run, score, audit.
Gold is inaccessible to model calls and is reopened only after committed predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import random
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "benchmarks" / "FOIL_RPS_V060_TINY_SMOKE.md"
POLICY = ROOT / "benchmarks" / "fixtures" / "FOIL_RPS_V060_EXPERIMENT_POLICY.md"
SKILL = ROOT / "skills" / "foil" / "SKILL.md"
EXECUTOR_PATH = ROOT / "benchmarks" / "harness" / "foil_adaptive_two_benchmark_pilot.py"
DOSE_PATH = ROOT / "benchmarks" / "harness" / "codex_dose_response_runner.py"
PRIOR_DOSE_ITEMS = ROOT / "benchmark_runs" / "2026-08-24" / "dose_items.json"

OUT = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v060_tiny_smoke"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "receipts"
ITEMS = OUT / "items.json"
MANIFEST = OUT / "manifest.json"
SCHEMA = OUT / "answer_schema.json"
LOCK = OUT / "config_lock.json"
PREDICTIONS = OUT / "predictions.json"
RESULTS = OUT / "results.json"
REPORT = OUT / "report.md"
SCORER_ROWS = OUT / "rps_scorer_rows.jsonl"

GPQA_REVISION = "56686c06f5e19865c153de0fdb11be3890014df7"
PROCESSBENCH_URL = (
    "https://huggingface.co/datasets/Qwen/ProcessBench/resolve/"
    "refs%2Fconvert%2Fparquet/default/gsm8k/0000.parquet"
)
PROCESSBENCH_SHA256 = "9896315aff77fff8fe60361f05b612250598a4bd88a70ffba567b4d580d6d4a3"
SEED = 20260825
MAX_CALLS = 18
TIMEOUT_SECONDS = 600
CONFIGS = {
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low"},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
}
ARMS = ("BASE", "RPS_060")
PRIOR_PROCESS_IDS = {"gsm8k-330", "gsm8k-36"}


class ProtocolError(RuntimeError):
    pass


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProtocolError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR = load_module("foil_adaptive_executor", EXECUTOR_PATH)
DOSE = load_module("foil_dose_source", DOSE_PATH)


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rank_key(prefix: str, identity: str) -> str:
    return sha256_text(f"{SEED}:{prefix}:{identity}")


def fetch_processbench() -> bytes:
    request = urllib.request.Request(
        PROCESSBENCH_URL, headers={"User-Agent": "FOIL-RPS-smoke/2026-08-25"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    actual = sha256_bytes(payload)
    if actual != PROCESSBENCH_SHA256:
        raise ProtocolError(f"ProcessBench digest mismatch: {actual}")
    return payload


def processbench_rows(payload: bytes) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ProtocolError("pyarrow is required for pinned ProcessBench parquet") from exc
    table = parquet.read_table(io.BytesIO(payload))
    expected = {"id", "generator", "problem", "steps", "final_answer_correct", "label"}
    if set(table.column_names) != expected or table.num_rows != 400:
        raise ProtocolError("unexpected ProcessBench schema or row count")
    rows = table.to_pylist()
    if any(set(row) != expected for row in rows):
        raise ProtocolError("ProcessBench row has unknown or missing fields")
    return rows


def shuffled_gpqa(index: int, row: dict[str, str]) -> tuple[dict[str, str], str]:
    options = [
        (DOSE.normalize_space(row["Correct Answer"]), True),
        (DOSE.normalize_space(row["Incorrect Answer 1"]), False),
        (DOSE.normalize_space(row["Incorrect Answer 2"]), False),
        (DOSE.normalize_space(row["Incorrect Answer 3"]), False),
    ]
    random.Random(SEED * 1000 + index).shuffle(options)
    letters = "ABCD"
    choices = {letters[pos]: answer for pos, (answer, _) in enumerate(options)}
    gold = letters[next(pos for pos, (_, correct) in enumerate(options) if correct)]
    return choices, gold


def select_items(gpqa_rows: list[dict[str, str]], process_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prior_gpqa = {
        str(row["id"])
        for row in read_json(PRIOR_DOSE_ITEMS).get("items", [])
    }
    gpqa = [
        pair
        for pair in DOSE.eligible_rows(gpqa_rows)
        if f"gpqa-diamond-{pair[0]:03d}" not in prior_gpqa
    ]
    gpqa.sort(key=lambda pair: rank_key("gpqa", f"gpqa-diamond-{pair[0]:03d}"))
    selected: list[dict[str, Any]] = []
    for index, row in gpqa[:2]:
        choices, _ = shuffled_gpqa(index, row)
        item = {
            "id": f"gpqa-diamond-{index:03d}",
            "benchmark": "GPQA_DIAMOND",
            "source_index": index,
            "question": DOSE.normalize_space(row["Question"]),
            "choices": choices,
        }
        item["item_sha256"] = sha256_text(canonical_json(item))
        selected.append(item)

    for stratum, clean in (("clean", True), ("error", False)):
        eligible = [
            row
            for row in process_rows
            if (int(row["label"]) == -1) is clean
            and str(row["id"]) not in PRIOR_PROCESS_IDS
            and len(str(row["problem"]))
            + sum(len(str(step)) for step in row["steps"])
            <= 3500
        ]
        eligible.sort(key=lambda row: rank_key(f"process-{stratum}", str(row["id"])))
        if not eligible:
            raise ProtocolError(f"no eligible ProcessBench {stratum} row")
        row = eligible[0]
        item = {
            "id": f"processbench-{row['id']}",
            "benchmark": "PROCESSBENCH_GSM8K",
            "source_id": str(row["id"]),
            "problem": str(row["problem"]),
            "steps": [str(step) for step in row["steps"]],
            "selection_stratum": stratum,
        }
        item["item_sha256"] = sha256_text(canonical_json(item))
        selected.append(item)
    if len(selected) != 4 or len({item["id"] for item in selected}) != 4:
        raise ProtocolError("selection did not produce four distinct items")
    return selected


TRACE_FIELDS = {
    "rps_eligible",
    "p1_kind",
    "p1_outcome",
    "p2_kind",
    "p2_outcome",
    "conflict",
    "repair_triggered",
    "answer_changed",
    "rollback_hinge",
    "tiebreak_used",
}


def answer_schema() -> dict[str, Any]:
    nullable_text = {"type": ["string", "null"], "maxLength": 80}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "answer": {"type": "string", "minLength": 1, "maxLength": 200},
            "rps_trace": {
                "type": "object",
                "properties": {
                    "rps_eligible": {"type": "boolean"},
                    "p1_kind": nullable_text,
                    "p1_outcome": {"enum": ["PASS", "FAIL", "UNCERTAIN", "N/A"]},
                    "p2_kind": nullable_text,
                    "p2_outcome": {"enum": ["PASS", "FAIL", "UNCERTAIN", "N/A"]},
                    "conflict": {"type": "boolean"},
                    "repair_triggered": {"type": "boolean"},
                    "answer_changed": {"type": "boolean"},
                    "rollback_hinge": {"type": ["integer", "null"], "minimum": 0, "maximum": 20},
                    "tiebreak_used": {"type": "boolean"},
                },
                "required": sorted(TRACE_FIELDS),
                "additionalProperties": False,
            },
        },
        "required": ["answer", "rps_trace"],
        "additionalProperties": False,
    }


def parse_answer(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != {"answer", "rps_trace"}:
        return None, "last output has unknown or missing fields"
    if not isinstance(value["answer"], str) or not 1 <= len(value["answer"]) <= 200:
        return None, "answer is not bounded non-empty text"
    trace = value["rps_trace"]
    if not isinstance(trace, dict) or set(trace) != TRACE_FIELDS:
        return None, "rps_trace has unknown or missing fields"
    bool_fields = {
        "rps_eligible", "conflict", "repair_triggered", "answer_changed", "tiebreak_used"
    }
    if any(not isinstance(trace[field], bool) for field in bool_fields):
        return None, "rps_trace boolean field has wrong type"
    for field in ("p1_kind", "p2_kind"):
        if trace[field] is not None and (
            not isinstance(trace[field], str) or len(trace[field]) > 80
        ):
            return None, f"{field} has wrong type or bound"
    for field in ("p1_outcome", "p2_outcome"):
        if trace[field] not in {"PASS", "FAIL", "UNCERTAIN", "N/A"}:
            return None, f"{field} has invalid enum"
    hinge = trace["rollback_hinge"]
    if hinge is not None and (
        not isinstance(hinge, int) or isinstance(hinge, bool) or not 0 <= hinge <= 20
    ):
        return None, "rollback_hinge has wrong type or bound"
    return value, None


def configure_executor() -> None:
    EXECUTOR.CONFIGS = CONFIGS
    EXECUTOR.SCHEMA = SCHEMA
    EXECUTOR.RECEIPTS = RECEIPTS
    EXECUTOR.PRIVATE = PRIVATE
    EXECUTOR.MAX_CALLS = MAX_CALLS
    EXECUTOR.TIMEOUT_SECONDS = TIMEOUT_SECONDS
    EXECUTOR.parse_answer = parse_answer


def common_task(item: dict[str, Any]) -> str:
    if item["benchmark"] == "GPQA_DIAMOND":
        choices = "\n".join(f"{key}. {value}" for key, value in item["choices"].items())
        return (
            "Choose the single best answer. The answer field must be exactly A, B, C, or D.\n\n"
            f"Question: {item['question']}\n\nChoices:\n{choices}"
        )
    steps = "\n".join(f"[{index}] {step}" for index, step in enumerate(item["steps"]))
    return (
        "Inspect the proposed solution. The answer field must be OK if every step is correct; "
        "otherwise it must be the zero-based integer index of the first erroneous step.\n\n"
        f"Problem: {item['problem']}\n\nProposed solution:\n{steps}"
    )


def trace_contract(arm: str) -> str:
    if arm == "BASE":
        behavior = (
            "Solve directly without FOIL or RPS. Set rps_eligible=false, p1_kind=null, "
            "p1_outcome=N/A, p2_kind=null, p2_outcome=N/A, and every trace boolean false; "
            "set rollback_hinge=null."
        )
    else:
        behavior = (
            "Follow the FOIL and RPS policy below internally. Report only the compact public "
            "control trace; do not expose private chain-of-thought. If no P2 runs, use "
            "p2_kind=null and p2_outcome=N/A."
        )
    return (
        "Closed book. Do not use tools, files, the network, other agents, or outside context. "
        "Return only the JSON object required by the response schema. " + behavior
    )


def prompt_for(item: dict[str, Any], arm: str) -> str:
    if arm == "BASE":
        return f"{trace_contract(arm)}\n\n{common_task(item)}"
    return (
        f"{trace_contract(arm)}\n\n"
        "<FOIL_SKILL>\n"
        f"{SKILL.read_text(encoding='utf-8')}\n"
        "</FOIL_SKILL>\n\n<RPS_EXPERIMENT_POLICY>\n"
        f"{POLICY.read_text(encoding='utf-8')}\n"
        "</RPS_EXPERIMENT_POLICY>\n\n"
        f"{common_task(item)}"
    )


CONTROL_PROMPT = (
    "Return only the JSON object required by the response schema. Set answer=CONTROL_OK. "
    "Set rps_eligible=false, p1_kind=null, p1_outcome=N/A, p2_kind=null, "
    "p2_outcome=N/A, conflict=false, repair_triggered=false, answer_changed=false, "
    "rollback_hinge=null, and tiebreak_used=false. Do not use tools."
)


def build_manifest(items: list[dict[str, Any]], gpqa_sha: str) -> dict[str, Any]:
    units = []
    for item in items:
        for config_id, config in CONFIGS.items():
            for arm in ARMS:
                prompt = prompt_for(item, arm)
                units.append(
                    {
                        "unit_id": f"{config_id.lower()}-{arm.lower()}-{item['id']}",
                        "item_id": item["id"],
                        "benchmark": item["benchmark"],
                        "config_id": config_id,
                        "model": config["model"],
                        "effort": config["effort"],
                        "arm": arm,
                        "prompt_sha256": sha256_text(prompt),
                    }
                )
    units.sort(key=lambda row: row["unit_id"])
    return {
        "schema": "foil.rps-v060-tiny-smoke-manifest.v1",
        "classification": "TINY_RPS_PROMPT_POLICY_SMOKE",
        "seed": SEED,
        "gpqa_revision": GPQA_REVISION,
        "gpqa_archive_sha256": gpqa_sha,
        "processbench_sha256": PROCESSBENCH_SHA256,
        "protocol_sha256": sha256_file(PROTOCOL),
        "policy_sha256": sha256_file(POLICY),
        "foil_skill_sha256": sha256_file(SKILL),
        "runner_sha256": sha256_file(Path(__file__)),
        "executor_sha256": sha256_file(EXECUTOR_PATH),
        "dose_source_sha256": sha256_file(DOSE_PATH),
        "items_sha256": sha256_text(canonical_json(items)),
        "units": units,
        "model_calls": 16,
        "control_calls": 2,
        "hard_call_cap": MAX_CALLS,
        "non_claims": [
            "calibration", "promotion", "superiority", "safety bound",
            "HLE efficacy", "frontier-model recall", "production token target",
        ],
    }


def prepare() -> None:
    if any(path.exists() for path in (ITEMS, MANIFEST, SCHEMA, LOCK, PREDICTIONS, RESULTS)):
        raise ProtocolError("prepare never overwrites an existing experiment")
    gpqa_payload = DOSE.fetch_archive()
    gpqa_sha = sha256_bytes(gpqa_payload)
    gpqa_rows = DOSE.load_rows(gpqa_payload)
    process_payload = fetch_processbench()
    items = select_items(gpqa_rows, processbench_rows(process_payload))
    write_json(ITEMS, {"schema": "foil.rps-v060-tiny-smoke-items.v1", "items": items})
    write_json(SCHEMA, answer_schema())
    write_json(MANIFEST, build_manifest(items, gpqa_sha))
    lock_files = (
        PROTOCOL, POLICY, SKILL, Path(__file__), EXECUTOR_PATH, DOSE_PATH,
        PRIOR_DOSE_ITEMS, ITEMS, SCHEMA, MANIFEST,
    )
    write_json(
        LOCK,
        {
            "schema": "foil.rps-v060-tiny-smoke-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in lock_files
            },
        },
    )
    print("prepared 4 items, 16 benchmark units, 2 controls, call cap 18")


def validate_lock() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for path in (PROTOCOL, POLICY, SKILL, ITEMS, MANIFEST, SCHEMA, LOCK):
        if not path.is_file():
            raise ProtocolError(f"missing frozen artifact: {path}")
    lock = read_json(LOCK)
    for relative, expected in lock["files"].items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise ProtocolError(f"frozen hash mismatch: {relative}: {actual}")
    manifest = read_json(MANIFEST)
    items = read_json(ITEMS)["items"]
    if manifest["runner_sha256"] != sha256_file(Path(__file__)):
        raise ProtocolError("runner changed after prepare")
    if manifest["items_sha256"] != sha256_text(canonical_json(items)):
        raise ProtocolError("items differ from manifest")
    if len(items) != 4 or len(manifest["units"]) != 16:
        raise ProtocolError("matrix conservation failed")
    by_id = {item["id"]: item for item in items}
    for unit in manifest["units"]:
        if sha256_text(prompt_for(by_id[unit["item_id"]], unit["arm"])) != unit["prompt_sha256"]:
            raise ProtocolError(f"prompt hash mismatch: {unit['unit_id']}")
    return manifest, items


def frozen_commit() -> str:
    validate_lock()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    for relative in read_json(LOCK)["files"]:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True
        )
        if tracked.returncode:
            raise ProtocolError(f"frozen artifact is not committed: {relative}")
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT)
        if dirty.returncode:
            raise ProtocolError(f"frozen artifact differs from HEAD: {relative}")
    return head


def run() -> None:
    configure_executor()
    manifest, items = validate_lock()
    head = frozen_commit()
    version = EXECUTOR.codex_version()
    for config_id in CONFIGS:
        receipt = EXECUTOR.execute_call(
            "controls", f"control-{config_id}", config_id, CONTROL_PROMPT, head, version
        )
        if receipt["answer"]["answer"] != "CONTROL_OK":
            raise ProtocolError(f"positive control failed: {config_id}")
    by_id = {item["id"]: item for item in items}
    predictions = []
    for unit in manifest["units"]:
        item = by_id[unit["item_id"]]
        prompt = prompt_for(item, unit["arm"])
        print(unit["unit_id"], flush=True)
        receipt = EXECUTOR.execute_call(
            unit["arm"].lower(), unit["unit_id"], unit["config_id"], prompt, head, version
        )
        trace = receipt["answer"]["rps_trace"]
        if unit["arm"] == "BASE" and (
            trace["rps_eligible"] or trace["p1_outcome"] != "N/A"
        ):
            raise ProtocolError(f"BASE emitted non-null RPS activity: {unit['unit_id']}")
        predictions.append(
            {
                **unit,
                "prediction": receipt["answer"],
                "receipt_sha256": sha256_file(
                    RECEIPTS / unit["arm"].lower() / f"{unit['unit_id']}.json"
                ),
            }
        )
    predictions.sort(key=lambda row: row["unit_id"])
    if len(predictions) != 16 or len({row["unit_id"] for row in predictions}) != 16:
        raise ProtocolError("prediction conservation failed")
    if EXECUTOR.call_count() != MAX_CALLS:
        raise ProtocolError(f"expected exactly {MAX_CALLS} provider calls")
    write_json(
        PREDICTIONS,
        {
            "schema": "foil.rps-v060-tiny-smoke-predictions.v1",
            "pre_call_commit": head,
            "codex_version": version,
            "provider_calls": EXECUTOR.call_count(),
            "tool_calls": 0,
            "profile_writes": 0,
            "host_answer_mutations": 0,
            "predictions": predictions,
        },
    )
    print("froze 16 predictions and 18 public receipts; commit before score")


def require_predictions_committed() -> None:
    required = [PREDICTIONS]
    required.extend(RECEIPTS.rglob("*.json"))
    for path in required:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True
        )
        if tracked.returncode:
            raise ProtocolError(f"prediction artifact is not committed: {relative}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    if status.strip():
        raise ProtocolError("working tree must be clean before scorer opens gold")


def process_answer(value: str) -> str:
    answer = str(value).strip().upper()
    if answer in {"OK", "CORRECT", "-1"}:
        return "OK"
    match = re.fullmatch(r"(?:STEP[_ ]*)?(\d+)", answer)
    return match.group(1) if match else f"INVALID:{answer}"


def gold_map(items: list[dict[str, Any]]) -> dict[str, str]:
    gpqa_payload = DOSE.fetch_archive()
    manifest = read_json(MANIFEST)
    if sha256_bytes(gpqa_payload) != manifest["gpqa_archive_sha256"]:
        raise ProtocolError("GPQA source changed after predictions froze")
    gpqa_rows = DOSE.load_rows(gpqa_payload, expected_sha256=manifest["gpqa_archive_sha256"])
    process = {str(row["id"]): row for row in processbench_rows(fetch_processbench())}
    gold: dict[str, str] = {}
    for item in items:
        if item["benchmark"] == "GPQA_DIAMOND":
            _, answer = shuffled_gpqa(int(item["source_index"]), gpqa_rows[int(item["source_index"])])
            gold[item["id"]] = answer
        else:
            label = int(process[item["source_id"]]["label"])
            gold[item["id"]] = "OK" if label == -1 else str(label)
    return gold


def usage(receipt: dict[str, Any]) -> dict[str, int]:
    raw = receipt.get("usage") or {}
    return {
        "input": int(raw.get("input_tokens", 0)),
        "cached_input": int(raw.get("cached_input_tokens", 0)),
        "output": int(raw.get("output_tokens", 0)),
    }


def ratio(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        pairs[(row["config_id"], row["item_id"])][row["arm"]] = row
    rescues = damages = both_correct = both_wrong = 0
    conflicts = conflict_on_base_wrong = repairs = repair_rescues = repair_damages = 0
    base_wrong = base_correct = 0
    token = {arm: {"input": 0, "cached_input": 0, "output": 0} for arm in ARMS}
    for pair in pairs.values():
        if set(pair) != set(ARMS):
            raise ProtocolError("incomplete pair in summary")
        base, rps = pair["BASE"], pair["RPS_060"]
        bc, rc = base["correct"], rps["correct"]
        base_correct += int(bc)
        base_wrong += int(not bc)
        both_correct += int(bc and rc)
        rescues += int((not bc) and rc)
        damages += int(bc and (not rc))
        both_wrong += int((not bc) and (not rc))
        trace = rps["prediction"]["rps_trace"]
        conflict = bool(trace["conflict"])
        repair = bool(trace["repair_triggered"])
        conflicts += int(conflict)
        conflict_on_base_wrong += int(conflict and (not bc))
        repairs += int(repair)
        repair_rescues += int(repair and (not bc) and rc)
        repair_damages += int(repair and bc and (not rc))
        for arm, current in pair.items():
            for key in token[arm]:
                token[arm][key] += current["usage"][key]
    n = len(pairs)
    for arm in ARMS:
        token[arm]["total"] = token[arm]["input"] + token[arm]["output"]
    return {
        "n_pairs": n,
        "both_correct": both_correct,
        "base_only": damages,
        "rps_only": rescues,
        "both_wrong": both_wrong,
        "base_correct": base_correct,
        "rps_correct": both_correct + rescues,
        "rescues": rescues,
        "damages": damages,
        "net_rescues": rescues - damages,
        "conflicts": conflicts,
        "conflict_precision_vs_independent_base": ratio(conflict_on_base_wrong, conflicts),
        "conflict_recall_vs_independent_base": ratio(conflict_on_base_wrong, base_wrong),
        "repairs": repairs,
        "repair_yield_vs_independent_base_wrong": ratio(repair_rescues, base_wrong),
        "damage_given_repair_vs_independent_base_correct": ratio(repair_damages, base_correct),
        "tokens": token,
        "output_token_multiplier": ratio(token["RPS_060"]["output"], token["BASE"]["output"]),
        "total_token_multiplier": ratio(token["RPS_060"]["total"], token["BASE"]["total"]),
    }


def build_results() -> dict[str, Any]:
    manifest, items = validate_lock()
    gold = gold_map(items)
    rows = []
    for prediction in read_json(PREDICTIONS)["predictions"]:
        receipt_path = RECEIPTS / prediction["arm"].lower() / f"{prediction['unit_id']}.json"
        if sha256_file(receipt_path) != prediction["receipt_sha256"]:
            raise ProtocolError(f"receipt hash mismatch: {prediction['unit_id']}")
        receipt = read_json(receipt_path)
        answer = prediction["prediction"]["answer"]
        target = gold[prediction["item_id"]]
        normalized = process_answer(answer) if prediction["benchmark"] == "PROCESSBENCH_GSM8K" else answer.strip().upper()
        rows.append(
            {
                **prediction,
                "gold": target,
                "normalized_answer": normalized,
                "correct": normalized == target,
                "usage": usage(receipt),
            }
        )
    rows.sort(key=lambda row: row["unit_id"])
    summaries: dict[str, Any] = {"OVERALL": summarize(rows)}
    for config_id in CONFIGS:
        summaries[config_id] = summarize([row for row in rows if row["config_id"] == config_id])
    for benchmark in ("GPQA_DIAMOND", "PROCESSBENCH_GSM8K"):
        summaries[benchmark] = summarize([row for row in rows if row["benchmark"] == benchmark])
    return {
        "schema": "foil.rps-v060-tiny-smoke-results.v1",
        "classification": manifest["classification"],
        "summaries": summaries,
        "rows": rows,
        "provider_calls": EXECUTOR.call_count(),
        "tool_calls": 0,
        "profile_writes": 0,
        "host_answer_mutations": 0,
        "telemetry_boundary": "RPS trace is model self-report, not independently observed hidden reasoning.",
        "non_claims": manifest["non_claims"],
    }


def write_scorer_rows(rows: list[dict[str, Any]]) -> None:
    lines = []
    for row in rows:
        lines.append(
            json.dumps(
                {
                    "benchmark": f"{row['benchmark']}::{row['config_id']}",
                    "item_id": row["item_id"],
                    "condition": row["arm"],
                    "replicate": 0,
                    "valid": True,
                    "correct": row["correct"],
                    "input_tokens": row["usage"]["input"],
                    "output_tokens": row["usage"]["output"],
                    "rps": row["prediction"]["rps_trace"],
                },
                sort_keys=True,
            )
        )
    SCORER_ROWS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def score() -> None:
    configure_executor()
    require_predictions_committed()
    result = build_results()
    if result["provider_calls"] != MAX_CALLS:
        raise ProtocolError("provider-call conservation failed")
    write_json(RESULTS, result)
    write_scorer_rows(result["rows"])
    lines = [
        "# FOIL RPS v0.6.0 Terra Low/High tiny smoke — results",
        "",
        "Classification: **TINY_RPS_PROMPT_POLICY_SMOKE**",
        "",
        "| Slice | BASE | RPS | Rescue | Damage | Conflict | Output × | Total × |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("TERRA_LOW", "TERRA_HIGH", "GPQA_DIAMOND", "PROCESSBENCH_GSM8K", "OVERALL"):
        value = result["summaries"][key]
        lines.append(
            f"| {key} | {value['base_correct']}/{value['n_pairs']} | "
            f"{value['rps_correct']}/{value['n_pairs']} | {value['rescues']} | "
            f"{value['damages']} | {value['conflicts']} | "
            f"{value['output_token_multiplier']:.3f} | {value['total_token_multiplier']:.3f} |"
        )
    lines.extend(
        [
            "",
            "The conflict/repair fields are model self-reports and are compared with an independent BASE run; they are not causal observations of RPS's private provisional answer.",
            "Four questions cannot calibrate, promote, establish safety, or estimate HLE efficacy.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(canonical_json(result["summaries"]))


def audit() -> None:
    configure_executor()
    expected = build_results()
    observed = read_json(RESULTS)
    if expected != observed:
        raise ProtocolError("independent recomputation differs from results.json")
    if len(observed["rows"]) != 16 or EXECUTOR.call_count() != MAX_CALLS:
        raise ProtocolError("row/call conservation failed")
    for row in observed["rows"]:
        receipt = read_json(RECEIPTS / row["arm"].lower() / f"{row['unit_id']}.json")
        if not receipt["valid"] or receipt["event_types"] == []:
            raise ProtocolError(f"invalid receipt: {row['unit_id']}")
    print(f"audit PASS results_sha256={sha256_file(RESULTS)} rows=16 calls={MAX_CALLS}")


def self_test() -> None:
    base = {
        "answer": "A",
        "rps_trace": {
            "rps_eligible": False, "p1_kind": None, "p1_outcome": "N/A",
            "p2_kind": None, "p2_outcome": "N/A", "conflict": False,
            "repair_triggered": False, "answer_changed": False,
            "rollback_hinge": None, "tiebreak_used": False,
        },
    }
    assert parse_answer(json.dumps(base))[1] is None
    broken = json.loads(json.dumps(base))
    broken["rps_trace"]["conflict"] = "false"
    assert parse_answer(json.dumps(broken))[1] is not None
    assert process_answer("step_3") == "3"
    assert process_answer("-1") == "OK"
    synthetic = []
    for arm, correct in (("BASE", False), ("RPS_060", True)):
        synthetic.append(
            {
                "config_id": "TERRA_LOW", "item_id": "x", "arm": arm,
                "correct": correct, "usage": {"input": 10, "cached_input": 0, "output": 5},
                "prediction": {**base, "rps_trace": {**base["rps_trace"], "conflict": arm == "RPS_060"}},
            }
        )
    summary = summarize(synthetic)
    assert summary["rescues"] == 1 and summary["damages"] == 0
    assert summary["total_token_multiplier"] == 1.0
    print("self-test PASS")


def check() -> None:
    manifest, items = validate_lock()
    print(
        canonical_json(
            {
                "items": [item["id"] for item in items],
                "units": len(manifest["units"]),
                "call_cap": manifest["hard_call_cap"],
                "policy_sha256": manifest["policy_sha256"],
                "classification": manifest["classification"],
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "self-test", "check", "run", "score", "audit"))
    args = parser.parse_args()
    configure_executor()
    if args.command == "prepare":
        prepare()
    elif args.command == "self-test":
        self_test()
    elif args.command == "check":
        check()
    elif args.command == "run":
        run()
    elif args.command == "score":
        score()
    else:
        audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
