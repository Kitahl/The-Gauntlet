"""Sealed Codex BASE-vs-FOIL GPQA experiment (2026-08-24).

Run order: prepare, check, dry-run, controls, run, commit predictions/receipts,
then score.  Scoring refuses to open gold until the complete prediction ledger is
tracked, committed, and clean. There are no retries and the hard call cap is 42.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-24"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "dose_receipts"
ITEMS = OUT / "dose_items.json"
MANIFEST = OUT / "dose_manifest.json"
CONDITION_MAP = OUT / "dose_condition_map.sealed.json"
SCHEMA_FILE = OUT / "answer_schema.json"
LOCK = OUT / "dose_config_lock.json"
PREDICTIONS = OUT / "dose_predictions.json"
RESULTS = OUT / "dose_results.json"
REPORT = OUT / "dose_report.md"
PROTOCOL = ROOT / "benchmarks" / "FOIL_CODEX_DOSE_RESPONSE_SMALL_PILOT.md"
SKILL_FILE = ROOT / "skills" / "foil" / "SKILL.md"
EXCLUSION_MANIFEST = OUT.parent / "2026-08-23" / "four_config_gpqa_manifest.json"

SOURCE_REVISION = "56686c06f5e19865c153de0fdb11be3890014df7"
SOURCE_URL = (
    "https://raw.githubusercontent.com/idavidrein/gpqa/"
    f"{SOURCE_REVISION}/dataset.zip"
)
ZIP_PASSWORD = b"deserted-untie-orchid"
SEED = 20260824
TARGET = 3
EXPECTED_ELIGIBLE = 25
EXPECTED_UNITS = 36
EXPECTED_PAIRS = 18
MAX_CALLS = 42
TIMEOUT_SECONDS = 600
LETTERS = "ABCD"

CONFIGS: dict[str, dict[str, str | int]] = {
    "LUNA_LOW": {"model": "gpt-5.6-luna", "effort": "low", "rank": 0},
    "LUNA_HIGH": {"model": "gpt-5.6-luna", "effort": "high", "rank": 1},
    "TERRA_LOW": {"model": "gpt-5.6-terra", "effort": "low", "rank": 2},
    "TERRA_HIGH": {"model": "gpt-5.6-terra", "effort": "high", "rank": 3},
    "SOL_LOW": {"model": "gpt-5.6-sol", "effort": "low", "rank": 4},
    "SOL_HIGH": {"model": "gpt-5.6-sol", "effort": "high", "rank": 5},
}


class ProtocolError(RuntimeError):
    """A frozen invariant failed; continuing would invalidate the experiment."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def write_json(path: Path, payload: Any) -> None:
    write_text(path, canonical_json(payload))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fetch_archive() -> bytes:
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "FOIL-dose-response/2026-08-24"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def load_rows(
    archive_bytes: bytes | None = None, *, expected_sha256: str | None = None
) -> list[dict[str, str]]:
    payload = fetch_archive() if archive_bytes is None else archive_bytes
    actual_sha256 = sha256_bytes(payload)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ProtocolError(
            f"pinned source archive digest mismatch: {actual_sha256} != {expected_sha256}"
        )
    archive = zipfile.ZipFile(io.BytesIO(payload))
    names = sorted(
        name
        for name in archive.namelist()
        if name.lower().endswith(".csv") and "diamond" in name.lower()
    )
    if not names:
        raise ProtocolError("pinned archive has no GPQA-Diamond CSV")
    raw = archive.read(names[0], pwd=ZIP_PASSWORD).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    required = {
        "Question",
        "Correct Answer",
        "Incorrect Answer 1",
        "Incorrect Answer 2",
        "Incorrect Answer 3",
        "Expert Validator Accuracy",
        "Non-Expert Validator Accuracy",
        "Writer's Difficulty Estimate",
    }
    if not rows or not required.issubset(rows[0]):
        raise ProtocolError(f"unexpected GPQA fields: {list(rows[0]) if rows else []}")
    return rows


def normalize_space(value: object) -> str:
    return " ".join(str(value).split())


def parse_accuracy(value: object) -> float:
    text = str(value).strip().rstrip("%")
    number = float(text)
    return number / 100.0 if number > 1.0 else number


def development_ids() -> set[str]:
    payload = read_json(EXCLUSION_MANIFEST)
    return {str(unit["item_id"]) for unit in payload["units"]}


def hard_difficulty(value: object) -> bool:
    label = str(value).strip().lower()
    return label.startswith(
        (
            "hard undergraduate level",
            "hard graduate level",
            "post-graduate level or harder",
        )
    )


def eligible_rows(rows: list[dict[str, str]]) -> list[tuple[int, dict[str, str]]]:
    excluded = development_ids()
    candidates: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(rows):
        question = normalize_space(row["Question"])
        item_id = f"gpqa-diamond-{index:03d}"
        if (
            parse_accuracy(row["Expert Validator Accuracy"]) <= 0.50
            and parse_accuracy(row["Non-Expert Validator Accuracy"]) <= 0.34
            and hard_difficulty(row["Writer's Difficulty Estimate"])
            and len(question) < 900
            and item_id not in excluded
        ):
            candidates.append((index, row))
    candidates.sort(
        key=lambda pair: (
            parse_accuracy(pair[1]["Expert Validator Accuracy"]),
            len(normalize_space(pair[1]["Question"])),
            pair[0],
        )
    )
    return candidates


def shuffled_options(index: int, row: dict[str, str]) -> tuple[dict[str, str], str]:
    options: list[tuple[str, bool]] = [
        (normalize_space(row["Correct Answer"]), True),
        (normalize_space(row["Incorrect Answer 1"]), False),
        (normalize_space(row["Incorrect Answer 2"]), False),
        (normalize_space(row["Incorrect Answer 3"]), False),
    ]
    random.Random(SEED * 1000 + index).shuffle(options)
    choices = {LETTERS[position]: answer for position, (answer, _) in enumerate(options)}
    gold = LETTERS[next(i for i, (_, correct) in enumerate(options) if correct)]
    return choices, gold


