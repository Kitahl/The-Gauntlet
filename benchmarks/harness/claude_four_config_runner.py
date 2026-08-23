"""Executable harness for the preregistered four-config BASE vs FOIL contract test.

What this runs
--------------
The same items, twice, under four Claude Code configurations
(`{sonnet, opus} x {low, high}`). The two conditions differ in exactly two
things: the FOIL arm appends the skill text as a system prompt file and prefixes
the user prompt with the skill's invocation line. Every other flag, the item
text, the answer-format instruction, the tool allowance and the tool budget are
byte-identical, so a difference between arms is attributable to the skill text
rather than to a richer prompt or a larger budget.

This is a **contract test of the skill text at matched cost**, not a
personalization test. Profile arms are a separate, later experiment.

Three subcommands, in the order they may legally be used
--------------------------------------------------------
``prepare``   writes the question-only items file, the sealed condition map and
              the run manifest. No gold is written and none is retained beyond
              the selection call. ``--check-only`` revalidates the committed
              artifacts offline and touches no network.
``run``       executes units. ``--dry-run`` prints the exact argv, environment
              delta, working directory and settings payload for each unit and
              writes nothing at all.
``score``     refuses to run until the predictions file is committed, then
              unseals the condition map, opens gold, and writes the results
              file. The refusal is the whole point: gold cannot be consulted
              while a prediction can still be edited.

Isolation, and what it does and does not buy
--------------------------------------------
Every unit runs in a fresh empty working directory, with a generated settings
file whose only content is the broker PreToolUse hook, and with a child
environment stripped of the parent Claude Code session variables
(``CLAUDECODE*``, ``CLAUDE_CODE_*``, ``CLAUDE_PID``) so a nested invocation does
not inherit the caller's session. Each unit also claims a distinct
``isolation_session_id`` in the task-guard sidecar index, so two units silently
sharing a session fails closed rather than being reported as isolated.

That is process and session isolation. It is not a sandbox, and it does not make
the *operator* blind: whoever launches the run necessarily knows which arm
carries the skill text. The sealed condition map prevents post-hoc relabelling
of arms; it does not prevent an operator from knowing the mapping.

Reuse, not reimplementation
---------------------------
Model invocation and envelope parsing come from ``tools/foil_models.py``
(``cli`` family, ``claude_json`` parser). Budget accounting comes from
``tools/foil_task_guard.py`` and is enforced by ``tools/foil_tool_broker.py``.
Item selection comes from the existing ``gpqa_prepare_score`` and
``browsecomp_*_prepare_score`` harnesses. Statistics come from
``paired_stats.py``. Nothing here duplicates any of them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

HARNESS_DIR = Path(__file__).resolve().parent
ROOT = HARNESS_DIR.parents[1]
sys.path.insert(0, str(HARNESS_DIR))
sys.path.insert(0, str(ROOT / "tools"))

import foil_models as fm  # noqa: E402
import foil_task_guard as tg  # noqa: E402
import paired_stats as ps  # noqa: E402

SCHEMA = "egrt.foil-four-config-runner.v1"

#: `foil_task_guard.start_state()` builds state in memory; this is the only
#: function that writes it, and the guard's own CLI uses the same one. Aliased
#: once with the reason rather than reaching into the module at each call site.
_save_guard_state = tg._atomic_save

RUN_DATE = "2026-08-23"
OUT = ROOT / "benchmark_runs" / RUN_DATE
RECEIPT_DIR = OUT / "four_config_receipts"
GUARD_DIR = ROOT / ".foil" / "four_config" / RUN_DATE          # gitignored runtime state
PROTOCOL = ROOT / "benchmarks" / "CLAUDE_FOUR_CONFIG_PROTOCOL.md"
SEALED_MAP = OUT / "condition_map.sealed.json"
SKILL_FILE = ROOT / "skills" / "foil" / "SKILL.md"
BROKER = ROOT / "tools" / "foil_tool_broker.py"

#: Configuration ids are opaque to the scorer but not to the runner: it has to
#: know which flags to pass. Order is fixed so Holm sees a stable family.
CONFIGS: dict[str, dict[str, str]] = {
    "C-SL": {"model": "sonnet", "effort": "low"},
    "C-SH": {"model": "sonnet", "effort": "high"},
    "C-OL": {"model": "opus", "effort": "low"},
    "C-OH": {"model": "opus", "effort": "high"},
}
CONDITIONS = ("BASE", "FOIL")
#: The literal prefix that turns the prompt into a skill invocation. The trailing
#: newline is part of it: the item text must start on its own line in both arms.
FOIL_PROMPT_PREFIX = "/foil solve\n"

ORDER_SEED = 20260823          # per-item execution order and the condition-id map
GPQA_SELECTION_SEED = 20260825  # owned by gpqa_prepare_score; restated for the receipt
BROWSECOMP_SELECTION_SEED = 20260831
BROWSECOMP_TARGET = 12
LEGACY_BROWSECOMP_SEED = 20260824  # the 20 rows the first BrowseComp pilot consumed
CONTAMINATION_STATUS = "known_public"
REPLICATES = 1                 # owner decision; see the protocol's exploratory declaration

ANSWER_LINE = re.compile(r"^\s*ANSWER:\s*(.+?)\s*$", re.MULTILINE)
GPQA_LETTER = re.compile(r"^[A-D]$")

BENCHMARKS: dict[str, dict[str, Any]] = {
    "gpqa": {
        "label": "GPQA-Diamond",
        "tools": "",
        "allowed_tools": [],
        "budgets": {"search": 0, "followup": 0},
        "timeout_seconds": 900.0,
        "answer_kind": "letter",
        "dataset_revision": "idavidrein/gpqa main dataset.zip (GPQA-Diamond CSV)",
        "selection_seed": GPQA_SELECTION_SEED,
        "n_items": 24,
    },
    "browsecomp": {
        "label": "BrowseComp",
        "tools": "WebSearch,WebFetch",
        "allowed_tools": ["WebSearch", "WebFetch"],
        "budgets": {"search": 12, "followup": 12},
        "timeout_seconds": 1200.0,
        "answer_kind": "text",
        "dataset_revision": "openai simple-evals browse_comp_test_set.csv",
        "selection_seed": BROWSECOMP_SELECTION_SEED,
        "n_items": BROWSECOMP_TARGET,
    },
}


class PrepareError(RuntimeError):
    """Selection or artifact validation failed. Never downgraded to a warning."""


class NotCommitted(RuntimeError):
    """Scoring was attempted while the predictions could still be edited."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, text: str) -> None:
    """Always LF.

    Text-mode writes translate `\\n` to the platform line ending, which would make a
    preregistered file hash differ between the machine that pinned it and the machine
    that checks it. Every artifact whose bytes are hashed is written through here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# prompts - the only place the two arms are allowed to differ                  #
# --------------------------------------------------------------------------- #

GPQA_INSTRUCTION = (
    "Closed book. No tools are available. Choose exactly one option.\n"
    "Think for as long as you need, then end your reply with a final line in "
    "exactly this form, and nothing after it:\n"
    "ANSWER: <letter>"
)
BROWSECOMP_INSTRUCTION = (
    "Use web search to establish the answer. The host enforces a ceiling of 12 "
    "web searches and 12 page fetches for this item; exceeding it is refused, "
    "not warned about.\n"
    "End your reply with a final line in exactly this form, and nothing after it:\n"
    "ANSWER: <exact answer>"
)


def item_body(benchmark: str, item: dict[str, Any]) -> str:
    """The condition-independent prompt body. Identical bytes in both arms."""
    if benchmark == "gpqa":
        choices = item["choices"]
        options = "\n".join(f"{letter}) {choices[letter]}" for letter in sorted(choices))
        return f"{item['question'].strip()}\n\n{options}\n\n{GPQA_INSTRUCTION}"
    return f"{item['question'].strip()}\n\n{BROWSECOMP_INSTRUCTION}"


def build_prompt(benchmark: str, item: dict[str, Any], condition: str) -> str:
    """BASE is the body. FOIL is the prefix plus the identical body.

    Any future divergence beyond this prefix breaks the matched-cost claim, which
    is why the two arms are built from one function and the test asserts the
    byte relationship rather than re-deriving each arm separately.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    body = item_body(benchmark, item)
    return (FOIL_PROMPT_PREFIX + body) if condition == "FOIL" else body


