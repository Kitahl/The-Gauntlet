"""Pure deterministic scanner for post-solve residual diagnostic needs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from egrt_claims import Applicability, Decidability, ImmutableBindings
from egrt_coverage import ContributionOutcome, CoverageContribution
from egrt_types import digest
from egrt_verifiers import DEFAULT_REGISTRY, VerificationStatus, VerifierResult
from foil_v5_metrics import (
    NoAnswer,
    NoAnswerCode,
    ResidualCoverageMetrics,
    ResidualDiagnosticNeed,
    ScanStatus,
    summarize_metrics,
)

FORBIDDEN_METADATA_NAMES = frozenset(
    {
        "answer",
        "correct",
        "correct_answer",
        "correct_index",
        "gold",
        "gold_label",
        "key",
        "label",
        "target",
    }
)


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a SHA-256 digest")


def forbidden_metadata_name(name: object) -> bool:
    if not isinstance(name, str):
        return True
    normalized = name.strip().lower()
    return normalized in FORBIDDEN_METADATA_NAMES or "gold" in normalized or "answer" in normalized


def contains_forbidden_metadata(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            forbidden_metadata_name(key) or contains_forbidden_metadata(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return any(contains_forbidden_metadata(item) for item in value)
    return False


@dataclass(frozen=True)
class DiagnosticCase:
    need_id: str
    verifier_input: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_text("need_id", self.need_id)
        if not isinstance(self.verifier_input, Mapping):
            raise TypeError("verifier_input must be a mapping")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")


@dataclass(frozen=True)
class ResidualScanPlan:
    claim_id: str
    a0_digest: str
    bindings: ImmutableBindings
    needs: tuple[ResidualDiagnosticNeed, ...]

    def __post_init__(self) -> None:
        _require_text("claim_id", self.claim_id)
        _require_digest("a0_digest", self.a0_digest)
        if not isinstance(self.bindings, ImmutableBindings):
            raise TypeError("bindings must be ImmutableBindings")
        if self.a0_digest != self.bindings.a0_digest:
            raise ValueError("plan must preserve the exact bound A0 digest")
        if not isinstance(self.needs, tuple) or not self.needs:
            raise ValueError("needs must be a non-empty tuple")
        for need in self.needs:
            if not isinstance(need, ResidualDiagnosticNeed):
                raise TypeError("needs must contain ResidualDiagnosticNeed")
            if need.claim_id != self.claim_id or need.bindings != self.bindings:
                raise ValueError("needs must bind to this plan's claim and immutable context")
            DEFAULT_REGISTRY.resolve(need.verifier_id)


@dataclass(frozen=True)
class DiagnosticResult:
    need_id: str
    status: ScanStatus
    reason: str
    verifier: VerifierResult | None = None

    def __post_init__(self) -> None:
        _require_text("need_id", self.need_id)
        if not isinstance(self.status, ScanStatus):
            raise TypeError("status must be ScanStatus")
        _require_text("reason", self.reason)
        if self.verifier is not None and not isinstance(self.verifier, VerifierResult):
            raise TypeError("verifier must be VerifierResult or None")


@dataclass(frozen=True)
class ResidualScanReport:
    status: ScanStatus
    reason: str
    a0_digest: str
    input_digest: str
    metrics: ResidualCoverageMetrics
    results: tuple[DiagnosticResult, ...]
    no_answer: NoAnswer | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ScanStatus):
            raise TypeError("status must be ScanStatus")
        _require_text("reason", self.reason)
        _require_digest("a0_digest", self.a0_digest)
        _require_digest("input_digest", self.input_digest)
        if not isinstance(self.metrics, ResidualCoverageMetrics):
            raise TypeError("metrics must be ResidualCoverageMetrics")
        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple")
        if self.no_answer is not None and not isinstance(self.no_answer, NoAnswer):
            raise TypeError("no_answer must be NoAnswer or None")


def _empty_metrics(plan: ResidualScanPlan) -> ResidualCoverageMetrics:
    return summarize_metrics(plan.needs)


def _report(
    plan: ResidualScanPlan,
    status: ScanStatus,
    reason: str,
    *,
    cases: tuple[DiagnosticCase, ...],
    metrics: ResidualCoverageMetrics | None = None,
    results: tuple[DiagnosticResult, ...] = (),
    no_answer: NoAnswer | None = None,
) -> ResidualScanReport:
    return ResidualScanReport(
        status=status,
        reason=reason,
        a0_digest=plan.a0_digest,
        input_digest=digest({"a0_digest": plan.a0_digest, "cases": cases}),
        metrics=metrics or _empty_metrics(plan),
        results=results,
        no_answer=no_answer,
    )


def scan(
    plan: ResidualScanPlan, observed_a0_digest: str, cases: tuple[DiagnosticCase, ...]
) -> ResidualScanReport:
    """Run only closed, in-process verifiers and report all missing material mass."""

    if not isinstance(plan, ResidualScanPlan):
        raise TypeError("plan must be ResidualScanPlan")
    _require_digest("observed_a0_digest", observed_a0_digest)
    if not isinstance(cases, tuple):
        raise TypeError("cases must be a tuple")
    if observed_a0_digest != plan.a0_digest:
        return _report(
            plan,
            ScanStatus.UNKNOWN,
            "observed A0 digest differs from immutable plan binding",
            cases=cases,
            no_answer=NoAnswer(
                NoAnswerCode.A0_DIGEST_MISMATCH, "exact A0 digest preservation failed"
            ),
        )
    if any(contains_forbidden_metadata(case.metadata) for case in cases):
        return _report(
            plan,
            ScanStatus.UNKNOWN,
            "forbidden answer-bearing metadata was rejected",
            cases=cases,
            no_answer=NoAnswer(
                NoAnswerCode.FORBIDDEN_METADATA,
                "metadata contains a forbidden answer/gold label name",
            ),
        )
    by_need: dict[str, DiagnosticCase] = {}
    for case in cases:
        if not isinstance(case, DiagnosticCase):
            raise TypeError("cases must contain DiagnosticCase")
        if case.need_id in by_need:
            raise ValueError("one diagnostic case is permitted per need")
        by_need[case.need_id] = case
    expected = {need.need_id for need in plan.needs}
    if any(need_id not in expected for need_id in by_need):
        return _report(
            plan,
            ScanStatus.UNKNOWN,
            "diagnostic case references a need outside the immutable plan",
            cases=cases,
            no_answer=NoAnswer(NoAnswerCode.MISSING_DIAGNOSTIC_CASE, "case set is not plan-scoped"),
        )

    results: list[DiagnosticResult] = []
    contributions: list[CoverageContribution] = []
    no_answers: list[NoAnswer] = []
    for need in plan.needs:
        if need.applicability is Applicability.NOT_APPLICABLE:
            results.append(
                DiagnosticResult(
                    need.need_id, ScanStatus.NOT_APPLICABLE, "diagnostic need is not applicable"
                )
            )
            continue
        if need.applicability is Applicability.UNKNOWN:
            results.append(
                DiagnosticResult(
                    need.need_id, ScanStatus.UNKNOWN, "diagnostic applicability is unknown"
                )
            )
            no_answers.append(
                NoAnswer(NoAnswerCode.APPLICABILITY_UNKNOWN, "applicability is unknown")
            )
            continue
        if need.decidability is not Decidability.DETERMINISTIC:
            results.append(
                DiagnosticResult(
                    need.need_id, ScanStatus.UNKNOWN, "diagnostic need is not decidable"
                )
            )
            no_answers.append(
                NoAnswer(NoAnswerCode.UNDECIDABLE, "no deterministic decision is available")
            )
            continue
        case = by_need.get(need.need_id)
        if case is None:
            no_answers.append(
                NoAnswer(NoAnswerCode.MISSING_DIAGNOSTIC_CASE, "material diagnostic case is absent")
            )
            continue
        verifier = DEFAULT_REGISTRY.run(need.verifier_id, case.verifier_input)
        if verifier.status is VerificationStatus.PASS:
            status, outcome, reason = ScanStatus.PASS, ContributionOutcome.PASS, verifier.reason
        elif verifier.status is VerificationStatus.FAIL:
            status, outcome, reason = ScanStatus.FAIL, ContributionOutcome.FAIL, verifier.reason
        else:
            status, outcome, reason = (
                ScanStatus.UNKNOWN,
                ContributionOutcome.UNRESOLVED,
                verifier.reason,
            )
            no_answers.append(
                NoAnswer(NoAnswerCode.VERIFIER_UNKNOWN, "closed verifier returned unknown")
            )
        results.append(DiagnosticResult(need.need_id, status, reason, verifier))
        contributions.append(
            CoverageContribution(need.need_id, verifier.evidence_digest, outcome, verifier.reason)
        )

    metrics = summarize_metrics(plan.needs, tuple(contributions))
    if metrics.failed_count:
        return _report(
            plan,
            ScanStatus.FAIL,
            "one or more material diagnostics failed",
            cases=cases,
            metrics=metrics,
            results=tuple(results),
        )
    if metrics.inapplicable_count == len(plan.needs):
        return _report(
            plan,
            ScanStatus.NOT_APPLICABLE,
            "all material diagnostics are not applicable",
            cases=cases,
            metrics=metrics,
            results=tuple(results),
        )
    if no_answers or metrics.unresolved_count or metrics.omitted_count or metrics.undecidable_count:
        no_answer = (
            no_answers[0]
            if no_answers
            else NoAnswer(NoAnswerCode.INCOMPLETE_COVERAGE, "decidable coverage is incomplete")
        )
        return _report(
            plan,
            ScanStatus.UNKNOWN,
            "material diagnostic coverage is unresolved",
            cases=cases,
            metrics=metrics,
            results=tuple(results),
            no_answer=no_answer,
        )
    return _report(
        plan,
        ScanStatus.PASS,
        "all material decidable diagnostics passed",
        cases=cases,
        metrics=metrics,
        results=tuple(results),
    )
