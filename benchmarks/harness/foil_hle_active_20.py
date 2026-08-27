#!/usr/bin/env python3
"""Run the preregistered 20-item active FOIL HLE tool-use pilot.

Commands: prepare, self-test, check, run, score, audit.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foil_policy import (  # noqa: E402
    ClaimKind,
    LoadBearingUncertainty,
    RuntimePolicyV2,
    TaskContext,
)
from egrt_types import digest  # noqa: E402
from foil_adaptive_executor import (  # noqa: E402
    BenchmarkExecutionPolicy,
    RouteWorkResult,
    execute_benchmark_route,
)
from foil_adaptive_route import (  # noqa: E402
    DecisionReason,
    Route,
    ShadowRouteDecision,
)


PROTOCOL = ROOT / "benchmarks" / "FOIL_HLE_ACTIVE_20_PROTOCOL.md"
SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_hle_active_answer_schema.json"
BASE_SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_hle_base_answer_schema.json"
FOIL_SKILL = ROOT / "skills" / "foil" / "SKILL.md"
POLICY_SOURCE = ROOT / "tools" / "foil_policy.py"
ADAPTIVE_SOURCE = ROOT / "tools" / "foil_adaptive_route.py"
ACTIVE_EXECUTOR = ROOT / "tools" / "foil_adaptive_executor.py"
OUT = ROOT / "benchmark_runs" / "2026-08-26" / "hle_active_20"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "receipts"
ITEMS = OUT / "items.json"
MANIFEST = OUT / "manifest.json"
LOCK = OUT / "config_lock.json"
PREDICTIONS = OUT / "predictions.json"
RESULTS = OUT / "results.json"
REPORT = OUT / "report.md"

SOURCE_URL = (
    "https://raw.githubusercontent.com/ustc-ai4science/Science-Star/"
    "4abe1db2d6d0920aa0a6236ee2f81de872adafa5/"
    "data/HLE/subset/hle_subset_50.jsonl"
)
SOURCE_SHA256 = "7e6deb84eafffaea128823ae53f9d7ee9ebfa7aaf77ff465f5d7df595606a361"
SEED = 20260826
ARMS = ("FOIL", "FOIL_TOOLS")
CONFIGS: dict[str, dict[str, str]] = {
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
    "LUNA_LOW": {"model": "gpt-5.6-luna", "effort": "low"},
    "LUNA_HIGH": {"model": "gpt-5.6-luna", "effort": "high"},
}
EXPECTED_ITEMS = 20
EXPECTED_PER_ARM = 10
EXPECTED_CALLS = 60
EXPECTED_PROVIDER_CALLS = 120
MAX_WORKERS = 3
TIMEOUT_SECONDS = 1200
ALLOWED_TOOL_TYPES = {"web_search", "command_execution"}
NON_TOOL_ITEM_TYPES = {"reasoning", "agent_message"}

PRIOR_HLE_IDS = {
    "66eaa401c7a3252f0f3fe535",
    "66ee60c50e499ab807af71f2",
    "66f05d93454a69621ec1badc",
    "66fcf81e8a146dd80cfb2296",
    "66fe16f4762ab58b937863b8",
    "6700ab4bfa64315ed5204e4d",
    "670417b84f1cdb9711ec68d6",
    "670b02d5560fcdf78354fad0",
    "670db60f6f63b774df6f4daa",
    "670f289fb671096a201efee4",
    "670faed07ddb2771c2d214ea",
    "6716260eae3149088ed859b9",
    "671ab94ffad7ae30b89eff8f",
    "671d91bcad7fb0793a0e93bd",
    "671f53490ac3c2f49e4fa4d5",
    "6722728827542064f9b14815",
    "6722809eb0e7186e733d6838",
    "672579985c16db8f9647559c",
    "6726140e196c3daaab906acc",
    "6726efce60a613901f1fdf0b",
    "673029b26ad714f5469388f5",
    "67352e9911e5510fc618f619",
    "6736d98353926b38af8c204b",
    "67391de141c297471963efc6",
    "673a76559e89466aa6433f66",
    "67383288f2df805520bc86b5",
}

IMAGE_MARKERS = (
    "attached image",
    "image above",
    "image below",
    "following image",
    "this image",
    "shown in the image",
    "shown in this image",
    "pictured",
    "figure above",
    "figure below",
    "attached figure",
    "this knot",
    "guess the music",
    "small part of the flag",
)

ANSWER_FIELDS = {
    "answer",
    "route",
    "gap_kind",
    "tool_decision",
    "tool_use_rationale",
    "evidence_urls",
    "confidence",
}
ROUTES = {"DIRECT", "VERIFY", "FULL"}
GAP_KINDS = {
    "EVIDENCE_GAP",
    "EXECUTION_SLIP",
    "INCORRECT_KNOWLEDGE",
    "MISSING_KNOWLEDGE",
    "MISSING_PROCEDURE",
    "REPRESENTATION_MISMATCH",
    "RETRIEVAL_FAILURE",
    "TOOL_OR_ARTIFACT_GAP",
    "VERIFICATION_GAP",
    "UNKNOWN",
}
TOOL_DECISIONS = {
    "NOT_AVAILABLE",
    "NOT_NEEDED",
    "USED_WEB_SEARCH",
    "USED_COMPUTATION",
    "USED_BOTH",
    "ATTEMPTED_FAILED",
}


class ProtocolError(RuntimeError):
    pass


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def pretty(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty(value), encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_source() -> tuple[bytes, list[dict[str, Any]]]:
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "FOIL-HLE-active-20/1.0"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    actual = sha256_bytes(payload)
    if actual != SOURCE_SHA256:
        raise ProtocolError(f"HLE source digest mismatch: {actual}")
    rows = [
        json.loads(line)
        for line in payload.decode("utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 50 or len({str(row.get("id")) for row in rows}) != 50:
        raise ProtocolError("HLE source row/id conservation failed")
    return payload, rows


def rank_key(identity: str) -> str:
    return sha256_text(f"{SEED}:HLE_ACTIVE_20:{identity}")


def select_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for row in rows:
        identity = str(row.get("id") or "")
        question = str(row.get("question") or "")
        answer_type = str(row.get("answer_type") or "")
        low = question.casefold()
        if not identity or identity in PRIOR_HLE_IDS:
            continue
        if not question or len(question) > 6500:
            continue
        if any(marker in low for marker in IMAGE_MARKERS):
            continue
        if answer_type not in {"exactMatch", "multipleChoice"}:
            continue
        eligible.append(row)
    eligible.sort(
        key=lambda row: (-len(str(row["question"])), rank_key(str(row["id"])))
    )
    if len(eligible) < EXPECTED_ITEMS:
        raise ProtocolError(
            f"need at least {EXPECTED_ITEMS} unseen text HLE rows, got {len(eligible)}"
        )
    selected: list[dict[str, Any]] = []
    for index, row in enumerate(eligible[:EXPECTED_ITEMS]):
        arm = ARMS[index % 2]
        item: dict[str, Any] = {
            "id": f"hle-{row['id']}",
            "source_id": str(row["id"]),
            "benchmark": "HLE_PUBLIC_TEXT_EXACT",
            "arm": arm,
            "category": str(row.get("category") or "Other"),
            "answer_type": str(row["answer_type"]),
            "question": str(row["question"]),
            "selection_rank": index + 1,
            "question_characters": len(str(row["question"])),
            "selection_proxy": (
                "descending question length; seeded SHA-256 tie-break; "
                "alternating disjoint arms"
            ),
        }
        item["item_sha256"] = sha256_text(canonical(item))
        selected.append(item)
    counts = Counter(item["arm"] for item in selected)
    if counts != Counter({"FOIL": 10, "FOIL_TOOLS": 10}):
        raise ProtocolError(f"arm assignment invariant failed: {dict(counts)}")
    return selected


def policy_document(arm: str) -> dict[str, object]:
    if arm == "FOIL":
        task = TaskContext(
            benchmark="receipt-only",
            closed_book=True,
            technical_reasoning=True,
            output_contract_required=True,
            uncertainties=(
                LoadBearingUncertainty(
                    "answer correctness", ClaimKind.LOGICAL, True, False
                ),
            ),
        )
        host_route = "FULL"
    elif arm == "FOIL_TOOLS":
        task = TaskContext(
            benchmark="receipt-only",
            requires_external_retrieval=True,
            output_contract_required=True,
            uncertainties=(
                LoadBearingUncertainty(
                    "answer evidence", ClaimKind.EXTERNAL_FACT, True, False
                ),
            ),
        )
        # Retrieval is a resource allocation inside the same FULL complement.
        # Route selection must not be derived from tool availability.
        host_route = "FULL"
    else:
        raise ValueError(f"unknown arm: {arm}")
    decision = RuntimePolicyV2().decide(task)
    trace = decision.trace()
    return {
        **trace,
        "host_route": host_route,
        "actions": [action.value for action in decision.actions],
        "required_verifiers": [value.value for value in decision.required_verifiers],
        "pending_verifiers": [value.value for value in decision.pending_verifiers],
        "retrieval_allowed": decision.resource_allocation.retrieval_allowed,
        "search_query_priority": decision.resource_allocation.search_query_priority,
        "source_followup_priority": decision.resource_allocation.source_followup_priority,
        "resource_rationale": decision.resource_allocation.rationale,
        "active_in_benchmark": True,
        "production_authorized": False,
    }


def base_prompt_for(item: Mapping[str, object]) -> str:
    return (
        "Produce the initial A0 answer to this HLE question closed-book. FOIL is not "
        "active in this call. Do not use tools, files, network access, or outside "
        "context. Return only the JSON object required by the response schema. The "
        "answer field must contain only the final answer text, not an explanation.\n\n"
        f"HLE question:\n{item['question']}"
    )


def prompt_for(
    item: Mapping[str, object], arm: str, a0: str = "__FROZEN_A0__"
) -> str:
    policy = policy_document(arm)
    if arm == "FOIL":
        capability = (
            "No external tool capability is available. Do the FULL closed-book FOIL "
            "reasoning complement. Set tool_decision=NOT_AVAILABLE and evidence_urls=[]."
        )
    else:
        capability = (
            "Read-only web search and sandboxed command execution are available. Follow "
            "the host VERIFY retrieval route. Use the minimum sufficient tool capability "
            "when it can supply load-bearing evidence; tools are not mandatory when they "
            "cannot help. Report URLs actually used in evidence_urls."
        )
    return (
        "This is an active benchmark execution over a frozen A0, not a shadow-only "
        "recommendation. The host has selected the route in FOIL_POLICY_TRACE. Follow "
        "that route and set "
        "the route field to the exact host_route. Identify the smallest task-local gap, "
        "supply the minimum useful complement, verify claim-natively where possible, and "
        "return only the JSON object required by the response schema. Do not expose chain "
        "of thought. The answer field must contain only the final answer text, not an "
        "explanation.\n\n"
        f"{capability}\n\n"
        "<FOIL_POLICY_TRACE>\n"
        f"{pretty(policy)}"
        "</FOIL_POLICY_TRACE>\n\n"
        f"<FROZEN_A0>{json.dumps(a0, ensure_ascii=False)}</FROZEN_A0>\n\n"
        "<FOIL_SKILL>\n"
        f"{FOIL_SKILL.read_text(encoding='utf-8')}"
        "\n</FOIL_SKILL>\n\n"
        f"HLE question:\n{item['question']}"
    )


def build_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for item in items:
        arm = str(item["arm"])
        policy = policy_document(arm)
        for config_id, config in CONFIGS.items():
            prompt = prompt_for(item, arm)
            units.append(
                {
                    "unit_id": f"{config_id.lower()}-{arm.lower()}-{item['id']}",
                    "item_id": item["id"],
                    "config_id": config_id,
                    "model": config["model"],
                    "effort": config["effort"],
                    "arm": arm,
                    "host_route": policy["host_route"],
                    "policy": policy,
                    "base_prompt_sha256": sha256_text(base_prompt_for(item)),
                    "prompt_sha256": sha256_text(prompt),
                }
            )
    units.sort(key=lambda row: str(row["unit_id"]))
    if len(units) != EXPECTED_CALLS or len(
        {str(row["unit_id"]) for row in units}
    ) != EXPECTED_CALLS:
        raise ProtocolError("unit/call conservation failed")
    return units


def build_manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "foil.hle-active-20-manifest.v1",
        "classification": "SMALL_ACTIVE_HLE_TOOL_USE_PILOT",
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "seed": SEED,
        "selection_rule": (
            "unseen text-only rows; descending question length; seeded digest "
            "tie-break; alternating disjoint arms"
        ),
        "items_sha256": sha256_text(canonical(items)),
        "protocol_sha256": sha256_file(PROTOCOL),
        "schema_sha256": sha256_file(SCHEMA),
        "base_schema_sha256": sha256_file(BASE_SCHEMA),
        "foil_skill_sha256": sha256_file(FOIL_SKILL),
        "policy_source_sha256": sha256_file(POLICY_SOURCE),
        "adaptive_source_sha256": sha256_file(ADAPTIVE_SOURCE),
        "active_executor_sha256": sha256_file(ACTIVE_EXECUTOR),
        "runner_sha256": sha256_file(Path(__file__)),
        "configs": CONFIGS,
        "arms": list(ARMS),
        "units": build_units(items),
        "result_units": EXPECTED_CALLS,
        "planned_provider_calls": EXPECTED_PROVIDER_CALLS,
        "calls_per_unit": 2,
        "maximum_parallel_calls": MAX_WORKERS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "artificial_token_cap": None,
        "allowed_tool_types": sorted(ALLOWED_TOOL_TYPES),
        "production_authorized": False,
        "promotion_authorized": False,
        "non_claims": [
            "HLE population accuracy",
            "same-item causal tool benefit",
            "production activation",
            "calibration",
            "promotion",
            "frontier-model recall",
            "production token target",
        ],
    }


def prepare() -> None:
    if any(path.exists() for path in (ITEMS, MANIFEST, LOCK, PREDICTIONS, RESULTS)):
        raise ProtocolError("prepare refuses to overwrite an existing experiment")
    _, rows = fetch_source()
    items = select_items(rows)
    write_json(ITEMS, {"schema": "foil.hle-active-20-items.v1", "items": items})
    write_json(MANIFEST, build_manifest(items))
    lock_files = (
        PROTOCOL,
        SCHEMA,
        BASE_SCHEMA,
        FOIL_SKILL,
        POLICY_SOURCE,
        ADAPTIVE_SOURCE,
        ACTIVE_EXECUTOR,
        Path(__file__),
        ITEMS,
        MANIFEST,
    )
    write_json(
        LOCK,
        {
            "schema": "foil.hle-active-20-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in lock_files
            },
        },
    )
    counts = Counter(item["category"] for item in items)
    print(
        f"prepared items={len(items)} arms=10/10 units={EXPECTED_CALLS} "
        f"categories={dict(sorted(counts.items()))}"
    )


def validate_lock() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for path in (PROTOCOL, SCHEMA, BASE_SCHEMA, ITEMS, MANIFEST, LOCK):
        if not path.is_file():
            raise ProtocolError(f"missing frozen artifact: {path}")
    lock = read_json(LOCK)
    for relative, expected in lock["files"].items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise ProtocolError(f"frozen hash mismatch: {relative}: {actual}")
    manifest = read_json(MANIFEST)
    items = read_json(ITEMS)["items"]
    if manifest["items_sha256"] != sha256_text(canonical(items)):
        raise ProtocolError("items differ from manifest")
    if manifest["units"] != build_units(items):
        raise ProtocolError("unit or prompt binding differs from manifest")
    if len(items) != EXPECTED_ITEMS or len(manifest["units"]) != EXPECTED_CALLS:
        raise ProtocolError("matrix size invariant failed")
    return manifest, items


def codex_executable() -> str:
    if sys.platform == "win32":
        shim = shutil.which("codex.cmd")
        if shim:
            package_root = (
                Path(shim).resolve().parent
                / "node_modules"
                / "@openai"
                / "codex"
                / "node_modules"
                / "@openai"
            )
            packaged = sorted(
                package_root.glob("codex-win32-*/vendor/*/bin/codex.exe")
            )
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
    process = subprocess.run(
        [codex_executable(), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if process.returncode:
        raise ProtocolError(f"codex --version failed: {process.stderr.strip()}")
    return process.stdout.strip()


def build_argv(
    config_id: str,
    arm: str,
    stage: str,
    workdir: Path,
    last: Path,
) -> list[str]:
    config = CONFIGS[config_id]
    if stage not in {"base", "route"}:
        raise ValueError("stage must be base or route")
    argv = [codex_executable()]
    if stage == "route" and arm == "FOIL_TOOLS":
        argv.append("--search")
    argv.extend(
        [
            "exec",
            "-m",
            config["model"],
            "-c",
            f'model_reasoning_effort="{config["effort"]}"',
            "-s",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--output-schema",
            str(BASE_SCHEMA if stage == "base" else SCHEMA),
            "--json",
            "-o",
            str(last),
            "-C",
            str(workdir),
            "-",
        ]
    )
    if any("token" in value.casefold() for value in argv):
        raise ProtocolError("artificial token limit unexpectedly entered argv")
    return argv


def parse_base_answer(text: str) -> tuple[dict[str, str] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"base last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != {"answer"}:
        return None, "base last output has unknown or missing fields"
    answer = value["answer"]
    if not isinstance(answer, str) or not 1 <= len(answer) <= 400:
        return None, "base answer is not bounded non-empty text"
    return {"answer": answer}, None


def parse_answer(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != ANSWER_FIELDS:
        return None, "last output has unknown or missing fields"
    if not isinstance(value["answer"], str) or not 1 <= len(value["answer"]) <= 400:
        return None, "answer is not bounded non-empty text"
    if value["route"] not in ROUTES or value["gap_kind"] not in GAP_KINDS:
        return None, "route or gap_kind is invalid"
    if value["tool_decision"] not in TOOL_DECISIONS:
        return None, "tool_decision is invalid"
    if not isinstance(value["tool_use_rationale"], str) or len(
        value["tool_use_rationale"]
    ) > 300:
        return None, "tool_use_rationale has wrong type or bound"
    urls = value["evidence_urls"]
    if not isinstance(urls, list) or len(urls) > 5 or not all(
        isinstance(url, str) and len(url) <= 500 for url in urls
    ):
        return None, "evidence_urls has wrong type or bound"
    confidence = value["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, int)
        or not 0 <= confidence <= 100
    ):
        return None, "confidence has wrong type or bound"
    return value, None


def _tool_metadata(item: Mapping[str, object], index: int) -> dict[str, object]:
    action = item.get("action") if isinstance(item.get("action"), dict) else {}
    output = item.get("aggregated_output")
    if not isinstance(output, str):
        output = item.get("output") if isinstance(item.get("output"), str) else ""
    query = item.get("query")
    if not isinstance(query, str):
        query = action.get("query") if isinstance(action.get("query"), str) else ""
    command_value = item.get("command")
    if isinstance(command_value, str):
        command_text = command_value
    elif isinstance(command_value, list) and all(isinstance(v, str) for v in command_value):
        command_text = canonical(command_value)
    else:
        command_text = ""
    lowered = command_text.casefold()
    if not command_text:
        command_kind = "NONE"
    elif "skill.md" in lowered:
        command_kind = "LOCAL_SKILL_READ"
    elif "python" in lowered:
        command_kind = "PYTHON_COMPUTE"
    elif "rg " in lowered or "get-content" in lowered:
        command_kind = "LOCAL_READ"
    else:
        command_kind = "SHELL_COMPUTE"
    public_action = action if str(item.get("type") or "") == "web_search" else {}
    return {
        "first_event_index": index,
        "last_event_index": index,
        "tool_id": str(item.get("id") or ""),
        "tool_type": str(item.get("type") or ""),
        "query": query,
        "command_kind": command_kind,
        "command_characters": len(command_text),
        "command_sha256": sha256_text(command_text),
        "status": str(item.get("status") or ""),
        "exit_code": item.get("exit_code"),
        "output_characters": len(output),
        "output_sha256": sha256_text(output),
        "action": public_action,
    }


def parse_stream(text: str) -> dict[str, object]:
    parse_errors = 0
    event_types: list[str] = []
    usage: dict[str, int] = {}
    tools: dict[str, dict[str, object]] = {}
    sequence: list[dict[str, object]] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(event, dict):
            parse_errors += 1
            continue
        event_type = str(event.get("type") or "unknown")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type") or "")
        event_types.append(f"{event_type}:{item_type}" if item_type else event_type)
        if event_type == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = {
                str(key): int(value)
                for key, value in event["usage"].items()
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            }
        if item_type and item_type not in NON_TOOL_ITEM_TYPES:
            metadata = _tool_metadata(item, index)
            key = str(metadata["tool_id"] or f"event-{index}")
            current = tools.get(key, {})
            first = min(int(current.get("first_event_index", index)), index)
            merged = {**current, **{k: v for k, v in metadata.items() if v not in ("", {}, None)}}
            merged["first_event_index"] = first
            merged["last_event_index"] = index
            merged["started"] = bool(current.get("started")) or event_type == "item.started"
            merged["completed"] = bool(current.get("completed")) or event_type == "item.completed"
            tools[key] = merged
            sequence.append(
                {
                    "event_index": index,
                    "event_type": event_type,
                    "tool_id": key,
                    "tool_type": item_type,
                }
            )
    rows = sorted(tools.values(), key=lambda row: int(row.get("first_event_index", 0)))
    return {
        "parse_errors": parse_errors,
        "event_types": sorted(set(event_types)),
        "usage": usage,
        "tools": rows,
        "tool_sequence": sequence,
    }


def _validate_tool_claim(
    arm: str, answer: Mapping[str, object] | None, tools: list[dict[str, object]]
) -> list[str]:
    errors: list[str] = []
    types = {str(row.get("tool_type")) for row in tools}
    if arm == "FOIL" and tools:
        errors.append("tools_used_in_no_tools_arm")
    if arm == "FOIL_TOOLS" and not types.issubset(ALLOWED_TOOL_TYPES):
        errors.append(f"unsupported_tool_types={sorted(types - ALLOWED_TOOL_TYPES)}")
    if answer is None:
        return errors
    expected_route = "FULL"
    if answer["route"] != expected_route:
        errors.append(
            f"route_mismatch expected={expected_route} observed={answer['route']}"
        )
    decision = str(answer["tool_decision"])
    used_web = "web_search" in types
    used_compute = "command_execution" in types
    claimed_used = decision.startswith("USED_")
    if (used_web or used_compute) and not claimed_used and decision != "ATTEMPTED_FAILED":
        errors.append("observed_tool_use_not_reported")
    if claimed_used and not (used_web or used_compute):
        errors.append("reported_tool_use_without_event")
    if arm == "FOIL" and decision != "NOT_AVAILABLE":
        errors.append("no_tools_arm_did_not_report_not_available")
    if used_web and not answer["evidence_urls"]:
        errors.append("web_search_without_evidence_url")
    return errors


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def frozen_commit() -> str:
    validate_lock()
    for relative in read_json(LOCK)["files"]:
        if _git("ls-files", "--error-unmatch", relative).returncode:
            raise ProtocolError(f"frozen artifact is not committed: {relative}")
        if _git("diff", "--quiet", "HEAD", "--", relative).returncode:
            raise ProtocolError(f"frozen artifact differs from HEAD: {relative}")
    head = _git("rev-parse", "HEAD")
    if head.returncode:
        raise ProtocolError("cannot resolve frozen commit")
    return head.stdout.strip()


def execute_unit(
    unit: Mapping[str, object], item: Mapping[str, object], commit: str, version: str
) -> dict[str, object]:
    unit_id = str(unit["unit_id"])
    receipt_path = RECEIPTS / f"{unit_id}.json"
    if receipt_path.exists():
        existing = read_json(receipt_path)
        if existing.get("base_prompt_sha256") != unit["base_prompt_sha256"]:
            raise ProtocolError(f"existing receipt prompt mismatch: {unit_id}")
        return existing
    raw = PRIVATE / unit_id
    if raw.exists():
        raise ProtocolError(f"orphaned attempt prohibits retry: {unit_id}")
    raw.mkdir(parents=True)
    started = now()
    clock = time.monotonic()

    def call(stage: str, prompt: str) -> dict[str, object]:
        stage_dir = raw / stage
        stage_dir.mkdir()
        (stage_dir / "prompt.txt").write_text(prompt, encoding="utf-8", newline="\n")
        last = stage_dir / "last.json"
        stage_clock = time.monotonic()
        with tempfile.TemporaryDirectory(prefix=f"foil-hle-{stage}-") as temporary:
            try:
                process = subprocess.run(
                    build_argv(
                        str(unit["config_id"]),
                        str(unit["arm"]),
                        stage,
                        Path(temporary),
                        last,
                    ),
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=TIMEOUT_SECONDS,
                    check=False,
                )
                returncode = process.returncode
                stdout = process.stdout
                stderr = process.stderr
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                returncode = None
                stdout = (
                    exc.stdout.decode("utf-8", "replace")
                    if isinstance(exc.stdout, bytes)
                    else (exc.stdout or "")
                )
                stderr = (
                    exc.stderr.decode("utf-8", "replace")
                    if isinstance(exc.stderr, bytes)
                    else (exc.stderr or "")
                )
                timed_out = True
        (stage_dir / "events.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
        (stage_dir / "stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
        last_text = last.read_text(encoding="utf-8") if last.exists() else ""
        return {
            "stage": stage,
            "returncode": returncode,
            "timed_out": timed_out,
            "wall_seconds": time.monotonic() - stage_clock,
            "prompt_sha256": sha256_text(prompt),
            "prompt_characters": len(prompt),
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            "last_output_sha256": sha256_text(last_text),
            "last_text": last_text,
            "stream": parse_stream(stdout),
        }

    base_prompt = base_prompt_for(item)
    base_call = call("base", base_prompt)
    base_stream = base_call["stream"]
    assert isinstance(base_stream, dict)
    base, base_error = parse_base_answer(str(base_call["last_text"]))
    invalid: list[str] = []
    if base_call["timed_out"]:
        invalid.append("base_timeout")
    if base_call["returncode"] != 0:
        invalid.append(f"base_returncode={base_call['returncode']}")
    if base_stream["parse_errors"]:
        invalid.append(f"base_parse_errors={base_stream['parse_errors']}")
    if base_stream["tools"]:
        invalid.append("base_used_tool")
    if base_error:
        invalid.append(base_error)

    route_call: dict[str, object] | None = None
    answer: dict[str, Any] | None = None
    active_trace: dict[str, object] | None = None
    if base is not None:
        a0 = base["answer"]
        route_prompt = prompt_for(item, str(unit["arm"]), a0)
        route_call = call("route", route_prompt)
        route_stream = route_call["stream"]
        assert isinstance(route_stream, dict)
        candidate, answer_error = parse_answer(str(route_call["last_text"]))
        if route_call["timed_out"]:
            invalid.append("route_timeout")
        if route_call["returncode"] != 0:
            invalid.append(f"route_returncode={route_call['returncode']}")
        if route_stream["parse_errors"]:
            invalid.append(f"route_parse_errors={route_stream['parse_errors']}")
        if answer_error:
            invalid.append(answer_error)
        invalid.extend(
            _validate_tool_claim(str(unit["arm"]), candidate, list(route_stream["tools"]))
        )
        if candidate is not None:
            decision = ShadowRouteDecision(
                route=Route(str(unit["host_route"])),
                reason=DecisionReason.FULL_POSITIVE_VALUE,
                a0_digest=digest(a0),
                binding_digest=digest(
                    {
                        "item_sha256": item["item_sha256"],
                        "config_id": unit["config_id"],
                        "arm": unit["arm"],
                    }
                ),
                expected_value_numerator=1,
            )
            work = RouteWorkResult(
                answer=str(candidate["answer"]),
                input_tokens=int(route_stream["usage"].get("input_tokens", 0)),
                cached_input_tokens=int(route_stream["usage"].get("cached_input_tokens", 0)),
                output_tokens=int(route_stream["usage"].get("output_tokens", 0)),
                tool_event_types=tuple(str(row["tool_type"]) for row in route_stream["tools"]),
            )
            final, active = execute_benchmark_route(
                decision,
                a0,
                policy=BenchmarkExecutionPolicy(enabled=True),
                full_runner=lambda: work,
            )
            answer = {**candidate, "answer": final}
            active_trace = active.trace()

    route_stream = (
        route_call["stream"]
        if route_call is not None
        else {"event_types": [], "usage": {}, "tools": [], "tool_sequence": []}
    )
    assert isinstance(route_stream, dict)
    base_usage = dict(base_stream["usage"])
    route_usage = dict(route_stream["usage"])
    all_usage_keys = set(base_usage) | set(route_usage)
    combined_usage = {
        key: int(base_usage.get(key, 0)) + int(route_usage.get(key, 0))
        for key in all_usage_keys
    }
    route_public = None
    if route_call is not None:
        route_public = {key: value for key, value in route_call.items() if key not in {"last_text", "stream"}}
    try:
        base_public = {key: value for key, value in base_call.items() if key not in {"last_text", "stream"}}
    except Exception as exc:  # pragma: no cover - defensive serialization boundary
        raise ProtocolError(f"failed to publish call metadata: {exc}") from exc
    receipt: dict[str, object] = {
        "schema": "foil.hle-active-20-receipt.v2",
        "unit_id": unit_id,
        "item_id": unit["item_id"],
        "arm": unit["arm"],
        "config_id": unit["config_id"],
        "model": unit["model"],
        "effort": unit["effort"],
        "host_route": unit["host_route"],
        "policy": unit["policy"],
        "codex_version": version,
        "pre_call_commit": commit,
        "started_at": started,
        "finished_at": now(),
        "wall_seconds": time.monotonic() - clock,
        "base_prompt_sha256": sha256_text(base_prompt),
        "route_prompt_sha256": None if route_call is None else route_call["prompt_sha256"],
        "base_call": base_public,
        "route_call": route_public,
        "base_answer": base,
        "active_route_receipt": active_trace,
        "base_usage": base_usage,
        "route_usage": route_usage,
        "usage": combined_usage,
        "base_event_types": base_stream["event_types"],
        "event_types": route_stream["event_types"],
        "tools": route_stream["tools"],
        "tool_sequence": route_stream["tool_sequence"],
        "actual_tool_calls": len(route_stream["tools"]),
        "answer": answer,
        "valid": not invalid,
        "invalid_reasons": sorted(set(invalid)),
        "artificial_token_cap": None,
        "benchmark_answer_active": True,
        "provider_calls": 1 + int(route_call is not None),
        "production_authorized": False,
        "promotion_authorized": False,
    }
    write_json(receipt_path, receipt)
    return receipt


def run() -> None:
    manifest, items = validate_lock()
    commit = frozen_commit()
    version = codex_version()
    by_id = {str(item["id"]): item for item in items}
    units = list(manifest["units"])
    results: dict[str, dict[str, object]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_unit = {
            pool.submit(execute_unit, unit, by_id[str(unit["item_id"])], commit, version): unit
            for unit in units
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_to_unit):
            unit = future_to_unit[future]
            receipt = future.result()
            results[str(unit["unit_id"])] = receipt
            completed += 1
            print(
                f"completed={completed}/{EXPECTED_CALLS} unit={unit['unit_id']} "
                f"valid={receipt['valid']} tools={receipt['actual_tool_calls']}",
                flush=True,
            )
    if len(results) != EXPECTED_CALLS or len(list(RECEIPTS.glob("*.json"))) != EXPECTED_CALLS:
        raise ProtocolError("receipt conservation failed")
    predictions: list[dict[str, object]] = []
    for unit in units:
        receipt = results[str(unit["unit_id"])]
        predictions.append(
            {
                **unit,
                "answer": receipt["answer"],
                "valid": receipt["valid"],
                "invalid_reasons": receipt["invalid_reasons"],
                "actual_tool_calls": receipt["actual_tool_calls"],
                "receipt_sha256": sha256_file(
                    RECEIPTS / f"{unit['unit_id']}.json"
                ),
            }
        )
    predictions.sort(key=lambda row: str(row["unit_id"]))
    write_json(
        PREDICTIONS,
        {
            "schema": "foil.hle-active-20-predictions.v1",
            "pre_call_commit": commit,
            "codex_version": version,
            "provider_calls": sum(int(row["provider_calls"]) for row in results.values()),
            "valid_rows": sum(bool(row["valid"]) for row in predictions),
            "profile_writes": 0,
            "external_write_tools": 0,
            "artificial_token_cap": None,
            "predictions": predictions,
        },
    )
    print(
        f"predictions frozen rows={len(predictions)} "
        f"valid={sum(bool(row['valid']) for row in predictions)}; commit before score"
    )


def require_predictions_committed() -> None:
    required = [PREDICTIONS, *sorted(RECEIPTS.glob("*.json"))]
    for path in required:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        if _git("ls-files", "--error-unmatch", relative).returncode:
            raise ProtocolError(f"prediction artifact is not committed: {relative}")
    if _git("status", "--porcelain").stdout.strip():
        raise ProtocolError("working tree must be clean before scorer opens gold")


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def usage(receipt: Mapping[str, object]) -> dict[str, int]:
    raw = receipt.get("usage") if isinstance(receipt.get("usage"), dict) else {}
    keys = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    return {key: int(raw.get(key, 0)) for key in keys}


def normalized_usage(raw: object) -> dict[str, int]:
    return usage({"usage": raw if isinstance(raw, dict) else {}})


def token_total(value: Mapping[str, int]) -> int:
    return int(value["input_tokens"]) + int(value["output_tokens"])


def summarize(rows: list[dict[str, Any]]) -> dict[str, object]:
    tokens = [token_total(row["usage"]) for row in rows]
    base_tokens = [token_total(row["base_usage"]) for row in rows]
    route_tokens = [token_total(row["route_usage"]) for row in rows]
    multipliers = [
        total / base
        for total, base in zip(tokens, base_tokens)
        if base > 0
    ]
    valid = [row for row in rows if row["valid"]]
    tools = [row for row in rows if row["actual_tool_calls"] > 0]
    return {
        "n": len(rows),
        "valid": len(valid),
        "correct": sum(bool(row["correct"]) for row in valid),
        "base_correct": sum(bool(row["base_correct"]) for row in valid),
        "rescues": sum(
            bool(not row["base_correct"] and row["correct"]) for row in valid
        ),
        "damages": sum(
            bool(row["base_correct"] and not row["correct"]) for row in valid
        ),
        "answer_changes": sum(bool(row["answer_changed"]) for row in valid),
        "accuracy_on_valid": (
            None if not valid else sum(bool(row["correct"]) for row in valid) / len(valid)
        ),
        "invalid": len(rows) - len(valid),
        "tool_rows": len(tools),
        "tool_use_rate": None if not rows else len(tools) / len(rows),
        "tool_calls": sum(int(row["actual_tool_calls"]) for row in rows),
        "web_search_calls": sum(
            sum(tool["tool_type"] == "web_search" for tool in row["tools"])
            for row in rows
        ),
        "command_calls": sum(
            sum(tool["tool_type"] == "command_execution" for tool in row["tools"])
            for row in rows
        ),
        "route_counts": dict(sorted(Counter(row["host_route"] for row in rows).items())),
        "model_route_counts": dict(
            sorted(
                Counter(
                    row["answer"]["route"]
                    for row in valid
                    if isinstance(row.get("answer"), dict)
                ).items()
            )
        ),
        "input_tokens": sum(row["usage"]["input_tokens"] for row in rows),
        "cached_input_tokens": sum(row["usage"]["cached_input_tokens"] for row in rows),
        "cache_write_input_tokens": sum(
            row["usage"]["cache_write_input_tokens"] for row in rows
        ),
        "output_tokens": sum(row["usage"]["output_tokens"] for row in rows),
        "reasoning_output_tokens": sum(
            row["usage"]["reasoning_output_tokens"] for row in rows
        ),
        "total_tokens": sum(tokens),
        "base_total_tokens": sum(base_tokens),
        "route_total_tokens": sum(route_tokens),
        "mean_base_tokens": None if not base_tokens else statistics.mean(base_tokens),
        "mean_route_tokens": None if not route_tokens else statistics.mean(route_tokens),
        "mean_total_tokens": None if not tokens else statistics.mean(tokens),
        "median_total_tokens": None if not tokens else statistics.median(tokens),
        "mean_total_multiplier_vs_a0": (
            None if not multipliers else statistics.mean(multipliers)
        ),
        "median_total_multiplier_vs_a0": (
            None if not multipliers else statistics.median(multipliers)
        ),
        "mean_wall_seconds": (
            None if not rows else statistics.mean(float(row["wall_seconds"]) for row in rows)
        ),
    }


def _group_tool_use(rows: list[dict[str, Any]], key: str) -> dict[str, object]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {
        name: {
            "rows": len(group),
            "tool_rows": sum(row["actual_tool_calls"] > 0 for row in group),
            "tool_calls": sum(row["actual_tool_calls"] for row in group),
            "correct": sum(row["correct"] for row in group if row["valid"]),
            "valid": sum(row["valid"] for row in group),
        }
        for name, group in sorted(grouped.items())
    }


def build_results() -> dict[str, object]:
    manifest, items = validate_lock()
    _, source_rows = fetch_source()
    source = {str(row["id"]): row for row in source_rows}
    gold = {str(item["id"]): source[str(item["source_id"])]["answer"] for item in items}
    item_map = {str(item["id"]): item for item in items}
    rows: list[dict[str, Any]] = []
    for prediction in read_json(PREDICTIONS)["predictions"]:
        receipt_path = RECEIPTS / f"{prediction['unit_id']}.json"
        if sha256_file(receipt_path) != prediction["receipt_sha256"]:
            raise ProtocolError(f"receipt hash mismatch: {prediction['unit_id']}")
        receipt = read_json(receipt_path)
        item = item_map[str(prediction["item_id"])]
        answer = receipt.get("answer")
        predicted = answer.get("answer") if isinstance(answer, dict) else None
        base_answer = receipt.get("base_answer")
        base_predicted = (
            base_answer.get("answer") if isinstance(base_answer, dict) else None
        )
        expected = gold[str(prediction["item_id"])]
        valid = bool(receipt["valid"])
        final_correct = bool(valid and normalize(predicted) == normalize(expected))
        base_correct = bool(valid and normalize(base_predicted) == normalize(expected))
        rows.append(
            {
                "unit_id": prediction["unit_id"],
                "item_id": prediction["item_id"],
                "category": item["category"],
                "arm": prediction["arm"],
                "config_id": prediction["config_id"],
                "model": prediction["model"],
                "effort": prediction["effort"],
                "host_route": prediction["host_route"],
                "answer": answer,
                "gold": expected,
                "base_answer": base_answer,
                "correct": final_correct,
                "base_correct": base_correct,
                "answer_changed": bool(
                    valid and normalize(predicted) != normalize(base_predicted)
                ),
                "valid": valid,
                "invalid_reasons": receipt["invalid_reasons"],
                "actual_tool_calls": receipt["actual_tool_calls"],
                "tools": receipt["tools"],
                "tool_sequence": receipt["tool_sequence"],
                "base_usage": normalized_usage(receipt.get("base_usage")),
                "route_usage": normalized_usage(receipt.get("route_usage")),
                "usage": usage(receipt),
                "wall_seconds": receipt["wall_seconds"],
                "active_route_receipt": receipt["active_route_receipt"],
                "receipt_sha256": prediction["receipt_sha256"],
            }
        )
    rows.sort(key=lambda row: str(row["unit_id"]))
    summaries: dict[str, object] = {"OVERALL": summarize(rows)}
    for arm in ARMS:
        summaries[arm] = summarize([row for row in rows if row["arm"] == arm])
    for config_id in CONFIGS:
        summaries[config_id] = summarize(
            [row for row in rows if row["config_id"] == config_id]
        )
        for arm in ARMS:
            summaries[f"{config_id}::{arm}"] = summarize(
                [
                    row
                    for row in rows
                    if row["config_id"] == config_id and row["arm"] == arm
                ]
            )
    return {
        "schema": "foil.hle-active-20-results.v1",
        "classification": "SMALL_ACTIVE_HLE_TOOL_USE_PILOT",
        "source_sha256": SOURCE_SHA256,
        "summaries": summaries,
        "tool_use_by_category": _group_tool_use(rows, "category"),
        "tool_use_by_config": _group_tool_use(rows, "config_id"),
        "rows": rows,
        "provider_calls": sum(
            read_json(RECEIPTS / f"{row['unit_id']}.json")["provider_calls"]
            for row in rows
        ),
        "profile_writes": 0,
        "external_write_tools": 0,
        "artificial_token_cap": None,
        "production_authorized": False,
        "promotion_authorized": False,
        "scoring_boundary": (
            "Whitespace/case-normalized exact match only; equivalent mathematical "
            "forms may be scored wrong. Arms use disjoint items, so their difference "
            "is descriptive rather than causal."
        ),
        "non_claims": manifest["non_claims"],
    }


def score() -> None:
    require_predictions_committed()
    result = build_results()
    write_json(RESULTS, result)
    lines = [
        "# FOIL HLE active-route 20-item pilot — results",
        "",
        "Classification: **SMALL_ACTIVE_HLE_TOOL_USE_PILOT**",
        "",
        "| Slice | Valid | A0 correct | Final correct | Rescues | Damages | Tool rows | Calls | A0 tokens | Route tokens | Total | Mean multiplier |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in (
        "TERRA_HIGH::FOIL",
        "TERRA_HIGH::FOIL_TOOLS",
        "LUNA_LOW::FOIL",
        "LUNA_LOW::FOIL_TOOLS",
        "LUNA_HIGH::FOIL",
        "LUNA_HIGH::FOIL_TOOLS",
        "FOIL",
        "FOIL_TOOLS",
        "OVERALL",
    ):
        row = result["summaries"][key]
        multiplier = (
            "N/A"
            if row["mean_total_multiplier_vs_a0"] is None
            else f"{row['mean_total_multiplier_vs_a0']:.3f}x"
        )
        lines.append(
            f"| {key} | {row['valid']}/{row['n']} | {row['base_correct']} | "
            f"{row['correct']} | {row['rescues']} | {row['damages']} | "
            f"{row['tool_rows']} | {row['tool_calls']} | {row['base_total_tokens']} | "
            f"{row['route_total_tokens']} | {row['total_tokens']} | {multiplier} |"
        )
    lines.extend(
        [
            "",
            "No artificial token cap was passed. Tool use is derived from JSONL events, not model self-report.",
            "The two arms contain different questions; accuracy differences are descriptive, not causal.",
            "Strict normalized exact match may reject mathematically equivalent answers.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(pretty(result["summaries"]))


def audit() -> None:
    expected = build_results()
    observed = read_json(RESULTS)
    if expected != observed:
        raise ProtocolError("independent recomputation differs from results.json")
    if len(observed["rows"]) != EXPECTED_CALLS:
        raise ProtocolError("result row conservation failed")
    for row in observed["rows"]:
        receipt = read_json(RECEIPTS / f"{row['unit_id']}.json")
        if receipt["arm"] == "FOIL" and receipt["actual_tool_calls"]:
            raise ProtocolError(f"no-tools row used a tool: {row['unit_id']}")
        if receipt["artificial_token_cap"] is not None:
            raise ProtocolError(f"token cap present: {row['unit_id']}")
    print(
        f"audit PASS rows={EXPECTED_CALLS} calls={observed['provider_calls']} "
        f"results_sha256={sha256_file(RESULTS)}"
    )


def self_test() -> None:
    synthetic = []
    for index in range(23):
        synthetic.append(
            {
                "id": f"fresh-{index:02d}",
                "question": "x" * (1000 - index),
                "answer_type": "exactMatch",
                "answer": str(index),
                "category": "Math" if index % 2 else "Other",
            }
        )
    items = select_items(synthetic)
    assert len(items) == 20
    assert Counter(item["arm"] for item in items) == Counter(
        {"FOIL": 10, "FOIL_TOOLS": 10}
    )
    assert policy_document("FOIL")["host_route"] == "FULL"
    assert policy_document("FOIL")["retrieval_allowed"] is False
    assert policy_document("FOIL_TOOLS")["host_route"] == "FULL"
    assert policy_document("FOIL_TOOLS")["retrieval_allowed"] is True
    no_tools_argv = build_argv("LUNA_LOW", "FOIL", "route", Path("x"), Path("y"))
    tools_argv = build_argv("LUNA_HIGH", "FOIL_TOOLS", "route", Path("x"), Path("y"))
    base_argv = build_argv("TERRA_HIGH", "FOIL_TOOLS", "base", Path("x"), Path("y"))
    assert "--search" not in no_tools_argv and "--search" in tools_argv
    assert "--search" not in base_argv
    assert not any("token" in value.casefold() for value in tools_argv)
    stream = parse_stream(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.started",
                        "item": {"id": "w", "type": "web_search", "query": ""},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "w",
                            "type": "web_search",
                            "query": "test query",
                            "action": {"type": "search", "query": "test query"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 10, "output_tokens": 2},
                    }
                ),
            ]
        )
    )
    assert len(stream["tools"]) == 1
    assert stream["tools"][0]["query"] == "test query"
    assert stream["usage"] == {"input_tokens": 10, "output_tokens": 2}
    good = {
        "answer": "42",
        "route": "FULL",
        "gap_kind": "EVIDENCE_GAP",
        "tool_decision": "USED_WEB_SEARCH",
        "tool_use_rationale": "checked source",
        "evidence_urls": ["https://example.test"],
        "confidence": 80,
    }
    assert parse_answer(json.dumps(good))[1] is None
    assert not _validate_tool_claim("FOIL_TOOLS", good, list(stream["tools"]))
    assert _validate_tool_claim("FOIL", good, list(stream["tools"]))
    print("self-test PASS")


def check() -> None:
    manifest, items = validate_lock()
    print(
        pretty(
            {
                "items": len(items),
                "arm_counts": dict(sorted(Counter(item["arm"] for item in items).items())),
                "category_counts": dict(
                    sorted(Counter(item["category"] for item in items).items())
                ),
                "units": len(manifest["units"]),
                "configs": manifest["configs"],
                "artificial_token_cap": manifest["artificial_token_cap"],
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("prepare", "self-test", "check", "run", "score", "audit")
    )
    args = parser.parse_args()
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