def delivered_prompt(prompt: str) -> str:
    """The bytes that actually reach the CLI's stdin.

    `foil_models._cli` renders messages as `[role]\\n<content>` before writing them,
    so the delivered bytes carry a `[user]` envelope that the item prompt does not.
    Mirrored here - and asserted against a real child process in the test suite - so
    the receipts can record what was sent rather than what was intended. The
    envelope is identical in both arms, so it does not disturb the matched-cost
    relationship between BASE and FOIL.
    """
    return f"[user]\n{prompt}"


def extract_answer(text: str, answer_kind: str) -> tuple[str | None, str | None]:
    """Return (answer, invalid_reason). A missing ANSWER line is INVALID, never a guess."""
    matches = ANSWER_LINE.findall(text or "")
    if not matches:
        return None, "no ANSWER line"
    answer = matches[-1].strip()
    if answer_kind == "letter":
        # The whole token must be one option letter. Taking the first character of
        # free text would silently score "beta" as B - a wrong answer recorded as a
        # confident right one, which is worse than an INVALID.
        candidate = answer.strip().strip("().,;:*\"' \t").upper()
        if not GPQA_LETTER.match(candidate):
            return None, f"ANSWER line is not an option letter A-D: {answer[:40]!r}"
        return candidate, None
    if not answer:
        return None, "empty ANSWER line"
    return answer, None


# --------------------------------------------------------------------------- #
# sealed condition map                                                         #
# --------------------------------------------------------------------------- #

def condition_map() -> dict[str, str]:
    """Opaque id -> condition, decided by the seed alone.

    Deriving it from the seed rather than from a fresh draw is what lets the
    protocol pin its SHA-256 before any item is selected: the map is a function
    of a preregistered number, so a later regeneration that disagrees is a
    detectable tamper rather than an ordinary rerun.
    """
    rng = random.Random(ORDER_SEED)
    flipped = rng.random() < 0.5
    return {"A": "FOIL" if flipped else "BASE", "B": "BASE" if flipped else "FOIL"}


