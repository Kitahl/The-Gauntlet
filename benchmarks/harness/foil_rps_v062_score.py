#!/usr/bin/env python3
"""Fail-closed paired scorer for RPS v0.6.2 benchmark rows."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path


_TOP_FIELDS = frozenset(
    {
        "benchmark",
        "item_id",
        "condition",
        "correct",
        "replicate",
        "input_tokens",
        "output_tokens",
        "rps_v062",
    }
)
_TRACE_FIELDS = frozenset(
    {
        "schema",
        "recommendation",
        "reason",
        "candidate_digest",
        "host_outcome",
        "rival_requested",
        "rival_used",
        "abstained",
        "base_answer_preserved",
        "execution_authorized",
        "answer_mutated",
        "promotion_authorized",
    }
)
_RECOMMENDATIONS = frozenset(
    {"STAND_DOWN", "REQUEST_BLIND_RIVAL", "CORRELATED_AGREEMENT", "ABSTAIN"}
)
_HOST_OUTCOMES = frozenset(
    {"CONFIRMED", "CONTRADICTED", "NOT_APPLICABLE", "UNCERTAIN"}
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _boolean(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _validate_trace(raw: object, *, context: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"{context}.rps_v062 must be an object")
    unknown = set(raw) - _TRACE_FIELDS
    missing = _TRACE_FIELDS - set(raw)
    if unknown or missing:
        raise ValueError(
            f"{context}.rps_v062 closed-schema mismatch: "
            f"unknown={sorted(unknown)!r}, missing={sorted(missing)!r}"
        )
    if raw["schema"] != "foil.rps-v062-shadow-decision.v1":
        raise ValueError(f"{context}: unknown RPS v0.6.2 trace schema")
    recommendation = raw["recommendation"]
    if recommendation not in _RECOMMENDATIONS:
        raise ValueError(f"{context}: invalid recommendation")
    _text(f"{context}.reason", raw["reason"])
    _digest(f"{context}.candidate_digest", raw["candidate_digest"])
    host_outcome = raw["host_outcome"]
    if host_outcome not in _HOST_OUTCOMES:
        raise ValueError(f"{context}: invalid host_outcome")
    for field in (
        "rival_requested",
        "rival_used",
        "abstained",
        "base_answer_preserved",
        "execution_authorized",
        "answer_mutated",
        "promotion_authorized",
    ):
        _boolean(f"{context}.{field}", raw[field])
    if raw["rival_used"] and not raw["rival_requested"]:
        raise ValueError(f"{context}: rival_used requires rival_requested")
    if raw["abstained"] != (recommendation == "ABSTAIN"):
        raise ValueError(f"{context}: abstained must equal the ABSTAIN recommendation")
    if recommendation == "REQUEST_BLIND_RIVAL" and (
        not raw["rival_requested"] or raw["rival_used"]
    ):
        raise ValueError(f"{context}: request recommendation has inconsistent rival state")
    if raw["base_answer_preserved"] is not True:
        raise ValueError(f"{context}: base answer was not preserved")
    for field in ("execution_authorized", "answer_mutated", "promotion_authorized"):
        if raw[field] is not False:
            raise ValueError(f"{context}: shadow authority invariant violated by {field}")
    unresolved = host_outcome in {"NOT_APPLICABLE", "UNCERTAIN"}
    if recommendation == "STAND_DOWN" and (
        host_outcome != "CONFIRMED" or raw["rival_requested"] or raw["rival_used"]
    ):
        raise ValueError(f"{context}: invalid STAND_DOWN transition")
    if recommendation == "REQUEST_BLIND_RIVAL" and not unresolved:
        raise ValueError(f"{context}: only unresolved host checks may request a rival")
    if recommendation == "CORRELATED_AGREEMENT" and (
        not unresolved or not raw["rival_requested"] or not raw["rival_used"]
    ):
        raise ValueError(f"{context}: invalid correlated-agreement transition")
    if recommendation == "ABSTAIN":
        contradicted = host_outcome == "CONTRADICTED"
        rival_disagreement = unresolved and raw["rival_requested"] and raw["rival_used"]
        if not (contradicted or rival_disagreement):
            raise ValueError(f"{context}: invalid abstention transition")
        if contradicted and (raw["rival_requested"] or raw["rival_used"]):
            raise ValueError(f"{context}: contradicted checks must not consume a rival")
    return raw


def load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    identities: set[tuple[str, str, str, int]] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        context = f"{path}:{line_no}"
        try:
            raw = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{context}: invalid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{context}: row must be an object")
        unknown = set(raw) - _TOP_FIELDS
        missing = {"benchmark", "item_id", "condition", "correct"} - set(raw)
        if unknown or missing:
            raise ValueError(
                f"{context}: closed-schema mismatch: "
                f"unknown={sorted(unknown)!r}, missing={sorted(missing)!r}"
            )
        row = dict(raw)
        _text(f"{context}.benchmark", row["benchmark"])
        if not isinstance(row["item_id"], (str, int)) or isinstance(row["item_id"], bool):
            raise ValueError(f"{context}.item_id must be text or integer")
        _text(f"{context}.condition", row["condition"])
        _boolean(f"{context}.correct", row["correct"])
        row.setdefault("replicate", 0)
        _count(f"{context}.replicate", row["replicate"])
        for field in ("input_tokens", "output_tokens"):
            if field in row:
                _count(f"{context}.{field}", row[field])
        if row["condition"] == "RPS_062":
            if "rps_v062" not in row:
                raise ValueError(f"{context}: RPS_062 row requires rps_v062 trace")
            row["rps_v062"] = _validate_trace(row["rps_v062"], context=context)
        elif "rps_v062" in row:
            raise ValueError(f"{context}: comparator row cannot carry RPS trace")
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


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _total(row: dict[str, object]) -> float | None:
    if "input_tokens" not in row or "output_tokens" not in row:
        return None
    return float(row["input_tokens"]) + float(row["output_tokens"])


def paired(rows: list[dict[str, object]], comparator: str = "DIRECT") -> dict[str, object]:
    grouped: dict[tuple[str, str, int], dict[str, dict[str, object]]] = {}
    for row in rows:
        if row["condition"] not in {comparator, "RPS_062"}:
            continue
        key = (str(row["benchmark"]), str(row["item_id"]), int(row["replicate"]))
        conditions = grouped.setdefault(key, {})
        condition = str(row["condition"])
        if condition in conditions:
            raise ValueError(f"duplicate condition in pair {key!r}")
        conditions[condition] = row
    pairs = [
        (conditions[comparator], conditions["RPS_062"])
        for conditions in grouped.values()
        if comparator in conditions and "RPS_062" in conditions
    ]
    rescues = damages = 0
    abstentions = rival_requests = rival_uses = correlated_agreements = 0
    host_outcomes: Counter[str] = Counter()
    output_multipliers: list[float] = []
    total_multipliers: list[float] = []
    for base, observed in pairs:
        base_correct = base["correct"] is True
        observed_correct = observed["correct"] is True
        rescues += int(not base_correct and observed_correct)
        damages += int(base_correct and not observed_correct)
        trace = observed["rps_v062"]
        assert isinstance(trace, dict)
        abstentions += int(trace["abstained"] is True)
        rival_requests += int(trace["rival_requested"] is True)
        rival_uses += int(trace["rival_used"] is True)
        correlated_agreements += int(trace["recommendation"] == "CORRELATED_AGREEMENT")
        if trace["host_outcome"] is not None:
            host_outcomes[str(trace["host_outcome"])] += 1
        if "output_tokens" in base and "output_tokens" in observed:
            denominator = float(base["output_tokens"])
            if denominator > 0:
                output_multipliers.append(float(observed["output_tokens"]) / denominator)
        base_total = _total(base)
        observed_total = _total(observed)
        if base_total is not None and observed_total is not None and base_total > 0:
            total_multipliers.append(observed_total / base_total)
    n = len(pairs)
    return {
        "schema": "foil.rps-v062-paired-score.v1",
        "comparator": comparator,
        "n_pairs": n,
        "rescues": rescues,
        "damages": damages,
        "net_rescues": rescues - damages,
        "abstentions": abstentions,
        "abstention_rate": abstentions / n if n else None,
        "rival_requests": rival_requests,
        "rival_request_rate": rival_requests / n if n else None,
        "rival_uses": rival_uses,
        "correlated_agreements": correlated_agreements,
        "host_outcome_counts": dict(sorted(host_outcomes.items())),
        "mean_output_token_multiplier": _mean(output_multipliers),
        "median_output_token_multiplier": _median(output_multipliers),
        "mean_total_token_multiplier": _mean(total_multipliers),
        "median_total_token_multiplier": _median(total_multipliers),
        "total_token_definition": "input_tokens_plus_output_tokens",
        "total_cost_gate_evaluable": len(total_multipliers) == n and n > 0,
        "answer_mutations": 0,
        "execution_authorizations": 0,
        "promotion_authorizations": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--comparator", default="DIRECT")
    args = parser.parse_args()
    result = paired(load_jsonl(args.jsonl), args.comparator)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
