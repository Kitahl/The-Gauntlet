"""Lightweight, provider-neutral FOIL run-cost receipts.

Every field is actual measured consumption or ``None`` when the runtime cannot
observe it.  Missing values are never guessed, and heterogeneous units are never
collapsed into a fabricated scalar "total cost".
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, fields
from typing import Any, Mapping, Sequence

SCHEMA = "egrt.foil-run-cost.v1"

COST_FIELDS = (
    "profile_lookup_count",
    "routing_decision_count",
    "model_calls",
    "tool_calls",
    "verification_calls",
    "retry_count",
    "branch_count",
    "revision_count",
    "tokens_in",
    "tokens_out",
    "wall_time_ms",
)

_COUNT_FIELDS = frozenset(COST_FIELDS) - {"wall_time_ms"}
_HASH_FIELDS = ("prompt_sha256", "profile_payload_sha256")


def _validate_count(name: str, value: int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or None")


@dataclass(frozen=True)
class RunCostReceipt:
    task_id: str
    condition: str
    prompt_sha256: str
    profile_payload_sha256: str | None = None
    profile_lookup_count: int | None = None
    routing_decision_count: int | None = None
    model_calls: int | None = None
    tool_calls: int | None = None
    verification_calls: int | None = None
    retry_count: int | None = None
    branch_count: int | None = None
    revision_count: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    wall_time_ms: float | None = None

    def __post_init__(self) -> None:
        for name in ("task_id", "condition"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value)
        for name in _HASH_FIELDS:
            value = getattr(self, name)
            if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a lowercase SHA-256 digest or None")
        for name in _COUNT_FIELDS:
            _validate_count(name, getattr(self, name))
        if self.wall_time_ms is not None:
            if (
                isinstance(self.wall_time_ms, bool)
                or not isinstance(self.wall_time_ms, (int, float))
                or not math.isfinite(float(self.wall_time_ms))
                or float(self.wall_time_ms) < 0.0
            ):
                raise ValueError("wall_time_ms must be a finite non-negative number or None")

    def body(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "task_id": self.task_id,
            "condition": self.condition,
            "prompt_sha256": self.prompt_sha256,
            "profile_payload_sha256": self.profile_payload_sha256,
            **{name: getattr(self, name) for name in COST_FIELDS},
            "raw_prompt_stored": False,
        }

    def trace(self) -> dict[str, object]:
        payload = self.body()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "RunCostReceipt":
        if raw.get("schema") not in (None, SCHEMA):
            raise ValueError("unknown FOIL run-cost schema")
        allowed = {field.name for field in fields(cls)} | {
            "schema",
            "raw_prompt_stored",
            "receipt_sha256",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown run-cost fields: {sorted(unknown)}")
        if raw.get("raw_prompt_stored") not in (None, False):
            raise ValueError("run-cost receipts cannot store raw prompts")
        kwargs = {field.name: raw.get(field.name) for field in fields(cls)}
        receipt = cls(**kwargs)
        expected = raw.get("receipt_sha256")
        if expected is not None and expected != receipt.trace()["receipt_sha256"]:
            raise ValueError("run-cost receipt digest mismatch")
        return receipt


def aggregate_costs(receipts: Sequence[RunCostReceipt]) -> dict[str, int | float | None]:
    """Sum each unit independently; any unavailable component stays unavailable."""

    return {
        name: (
            None
            if any(getattr(receipt, name) is None for receipt in receipts)
            else sum(getattr(receipt, name) for receipt in receipts)  # type: ignore[misc]
        )
        for name in COST_FIELDS
    }


def mean_costs(receipts: Sequence[RunCostReceipt]) -> dict[str, float | None]:
    if not receipts:
        return {name: None for name in COST_FIELDS}
    totals = aggregate_costs(receipts)
    return {
        name: None if totals[name] is None else float(totals[name]) / len(receipts)
        for name in COST_FIELDS
    }


def cost_per_correct(
    receipts: Sequence[RunCostReceipt], correct_count: int
) -> dict[str, float | None]:
    if isinstance(correct_count, bool) or not isinstance(correct_count, int) or correct_count < 0:
        raise ValueError("correct_count must be a non-negative integer")
    totals = aggregate_costs(receipts)
    return {
        name: (
            None
            if correct_count == 0 or totals[name] is None
            else float(totals[name]) / correct_count
        )
        for name in COST_FIELDS
    }


def matched_total_cost(receipts: Sequence[RunCostReceipt]) -> bool:
    """True only when every recorded cost unit is known and exactly matched."""

    if not receipts:
        return False
    vectors = []
    for receipt in receipts:
        vector = tuple(getattr(receipt, name) for name in COST_FIELDS)
        if any(value is None for value in vector):
            return False
        vectors.append(vector)
    return all(vector == vectors[0] for vector in vectors[1:])
