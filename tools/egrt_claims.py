"""Pure typed claims for the post-solve EGR namespace.

This module deliberately contains neither tools nor policy execution.  A claim
compiler records the immutable context it was compiled against and produces one
explicit outcome; it never turns an undecidable, unknown, or inapplicable claim
into a green result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from egrt_types import digest, text_digest

POST_SOLVE_CLAIM_NAMESPACE = "egr.post-solve.claim.v1"
POST_SOLVE_OBLIGATION_NAMESPACE = "egr.post-solve.obligation.v1"


class ClaimOutcome(str, Enum):
    COMPILED = "COMPILED"
    UNDECIDABLE = "UNDECIDABLE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Decidability(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    EMPIRICAL = "EMPIRICAL"
    SEMANTIC = "SEMANTIC"
    UNDECIDABLE = "UNDECIDABLE"
    UNKNOWN = "UNKNOWN"


class Applicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ClaimKind(str, Enum):
    EXACT_ARITHMETIC = "EXACT_ARITHMETIC"
    JSON = "JSON"
    DIGEST = "DIGEST"
    EXACT_MATCH = "EXACT_MATCH"
    NUMERIC_TOLERANCE = "NUMERIC_TOLERANCE"
    OTHER = "OTHER"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a SHA-256 digest")


def _require_weight(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("weight_units must be int")
    if value <= 0:
        raise ValueError("weight_units must be positive")


@dataclass(frozen=True)
class ImmutableBindings:
    """The immutable A0/task/spec/compiler/config context for a compilation."""

    a0_digest: str
    task_digest: str
    spec_digest: str
    compiler_digest: str
    config_digest: str

    def __post_init__(self) -> None:
        for name in (
            "a0_digest",
            "task_digest",
            "spec_digest",
            "compiler_digest",
            "config_digest",
        ):
            _require_digest(name, getattr(self, name))

    @property
    def binding_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class PostSolveClaim:
    """A compiled claim; statement content is represented by a one-way digest."""

    claim_id: str
    statement_digest: str
    kind: ClaimKind
    decidability: Decidability
    applicability: Applicability
    bindings: ImmutableBindings
    required_verifiers: tuple[str, ...]
    namespace: str = POST_SOLVE_CLAIM_NAMESPACE

    def __post_init__(self) -> None:
        _require_text("claim_id", self.claim_id)
        _require_digest("statement_digest", self.statement_digest)
        if not isinstance(self.kind, ClaimKind):
            raise TypeError("kind must be ClaimKind")
        if not isinstance(self.decidability, Decidability):
            raise TypeError("decidability must be Decidability")
        if not isinstance(self.applicability, Applicability):
            raise TypeError("applicability must be Applicability")
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if self.namespace != POST_SOLVE_CLAIM_NAMESPACE:
            raise ValueError("claim namespace is fixed")
        if self.applicability is not Applicability.APPLICABLE:
            raise ValueError("compiled claims must be applicable")
        if self.decidability in {Decidability.UNDECIDABLE, Decidability.UNKNOWN}:
            raise ValueError("compiled claims must have a decidable verification mode")
        if not isinstance(self.required_verifiers, tuple):
            raise TypeError("required_verifiers must be a tuple")
        for verifier in self.required_verifiers:
            _require_text("required_verifier", verifier)


@dataclass(frozen=True)
class PostSolveObligation:
    """A non-overlapping claim requirement with an integer coverage weight."""

    obligation_id: str
    claim_id: str
    requirement: str
    weight_units: int
    namespace: str = POST_SOLVE_OBLIGATION_NAMESPACE

    def __post_init__(self) -> None:
        for name in ("obligation_id", "claim_id", "requirement"):
            _require_text(name, getattr(self, name))
        _require_weight(self.weight_units)
        if self.namespace != POST_SOLVE_OBLIGATION_NAMESPACE:
            raise ValueError("obligation namespace is fixed")


@dataclass(frozen=True)
class ClaimCompilation:
    outcome: ClaimOutcome
    reason: str
    claim: PostSolveClaim | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ClaimOutcome):
            raise TypeError("outcome must be ClaimOutcome")
        _require_text("reason", self.reason)
        if self.outcome is ClaimOutcome.COMPILED:
            if not isinstance(self.claim, PostSolveClaim):
                raise ValueError("COMPILED requires a PostSolveClaim")
        elif self.claim is not None:
            raise ValueError("non-compiled outcomes cannot carry a claim")


def classify_outcome(decidability: Decidability, applicability: Applicability) -> ClaimOutcome:
    """Classify orthogonal axes without interpreting either as a verification pass."""

    if not isinstance(decidability, Decidability):
        raise TypeError("decidability must be Decidability")
    if not isinstance(applicability, Applicability):
        raise TypeError("applicability must be Applicability")
    if applicability is Applicability.NOT_APPLICABLE:
        return ClaimOutcome.NOT_APPLICABLE
    if applicability is Applicability.UNKNOWN or decidability is Decidability.UNKNOWN:
        return ClaimOutcome.UNKNOWN
    if decidability is Decidability.UNDECIDABLE:
        return ClaimOutcome.UNDECIDABLE
    return ClaimOutcome.COMPILED


def compile_claim(
    *,
    statement: str,
    kind: ClaimKind,
    decidability: Decidability,
    applicability: Applicability,
    bindings: ImmutableBindings,
    required_verifiers: tuple[str, ...] = (),
    reason: str,
) -> ClaimCompilation:
    """Compile a claim into the fixed post-solve namespace.

    The compiler is intentionally declarative: callers provide classifications
    and an explicit reason.  It cannot silently infer an applicability or
    decidability result from untyped prose.
    """

    _require_text("statement", statement)
    _require_text("reason", reason)
    if not isinstance(kind, ClaimKind):
        raise TypeError("kind must be ClaimKind")
    if not isinstance(bindings, ImmutableBindings):
        raise TypeError("bindings must be ImmutableBindings")
    if not isinstance(required_verifiers, tuple):
        raise TypeError("required_verifiers must be a tuple")
    outcome = classify_outcome(decidability, applicability)
    if outcome is not ClaimOutcome.COMPILED:
        return ClaimCompilation(outcome=outcome, reason=reason)
    statement_digest = text_digest(statement)
    claim_id = (
        "claim-"
        + digest(
            {
                "namespace": POST_SOLVE_CLAIM_NAMESPACE,
                "statement_digest": statement_digest,
                "kind": kind,
                "bindings": bindings,
                "required_verifiers": required_verifiers,
            }
        )[:24]
    )
    return ClaimCompilation(
        outcome=ClaimOutcome.COMPILED,
        reason=reason,
        claim=PostSolveClaim(
            claim_id=claim_id,
            statement_digest=statement_digest,
            kind=kind,
            decidability=decidability,
            applicability=applicability,
            bindings=bindings,
            required_verifiers=required_verifiers,
        ),
    )
