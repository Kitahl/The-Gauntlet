"""FOIL v5 coverage and action-conditioned evaluation metrics.

Declared-universe coverage and adjudicated compiler coverage are deliberately
separate.  A high score over a self-selected declared universe cannot establish
that the compiler found every load-bearing obligation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from foil_v5_metrics import ResidualCoverageMetrics


class UniverseEvidence(str, Enum):
    DECLARED_ONLY = "DECLARED_ONLY"
    ADJUDICATED = "ADJUDICATED"


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class DeclaredCoverageScore:
    evidence: UniverseEvidence
    material_weight: int
    decidable_weight: int
    mechanically_cleared_weight: int
    failed_weight: int
    unresolved_weight: int
    decidable_coverage: float | None
    mechanically_cleared_coverage: float | None
    known_failed_fraction: float | None
    unresolved_residual_fraction: float | None
    material_count: int
    decidable_count: int
    mechanically_cleared_count: int
    decidable_count_coverage: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, UniverseEvidence):
            raise TypeError("evidence must be UniverseEvidence")
        for name in (
            "material_weight",
            "decidable_weight",
            "mechanically_cleared_weight",
            "failed_weight",
            "unresolved_weight",
            "material_count",
            "decidable_count",
            "mechanically_cleared_count",
        ):
            _count(name, getattr(self, name))


def score_declared_coverage(metrics: ResidualCoverageMetrics) -> DeclaredCoverageScore:
    if not isinstance(metrics, ResidualCoverageMetrics):
        raise TypeError("metrics must be ResidualCoverageMetrics")
    weighted = metrics.weighted
    material_weight = weighted.decidable_mass + weighted.undecidable_mass
    unresolved_weight = weighted.unresolved_mass + weighted.omitted_mass + weighted.undecidable_mass
    material_count = metrics.decidable_count + metrics.undecidable_count
    return DeclaredCoverageScore(
        evidence=UniverseEvidence.DECLARED_ONLY,
        material_weight=material_weight,
        decidable_weight=weighted.decidable_mass,
        mechanically_cleared_weight=weighted.covered_mass,
        failed_weight=weighted.failed_mass,
        unresolved_weight=unresolved_weight,
        decidable_coverage=_ratio(weighted.decidable_mass, material_weight),
        mechanically_cleared_coverage=_ratio(weighted.covered_mass, material_weight),
        known_failed_fraction=_ratio(weighted.failed_mass, material_weight),
        unresolved_residual_fraction=_ratio(unresolved_weight, material_weight),
        material_count=material_count,
        decidable_count=metrics.decidable_count,
        mechanically_cleared_count=metrics.covered_count,
        decidable_count_coverage=_ratio(metrics.decidable_count, material_count),
    )


@dataclass(frozen=True)
class AdjudicatedObligation:
    obligation_id: str
    weight_units: int
    extracted: bool
    correctly_extracted: bool
    deterministically_decidable: bool

    def __post_init__(self) -> None:
        if not isinstance(self.obligation_id, str) or not self.obligation_id.strip():
            raise ValueError("obligation_id must be non-empty text")
        _count("weight_units", self.weight_units)
        if self.weight_units == 0:
            raise ValueError("weight_units must be positive")
        for name in ("extracted", "correctly_extracted", "deterministically_decidable"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.correctly_extracted and not self.extracted:
            raise ValueError("a correctly extracted obligation must be extracted")
        if self.deterministically_decidable and not self.correctly_extracted:
            raise ValueError("decidability credit requires a correct extraction")


@dataclass(frozen=True)
class CompilerScore:
    evidence: UniverseEvidence
    obligation_count: int
    material_weight: int
    extracted_weight: int
    correctly_extracted_weight: int
    decidable_weight: int
    compiler_coverage: float
    compiler_precision: float | None
    weighted_decidable_coverage: float


def score_adjudicated_compiler(rows: tuple[AdjudicatedObligation, ...]) -> CompilerScore:
    if not isinstance(rows, tuple) or not rows:
        raise ValueError("rows must be a non-empty tuple")
    ids = {row.obligation_id for row in rows}
    if len(ids) != len(rows):
        raise ValueError("adjudicated obligation ids must be unique")
    material = sum(row.weight_units for row in rows)
    extracted = sum(row.weight_units for row in rows if row.extracted)
    correct = sum(row.weight_units for row in rows if row.correctly_extracted)
    decidable = sum(row.weight_units for row in rows if row.deterministically_decidable)
    return CompilerScore(
        evidence=UniverseEvidence.ADJUDICATED,
        obligation_count=len(rows),
        material_weight=material,
        extracted_weight=extracted,
        correctly_extracted_weight=correct,
        decidable_weight=decidable,
        compiler_coverage=correct / material,
        compiler_precision=_ratio(correct, extracted),
        weighted_decidable_coverage=decidable / material,
    )


@dataclass(frozen=True)
class ActionOutcome:
    base_correct: bool
    flagged: bool
    action_authorized: bool
    final_correct: bool

    def __post_init__(self) -> None:
        for name in ("base_correct", "flagged", "action_authorized", "final_correct"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True)
class ActionConditionedScore:
    wrong_count: int
    correct_count: int
    flagged_wrong: int
    flagged_correct: int
    authorized_wrong: int
    authorized_correct: int
    repaired_wrong_to_correct: int
    damaged_correct_to_wrong: int
    r_flag: float | None
    alpha_flag: float | None
    r_act: float | None
    alpha_act: float | None
    u_act: float | None
    d_act: float | None


def score_action_conditioned(rows: tuple[ActionOutcome, ...]) -> ActionConditionedScore:
    if not isinstance(rows, tuple):
        raise TypeError("rows must be a tuple")
    wrong = sum(not row.base_correct for row in rows)
    correct = sum(row.base_correct for row in rows)
    flagged_wrong = sum((not row.base_correct) and row.flagged for row in rows)
    flagged_correct = sum(row.base_correct and row.flagged for row in rows)
    authorized_wrong = sum((not row.base_correct) and row.action_authorized for row in rows)
    authorized_correct = sum(row.base_correct and row.action_authorized for row in rows)
    rescued = sum(
        (not row.base_correct) and row.action_authorized and row.final_correct for row in rows
    )
    damaged = sum(
        row.base_correct and row.action_authorized and (not row.final_correct) for row in rows
    )
    return ActionConditionedScore(
        wrong_count=wrong,
        correct_count=correct,
        flagged_wrong=flagged_wrong,
        flagged_correct=flagged_correct,
        authorized_wrong=authorized_wrong,
        authorized_correct=authorized_correct,
        repaired_wrong_to_correct=rescued,
        damaged_correct_to_wrong=damaged,
        r_flag=_ratio(flagged_wrong, wrong),
        alpha_flag=_ratio(flagged_correct, correct),
        r_act=_ratio(authorized_wrong, wrong),
        alpha_act=_ratio(authorized_correct, correct),
        u_act=_ratio(rescued, authorized_wrong),
        d_act=_ratio(damaged, authorized_correct),
    )
