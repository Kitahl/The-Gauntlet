#!/usr/bin/env python3
"""Fail-closed scorer for frozen FOIL RPS benchmark rows.

The historical bundle scorer accepted truthy strings, duplicate identities,
negative token counts, and incomplete RPS telemetry.  This replacement keeps
the public scoring functions but validates the row contract before computing
any result.  Total-token multipliers use input + output tokens; output-only
metrics remain diagnostic.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


RPS_DEFAULT = "RPS_060"
_TOP_FIELDS = frozenset(
    {
        "benchmark",
        "item_id",
        "condition",
        "correct",
        "valid",
        "replicate",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "rps",
    }
)
_RPS_FIELDS = frozenset(
    {
        "p1_outcome",
        "p2_outcome",
        "conflict",
        "repair_triggered",
        "answer_changed",
        "rollback_hinge",
        "tiebreak_used",
    }
)
_OUTCOMES = frozenset({"PASS", "FAIL", "UNCERTAIN", "N/A"})


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _validate_rps(block: object, *, context: str) -> dict[str, object]:
    if not isinstance(block, dict):
        raise ValueError(f"{context}.rps must be an object")
    unknown = set(block) - _RPS_FIELDS
    missing = _RPS_FIELDS - set(block)
    if unknown or missing:
        raise ValueError(
            f"{context}.rps closed-schema mismatch: "
            f"unknown={sorted(unknown)!r}, missing={sorted(missing)!r}"
        )
    p1 = block["p1_outcome"]
    p2 = block["p2_outcome"]
    if p1 not in _OUTCOMES or p2 not in _OUTCOMES:
        raise ValueError(f"{context}.rps outcomes are invalid")
    for field in ("conflict", "repair_triggered", "answer_changed", "tiebreak_used"):
        _require_bool(f"{context}.rps.{field}", block[field])
    rollback = block["rollback_hinge"]
    if rollback is not None:
        _require_nonnegative_int(f"{context}.rps.rollback_hinge", rollback)

    conflict = block["conflict"]
    repair = block["repair_triggered"]
    changed = block["answer_changed"]
    if p1 == "FAIL" and not (conflict and repair):
        raise ValueError(f"{context}: P1 FAIL requires conflict and repair_triggered")
    if p1 == "PASS" and (conflict or repair):
        raise ValueError(f"{context}: P1 PASS cannot claim conflict or repair")
    if repair and not conflict:
        raise ValueError(f"{context}: repair requires conflict")
    if repair and rollback is None:
        raise ValueError(f"{context}: repair requires rollback_hinge")
    if not repair and rollback is not None:
        raise ValueError(f"{context}: rollback_hinge requires repair")
    if changed and not repair:
        raise ValueError(f"{context}: answer_changed requires repair")
    return block


def _validate_row(raw: object, *, context: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"{context}: row must be an object")
    unknown = set(raw) - _TOP_FIELDS
    if unknown:
        raise ValueError(f"{context}: unknown fields {sorted(unknown)!r}")
    for field in ("benchmark", "item_id", "condition", "correct"):
        if field not in raw:
            raise ValueError(f"{context}: missing required field {field!r}")
    row = dict(raw)
    _require_text(f"{context}.benchmark", row["benchmark"])
    if not isinstance(row["item_id"], (str, int)) or isinstance(row["item_id"], bool):
        raise ValueError(f"{context}.item_id must be text or integer")
    if isinstance(row["item_id"], str) and not row["item_id"].strip():
        raise ValueError(f"{context}.item_id must not be empty")
    _require_text(f"{context}.condition", row["condition"])
    _require_bool(f"{context}.correct", row["correct"])
    row.setdefault("valid", True)
    row.setdefault("replicate", 0)
    _require_bool(f"{context}.valid", row["valid"])
    _require_nonnegative_int(f"{context}.replicate", row["replicate"])
    for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
        if field in row:
            _require_nonnegative_int(f"{context}.{field}", row[field])
    if row["condition"].startswith("RPS_"):
        if "rps" not in row:
            raise ValueError(f"{context}: RPS rows require telemetry")
        row["rps"] = _validate_rps(row["rps"], context=context)
    elif "rps" in row:
        raise ValueError(f"{context}: non-RPS rows cannot carry RPS telemetry")
    return row


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    identities: set[tuple[str, str, str, int]] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        context = f"{path}:{line_no}"
        try:
            raw = json.loads(line, object_pairs_hook=_reject_duplicate_object_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{context}: invalid JSON: {exc}") from exc
        row = _validate_row(raw, context=context)
        identity = (
            str(row["benchmark"]),
            str(row["item_id"]),
            str(row["condition"]),
            int(row["replicate"]),
        )
        if identity in identities:
            raise ValueError(f"{context}: duplicate unit identity {identity!r}")
        identities.add(identity)
        rows.append(row)
    return rows


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float | None]:
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / den
    return [max(0.0, center - half), min(1.0, center + half)]


def binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def exact_mcnemar_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    return min(1.0, 2.0 * sum(binom_pmf(k, n) for k in range(m + 1)))


def midp_mcnemar_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    tail = sum(binom_pmf(k, n) for k in range(m + 1))
    observed = binom_pmf(m, n)
    return min(1.0, max(0.0, 2.0 * (tail - 0.5 * observed)))


def median_or_none(values: Iterable[float]) -> float | None:
    rows = list(values)
    return statistics.median(rows) if rows else None


def mean_or_none(values: Iterable[float]) -> float | None:
    rows = list(values)
    return statistics.fmean(rows) if rows else None


def aggregate_replicates(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    groups: defaultdict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["valid"] is True:
            groups[(str(row["benchmark"]), str(row["item_id"]), str(row["condition"]))].append(row)

    aggregated: list[dict[str, object]] = []
    for (benchmark, item_id, condition), group in groups.items():
        correct = sum(row["correct"] is True for row in group) > len(group) / 2
        result: dict[str, object] = {
            "benchmark": benchmark,
            "item_id": item_id,
            "condition": condition,
            "correct": correct,
            "valid": True,
            "replicates": len(group),
        }
        for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
            values = [float(row[field]) for row in group if field in row]
            result[field] = mean_or_none(values)
        if condition.startswith("RPS_"):
            blocks = [row["rps"] for row in group]
            assert all(isinstance(block, dict) for block in blocks)
            telemetry: dict[str, object] = {}
            for field in _RPS_FIELDS:
                values = [block[field] for block in blocks]  # type: ignore[index]
                counts: defaultdict[object, int] = defaultdict(int)
                for value in values:
                    counts[value] += 1
                winner, count = max(counts.items(), key=lambda pair: pair[1])
                telemetry[field] = winner if count > len(values) / 2 else "MIXED"
            result["rps"] = telemetry
        aggregated.append(result)
    return aggregated


def _token_total(row: dict[str, object]) -> float | None:
    if "input_tokens" not in row or "output_tokens" not in row:
        return None
    return float(row["input_tokens"]) + float(row["output_tokens"])


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def condition_summary(rows: Iterable[dict[str, object]], condition: str) -> dict[str, object]:
    selected = [row for row in rows if row["condition"] == condition and row["valid"] is True]
    correct = sum(row["correct"] is True for row in selected)
    output = [float(row["output_tokens"]) for row in selected if "output_tokens" in row]
    total = [value for row in selected if (value := _token_total(row)) is not None]
    return {
        "condition": condition,
        "n": len(selected),
        "correct": correct,
        "accuracy": correct / len(selected) if selected else None,
        "wilson95": wilson(correct, len(selected)),
        "mean_output_tokens": mean_or_none(output),
        "median_output_tokens": median_or_none(output),
        "mean_total_tokens": mean_or_none(total),
        "median_total_tokens": median_or_none(total),
        "total_token_definition": "input_tokens_plus_output_tokens",
    }


def paired(
    rows: Iterable[dict[str, object]],
    comparator: str,
    rps_condition: str = RPS_DEFAULT,
) -> dict[str, object]:
    by: defaultdict[tuple[str, str], dict[str, dict[str, object]]] = defaultdict(dict)
    for row in rows:
        if row["valid"] is True and row["condition"] in {comparator, rps_condition}:
            key = (str(row["benchmark"]), str(row["item_id"]))
            condition = str(row["condition"])
            if condition in by[key]:
                raise ValueError(f"duplicate aggregated condition for pair {key!r}")
            by[key][condition] = row
    pairs = [
        (conditions[comparator], conditions[rps_condition])
        for conditions in by.values()
        if comparator in conditions and rps_condition in conditions
    ]

    both_correct = comparator_only = rps_only = both_wrong = 0
    added_output: list[float] = []
    output_multipliers: list[float] = []
    total_multipliers: list[float] = []
    conflicts: list[tuple[bool, bool]] = []
    repairs: list[tuple[bool, bool]] = []
    p1_fail_base_wrong = p1_nonfail_base_wrong = p2_fail_after_p1_nonfail = 0

    for base, rps in pairs:
        base_correct = base["correct"] is True
        rps_correct = rps["correct"] is True
        if base_correct and rps_correct:
            both_correct += 1
        elif base_correct:
            comparator_only += 1
        elif rps_correct:
            rps_only += 1
        else:
            both_wrong += 1

        base_output = float(base["output_tokens"]) if "output_tokens" in base else None
        rps_output = float(rps["output_tokens"]) if "output_tokens" in rps else None
        if base_output is not None and rps_output is not None:
            added_output.append(rps_output - base_output)
            ratio = _ratio(rps_output, base_output)
            if ratio is not None:
                output_multipliers.append(ratio)
        total_ratio = _ratio(_token_total(rps), _token_total(base))
        if total_ratio is not None:
            total_multipliers.append(total_ratio)

        telemetry = rps["rps"]
        assert isinstance(telemetry, dict)
        conflict = telemetry["conflict"] is True
        conflicts.append((conflict, not base_correct))
        if telemetry["repair_triggered"] is True:
            repairs.append((base_correct, rps_correct))
        if not base_correct:
            if telemetry["p1_outcome"] == "FAIL":
                p1_fail_base_wrong += 1
            else:
                p1_nonfail_base_wrong += 1
                if telemetry["p2_outcome"] == "FAIL":
                    p2_fail_after_p1_nonfail += 1

    n = len(pairs)
    base_wrong = comparator_only + both_wrong
    conflict_count = sum(conflict for conflict, _ in conflicts)
    conflict_on_wrong = sum(conflict and wrong for conflict, wrong in conflicts)
    repairs_on_wrong = [after for before, after in repairs if not before]
    repairs_on_correct = [after for before, after in repairs if before]
    added_k = max(1.0, sum(added_output) / 1000.0) if added_output else None
    positive_k = (
        max(1.0, sum(max(0.0, value) for value in added_output) / 1000.0)
        if added_output
        else None
    )

    return {
        "comparator": comparator,
        "rps_condition": rps_condition,
        "n_pairs": n,
        "both_correct": both_correct,
        "comparator_only": comparator_only,
        "rps_only": rps_only,
        "both_wrong": both_wrong,
        "rescues": rps_only,
        "damages": comparator_only,
        "net_rescues": rps_only - comparator_only,
        "accuracy_delta": (rps_only - comparator_only) / n if n else None,
        "rescue_damage_ratio": rps_only / comparator_only if comparator_only else None,
        "rescue_damage_ratio_unbounded": bool(rps_only and not comparator_only),
        "midp_mcnemar_two_sided": midp_mcnemar_two_sided(comparator_only, rps_only),
        "exact_mcnemar_two_sided": exact_mcnemar_two_sided(comparator_only, rps_only),
        "mean_added_output_tokens": mean_or_none(added_output),
        "median_added_output_tokens": median_or_none(added_output),
        "mean_output_token_multiplier": mean_or_none(output_multipliers),
        "median_output_token_multiplier": median_or_none(output_multipliers),
        "mean_total_token_multiplier": mean_or_none(total_multipliers),
        "median_total_token_multiplier": median_or_none(total_multipliers),
        "total_token_definition": "input_tokens_plus_output_tokens",
        "total_cost_gate_evaluable": len(total_multipliers) == n and n > 0,
        "net_rescues_per_1k_added_output_tokens": (
            (rps_only - comparator_only) / added_k if added_k is not None else None
        ),
        "rescues_per_1k_positive_added_output_tokens": (
            rps_only / positive_k if positive_k is not None else None
        ),
        "comparator_error_rate": base_wrong / n if n else None,
        "conflict_rate": conflict_count / n if n else None,
        "conflict_precision": conflict_on_wrong / conflict_count if conflict_count else None,
        "conflict_recall": conflict_on_wrong / base_wrong if base_wrong else None,
        "repairs": len(repairs),
        "repair_yield_on_comparator_wrong": (
            sum(repairs_on_wrong) / len(repairs_on_wrong) if repairs_on_wrong else None
        ),
        "damage_given_repair_on_comparator_correct": (
            sum(not value for value in repairs_on_correct) / len(repairs_on_correct)
            if repairs_on_correct
            else None
        ),
        "d1_residual_detection": p1_fail_base_wrong / base_wrong if base_wrong else None,
        "d2_residual_detection": (
            p2_fail_after_p1_nonfail / p1_nonfail_base_wrong
            if p1_nonfail_base_wrong
            else None
        ),
    }


def score(
    rows: list[dict[str, object]],
    *,
    comparators: Iterable[str],
    rps_condition: str,
) -> dict[str, object]:
    benchmarks = sorted({str(row["benchmark"]) for row in rows})
    result: dict[str, object] = {"benchmarks": {}}
    for benchmark in benchmarks:
        selected = [row for row in rows if row["benchmark"] == benchmark]
        conditions = sorted({str(row["condition"]) for row in selected})
        result["benchmarks"][benchmark] = {  # type: ignore[index]
            "conditions": {
                condition: condition_summary(selected, condition)
                for condition in conditions
            },
            "paired_vs_rps": {
                comparator: paired(selected, comparator, rps_condition)
                for comparator in comparators
                if comparator in conditions and rps_condition in conditions
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--rps-condition", default=RPS_DEFAULT)
    parser.add_argument(
        "--comparators", nargs="+", default=["BASE", "FOIL_051", "FRONTIER_OLD"]
    )
    parser.add_argument(
        "--aggregate-replicates", choices=["none", "majority"], default="none"
    )
    args = parser.parse_args()
    rows = load_jsonl(args.jsonl)
    if args.aggregate_replicates == "majority":
        rows = aggregate_replicates(rows)
    print(
        json.dumps(
            score(rows, comparators=args.comparators, rps_condition=args.rps_condition),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
