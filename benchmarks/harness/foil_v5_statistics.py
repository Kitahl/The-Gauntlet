"""Base-item-clustered descriptive statistics for offline FOIL v5 Gate-1 runs.

Mutants are diagnostic variants, not independent observations.  Every reported
binary rate therefore collapses rows to one declared base item before computing
Wilson intervals.  These functions are descriptive and select no threshold.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1:
        raise ValueError("confidence must be a number strictly between 0 and 1")
    return float(value)


@dataclass(frozen=True)
class WilsonInterval:
    successes: int
    total: int
    confidence: float
    estimate: float | None
    lower: float | None
    upper: float | None


def wilson_interval(successes: int, total: int, *, confidence: float = 0.95) -> WilsonInterval:
    """Return a two-sided Wilson interval; no observations remains undefined."""

    successes, total, confidence = _count("successes", successes), _count("total", total), _confidence(confidence)
    if successes > total:
        raise ValueError("successes cannot exceed total")
    if total == 0:
        return WilsonInterval(successes, total, confidence, None, None, None)
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    radius = z * ((p * (1 - p) / total + z**2 / (4 * total**2)) ** 0.5) / denominator
    return WilsonInterval(successes, total, confidence, p, max(0.0, center - radius), min(1.0, center + radius))


@dataclass(frozen=True)
class ClusterObservation:
    """One scanner row, grouped by ``base_item_id`` before any rate is calculated."""

    item_id: str
    base_item_id: str
    domain: str
    base_correct: bool
    flagged: bool
    status: str
    no_answer_code: str | None

    def __post_init__(self) -> None:
        for name in ("item_id", "base_item_id", "domain", "status"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be non-empty text")
        for name in ("base_correct", "flagged"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.no_answer_code is not None and (
            not isinstance(self.no_answer_code, str) or not self.no_answer_code
        ):
            raise ValueError("no_answer_code must be non-empty text or None")


@dataclass(frozen=True)
class ClusteredOutcome:
    base_item_id: str
    domain: str
    base_correct: bool
    flagged: bool
    row_count: int
    status_counts: tuple[tuple[str, int], ...]
    no_answer_counts: tuple[tuple[str, int], ...]


def cluster_base_items(rows: Iterable[ClusterObservation]) -> tuple[ClusteredOutcome, ...]:
    """Collapse variants conservatively: any flag is a flag for its base item."""

    grouped: dict[str, list[ClusterObservation]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, ClusterObservation):
            raise TypeError("rows must contain ClusterObservation")
        grouped[row.base_item_id].append(row)
    outcome: list[ClusteredOutcome] = []
    for base_item_id in sorted(grouped):
        cluster = grouped[base_item_id]
        domains, correctness = {row.domain for row in cluster}, {row.base_correct for row in cluster}
        if len(domains) != 1 or len(correctness) != 1:
            raise ValueError("all variants of a base item must share domain and base correctness")
        status_counts: dict[str, int] = defaultdict(int)
        no_answer_counts: dict[str, int] = defaultdict(int)
        for row in cluster:
            status_counts[row.status] += 1
            if row.no_answer_code is not None:
                no_answer_counts[row.no_answer_code] += 1
        outcome.append(
            ClusteredOutcome(
                base_item_id=base_item_id,
                domain=cluster[0].domain,
                base_correct=cluster[0].base_correct,
                flagged=any(row.flagged for row in cluster),
                row_count=len(cluster),
                status_counts=tuple(sorted(status_counts.items())),
                no_answer_counts=tuple(sorted(no_answer_counts.items())),
            )
        )
    return tuple(outcome)


@dataclass(frozen=True)
class ResidualRates:
    clusters: int
    raw_rows: int
    residual_recall: WilsonInterval
    false_positive_rate: WilsonInterval
    positive_predictive_value: WilsonInterval
    status_counts: tuple[tuple[str, int], ...]
    no_answer_counts: tuple[tuple[str, int], ...]


def residual_rates(rows: Iterable[ClusterObservation], *, confidence: float = 0.95) -> ResidualRates:
    """Report recall/FPR/PPV over clustered base answers and all raw statuses."""

    original = tuple(rows)
    clustered = cluster_base_items(original)
    wrong = [row for row in clustered if not row.base_correct]
    correct = [row for row in clustered if row.base_correct]
    flagged = [row for row in clustered if row.flagged]
    status_counts: dict[str, int] = defaultdict(int)
    no_answer_counts: dict[str, int] = defaultdict(int)
    for row in original:
        status_counts[row.status] += 1
        if row.no_answer_code is not None:
            no_answer_counts[row.no_answer_code] += 1
    return ResidualRates(
        clusters=len(clustered),
        raw_rows=len(original),
        residual_recall=wilson_interval(sum(row.flagged for row in wrong), len(wrong), confidence=confidence),
        false_positive_rate=wilson_interval(sum(row.flagged for row in correct), len(correct), confidence=confidence),
        positive_predictive_value=wilson_interval(
            sum(not row.base_correct for row in flagged), len(flagged), confidence=confidence
        ),
        status_counts=tuple(sorted(status_counts.items())),
        no_answer_counts=tuple(sorted(no_answer_counts.items())),
    )