def sealed_payload() -> dict[str, Any]:
    mapping = condition_map()
    return {
        "schema": "foil-four-config-condition-map/v1",
        "run_date": RUN_DATE,
        "order_seed": ORDER_SEED,
        "map": mapping,
        "note": (
            "Written before any run. Prevents post-hoc relabelling of arms. It does "
            "not blind the operator, who necessarily knows which arm carries the skill text."
        ),
    }


def write_sealed_map() -> Path:
    """Idempotent. A different existing seal is a hard error, never an overwrite."""
    payload = sealed_payload()
    blob = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if SEALED_MAP.exists():
        existing = SEALED_MAP.read_text(encoding="utf-8")
        if existing != blob:
            raise PrepareError(
                f"{SEALED_MAP} already exists with different content; a sealed map is "
                "never overwritten. Investigate before touching it."
            )
        return SEALED_MAP
    _write_text(SEALED_MAP, blob)
    return SEALED_MAP


def condition_id_for(condition: str) -> str:
    for key, value in condition_map().items():
        if value == condition:
            return key
    raise ValueError(f"unmapped condition: {condition}")


# --------------------------------------------------------------------------- #
# item selection - delegated to the existing harnesses                         #
# --------------------------------------------------------------------------- #

def _select_gpqa() -> list[dict[str, Any]]:
    """Reuse `gpqa_prepare_score.prepare()`; keep the questions, discard the gold.

    The gold mapping it returns is dropped on the next line and never written,
    so preparing an item file cannot leak an answer into the run directory.
    """
    import gpqa_prepare_score as gpqa

    questions, gold = gpqa.prepare()
    del gold
    items = []
    for index, question in enumerate(questions):
        items.append({
            "index": index,
            "id": question["id"],
            "question": question["question"],
            "choices": question["choices"],
            "category": question.get("category", "unknown"),
        })
    if len(items) != BENCHMARKS["gpqa"]["n_items"]:
        raise PrepareError(f"expected {BENCHMARKS['gpqa']['n_items']} GPQA items, got {len(items)}")
    return items


def prior_browsecomp_fingerprints() -> set[str]:
    """Every BrowseComp row fingerprint any earlier pilot has already exposed.

    Read offline from the committed four-way receipt: its scored items plus its
    three exclusion lists are the complete 40-row selection chain. The 20 rows the
    legacy pilot consumed are added at selection time from the CSV, because they
    are defined by a seed rather than listed anywhere.
    """
    receipt = ROOT / "benchmark_runs" / "2026-08-22" / "browsecomp_four_way_results.json"
    data = _read_json(receipt)
    ids: set[str] = {str(row["id"]) for row in data.get("items", [])}
    for key in ("post_exposure_excluded_ids", "execution_budget_excluded_ids",
                "execution_integrity_excluded_ids"):
        ids |= {str(value) for value in data.get(key, [])}
    prefixes = {item.split("-")[-1] for item in ids}
    if len(prefixes) != 40:
        raise PrepareError(
            f"expected the 40-row four-way selection chain in {receipt.name}, "
            f"found {len(prefixes)} fingerprints; refusing to select against an "
            "incomplete exclusion set"
        )
    return prefixes


def _select_browsecomp() -> list[dict[str, Any]]:
    """Fresh rows only. The decrypted problem text stays out of any private file."""
    import browsecomp_four_way_prepare_score as bc

    rows = list(csv.DictReader(io.StringIO(bc.fetch(bc.URL).decode("utf-8-sig"))))
    excluded = prior_browsecomp_fingerprints()
    excluded |= {bc.row_fingerprint(row)[:8]
                 for row in random.Random(LEGACY_BROWSECOMP_SEED).sample(rows, 20)}
    if len(excluded) != 60:
        raise PrepareError(f"expected 60 previously exposed rows, computed {len(excluded)}")
    pool = [row for row in rows if bc.row_fingerprint(row)[:8] not in excluded]
    if len(pool) < BROWSECOMP_TARGET:
        raise PrepareError(f"need {BROWSECOMP_TARGET} fresh rows, pool holds {len(pool)}")
    selected = random.Random(BROWSECOMP_SELECTION_SEED).sample(pool, BROWSECOMP_TARGET)
    items = []
    for index, row in enumerate(selected):
        fingerprint = bc.row_fingerprint(row)
        items.append({
            "index": index,
            "id": f"bc5-{index:02d}-{fingerprint[:8]}",
            "question": bc.decrypt(row["problem"], row["canary"]),
        })
    return items


SELECTORS = {"gpqa": _select_gpqa, "browsecomp": _select_browsecomp}


# --------------------------------------------------------------------------- #
# manifest                                                                     #
# --------------------------------------------------------------------------- #

def items_path(benchmark: str) -> Path:
    return OUT / f"four_config_{benchmark}_items.json"


def manifest_path(benchmark: str) -> Path:
    return OUT / f"four_config_{benchmark}_manifest.json"


