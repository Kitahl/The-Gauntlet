"""Pure, sealed span ledger for FOIL v5 shadow evaluations.

The ledger records declared categories and host-supplied timing/usage facts.  It
does not start processes, perform I/O, call providers, or infer absent costs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

SCHEMA = "egrt.foil-v5-run-ledger.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EFFECT_CATEGORIES = frozenset(
    {
        "local",
        "model",
        "tool",
        "network",
        "subprocess",
        "retry",
        "async",
        "profile",
        "router",
        "parser",
    }
)


class LedgerError(ValueError):
    """A run ledger cannot safely account for the supplied effect or timing."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise LedgerError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_time(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LedgerError(f"{name} must be a non-negative integer nanosecond timestamp")
    return value


class RunLedger:
    """One mutable-until-sealed account of a single evaluation run.

    Every declared category must be covered by either a completed span or an
    explicit observation record.  A covered category may retain ``None`` fields;
    completeness means attribution happened, not that the host observed billing.
    """

    def __init__(
        self,
        *,
        candidate_sha256: str,
        protocol_sha256: str,
        required_categories: frozenset[str] = EFFECT_CATEGORIES,
    ) -> None:
        self._candidate_sha256 = _require_digest("candidate_sha256", candidate_sha256)
        self._protocol_sha256 = _require_digest("protocol_sha256", protocol_sha256)
        if not required_categories or not required_categories.issubset(EFFECT_CATEGORIES):
            raise LedgerError("required_categories must be a non-empty known category set")
        self._categories = set(required_categories)
        self._coverage: dict[str, dict[str, Any]] = {}
        self._spans: dict[str, dict[str, Any]] = {}
        self._run_started_ns: int | None = None
        self._run_ended_ns: int | None = None
        self._sealed: dict[str, Any] | None = None

    def _ensure_mutable(self) -> None:
        if self._sealed is not None:
            raise LedgerError("sealed ledgers are immutable")

    def _require_category(self, category: str) -> None:
        if category not in EFFECT_CATEGORIES:
            raise LedgerError(f"unknown effector category: {category!r}")
        if category not in self._categories:
            raise LedgerError(f"unregistered effector category: {category!r}")

    def begin(self, started_ns: int) -> None:
        self._ensure_mutable()
        if self._run_started_ns is not None:
            raise LedgerError("run already started")
        self._run_started_ns = _require_time("started_ns", started_ns)

    def record_category(
        self,
        category: str,
        *,
        observation: Mapping[str, Any] | None = None,
        reason: str = "observed",
    ) -> None:
        """Mark a category covered without converting unknown values to zero."""

        self._ensure_mutable()
        self._require_category(category)
        if not isinstance(reason, str) or not reason:
            raise LedgerError("reason must be non-empty text")
        if observation is not None and not isinstance(observation, Mapping):
            raise LedgerError("observation must be an object or None")
        self._coverage[category] = {
            "reason": reason,
            "observation": copy.deepcopy(dict(observation)) if observation is not None else None,
        }

    def start_span(
        self,
        span_id: str,
        *,
        category: str,
        started_ns: int,
        parent_span_id: str | None = None,
        observation: Mapping[str, Any] | None = None,
    ) -> None:
        self._ensure_mutable()
        self._require_category(category)
        if self._run_started_ns is None:
            raise LedgerError("run must begin before a span")
        if not isinstance(span_id, str) or not span_id:
            raise LedgerError("span_id must be non-empty text")
        if span_id in self._spans:
            raise LedgerError("span_id is already registered")
        started = _require_time("started_ns", started_ns)
        if started < self._run_started_ns:
            raise LedgerError("span cannot start before the run")
        if parent_span_id is not None:
            if parent_span_id not in self._spans:
                raise LedgerError("parent span is unknown")
            if self._spans[parent_span_id]["ended_ns"] is not None:
                raise LedgerError("parent span is already closed")
        if observation is not None and not isinstance(observation, Mapping):
            raise LedgerError("observation must be an object or None")
        self._spans[span_id] = {
            "span_id": span_id,
            "category": category,
            "parent_span_id": parent_span_id,
            "started_ns": started,
            "ended_ns": None,
            "duration_ns": None,
            "observation": copy.deepcopy(dict(observation)) if observation is not None else None,
        }

    def end_span(
        self,
        span_id: str,
        *,
        ended_ns: int,
        observation: Mapping[str, Any] | None = None,
    ) -> None:
        self._ensure_mutable()
        if span_id not in self._spans:
            raise LedgerError("span_id is unknown")
        row = self._spans[span_id]
        if row["ended_ns"] is not None:
            raise LedgerError("span is already closed")
        ended = _require_time("ended_ns", ended_ns)
        if ended < row["started_ns"]:
            raise LedgerError("span cannot end before it starts")
        if observation is not None and not isinstance(observation, Mapping):
            raise LedgerError("observation must be an object or None")
        row["ended_ns"] = ended
        row["duration_ns"] = ended - row["started_ns"]
        if observation is not None:
            row["observation"] = copy.deepcopy(dict(observation))
        self._coverage[row["category"]] = {
            "reason": "completed_span",
            "observation": row["observation"],
        }

    def close(self, ended_ns: int) -> None:
        self._ensure_mutable()
        if self._run_started_ns is None:
            raise LedgerError("run has not started")
        if self._run_ended_ns is not None:
            raise LedgerError("run is already closed")
        ended = _require_time("ended_ns", ended_ns)
        if ended < self._run_started_ns:
            raise LedgerError("run cannot end before it starts")
        if any(row["ended_ns"] is None for row in self._spans.values()):
            raise LedgerError("all spans must close before the run")
        self._run_ended_ns = ended

    def seal(self) -> dict[str, Any]:
        self._ensure_mutable()
        if self._run_started_ns is None or self._run_ended_ns is None:
            raise LedgerError("run must close before it can seal")
        missing = self._categories - set(self._coverage)
        if missing:
            raise LedgerError(f"registered effect categories are uncovered: {sorted(missing)}")
        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "candidate_sha256": self._candidate_sha256,
            "protocol_sha256": self._protocol_sha256,
            "required_categories": sorted(self._categories),
            "category_coverage": copy.deepcopy(self._coverage),
            "spans": [copy.deepcopy(self._spans[key]) for key in sorted(self._spans)],
            "top_level": {
                "started_ns": self._run_started_ns,
                "ended_ns": self._run_ended_ns,
                "wall_time_ns": self._run_ended_ns - self._run_started_ns,
            },
        }
        receipt["receipt_sha256"] = _digest(receipt)
        verify_receipt(receipt)
        self._sealed = copy.deepcopy(receipt)
        return copy.deepcopy(receipt)


