#!/usr/bin/env python3
"""Frozen, provider-bound Stage-2 blind-rival diagnostic pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools"
for candidate in (str(TOOLS), str(HERE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import foil_adaptive_two_benchmark_pilot as adaptive  # noqa: E402
from foil_rps_blind_rival import (  # noqa: E402
    BlindRivalRequest,
    ComparatorKind,
    RivalTask,
    Stage2Action,
    build_blind_rival_request,
    digest,
    finalize_stage2,
    make_rival_receipt,
)
from foil_rps_host_verifier import (  # noqa: E402
    HostTaskDescriptor,
    HostTaskType,
    Stage1Outcome,
    select_check,
    verify_answer,
)
from foil_rps_v063 import (  # noqa: E402
    RPSV063Action,
    RPSV063Policy,
    evaluate_unique_host_result,
)

SOURCE = ROOT / "benchmark_runs" / "2026-08-25" / "adaptive_two_benchmark"
SOURCE_ITEMS = SOURCE / "items.json"
SOURCE_PREDICTIONS = SOURCE / "predictions.json"
SOURCE_RESULTS = SOURCE / "results.json"
SOURCE_BASE_RECEIPTS = SOURCE / "receipts" / "base"

OUT = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v063_stage2_small"
REQUESTS = OUT / "requests.json"
MANIFEST = OUT / "manifest.json"
PREDICTIONS = OUT / "predictions.json"
REPORT = OUT / "report.json"
RECEIPTS = OUT / "receipts"
PRIVATE = OUT / "private"

PROTOCOL = ROOT / "benchmarks" / "protocols" / "FOIL_RPS_V063_STAGE2_SMALL_PROTOCOL.md"
SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_rps_stage2_answer_schema.json"
CORE = ROOT / "tools" / "foil_rps_blind_rival.py"
HOST = ROOT / "tools" / "foil_rps_host_verifier.py"
AUTHORITY = ROOT / "tools" / "foil_rps_v063.py"

CONFIGS: dict[str, dict[str, str]] = {
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low"},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high"},
    "SOL_LOW": {"model": "gpt-5.6-sol", "effort": "low"},
}
MAX_STAGE2_CALLS = 3
TIMEOUT_SECONDS = 900
ABSTENTION_CEILING = 0.20
TOTAL_TOKEN_MULTIPLIER_CEILING = 1.35


class ProtocolError(RuntimeError):
    pass


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8", newline="\n")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _items(document: object) -> list[dict[str, object]]:
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ProtocolError("items document must contain an items list")
    rows = document["items"]
    if not all(isinstance(row, dict) for row in rows):
        raise ProtocolError("invalid item row")
    selected = [row for row in rows if row.get("benchmark") == "PROCESSBENCH_GSM8K"]
    if len(selected) != 2 or len({row.get("id") for row in selected}) != 2:
        raise ProtocolError("Stage-2 pilot requires exactly two ProcessBench items")
    return sorted(selected, key=lambda row: str(row["id"]))


def _task_payload(item: Mapping[str, object]) -> dict[str, object]:
    steps = item.get("steps")
    if not isinstance(steps, list) or not steps or not all(
        isinstance(step, str) and step.strip() for step in steps
    ):
        raise ProtocolError("ProcessBench item has invalid steps")
    problem = item.get("problem")
    if not isinstance(problem, str) or not problem.strip():
        raise ProtocolError("ProcessBench item has invalid problem")
    return {"problem": problem, "steps": steps}


def request_to_dict(item_id: str, request: BlindRivalRequest) -> dict[str, object]:
    return {
        "item_id": item_id,
        "task_digest": request.task_digest,
        "answer_form_digest": request.answer_form_digest,
        "comparator": request.comparator.value,
        "method_id": request.method_id,
        "prompt": request.prompt,
        "prompt_digest": request.prompt_digest,
        "request_digest": request.request_digest,
        "incumbent_withheld": True,
    }


def request_from_dict(value: object) -> BlindRivalRequest:
    if not isinstance(value, dict) or set(value) != {
        "item_id",
        "task_digest",
        "answer_form_digest",
        "comparator",
        "method_id",
        "prompt",
        "prompt_digest",
        "request_digest",
        "incumbent_withheld",
    }:
        raise ProtocolError("blind request has unknown or missing fields")
    return BlindRivalRequest(
        task_digest=value["task_digest"],
        answer_form_digest=value["answer_form_digest"],
        comparator=ComparatorKind(value["comparator"]),
        method_id=value["method_id"],
        prompt=value["prompt"],
        prompt_digest=value["prompt_digest"],
        request_digest=value["request_digest"],
        incumbent_withheld=value["incumbent_withheld"],
    )


def build_requests_document(items_document: object) -> dict[str, object]:
    answer_form_digest = digest(
        {"answer": "STRING", "abstain": "BOOLEAN", "method_summary": "STRING"}
    )
    rows: list[dict[str, object]] = []
    for item in _items(items_document):
        payload = _task_payload(item)
        request = build_blind_rival_request(
            RivalTask(
                task_digest=digest(payload),
                answer_form_digest=answer_form_digest,
                benchmark="PROCESSBENCH_GSM8K",
                problem=payload["problem"],
                steps=tuple(payload["steps"]),
                comparator=ComparatorKind.PROCESSBENCH_FIRST_ERROR,
            )
        )
        rows.append(request_to_dict(str(item["id"]), request))
    document: dict[str, object] = {
        "schema": "foil.rps-stage2-requests.v1",
        "created_from": "items_only_before_a0",
        "requests": rows,
        "request_count": len(rows),
    }
    document["requests_sha256"] = digest(document)
    return document


def build_manifest(requests_document: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema": "foil.rps-v063-stage2-manifest.v1",
        "classification": "PREREGISTERED_DIAGNOSTIC_SMOKE_ONLY",
        "source_items_sha256": sha256_file(SOURCE_ITEMS),
        "source_predictions_sha256": sha256_file(SOURCE_PREDICTIONS),
        "source_base_receipts": 6,
        "requests_sha256": requests_document["requests_sha256"],
        "protocol_sha256": sha256_file(PROTOCOL),
        "schema_sha256": sha256_file(SCHEMA),
        "runner_sha256": sha256_file(Path(__file__)),
        "core_sha256": sha256_file(CORE),
        "host_sha256": sha256_file(HOST),
        "authority_sha256": sha256_file(AUTHORITY),
        "configs": CONFIGS,
        "maximum_stage2_calls": MAX_STAGE2_CALLS,
        "abstention_ceiling": ABSTENTION_CEILING,
        "total_token_multiplier_ceiling": TOTAL_TOKEN_MULTIPLIER_CEILING,
        "production_authorized": False,
        "promotion_authorized": False,
        "non_claims": ["calibration", "promotion", "frontier efficacy"],
    }


def cmd_prepare() -> int:
    for path in (REQUESTS, MANIFEST, PREDICTIONS, REPORT):
        if path.exists():
            raise ProtocolError(f"prepare refuses existing artifact: {path}")
    requests_document = build_requests_document(read_json(SOURCE_ITEMS))
    write_json(REQUESTS, requests_document)
    write_json(MANIFEST, build_manifest(requests_document))
    print(f"prepared_requests={requests_document['request_count']}")
    print(f"requests_sha256={requests_document['requests_sha256']}")
    return 0


def parse_rival_answer(text: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(value, dict) or set(value) != {
        "answer",
        "abstain",
        "method_summary",
    }:
        return None, "last output has unknown or missing fields"
    if not isinstance(value["answer"], str) or not 1 <= len(value["answer"]) <= 200:
        return None, "answer is not bounded non-empty text"
    if not isinstance(value["abstain"], bool):
        return None, "abstain is not boolean"
    if not isinstance(value["method_summary"], str) or not 1 <= len(
        value["method_summary"].strip()
    ) <= 400:
        return None, "method_summary is not bounded non-empty text"
    return value, None


def build_argv(config_id: str, workdir: Path, last: Path) -> list[str]:
    config = CONFIGS[config_id]
    return [
        adaptive.codex_executable(),
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
        str(SCHEMA),
        "--json",
        "-o",
        str(last),
        "-C",
        str(workdir),
        "-",
    ]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def frozen_commit() -> str:
    artifacts = (
        PROTOCOL,
        SCHEMA,
        Path(__file__),
        CORE,
        HOST,
        AUTHORITY,
        REQUESTS,
        MANIFEST,
        SOURCE_ITEMS,
        SOURCE_PREDICTIONS,
    )
    for path in artifacts:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        if _git("ls-files", "--error-unmatch", relative).returncode:
            raise ProtocolError(f"frozen artifact is not committed: {relative}")
        if _git("diff", "--quiet", "HEAD", "--", relative).returncode:
            raise ProtocolError(f"frozen artifact differs from HEAD: {relative}")
    head = _git("rev-parse", "HEAD")
    if head.returncode:
        raise ProtocolError("cannot resolve frozen commit")
    return head.stdout.strip()


def _public_receipt_path(unit_id: str) -> Path:
    return RECEIPTS / f"{unit_id}.json"


def execute_stage2_call(
    unit_id: str,
    config_id: str,
    request: BlindRivalRequest,
    *,
    frozen: str,
    cli_version: str,
) -> dict[str, object]:
    receipt_path = _public_receipt_path(unit_id)
    if receipt_path.exists():
        existing = read_json(receipt_path)
        if not isinstance(existing, dict) or existing.get("valid") is not True:
            raise ProtocolError(f"invalid existing receipt: {unit_id}")
        if existing.get("request_digest") != request.request_digest:
            raise ProtocolError(f"existing receipt request mismatch: {unit_id}")
        return existing
    if len(list(RECEIPTS.glob("*.json"))) >= MAX_STAGE2_CALLS:
        raise ProtocolError("hard Stage-2 call cap reached")
    raw = PRIVATE / unit_id
    if raw.exists():
        raise ProtocolError(f"orphaned Stage-2 attempt prohibits retry: {unit_id}")
    raw.mkdir(parents=True)
    (raw / "rival_prompt.txt").write_text(request.prompt, encoding="utf-8")
    last = raw / "last.json"
    started = now()
    clock = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="foil-rps-stage2-") as temporary:
        try:
            process = subprocess.run(
                build_argv(config_id, Path(temporary), last),
                input=request.prompt,
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
    (raw / "events.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
    (raw / "stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
    last_text = last.read_text(encoding="utf-8") if last.exists() else ""
    stream = adaptive.parse_stream(stdout)
    answer, answer_error = parse_rival_answer(last_text)
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
    config = CONFIGS[config_id]
    receipt: dict[str, object] = {
        "schema": "foil.rps-stage2-provider-receipt.v1",
        "unit_id": unit_id,
        "config_id": config_id,
        "model": config["model"],
        "effort": config["effort"],
        "codex_version": cli_version,
        "pre_call_commit": frozen,
        "started_at": started,
        "finished_at": now(),
        "wall_seconds": time.monotonic() - clock,
        "returncode": returncode,
        "timed_out": timed_out,
        "request_digest": request.request_digest,
        "prompt_sha256": sha256_text(request.prompt),
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "last_output_sha256": sha256_text(last_text),
        "event_types": stream["event_types"],
        "usage": stream["usage"],
        "answer": answer,
        "valid": not invalid,
        "invalid_reasons": invalid,
        "tool_calls": len(stream["tool_events"]),
        "production_authorized": False,
    }
    write_json(receipt_path, receipt)
    if invalid:
        raise ProtocolError(f"Stage-2 call failed without retry: {unit_id}: {invalid}")
    return receipt


def _prediction_rows(document: object) -> list[dict[str, object]]:
    if not isinstance(document, dict) or not isinstance(
        document.get("predictions"), list
    ):
        raise ProtocolError("source predictions document is invalid")
    rows = [
        row
        for row in document["predictions"]
        if isinstance(row, dict) and row.get("benchmark") == "PROCESSBENCH_GSM8K"
    ]
    if len(rows) != 6 or len({row.get("unit_id") for row in rows}) != 6:
        raise ProtocolError("expected exactly six frozen ProcessBench predictions")
    return sorted(rows, key=lambda row: str(row["unit_id"]))


def _base_receipt(unit_id: str, prediction: Mapping[str, object]) -> dict[str, object]:
    path = SOURCE_BASE_RECEIPTS / f"{unit_id}.json"
    if sha256_file(path) != prediction.get("base_receipt_sha256"):
        raise ProtocolError(f"base receipt digest mismatch: {unit_id}")
    receipt = read_json(path)
    if not isinstance(receipt, dict) or receipt.get("valid") is not True:
        raise ProtocolError(f"invalid base receipt: {unit_id}")
    if receipt.get("answer") != prediction.get("base"):
        raise ProtocolError(f"base answer/receipt mismatch: {unit_id}")
    return receipt


def _usage(receipt: Mapping[str, object]) -> tuple[int, int]:
    usage = receipt.get("usage")
    if not isinstance(usage, dict):
        raise ProtocolError("receipt lacks usage")
    values: list[int] = []
    for name in ("input_tokens", "output_tokens"):
        value = usage.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ProtocolError(f"invalid {name}")
        values.append(value)
    return values[0], values[1]


def _selected_host_check(item: Mapping[str, object], request: BlindRivalRequest):
    payload = _task_payload(item)
    if request.task_digest != digest(payload):
        raise ProtocolError("request/task digest mismatch")
    return select_check(
        HostTaskDescriptor(
            task_digest=request.task_digest,
            answer_form_digest=request.answer_form_digest,
            task_type=HostTaskType.PROCESSBENCH_FIRST_ERROR,
            source_steps=tuple(payload["steps"]),
        )
    )


def cmd_run() -> int:
    if PREDICTIONS.exists() or REPORT.exists():
        raise ProtocolError("run refuses existing predictions/report")
    frozen = frozen_commit()
    cli_version = adaptive.codex_version()
    items = {str(item["id"]): item for item in _items(read_json(SOURCE_ITEMS))}
    request_doc = read_json(REQUESTS)
    if not isinstance(request_doc, dict) or request_doc.get("schema") != "foil.rps-stage2-requests.v1":
        raise ProtocolError("request document schema mismatch")
    requests = {
        str(row["item_id"]): request_from_dict(row)
        for row in request_doc["requests"]
    }
    output_rows: list[dict[str, object]] = []
    for prediction in _prediction_rows(read_json(SOURCE_PREDICTIONS)):
        unit_id = str(prediction["unit_id"])
        item_id = str(prediction["item_id"])
        config_id = str(prediction["config_id"])
        if config_id not in CONFIGS:
            raise ProtocolError(f"unknown config: {config_id}")
        item = items[item_id]
        request = requests[item_id]
        base = prediction.get("base")
        if not isinstance(base, dict) or set(base) != {"answer", "abstain"}:
            raise ProtocolError(f"invalid frozen base answer: {unit_id}")
        base_receipt = _base_receipt(unit_id, prediction)
        base_prompt = adaptive.item_prompt(item)
        if base_receipt.get("prompt_sha256") != sha256_text(base_prompt):
            raise ProtocolError(f"reconstructed base prompt mismatch: {unit_id}")
        base_input, base_output = _usage(base_receipt)
        selected = _selected_host_check(item, request)
        stage1 = verify_answer(selected, base)
        provider_receipt: dict[str, object] | None = None
        rival_answer: dict[str, object] | None = None
        stage2_trace: dict[str, object] | None = None
        added_input = added_output = 0
        if stage1.outcome in {Stage1Outcome.NOT_APPLICABLE, Stage1Outcome.UNCERTAIN}:
            provider_receipt = execute_stage2_call(
                unit_id,
                config_id,
                request,
                frozen=frozen,
                cli_version=cli_version,
            )
            rival_answer = provider_receipt["answer"]
            if not isinstance(rival_answer, dict):
                raise ProtocolError(f"missing rival answer: {unit_id}")
            added_input, added_output = _usage(provider_receipt)
            rival_receipt = make_rival_receipt(
                request,
                rival_answer,
                model_route_digest=digest(CONFIGS[config_id]),
                input_tokens=added_input,
                output_tokens=added_output,
            )
            stage2 = finalize_stage2(request, base, rival_answer, rival_receipt)
            stage2_trace = stage2.trace()
            final = (
                base
                if stage2.action is Stage2Action.KEEP_BASE
                else {"answer": "ABSTAIN", "abstain": True}
            )
            final_action = stage2.action.value
        else:
            expected = selected.spec.get("expected_answer")
            host_candidate = (
                {"answer": expected, "abstain": False}
                if isinstance(expected, str)
                else None
            )
            active = evaluate_unique_host_result(
                selected,
                stage1,
                host_candidate,
                policy=RPSV063Policy(enabled=True),
            )
            if active.action is RPSV063Action.SELECT_HOST_RESULT:
                if host_candidate is None:
                    raise ProtocolError("host selection lacks materialized candidate")
                final = host_candidate
            else:
                final = base
            final_action = active.action.value
        private_row = {
            "schema": "foil.rps-stage2-private-row.v1",
            "unit_id": unit_id,
            "base_prompt": base_prompt,
            "base_answer": base,
            "rival_prompt": request.prompt if provider_receipt else None,
            "rival_answer": rival_answer,
            "stage2_trace": stage2_trace,
            "base_usage": base_receipt["usage"],
            "rival_usage": provider_receipt["usage"] if provider_receipt else None,
        }
        write_json(PRIVATE / "row_receipts" / f"{unit_id}.json", private_row)
        output_rows.append(
            {
                "unit_id": unit_id,
                "item_id": item_id,
                "config_id": config_id,
                "base": base,
                "base_receipt_sha256": prediction["base_receipt_sha256"],
                "base_input_tokens": base_input,
                "base_output_tokens": base_output,
                "stage1_outcome": stage1.outcome.value,
                "stage1_reason": stage1.reason,
                "request_digest": request.request_digest,
                "rival": rival_answer,
                "rival_receipt_sha256": (
                    sha256_file(_public_receipt_path(unit_id))
                    if provider_receipt
                    else None
                ),
                "stage2": stage2_trace,
                "final": final,
                "final_action": final_action,
                "added_input_tokens": added_input,
                "added_output_tokens": added_output,
                "provider_calls": int(provider_receipt is not None),
                "tool_calls": 0,
                "production_authorized": False,
            }
        )
    predictions: dict[str, object] = {
        "schema": "foil.rps-v063-stage2-predictions.v1",
        "classification": "FROZEN_A0_FRESH_BLIND_RIVAL_DIAGNOSTIC",
        "pre_call_commit": frozen,
        "source_items_sha256": sha256_file(SOURCE_ITEMS),
        "source_predictions_sha256": sha256_file(SOURCE_PREDICTIONS),
        "rows": output_rows,
        "provider_calls": sum(int(row["provider_calls"]) for row in output_rows),
        "tool_calls": 0,
        "profile_writes": 0,
        "production_activation_changed": False,
    }
    predictions["predictions_sha256"] = digest(predictions)
    write_json(PREDICTIONS, predictions)
    print(f"rows={len(output_rows)}")
    print(f"provider_calls={predictions['provider_calls']}")
    print(f"predictions_sha256={predictions['predictions_sha256']}")
    return 0


def _correct(answer: object, gold: str) -> bool:
    return (
        isinstance(answer, dict)
        and set(answer) == {"answer", "abstain"}
        and answer["abstain"] is False
        and isinstance(answer["answer"], str)
        and answer["answer"].strip() == gold.strip()
    )


def score_documents(predictions: object, results: object) -> dict[str, object]:
    if not isinstance(predictions, dict) or not isinstance(predictions.get("rows"), list):
        raise ProtocolError("predictions document is invalid")
    if not isinstance(results, dict) or not isinstance(results.get("rows"), list):
        raise ProtocolError("results document is invalid")
    gold_rows = {
        str(row["unit_id"]): row
        for row in results["rows"]
        if isinstance(row, dict) and row.get("benchmark") == "PROCESSBENCH_GSM8K"
    }
    scored: list[dict[str, object]] = []
    multipliers: list[float] = []
    base_total_sum = stage_total_sum = 0
    for row in predictions["rows"]:
        if not isinstance(row, dict) or str(row.get("unit_id")) not in gold_rows:
            raise ProtocolError("prediction/gold unit mismatch")
        gold_row = gold_rows[str(row["unit_id"])]
        gold = gold_row.get("gold")
        if not isinstance(gold, str):
            raise ProtocolError("gold must be text")
        base_ok = _correct(row.get("base"), gold)
        final_ok = _correct(row.get("final"), gold)
        base_total = int(row["base_input_tokens"]) + int(row["base_output_tokens"])
        added_total = int(row["added_input_tokens"]) + int(row["added_output_tokens"])
        if base_total <= 0 or added_total < 0:
            raise ProtocolError("invalid token denominator")
        multiplier = (base_total + added_total) / base_total
        multipliers.append(multiplier)
        base_total_sum += base_total
        stage_total_sum += base_total + added_total
        stage2 = row.get("stage2")
        outcome = stage2.get("outcome") if isinstance(stage2, dict) else None
        scored.append(
            {
                "unit_id": row["unit_id"],
                "item_id": row["item_id"],
                "config_id": row["config_id"],
                "gold": gold,
                "base": row["base"],
                "base_correct": base_ok,
                "final": row["final"],
                "final_correct": final_ok,
                "rescued": (not base_ok and final_ok),
                "damaged": (base_ok and not final_ok),
                "stage2_outcome": outcome,
                "stage2_triggered": stage2 is not None,
                "final_abstained": bool(
                    isinstance(row.get("final"), dict)
                    and row["final"].get("abstain") is True
                ),
                "total_token_multiplier": multiplier,
            }
        )
    triggers = [row for row in scored if row["stage2_triggered"]]
    agreements = [row for row in triggers if row["stage2_outcome"] == "AGREE"]
    triggered_abstentions = sum(bool(row["final_abstained"]) for row in triggers)
    abstention_rate = triggered_abstentions / len(triggers) if triggers else 0.0
    aggregate_multiplier = stage_total_sum / base_total_sum
    damages = sum(bool(row["damaged"]) for row in scored)
    summary = {
        "rows": len(scored),
        "questions": len({row["item_id"] for row in scored}),
        "configs": len({row["config_id"] for row in scored}),
        "base_correct": sum(bool(row["base_correct"]) for row in scored),
        "final_correct": sum(bool(row["final_correct"]) for row in scored),
        "rescues": sum(bool(row["rescued"]) for row in scored),
        "damages": damages,
        "stage2_triggers": len(triggers),
        "stage2_agreements": len(agreements),
        "stage2_abstentions": triggered_abstentions,
        "stage2_abstention_rate": abstention_rate,
        "agreement_correct": sum(bool(row["final_correct"]) for row in agreements),
        "agreement_total": len(agreements),
        "mean_total_token_multiplier": statistics.fmean(multipliers),
        "median_total_token_multiplier": statistics.median(multipliers),
        "aggregate_total_token_multiplier": aggregate_multiplier,
        "provider_calls": int(predictions.get("provider_calls", -1)),
        "tool_calls": int(predictions.get("tool_calls", -1)),
    }
    kills = {
        "damage": damages > 0,
        "triggered_abstention": abstention_rate > ABSTENTION_CEILING,
        "total_token_cost": aggregate_multiplier > TOTAL_TOKEN_MULTIPLIER_CEILING,
        "provider_or_tool_cap": (
            summary["provider_calls"] > MAX_STAGE2_CALLS or summary["tool_calls"] != 0
        ),
    }
    report: dict[str, object] = {
        "schema": "foil.rps-v063-stage2-report.v1",
        "classification": (
            "DIAGNOSTIC_SMOKE_FAIL" if any(kills.values()) else "DIAGNOSTIC_SMOKE_PASS"
        ),
        "summary": summary,
        "kill_conditions": kills,
        "thresholds": {
            "stage2_abstention_rate_max": ABSTENTION_CEILING,
            "aggregate_total_token_multiplier_max": TOTAL_TOKEN_MULTIPLIER_CEILING,
        },
        "rows": scored,
        "production_authorized": False,
        "promotion_authorized": False,
        "non_claims": [
            "This two-question diagnostic is not calibration or promotion evidence.",
            "A reused frozen A0 does not estimate fresh paired efficacy.",
            "Agreement is correlated supporting evidence, not proof.",
        ],
    }
    report["report_sha256"] = digest(report)
    return report


def _require_committed_predictions() -> str:
    relative = str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/")
    if _git("ls-files", "--error-unmatch", relative).returncode:
        raise ProtocolError("predictions must be committed before scoring")
    if _git("diff", "--quiet", "HEAD", "--", relative).returncode:
        raise ProtocolError("predictions differ from committed version")
    return _git("rev-parse", "HEAD").stdout.strip()


def cmd_score() -> int:
    if REPORT.exists():
        raise ProtocolError("score refuses existing report")
    score_commit = _require_committed_predictions()
    report = score_documents(read_json(PREDICTIONS), read_json(SOURCE_RESULTS))
    report["score_commit"] = score_commit
    unhashed = dict(report)
    unhashed.pop("report_sha256")
    report["report_sha256"] = digest(unhashed)
    write_json(REPORT, report)
    print(canonical(report["summary"]))
    print(f"classification={report['classification']}")
    print(f"report_sha256={report['report_sha256']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "score"))
    args = parser.parse_args()
    if args.command == "prepare":
        return cmd_prepare()
    if args.command == "run":
        return cmd_run()
    return cmd_score()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtocolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