def predictions_path(benchmark: str) -> Path:
    return OUT / f"four_config_{benchmark}_predictions.json"


def results_path(benchmark: str) -> Path:
    return OUT / f"four_config_{benchmark}_results.json"


def isolation_session_id(unit: str) -> str:
    """Deterministic, unique, and shaped like a session id so a collision is visible."""
    digest = sha256_text(f"{SCHEMA}|{RUN_DATE}|{unit}")
    return f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def build_manifest(benchmark: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Every (item, config, condition) unit, with its prompt digest and order.

    Execution order is randomised *within* each (item, config) pair from a
    per-item seed, so a systematic ordering effect - a warm cache, an operator
    getting tired - cannot line up with one arm.
    """
    spec = BENCHMARKS[benchmark]
    units: list[dict[str, Any]] = []
    for item in items:
        item_blob = json.dumps(item, sort_keys=True, ensure_ascii=False)
        for config, flags in CONFIGS.items():
            rng = random.Random(f"{ORDER_SEED}|{benchmark}|{item['id']}|{config}")
            order = list(CONDITIONS)
            rng.shuffle(order)
            for position, condition in enumerate(order):
                prompt = build_prompt(benchmark, item, condition)
                cid = condition_id_for(condition)
                unit = f"{benchmark}-{item['index']:03d}-{config}-{cid}"
                units.append({
                    "unit": unit,
                    "item_id": item["id"],
                    "item_index": item["index"],
                    "item_sha256": sha256_text(item_blob),
                    "config": config,
                    "model": flags["model"],
                    "effort": flags["effort"],
                    "condition_id": cid,
                    "order_position": position,
                    "prompt_sha256": sha256_text(prompt),
                    "isolation_session_id": isolation_session_id(unit),
                })
    session_ids = [row["isolation_session_id"] for row in units]
    if len(set(session_ids)) != len(session_ids):
        raise PrepareError("isolation session ids are not unique; refusing to write the manifest")
    expected = len(items) * len(CONFIGS) * len(CONDITIONS)
    if len(units) != expected:
        raise PrepareError(f"expected {expected} units, built {len(units)}")
    return {
        "schema": "foil-four-config-manifest/v1",
        "benchmark": benchmark,
        "benchmark_label": spec["label"],
        "run_date": RUN_DATE,
        "order_seed": ORDER_SEED,
        "selection_seed": spec["selection_seed"],
        "replicates": REPLICATES,
        "configs": CONFIGS,
        "condition_ids": sorted(condition_map()),
        "condition_map_sha256": sha256_text(
            json.dumps(sealed_payload(), indent=2, ensure_ascii=False) + "\n"),
        "skill_sha256": sha256_file(SKILL_FILE) if SKILL_FILE.is_file() else None,
        "foil_prompt_prefix": FOIL_PROMPT_PREFIX,
        "tools": spec["tools"],
        "allowed_tools": spec["allowed_tools"],
        "budgets": spec["budgets"],
        "timeout_seconds": spec["timeout_seconds"],
        "dataset_revision": spec["dataset_revision"],
        "contamination_status": CONTAMINATION_STATUS,
        "as_of": now(),
        "units": units,
    }


# --------------------------------------------------------------------------- #
# unit plans - argv, env, cwd, settings                                        #
# --------------------------------------------------------------------------- #

#: Parent-session variables a nested `claude -p` must not inherit. Leaving them in
#: place lets the child attach to the caller's session, which would silently
#: destroy the per-unit isolation the manifest claims.
STRIPPED_ENV_PREFIXES = ("CLAUDECODE", "CLAUDE_CODE_")
STRIPPED_ENV_EXACT = ("CLAUDE_PID",)


def child_env(extra: dict[str, str], base: dict[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if base is None else base)
    cleaned = {
        key: value for key, value in source.items()
        if not key.startswith(STRIPPED_ENV_PREFIXES) and key not in STRIPPED_ENV_EXACT
    }
    cleaned.update(extra)
    return cleaned


def settings_payload(broker: Path | None = None,
                     python_executable: str | None = None) -> dict[str, Any]:
    """The generated settings file: the broker PreToolUse hook and nothing else.

    The command is resolved at runtime from this file's own location and the
    running interpreter, so the settings never carry a machine-specific path
    that was baked in when the harness was written.
    """
    broker_path = Path(broker) if broker is not None else BROKER
    executable = python_executable or sys.executable or "python"
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'"{executable}" "{broker_path.as_posix()}"',
                        }
                    ],
                }
            ]
        }
    }


def build_argv(benchmark: str, unit: dict[str, Any], condition: str,
               settings_file: Path) -> list[str]:
    """The exact command line. Flags are identical across arms except the skill file."""
    spec = BENCHMARKS[benchmark]
    # The model is written literally rather than as foil_models' `{model}` token,
    # so the printed argv is the argv, with no substitution left to imagine.
    argv = [
        "claude", "-p",
        "--output-format", "json",
        "--model", unit["model"],
        "--effort", unit["effort"],
        "--tools", spec["tools"],
        "--settings", str(settings_file),
    ]
    if spec["allowed_tools"]:
        argv += ["--allowedTools", ",".join(spec["allowed_tools"])]
    if condition == "FOIL":
        argv += ["--append-system-prompt-file", str(SKILL_FILE)]
    return argv


def build_unit_plan(benchmark: str, unit: dict[str, Any], item: dict[str, Any],
                    *, settings_file: Path, guard_state: Path,
                    env_base: dict[str, str] | None = None) -> dict[str, Any]:
    """Everything a unit needs, assembled without side effects, so it can be asserted on."""
    condition = condition_map()[unit["condition_id"]]
    prompt = build_prompt(benchmark, item, condition)
    if sha256_text(prompt) != unit["prompt_sha256"]:
        raise PrepareError(
            f"{unit['unit']}: prompt digest does not match the manifest; the item file, "
            "the prompt builder or the manifest has moved since preparation"
        )
    env_extra = {
        "FOIL_TASK_RUN": str(guard_state),
        "FOIL_TASK_ID": unit["unit"],
        "FOIL_TASK_CONDITION": unit["condition_id"],
        "FOIL_TASK_PROMPT_SHA256": unit["prompt_sha256"],
    }
    return {
        "unit": unit["unit"],
        "benchmark": benchmark,
        "config": unit["config"],
        "condition_id": unit["condition_id"],
        "argv": build_argv(benchmark, unit, condition, settings_file),
        "prompt": prompt,
        "prompt_delivery": "stdin",
        "delivered_prompt_sha256": sha256_text(delivered_prompt(prompt)),
        "env_extra": env_extra,
        "env": child_env(env_extra, env_base),
        "settings": settings_payload(),
        "settings_file": str(settings_file),
        "guard_state": str(guard_state),
        "timeout_seconds": BENCHMARKS[benchmark]["timeout_seconds"],
    }


@contextmanager
def _isolated_process_context(cwd: Path, env: dict[str, str]) -> Iterator[None]:
    """Run the child from `cwd` with `env`.

    `foil_models._cli` deliberately exposes no cwd/env parameters, and this
    harness does not get to edit it, so the process state is swapped around the
    call and restored on every path. Units are executed sequentially for exactly
    this reason: process-global state cannot be shared by concurrent workers.
    """
    previous_cwd = Path.cwd()
    previous_env = dict(os.environ)
    os.chdir(cwd)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous_env)
        os.chdir(previous_cwd)


# --------------------------------------------------------------------------- #
# prepare                                                                      #
# --------------------------------------------------------------------------- #

def cmd_prepare(benchmark: str) -> int:
    write_sealed_map()
    items = SELECTORS[benchmark]()
    payload = {
        "schema": "foil-four-config-items/v1",
        "benchmark": benchmark,
        "benchmark_label": BENCHMARKS[benchmark]["label"],
        "run_date": RUN_DATE,
        "selection_seed": BENCHMARKS[benchmark]["selection_seed"],
        "dataset_revision": BENCHMARKS[benchmark]["dataset_revision"],
        "contamination_status": CONTAMINATION_STATUS,
        "gold_opened": False,
        "note": "Questions only. No gold field is written by this harness at any point.",
        "items": items,
    }
    _write_json(items_path(benchmark), payload)
    manifest = build_manifest(benchmark, items)
    _write_json(manifest_path(benchmark), manifest)
    print(json.dumps({
        "prepared": benchmark,
        "items": len(items),
        "units": len(manifest["units"]),
        "items_file": str(items_path(benchmark).relative_to(ROOT)),
        "manifest_file": str(manifest_path(benchmark).relative_to(ROOT)),
        "condition_map_sha256": manifest["condition_map_sha256"],
    }, indent=2))
    return 0


def cmd_check_only(benchmark: str) -> int:
    """Offline validation of the committed artifacts. Never touches the network.

    This is what CI runs. It cannot download a dataset, so it checks the things
    that do not need one: that the preregistration exists and names this
    configuration, that the sealed map matches the seed-derived map and the hash
    the protocol pinned, and - if a manifest has been prepared - that every
    prompt digest still reproduces from the committed item file.
    """
    report: dict[str, Any] = {"benchmark": benchmark, "checks": [], "ok": True}

    def check(name: str, ok: bool, detail: str = "") -> None:
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            report["ok"] = False

    check("protocol_exists", PROTOCOL.is_file(), str(PROTOCOL.relative_to(ROOT)))
    protocol_text = PROTOCOL.read_text(encoding="utf-8") if PROTOCOL.is_file() else ""
    for config in CONFIGS:
        check(f"protocol_names_{config}", config in protocol_text)
    check("protocol_names_order_seed", str(ORDER_SEED) in protocol_text)
    check("protocol_names_selection_seed",
          str(BENCHMARKS[benchmark]["selection_seed"]) in protocol_text)
    check("protocol_names_foil_prefix", FOIL_PROMPT_PREFIX.strip() in protocol_text)

    expected_seal = json.dumps(sealed_payload(), indent=2, ensure_ascii=False) + "\n"
    expected_sha = sha256_text(expected_seal)
    check("protocol_pins_condition_map_sha256", expected_sha in protocol_text, expected_sha)
    if SEALED_MAP.is_file():
        check("sealed_map_matches_seed",
              SEALED_MAP.read_text(encoding="utf-8") == expected_seal)
    else:
        check("sealed_map_present_or_absent", True, "not yet written")

    if manifest_path(benchmark).is_file() and items_path(benchmark).is_file():
        manifest = _read_json(manifest_path(benchmark))
        items = {row["index"]: row for row in _read_json(items_path(benchmark))["items"]}
        mismatched = []
        for unit in manifest["units"]:
            item = items.get(unit["item_index"])
            if item is None:
                mismatched.append(unit["unit"])
                continue
            condition = condition_map()[unit["condition_id"]]
            if sha256_text(build_prompt(benchmark, item, condition)) != unit["prompt_sha256"]:
                mismatched.append(unit["unit"])
        check("manifest_prompt_digests_reproduce", not mismatched, ",".join(mismatched[:5]))
        sessions = [unit["isolation_session_id"] for unit in manifest["units"]]
        check("isolation_ids_unique", len(set(sessions)) == len(sessions))
        check("unit_count",
              len(manifest["units"]) == len(items) * len(CONFIGS) * len(CONDITIONS))
        check("manifest_pins_condition_map_sha256",
              manifest.get("condition_map_sha256") == expected_sha)
    else:
        check("manifest_present_or_absent", True, "not yet prepared")

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


# --------------------------------------------------------------------------- #
# run                                                                          #
# --------------------------------------------------------------------------- #

def _model_spec(benchmark: str, unit: dict[str, Any], argv: list[str]) -> fm.ModelSpec:
    """A `claude_cli` spec whose argv is this unit's argv. No new adapter, no new parser."""
    return fm.spec_from_row({
        "preset": "claude_cli",
        "id": f"claude-{unit['config']}",
        "model": unit["model"],
        "command": argv,
        "timeout_seconds": BENCHMARKS[benchmark]["timeout_seconds"],
    })


def _load_predictions(benchmark: str) -> dict[str, Any]:
    path = predictions_path(benchmark)
    if path.is_file():
        return _read_json(path)
    return {
        "schema": "foil-four-config-predictions/v1",
        "benchmark": benchmark,
        "run_date": RUN_DATE,
        "gold_opened": False,
        "replicates": REPLICATES,
        "predictions": [],
    }


def _record_prediction(benchmark: str, row: dict[str, Any]) -> None:
    """Written after every unit, so a crash keeps what already ran."""
    payload = _load_predictions(benchmark)
    payload["predictions"] = [
        existing for existing in payload["predictions"] if existing["unit"] != row["unit"]
    ] + [row]
    payload["predictions"].sort(key=lambda item: item["unit"])
    payload["updated_at"] = now()
    _write_json(predictions_path(benchmark), payload)


def _execute_unit(benchmark: str, unit: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    spec_meta = BENCHMARKS[benchmark]
    guard_state = GUARD_DIR / benchmark / f"{unit['unit']}.json"
    workdir = Path(tempfile.mkdtemp(prefix="foil-4cfg-"))
    settings_file = workdir / "foil_settings.json"
    plan = build_unit_plan(benchmark, unit, item,
                           settings_file=settings_file, guard_state=guard_state)
    settings_file.write_text(json.dumps(plan["settings"], indent=2) + "\n", encoding="utf-8")

    state = tg.start_state(
        task_id=unit["unit"], prompt=plan["prompt"], condition=unit["condition_id"],
        budgets=dict(spec_meta["budgets"]),
        dataset_revision=spec_meta["dataset_revision"], as_of=now(),
        model=unit["model"], effort=unit["effort"],
        allowed_tools=list(spec_meta["allowed_tools"]),
        isolation_session_id=unit["isolation_session_id"], state_path=guard_state,
    )
    guard_state.parent.mkdir(parents=True, exist_ok=True)
    _save_guard_state(guard_state, state)

    spec = _model_spec(benchmark, unit, plan["argv"])
    status, answer, invalid_reason, usage, finish = "OK", None, None, {}, ""
    text = ""
    is_error: bool | None = None
    try:
        with _isolated_process_context(workdir, plan["env"]):
            response = fm.complete(spec, plan["prompt"])
        text, usage, finish = response.text, dict(response.usage), response.finish_reason
        is_error = bool(usage.get("is_error", False))
        # Two independent signals, and both are consulted on purpose: the
        # envelope's own `is_error` flag, and a `subtype` that is anything other
        # than "success". Either alone can miss a case - a failure flagged without
        # a changed subtype, or a non-success subtype on an unflagged envelope -
        # and scoring a failed run is worse than recording an extra INVALID.
        if is_error or finish != "success":
            status = "INVALID"
            invalid_reason = f"error envelope: is_error={is_error}, subtype={finish!r}"
        else:
            answer, invalid_reason = extract_answer(text, spec_meta["answer_kind"])
            if answer is None:
                status = "INVALID"
    except fm.ModelError as error:
        status, invalid_reason = "INVALID", f"model error: {error}"

    final_state = tg.load(guard_state)
    tg.close(final_state, result="COMMITTED" if status == "OK" else "INVALID")
    _save_guard_state(guard_state, final_state)
    attest = tg.attest(final_state)

    receipt = {
        "schema": "foil-four-config-receipt/v1",
        "unit": unit["unit"],
        "benchmark": benchmark,
        "item_id": unit["item_id"],
        "item_sha256": unit["item_sha256"],
        "condition_id": unit["condition_id"],
        "config": unit["config"],
        "model": unit["model"],
        "effort": unit["effort"],
        "status": status,
        "invalid_reason": invalid_reason,
        "prompt_sha256": unit["prompt_sha256"],
        "delivered_prompt_sha256": plan["delivered_prompt_sha256"],
        "prediction_sha256": sha256_text(answer) if answer is not None else None,
        "response_sha256": sha256_text(text),
        "session_id": usage.get("session_id"),
        "isolation_session_id": unit["isolation_session_id"],
        "total_cost_usd": usage.get("total_cost_usd"),
        "num_turns": usage.get("num_turns"),
        "duration_ms": usage.get("duration_ms"),
        "finish_reason": finish,
        "is_error": is_error,
        "decoding": dict(spec.decoding),
        "determinism": spec.determinism,
        "replicates": REPLICATES,
        "dataset_revision": spec_meta["dataset_revision"],
        "as_of": now(),
        "contamination_status": CONTAMINATION_STATUS,
        "gold_opened": False,
        "guard_attest": {"valid": attest["valid"], "head": attest.get("head"),
                         "used": attest.get("used"), "budgets": attest.get("budgets")},
        "guard_attest_sha256": sha256_text(json.dumps(attest, sort_keys=True, default=str)),
        "allowed_tools": list(spec_meta["allowed_tools"]),
        "tools_flag": spec_meta["tools"],
    }
    _write_json(RECEIPT_DIR / benchmark / f"{unit['unit']}.json", receipt)
    _record_prediction(benchmark, {
        "unit": unit["unit"], "item_id": unit["item_id"], "config": unit["config"],
        "condition_id": unit["condition_id"], "status": status, "answer": answer,
        "invalid_reason": invalid_reason,
    })
    shutil.rmtree(workdir, ignore_errors=True)
    return receipt


def cmd_run(benchmark: str, configs: list[str], limit: int | None, dry_run: bool) -> int:
    manifest = _read_json(manifest_path(benchmark))
    items = {row["index"]: row for row in _read_json(items_path(benchmark))["items"]}
    selected = [unit for unit in manifest["units"] if unit["config"] in configs]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        print("no units selected", file=sys.stderr)
        return 1

    if dry_run:
        for unit in selected:
            plan = build_unit_plan(
                benchmark, unit, items[unit["item_index"]],
                settings_file=Path("<generated per-unit temp dir>") / "foil_settings.json",
                guard_state=GUARD_DIR / benchmark / f"{unit['unit']}.json",
            )
            print(json.dumps({
                "unit": plan["unit"],
                "config": plan["config"],
                "condition_id": plan["condition_id"],
                "cwd": "<fresh empty temp dir created per unit>",
                "argv": plan["argv"],
                "prompt_delivery": "stdin",
                "prompt_sha256": unit["prompt_sha256"],
                "delivered_prompt_sha256": plan["delivered_prompt_sha256"],
                "prompt_bytes": len(plan["prompt"].encode("utf-8")),
                "env_stripped_prefixes": list(STRIPPED_ENV_PREFIXES) + list(STRIPPED_ENV_EXACT),
                "env_added": plan["env_extra"],
                "settings": plan["settings"],
                "timeout_seconds": plan["timeout_seconds"],
                "writes": "none (dry run)",
            }, indent=2))
        print(json.dumps({"dry_run": True, "units": len(selected),
                          "billable_calls": 0, "files_written": 0}, indent=2))
        return 0

    for unit in selected:
        receipt = _execute_unit(benchmark, unit, items[unit["item_index"]])
        print(json.dumps({"unit": receipt["unit"], "status": receipt["status"],
                          "invalid_reason": receipt["invalid_reason"]}))
    return 0


# --------------------------------------------------------------------------- #
# score                                                                        #
# --------------------------------------------------------------------------- #

def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True,
                          capture_output=True, check=False, timeout=30)


def require_committed(path: Path) -> None:
    """Gold stays shut until the predictions cannot be edited without a trace.

    Two conditions, both necessary: the working tree is clean for that file
    (nothing staged or modified) and the file has at least one commit. Checking
    only the first would pass for a file git has never seen.
    """
    relative = path.relative_to(ROOT).as_posix()
    status = _git(["status", "--porcelain", "--", relative])
    if status.returncode != 0:
        raise NotCommitted(f"git status failed for {relative}: {status.stderr.strip()}")
    if status.stdout.strip():
        raise NotCommitted(
            f"{relative} has uncommitted changes ({status.stdout.strip()!r}); commit the "
            "predictions before scoring - gold is not opened while a prediction can move"
        )
    log = _git(["log", "-1", "--format=%H", "--", relative])
    if log.returncode != 0 or not log.stdout.strip():
        raise NotCommitted(f"{relative} has no commit; commit the predictions before scoring")


def _gold_for(benchmark: str) -> dict[str, str]:
    """Opened only from `score`, and only after `require_committed` has passed."""
    if benchmark == "gpqa":
        import gpqa_prepare_score as gpqa

        _, gold = gpqa.prepare()
        return gold
    import browsecomp_four_way_prepare_score as bc

    rows = list(csv.DictReader(io.StringIO(bc.fetch(bc.URL).decode("utf-8-sig"))))
    by_prefix = {bc.row_fingerprint(row)[:8]: row for row in rows}
    gold: dict[str, str] = {}
    for item in _read_json(items_path(benchmark))["items"]:
        row = by_prefix[item["id"].split("-")[-1]]
        gold[item["id"]] = bc.decrypt(row["answer"], row["canary"])
    return gold


def _normaliser(benchmark: str):
    if benchmark == "gpqa":
        import gpqa_prepare_score as gpqa

        return gpqa.norm
    import browsecomp_four_way_prepare_score as bc

    return bc.normalize


def cmd_score(benchmark: str) -> int:
    path = predictions_path(benchmark)
    if not path.is_file():
        raise NotCommitted(f"{path} does not exist")
    require_committed(path)

    mapping = condition_map()
    if not SEALED_MAP.is_file():
        raise NotCommitted(f"{SEALED_MAP} is missing; the condition map was never sealed")
    sealed = _read_json(SEALED_MAP)
    if sealed["map"] != mapping:
        raise NotCommitted("sealed condition map disagrees with the seed-derived map")

    predictions = _read_json(path)["predictions"]
    gold = _gold_for(benchmark)
    normalise = _normaliser(benchmark)

    outcome: dict[tuple[str, str, str], Any] = {}
    invalid: list[dict[str, Any]] = []
    for row in predictions:
        key = (row["config"], row["item_id"], mapping[row["condition_id"]])
        if row["status"] != "OK":
            invalid.append({"unit": row["unit"], "reason": row.get("invalid_reason")})
            outcome[key] = None
            continue
        outcome[key] = normalise(row["answer"]) == normalise(gold[row["item_id"]])

    item_ids = sorted({row["item_id"] for row in predictions})
    per_config: list[dict[str, Any]] = []
    raw_p: list[float] = []
    for config in CONFIGS:
        pairs, dropped = [], []
        for item_id in item_ids:
            base = outcome.get((config, item_id, "BASE"))
            foil = outcome.get((config, item_id, "FOIL"))
            if base is None or foil is None:
                dropped.append(item_id)
                continue
            pairs.append((base, foil))
        report = ps.paired_report(pairs, first_label="BASE", second_label="FOIL")
        report["config"] = config
        report["model"] = CONFIGS[config]["model"]
        report["effort"] = CONFIGS[config]["effort"]
        report["excluded_invalid_items"] = dropped
        per_config.append(report)
        raw_p.append(report["primary_test"]["p_value"])

    holm = ps.holm_adjust(raw_p)
    for report, adjusted in zip(per_config, holm):
        report["primary_test"]["holm_adjusted_p"] = adjusted

    results = {
        "schema": "foil-four-config-results/v1",
        "benchmark": benchmark,
        "benchmark_label": BENCHMARKS[benchmark]["label"],
        "run_date": RUN_DATE,
        "gold_opened": True,
        "replicates": REPLICATES,
        "condition_map": mapping,
        "condition_map_sha256": sha256_file(SEALED_MAP),
        "predictions_sha256": sha256_file(path),
        "scorer": "gpqa_prepare_score.norm" if benchmark == "gpqa"
                  else "browsecomp_four_way_prepare_score.normalize (exact-normalized, "
                       "not the official BrowseComp LLM judge)",
        "multiplicity": "Holm across the four configurations on the primary mid-p p-values",
        "invalid_units": invalid,
        "per_config": per_config,
        "validity_boundary": (
            "Exploratory. One replicate per cell against a model class the harness "
            "declares NONDETERMINISTIC, so a per-item outcome mixes effect with "
            "sampling noise. Item counts are far below the size at which the "
            "preregistered test has usable power; a null here is not evidence of "
            "equivalence, and a positive result is directional only."
        ),
    }
    _write_json(results_path(benchmark), results)
    print(json.dumps(results, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--benchmark", required=True, choices=sorted(BENCHMARKS))
    prepare.add_argument("--check-only", action="store_true",
                         help="offline validation of committed artifacts; no network")

    run = sub.add_parser("run")
    run.add_argument("--benchmark", required=True, choices=sorted(BENCHMARKS))
    run.add_argument("--config", action="append", choices=sorted(CONFIGS),
                     help="repeatable; default is all four")
    run.add_argument("--limit", type=int)
    run.add_argument("--dry-run", action="store_true")

    score = sub.add_parser("score")
    score.add_argument("--benchmark", required=True, choices=sorted(BENCHMARKS))

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return cmd_check_only(args.benchmark) if args.check_only else cmd_prepare(args.benchmark)
    if args.command == "run":
        return cmd_run(args.benchmark, args.config or sorted(CONFIGS), args.limit, args.dry_run)
    return cmd_score(args.benchmark)


if __name__ == "__main__":
    raise SystemExit(main())
