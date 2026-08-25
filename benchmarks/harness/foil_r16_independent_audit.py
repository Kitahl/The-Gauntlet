#!/usr/bin/env python3
"""Independent raw-row audit for a FOIL R1.6 report.

This module intentionally imports neither the R1.6 runner nor its statistics
helpers.  It is a second implementation of the report arithmetic.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Mapping, Sequence

SCHEMA = "foil.r16-no-oracle-discovery-report.v1"
LABELS = (
    "RESULT",
    "FINAL",
    "OPERAND",
    "DROPSTEP",
    "SWAPOP",
    "CONSISTENT_LOCAL",
    "CONSISTENT_GLOBAL",
)
OPERATORS = {
    "M1_RESULT": "RESULT",
    "M2_FINAL": "FINAL",
    "M3_OPERAND": "OPERAND",
    "M4_DROPSTEP": "DROPSTEP",
    "M5_SWAPOP": "SWAPOP",
    "M7_CONSISTENT": "CONSISTENT_LOCAL",
    "M9_CONSISTENT_BIG": "CONSISTENT_GLOBAL",
}
ZERO_KEYS = {
    "provider_calls",
    "external_bot_calls",
    "runtime_model_calls",
    "token_spend",
    "answer_mutations_by_foil",
    "profile_writes",
    "execution_authorizations",
    "promotion_changes",
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _wilson(successes: int, total: int) -> dict[str, float | int | str | None]:
    if total == 0:
        return {
            "successes": successes,
            "total": total,
            "rate": None,
            "interval_name": "Wilson two-sided 95%",
            "lower": None,
            "upper": None,
        }
    z = NormalDist().inv_cdf(0.975)
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        rate * (1 - rate) / total + z * z / (4 * total * total)
    ) / denominator
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "interval_name": "Wilson two-sided 95%",
        "lower": max(0.0, center - radius),
        "upper": min(1.0, center + radius),
    }


def _rates(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        label: _wilson(
            sum(row["class"] == label and bool(row["detected"]) for row in rows),
            sum(row["class"] == label for row in rows),
        )
        for label in LABELS
    }


def _ranks(values: Sequence[float]) -> tuple[float, ...]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[start]] == values[order[end]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in order[start:end]:
            result[index] = rank
        start = end
    return tuple(result)


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True)
    )
    left_mass = sum((item - left_mean) ** 2 for item in left)
    right_mass = sum((item - right_mean) ** 2 for item in right)
    if left_mass == 0 or right_mass == 0:
        raise ValueError("constant vector")
    return numerator / math.sqrt(left_mass * right_mass)


def _association(mutation: Mapping[str, object], natural: Mapping[str, object]) -> dict[str, object]:
    common = [
        label
        for label in LABELS
        if int(mutation[label]["total"]) > 0 and int(natural[label]["total"]) > 0
    ]
    reasons = []
    if len(common) < 3:
        reasons.append("FEWER_THAN_THREE_COMMON_CLASSES")
    x = [float(mutation[label]["rate"]) for label in common]
    y = [float(natural[label]["rate"]) for label in common]
    if x and len(set(x)) < 2:
        reasons.append("MUTATION_RATE_VECTOR_ZERO_VARIANCE")
    if y and len(set(y)) < 2:
        reasons.append("NATURAL_RATE_VECTOR_ZERO_VARIANCE")
    if reasons:
        return {
            "status": "NOT_IDENTIFIABLE",
            "reason_codes": reasons,
            "common_classes": common,
            "spearman": None,
            "exact_permutation_two_sided_p": None,
            "pearson_descriptive": None,
        }
    observed = _pearson(_ranks(x), _ranks(y))
    permutations = tuple(itertools.permutations(y))
    extreme = sum(
        abs(_pearson(_ranks(x), _ranks(candidate))) >= abs(observed) - 1e-15
        for candidate in permutations
    )
    return {
        "status": "ESTIMABLE_SMOKE_ONLY",
        "reason_codes": [],
        "common_classes": common,
        "spearman": observed,
        "exact_permutation_two_sided_p": extreme / len(permutations),
        "exact_permutation_count": len(permutations),
        "pearson_descriptive": _pearson(x, y),
    }


def audit(report: Mapping[str, object]) -> dict[str, object]:
    if report.get("schema") != SCHEMA:
        raise RuntimeError("schema mismatch")
    clone = dict(report)
    claimed = clone.pop("report_sha256", None)
    if claimed != _digest(clone):
        raise RuntimeError("report digest mismatch")
    raw = report.get("raw_rows")
    if not isinstance(raw, list):
        raise RuntimeError("raw rows absent")
    mutation = [row for row in raw if row.get("kind") == "MUTANT"]
    natural = [row for row in raw if row.get("kind") == "NATURAL_MISS"]
    controls = [row for row in raw if row.get("kind") == "CORRECT_CONTROL"]
    if len(raw) != len(mutation) + len(natural) + len(controls):
        raise RuntimeError("unknown raw row kind")
    mutation_rates = _rates(mutation)
    natural_rates = _rates(natural)
    control_rate = _wilson(
        sum(bool(row["detected"]) for row in controls), len(controls)
    )
    if mutation_rates != report.get("mutation_detection_by_class"):
        raise RuntimeError("mutation rates mismatch")
    if natural_rates != report.get("natural_detection_by_class"):
        raise RuntimeError("natural rates mismatch")
    if control_rate != report.get("correct_control_false_fires"):
        raise RuntimeError("control rate mismatch")
    derived_association = _association(mutation_rates, natural_rates)
    if derived_association != report.get("association"):
        raise RuntimeError("association mismatch")
    counts = Counter(str(row["operator_id"]) for row in mutation)
    if counts != Counter({operator: 8 for operator in OPERATORS}):
        raise RuntimeError("operator denominator mismatch")
    conservation = report.get("mutation_conservation")
    if not isinstance(conservation, Mapping):
        raise RuntimeError("conservation absent")
    if conservation.get("attempted") != len(mutation) or not conservation.get("conserved"):
        raise RuntimeError("global conservation mismatch")
    if conservation.get("by_status", {}).get("EXECUTED") != len(mutation):
        raise RuntimeError("executed denominator mismatch")
    costs = report.get("cost_and_authority")
    if not isinstance(costs, Mapping) or any(costs.get(key) != 0 for key in ZERO_KEYS):
        raise RuntimeError("zero-cost or zero-authority invariant mismatch")
    if not all(bool(row.get("a0_preserved")) for row in raw):
        raise RuntimeError("A0 preservation mismatch")
    return {
        "verified": True,
        "report_sha256": claimed,
        "raw_rows": len(raw),
        "mutation_rows": len(mutation),
        "natural_rows": len(natural),
        "control_rows": len(controls),
        "association_status": derived_association["status"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(_canonical(audit(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