def public_items(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates = eligible_rows(rows)
    if len(candidates) != EXPECTED_ELIGIBLE:
        raise ProtocolError(
            f"expected {EXPECTED_ELIGIBLE} eligible rows at pinned revision, got {len(candidates)}"
        )
    items: list[dict[str, Any]] = []
    for index, row in candidates[:TARGET]:
        choices, _ = shuffled_options(index, row)
        item = {
            "id": f"gpqa-diamond-{index:03d}",
            "source_index": index,
            "question": normalize_space(row["Question"]),
            "choices": choices,
            "expert_accuracy": parse_accuracy(row["Expert Validator Accuracy"]),
            "nonexpert_accuracy": parse_accuracy(row["Non-Expert Validator Accuracy"]),
            "difficulty": row["Writer's Difficulty Estimate"].strip(),
        }
        item["item_sha256"] = sha256_text(canonical_json(item))
        items.append(item)
    return items


def condition_payload() -> dict[str, Any]:
    values = ["BASE", "FOIL"]
    random.Random(SEED).shuffle(values)
    return {
        "schema": "foil-codex-dose-condition-map/v1",
        "seed": SEED,
        "map": {"A": values[0], "B": values[1]},
        "boundary": "Committed before calls; prevents post-hoc relabelling, not operator blindness.",
    }


def answer_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": list(LETTERS)}},
        "required": ["answer"],
        "additionalProperties": False,
    }


COMMON_SUFFIX = (
    "Closed book. Do not use tools, files, the network, or outside context. "
    "Choose exactly one option. Return only the JSON object required by the response schema."
)
CONTROL_PROMPT = (
    "Positive control. Return the answer A. Do not use tools, files, the network, "
    "or outside context. Return only the JSON object required by the response schema."
)


def item_body(item: dict[str, Any]) -> str:
    choices = "\n".join(f"{letter}) {item['choices'][letter]}" for letter in LETTERS)
    return f"{item['question']}\n\n{choices}\n\n{COMMON_SUFFIX}"


def prompt_for(item: dict[str, Any], arm: str, skill_text: str | None = None) -> str:
    body = item_body(item)
    if arm == "BASE":
        return body
    if arm != "FOIL":
        raise ValueError(f"unknown arm: {arm}")
    skill = SKILL_FILE.read_text(encoding="utf-8") if skill_text is None else skill_text
    return (
        "/foil solve\n\n"
        "Apply the following frozen public FOIL skill contract to this task. "
        "No user profile or persistent state is available.\n\n"
        "<foil_skill_contract>\n"
        f"{skill.rstrip()}\n"
        "</foil_skill_contract>\n\n"
        f"{body}"
    )


def build_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = condition_payload()["map"]
    units: list[dict[str, Any]] = []
    for item in items:
        for config_id, config in CONFIGS.items():
            for condition_id in sorted(mapping):
                arm = mapping[condition_id]
                prompt = prompt_for(item, arm)
                units.append(
                    {
                        "unit_id": f"{item['id']}-{config_id}-{condition_id}",
                        "item_id": item["id"],
                        "config_id": config_id,
                        "model": config["model"],
                        "effort": config["effort"],
                        "rank": config["rank"],
                        "condition_id": condition_id,
                        "item_sha256": item["item_sha256"],
                        "prompt_sha256": sha256_text(prompt),
                    }
                )
    random.Random(SEED).shuffle(units)
    for order, unit in enumerate(units):
        unit["order"] = order
    return units


def build_manifest(items: list[dict[str, Any]], *, source_archive_sha256: str) -> dict[str, Any]:
    return {
        "schema": "foil-codex-dose-manifest/v1",
        "created_at": now(),
        "source_url": SOURCE_URL,
        "source_revision": SOURCE_REVISION,
        "source_archive_sha256": source_archive_sha256,
        "exclusion_manifest_sha256": sha256_file(EXCLUSION_MANIFEST),
        "selection_seed": SEED,
        "order_seed": SEED,
        "eligible_count": EXPECTED_ELIGIBLE,
        "sample_n": TARGET,
        "configs": CONFIGS,
        "replicates": 1,
        "call_cap": MAX_CALLS,
        "scored_call_count": TARGET * len(CONFIGS) * 2,
        "control_call_count": len(CONFIGS),
        "condition_map_sha256": sha256_text(canonical_json(condition_payload())),
        "items_sha256": sha256_text(
            canonical_json({"schema": "foil-codex-dose-items/v1", "items": items})
        ),
        "skill_sha256": sha256_file(SKILL_FILE),
        "protocol_sha256": sha256_file(PROTOCOL),
        "runner_sha256": sha256_file(Path(__file__)),
        "units": build_units(items),
        "analysis_boundary": (
            "Exploratory matched prompt-contract experiment; no superiority, controller, "
            "personalization, or general capability claim."
        ),
    }


def build_lock() -> dict[str, Any]:
    return {
        "schema": "foil-codex-dose-lock/v1",
        "files": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in (
                PROTOCOL,
                Path(__file__),
                SKILL_FILE,
                SCHEMA_FILE,
                ITEMS,
                CONDITION_MAP,
                MANIFEST,
                EXCLUSION_MANIFEST,
            )
        },
    }


def prepare() -> None:
    frozen_outputs = (ITEMS, MANIFEST, CONDITION_MAP, SCHEMA_FILE, LOCK)
    if (
        any(path.exists() for path in frozen_outputs)
        or any(RECEIPTS.rglob("*.json"))
        or PREDICTIONS.exists()
        or RESULTS.exists()
    ):
        raise ProtocolError("frozen or run artifacts exist; prepare never overwrites an experiment")
    archive_bytes = fetch_archive()
    source_archive_sha256 = sha256_bytes(archive_bytes)
    items = public_items(load_rows(archive_bytes, expected_sha256=source_archive_sha256))
    write_json(ITEMS, {"schema": "foil-codex-dose-items/v1", "items": items})
    write_json(CONDITION_MAP, condition_payload())
    write_json(SCHEMA_FILE, answer_schema())
    write_json(
        MANIFEST,
        build_manifest(items, source_archive_sha256=source_archive_sha256),
    )
    write_json(LOCK, build_lock())
    print(f"prepared {len(items)} items and {len(read_json(MANIFEST)['units'])} units")


