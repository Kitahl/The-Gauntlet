"""Integer, claim-scoped coverage accounting with a no-double-counting rule."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_claims import Applicability, Decidability, PostSolveObligation
from egrt_types import digest


class ContributionOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a SHA-256 digest")


@dataclass(frozen=True)
class CoverageRequirement:
    obligation: PostSolveObligation
    decidability: Decidability
    applicability: Applicability

    def __post_init__(self) -> None:
        if not isinstance(self.obligation, PostSolveObligation):
            raise TypeError("obligation must be PostSolveObligation")
        if not isinstance(self.decidability, Decidability):
            raise TypeError("decidability must be Decidability")
        if not isinstance(self.applicability, Applicability):
            raise TypeError("applicability must be Applicability")

    @property
    def is_decidable(self) -> bool:
        return (
            self.applicability is Applicability.APPLICABLE
            and self.decidability is Decidability.DETERMINISTIC
        )


@dataclass(frozen=True)
class CoverageContribution:
    obligation_id: str
    evidence_digest: str
    outcome: ContributionOutcome
    reason: str

    def __post_init__(self) -> None:
        _require_text("obligation_id", self.obligation_id)
        _require_digest("evidence_digest", self.evidence_digest)
        if not isinstance(self.outcome, ContributionOutcome):
            raise TypeError("outcome must be ContributionOutcome")
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class CoverageSummary:
    claim_id: str
    decidable_mass: int
    covered_mass: int
    failed_mass: int
    unresolved_mass: int
    omitted_mass: int
    inapplicable_mass: int
    undecidable_mass: int
    coverage_digest: str

    def __post_init__(self) -> None:
        _require_text("claim_id", self.claim_id)
        for name in (
            "decidable_mass",
            "covered_mass",
            "failed_mass",
            "unresolved_mass",
            "omitted_mass",
            "inapplicable_mass",
            "undecidable_mass",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _require_digest("coverage_digest", self.coverage_digest)
        if self.covered_mass + self.failed_mass + self.unresolved_mass + self.omitted_mass != self.decidable_mass:
            raise ValueError("decidable mass must equal the classified decidable mass")

    @property
    def complete(self) -> bool:
        return (
            self.decidable_mass > 0
            and self.covered_mass == self.decidable_mass
            and self.failed_mass == self.unresolved_mass == self.omitted_mass == 0
        )


def summarize_coverage(
    requirements: tuple[CoverageRequirement, ...],
    contributions: tuple[CoverageContribution, ...] = (),
) -> CoverageSummary:
    """Account for every requirement exactly once.

    An evidence digest may support one obligation only.  The prohibition is
    deliberate: otherwise one green check can be copied across requirements to
    manufacture coverage.
    """

    if not isinstance(requirements, tuple) or not requirements:
        raise ValueError("requirements must be a non-empty tuple")
    if not isinstance(contributions, tuple):
        raise TypeError("contributions must be a tuple")
    claim_ids = {requirement.obligation.claim_id for requirement in requirements}
    if len(claim_ids) != 1:
        raise ValueError("requirements must belong to exactly one claim")
    by_id = {requirement.obligation.obligation_id: requirement for requirement in requirements}
    if len(by_id) != len(requirements):
        raise ValueError("obligation ids must be unique")
    by_obligation: dict[str, CoverageContribution] = {}
    seen_evidence: set[str] = set()
    for contribution in contributions:
        if not isinstance(contribution, CoverageContribution):
            raise TypeError("contributions must contain CoverageContribution")
        if contribution.obligation_id not in by_id:
            raise ValueError("contribution references an unknown obligation")
        if contribution.obligation_id in by_obligation:
            raise ValueError("an obligation can receive one contribution only")
        if contribution.evidence_digest in seen_evidence:
            raise ValueError("evidence cannot be double-counted across obligations")
        by_obligation[contribution.obligation_id] = contribution
        seen_evidence.add(contribution.evidence_digest)

    covered = failed = unresolved = omitted = inapplicable = undecidable = decidable = 0
    for requirement in requirements:
        weight = requirement.obligation.weight_units
        if requirement.applicability is Applicability.NOT_APPLICABLE:
            inapplicable += weight
            continue
        if not requirement.is_decidable:
            undecidable += weight
            continue
        decidable += weight
        contribution = by_obligation.get(requirement.obligation.obligation_id)
        if contribution is None:
            omitted += weight
        elif contribution.outcome is ContributionOutcome.PASS:
            covered += weight
        elif contribution.outcome is ContributionOutcome.FAIL:
            failed += weight
        else:
            unresolved += weight
    payload = {"requirements": requirements, "contributions": contributions}
    return CoverageSummary(
        claim_id=next(iter(claim_ids)),
        decidable_mass=decidable,
        covered_mass=covered,
        failed_mass=failed,
        unresolved_mass=unresolved,
        omitted_mass=omitted,
        inapplicable_mass=inapplicable,
        undecidable_mass=undecidable,
        coverage_digest=digest(payload),
    )