def verify_receipt(receipt: Mapping[str, Any]) -> None:
    """Reject altered seals and structurally inconsistent receipts."""

    if not isinstance(receipt, Mapping) or receipt.get("schema") != SCHEMA:
        raise LedgerError("receipt schema is invalid")
    _require_digest("candidate_sha256", receipt.get("candidate_sha256"))
    _require_digest("protocol_sha256", receipt.get("protocol_sha256"))
    expected = receipt.get("receipt_sha256")
    _require_digest("receipt_sha256", expected)
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if _digest(unsigned) != expected:
        raise LedgerError("receipt_sha256 does not match canonical receipt content")
    categories = receipt.get("required_categories")
    coverage = receipt.get("category_coverage")
    if not isinstance(categories, list) or set(categories) - EFFECT_CATEGORIES:
        raise LedgerError("receipt categories are invalid")
    if not isinstance(coverage, Mapping) or set(categories) != set(coverage):
        raise LedgerError("receipt coverage is incomplete")
    top_level = receipt.get("top_level")
    if not isinstance(top_level, Mapping):
        raise LedgerError("top_level timing is missing")
    started = _require_time("top_level.started_ns", top_level.get("started_ns"))
    ended = _require_time("top_level.ended_ns", top_level.get("ended_ns"))
    if top_level.get("wall_time_ns") != ended - started:
        raise LedgerError("top-level wall time is inconsistent")
