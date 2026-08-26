"""Independent read-only audit for the sealed RPS v0.6.1 small shadow result."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    ROOT
    / "benchmarks"
    / "harness"
    / "foil_rps_v061_hle_shadow_small_schemafix.py"
)


def load_wrapper():
    spec = importlib.util.spec_from_file_location("rps_v061_schemafix_audit", WRAPPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {WRAPPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wrong = [row for row in rows if not row["base_correct"]]
    correct = [row for row in rows if row["base_correct"]]
    base = {"input": 0, "cached_input": 0, "output": 0}
    observer = {"input": 0, "cached_input": 0, "output": 0}
    for row in rows:
        for field in base:
            base[field] += int(row["base_usage"][field])
            observer[field] += int(row["observer_usage"][field])
    base["total"] = base["input"] + base["output"]
    observer["total"] = observer["input"] + observer["output"]
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
        "base_plus_observer_token_multiplier": (
            None
            if base["total"] == 0
            else (base["total"] + observer["total"]) / base["total"]
        ),
    }


def main() -> int:
    wrapper = load_wrapper()
    wrapper.configure()
    base = wrapper.BASE
    expected = base.build_results()
    observed = base.read_json(base.RESULTS)
    if canonical_json(expected) != canonical_json(observed):
        raise RuntimeError("locked scorer recomputation differs from results.json")
    if len(observed["rows"]) != 4 or observed["provider_calls"] != 6:
        raise RuntimeError("row/provider-call conservation failed")
    if observed["structural_microbenchmark"]["passed"] != 6:
        raise RuntimeError("structural microbenchmark failed")
    if any(
        row["answer_mutated"] or row["final_answer"] != row["candidate"]
        for row in observed["rows"]
    ):
        raise RuntimeError("shadow answer identity failed")

    for config_id in (*base.CONFIGS, "OVERALL"):
        subset = (
            observed["rows"]
            if config_id == "OVERALL"
            else [row for row in observed["rows"] if row["config_id"] == config_id]
        )
        if independent_summary(subset) != observed["summaries"][config_id]:
            raise RuntimeError(f"independent summary mismatch: {config_id}")

    receipts = list(base.RECEIPTS.rglob("*.json"))
    if len(receipts) != 6:
        raise RuntimeError("receipt conservation failed")
    for path in receipts:
        receipt = base.read_json(path)
        if receipt["valid"] is not True or receipt["invalid_reasons"] != []:
            raise RuntimeError(f"invalid receipt: {path.name}")
        if any(
            event == "error" or event == "turn.failed"
            for event in receipt["event_types"]
        ):
            raise RuntimeError(f"failed event in receipt: {path.name}")
        if receipt["answer"] is None:
            raise RuntimeError(f"missing structured answer: {path.name}")

    print(
        "independent audit PASS "
        f"results_sha256={sha256_file(base.RESULTS)} rows=4 calls=6 receipts=6"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