def validate_lock() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (PROTOCOL, SKILL_FILE, SCHEMA_FILE, ITEMS, CONDITION_MAP, MANIFEST, LOCK):
        if not path.exists():
            raise ProtocolError(f"missing frozen artifact: {path}")
    lock = read_json(LOCK)
    for relative, expected in lock["files"].items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise ProtocolError(f"frozen hash mismatch: {relative}: {actual} != {expected}")
    manifest = read_json(MANIFEST)
    items_payload = read_json(ITEMS)
    condition = read_json(CONDITION_MAP)
    if sha256_file(SKILL_FILE) != manifest["skill_sha256"]:
        raise ProtocolError("skill hash differs from manifest")
    if sha256_file(PROTOCOL) != manifest["protocol_sha256"]:
        raise ProtocolError("protocol hash differs from manifest")
    if sha256_file(Path(__file__)) != manifest["runner_sha256"]:
        raise ProtocolError("runner hash differs from manifest")
    if sha256_file(EXCLUSION_MANIFEST) != manifest["exclusion_manifest_sha256"]:
        raise ProtocolError("exclusion manifest hash differs from manifest")
    source_archive_sha256 = manifest.get("source_archive_sha256")
    if not isinstance(source_archive_sha256, str) or len(source_archive_sha256) != 64:
        raise ProtocolError("source archive digest is absent or malformed")
    if sha256_text(canonical_json(condition)) != manifest["condition_map_sha256"]:
        raise ProtocolError("condition map differs from manifest")
    if sha256_text(canonical_json(items_payload)) != manifest["items_sha256"]:
        raise ProtocolError("items differ from manifest")
    if len(items_payload["items"]) != TARGET or len(manifest["units"]) != EXPECTED_UNITS:
        raise ProtocolError("matrix size invariant failed")
    if len({unit["unit_id"] for unit in manifest["units"]}) != EXPECTED_UNITS:
        raise ProtocolError("unit ids are not unique")
    return manifest, items_payload, condition


def codex_executable() -> str:
    """Resolve an executable Python can launch without a Windows shell."""
    if sys.platform == "win32":
        cmd_shim = shutil.which("codex.cmd")
        if cmd_shim is not None:
            package_root = (
                Path(cmd_shim).resolve().parent
                / "node_modules"
                / "@openai"
                / "codex"
                / "node_modules"
                / "@openai"
            )
            packaged = sorted(
                package_root.glob("codex-win32-*/vendor/*/bin/codex.exe")
            )
            if len(packaged) == 1 and packaged[0].is_file():
                return str(packaged[0])
        native = shutil.which("codex.exe")
        if native is not None:
            return native
        raise ProtocolError("no native codex.exe is available to Python")

    executable = shutil.which("codex")
    if executable is None:
        raise ProtocolError("codex executable is not available")
    return executable


