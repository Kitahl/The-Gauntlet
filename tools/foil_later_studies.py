"""Fail-closed contracts for FOIL's later empirical studies.

This module validates frozen study topology and sealed run inventories.  It does
not run models, score outcomes, infer efficacy, or authorize promotion.  A
complete contract means only that an external evaluator has the preregistered
arms and evidence cells needed to begin an honest analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from egrt_types import digest
from foil_promotion_gates import EvidencePartition


class StudyKind(str, Enum):
    PROFILE_P0 = "PROFILE_P0"
    RQ26_COMPLEMENT = "RQ26_COMPLEMENT"
    MODEL_STRENGTH_LADDER = "MODEL_STRENGTH_LADDER"
    HISTORY_POLICY = "HISTORY_POLICY"
    HUMAN_COMPLEMENT = "HUMAN_COMPLEMENT"


class StudyContractStatus(str, Enum):
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    DEVELOPMENT_ONLY = "DEVELOPMENT_ONLY"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


FIXED_ARMS: dict[StudyKind, tuple[str, ...]] = {
    StudyKind.PROFILE_P0: (
        "CORRECT_PROFILE",
        "WRONG_PROFILE",
        "NO_PROFILE",
    ),
    StudyKind.RQ26_COMPLEMENT: (
        "RAW",
        "CHECKLIST",
        "FOIL",
        "ORACLE",
    ),
    StudyKind.HISTORY_POLICY: (
        "STATIC",
        "SIMPLE_HISTORY",
        "CONTEXTUAL_STATISTICAL",
        "SYNAPSE",
        "HEBBIAN_MUTANT",
    ),
    StudyKind.HUMAN_COMPLEMENT: (
        "USER_ALONE",
        "GENERIC_AI",
        "STATIC_FOIL",
        "ADAPTIVE_FOIL",
    ),
}


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


def _unique_text_tuple(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise ValueError(f"{name} must be a non-empty tuple")
    for item in value:
        _text(name, item)
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must be unique")
    return value


@dataclass(frozen=True)
class StudyPlan:
    study_id: str
    kind: StudyKind
    arms: tuple[str, ...]
    domains: tuple[str, ...]
    metrics: tuple[str, ...]
    partitions: tuple[EvidencePartition, ...]
    minimum_replicates: int
    protocol_sha256: str
    environment_sha256: str
    frozen: bool
    matched_budget_required: bool = True
    model_fingerprints: tuple[str, ...] = ()
    effort_levels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text("study_id", self.study_id)
        object.__setattr__(self, "kind", StudyKind(self.kind))
        _unique_text_tuple("arms", self.arms)
        _unique_text_tuple("domains", self.domains)
        _unique_text_tuple("metrics", self.metrics)
        if not isinstance(self.partitions, tuple) or not self.partitions:
            raise ValueError("partitions must be a non-empty tuple")
        partitions = tuple(EvidencePartition(item) for item in self.partitions)
        object.__setattr__(self, "partitions", partitions)
        if len(set(partitions)) != len(partitions):
            raise ValueError("partitions must be unique")
        if EvidencePartition.DEVELOPMENT in partitions and len(partitions) > 1:
            raise ValueError("development cannot be pooled with held-out partitions")
        if self.minimum_replicates <= 0:
            raise ValueError("minimum_replicates must be positive")
        _digest("protocol_sha256", self.protocol_sha256)
        _digest("environment_sha256", self.environment_sha256)
        if not isinstance(self.frozen, bool):
            raise TypeError("frozen must be bool")
        if not isinstance(self.matched_budget_required, bool):
            raise TypeError("matched_budget_required must be bool")
        if self.kind is StudyKind.MODEL_STRENGTH_LADDER:
            _unique_text_tuple("model_fingerprints", self.model_fingerprints)
            _unique_text_tuple("effort_levels", self.effort_levels)
            if len(self.model_fingerprints) < 2 or len(self.effort_levels) < 2:
                raise ValueError("model ladder needs at least two models and two efforts")
        elif self.model_fingerprints or self.effort_levels:
            raise ValueError("model and effort axes belong only to the model ladder")

    @property
    def required_arms(self) -> tuple[str, ...]:
        if self.kind is StudyKind.MODEL_STRENGTH_LADDER:
            return tuple(
                f"{model}@{effort}"
                for model in self.model_fingerprints
                for effort in self.effort_levels
            )
        return FIXED_ARMS[self.kind]

    @property
    def plan_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class StudyRunCell:
    partition: EvidencePartition
    domain: str
    arm: str
    replicate_count: int
    source_sha256: str
    budget_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "partition", EvidencePartition(self.partition))
        _text("domain", self.domain)
        _text("arm", self.arm)
        if self.replicate_count <= 0:
            raise ValueError("replicate_count must be positive")
        _digest("source_sha256", self.source_sha256)
        _digest("budget_sha256", self.budget_sha256)


@dataclass(frozen=True)
class StudySafeguards:
    cost_complete: bool
    contamination_free: bool
    negative_controls_passed: bool
    redaction_enforced: bool = False
    provenance_bound: bool = False
    expiry_enforced: bool = False
    drift_checked: bool = False
    rollback_tested: bool = False
    delayed_transfer_measured: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True)
class StudyRunInventory:
    cells: tuple[StudyRunCell, ...]
    safeguards: StudySafeguards
    cost_ledger_sha256: str
    source_bundle_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.cells, tuple) or any(
            not isinstance(item, StudyRunCell) for item in self.cells
        ):
            raise TypeError("cells must contain StudyRunCell")
        if not isinstance(self.safeguards, StudySafeguards):
            raise TypeError("safeguards must be StudySafeguards")
        _digest("cost_ledger_sha256", self.cost_ledger_sha256)
        _digest("source_bundle_sha256", self.source_bundle_sha256)


@dataclass(frozen=True)
class StudyContractResult:
    plan_digest: str
    inventory_digest: str
    status: StudyContractStatus
    reason_codes: tuple[str, ...]
    missing_cells: tuple[str, ...]
    unexpected_cells: tuple[str, ...]
    efficacy_established: bool = field(default=False, init=False)
    promotion_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _digest("plan_digest", self.plan_digest)
        _digest("inventory_digest", self.inventory_digest)
        object.__setattr__(self, "status", StudyContractStatus(self.status))
        for name in ("reason_codes", "missing_cells", "unexpected_cells"):
            if not isinstance(getattr(self, name), tuple):
                raise TypeError(f"{name} must be a tuple")
        if self.efficacy_established or self.promotion_authorized:
            raise ValueError("study topology cannot establish efficacy or promotion")
        if self.execution_authorized:
            raise ValueError("study topology cannot authorize execution")


def validate_study_contract(
    plan: StudyPlan,
    inventory: StudyRunInventory,
) -> StudyContractResult:
    """Validate exact arms, cells, safeguards, and matched-budget topology."""

    if not isinstance(plan, StudyPlan):
        raise TypeError("plan must be StudyPlan")
    if not isinstance(inventory, StudyRunInventory):
        raise TypeError("inventory must be StudyRunInventory")
    reasons: list[str] = []
    if not plan.frozen:
        reasons.append("protocol_not_frozen")
    if set(plan.arms) != set(plan.required_arms):
        reasons.append("arm_contract_mismatch")

    actual: dict[tuple[EvidencePartition, str, str], StudyRunCell] = {}
    duplicates = False
    for cell in inventory.cells:
        key = (cell.partition, cell.domain, cell.arm)
        if key in actual:
            duplicates = True
        actual[key] = cell
    if duplicates:
        reasons.append("duplicate_run_cell")

    expected = {
        (partition, domain, arm)
        for partition in plan.partitions
        for domain in plan.domains
        for arm in plan.arms
    }
    missing_keys = expected - set(actual)
    extra_keys = set(actual) - expected
    missing = tuple(sorted(_cell_name(item) for item in missing_keys))
    unexpected = tuple(sorted(_cell_name(item) for item in extra_keys))
    if missing:
        reasons.append("incomplete_run_matrix")
    if unexpected:
        reasons.append("unexpected_run_cell")
    if any(actual[key].replicate_count < plan.minimum_replicates for key in expected & set(actual)):
        reasons.append("insufficient_replicates")

    if plan.matched_budget_required:
        for partition in plan.partitions:
            for domain in plan.domains:
                budgets = {
                    cell.budget_sha256
                    for key, cell in actual.items()
                    if key[0] is partition and key[1] == domain and key in expected
                }
                if len(budgets) > 1:
                    reasons.append("arm_budget_mismatch")
                    break

    safeguards = inventory.safeguards
    if not safeguards.cost_complete:
        reasons.append("cost_ledger_incomplete")
    if not safeguards.contamination_free:
        reasons.append("partition_contamination")
    if not safeguards.negative_controls_passed:
        reasons.append("negative_controls_failed")
    if plan.kind is StudyKind.HISTORY_POLICY and not all(
        (
            safeguards.redaction_enforced,
            safeguards.provenance_bound,
            safeguards.expiry_enforced,
            safeguards.drift_checked,
            safeguards.rollback_tested,
        )
    ):
        reasons.append("history_safeguards_incomplete")
    if (
        plan.kind is StudyKind.HUMAN_COMPLEMENT
        and not safeguards.delayed_transfer_measured
    ):
        reasons.append("delayed_transfer_missing")

    if any(reason in {"arm_contract_mismatch", "unexpected_run_cell"} for reason in reasons):
        status = StudyContractStatus.INVALID
    elif reasons:
        status = StudyContractStatus.INCOMPLETE
    elif EvidencePartition.DEVELOPMENT in plan.partitions:
        status = StudyContractStatus.DEVELOPMENT_ONLY
    else:
        status = StudyContractStatus.READY_FOR_ANALYSIS
    return StudyContractResult(
        plan_digest=plan.plan_digest,
        inventory_digest=digest(inventory),
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons)),
        missing_cells=missing,
        unexpected_cells=unexpected,
    )


def _cell_name(key: tuple[EvidencePartition, str, str]) -> str:
    partition, domain, arm = key
    return f"{partition.value}:{domain}:{arm}"
