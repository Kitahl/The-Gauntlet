"""Reusable Evaluation & Benchmarking statistical primitives and receipts.

This stdlib implementation is fixed-n. It does not make repeated peeking anytime-valid;
sequential monitoring requires a separately preregistered confidence-sequence/e-process
implementation. Exclusions are item-addressed and contamination is never silently
ignored.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest


@dataclass(frozen=True)
class Exclusion:
    item_id: str
    reason: str
    condition: str | None = None
    contamination: bool = False


@dataclass(frozen=True)
class PairedBinaryObservation:
    item_id: str
    base_correct: bool
    candidate_correct: bool
    contaminated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PairedBinaryPlan:
    plan_id: str
    obligation_id: str
    alpha: float = 0.05
    multiplicity_family: str | None = None
    exclusions: tuple[Exclusion, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be in (0,1)")
        ids = [row.item_id for row in self.exclusions]
        if len(ids) != len(set(ids)):
            raise ValueError("exclusion item IDs must be unique")


def wilson_interval(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("require 0 <= successes <= n and n > 0")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def mcnemar_exact(b: int, c: int) -> float:
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(_binom_pmf(i, n, 0.5) for i in range(k + 1)))


def paired_binary(base: list[bool], candidate: list[bool], *, alpha: float = 0.05) -> dict[str, Any]:
    if len(base) != len(candidate) or not base:
        raise ValueError("paired binary vectors must have equal non-zero length")
    a = sum(1 for x, y in zip(base, candidate) if x and y)
    b = sum(1 for x, y in zip(base, candidate) if x and not y)
    c = sum(1 for x, y in zip(base, candidate) if not x and y)
    d = sum(1 for x, y in zip(base, candidate) if not x and not y)
    n = len(base)
    base_correct = a + b
    cand_correct = a + c
    return {
        "n": n, "both_correct": a, "base_only": b, "candidate_only": c, "both_wrong": d,
        "base_accuracy": base_correct / n, "candidate_accuracy": cand_correct / n,
        "delta": (cand_correct - base_correct) / n,
        "mcnemar_exact_p": mcnemar_exact(b, c),
        "base_wilson": wilson_interval(base_correct, n, alpha),
        "candidate_wilson": wilson_interval(cand_correct, n, alpha),
        "confidence_level": 1 - alpha,
    }


def holm(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    if not all(0 <= p <= 1 for p in pvalues):
        raise ValueError("p-values must be in [0,1]")
    indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
    reject = [False] * len(pvalues)
    for rank, (idx, p) in enumerate(indexed):
        threshold = alpha / (len(pvalues) - rank)
        if p <= threshold:
            reject[idx] = True
        else:
            break
    return reject


def apply_exclusions(plan: PairedBinaryPlan, observations: list[PairedBinaryObservation]) -> tuple[list[PairedBinaryObservation], list[dict[str, Any]]]:
    ids = [row.item_id for row in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("paired observations contain duplicate item IDs")
    exclusion_map = {row.item_id: row for row in plan.exclusions}
    included: list[PairedBinaryObservation] = []
    applied: list[dict[str, Any]] = []
    for row in observations:
        exclusion = exclusion_map.get(row.item_id)
        if row.contaminated and exclusion is None:
            raise ValueError(f"contaminated item {row.item_id} requires an explicit frozen exclusion")
        if exclusion is None:
            included.append(row)
            continue
        applied.append({
            "item_id": row.item_id,
            "reason": exclusion.reason,
            "condition": exclusion.condition,
            "contamination": exclusion.contamination,
        })
    unmatched = sorted(set(exclusion_map) - set(ids))
    if unmatched:
        raise ValueError(f"frozen exclusions reference absent item IDs: {unmatched}")
    return included, applied


def record_paired_observations(root: Path, plan: PairedBinaryPlan, observations: list[PairedBinaryObservation]) -> Receipt:
    store = RuntimeStore(root)
    included, applied = apply_exclusions(plan, observations)
    if not included:
        result = {"n": 0, "status": "NO_INCLUDED_ITEMS", "applied_exclusions": applied}
        verdict = Verdict.UNKNOWN
    else:
        result = paired_binary(
            [row.base_correct for row in included],
            [row.candidate_correct for row in included],
            alpha=plan.alpha,
        )
        result.update({
            "status": "FIXED_N_ANALYSIS_COMPLETE",
            "included_item_ids": [row.item_id for row in included],
            "applied_exclusions": applied,
            "multiplicity_family": plan.multiplicity_family,
        })
        verdict = Verdict.CLEARED
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="time", obligation_id=plan.obligation_id,
        verdict=verdict, action="paired-binary-fixed-n-analysis",
        input_hash=digest({"plan": plan, "observations": observations}),
        output_hash=digest(result),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.MEASURED,
            verifier="time_runtime",
            metadata={
                "analysis": "paired binary fixed-n",
                "n_included": result.get("n", 0),
                "exclusion_count": len(applied),
                "alpha": plan.alpha,
            },
        ),),
        verifier="time_runtime", started_at=utcnow(), finished_at=utcnow(),
        unresolved=("anytime-valid inference is not provided by this fixed-n implementation; preregister a validated sequential method before repeated monitoring",),
        notes="Exact conditional McNemar + Wilson intervals. Exclusions are frozen/item-addressed; contamination cannot be silently included or dropped.",
    )
    store.write_named_state("time", plan.plan_id, result)
    store.write_receipt(receipt)
    return receipt


def record_paired(root: Path, plan: PairedBinaryPlan, base: list[bool], candidate: list[bool]) -> Receipt:
    if plan.exclusions:
        raise ValueError("record_paired cannot apply item-addressed exclusions; use record_paired_observations")
    if len(base) != len(candidate):
        raise ValueError("paired vectors must have equal length")
    observations = [
        PairedBinaryObservation(f"item-{index:05d}", x, y)
        for index, (x, y) in enumerate(zip(base, candidate))
    ]
    return record_paired_observations(root, plan, observations)
