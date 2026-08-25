"""Frozen two-benchmark BASE-vs-executed-adaptive FOIL smoke pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from egrt_types import digest  # noqa: E402
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus  # noqa: E402
from foil_adaptive_route import (  # noqa: E402
    AdaptiveRoutePolicy,
    FrozenEVModel,
    RiskClass,
    Route,
    decide_shadow_route,
    host_verifier_routes,
)
from foil_certified_arithmetic import CERTIFIED_LANGUAGE, extract_steps  # noqa: E402
from foil_obligation_compiler import (  # noqa: E402
    COMPILER_VERSION,
    TASK_SPEC_SCHEMA,
    compile_task_spec,
)

PROTOCOL = ROOT / "benchmarks" / "FOIL_ADAPTIVE_TWO_BENCHMARK_SMALL_PILOT.md"
SKILL = ROOT / "skills" / "foil" / "SKILL.md"
OUT = ROOT / "benchmark_runs" / "2026-08-25" / "adaptive_two_benchmark"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "receipts"
ITEMS = OUT / "items.json"
MANIFEST = OUT / "manifest.json"
SCHEMA = OUT / "answer_schema.json"
LOCK = OUT / "config_lock.json"
PREDICTIONS = OUT / "predictions.json"
RESULTS = OUT / "results.json"
REPORT = OUT / "report.md"

SIMPLEQA_URL = (
    "https://openaipublic.blob.core.windows.net/simple-evals/"
    "simple_qa_test_set.csv"
)
PROCESSBENCH_GSM8K_SHA256 = (
    "9896315aff77fff8fe60361f05b612250598a4bd88a70ffba567b4d580d6d4a3"
)
SEED = 20260825
TIMEOUT_SECONDS = 600
MAX_CALLS = 21
CONFIGS: dict[str, dict[str, str]] = {
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low"},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
    "SOL_LOW": {"model": "gpt-5.6-sol", "effort": "low"},
}


class ProtocolError(RuntimeError):
    pass


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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_simpleqa() -> bytes:
    request = urllib.request.Request(
        SIMPLEQA_URL, headers={"User-Agent": "FOIL-adaptive-smoke/2026-08-25"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def simpleqa_rows(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    if not rows or not {"problem", "answer"}.issubset(rows[0]):
        raise ProtocolError(f"unexpected SimpleQA fields: {list(rows[0]) if rows else []}")
    if not all(row.get("problem", "").strip() and row.get("answer", "").strip() for row in rows):
        raise ProtocolError("SimpleQA contains an empty problem or answer")
    return rows


def load_processbench(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or sha256_file(path) != PROCESSBENCH_GSM8K_SHA256:
        raise ProtocolError("ProcessBench GSM8K parquet is absent or has the wrong digest")
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ProtocolError("pyarrow is required for ProcessBench") from exc
    table = parquet.read_table(path)
    expected = {"id", "generator", "problem", "steps", "final_answer_correct", "label"}
    if set(table.column_names) != expected or table.num_rows != 400:
        raise ProtocolError("unexpected ProcessBench GSM8K schema or row count")
    rows = table.to_pylist()
    if any(set(row) != expected for row in rows):
        raise ProtocolError("ProcessBench row has unknown or missing fields")
    return rows


def rank_key(prefix: str, identity: str) -> str:
    return sha256_text(f"{SEED}:{prefix}:{identity}")


def select_items(process_rows: list[dict[str, Any]], simple_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for stratum, clean in (("clean", True), ("error", False)):
        eligible = [
            row
            for row in process_rows
            if (int(row["label"]) == -1) is clean
            and len(str(row["problem"])) + sum(len(str(step)) for step in row["steps"]) <= 3500
            and (
                clean
                or any(
                    finding.violating
                    for finding in extract_steps(row["steps"], language=CERTIFIED_LANGUAGE)
                )
            )
        ]
        eligible.sort(key=lambda row: rank_key(stratum, str(row["id"])))
        if not eligible:
            raise ProtocolError(f"no eligible ProcessBench {stratum} rows")
        row = eligible[0]
        item = {
            "id": f"processbench-{row['id']}",
            "benchmark": "PROCESSBENCH_GSM8K",
            "problem": str(row["problem"]),
            "steps": [str(step) for step in row["steps"]],
            "selection_stratum": stratum,
            "route_positive_sentinel": not clean,
        }
        item["item_sha256"] = digest(item)
        selected.append(item)

    eligible_simple = [
        (index, row)
        for index, row in enumerate(simple_rows)
        if len(row["problem"].strip()) <= 260
    ]
    eligible_simple.sort(key=lambda pair: rank_key("simpleqa", pair[1]["problem"].strip()))
    for index, row in eligible_simple[:2]:
        item = {
            "id": f"simpleqa-{index:04d}",
            "benchmark": "SIMPLEQA_NO_BROWSE",
            "problem": row["problem"].strip(),
        }
        item["item_sha256"] = digest(item)
        selected.append(item)
    if len(selected) != 4:
        raise ProtocolError("selection did not yield exactly four items")
    return selected


def answer_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "answer": {"type": "string", "minLength": 1, "maxLength": 200},
            "abstain": {"type": "boolean"},
        },
        "required": ["answer", "abstain"],
        "additionalProperties": False,
    }


def item_prompt(item: dict[str, Any]) -> str:
    boundary = (
        "Closed book. Do not use tools, files, the network, or outside context. "
        "Return only the JSON object required by the response schema."
    )
    if item["benchmark"] == "PROCESSBENCH_GSM8K":
        steps = "\n".join(f"[{index}] {step}" for index, step in enumerate(item["steps"]))
        return (
            "Inspect the proposed solution. Return answer=OK if every step is correct; "
            "otherwise return the zero-based integer index of the first erroneous step. "
            "Set abstain=false unless the text is genuinely insufficient.\n\n"
            f"Problem:\n{item['problem']}\n\nProposed solution:\n{steps}\n\n{boundary}"
        )
    return (
        "Answer the factual question as briefly as possible. Set abstain=true only if you "
        "cannot responsibly supply an answer.\n\n"
        f"Question:\n{item['problem']}\n\n{boundary}"
    )


def full_prompt(item: dict[str, Any], a0: dict[str, Any]) -> str:
    return (
        "/foil solve\n\n"
        "Review the frozen A0 below using the frozen public FOIL skill contract. The host "
        "has routed this unit to FULL after a deterministic check; do not assume that A0 "
        "is wrong, and do not change a correct answer without sufficient reason. No profile "
        "is available. Return the final answer in the response schema.\n\n"
        "<foil_skill_contract>\n"
        f"{SKILL.read_text(encoding='utf-8').rstrip()}\n"
        "</foil_skill_contract>\n\n"
        f"<frozen_a0>{json.dumps(a0, ensure_ascii=False, sort_keys=True)}</frozen_a0>\n\n"
        f"{item_prompt(item)}"
    )


CONTROL_PROMPT = (
    "Positive control. Return answer=A and abstain=false. Do not use tools, files, the "
    "network, or outside context. Return only the required JSON object."
)


def pilot_ev() -> FrozenEVModel:
    return FrozenEVModel(
        base_correct_ppm=500_000,
        verify_rescue_ppm=0,
        verify_damage_ppm=0,
        full_rescue_ppm=800_000,
        full_damage_ppm=50_000,
        rescue_utility_micro=1_000_000,
        damage_disutility_micro=1_000_000,
        cost_penalty_micro_per_unit=10_000,
        verify_incremental_cost_units=0,
        full_incremental_cost_units=1,
        evidence_digest=sha256_text("uncalibrated benchmark-only EV v1"),
    )


def route_item(item: dict[str, Any], a0: dict[str, Any], config_id: str) -> dict[str, Any]:
    if item["benchmark"] != "PROCESSBENCH_GSM8K":
        return {"route": "DIRECT", "reason": "NO_HOST_DECLARED_DECIDABLE_OBLIGATION", "trace": None}
    findings = extract_steps(item["steps"], language=CERTIFIED_LANGUAGE)
    if not findings:
        return {"route": "DIRECT", "reason": "NO_CERTIFIED_EQUALITY", "trace": None}
    claims: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        claims.append(
            {
                "claim_key": f"source-equality-{index}",
                "statement_digest": sha256_text(finding.source_span),
                "claim_kind": "EXACT_MATCH",
                "decidability": "DETERMINISTIC",
                "applicability": "APPLICABLE",
                "reason": "Benchmark host declared a certified fully numeric source equality.",
                "obligations": [
                    {
                        "obligation_key": f"numeric-equality-{index}",
                        "description": "Canonical rational values on both sides must match.",
                        "weight_range": {"start": 1, "end": 1},
                        "predicate_kind": "EXACT_MATCH",
                        "verifier_id": "builtin.exact_match",
                        "verifier_version": "1",
                        "verifier_input": {
                            "actual": str(finding.left_value),
                            "expected": str(finding.right_value),
                        },
                    }
                ],
            }
        )
    spec = {
        "schema": TASK_SPEC_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "task_digest": sha256_text(canonical_json(item)),
        "a0_digest": sha256_text(canonical_json(a0)),
        "config_digest": sha256_text(config_id),
        "claims": claims,
    }
    compiled = compile_task_spec(spec, observed_a0_digest=spec["a0_digest"])
    routes = host_verifier_routes(compiled)
    failed: list[tuple[Any, Any]] = []
    for route in routes:
        case = compiled.deterministic_cases(route.claim_id)[0]
        result = DEFAULT_REGISTRY.run(route.verifier_id, case.verifier_input)
        if result.status is VerificationStatus.FAIL:
            failed.append((route, result))
    if not failed:
        decision = decide_shadow_route(
            bindings=compiled.bindings,
            risk=RiskClass.NONE,
            policy=AdaptiveRoutePolicy(enabled=True),
        )
    else:
        route, result = failed[0]
        decision = decide_shadow_route(
            bindings=compiled.bindings,
            risk=RiskClass.VERIFIED_DEFECT,
            policy=AdaptiveRoutePolicy(enabled=True),
            ev=pilot_ev(),
            compiled_spec=compiled,
            obligation_ids=(route.obligation_id,),
            verifier_routes=(route,),
            verification=result,
            remaining_cost_units=1,
        )
    return {
        "route": decision.route.value,
        "reason": decision.reason.value,
        "checkable_equalities": len(findings),
        "failed_equalities": len(failed),
        "trace": decision.trace(),
    }


def build_manifest(items: list[dict[str, Any]], simpleqa_sha256: str) -> dict[str, Any]:
    units = [
        {"unit_id": f"{item['id']}-{config_id}", "item_id": item["id"], "config_id": config_id}
        for item in items
        for config_id in CONFIGS
    ]
    random.Random(SEED).shuffle(units)
    return {
        "schema": "foil.adaptive-two-benchmark-manifest.v1",
        "created_at": now(),
        "seed": SEED,
        "configs": CONFIGS,
        "simpleqa_url": SIMPLEQA_URL,
        "simpleqa_sha256": simpleqa_sha256,
        "processbench_gsm8k_sha256": PROCESSBENCH_GSM8K_SHA256,
        "skill_sha256": sha256_file(SKILL),
        "protocol_sha256": sha256_file(PROTOCOL),
        "runner_sha256": sha256_file(Path(__file__)),
        "items_sha256": sha256_text(canonical_json(items)),
        "base_units": units,
        "base_calls": 12,
        "maximum_full_calls": 6,
        "control_calls": 3,
        "hard_call_cap": MAX_CALLS,
        "classification": "TINY_EXECUTED_ADAPTIVE_SMOKE",
        "non_claims": [
            "calibration",
            "promotion",
            "10-percent production overhead",
            "superiority",
            "natural route frequency",
            "scanner recall",
        ],
    }


def prepare(processbench_data: Path) -> None:
    if any(path.exists() for path in (ITEMS, MANIFEST, SCHEMA, LOCK, PREDICTIONS, RESULTS)):
        raise ProtocolError("prepare never overwrites an existing experiment")
    simple_payload = fetch_simpleqa()
    items = select_items(
        load_processbench(processbench_data / "gsm8k.parquet"),
        simpleqa_rows(simple_payload),
    )
    write_json(ITEMS, {"schema": "foil.adaptive-two-benchmark-items.v1", "items": items})
    write_json(SCHEMA, answer_schema())
    manifest = build_manifest(items, sha256_bytes(simple_payload))
    write_json(MANIFEST, manifest)
    lock_files = (PROTOCOL, Path(__file__), SKILL, ITEMS, SCHEMA, MANIFEST)
    write_json(
        LOCK,
        {
            "schema": "foil.adaptive-two-benchmark-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in lock_files
            },
        },
    )
    print(f"prepared 4 items, 12 BASE units, at most 6 FULL units; call cap {MAX_CALLS}")


def validate_lock() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for path in (PROTOCOL, SKILL, ITEMS, MANIFEST, SCHEMA, LOCK):
        if not path.is_file():
            raise ProtocolError(f"missing frozen artifact: {path}")
    lock = read_json(LOCK)
    for relative, expected in lock["files"].items():
        if sha256_file(ROOT / relative) != expected:
            raise ProtocolError(f"frozen hash mismatch: {relative}")
    manifest = read_json(MANIFEST)
    items = read_json(ITEMS)["items"]
    if manifest["runner_sha256"] != sha256_file(Path(__file__)):
        raise ProtocolError("runner changed after preparation")
    if manifest["protocol_sha256"] != sha256_file(PROTOCOL):
        raise ProtocolError("protocol changed after preparation")
    if manifest["skill_sha256"] != sha256_file(SKILL):
        raise ProtocolError("FOIL skill changed after preparation")
    if manifest["items_sha256"] != sha256_text(canonical_json(items)):
        raise ProtocolError("items changed after preparation")
    if len(items) != 4 or len(manifest["base_units"]) != 12:
        raise ProtocolError("matrix size invariant failed")
    return manifest, items


def codex_executable() -> str:
    if sys.platform == "win32":
        shim = shutil.which("codex.cmd")
        if shim:
            package_root = Path(shim).resolve().parent / "node_modules" / "@openai" / "codex" / "node_modules" / "@openai"
            packaged = sorted(package_root.glob("codex-win32-*/vendor/*/bin/codex.exe"))
            if len(packaged) == 1:
                return str(packaged[0])
        native = shutil.which("codex.exe")
        if native:
            return native
    executable = shutil.which("codex")
    if not executable:
        raise ProtocolError("native Codex executable is unavailable")
    return executable


def codex_version() -> str:
    result = subprocess.run([codex_executable(), "--version"], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ProtocolError(f"codex --version failed: {result.stderr.strip()}")
    return result.stdout.strip()


def build_argv(model: str, effort: str, workdir: Path, last: Path) -> list[str]:
    return [
        codex_executable(), "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
        "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
        "--ignore-rules", "--output-schema", str(SCHEMA), "--json", "-o", str(last),
        "-C", str(workdir), "-",
    ]


ALLOWED_STREAM = {
    "thread.started": {""}, "turn.started": {""},
    "item.started": {"reasoning", "agent_message"},
    "item.updated": {"reasoning", "agent_message"},
    "item.completed": {"reasoning", "agent_message"},
    "turn.completed": {""},
}


def parse_stream(text: str) -> dict[str, Any]:
    types: list[str] = []
    tools: list[str] = []
    usage: dict[str, int] = defaultdict(int)
    errors = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if not isinstance(event, dict):
            tools.append("non-object")
            continue
        event_type = str(event.get("type", "unknown"))
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type", ""))
        types.append(f"{event_type}:{item_type}" if item_type else event_type)
        if event_type not in ALLOWED_STREAM or item_type not in ALLOWED_STREAM[event_type]:
            tools.append(f"{event_type}:{item_type or '<none>'}")
        candidate = event.get("usage") if isinstance(event.get("usage"), dict) else item.get("usage")
        if isinstance(candidate, dict):
            for key, value in candidate.items():
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    usage[str(key)] += value
    if not types and not errors:
        tools.append("empty-stream")
    return {"event_types": sorted(set(types)), "tool_events": tools, "usage": dict(usage), "parse_errors": errors}


def parse_answer(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != {"answer", "abstain"}:
        return None, "last output has unknown or missing fields"
    if not isinstance(value["answer"], str) or not 1 <= len(value["answer"]) <= 200:
        return None, "answer is not bounded non-empty text"
    if not isinstance(value["abstain"], bool):
        return None, "abstain is not boolean"
    return value, None


def call_count() -> int:
    return len(list(RECEIPTS.rglob("*.json")))


def execute_call(kind: str, call_id: str, config_id: str, prompt: str, frozen_commit: str, cli_version: str) -> dict[str, Any]:
    config = CONFIGS[config_id]
    receipt_path = RECEIPTS / kind / f"{call_id}.json"
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt.get("valid") is not True or receipt.get("prompt_sha256") != sha256_text(prompt):
            raise ProtocolError(f"invalid or mismatched existing receipt: {call_id}")
        return receipt
    if call_count() >= MAX_CALLS:
        raise ProtocolError("hard model-call cap reached")
    raw = PRIVATE / kind / call_id
    if raw.exists():
        raise ProtocolError(f"orphaned attempt prohibits retry: {call_id}")
    raw.mkdir(parents=True)
    last = raw / "last.json"
    started = now()
    clock = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="foil-adaptive-smoke-") as temporary:
        try:
            process = subprocess.run(
                build_argv(config["model"], config["effort"], Path(temporary), last),
                input=prompt, capture_output=True, text=True, encoding="utf-8",
                timeout=TIMEOUT_SECONDS, check=False,
            )
            returncode, stdout, stderr, timed_out = process.returncode, process.stdout, process.stderr, False
        except subprocess.TimeoutExpired as exc:
            returncode = None
            stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            timed_out = True
    (raw / "events.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
    (raw / "stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
    last_text = last.read_text(encoding="utf-8") if last.exists() else ""
    stream = parse_stream(stdout)
    answer, answer_error = parse_answer(last_text)
    invalid: list[str] = []
    if timed_out:
        invalid.append("timeout")
    if returncode != 0:
        invalid.append(f"returncode={returncode}")
    if stream["parse_errors"]:
        invalid.append(f"parse_errors={stream['parse_errors']}")
    if stream["tool_events"]:
        invalid.append(f"tool_events={stream['tool_events']}")
    if answer_error:
        invalid.append(answer_error)
    receipt = {
        "schema": "foil.adaptive-two-benchmark-receipt.v1",
        "kind": kind,
        "call_id": call_id,
        "config_id": config_id,
        "model": config["model"],
        "effort": config["effort"],
        "codex_version": cli_version,
        "pre_call_commit": frozen_commit,
        "started_at": started,
        "finished_at": now(),
        "wall_seconds": time.monotonic() - clock,
        "returncode": returncode,
        "timed_out": timed_out,
        "prompt_sha256": sha256_text(prompt),
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "last_output_sha256": sha256_text(last_text),
        "event_types": stream["event_types"],
        "usage": stream["usage"],
        "answer": answer,
        "valid": not invalid,
        "invalid_reasons": invalid,
    }
    write_json(receipt_path, receipt)
    if invalid:
        raise ProtocolError(f"call failed without retry: {call_id}: {invalid}")
    return receipt


def frozen_commit() -> str:
    validate_lock()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    for path in (PROTOCOL, Path(__file__), SKILL, ITEMS, MANIFEST, SCHEMA, LOCK):
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True, text=True)
        if tracked.returncode:
            raise ProtocolError(f"frozen artifact is not committed: {relative}")
        diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT)
        if diff.returncode:
            raise ProtocolError(f"frozen artifact differs from HEAD: {relative}")
    return head


def run() -> None:
    manifest, items = validate_lock()
    head = frozen_commit()
    version = codex_version()
    for config_id in CONFIGS:
        control = execute_call("controls", f"control-{config_id}", config_id, CONTROL_PROMPT, head, version)
        if control["answer"] != {"answer": "A", "abstain": False}:
            raise ProtocolError(f"positive control failed: {config_id}")
    by_id = {item["id"]: item for item in items}
    predictions: list[dict[str, Any]] = []
    for unit in manifest["base_units"]:
        item = by_id[unit["item_id"]]
        config_id = unit["config_id"]
        call_id = unit["unit_id"]
        print(f"BASE {call_id}", flush=True)
        base = execute_call("base", call_id, config_id, item_prompt(item), head, version)
        a0 = base["answer"]
        route = route_item(item, a0, config_id)
        full = None
        final = a0
        if route["route"] == Route.FULL.value:
            print(f"FULL {call_id}", flush=True)
            full = execute_call("full", call_id, config_id, full_prompt(item, a0), head, version)
            final = full["answer"]
        elif route["route"] != Route.DIRECT.value:
            raise ProtocolError(f"unsupported executable route: {route['route']}")
        predictions.append(
            {
                "unit_id": call_id,
                "item_id": item["id"],
                "benchmark": item["benchmark"],
                "config_id": config_id,
                "base": a0,
                "route": route,
                "full": None if full is None else full["answer"],
                "final": final,
                "base_receipt_sha256": sha256_file(RECEIPTS / "base" / f"{call_id}.json"),
                "full_receipt_sha256": None if full is None else sha256_file(RECEIPTS / "full" / f"{call_id}.json"),
            }
        )
    predictions.sort(key=lambda row: row["unit_id"])
    if len(predictions) != 12 or len({row["unit_id"] for row in predictions}) != 12:
        raise ProtocolError("prediction conservation failed")
    for row in predictions:
        if row["route"]["route"] == "DIRECT" and (row["full"] is not None or row["final"] != row["base"]):
            raise ProtocolError("DIRECT did not preserve A0")
    write_json(
        PREDICTIONS,
        {
            "schema": "foil.adaptive-two-benchmark-predictions.v1",
            "pre_call_commit": head,
            "codex_version": version,
            "provider_calls": call_count(),
            "tool_calls": 0,
            "profile_writes": 0,
            "answer_mutations": 0,
            "predictions": predictions,
        },
    )
    print(f"frozen 12 predictions; provider calls={call_count()}; commit receipts and predictions before score")


def normalize_text(value: str) -> str:
    value = value.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in value.split() if token not in {"a", "an", "the"})


def process_prediction(value: dict[str, Any]) -> str:
    answer = str(value["answer"]).strip().upper()
    if answer in {"OK", "CORRECT", "-1"}:
        return "OK"
    match = re.fullmatch(r"(?:STEP[_ ]*)?(\d+)", answer)
    return match.group(1) if match else f"INVALID:{answer}"


def sum_usage(receipt: dict[str, Any]) -> tuple[int, int]:
    usage = receipt["usage"]
    return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


def require_predictions_committed() -> None:
    relative = str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True)
    if tracked.returncode:
        raise ProtocolError("predictions are not committed")
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    if status.strip():
        raise ProtocolError("working tree must be clean before scorer opens gold")


def score(processbench_data: Path) -> None:
    require_predictions_committed()
    manifest, items = validate_lock()
    simple_payload = fetch_simpleqa()
    if sha256_bytes(simple_payload) != manifest["simpleqa_sha256"]:
        raise ProtocolError("SimpleQA source changed after predictions froze")
    simple_rows = simpleqa_rows(simple_payload)
    process_rows = {str(row["id"]): row for row in load_processbench(processbench_data / "gsm8k.parquet")}
    gold: dict[str, str] = {}
    for item in items:
        if item["benchmark"] == "PROCESSBENCH_GSM8K":
            source_id = item["id"].removeprefix("processbench-")
            label = int(process_rows[source_id]["label"])
            gold[item["id"]] = "OK" if label == -1 else str(label)
        else:
            index = int(item["id"].split("-")[1])
            gold[item["id"]] = simple_rows[index]["answer"].strip()
    rows: list[dict[str, Any]] = []
    for prediction in read_json(PREDICTIONS)["predictions"]:
        item_id = prediction["item_id"]
        benchmark = prediction["benchmark"]
        if benchmark == "PROCESSBENCH_GSM8K":
            base_value = process_prediction(prediction["base"])
            final_value = process_prediction(prediction["final"])
            target = gold[item_id]
            base_correct, final_correct = base_value == target, final_value == target
        else:
            target = normalize_text(gold[item_id])
            base_correct = not prediction["base"]["abstain"] and normalize_text(prediction["base"]["answer"]) == target
            final_correct = not prediction["final"]["abstain"] and normalize_text(prediction["final"]["answer"]) == target
        base_receipt = read_json(RECEIPTS / "base" / f"{prediction['unit_id']}.json")
        base_in, base_out = sum_usage(base_receipt)
        full_in = full_out = 0
        if prediction["full"] is not None:
            full_receipt = read_json(RECEIPTS / "full" / f"{prediction['unit_id']}.json")
            full_in, full_out = sum_usage(full_receipt)
        rows.append(
            {
                **prediction,
                "gold": gold[item_id],
                "base_correct": base_correct,
                "final_correct": final_correct,
                "rescued": (not base_correct) and final_correct,
                "damaged": base_correct and (not final_correct),
                "base_input_tokens": base_in,
                "base_output_tokens": base_out,
                "full_input_tokens": full_in,
                "full_output_tokens": full_out,
            }
        )
    summaries: dict[str, Any] = {}
    for key, subset in [("OVERALL", rows)] + [(config, [row for row in rows if row["config_id"] == config]) for config in CONFIGS]:
        base_tokens = sum(row["base_input_tokens"] + row["base_output_tokens"] for row in subset)
        extra_tokens = sum(row["full_input_tokens"] + row["full_output_tokens"] for row in subset)
        summaries[key] = {
            "n": len(subset),
            "base_correct": sum(row["base_correct"] for row in subset),
            "adaptive_correct": sum(row["final_correct"] for row in subset),
            "rescued": sum(row["rescued"] for row in subset),
            "damaged": sum(row["damaged"] for row in subset),
            "direct": sum(row["route"]["route"] == "DIRECT" for row in subset),
            "full": sum(row["route"]["route"] == "FULL" for row in subset),
            "base_tokens": base_tokens,
            "incremental_full_tokens": extra_tokens,
            "adaptive_total_tokens": base_tokens + extra_tokens,
            "incremental_overhead_fraction": None if not base_tokens else extra_tokens / base_tokens,
            "base_abstentions": sum(row["base"]["abstain"] for row in subset),
            "adaptive_abstentions": sum(row["final"]["abstain"] for row in subset),
        }
    results = {
        "schema": "foil.adaptive-two-benchmark-results.v1",
        "classification": "TINY_EXECUTED_ADAPTIVE_SMOKE",
        "summaries": summaries,
        "rows": rows,
        "provider_calls": call_count(),
        "tool_calls": 0,
        "profile_writes": 0,
        "production_activation_changed": False,
        "non_claims": manifest["non_claims"],
    }
    write_json(RESULTS, results)
    overall = summaries["OVERALL"]
    lines = [
        "# FOIL adaptive-compute two-benchmark small pilot — results",
        "",
        "Classification: **TINY_EXECUTED_ADAPTIVE_SMOKE**",
        "",
        "| Configuration | BASE | Adaptive | Rescue | Damage | DIRECT | FULL | Token overhead |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for config in CONFIGS:
        value = summaries[config]
        lines.append(
            f"| {config} | {value['base_correct']}/{value['n']} | {value['adaptive_correct']}/{value['n']} | "
            f"{value['rescued']} | {value['damaged']} | {value['direct']} | {value['full']} | "
            f"{100 * value['incremental_overhead_fraction']:.1f}% |"
        )
    lines.extend(
        [
            f"| **Overall** | **{overall['base_correct']}/{overall['n']}** | **{overall['adaptive_correct']}/{overall['n']}** | "
            f"**{overall['rescued']}** | **{overall['damaged']}** | **{overall['direct']}** | **{overall['full']}** | "
            f"**{100 * overall['incremental_overhead_fraction']:.1f}%** |",
            "",
            "Strict SimpleQA normalized exact match is not the official model-graded score. Four questions cannot calibrate or promote the route.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(canonical_json(summaries))


def self_test() -> None:
    good = {"id": "x", "benchmark": "PROCESSBENCH_GSM8K", "problem": "x", "steps": ["$2+2=4$"], "item_sha256": "x"}
    bad = {**good, "steps": ["$2+2=5$"]}
    a0 = {"answer": "OK", "abstain": False}
    direct = route_item(good, a0, "TERRA_LOW")
    full = route_item(bad, a0, "TERRA_LOW")
    assert direct["route"] == "DIRECT" and direct["failed_equalities"] == 0
    assert full["route"] == "FULL" and full["failed_equalities"] == 1
    assert normalize_text("The Eiffel-Tower") == "eiffeltower"
    assert process_prediction({"answer": "step_3", "abstain": False}) == "3"
    assert parse_answer('{"answer":"A","abstain":false}')[1] is None
    assert parse_stream('{"type":"item.completed","item":{"type":"tool_call"}}')["tool_events"]
    print("self-test PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "check", "self-test", "run", "score"))
    parser.add_argument("--processbench-data", type=Path)
    args = parser.parse_args()
    if args.command in {"prepare", "score"} and args.processbench_data is None:
        parser.error("--processbench-data is required")
    if args.command == "prepare":
        prepare(args.processbench_data)
    elif args.command == "check":
        validate_lock()
        print("check PASS")
    elif args.command == "self-test":
        self_test()
    elif args.command == "run":
        run()
    else:
        score(args.processbench_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