def codex_version() -> str:
    process = subprocess.run(
        [codex_executable(), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise ProtocolError(f"codex --version failed: {process.stderr.strip()}")
    return process.stdout.strip()


def build_argv(
    model: str,
    effort: str,
    workdir: Path,
    last_output: Path,
    schema_path: Path = SCHEMA_FILE,
    executable: str | None = None,
) -> list[str]:
    return [
        codex_executable() if executable is None else executable,
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-s",
        "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--output-schema",
        str(schema_path),
        "--json",
        "-o",
        str(last_output),
        "-C",
        str(workdir),
        "-",
    ]


ALLOWED_STREAM_SHAPES: dict[str, frozenset[str]] = {
    "thread.started": frozenset({""}),
    "turn.started": frozenset({""}),
    "item.started": frozenset({"reasoning", "agent_message"}),
    "item.updated": frozenset({"reasoning", "agent_message"}),
    "item.completed": frozenset({"reasoning", "agent_message"}),
    "turn.completed": frozenset({""}),
}


def parse_stream(text: str) -> dict[str, Any]:
    event_types: list[str] = []
    usage: dict[str, int] = defaultdict(int)
    tool_events: list[str] = []
    parse_errors = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(event, dict):
            tool_events.append("non-object-event:<none>")
            continue
        event_type = str(event.get("type", "unknown"))
        raw_item = event.get("item")
        if raw_item is not None and not isinstance(raw_item, dict):
            tool_events.append(f"{event_type}:non-object-item")
        item = raw_item if isinstance(raw_item, dict) else {}
        item_type = str(item.get("type", ""))
        event_types.append(f"{event_type}:{item_type}" if item_type else event_type)
        shape = ALLOWED_STREAM_SHAPES.get(event_type)
        if shape is None or item_type not in shape:
            tool_events.append(f"{event_type}:{item_type or '<none>'}")
        candidate_usage = event.get("usage")
        if not isinstance(candidate_usage, dict):
            candidate_usage = item.get("usage")
        if isinstance(candidate_usage, dict):
            for key, value in candidate_usage.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[str(key)] += value
    if not event_types and parse_errors == 0:
        tool_events.append("empty-stream:<none>")
    return {
        "event_types": sorted(set(event_types)),
        "tool_events": tool_events,
        "usage": dict(usage),
        "jsonl_parse_errors": parse_errors,
    }


def parse_answer(last_text: str) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(last_text)
    except json.JSONDecodeError as exc:
        return None, f"last output is not JSON: {exc}"
    if not isinstance(payload, dict) or set(payload) != {"answer"}:
        return None, "last output does not exactly match answer schema"
    answer = payload["answer"]
    if answer not in LETTERS:
        return None, f"answer is not A-D: {answer!r}"
    return answer, None

def receipt_path(kind: str, call_id: str) -> Path:
    return RECEIPTS / kind / f"{call_id}.json"


def call_count() -> int:
    return len(list(RECEIPTS.rglob("*.json")))


RECEIPT_FIELDS = {
    "schema",
    "kind",
    "call_id",
    "model",
    "effort",
    "codex_version",
    "pre_call_commit",
    "started_at",
    "finished_at",
    "wall_seconds",
    "returncode",
    "timed_out",
    "prompt_sha256",
    "stdout_sha256",
    "stderr_sha256",
    "last_output_sha256",
    "event_types",
    "usage",
    "answer",
    "valid",
    "invalid_reasons",
}


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_object_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) in {40, 64}
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_receipt_binding(
    receipt: object,
    *,
    kind: str,
    call_id: str,
    model: str,
    effort: str,
    prompt: str,
    frozen_commit: str,
    codex_cli_version: str,
    expected_answer: str | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise ProtocolError(f"receipt has unknown or missing fields: {kind}/{call_id}")
    expected = {
        "schema": "foil-codex-dose-receipt/v1",
        "kind": kind,
        "call_id": call_id,
        "model": model,
        "effort": effort,
        "codex_version": codex_cli_version,
        "pre_call_commit": frozen_commit,
        "prompt_sha256": sha256_text(prompt),
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ProtocolError(
                f"receipt binding mismatch for {kind}/{call_id}: {field}"
            )
    if not _is_git_object_id(receipt.get("pre_call_commit")):
        raise ProtocolError(f"receipt pre-call commit is malformed: {kind}/{call_id}")
    for field in (
        "prompt_sha256",
        "stdout_sha256",
        "stderr_sha256",
        "last_output_sha256",
    ):
        if not _is_sha256(receipt.get(field)):
            raise ProtocolError(f"receipt digest is malformed: {kind}/{call_id}: {field}")
    if (
        receipt.get("valid") is not True
        or receipt.get("invalid_reasons") != []
        or receipt.get("returncode") != 0
        or receipt.get("timed_out") is not False
        or receipt.get("answer") not in LETTERS
    ):
        raise ProtocolError(f"receipt is not a valid completed call: {kind}/{call_id}")
    if expected_answer is not None and receipt.get("answer") != expected_answer:
        raise ProtocolError(f"positive control answer mismatch: {kind}/{call_id}")
    wall_seconds = receipt.get("wall_seconds")
    if (
        isinstance(wall_seconds, bool)
        or not isinstance(wall_seconds, (int, float))
        or not math.isfinite(float(wall_seconds))
        or float(wall_seconds) < 0
    ):
        raise ProtocolError(f"receipt wall time is invalid: {kind}/{call_id}")
    if not isinstance(receipt.get("event_types"), list) or not all(
        isinstance(value, str) for value in receipt["event_types"]
    ):
        raise ProtocolError(f"receipt event types are invalid: {kind}/{call_id}")
    usage = receipt.get("usage")
    if not isinstance(usage, dict) or not all(
        isinstance(key, str)
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for key, value in usage.items()
    ):
        raise ProtocolError(f"receipt usage is invalid: {kind}/{call_id}")
    if not all(
        isinstance(receipt.get(field), str) and receipt[field]
        for field in ("started_at", "finished_at")
    ):
        raise ProtocolError(f"receipt timestamps are invalid: {kind}/{call_id}")
    return receipt


def validate_private_material(
    *, kind: str, call_id: str, receipt: dict[str, Any]
) -> None:
    raw_dir = PRIVATE / kind / call_id
    stdout_path = raw_dir / "events.jsonl"
    stderr_path = raw_dir / "stderr.txt"
    last_path = raw_dir / "last.json"
    if not all(path.is_file() for path in (stdout_path, stderr_path, last_path)):
        raise ProtocolError(f"private raw material is missing: {kind}/{call_id}")
    stdout = stdout_path.read_text(encoding="utf-8")
    stderr = stderr_path.read_text(encoding="utf-8")
    last_text = last_path.read_text(encoding="utf-8")
    for field, actual in (
        ("stdout_sha256", sha256_text(stdout)),
        ("stderr_sha256", sha256_text(stderr)),
        ("last_output_sha256", sha256_text(last_text)),
    ):
        if receipt[field] != actual:
            raise ProtocolError(f"private raw digest mismatch: {kind}/{call_id}: {field}")
    stream = parse_stream(stdout)
    if stream["jsonl_parse_errors"] or stream["tool_events"]:
        raise ProtocolError(f"private stream violates closed event contract: {kind}/{call_id}")
    if stream["event_types"] != receipt["event_types"] or stream["usage"] != receipt["usage"]:
        raise ProtocolError(f"private stream summary mismatch: {kind}/{call_id}")
    answer, answer_error = parse_answer(last_text)
    if answer_error is not None or answer != receipt["answer"]:
        raise ProtocolError(f"private answer differs from receipt: {kind}/{call_id}")


def execute_call(
    *,
    kind: str,
    call_id: str,
    model: str,
    effort: str,
    prompt: str,
    frozen_commit: str,
    codex_cli_version: str,
    expected_answer: str | None = None,
) -> dict[str, Any]:
    public_receipt = receipt_path(kind, call_id)
    if public_receipt.exists():
        existing = read_json(public_receipt)
        if not existing.get("valid"):
            raise ProtocolError(f"existing invalid receipt prohibits retry: {public_receipt}")
        validated = validate_receipt_binding(
            existing,
            kind=kind,
            call_id=call_id,
            model=model,
            effort=effort,
            prompt=prompt,
            frozen_commit=frozen_commit,
            codex_cli_version=codex_cli_version,
            expected_answer=expected_answer,
        )
        validate_private_material(kind=kind, call_id=call_id, receipt=validated)
        return validated
    if call_count() >= MAX_CALLS:
        raise ProtocolError(f"hard call cap {MAX_CALLS} reached")

    raw_dir = PRIVATE / kind / call_id
    if raw_dir.exists():
        raise ProtocolError(
            f"private attempt exists without a resumable receipt; retry prohibited: {kind}/{call_id}"
        )
    raw_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = raw_dir / "events.jsonl"
    stderr_path = raw_dir / "stderr.txt"
    last_path = raw_dir / "last.json"
    started = now()
    start_clock = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="foil-dose-") as temporary:
        workdir = Path(temporary)
        argv = build_argv(model, effort, workdir, last_path)
        try:
            process = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
            returncode: int | None = process.returncode
            stdout = process.stdout
            stderr = process.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            returncode = None
            if isinstance(exc.stdout, bytes):
                stdout = exc.stdout.decode("utf-8", errors="replace")
            else:
                stdout = exc.stdout or ""
            if isinstance(exc.stderr, bytes):
                stderr = exc.stderr.decode("utf-8", errors="replace")
            else:
                stderr = exc.stderr or ""
            timed_out = True
    wall_seconds = time.monotonic() - start_clock
    write_text(stdout_path, stdout)
    write_text(stderr_path, stderr)
    last_text = last_path.read_text(encoding="utf-8") if last_path.exists() else ""
    stream = parse_stream(stdout)
    answer, answer_error = parse_answer(last_text)
    invalid_reasons: list[str] = []
    if timed_out:
        invalid_reasons.append("timeout")
    if returncode != 0:
        invalid_reasons.append(f"returncode={returncode}")
    if stream["jsonl_parse_errors"]:
        invalid_reasons.append(f"jsonl_parse_errors={stream['jsonl_parse_errors']}")
    if stream["tool_events"]:
        invalid_reasons.append(f"tool_events={stream['tool_events']}")
    if answer_error:
        invalid_reasons.append(answer_error)
    if expected_answer is not None and answer != expected_answer:
        invalid_reasons.append(f"positive control expected {expected_answer}, got {answer}")
    receipt = {
        "schema": "foil-codex-dose-receipt/v1",
        "kind": kind,
        "call_id": call_id,
        "model": model,
        "effort": effort,
        "codex_version": codex_cli_version,
        "pre_call_commit": frozen_commit,
        "started_at": started,
        "finished_at": now(),
        "wall_seconds": wall_seconds,
        "returncode": returncode,
        "timed_out": timed_out,
        "prompt_sha256": sha256_text(prompt),
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "last_output_sha256": sha256_text(last_text),
        "event_types": stream["event_types"],
        "usage": stream["usage"],
        "answer": answer,
        "valid": not invalid_reasons,
        "invalid_reasons": invalid_reasons,
    }
    write_json(public_receipt, receipt)
    return receipt


def completed_controls() -> list[dict[str, Any]]:
    return [read_json(path) for path in sorted((RECEIPTS / "controls").glob("*.json"))]


def run_controls() -> None:
    validate_lock()
    existing = completed_controls()
    if existing:
        commits = {receipt.get("pre_call_commit") for receipt in existing}
        versions = {receipt.get("codex_version") for receipt in existing}
        if len(commits) != 1 or len(versions) != 1:
            raise ProtocolError("existing controls do not share one frozen commit and CLI version")
        frozen_commit = require_frozen_artifacts_committed(str(next(iter(commits))))
        codex_cli_version = str(next(iter(versions)))
        if codex_version() != codex_cli_version:
            raise ProtocolError("Codex CLI version changed during control resume")
    else:
        frozen_commit = require_frozen_artifacts_committed()
        codex_cli_version = codex_version()
    for config_id, config in CONFIGS.items():
        call_id = f"control-{config_id}"
        print(f"control {config_id}: {config['model']} {config['effort']}", flush=True)
        receipt = execute_call(
            kind="controls",
            call_id=call_id,
            model=str(config["model"]),
            effort=str(config["effort"]),
            prompt=CONTROL_PROMPT,
            frozen_commit=frozen_commit,
            codex_cli_version=codex_cli_version,
            expected_answer="A",
        )
        if not receipt["valid"]:
            raise ProtocolError(f"positive control failed: {call_id}: {receipt['invalid_reasons']}")
    print("all six positive controls passed")


def validate_controls() -> tuple[str, str]:
    receipts = completed_controls()
    if len(receipts) != len(CONFIGS):
        raise ProtocolError("exactly six positive-control receipts are required")
    by_call_id = {receipt.get("call_id"): receipt for receipt in receipts}
    expected_ids = {f"control-{config_id}" for config_id in CONFIGS}
    if set(by_call_id) != expected_ids:
        raise ProtocolError("positive-control receipt inventory is not exact")
    commits = {receipt.get("pre_call_commit") for receipt in receipts}
    versions = {receipt.get("codex_version") for receipt in receipts}
    if len(commits) != 1 or len(versions) != 1:
        raise ProtocolError("positive controls do not share one frozen commit and CLI version")
    frozen_commit = require_frozen_artifacts_committed(str(next(iter(commits))))
    codex_cli_version = str(next(iter(versions)))
    for config_id, config in CONFIGS.items():
        call_id = f"control-{config_id}"
        validated = validate_receipt_binding(
            by_call_id[call_id],
            kind="controls",
            call_id=call_id,
            model=str(config["model"]),
            effort=str(config["effort"]),
            prompt=CONTROL_PROMPT,
            frozen_commit=frozen_commit,
            codex_cli_version=codex_cli_version,
            expected_answer="A",
        )
        validate_private_material(kind="controls", call_id=call_id, receipt=validated)
    return frozen_commit, codex_cli_version


def controls_passed() -> bool:
    try:
        validate_controls()
    except ProtocolError:
        return False
    return True

def prediction_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for unit in manifest["units"]:
        path = receipt_path("units", unit["unit_id"])
        if not path.exists():
            continue
        receipt = read_json(path)
        rows.append(
            {
                "unit_id": unit["unit_id"],
                "item_id": unit["item_id"],
                "config_id": unit["config_id"],
                "condition_id": unit["condition_id"],
                "answer": receipt.get("answer"),
                "valid": receipt.get("valid", False),
                "receipt_sha256": sha256_file(path),
            }
        )
    return {
        "schema": "foil-codex-dose-predictions/v1",
        "manifest_sha256": sha256_file(MANIFEST),
        "complete": len(rows) == len(manifest["units"]) and all(row["valid"] for row in rows),
        "predictions": rows,
    }


def run_units() -> None:
    manifest, items_payload, condition = validate_lock()
    frozen_commit, codex_cli_version = validate_controls()
    if codex_version() != codex_cli_version:
        raise ProtocolError("Codex CLI version changed between controls and scored calls")
    items = {item["id"]: item for item in items_payload["items"]}
    mapping = condition["map"]
    skill_text = SKILL_FILE.read_text(encoding="utf-8")
    for unit in sorted(manifest["units"], key=lambda row: row["order"]):
        arm = mapping[unit["condition_id"]]
        prompt = prompt_for(items[unit["item_id"]], arm, skill_text)
        if sha256_text(prompt) != unit["prompt_sha256"]:
            raise ProtocolError(f"prompt hash mismatch before {unit['unit_id']}")
        print(f"unit {unit['order'] + 1:03d}/{EXPECTED_UNITS} {unit['unit_id']}", flush=True)
        receipt = execute_call(
            kind="units",
            call_id=unit["unit_id"],
            model=unit["model"],
            effort=unit["effort"],
            prompt=prompt,
            frozen_commit=frozen_commit,
            codex_cli_version=codex_cli_version,
        )
        write_json(PREDICTIONS, prediction_payload(manifest))
        if not receipt["valid"]:
            raise ProtocolError(
                f"unit failed without retry: {unit['unit_id']}: {receipt['invalid_reasons']}"
            )
    predictions = prediction_payload(manifest)
    write_json(PREDICTIONS, predictions)
    if not predictions["complete"]:
        raise ProtocolError("prediction ledger incomplete after run")
    print(f"all {EXPECTED_UNITS} scored units completed; commit predictions and receipts before scoring")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
    )


def git_ignored(path: Path) -> bool:
    result = run_git("check-ignore", "-q", str(path.relative_to(ROOT)))
    return result.returncode == 0


def require_committed(path: Path) -> None:
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    tracked = run_git("ls-files", "--error-unmatch", relative)
    if tracked.returncode != 0:
        raise ProtocolError(f"gold gate: {relative} is not tracked and committed")
    dirty = run_git("status", "--porcelain", "--", relative)
    if dirty.returncode != 0 or dirty.stdout.strip():
        raise ProtocolError(f"gold gate: {relative} has uncommitted changes")


def frozen_artifacts() -> tuple[Path, ...]:
    return (
        PROTOCOL,
        Path(__file__),
        SKILL_FILE,
        SCHEMA_FILE,
        ITEMS,
        CONDITION_MAP,
        MANIFEST,
        LOCK,
        EXCLUSION_MANIFEST,
    )


def require_frozen_artifacts_committed(expected_commit: str | None = None) -> str:
    validate_lock()
    for path in frozen_artifacts():
        require_committed(path)
    if not git_ignored(PRIVATE / "sentinel.jsonl"):
        raise ProtocolError("private raw directory is not ignored by repository policy")
    if expected_commit is None:
        resolved = run_git("rev-parse", "HEAD")
        if resolved.returncode != 0:
            raise ProtocolError("cannot resolve pre-call Git commit")
        commit = resolved.stdout.strip()
    else:
        commit = expected_commit
    if not _is_git_object_id(commit):
        raise ProtocolError("pre-call Git commit is malformed")
    resolved = run_git("rev-parse", "--verify", f"{commit}^{{commit}}")
    if resolved.returncode != 0 or resolved.stdout.strip() != commit:
        raise ProtocolError("pre-call Git commit cannot be verified exactly")
    ancestry = run_git("merge-base", "--is-ancestor", commit, "HEAD")
    if ancestry.returncode != 0:
        raise ProtocolError("pre-call Git commit is not an ancestor of current HEAD")
    for path in frozen_artifacts():
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        blob = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=ROOT,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if blob.returncode != 0 or sha256_bytes(blob.stdout) != sha256_file(path):
            raise ProtocolError(f"pre-call commit does not bind frozen artifact: {relative}")
    return commit


def print_dry_run() -> None:
    manifest, items_payload, condition = validate_lock()
    first = min(manifest["units"], key=lambda row: row["order"])
    item = next(row for row in items_payload["items"] if row["id"] == first["item_id"])
    arm = condition["map"][first["condition_id"]]
    prompt = prompt_for(item, arm)
    fake_work = Path("<fresh-empty-workdir>")
    fake_last = Path("<private-last-output.json>")
    if not git_ignored(PRIVATE / "sentinel.jsonl"):
        raise ProtocolError("private raw directory is not ignored by repository policy")
    payload = {
        "model_exec_call_cap": MAX_CALLS,
        "controls": len(CONFIGS),
        "units": len(manifest["units"]),
        "first_unit": first,
        "first_arm": arm,
        "argv": build_argv(first["model"], first["effort"], fake_work, fake_last),
        "prompt_sha256_matches": sha256_text(prompt) == first["prompt_sha256"],
        "private_raw_ignored": git_ignored(PRIVATE / "sentinel.jsonl"),
    }
    print(json.dumps(payload, indent=2))


def status() -> None:
    manifest, _, _ = validate_lock()
    controls = completed_controls()
    units = list((RECEIPTS / "units").glob("*.json"))
    valid_units = sum(bool(read_json(path).get("valid")) for path in units)
    payload = {
        "codex_version": codex_version(),
        "controls_valid": sum(bool(row.get("valid")) for row in controls),
        "controls_expected": len(CONFIGS),
        "units_valid": valid_units,
        "units_recorded": len(units),
        "units_expected": len(manifest["units"]),
        "model_exec_receipts_recorded": call_count(),
        "model_exec_call_cap": MAX_CALLS,
        "predictions_exist": PREDICTIONS.exists(),
        "results_exist": RESULTS.exists(),
    }
    print(json.dumps(payload, indent=2))

def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def exact_mcnemar(foil_only: int, base_only: int) -> float:
    discordant = foil_only + base_only
    if discordant == 0:
        return 1.0
    smaller = min(foil_only, base_only)
    lower_tail = sum(math.comb(discordant, k) for k in range(smaller + 1)) / (2**discordant)
    return min(1.0, 2 * lower_tail)


def exact_sign_flip(values: list[float]) -> float:
    nonzero = [value for value in values if value != 0]
    if not nonzero:
        return 1.0
    observed = abs(sum(nonzero))
    extreme = 0
    total = 2 ** len(nonzero)
    for signs in itertools.product((-1, 1), repeat=len(nonzero)):
        if abs(sum(sign * value for sign, value in zip(signs, nonzero))) >= observed - 1e-12:
            extreme += 1
    return extreme / total


def slope(xs: list[float], ys: list[float]) -> float:
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def pstar_posterior(
    foil_only: int,
    base_wrong: int,
    base_only: int,
    base_correct: int,
    draws: int = 100_000,
) -> dict[str, Any] | None:
    if base_wrong == 0 or base_correct == 0:
        return None
    rng = random.Random(SEED + 91)
    values: list[float] = []
    for _ in range(draws):
        rescue = rng.betavariate(foil_only + 0.5, base_wrong - foil_only + 0.5)
        damage = rng.betavariate(base_only + 0.5, base_correct - base_only + 0.5)
        values.append(rescue / (rescue + damage))
    values.sort()
    return {
        "method": "deterministic Monte Carlo from independent Jeffreys beta posteriors",
        "draws": draws,
        "seed": SEED + 91,
        "median": values[draws // 2],
        "interval_95": [values[int(draws * 0.025)], values[int(draws * 0.975)]],
    }


def transition_table(base: list[bool], foil: list[bool]) -> dict[str, Any]:
    both_correct = sum(b and f for b, f in zip(base, foil))
    foil_only = sum((not b) and f for b, f in zip(base, foil))
    base_only = sum(b and (not f) for b, f in zip(base, foil))
    both_wrong = sum((not b) and (not f) for b, f in zip(base, foil))
    total = len(base)
    base_wrong = foil_only + both_wrong
    base_correct = both_correct + base_only
    return {
        "n": total,
        "both_correct": both_correct,
        "foil_only": foil_only,
        "base_only": base_only,
        "both_wrong": both_wrong,
        "base_accuracy": (both_correct + base_only) / total,
        "foil_accuracy": (both_correct + foil_only) / total,
        "paired_risk_difference": (foil_only - base_only) / total,
        "foil_only_given_base_wrong": foil_only / base_wrong if base_wrong else None,
        "foil_only_given_base_wrong_wilson_95": wilson(foil_only, base_wrong),
        "base_only_given_base_correct": base_only / base_correct if base_correct else None,
        "base_only_given_base_correct_wilson_95": wilson(base_only, base_correct),
        "mcnemar_exact_two_sided_p": exact_mcnemar(foil_only, base_only),
    }


def require_receipts_committed(manifest: dict[str, Any]) -> None:
    expected = [receipt_path("controls", f"control-{config_id}") for config_id in CONFIGS]
    expected.extend(receipt_path("units", unit["unit_id"]) for unit in manifest["units"])
    expected_relative = {
        str(path.relative_to(RECEIPTS)).replace("\\", "/") for path in expected
    }
    actual_relative = {
        str(path.relative_to(RECEIPTS)).replace("\\", "/")
        for path in RECEIPTS.rglob("*.json")
    }
    if actual_relative != expected_relative or len(actual_relative) != MAX_CALLS:
        raise ProtocolError("gold gate: public receipt inventory is not exactly 42 model calls")
    for path in expected:
        if not path.exists():
            raise ProtocolError(f"gold gate: missing receipt {path}")
        require_committed(path)


def gold_answers(rows: list[dict[str, str]], items: list[dict[str, Any]]) -> dict[str, str]:
    answers: dict[str, str] = {}
    for item in items:
        index = int(item["source_index"])
        choices, gold = shuffled_options(index, rows[index])
        if choices != item["choices"]:
            raise ProtocolError(f"gold reconstruction choices differ for {item['id']}")
        answers[item["id"]] = gold
    return answers


def validate_scoring_bindings(
    manifest: dict[str, Any],
    items_payload: dict[str, Any],
    condition: dict[str, Any],
    predictions: object,
) -> dict[str, dict[str, Any]]:
    if not isinstance(predictions, dict) or set(predictions) != {
        "schema",
        "manifest_sha256",
        "complete",
        "predictions",
    }:
        raise ProtocolError("gold gate: prediction ledger schema is not closed")
    if (
        predictions["schema"] != "foil-codex-dose-predictions/v1"
        or predictions["manifest_sha256"] != sha256_file(MANIFEST)
        or predictions["complete"] is not True
        or not isinstance(predictions["predictions"], list)
        or len(predictions["predictions"]) != EXPECTED_UNITS
    ):
        raise ProtocolError("gold gate: prediction ledger is not complete and manifest-bound")
    frozen_commit, codex_cli_version = validate_controls()
    require_receipts_committed(manifest)
    units = {unit["unit_id"]: unit for unit in manifest["units"]}
    items = {item["id"]: item for item in items_payload["items"]}
    mapping = condition["map"]
    expected_row_fields = {
        "unit_id",
        "item_id",
        "config_id",
        "condition_id",
        "answer",
        "valid",
        "receipt_sha256",
    }
    rows = predictions["predictions"]
    if any(not isinstance(row, dict) or set(row) != expected_row_fields for row in rows):
        raise ProtocolError("gold gate: prediction row schema is not closed")
    by_unit = {row["unit_id"]: row for row in rows}
    if len(by_unit) != EXPECTED_UNITS or set(by_unit) != set(units):
        raise ProtocolError("gold gate: prediction unit inventory is not exact")
    receipts: dict[str, dict[str, Any]] = {}
    skill_text = SKILL_FILE.read_text(encoding="utf-8")
    for unit_id, unit in units.items():
        row = by_unit[unit_id]
        expected_identity = {
            "item_id": unit["item_id"],
            "config_id": unit["config_id"],
            "condition_id": unit["condition_id"],
        }
        if any(row[field] != value for field, value in expected_identity.items()):
            raise ProtocolError(f"gold gate: prediction identity mismatch: {unit_id}")
        path = receipt_path("units", unit_id)
        if row["receipt_sha256"] != sha256_file(path):
            raise ProtocolError(f"gold gate: receipt hash differs for {unit_id}")
        arm = mapping[unit["condition_id"]]
        prompt = prompt_for(items[unit["item_id"]], arm, skill_text)
        receipt = validate_receipt_binding(
            read_json(path),
            kind="units",
            call_id=unit_id,
            model=unit["model"],
            effort=unit["effort"],
            prompt=prompt,
            frozen_commit=frozen_commit,
            codex_cli_version=codex_cli_version,
        )
        validate_private_material(kind="units", call_id=unit_id, receipt=receipt)
        if row["valid"] is not True or row["answer"] != receipt["answer"]:
            raise ProtocolError(f"gold gate: prediction differs from receipt: {unit_id}")
        receipts[unit_id] = receipt
    return receipts


def score() -> None:
    manifest, items_payload, condition = validate_lock()
    require_committed(PREDICTIONS)
    predictions = read_json(PREDICTIONS)
    receipts = validate_scoring_bindings(
        manifest,
        items_payload,
        condition,
        predictions,
    )

    items = items_payload["items"]
    source_archive_sha256 = manifest["source_archive_sha256"]
    gold = gold_answers(
        load_rows(expected_sha256=source_archive_sha256),
        items,
    )
    mapping = condition["map"]
    outcomes: dict[tuple[str, str, str], bool] = {}
    runtime: dict[str, dict[str, list[float]]] = {
        "BASE": defaultdict(list),
        "FOIL": defaultdict(list),
    }
    units = {unit["unit_id"]: unit for unit in manifest["units"]}
    for prediction in predictions["predictions"]:
        unit = units[prediction["unit_id"]]
        receipt = receipts[unit["unit_id"]]
        arm = mapping[unit["condition_id"]]
        key = (unit["item_id"], unit["config_id"], arm)
        if key in outcomes:
            raise ProtocolError(f"duplicate outcome: {key}")
        outcomes[key] = receipt["answer"] == gold[unit["item_id"]]
        runtime[arm]["wall_seconds"].append(float(receipt["wall_seconds"]))
        for token_key in ("input_tokens", "cached_input_tokens", "output_tokens"):
            value = receipt.get("usage", {}).get(token_key)
            if isinstance(value, int):
                runtime[arm][token_key].append(float(value))

    config_results: list[dict[str, Any]] = []
    all_base: list[bool] = []
    all_foil: list[bool] = []
    for config_id, config in CONFIGS.items():
        base = [outcomes[(item["id"], config_id, "BASE")] for item in items]
        foil = [outcomes[(item["id"], config_id, "FOIL")] for item in items]
        row = {
            "config_id": config_id,
            "model": config["model"],
            "effort": config["effort"],
            "rank": config["rank"],
            **transition_table(base, foil),
        }
        config_results.append(row)
        all_base.extend(base)
        all_foil.extend(foil)

    overall = transition_table(all_base, all_foil)
    item_differences = [
        sum(
            int(outcomes[(item["id"], config_id, "FOIL")])
            - int(outcomes[(item["id"], config_id, "BASE")])
            for config_id in CONFIGS
        )
        for item in items
    ]
    overall["item_cluster_sign_flip_two_sided_p"] = exact_sign_flip(item_differences)
    overall["item_aggregate_differences"] = item_differences

    efficiency: dict[str, Any] = {}
    for arm, metrics in runtime.items():
        efficiency[arm] = {
            key: {
                "n": len(values),
                "mean": sum(values) / len(values) if values else None,
                "total": sum(values) if values else None,
            }
            for key, values in metrics.items()
        }
    result = {
        "schema": "foil-codex-dose-results/v1",
        "scored_at": now(),
        "manifest_sha256": sha256_file(MANIFEST),
        "predictions_sha256": sha256_file(PREDICTIONS),
        "source_revision": SOURCE_REVISION,
        "n_items": TARGET,
        "n_matched_pairs": EXPECTED_PAIRS,
        "execution_inventory": {
            "model_exec_receipts": call_count(),
            "model_exec_cap": MAX_CALLS,
            "auxiliary_local_subprocesses": (
                "Git integrity checks and Codex CLI version probes are outside the model-exec cap."
            ),
        },
        "configurations": config_results,
        "overall": overall,
        "pattern": {
            "label": "OBSERVED_IN_THIS_PILOT",
            "scope": "three-item descriptive development result; no fitted dose-response claim",
        },
        "efficiency": efficiency,
        "invalid_original_primary": {
            "status": "NOT_RUN_INVALID_GENERATED_REGRESSOR",
            "model": "correct ~ arm * p_hat_config + (1 | item)",
            "reason": "p_hat_config is computed from outcomes in this same three-item run.",
        },
        "claim_boundary": (
            "Three-item development observation of a bundled FOIL prompt-contract effect under "
            "independent stochastic calls. No general superiority, causal rescue/damage, "
            "validated dose, calibration, certification, personalization, controller, or "
            "deployment claim."
        ),
    }
    write_json(RESULTS, result)
    write_report(result)
    print(json.dumps(result, indent=2))


def format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def write_report(result: dict[str, Any]) -> None:
    lines = [
        "# FOIL Codex dose-response benchmark — development report",
        "",
        f"**Evidence label:** `{result['pattern']['label']}`  ",
        f"**Pairs:** {result['n_matched_pairs']} across {result['n_items']} items and six configurations  ",
        "**Boundary:** exploratory matched prompt-contract evidence, not a superiority or deployment claim.",
        "",
        "| Configuration | BASE | FOIL | FOIL only | BASE only | Paired difference | McNemar p |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(result["configurations"], key=lambda value: value["rank"]):
        lines.append(
            f"| {row['config_id']} | {format_rate(row['base_accuracy'])} | "
            f"{format_rate(row['foil_accuracy'])} | {row['foil_only']} | {row['base_only']} | "
            f"{row['paired_risk_difference']:+.1%} | {row['mcnemar_exact_two_sided_p']:.4f} |"
        )
    overall = result["overall"]
    lines.extend(
        [
            "",
            "## Overall",
            "",
            f"- BASE accuracy: {format_rate(overall['base_accuracy'])}",
            f"- FOIL accuracy: {format_rate(overall['foil_accuracy'])}",
            f"- Paired risk difference: {overall['paired_risk_difference']:+.1%}",
            f"- Discordant pairs: {overall['foil_only'] + overall['base_only']} "
            f"(FOIL only {overall['foil_only']}, BASE only {overall['base_only']})",
            f"- Exact McNemar p: {overall['mcnemar_exact_two_sided_p']:.4f}",
            f"- Exact item-cluster sign-flip p: {overall['item_cluster_sign_flip_two_sided_p']:.4f}",
            "",
            "## Interpretation boundary",
            "",
            result["claim_boundary"],
            "",
            "The draft same-run p-hat mixed model was not run because it uses an outcome-derived "
            "regressor and three items cannot support a fitted dose-response claim. Configuration "
            "order is descriptive only.",
        ]
    )
    write_text(REPORT, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("prepare", "check", "dry-run", "controls", "run", "status", "score")
    )
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare()
        elif args.command == "check":
            validate_lock()
            print("frozen artifacts valid")
        elif args.command == "dry-run":
            print_dry_run()
        elif args.command == "controls":
            run_controls()
        elif args.command == "run":
            run_units()
        elif args.command == "status":
            status()
        elif args.command == "score":
            score()
    except ProtocolError as exc:
        print(f"PROTOCOL ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())