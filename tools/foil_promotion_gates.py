"""Deterministic evaluator for FOIL's external promotion gates.

The module does not collect data or call models.  It converts a preregistered,
content-addressed set of binomial gate observations into a GateReceipt.  Missing
partitions, domains, metrics, costs, negative controls, or A0 equivalence remain
UNKNOWN and cannot promote a candidate.  Development evidence is reportable but
never promotion eligible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from egrt_types import digest
from foil_candidate_state import (
    CandidateBinding,
    Gate,
    GateReceipt,
    GateStatus,
)
from foil_formalization_admission import PPM, clopper_pearson_lower_ppm


class EvidencePartition(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    LOCK = "LOCK"
    PROSPECTIVE = "PROSPECTIVE"


class MetricDirection(str, Enum):
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"


class GateEvaluationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _digest(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _ppm(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= PPM:
        raise ValueError(f"{name} must be an integer in [0, 1000000]")
    return value


def clopper_pearson_upper_ppm(
    successes: int,
    total: int,
    confidence_ppm: int,
) -> int:
    """Return a conservative exact one-sided binomial upper bound in ppm."""

    _count("successes", successes)
    _count("total", total)
    _ppm("confidence_ppm", confidence_ppm)
    if total <= 0 or successes > total:
        raise ValueError("require 0 <= successes <= total and total > 0")
    return PPM - clopper_pearson_lower_ppm(
        total - successes,
        total,
        confidence_ppm,
    )


@dataclass(frozen=True)
class MetricRule:
    metric_id: str
    direction: MetricDirection
    threshold_ppm: int
    confidence_ppm: int
    minimum_n: int

    def __post_init__(self) -> None:
        _text("metric_id", self.metric_id)
        object.__setattr__(self, "direction", MetricDirection(self.direction))
        _ppm("threshold_ppm", self.threshold_ppm)
        _ppm("confidence_ppm", self.confidence_ppm)
        if not 500_000 <= self.confidence_ppm < PPM:
            raise ValueError("confidence_ppm must be in [500000, 1000000)")
        if self.minimum_n <= 0:
            raise ValueError("minimum_n must be positive")


@dataclass(frozen=True)
class GateEvaluationPlan:
    plan_id: str
    gate: Gate
    candidate_binding_digest: str
    required_partitions: tuple[EvidencePartition, ...]
    required_domains: tuple[str, ...]
    metric_rules: tuple[MetricRule, ...]
    protocol_sha256: str

    def __post_init__(self) -> None:
        _text("plan_id", self.plan_id)
        object.__setattr__(self, "gate", Gate(self.gate))
        _digest("candidate_binding_digest", self.candidate_binding_digest)
        if not isinstance(self.required_partitions, tuple) or not self.required_partitions:
            raise ValueError("required_partitions must be a non-empty tuple")
        partitions = tuple(EvidencePartition(item) for item in self.required_partitions)
        object.__setattr__(self, "required_partitions", partitions)
        if len(set(partitions)) != len(partitions):
            raise ValueError("required_partitions must be unique")
        if EvidencePartition.DEVELOPMENT in partitions and len(partitions) > 1:
            raise ValueError("development cannot be pooled with promotion partitions")
        if not isinstance(self.required_domains, tuple) or not self.required_domains:
            raise ValueError("required_domains must be a non-empty tuple")
        for domain in self.required_domains:
            _text("required_domain", domain)
        if len(set(self.required_domains)) != len(self.required_domains):
            raise ValueError("required_domains must be unique")
        if not isinstance(self.metric_rules, tuple) or not self.metric_rules:
            raise ValueError("metric_rules must be a non-empty tuple")
        if any(not isinstance(item, MetricRule) for item in self.metric_rules):
            raise TypeError("metric_rules must contain MetricRule")
        if len({item.metric_id for item in self.metric_rules}) != len(self.metric_rules):
            raise ValueError("metric rule ids must be unique")
        _digest("protocol_sha256", self.protocol_sha256)

    @property
    def plan_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class GateMetricObservation:
    partition: EvidencePartition
    domain: str
    metric_id: str
    successes: int
    total: int
    source_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "partition", EvidencePartition(self.partition))
        _text("domain", self.domain)
        _text("metric_id", self.metric_id)
        _count("successes", self.successes)
        _count("total", self.total)
        if self.total <= 0 or self.successes > self.total:
            raise ValueError("require 0 <= successes <= total and total > 0")
        _digest("source_sha256", self.source_sha256)


@dataclass(frozen=True)
class GateEvidence:
    observations: tuple[GateMetricObservation, ...]
    cost_ledger_sha256: str
    source_bundle_sha256: str
    forbidden_calls: int
    cost_complete: bool
    exact_a0_preserved: bool
    negative_controls_passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.observations, tuple) or any(
            not isinstance(item, GateMetricObservation) for item in self.observations
        ):
            raise TypeError("observations must contain GateMetricObservation")
        _digest("cost_ledger_sha256", self.cost_ledger_sha256)
        _digest("source_bundle_sha256", self.source_bundle_sha256)
        _count("forbidden_calls", self.forbidden_calls)
        for name in (
            "cost_complete",
            "exact_a0_preserved",
            "negative_controls_passed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True)
class MetricEvaluation:
    partition: EvidencePartition
    domain: str
    metric_id: str
    successes: int
    total: int
    bound_ppm: int
    passed: bool


@dataclass(frozen=True)
class GateEvaluationResult:
    plan: GateEvaluationPlan
    status: GateEvaluationStatus
    reason_code: str
    metrics: tuple[MetricEvaluation, ...]
    missing_cells: tuple[str, ...]
    evidence_sha256: str
    cost_ledger_sha256: str
    forbidden_calls: int
    cost_complete: bool
    exact_a0_preserved: bool
    negative_controls_passed: bool
    promotion_eligible: bool
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, GateEvaluationPlan):
            raise TypeError("plan must be GateEvaluationPlan")
        object.__setattr__(self, "status", GateEvaluationStatus(self.status))
        _text("reason_code", self.reason_code)
        if not isinstance(self.metrics, tuple) or any(
            not isinstance(item, MetricEvaluation) for item in self.metrics
        ):
            raise TypeError("metrics must contain MetricEvaluation")
        if not isinstance(self.missing_cells, tuple):
            raise TypeError("missing_cells must be a tuple")
        _digest("evidence_sha256", self.evidence_sha256)
        _digest("cost_ledger_sha256", self.cost_ledger_sha256)
        _count("forbidden_calls", self.forbidden_calls)
        for name in (
            "cost_complete",
            "exact_a0_preserved",
            "negative_controls_passed",
            "promotion_eligible",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.promotion_eligible and self.status is not GateEvaluationStatus.PASS:
            raise ValueError("only a passing evaluation may be promotion eligible")
        if self.execution_authorized:
            raise ValueError("gate evaluation cannot authorize execution")

    @property
    def result_digest(self) -> str:
        return digest(self)

    def gate_receipt(self, binding: CandidateBinding) -> GateReceipt:
        if not isinstance(binding, CandidateBinding):
            raise TypeError("binding must be CandidateBinding")
        if binding.digest() != self.plan.candidate_binding_digest:
            raise ValueError("candidate binding does not match the frozen gate plan")
        if self.status is GateEvaluationStatus.FAIL:
            gate_status = GateStatus.FAIL
        elif self.promotion_eligible:
            gate_status = GateStatus.PASS
        else:
            gate_status = GateStatus.UNKNOWN
        return GateReceipt(
            gate=self.plan.gate,
            status=gate_status,
            binding_digest=binding.digest(),
            evidence_digest=self.result_digest,
            solve_equivalence_digest=binding.base_answer_digest,
            cost_ledger_digest=self.cost_ledger_sha256,
            reason=self.reason_code,
            forbidden_calls=self.forbidden_calls,
            required_domains_passed=(
                not self.missing_cells and all(item.passed for item in self.metrics)
            ),
            cost_complete=self.cost_complete,
            conditional_validity_passed=(
                self.exact_a0_preserved
                and self.negative_controls_passed
                and self.promotion_eligible
            ),
        )


def evaluate_gate(
    plan: GateEvaluationPlan,
    evidence: GateEvidence,
) -> GateEvaluationResult:
    """Evaluate every preregistered partition/domain/metric cell exactly once."""

    if not isinstance(plan, GateEvaluationPlan):
        raise TypeError("plan must be GateEvaluationPlan")
    if not isinstance(evidence, GateEvidence):
        raise TypeError("evidence must be GateEvidence")
    by_key: dict[tuple[EvidencePartition, str, str], GateMetricObservation] = {}
    duplicate = False
    for row in evidence.observations:
        key = (row.partition, row.domain, row.metric_id)
        if key in by_key:
            duplicate = True
        by_key[key] = row

    evaluations: list[MetricEvaluation] = []
    missing: list[str] = []
    for partition in plan.required_partitions:
        for domain in plan.required_domains:
            for rule in plan.metric_rules:
                key = (partition, domain, rule.metric_id)
                row = by_key.get(key)
                cell = f"{partition.value}:{domain}:{rule.metric_id}"
                if row is None:
                    missing.append(cell)
                    continue
                if row.total < rule.minimum_n:
                    missing.append(f"{cell}:n<{rule.minimum_n}")
                    continue
                if rule.direction is MetricDirection.AT_LEAST:
                    bound = clopper_pearson_lower_ppm(
                        row.successes,
                        row.total,
                        rule.confidence_ppm,
                    )
                    passed = bound >= rule.threshold_ppm
                else:
                    bound = clopper_pearson_upper_ppm(
                        row.successes,
                        row.total,
                        rule.confidence_ppm,
                    )
                    passed = bound <= rule.threshold_ppm
                evaluations.append(
                    MetricEvaluation(
                        partition=partition,
                        domain=domain,
                        metric_id=rule.metric_id,
                        successes=row.successes,
                        total=row.total,
                        bound_ppm=bound,
                        passed=passed,
                    )
                )

    expected_keys = {
        (partition, domain, rule.metric_id)
        for partition in plan.required_partitions
        for domain in plan.required_domains
        for rule in plan.metric_rules
    }
    unexpected = sorted(
        f"{partition.value}:{domain}:{metric}"
        for partition, domain, metric in set(by_key) - expected_keys
    )
    if unexpected:
        missing.extend(f"unexpected:{item}" for item in unexpected)
    structural_ok = all(
        (
            not duplicate,
            not missing,
            evidence.forbidden_calls == 0,
            evidence.cost_complete,
            evidence.exact_a0_preserved,
            evidence.negative_controls_passed,
        )
    )
    metrics_pass = bool(evaluations) and all(item.passed for item in evaluations)
    promotion_partitions = EvidencePartition.DEVELOPMENT not in plan.required_partitions
    promotion_eligible = structural_ok and metrics_pass and promotion_partitions
    if duplicate:
        status, reason = GateEvaluationStatus.UNKNOWN, "duplicate_metric_cell"
    elif missing:
        status, reason = GateEvaluationStatus.UNKNOWN, "incomplete_metric_matrix"
    elif evidence.forbidden_calls:
        status, reason = GateEvaluationStatus.FAIL, "forbidden_calls_observed"
    elif not evidence.cost_complete:
        status, reason = GateEvaluationStatus.UNKNOWN, "cost_ledger_incomplete"
    elif not evidence.exact_a0_preserved:
        status, reason = GateEvaluationStatus.FAIL, "a0_equivalence_failed"
    elif not evidence.negative_controls_passed:
        status, reason = GateEvaluationStatus.FAIL, "negative_controls_failed"
    elif not metrics_pass:
        status, reason = GateEvaluationStatus.FAIL, "one_or_more_metric_bounds_failed"
    elif not promotion_partitions:
        status, reason = GateEvaluationStatus.PASS, "development_evidence_only"
    else:
        status, reason = GateEvaluationStatus.PASS, "all_preregistered_gate_cells_passed"
    evidence_sha256 = digest(
        {
            "plan_digest": plan.plan_digest,
            "source_bundle_sha256": evidence.source_bundle_sha256,
            "cost_ledger_sha256": evidence.cost_ledger_sha256,
            "observation_sources": tuple(
                sorted(item.source_sha256 for item in evidence.observations)
            ),
        }
    )
    return GateEvaluationResult(
        plan=plan,
        status=status,
        reason_code=reason,
        metrics=tuple(evaluations),
        missing_cells=tuple(missing),
        evidence_sha256=evidence_sha256,
        cost_ledger_sha256=evidence.cost_ledger_sha256,
        forbidden_calls=evidence.forbidden_calls,
        cost_complete=evidence.cost_complete,
        exact_a0_preserved=evidence.exact_a0_preserved,
        negative_controls_passed=evidence.negative_controls_passed,
        promotion_eligible=promotion_eligible,
    )
