"""Schema-fixed sealed wrapper for the RPS v0.6.1 small shadow benchmark.

The original attempt remains immutable. This revision removes only the live API's
unsupported `uniqueItems` keyword; the closed parser still enforces uniqueness.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER = ROOT / "benchmarks" / "harness" / "foil_rps_v061_hle_shadow_small.py"
PROTOCOL = ROOT / "benchmarks" / "FOIL_RPS_V061_HLE_SHADOW_SMALL_SCHEMAFIX.md"
FAILED_RECEIPT = (
    ROOT
    / "benchmark_runs"
    / "2026-08-25"
    / "rps_v061_hle_shadow_small"
    / "receipts"
    / "controls"
    / "control-TERRA_LOW.json"
)
FAILURE_REPORT = FAILED_RECEIPT.parents[2] / "failure.md"
OUT = ROOT / "benchmark_runs" / "2026-08-25" / "rps_v061_hle_shadow_small_schemafix"


def load_base():
    spec = importlib.util.spec_from_file_location("rps_v061_small_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def schema_fixed() -> dict[str, Any]:
    schema = copy.deepcopy(BASE.answer_schema())
    schema["properties"]["hinges"].pop("uniqueItems")
    return schema


def configure() -> None:
    BASE.PROTOCOL = PROTOCOL
    BASE.OUT = OUT
    BASE.PRIVATE = OUT / "private"
    BASE.RECEIPTS = OUT / "receipts"
    BASE.ITEMS = OUT / "items.json"
    BASE.MANIFEST = OUT / "manifest.json"
    BASE.SCHEMA = OUT / "answer_schema.json"
    BASE.LOCK = OUT / "config_lock.json"
    BASE.PREDICTIONS = OUT / "predictions.json"
    BASE.RESULTS = OUT / "results.json"
    BASE.REPORT = OUT / "report.md"
    BASE.configure_executor()


def prepare() -> None:
    configure()
    if any(
        path.exists()
        for path in (
            BASE.ITEMS,
            BASE.MANIFEST,
            BASE.SCHEMA,
            BASE.LOCK,
            BASE.PREDICTIONS,
            BASE.RESULTS,
        )
    ):
        raise BASE.ProtocolError("prepare never overwrites an existing experiment")
    if not FAILED_RECEIPT.is_file() or not FAILURE_REPORT.is_file():
        raise BASE.ProtocolError("the stopped original attempt is not preserved")

    items, units = BASE.source_units()
    BASE.write_json(
        BASE.ITEMS,
        {"schema": "foil.rps-v061-hle-shadow-small-schemafix-items.v1", "items": items},
    )
    BASE.write_json(BASE.SCHEMA, schema_fixed())
    manifest = BASE.build_manifest(items, units)
    manifest.update(
        {
            "schema": "foil.rps-v061-hle-shadow-small-schemafix-manifest.v1",
            "runner_sha256": BASE.sha256_file(Path(__file__)),
            "base_runner_sha256": BASE.sha256_file(BASE_RUNNER),
            "supersedes_failed_attempt": str(
                FAILED_RECEIPT.relative_to(ROOT)
            ).replace("\\", "/"),
            "prior_failed_schema_requests": 1,
            "maximum_provider_requests_across_revisions": 7,
            "schema_fix": "removed unsupported uniqueItems; parser uniqueness unchanged",
        }
    )
    BASE.write_json(BASE.MANIFEST, manifest)
    lock_files = (
        PROTOCOL,
        BASE.POLICY_060,
        BASE.POLICY_061,
        BASE.RPS_MODULE,
        BASE.RUNTIME_POLICY,
        Path(__file__),
        BASE_RUNNER,
        BASE.EXECUTOR_PATH,
        BASE.SOURCE_ITEMS,
        BASE.SOURCE_PREDICTIONS,
        BASE.SOURCE_RESULTS,
        FAILED_RECEIPT,
        FAILURE_REPORT,
        BASE.ITEMS,
        BASE.SCHEMA,
        BASE.MANIFEST,
    )
    BASE.write_json(
        BASE.LOCK,
        {
            "schema": "foil.rps-v061-hle-shadow-small-schemafix-lock.v1",
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): BASE.sha256_file(path)
                for path in lock_files
            },
        },
    )
    print("prepared schema-fixed revision: 4 observers, 2 controls, call cap 6")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("prepare", "self-test", "check", "run", "score", "audit")
    )
    command = parser.parse_args().command
    configure()
    if command == "prepare":
        prepare()
    elif command == "self-test":
        BASE.self_test()
    elif command == "check":
        BASE.check()
    elif command == "run":
        BASE.run()
    elif command == "score":
        BASE.score()
    else:
        BASE.audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
