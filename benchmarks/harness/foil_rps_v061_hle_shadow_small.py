"""Sealed tiny replay benchmark for the RPS v0.6.1 decisive-hinge gate.

Commands: prepare, self-test, check, run, score, audit.
Gold is present only in the frozen v0.6.0 result and is not opened until score,
after v0.6.1 observations and receipts have been committed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_policy import RuntimePolicyV2, TaskContext  # noqa: E402
from foil_rps import (  # noqa: E402
    CheckKind,
    ParityObservation,
    RPSRecommendation,
    RPSShadowPolicy,
    ReasoningCapsule,
    evaluate_rps_shadow,
)


PROTOCOL = ROOT / "benchmarks" / "FOIL_RPS_V061_HLE_SHADOW_SMALL.md"
POLICY_060 = ROOT / "benchmarks" / "fixtures" / "FOIL_RPS_V060_EXPERIMENT_POLICY.md"
POLICY_061 = ROOT / "benchmarks" / "fixtures" / "FOIL_RPS_V061_HINGE_COVERAGE_POLICY.md"
RPS_MODULE = ROOT / "tools" / "foil_rps.py"
RUNTIME_POLICY = ROOT / "tools" / "foil_policy.py"
EXECUTOR_PATH = ROOT / "benchmarks" / "harness" / "foil_adaptive_two_benchmark_pilot.py"

SOURCE = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v060_hle_hard_two"
SOURCE_ITEMS = SOURCE / "items.json"
SOURCE_PREDICTIONS = SOURCE / "predictions.json"
SOURCE_RESULTS = SOURCE / "results.json"
SOURCE_SHA256 = {
    "items.json": "c58c3e48685479d2eb02573c5069c19cda3ea4c7814e0b35fa49fbd15fbf6e07",
    "predictions.json": "40fcb503bb780fd6062f2d07001108bc1713676af435bd0130f581a0a398187f",
    "results.json": "8de490bcd399ba149204d40bf48981c256a19d44d51a38819c96be4906096b10",
}

OUT = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v061_hle_shadow_small"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "receipts"
ITEMS = OUT / "items.json"
MANIFEST = OUT / "manifest.json"
SCHEMA = OUT / "answer_schema.json"
LOCK = OUT / "config_lock.json"
PREDICTIONS = OUT / "predictions.json"
RESULTS = OUT / "results.json"
REPORT = OUT / "report.md"

CONFIGS = {
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low"},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
}
MAX_CALLS = 6
TIMEOUT_SECONDS = 600
VALUE_ENUM = {"HOLDS", "FAILS"}
CHECK_FIELDS = {
    "kind",
    "hinge_index",
    "applicable",
    "candidate_prediction",
    "challenger_prediction",
    "observed",
}
ANSWER_FIELDS = {"challenger", "hinges", "fragile_hinge", "p1", "p2"}


class ProtocolError(RuntimeError):
    pass


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProtocolError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR = load_module("foil_rps_v061_executor", EXECUTOR_PATH)


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


def assert_sources() -> None:
    for name, expected in SOURCE_SHA256.items():
        path = SOURCE / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"frozen v0.6.0 source mismatch: {name}")


def answer_schema() -> dict[str, Any]:
    check = {
        "type": "object",
        "properties": {
            "kind": {"enum": [kind.value for kind in CheckKind]},
            "hinge_index": {"type": "integer", "minimum": 0, "maximum": 2},
            "applicable": {"type": "boolean"},
            "candidate_prediction": {"enum": ["HOLDS", "FAILS", None]},
            "challenger_prediction": {"enum": ["HOLDS", "FAILS", None]},
            "observed": {"enum": ["HOLDS", "FAILS", None]},
        },
        "required": sorted(CHECK_FIELDS),
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "challenger": {"type": "string", "pattern": "^[A-Z]$"},
            "hinges": {
                "type": "array",
                "items": {"type": "string", "minLength": 1, "maxLength": 80},
                "minItems": 1,
                "maxItems": 3,
                "uniqueItems": True,
            },
            "fragile_hinge": {"type": "integer", "minimum": 0, "maximum": 2},
            "p1": check,
            "p2": {"anyOf": [check, {"type": "null"}]},
        },
        "required": sorted(ANSWER_FIELDS),
        "additionalProperties": False,
    }


def _valid_check(value: Any) -> str | None:
    if not isinstance(value, dict) or set(value) != CHECK_FIELDS:
        return "check has unknown or missing fields"
    try:
        CheckKind(value["kind"])
    except (TypeError, ValueError):
        return "check kind is invalid"
    hinge = value["hinge_index"]
    if isinstance(hinge, bool) or not isinstance(hinge, int) or not 0 <= hinge <= 2:
        return "check hinge_index is invalid"
    if not isinstance(value["applicable"], bool):
        return "check applicable is not boolean"
    predictions = (
        value["candidate_prediction"],
        value["challenger_prediction"],
        value["observed"],
    )
    if any(item is not None and item not in VALUE_ENUM for item in predictions):
        return "check prediction has invalid enum"
    if not value["applicable"] and any(item is not None for item in predictions):
        return "inapplicable check carries an outcome"
    if value["applicable"] and value["candidate_prediction"] is None:
        return "applicable check lacks candidate prediction"
    return None


def parse_answer(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != ANSWER_FIELDS:
        return None, "last output has unknown or missing fields"
    if not isinstance(value["challenger"], str) or re.fullmatch(r"[A-Z]", value["challenger"]) is None:
        return None, "challenger is not one option label"
    hinges = value["hinges"]
    if (
        not isinstance(hinges, list)
        or not 1 <= len(hinges) <= 3
        or len(set(hinges)) != len(hinges)
        or any(not isinstance(item, str) or not 1 <= len(item) <= 80 for item in hinges)
    ):
        return None, "hinges are invalid"
    fragile = value["fragile_hinge"]
    if isinstance(fragile, bool) or not isinstance(fragile, int) or not 0 <= fragile < len(hinges):
        return None, "fragile_hinge is outside hinges"
    error = _valid_check(value["p1"])
    if error:
        return None, f"p1: {error}"
    if value["p2"] is not None:
        error = _valid_check(value["p2"])
        if error:
            return None, f"p2: {error}"
    for label in ("p1", "p2"):
        check = value[label]
        if check is not None and check["hinge_index"] >= len(hinges):
            return None, f"{label}: hinge_index is outside hinges"
    return value, None


def configure_executor() -> None:
    EXECUTOR.CONFIGS = CONFIGS
    EXECUTOR.SCHEMA = SCHEMA
    EXECUTOR.RECEIPTS = RECEIPTS
    EXECUTOR.PRIVATE = PRIVATE
    EXECUTOR.MAX_CALLS = MAX_CALLS
    EXECUTOR.TIMEOUT_SECONDS = TIMEOUT_SECONDS
    EXECUTOR.parse_answer = parse_answer


def observer_prompt(item: dict[str, Any], candidate: str) -> str:
    return (
        "You are an observation-only Residual Parity Search monitor. Do not solve by "
        "writing a second full solution. Do not use tools, files, the network, other "
        "agents, or outside context. Never assume the frozen candidate is wrong. Gold "
        "and correctness labels are unavailable. Return only the required JSON.\n\n"
        "Choose one plausible incompatible option as challenger. Name one to three "
        "compact public hinge identifiers, not private chain-of-thought, and mark the "
        "fragile hinge. Run one claim-native P1 check. For the candidate and challenger, "
        "record whether the checked property predicts HOLDS or FAILS, then record the "
        "observed result. Predictions may differ only when the check really distinguishes "
        "the candidates. If the check is inapplicable, all three outcomes must be null. "
        "Use P2 only when P1 is uncertain, inapplicable, or non-discriminating; P2 must "
        "use a different check kind. Do not report a final answer or repair.\n\n"
        "<RPS_V060_CORE>\n"
        f"{POLICY_060.read_text(encoding='utf-8').rstrip()}\n"
        "</RPS_V060_CORE>\n\n<RPS_V061_GATE>\n"
        f"{POLICY_061.read_text(encoding='utf-8').rstrip()}\n"
        "</RPS_V061_GATE>\n\n"
        f"Frozen candidate: {candidate}\n\nQuestion:\n{item['question']}"
    )


CONTROL_PROMPT = (
    "Positive control. Return challenger=B, hinges=[\"control\"], fragile_hinge=0, "
    "p1 with kind=EXACT_RELATION, hinge_index=0, applicable=true, "
    "candidate_prediction=HOLDS, challenger_prediction=FAILS, observed=HOLDS, "
    "and p2=null. Return only the required JSON and use no tools."
)


def source_units() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assert_sources()
    items = read_json(SOURCE_ITEMS)["items"]
    by_id = {item["id"]: item for item in items}
    units = []
    for row in read_json(SOURCE_PREDICTIONS)["predictions"]:
        if row["arm"] != "BASE" or row["config_id"] not in CONFIGS:
            continue
        candidate = str(row["prediction"]["answer"]).strip().upper()
        if re.fullmatch(r"[A-Z]", candidate) is None:
            raise ProtocolError(f"invalid frozen BASE candidate: {row['unit_id']}")
        item = by_id[row["item_id"]]
        unit = {
            "unit_id": f"{row['config_id'].lower()}-{row['item_id']}",
            "item_id": row["item_id"],
            "config_id": row["config_id"],
            "model": CONFIGS[row["config_id"]]["model"],
            "effort": CONFIGS[row["config_id"]]["effort"],
            "candidate": candidate,
            "source_base_unit_id": row["unit_id"],
            "source_base_receipt_sha256": row["receipt_sha256"],
            "prompt_sha256": sha256_text(observer_prompt(item, candidate)),
        }
        units.append(unit)
    units.sort(key=lambda row: row["unit_id"])
    if len(units) != 4 or len({row["unit_id"] for row in units}) != 4:
        raise ProtocolError("expected four distinct frozen BASE units")
    return items, units


def build_manifest(items: list[dict[str, Any]], units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "foil.rps-v061-hle-shadow-small-manifest.v1",
        "classification": "TINY_HISTORICAL_BASE_SHADOW_GATE_SMOKE",
        "source_sha256": SOURCE_SHA256,
        "protocol_sha256": sha256_file(PROTOCOL),
        "policy_060_sha256": sha256_file(POLICY_060),
        "policy_061_sha256": sha256_file(POLICY_061),
        "rps_module_sha256": sha256_file(RPS_MODULE),
        "runtime_policy_sha256": sha256_file(RUNTIME_POLICY),
        "runner_sha256": sha256_file(Path(__file__)),
        "executor_sha256": sha256_file(EXECUTOR_PATH),
        "items_sha256": sha256_text(canonical_json(items)),
        "units": units,
        "observer_calls": 4,
        "control_calls": 2,
        "hard_call_cap": MAX_CALLS,
        "non_claims": [
            "calibration",
            "promotion",
            "safety bound",
            "HLE population efficacy",
            "frontier-model recall",
            "semantic hinge fidelity",
            "production token target",
        ],
    }


def prepare() -> None:
    if any(path.exists() for path in (ITEMS, MANIFEST, SCHEMA, LOCK, PREDICTIONS, RESULTS)):
        raise ProtocolError("prepare never overwrites an existing experiment")
    items, units = source_units()
    write_json(ITEMS, {"schema": "foil.rps-v061-hle-shadow-small-items.v1", "items": items})
    write_json(SCHEMA, answer_schema())
    write_json(MANIFEST, build_manifest(items, units))
    lock_files = (
        PROTOCOL,
        POLICY_060,
        POLICY_061,
        RPS_MODULE,
        RUNTIME_POLICY,
        Path(__file__),
        EXECUTOR_PATH,
        SOURCE_ITEMS,
        SOURCE_PREDICTIONS,
        SOURCE_RESULTS,
        ITEMS,
        SCHEMA,
        MANIFEST,
    )
    write_json(
        LOCK,
        {
            "schema": "foil.rps-v061-hle-shadow-small-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in lock_files
            },
        },
    )
    print("prepared 2 HLE items, 4 frozen BASE replays, 2 controls; call cap 6")


def validate_lock() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required = (
        PROTOCOL,
        POLICY_060,
        POLICY_061,
        RPS_MODULE,
        RUNTIME_POLICY,
        ITEMS,
        MANIFEST,
        SCHEMA,
        LOCK,
    )
    for path in required:
        if not path.is_file():
            raise ProtocolError(f"missing frozen artifact: {path}")
    lock = read_json(LOCK)
    for relative, expected in lock["files"].items():
        if sha256_file(ROOT / relative) != expected:
            raise ProtocolError(f"frozen hash mismatch: {relative}")
    manifest = read_json(MANIFEST)
    items = read_json(ITEMS)["items"]
    if manifest["items_sha256"] != sha256_text(canonical_json(items)):
        raise ProtocolError("item digest mismatch")
    by_id = {item["id"]: item for item in items}
    if len(items) != 2 or len(manifest["units"]) != 4:
        raise ProtocolError("matrix conservation failed")
    for unit in manifest["units"]:
        prompt = observer_prompt(by_id[unit["item_id"]], unit["candidate"])
        if sha256_text(prompt) != unit["prompt_sha256"]:
            raise ProtocolError(f"prompt hash mismatch: {unit['unit_id']}")
    return manifest, items


def frozen_commit() -> str:
    validate_lock()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    for relative in read_json(LOCK)["files"]:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=ROOT,
            capture_output=True,
        )
        if tracked.returncode:
            raise ProtocolError(f"frozen artifact is not committed: {relative}")
        dirty = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT
        )
        if dirty.returncode:
            raise ProtocolError(f"frozen artifact differs from HEAD: {relative}")
    return head


def _digest_value(value: str | None) -> str | None:
    return None if value is None else sha256_text(value)


def _observation(
    unit_id: str, label: str, value: dict[str, Any]
) -> ParityObservation:
    if not value["applicable"]:
        candidate = challenger = observed = None
    else:
        candidate = _digest_value(value["candidate_prediction"])
        challenger = _digest_value(value["challenger_prediction"])
        observed = _digest_value(value["observed"])
    return ParityObservation(
        check_id=f"{unit_id}-{label}",
        kind=CheckKind(value["kind"]),
        hinge_index=value["hinge_index"],
        candidate_expected_digest=candidate,
        challenger_expected_digest=challenger,
        observed_digest=observed,
        applicable=value["applicable"],
    )


def evaluate_observer(
    unit: dict[str, Any], answer: dict[str, Any]
) -> dict[str, Any]:
    if answer["challenger"] == unit["candidate"]:
        raise ProtocolError(f"challenger duplicates candidate: {unit['unit_id']}")
    capsule = ReasoningCapsule(
        candidate_digest=sha256_text(unit["candidate"]),
        hinge_digests=tuple(sha256_text(value) for value in answer["hinges"]),
        fragile_hinge=answer["fragile_hinge"],
        answer_form_digest=sha256_text("single displayed option label"),
    )
    primary = _observation(unit["unit_id"], "p1", answer["p1"])
    secondary = (
        None
        if answer["p2"] is None
        else _observation(unit["unit_id"], "p2", answer["p2"])
    )
    policy = RuntimePolicyV2(rps_shadow_enabled=True)
    runtime = policy.decide(
        TaskContext(
            closed_book=True,
            technical_reasoning=True,
            has_viable_candidate=True,
        )
    )
    return policy.observe_residual_parity(
        runtime, capsule, primary, secondary=secondary
    ).trace()


def expected_control() -> dict[str, Any]:
    return {
        "challenger": "B",
        "hinges": ["control"],
        "fragile_hinge": 0,
        "p1": {
            "kind": "EXACT_RELATION",
            "hinge_index": 0,
            "applicable": True,
            "candidate_prediction": "HOLDS",
            "challenger_prediction": "FAILS",
            "observed": "HOLDS",
        },
        "p2": None,
    }


def run() -> None:
    configure_executor()
    if PREDICTIONS.exists():
        raise ProtocolError("run never overwrites frozen predictions")
    manifest, items = validate_lock()
    head = frozen_commit()
    version = EXECUTOR.codex_version()
    for config_id in CONFIGS:
        receipt = EXECUTOR.execute_call(
            "controls",
            f"control-{config_id}",
            config_id,
            CONTROL_PROMPT,
            head,
            version,
        )
        if receipt["answer"] != expected_control():
            raise ProtocolError(f"positive control failed: {config_id}")
    by_id = {item["id"]: item for item in items}
    predictions = []
    for unit in manifest["units"]:
        print(unit["unit_id"], flush=True)
        receipt = EXECUTOR.execute_call(
            "observer",
            unit["unit_id"],
            unit["config_id"],
            observer_prompt(by_id[unit["item_id"]], unit["candidate"]),
            head,
            version,
        )
        answer = receipt["answer"]
        decision = evaluate_observer(unit, answer)
        receipt_path = RECEIPTS / "observer" / f"{unit['unit_id']}.json"
        predictions.append(
            {
                **unit,
                "observer": answer,
                "decision": decision,
                "final_answer": unit["candidate"],
                "answer_mutated": False,
                "receipt_sha256": sha256_file(receipt_path),
            }
        )
    predictions.sort(key=lambda row: row["unit_id"])
    if len(predictions) != 4 or EXECUTOR.call_count() != MAX_CALLS:
        raise ProtocolError("prediction or provider-call conservation failed")
    if any(
        row["final_answer"] != row["candidate"] or row["answer_mutated"]
        for row in predictions
    ):
        raise ProtocolError("shadow replay changed a frozen BASE answer")
    write_json(
        PREDICTIONS,
        {
            "schema": "foil.rps-v061-hle-shadow-small-predictions.v1",
            "pre_call_commit": head,
            "codex_version": version,
            "provider_calls": EXECUTOR.call_count(),
            "tool_calls": 0,
            "profile_writes": 0,
            "answer_mutations": 0,
            "predictions": predictions,
        },
    )
    print("froze 4 shadow predictions and 6 receipts; commit before score")


def require_predictions_committed() -> None:
    required = [PREDICTIONS, *RECEIPTS.rglob("*.json")]
    for path in required:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=ROOT,
            capture_output=True,
        )
        if tracked.returncode:
            raise ProtocolError(f"prediction artifact is not committed: {relative}")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if status.strip():
        raise ProtocolError("working tree must be clean before scorer opens gold")


def usage(receipt: dict[str, Any]) -> dict[str, int]:
    raw = receipt.get("usage") or {}
    return {
        "input": int(raw.get("input_tokens", 0)),
        "cached_input": int(raw.get("cached_input_tokens", 0)),
        "output": int(raw.get("output_tokens", 0)),
    }


def structural_microbenchmark() -> list[dict[str, Any]]:
    capsule = ReasoningCapsule(
        sha256_text("candidate"),
        (sha256_text("support"), sha256_text("fragile")),
        1,
        sha256_text("label"),
    )

    def check(
        kind: CheckKind,
        hinge: int,
        candidate: str,
        challenger: str | None,
        observed: str | None,
    ) -> ParityObservation:
        return ParityObservation(
            "micro",
            kind,
            hinge,
            sha256_text(candidate),
            _digest_value(challenger),
            _digest_value(observed),
        )

    cases = [
        (
            "non-discriminating-pass",
            check(CheckKind.INVARIANT, 1, "H", "H", "H"),
            None,
            RPSRecommendation.RUN_P2,
        ),
        (
            "decisive-pass",
            check(CheckKind.PAIRWISE_DISCRIMINATOR, 1, "H", "F", "H"),
            None,
            RPSRecommendation.FAST_ACCEPT,
        ),
        (
            "decisive-fail",
            check(CheckKind.PAIRWISE_DISCRIMINATOR, 1, "H", "F", "F"),
            None,
            RPSRecommendation.LOCAL_REPAIR,
        ),
        (
            "wrong-hinge-pass",
            check(CheckKind.PAIRWISE_DISCRIMINATOR, 0, "H", "F", "H"),
            None,
            RPSRecommendation.RUN_P2,
        ),
        (
            "orthogonal-p2",
            check(CheckKind.INVARIANT, 1, "H", "H", "H"),
            check(CheckKind.COUNTEREXAMPLE, 1, "H", "F", "H"),
            RPSRecommendation.FAST_ACCEPT,
        ),
        (
            "repeated-p2",
            check(CheckKind.INVARIANT, 1, "H", "H", "H"),
            check(CheckKind.INVARIANT, 1, "H", "F", "H"),
            RPSRecommendation.ABSTAIN,
        ),
    ]
    rows = []
    for name, p1, p2, expected in cases:
        actual = evaluate_rps_shadow(
            capsule,
            p1,
            policy=RPSShadowPolicy(enabled=True),
            secondary=p2,
        ).recommendation
        rows.append(
            {
                "case": name,
                "expected": expected.value,
                "actual": actual.value,
                "pass": actual is expected,
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wrong = [row for row in rows if not row["base_correct"]]
    correct = [row for row in rows if row["base_correct"]]
    observer = {"input": 0, "cached_input": 0, "output": 0}
    base = {"input": 0, "cached_input": 0, "output": 0}
    for row in rows:
        for key in observer:
            observer[key] += row["observer_usage"][key]
            base[key] += row["base_usage"][key]
    observer["total"] = observer["input"] + observer["output"]
    base["total"] = base["input"] + base["output"]
    multiplier = (
        None
        if base["total"] == 0
        else (base["total"] + observer["total"]) / base["total"]
    )
    return {
        "n": len(rows),
        "base_correct": len(correct),
        "unsafe_fast_accepts_on_wrong": sum(
            row["recommendation"] == "FAST_ACCEPT" for row in wrong
        ),
        "wrong_not_fast_accepted": sum(
            row["recommendation"] != "FAST_ACCEPT" for row in wrong
        ),
        "correct_fast_accepts": sum(
            row["recommendation"] == "FAST_ACCEPT" for row in correct
        ),
        "false_local_repairs_on_correct": sum(
            row["recommendation"] == "LOCAL_REPAIR" for row in correct
        ),
        "run_p2": sum(row["recommendation"] == "RUN_P2" for row in rows),
        "abstain": sum(row["recommendation"] == "ABSTAIN" for row in rows),
        "local_repair": sum(
            row["recommendation"] == "LOCAL_REPAIR" for row in rows
        ),
        "fast_accept": sum(
            row["recommendation"] == "FAST_ACCEPT" for row in rows
        ),
        "base_tokens": base,
        "observer_tokens": observer,
        "base_plus_observer_token_multiplier": multiplier,
    }


def build_results() -> dict[str, Any]:
    manifest, _items = validate_lock()
    source_rows = {
        (row["config_id"], row["item_id"]): row
        for row in read_json(SOURCE_RESULTS)["rows"]
        if row["arm"] == "BASE"
    }
    rows = []
    for prediction in read_json(PREDICTIONS)["predictions"]:
        key = (prediction["config_id"], prediction["item_id"])
        if key not in source_rows:
            raise ProtocolError(f"missing frozen BASE score: {key}")
        source = source_rows[key]
        receipt_path = RECEIPTS / "observer" / f"{prediction['unit_id']}.json"
        if sha256_file(receipt_path) != prediction["receipt_sha256"]:
            raise ProtocolError(f"observer receipt mismatch: {prediction['unit_id']}")
        rows.append(
            {
                "unit_id": prediction["unit_id"],
                "item_id": prediction["item_id"],
                "config_id": prediction["config_id"],
                "model": prediction["model"],
                "effort": prediction["effort"],
                "candidate": prediction["candidate"],
                "gold": source["gold"],
                "base_correct": bool(source["correct"]),
                "recommendation": prediction["decision"]["recommendation"],
                "decision": prediction["decision"],
                "observer": prediction["observer"],
                "base_usage": source["usage"],
                "observer_usage": usage(read_json(receipt_path)),
                "final_answer": prediction["candidate"],
                "answer_mutated": False,
            }
        )
    rows.sort(key=lambda row: row["unit_id"])
    structural = structural_microbenchmark()
    return {
        "schema": "foil.rps-v061-hle-shadow-small-results.v1",
        "classification": manifest["classification"],
        "structural_microbenchmark": {
            "passed": sum(row["pass"] for row in structural),
            "total": len(structural),
            "rows": structural,
        },
        "summaries": {
            "OVERALL": summarize(rows),
            **{
                config_id: summarize(
                    [row for row in rows if row["config_id"] == config_id]
                )
                for config_id in CONFIGS
            },
        },
        "rows": rows,
        "provider_calls": read_json(PREDICTIONS)["provider_calls"],
        "tool_calls": 0,
        "profile_writes": 0,
        "answer_mutations": 0,
        "telemetry_boundary": (
            "Hinges and check outcomes are model-authored structured self-report; "
            "the host independently enforces only the transition law."
        ),
        "non_claims": manifest["non_claims"],
    }


def score() -> None:
    configure_executor()
    require_predictions_committed()
    result = build_results()
    write_json(RESULTS, result)
    lines = [
        "# FOIL RPS v0.6.1 — small shadow benchmark",
        "",
        (
            f"Structural gate: **{result['structural_microbenchmark']['passed']}/"
            f"{result['structural_microbenchmark']['total']}**."
        ),
        "",
        "| Slice | BASE correct | Unsafe accept / wrong | Wrong protected | Correct fast accept | False repair / correct | P2 | Abstain | Total × |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("TERRA_LOW", "TERRA_HIGH", "OVERALL"):
        value = result["summaries"][key]
        multiplier = value["base_plus_observer_token_multiplier"]
        lines.append(
            f"| {key} | {value['base_correct']}/{value['n']} | "
            f"{value['unsafe_fast_accepts_on_wrong']} | "
            f"{value['wrong_not_fast_accepted']} | "
            f"{value['correct_fast_accepts']} | "
            f"{value['false_local_repairs_on_correct']} | "
            f"{value['run_p2']} | {value['abstain']} | {multiplier:.3f} |"
        )
    lines.extend(
        [
            "",
            "All final answers are the frozen BASE answers; shadow RPS made zero mutations.",
            "The four rows are a smoke test, not calibration or promotion evidence.",
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
    if len(observed["rows"]) != 4 or observed["provider_calls"] != MAX_CALLS:
        raise ProtocolError("row or provider-call conservation failed")
    if observed["structural_microbenchmark"]["passed"] != 6:
        raise ProtocolError("structural microbenchmark failed")
    if any(
        row["answer_mutated"] or row["final_answer"] != row["candidate"]
        for row in observed["rows"]
    ):
        raise ProtocolError("shadow answer-identity invariant failed")
    for path in RECEIPTS.rglob("*.json"):
        receipt = read_json(path)
        if not receipt["valid"] or receipt["tool_events"]:
            raise ProtocolError(f"invalid provider receipt: {path.name}")
    print(
        f"audit PASS results_sha256={sha256_file(RESULTS)} "
        f"rows=4 calls={MAX_CALLS}"
    )


def self_test() -> None:
    value = expected_control()
    assert parse_answer(json.dumps(value))[1] is None
    broken = dict(value)
    broken["gold"] = "A"
    assert parse_answer(json.dumps(broken))[1] is not None
    assert all(row["pass"] for row in structural_microbenchmark())
    print("self-test PASS structural=6/6")


def check() -> None:
    manifest, items = validate_lock()
    print(
        canonical_json(
            {
                "items": [item["id"] for item in items],
                "units": len(manifest["units"]),
                "call_cap": manifest["hard_call_cap"],
                "classification": manifest["classification"],
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("prepare", "self-test", "check", "run", "score", "audit")
    )
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
