"""Pure v5 residual-diagnostic types and coverage metrics.

Residual diagnostic need is deliberately not a task capability requirement.  A
diagnostic says what evidence is still needed after a candidate exists; a task
capability says what a task may need in general.  Neither type grants authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_claims import Applicability, Decidability, ImmutableBindings, PostSolveObligation
from egrt_coverage import (
    CoverageContribution,
    CoverageRequirement,
    CoverageSummary,
    summarize_coverage,
)
from egrt_verifiers import DEFAULT_REGISTRY

RESIDUAL_DIAGNOSTIC_NEED_NAMESPACE = "foil.v5.residual-diagnostic-need.v1"
DIAGNOSTIC_CAPABILITY_REQUIREMENT_NAMESPACE = "foil.v5.diagnostic-capability-requirement.v1"


class ScanStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class NoAnswerCode(str, Enum):
    A0_DIGEST_MISMATCH = "A0_DIGEST_MISMATCH"
    FORBIDDEN_METADATA = "FORBIDDEN_METADATA"
    MISSING_DIAGNOSTIC_CASE = "MISSING_DIAGNOSTIC_CASE"
    UNDECIDABLE = "UNDECIDABLE"
    APPLICABILITY_UNKNOWN = "APPLICABILITY_UNKNOWN"
    VERIFIER_UNKNOWN = "VERIFIER_UNKNOWN"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    CALIBRATION_STALE = "CALIBRATION_STALE"
    CALIBRATION_MISMATCH = "CALIBRATION_MISMATCH"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_weight(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("weight_units must be int")
    if value <= 0:
        raise ValueError("weight_units must be positive")


@dataclass(frozen=True)
class ResidualDiagnosticNeed:
    need_id: str
    claim_id: str
    description: str
    verifier_id: str
    weight_units: int
    decidability: Decidability
    applicability: Applicability
    bindings: ImmutableBindings
    namespace: str = RESIDUAL_DIAGNOSTIC_NEED_NAMESPACE

    def __post_init__(self) -> None:
        for name in ("need_id", "claim_id", "description", "verifier_id"):
            _require_text(name, getattr(self, name))
        _require_weight(self.weight_units)
        if not isinstance(self.decidability, Decidability):
            raise TypeError("decidability must be Decidability")
        if not isinstance(self.applicability, Applicability):
            raise TypeError("applicability must be Applicability")
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if self.namespace != RESIDUAL_DIAGNOSTIC_NEED_NAMESPACE:
            raise ValueError("residual diagnostic namespace is fixed")
        # A verifier id is an allow-list reference, not caller-provided code.
        DEFAULT_REGISTRY.resolve(self.verifier_id)

    def coverage_requirement(self) -> CoverageRequirement:
        return CoverageRequirement(
            obligation=PostSolveObligation(
                obligation_id=self.need_id,
                claim_id=self.claim_id,
                requirement=self.description,
                weight_units=self.weight_units,
            ),
            decidability=self.decidability,
            applicability=self.applicability,
        )


@dataclass(frozen=True)
class DiagnosticCapabilityRequirement:
    requirement_id: str
    capability: str
    bindings: ImmutableBindings
    namespace: str = DIAGNOSTIC_CAPABILITY_REQUIREMENT_NAMESPACE

    def __post_init__(self) -> None:
        _require_text("requirement_id", self.requirement_id)
        _require_text("capability", self.capability)
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if self.namespace != DIAGNOSTIC_CAPABILITY_REQUIREMENT_NAMESPACE:
            raise ValueError("task capability namespace is fixed")


@dataclass(frozen=True)
class NoAnswer:
    code: NoAnswerCode
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, NoAnswerCode):
            raise TypeError("code must be NoAnswerCode")
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class ResidualCoverageMetrics:
    weighted: CoverageSummary
    decidable_count: int
    covered_count: int
    failed_count: int
    unresolved_count: int
    omitted_count: int
    inapplicable_count: int
    undecidable_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.weighted, CoverageSummary):
            raise TypeError("weighted must be CoverageSummary")
        values = (
            self.decidable_count,
            self.covered_count,
            self.failed_count,
            self.unresolved_count,
            self.omitted_count,
            self.inapplicable_count,
            self.undecidable_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values
        ):
            raise ValueError("unweighted coverage counts must be non-negative integers")
        if (
            self.covered_count + self.failed_count + self.unresolved_count + self.omitted_count
            != self.decidable_count
        ):
            raise ValueError("decidable count must equal classified decidable count")


def summarize_metrics(
    needs: tuple[ResidualDiagnosticNeed, ...],
    contributions: tuple[CoverageContribution, ...] = (),
) -> ResidualCoverageMetrics:
    """Return weighted and one-obligation-one-vote coverage for all material needs."""

    if not isinstance(needs, tuple) or not needs:
        raise ValueError("needs must be a non-empty tuple")
    if not isinstance(contributions, tuple):
        raise TypeError("contributions must be a tuple")
    claim_ids = {need.claim_id for need in needs}
    binding_digests = {need.bindings.binding_digest for need in needs}
    if len(claim_ids) != 1 or len(binding_digests) != 1:
        raise ValueError("needs must share one claim and immutable binding")
    by_need = {need.need_id: need for need in needs}
    if len(by_need) != len(needs):
        raise ValueError("need ids must be unique")
    weighted = summarize_coverage(
        tuple(need.coverage_requirement() for need in needs), contributions
    )
    contributed = {row.obligation_id: row for row in contributions}
    decidable = covered = failed = unresolved = omitted = inapplicable = undecidable = 0
    for need in needs:
        if need.applicability is Applicability.NOT_APPLICABLE:
            inapplicable += 1
            continue
        if need.applicability is Applicability.UNKNOWN or need.decidability in {
            Decidability.UNDECIDABLE,
            Decidability.UNKNOWN,
        }:
            undecidable += 1
            continue
        decidable += 1
        row = contributed.get(need.need_id)
        if row is None:
            omitted += 1
        elif row.outcome.value == "PASS":
            covered += 1
        elif row.outcome.value == "FAIL":
            failed += 1
        else:
            unresolved += 1
    return ResidualCoverageMetrics(
        weighted=weighted,
        decidable_count=decidable,
        covered_count=covered,
        failed_count=failed,
        unresolved_count=unresolved,
        omitted_count=omitted,
        inapplicable_count=inapplicable,
        undecidable_count=undecidable,
    )
