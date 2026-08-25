"""Frozen two-item HLE-Verified Gold BASE-vs-RPS Terra Low/High challenge.

Commands: prepare, self-test, check, run, score, audit.
Gold is inaccessible to model calls and is reopened only after committed predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "benchmarks" / "FOIL_RPS_V060_HLE_HARD_TWO.md"
POLICY = ROOT / "benchmarks" / "fixtures" / "FOIL_RPS_V060_EXPERIMENT_POLICY.md"
SKILL = ROOT / "skills" / "foil" / "SKILL.md"
EXECUTOR_PATH = ROOT / "benchmarks" / "harness" / "foil_adaptive_two_benchmark_pilot.py"

OUT = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v060_hle_hard_two"
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

HLE_REVISION = "0bc83643672d4f68a5f89998617a639d85e7318b"
HLE_DATA = Path(
    os.environ.get(
        "FOIL_HLE_VERIFIED_DATA",
        r"C:\Users\tombl\Documents\Codex\benchmark-data\HLE-Verified_0bc8364",
    )
)
HLE_SHARDS = {
    "Gold_subset.part01.parquet": "0f9347730c0b9a7b690931bfe38f748d2b142be8b4b3318e16d23844b18af98b",
    "Gold_subset.part02.parquet": "9661a90148056d7d39e0fef058159e72532119aa8ee30a26f06dfa27b61d015f",
    "Gold_subset.part03.parquet": "ace18833057f09e9071be632239b255a1cd23a3a602dddd524b88e573bf427aa",
    "Gold_subset.part04.parquet": "f09e14efe051a8a5af54e5f14f0bb2231ddb4b68cbba8886afb2f0a2995e3737",
    "Gold_subset.part05.parquet": "23211a403e2c013b01dd8634ffa982b9f6dfcb6a4c126a3223c2a18913030ee2",
}
SEED = 20260825
MAX_CALLS = 10
TIMEOUT_SECONDS = 600
CONFIGS = {
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low"},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
}
ARMS = ("BASE", "RPS_060")
PRIOR_HLE_IDS = {
    "66eaa401c7a3252f0f3fe535", "66ee60c50e499ab807af71f2",
    "66f05d93454a69621ec1badc", "66fcf81e8a146dd80cfb2296",
    "66fe16f4762ab58b937863b8", "6700ab4bfa64315ed5204e4d",
    "670417b84f1cdb9711ec68d6", "670b02d5560fcdf78354fad0",
    "670db60f6f63b774df6f4daa", "670f289fb671096a201efee4",
    "670faed07ddb2771c2d214ea", "6716260eae3149088ed859b9",
    "671ab94ffad7ae30b89eff8f", "671d91bcad7fb0793a0e93bd",
    "671f53490ac3c2f49e4fa4d5", "6722728827542064f9b14815",
    "6722809eb0e7186e733d6838", "672579985c16db8f9647559c",
    "6726140e196c3daaab906acc", "6726efce60a613901f1fdf0b",
    "673029b26ad714f5469388f5", "67352e9911e5510fc618f619",
    "6736d98353926b38af8c204b", "67391de141c297471963efc6",
    "673a76559e89466aa6433f66", "67383288f2df805520bc86b5",
}


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


def hle_rows() -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ProtocolError("pyarrow is required for pinned HLE-Verified parquet") from exc
    expected = {
        "id", "Verified_Classes", "category", "raw_subject", "problem_is_valid",
        "problem_error_type", "answer_is_valid", "answer_error_type",
        "rationale_is_valid", "rationale_error_type", "question", "answer", "json",
    }
    rows: list[dict[str, Any]] = []
    for filename, expected_sha in HLE_SHARDS.items():
        path = HLE_DATA / filename
        if not path.is_file():
            raise ProtocolError(f"missing pinned HLE shard: {path}")
        actual = sha256_file(path)
        if actual != expected_sha:
            raise ProtocolError(f"HLE shard digest mismatch: {filename}: {actual}")
        table = parquet.read_table(path)
        if set(table.column_names) != expected:
            raise ProtocolError(f"unexpected HLE schema: {filename}")
        rows.extend(table.to_pylist())
    if len(rows) != 668 or len({str(row["id"]) for row in rows}) != 668:
        raise ProtocolError("HLE Gold row/id conservation failed")
    return rows


def row_payload(row: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(str(row["json"]))
    if not isinstance(value, dict) or value.get("id") != row["id"]:
        raise ProtocolError(f"malformed HLE row payload: {row['id']}")
    return value


def select_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for row in rows:
        payload = row_payload(row)
        image_fields = (
            payload.get("image"),
            payload.get("image_preview"),
            payload.get("rationale_image"),
        )
        if (
            row["Verified_Classes"] == "Gold subset"
            and row["id"] not in PRIOR_HLE_IDS
            and payload.get("answer_type") == "multipleChoice"
            and not any(image_fields)
            and len(str(row["question"])) <= 12000
        ):
            eligible.append(row)
    eligible.sort(
        key=lambda row: (
            -len(str(row["question"])),
            rank_key("HLE_HARD", str(row["id"])),
        )
    )
    if not eligible:
        raise ProtocolError("no eligible HLE Gold rows")
    chosen = [eligible[0]]
    chosen.extend(
        row for row in eligible[1:] if row["category"] != chosen[0]["category"]
    )
    chosen = chosen[:2]
    if len(chosen) != 2:
        raise ProtocolError("could not select two distinct-category HLE items")
    selected: list[dict[str, Any]] = []
    for rank, row in enumerate(chosen, start=1):
        payload = row_payload(row)
        if re.fullmatch(r"[A-Z]", str(row["answer"]).strip().upper()) is None:
            raise ProtocolError(f"selected HLE item lacks letter gold: {row['id']}")
        item = {
            "id": f"hle-verified-{row['id']}",
            "benchmark": "HLE_VERIFIED_GOLD_TEXT",
            "source_id": str(row["id"]),
            "category": str(row["category"]),
            "answer_type": str(payload["answer_type"]),
            "question": str(row["question"]),
            "selection_rank": rank,
            "question_characters": len(str(row["question"])),
            "selection_proxy": (
                "descending question character count; seeded SHA-256 tie-break; "
                "second item must differ in category"
            ),
        }
        item["item_sha256"] = sha256_text(canonical_json(item))
        selected.append(item)
    if len({item["id"] for item in selected}) != 2:
        raise ProtocolError("selection did not produce two distinct items")
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


def trace_integrity_errors(arm: str, trace: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if arm == "BASE":
        expected = {
            "rps_eligible": False,
            "p1_kind": None,
            "p1_outcome": "N/A",
            "p2_kind": None,
            "p2_outcome": "N/A",
            "conflict": False,
            "repair_triggered": False,
            "answer_changed": False,
            "rollback_hinge": None,
            "tiebreak_used": False,
        }
        if trace != expected:
            errors.append("BASE_EMITTED_RPS_ACTIVITY")
        return errors
    if not trace["rps_eligible"]:
        errors.append("RPS_NOT_MARKED_ELIGIBLE")
    if trace["p1_kind"] is None:
        errors.append("P1_KIND_MISSING")
    if trace["p1_outcome"] == "FAIL":
        if not trace["conflict"]:
            errors.append("P1_FAIL_WITHOUT_CONFLICT")
        if not trace["repair_triggered"]:
            errors.append("P1_FAIL_WITHOUT_REPAIR")
        if trace["rollback_hinge"] is None:
            errors.append("P1_FAIL_WITHOUT_HINGE")
    if trace["p1_outcome"] == "PASS" and (
        trace["conflict"]
        or trace["repair_triggered"]
        or trace["answer_changed"]
        or trace["rollback_hinge"] is not None
        or trace["p2_kind"] is not None
        or trace["p2_outcome"] != "N/A"
        or trace["tiebreak_used"]
    ):
        errors.append("P1_PASS_DID_NOT_FAST_ACCEPT")
    if trace["repair_triggered"] and not trace["conflict"]:
        errors.append("REPAIR_WITHOUT_CONFLICT")
    if trace["answer_changed"] and not trace["repair_triggered"]:
        errors.append("ANSWER_CHANGED_WITHOUT_REPAIR")
    if trace["repair_triggered"] and trace["rollback_hinge"] is None:
        errors.append("REPAIR_WITHOUT_HINGE")
    if not trace["repair_triggered"] and trace["rollback_hinge"] is not None:
        errors.append("HINGE_WITHOUT_REPAIR")
    if (trace["p2_kind"] is None) != (trace["p2_outcome"] == "N/A"):
        errors.append("P2_KIND_OUTCOME_MISMATCH")
    return sorted(set(errors))


def configure_executor() -> None:
    EXECUTOR.CONFIGS = CONFIGS
    EXECUTOR.SCHEMA = SCHEMA
    EXECUTOR.RECEIPTS = RECEIPTS
    EXECUTOR.PRIVATE = PRIVATE
    EXECUTOR.MAX_CALLS = MAX_CALLS
    EXECUTOR.TIMEOUT_SECONDS = TIMEOUT_SECONDS
    EXECUTOR.parse_answer = parse_answer


def common_task(item: dict[str, Any]) -> str:
    return (
        "Choose the single best answer. The answer field must be exactly the one "
        "capital-letter label of the selected displayed option. "
        "The choices are contained in the question.\n\n"
        f"Question:\n{item['question']}"
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


def build_manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
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
        "schema": "foil.rps-v060-hle-hard-two-manifest.v1",
        "classification": "HLE_VERIFIED_GOLD_HARD_TWO_CHALLENGE",
        "seed": SEED,
        "hle_dataset": "skylenage-ai/HLE-Verified",
        "hle_revision": HLE_REVISION,
        "hle_gold_shards_sha256": HLE_SHARDS,
        "selection_rule": (
            "Gold subset; text-only; multipleChoice; unused IDs; <=12000 characters; "
            "descending question length with seeded SHA-256 tie-break; distinct categories"
        ),
        "protocol_sha256": sha256_file(PROTOCOL),
        "policy_sha256": sha256_file(POLICY),
        "foil_skill_sha256": sha256_file(SKILL),
        "runner_sha256": sha256_file(Path(__file__)),
        "executor_sha256": sha256_file(EXECUTOR_PATH),
        "items_sha256": sha256_text(canonical_json(items)),
        "units": units,
        "model_calls": 8,
        "control_calls": 2,
        "hard_call_cap": MAX_CALLS,
        "non_claims": [
            "calibration", "promotion", "superiority", "safety bound",
            "HLE population efficacy", "frontier-model recall", "production token target",
            "per-item causal effect under a nondeterministic provider",
        ],
    }


def prepare() -> None:
    if any(path.exists() for path in (ITEMS, MANIFEST, SCHEMA, LOCK, PREDICTIONS, RESULTS)):
        raise ProtocolError("prepare never overwrites an existing experiment")
    items = select_items(hle_rows())
    write_json(ITEMS, {"schema": "foil.rps-v060-hle-hard-two-items.v1", "items": items})
    write_json(SCHEMA, answer_schema())
    write_json(MANIFEST, build_manifest(items))
    lock_files = (
        PROTOCOL, POLICY, SKILL, Path(__file__), EXECUTOR_PATH,
        ITEMS, SCHEMA, MANIFEST,
    )
    write_json(
        LOCK,
        {
            "schema": "foil.rps-v060-hle-hard-two-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in lock_files
            },
        },
    )
    print("prepared 2 HLE Gold items, 8 benchmark units, 2 controls, call cap 10")


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
    if len(items) != 2 or len(manifest["units"]) != 8:
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
        integrity_errors = trace_integrity_errors(unit["arm"], trace)
        predictions.append(
            {
                **unit,
                "prediction": receipt["answer"],
                "trace_integrity_errors": integrity_errors,
                "receipt_sha256": sha256_file(
                    RECEIPTS / unit["arm"].lower() / f"{unit['unit_id']}.json"
                ),
            }
        )
    predictions.sort(key=lambda row: row["unit_id"])
    if len(predictions) != 8 or len({row["unit_id"] for row in predictions}) != 8:
        raise ProtocolError("prediction conservation failed")
    if EXECUTOR.call_count() != MAX_CALLS:
        raise ProtocolError(f"expected exactly {MAX_CALLS} provider calls")
    write_json(
        PREDICTIONS,
        {
            "schema": "foil.rps-v060-hle-hard-two-predictions.v1",
            "pre_call_commit": head,
            "codex_version": version,
            "provider_calls": EXECUTOR.call_count(),
            "tool_calls": 0,
            "profile_writes": 0,
            "host_answer_mutations": 0,
            "predictions": predictions,
        },
    )
    print("froze 8 predictions and 10 public receipts; commit before score")


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


def gold_map(items: list[dict[str, Any]]) -> dict[str, str]:
    manifest = read_json(MANIFEST)
    if manifest["hle_revision"] != HLE_REVISION:
        raise ProtocolError("HLE revision changed after predictions froze")
    if manifest["hle_gold_shards_sha256"] != HLE_SHARDS:
        raise ProtocolError("HLE shard map changed after predictions froze")
    source = {str(row["id"]): row for row in hle_rows()}
    gold: dict[str, str] = {}
    for item in items:
        answer = str(source[item["source_id"]]["answer"]).strip().upper()
        if re.fullmatch(r"[A-Z]", answer) is None:
            raise ProtocolError(f"unexpected HLE gold format: {item['id']}")
        gold[item["id"]] = answer
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
        normalized = answer.strip().upper()
        if re.fullmatch(r"[A-Z]", normalized) is None:
            normalized = f"INVALID:{normalized}"
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
    summaries["HLE_VERIFIED_GOLD_TEXT"] = summarize(rows)
    integrity_rows = [
        {
            "unit_id": row["unit_id"],
            "errors": row["trace_integrity_errors"],
        }
        for row in rows
        if row["trace_integrity_errors"]
    ]
    return {
        "schema": "foil.rps-v060-hle-hard-two-results.v1",
        "classification": manifest["classification"],
        "summaries": summaries,
        "rows": rows,
        "trace_integrity_failures": integrity_rows,
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
        "# FOIL RPS v0.6.0 — HLE-Verified Gold hard-two challenge",
        "",
        "Classification: **HLE_VERIFIED_GOLD_HARD_TWO_CHALLENGE**",
        "",
        "| Slice | BASE | RPS | Rescue | Damage | Conflict | Output × | Total × |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("TERRA_LOW", "TERRA_HIGH", "HLE_VERIFIED_GOLD_TEXT", "OVERALL"):
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
            f"Trace-integrity failures: **{len(result['trace_integrity_failures'])}**.",
            "",
            "The conflict/repair fields are model self-reports and are compared with an independent BASE run; they are not causal observations of RPS's private provisional answer.",
            "Two questions cannot calibrate, promote, establish safety, or estimate HLE population efficacy.",
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
    if len(observed["rows"]) != 8 or EXECUTOR.call_count() != MAX_CALLS:
        raise ProtocolError("row/call conservation failed")
    for row in observed["rows"]:
        receipt = read_json(RECEIPTS / row["arm"].lower() / f"{row['unit_id']}.json")
        if not receipt["valid"] or receipt["event_types"] == []:
            raise ProtocolError(f"invalid receipt: {row['unit_id']}")
    print(f"audit PASS results_sha256={sha256_file(RESULTS)} rows=8 calls={MAX_CALLS}")


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
    assert trace_integrity_errors("BASE", base["rps_trace"]) == []
    valid_rps = {
        **base["rps_trace"],
        "rps_eligible": True,
        "p1_kind": "BOUNDARY",
        "p1_outcome": "PASS",
    }
    assert trace_integrity_errors("RPS_060", valid_rps) == []
    broken_trace = {
        **valid_rps,
        "p1_outcome": "FAIL",
        "conflict": True,
    }
    assert "P1_FAIL_WITHOUT_REPAIR" in trace_integrity_errors("RPS_060", broken_trace)
    assert "P1_FAIL_WITHOUT_HINGE" in trace_integrity_errors("RPS_060", broken_trace)
    synthetic = []
    for arm, correct in (("BASE", False), ("RPS_060", True)):
        synthetic.append(
            {
                "config_id": "TERRA_LOW", "item_id": "x", "arm": arm,
                "correct": correct, "usage": {"input": 10, "cached_input": 0, "output": 5},
                "prediction": {**base, "rps_trace": valid_rps if arm == "RPS_060" else base["rps_trace"]},
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
