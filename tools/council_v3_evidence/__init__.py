"""Council v3 seat-local smart-evidence acquisition.

This additive layer wraps the Council vNext state machine without importing FOIL.
It freezes per-seat evidence budgets and bundle plans before acquisition, admits only
task-local read-only evidence, prevents cross-seat result reuse before commit, and
binds an evidence-audit digest into Council's REVIEW receipt.

Council v3 does not establish behavioral efficacy and does not grant domain authority.
A future FOIL smart-tool controller may propose neutral bundle candidates, but Council
retains the same REVIEW_ONLY boundary and target modules retain claim-native authority.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import council_runtime as council
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import Receipt, digest

SCHEMA_VERSION = "egrt.council.v3"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_STATUSES = {"VALID", "UNRESOLVED", "INVALID"}
_SIDE_EFFECT_CLASSES = {"READ_ONLY", "REVERSIBLE", "CONSEQUENTIAL"}


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _probability(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1")


def _nonnegative_number(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{name} must be finite and non-negative")


def _nonnegative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _unique_texts(name: str, values: Sequence[str]) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


@dataclass(frozen=True)
class EvidenceBudget:
    """Caller-frozen upper bounds for one Council evidence partition."""

    token_limit: int
    money_microunits_limit: int
    latency_ms_limit: int
    tool_call_limit: int

    def __post_init__(self) -> None:
        for name in (
            "token_limit",
            "money_microunits_limit",
            "latency_ms_limit",
            "tool_call_limit",
        ):
            _nonnegative_int(name, getattr(self, name))


@dataclass(frozen=True)
class EvidenceUtilityPolicy:
    """Frozen decision values/prices shared across all candidate bundles for one seat."""

    rescue_value: float
    damage_loss: float
    token_price: float
    money_price: float
    latency_price: float
    privacy_price: float
    failure_loss: float
    minimum_margin: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "rescue_value",
            "damage_loss",
            "token_price",
            "money_price",
            "latency_price",
            "privacy_price",
            "failure_loss",
            "minimum_margin",
        ):
            _nonnegative_number(name, getattr(self, name))


@dataclass(frozen=True)
class EvidenceBundleCandidate:
    """Neutral, receipt-backed candidate tool bundle for one frozen Council seat."""

    bundle_id: str
    seat_id: str
    provided_capabilities: tuple[str, ...]
    tool_ids: tuple[str, ...]
    tool_contracts: tuple[tuple[str, str], ...]
    estimate_receipt_ids: tuple[str, ...]
    estimate_receipt_digests: tuple[str, ...]
    rescue_probability_lcb: float
    valid_evidence_probability_lcb: float
    damage_probability_ucb: float
    token_cost: int
    money_microunits_cost: int
    latency_ms: int
    privacy_cost: float
    failure_probability_ucb: float
    interaction_basis: str = "DIRECT_BUNDLE_RECEIPTS"
    dependency_edges: tuple[tuple[str, str], ...] = ()
    task_only_frontier: bool = True
    hidden_gold_dependent: bool = False
    side_effect_class: str = "READ_ONLY"
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_text("bundle_id", self.bundle_id)
        _require_text("seat_id", self.seat_id)
        _unique_texts("provided_capabilities", self.provided_capabilities)
        _unique_texts("tool_ids", self.tool_ids)
        _unique_texts("estimate_receipt_ids", self.estimate_receipt_ids)
        if not self.estimate_receipt_ids:
            raise ValueError("bundle estimates require at least one frozen scored receipt")
        if len(self.estimate_receipt_digests) != len(self.estimate_receipt_ids):
            raise ValueError("estimate receipt IDs and digests must have equal length")
        for estimate_digest in self.estimate_receipt_digests:
            _sha256("estimate_receipt_digest", estimate_digest)
        if not self.tool_ids:
            raise ValueError("bundle requires at least one tool")
        if self.side_effect_class not in _SIDE_EFFECT_CLASSES:
            raise ValueError("unknown side_effect_class")
        if not isinstance(self.task_only_frontier, bool):
            raise TypeError("task_only_frontier must be bool")
        if not isinstance(self.hidden_gold_dependent, bool):
            raise TypeError("hidden_gold_dependent must be bool")

        contract_ids: list[str] = []
        for tool_id, contract_digest in self.tool_contracts:
            _require_text("tool_contract tool_id", tool_id)
            _sha256("tool_contract digest", contract_digest)
            contract_ids.append(tool_id)
        if set(contract_ids) != set(self.tool_ids) or len(contract_ids) != len(self.tool_ids):
            raise ValueError("tool_contracts must bind exactly one digest to every bundle tool")

        tool_set = set(self.tool_ids)
        for parent, child in self.dependency_edges:
            if parent not in tool_set or child not in tool_set:
                raise ValueError("dependency edge references tool outside the bundle")
            if parent == child:
                raise ValueError("dependency graph cannot contain self loops")
        _require_acyclic(self.tool_ids, self.dependency_edges)

        _probability("rescue_probability_lcb", self.rescue_probability_lcb)
        _probability("valid_evidence_probability_lcb", self.valid_evidence_probability_lcb)
        _probability("damage_probability_ucb", self.damage_probability_ucb)
        _probability("failure_probability_ucb", self.failure_probability_ucb)
        _nonnegative_number("privacy_cost", self.privacy_cost)
        if self.interaction_basis not in {"DIRECT_BUNDLE_RECEIPTS", "PESSIMISTIC_PRIOR"}:
            raise ValueError(
                "interaction_basis must be DIRECT_BUNDLE_RECEIPTS or PESSIMISTIC_PRIOR"
            )
        for name in ("token_cost", "money_microunits_cost", "latency_ms"):
            _nonnegative_int(name, getattr(self, name))

    @property
    def tool_call_cost(self) -> int:
        return len(self.tool_ids)


@dataclass(frozen=True)
class SeatEvidenceReceipt:
    """One normalized acquisition envelope for a selected Council seat bundle."""

    evidence_envelope_id: str
    council_id: str
    seat_id: str
    bundle_id: str
    evidence_status: str
    executed_tool_ids: tuple[str, ...]
    tool_receipt_ids: tuple[str, ...]
    source_artifact_digests: tuple[str, ...]
    provenance_groups: tuple[str, ...]
    admitted_evidence_ids: tuple[str, ...]
    token_used: int
    money_microunits_used: int
    latency_ms: int
    calls_attempted: int
    calls_completed: int
    calls_failed: int
    calls_cancelled: int
    output_digest: str
    side_effect_class: str = "READ_ONLY"
    reused_from_seat_ids: tuple[str, ...] = ()
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("evidence_envelope_id", "council_id", "seat_id", "bundle_id"):
            _require_text(name, getattr(self, name))
        if self.evidence_status not in _EVIDENCE_STATUSES:
            raise ValueError("evidence_status must be VALID, UNRESOLVED, or INVALID")
        if self.side_effect_class != "READ_ONLY":
            raise ValueError("Council v3 admits only READ_ONLY seat evidence")
        _unique_texts("executed_tool_ids", self.executed_tool_ids)
        _unique_texts("tool_receipt_ids", self.tool_receipt_ids)
        _unique_texts("provenance_groups", self.provenance_groups)
        _unique_texts("admitted_evidence_ids", self.admitted_evidence_ids)
        _unique_texts("reused_from_seat_ids", self.reused_from_seat_ids)
        for source_digest in self.source_artifact_digests:
            _sha256("source_artifact_digest", source_digest)
        if len(set(self.source_artifact_digests)) != len(self.source_artifact_digests):
            raise ValueError("source_artifact_digests must be unique")
        _sha256("output_digest", self.output_digest)
        for name in (
            "token_used",
            "money_microunits_used",
            "latency_ms",
            "calls_attempted",
            "calls_completed",
            "calls_failed",
            "calls_cancelled",
        ):
            _nonnegative_int(name, getattr(self, name))
        if self.calls_completed + self.calls_failed + self.calls_cancelled != self.calls_attempted:
            raise ValueError("call outcome counts must conserve calls_attempted")
        if self.evidence_status != "VALID" and self.admitted_evidence_ids:
            raise ValueError("invalid or unresolved evidence cannot be admitted")


def _require_acyclic(
    tool_ids: Sequence[str],
    edges: Sequence[tuple[str, str]],
) -> None:
    children: dict[str, list[str]] = {tool_id: [] for tool_id in tool_ids}
    indegree: dict[str, int] = {tool_id: 0 for tool_id in tool_ids}
    for parent, child in edges:
        children[parent].append(child)
        indegree[child] += 1
    frontier = sorted(tool_id for tool_id, degree in indegree.items() if degree == 0)
    seen = 0
    while frontier:
        node = frontier.pop(0)
        seen += 1
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                frontier.append(child)
                frontier.sort()
    if seen != len(tool_ids):
        raise ValueError("dependency graph must be acyclic")


def _plain(value: object) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return json.loads(json.dumps(asdict(value), sort_keys=True))
    return json.loads(json.dumps(value, sort_keys=True))


def _council_row(root: Path, council_id: str) -> dict[str, Any]:
    row = RuntimeStore(root).read_named_state("councils", council_id)
    if row is None:
        raise KeyError(council_id)
    return row


def _v3_row(root: Path, council_id: str) -> dict[str, Any]:
    row = RuntimeStore(root).read_named_state("council_v3", council_id)
    if row is None:
        raise KeyError(f"Council v3 evidence state not initialized: {council_id}")
    return row


def _write_v3(root: Path, council_id: str, row: Mapping[str, Any]) -> None:
    RuntimeStore(root).write_named_state("council_v3", council_id, dict(row))


def _validate_frozen_partition(
    seat_ids: set[str],
    total_budget: EvidenceBudget,
    seat_budgets: Mapping[str, EvidenceBudget],
    utility_policies: Mapping[str, EvidenceUtilityPolicy],
) -> None:
    if set(seat_budgets) != seat_ids:
        raise ValueError("seat_budgets must contain exactly one budget for every Council seat")
    if set(utility_policies) != seat_ids:
        raise ValueError("utility_policies must contain exactly one policy for every Council seat")
    token_sum = sum(budget.token_limit for budget in seat_budgets.values())
    money_sum = sum(budget.money_microunits_limit for budget in seat_budgets.values())
    call_sum = sum(budget.tool_call_limit for budget in seat_budgets.values())
    max_latency = max((budget.latency_ms_limit for budget in seat_budgets.values()), default=0)
    if token_sum > total_budget.token_limit:
        raise ValueError("seat token budgets exceed frozen Council total")
    if money_sum > total_budget.money_microunits_limit:
        raise ValueError("seat money budgets exceed frozen Council total")
    if call_sum > total_budget.tool_call_limit:
        raise ValueError("seat call budgets exceed frozen Council total")
    if max_latency > total_budget.latency_ms_limit:
        raise ValueError("a seat latency budget exceeds the frozen Council wall-time ceiling")


def create_council_v3(
    root: Path,
    artifact_hash: str,
    budget_hash: str,
    seats: list[council.CouncilSeat],
    *,
    total_budget: EvidenceBudget,
    seat_budgets: Mapping[str, EvidenceBudget],
    utility_policies: Mapping[str, EvidenceUtilityPolicy],
    task_id: str | None = None,
    baseline_evidence_ids: Mapping[str, Sequence[str]] | None = None,
    baseline_provenance_groups: Mapping[str, Sequence[str]] | None = None,
) -> council.CouncilState:
    """Create Council vNext and freeze Council-v3 evidence partitions/budgets."""
    if not seats or any(seat.challenge_contract != "vnext" for seat in seats):
        raise ValueError("Council v3 requires vNext challenge-derived seats")
    seat_ids = {seat.seat_id for seat in seats}
    if len(seat_ids) != len(seats):
        raise ValueError("Council v3 seat IDs must be unique")
    _validate_frozen_partition(seat_ids, total_budget, seat_budgets, utility_policies)
    state = council.create_council(
        root,
        artifact_hash,
        budget_hash,
        seats,
        task_id=task_id,
    )
    initialize_evidence_layer(
        root,
        state.council_id,
        total_budget=total_budget,
        seat_budgets=seat_budgets,
        utility_policies=utility_policies,
        baseline_evidence_ids=baseline_evidence_ids,
        baseline_provenance_groups=baseline_provenance_groups,
    )
    return state


def initialize_evidence_layer(
    root: Path,
    council_id: str,
    *,
    total_budget: EvidenceBudget,
    seat_budgets: Mapping[str, EvidenceBudget],
    utility_policies: Mapping[str, EvidenceUtilityPolicy],
    baseline_evidence_ids: Mapping[str, Sequence[str]] | None = None,
    baseline_provenance_groups: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """Freeze seat-local budgets before any evidence acquisition or first-pass commit."""
    council_row = _council_row(root, council_id)
    if council_row.get("phase") != "COMMIT" or council_row.get("commitments"):
        raise ValueError("Council v3 evidence budgets must freeze before any seat commit")
    seats = council_row.get("seats", [])
    if not seats or any(seat.get("challenge_contract") != "vnext" for seat in seats):
        raise ValueError("Council v3 requires vNext challenge-derived seats")
    seat_ids = {str(seat["seat_id"]) for seat in seats}
    _validate_frozen_partition(seat_ids, total_budget, seat_budgets, utility_policies)

    baseline_evidence_ids = baseline_evidence_ids or {}
    baseline_provenance_groups = baseline_provenance_groups or {}
    baseline_rows: dict[str, Any] = {}
    for seat_id in sorted(seat_ids):
        evidence = tuple(baseline_evidence_ids.get(seat_id, ()))
        provenance = tuple(baseline_provenance_groups.get(seat_id, ()))
        _unique_texts("baseline_evidence_ids", evidence)
        _unique_texts("baseline_provenance_groups", provenance)
        baseline_rows[seat_id] = {
            "evidence_ids": list(evidence),
            "provenance_groups": list(provenance),
        }

    row = {
        "schema": SCHEMA_VERSION,
        "council_id": council_id,
        "phase": "INITIALIZED",
        "initialized_at": utcnow(),
        "total_budget": _plain(total_budget),
        "seat_budgets": {
            seat_id: _plain(seat_budgets[seat_id])
            for seat_id in sorted(seat_ids)
        },
        "utility_policies": {
            seat_id: _plain(utility_policies[seat_id])
            for seat_id in sorted(seat_ids)
        },
        "baseline": baseline_rows,
        "plans": {},
        "receipts": {},
        "committed_seats": [],
        "plan_freeze_hash": None,
        "audit": None,
        "authority": "EVIDENCE_ACQUISITION_ONLY",
        "domain_clearance_authorized": False,
        "cross_seat_budget_transfer_authorized": False,
        "cross_seat_result_reuse_before_reveal_authorized": False,
    }
    _write_v3(root, council_id, row)


def _budget_from_row(row: Mapping[str, Any]) -> EvidenceBudget:
    return EvidenceBudget(**dict(row))


def _policy_from_row(row: Mapping[str, Any]) -> EvidenceUtilityPolicy:
    return EvidenceUtilityPolicy(**dict(row))


def _utility_lcb(
    candidate: EvidenceBundleCandidate,
    policy: EvidenceUtilityPolicy,
) -> float:
    return (
        float(policy.rescue_value)
        * float(candidate.rescue_probability_lcb)
        * float(candidate.valid_evidence_probability_lcb)
        - float(policy.damage_loss) * float(candidate.damage_probability_ucb)
        - float(policy.token_price) * float(candidate.token_cost)
        - float(policy.money_price) * float(candidate.money_microunits_cost)
        - float(policy.latency_price) * float(candidate.latency_ms)
        - float(policy.privacy_price) * float(candidate.privacy_cost)
        - float(policy.failure_loss) * float(candidate.failure_probability_ucb)
    )


def _within_budget(candidate: EvidenceBundleCandidate, budget: EvidenceBudget) -> bool:
    return (
        candidate.token_cost <= budget.token_limit
        and candidate.money_microunits_cost <= budget.money_microunits_limit
        and candidate.latency_ms <= budget.latency_ms_limit
        and candidate.tool_call_cost <= budget.tool_call_limit
    )


def _dominates(
    left: EvidenceBundleCandidate,
    right: EvidenceBundleCandidate,
    *,
    left_utility: float,
    right_utility: float,
) -> bool:
    weak = (
        left_utility >= right_utility
        and left.token_cost <= right.token_cost
        and left.money_microunits_cost <= right.money_microunits_cost
        and left.latency_ms <= right.latency_ms
        and left.tool_call_cost <= right.tool_call_cost
    )
    strict = (
        left_utility > right_utility
        or left.token_cost < right.token_cost
        or left.money_microunits_cost < right.money_microunits_cost
        or left.latency_ms < right.latency_ms
        or left.tool_call_cost < right.tool_call_cost
    )
    return weak and strict


def freeze_evidence_plans(
    root: Path,
    council_id: str,
    candidates_by_seat: Mapping[str, Sequence[EvidenceBundleCandidate]],
) -> dict[str, Any]:
    """Freeze all seat plans atomically before any Council first-pass commit."""
    council_row = _council_row(root, council_id)
    v3 = _v3_row(root, council_id)
    if v3.get("phase") != "INITIALIZED":
        raise ValueError("Council v3 evidence plans are immutable once frozen")
    if council_row.get("phase") != "COMMIT" or council_row.get("commitments"):
        raise ValueError("all Council v3 plans must freeze before any seat commit")

    seat_map = {str(seat["seat_id"]): seat for seat in council_row.get("seats", [])}
    unknown = set(candidates_by_seat) - set(seat_map)
    if unknown:
        raise KeyError(f"candidate bundles supplied for unknown seats: {sorted(unknown)}")

    plans: dict[str, Any] = {}
    for seat_id in sorted(seat_map):
        seat = seat_map[seat_id]
        required_capability = seat.get("required_capability")
        budget = _budget_from_row(v3["seat_budgets"][seat_id])
        policy = _policy_from_row(v3["utility_policies"][seat_id])
        candidates = list(candidates_by_seat.get(seat_id, ()))
        if len({candidate.bundle_id for candidate in candidates}) != len(candidates):
            raise ValueError(f"duplicate bundle_id in seat {seat_id}")

        exclusions: dict[str, str] = {}
        feasible: list[EvidenceBundleCandidate] = []
        for candidate in candidates:
            if candidate.seat_id != seat_id:
                raise ValueError("bundle seat_id does not match its Council evidence partition")
            reason: str | None = None
            if not candidate.task_only_frontier:
                reason = "NOT_TASK_ONLY_FRONTIER"
            elif candidate.hidden_gold_dependent:
                reason = "HIDDEN_GOLD_DEPENDENT"
            elif candidate.side_effect_class != "READ_ONLY":
                reason = "NON_READ_ONLY"
            elif required_capability and required_capability not in candidate.provided_capabilities:
                reason = "MISSING_REQUIRED_CAPABILITY"
            elif not _within_budget(candidate, budget):
                reason = "OVER_SEAT_BUDGET"
            if reason:
                exclusions[candidate.bundle_id] = reason
            else:
                feasible.append(candidate)

        utility = {
            candidate.bundle_id: _utility_lcb(candidate, policy)
            for candidate in feasible
        }
        nondominated: list[EvidenceBundleCandidate] = []
        for candidate in feasible:
            dominator = next(
                (
                    other
                    for other in feasible
                    if (
                        other.bundle_id != candidate.bundle_id
                        and _dominates(
                            other,
                            candidate,
                            left_utility=utility[other.bundle_id],
                            right_utility=utility[candidate.bundle_id],
                        )
                    )
                ),
                None,
            )
            if dominator is not None:
                exclusions[candidate.bundle_id] = f"DOMINATED_BY:{dominator.bundle_id}"
            else:
                nondominated.append(candidate)

        ranked = sorted(
            nondominated,
            key=lambda candidate: (
                -utility[candidate.bundle_id],
                candidate.token_cost,
                candidate.money_microunits_cost,
                candidate.latency_ms,
                candidate.tool_call_cost,
                candidate.bundle_id,
            ),
        )
        selected = (
            ranked[0]
            if ranked and utility[ranked[0].bundle_id] > policy.minimum_margin
            else None
        )
        reason = "POSITIVE_CONSERVATIVE_VALUE" if selected else "STAND_DOWN_NONPOSITIVE_OR_INFEASIBLE"

        plan_payload = {
            "schema": SCHEMA_VERSION,
            "plan_id": new_id("c3plan"),
            "council_id": council_id,
            "seat_id": seat_id,
            "evidence_partition": seat.get("evidence_partition"),
            "required_capability": required_capability,
            "frozen_budget": _plain(budget),
            "utility_policy": _plain(policy),
            "baseline": dict(v3["baseline"][seat_id]),
            "candidate_rows": [
                {
                    **_plain(candidate),
                    "utility_lcb": _utility_lcb(candidate, policy),
                    "exclusion_reason": exclusions.get(candidate.bundle_id),
                }
                for candidate in sorted(candidates, key=lambda item: item.bundle_id)
            ],
            "selected_bundle_id": selected.bundle_id if selected else None,
            "selected_utility_lcb": (
                _utility_lcb(selected, policy) if selected else None
            ),
            "selection_reason": reason,
            "frozen_before_any_commit": True,
            "frozen_at": utcnow(),
        }
        plan_payload["plan_hash"] = digest(plan_payload)
        plans[seat_id] = plan_payload

    v3["plans"] = plans
    v3["plan_freeze_hash"] = digest(
        {
            "council_id": council_id,
            "plans": {seat_id: plans[seat_id]["plan_hash"] for seat_id in sorted(plans)},
        }
    )
    v3["phase"] = "PLANS_FROZEN"
    _write_v3(root, council_id, v3)
    return plans


def selected_bundle(root: Path, council_id: str, seat_id: str) -> dict[str, Any] | None:
    v3 = _v3_row(root, council_id)
    plan = v3.get("plans", {}).get(seat_id)
    if plan is None:
        raise KeyError(seat_id)
    selected_id = plan.get("selected_bundle_id")
    if selected_id is None:
        return None
    for row in plan.get("candidate_rows", []):
        if row.get("bundle_id") == selected_id:
            return dict(row)
    raise ValueError("selected Council v3 bundle is missing from its frozen plan")


def record_seat_evidence(
    root: Path,
    council_id: str,
    receipt: SeatEvidenceReceipt,
) -> None:
    """Record one seat-local evidence envelope before any seat first-pass commit."""
    council_row = _council_row(root, council_id)
    v3 = _v3_row(root, council_id)
    if receipt.council_id != council_id:
        raise ValueError("evidence receipt council_id mismatch")
    if v3.get("phase") not in {"PLANS_FROZEN", "EVIDENCE_READY"}:
        raise ValueError("Council v3 is not accepting evidence acquisition receipts")
    if council_row.get("commitments"):
        raise ValueError("seat evidence acquisition must finish before any first-pass commit")
    if receipt.seat_id in v3.get("receipts", {}):
        raise ValueError("Council v3 accepts one normalized evidence envelope per seat")
    if receipt.reused_from_seat_ids:
        raise ValueError("cross-seat result reuse is forbidden before Council reveal")

    selected = selected_bundle(root, council_id, receipt.seat_id)
    if selected is None:
        raise ValueError("seat stood down; no tool evidence may be recorded")
    if receipt.bundle_id != selected.get("bundle_id"):
        raise ValueError("evidence receipt does not match the frozen selected bundle")
    if not set(receipt.executed_tool_ids).issubset(set(selected.get("tool_ids", []))):
        raise ValueError("evidence receipt executed a tool outside the frozen selected bundle")
    budget = _budget_from_row(v3["seat_budgets"][receipt.seat_id])
    if receipt.token_used > budget.token_limit:
        raise ValueError("seat evidence exceeded frozen token budget")
    if receipt.money_microunits_used > budget.money_microunits_limit:
        raise ValueError("seat evidence exceeded frozen money budget")
    if receipt.latency_ms > budget.latency_ms_limit:
        raise ValueError("seat evidence exceeded frozen latency budget")
    if receipt.calls_attempted > budget.tool_call_limit:
        raise ValueError("seat evidence exceeded frozen tool-call budget")

    v3.setdefault("receipts", {})[receipt.seat_id] = _plain(receipt)
    all_ready = all(
        plan.get("selected_bundle_id") is None or seat_id in v3["receipts"]
        for seat_id, plan in v3.get("plans", {}).items()
    )
    if all_ready:
        v3["phase"] = "EVIDENCE_READY"
    _write_v3(root, council_id, v3)


def commit_v3(
    root: Path,
    council_id: str,
    seat_id: str,
    submission: council.SeatSubmission,
    *,
    nonce: str | None = None,
) -> tuple[str, str]:
    """Commit only after every seat's acquisition phase is complete and isolated."""
    v3 = _v3_row(root, council_id)
    if v3.get("phase") not in {"EVIDENCE_READY", "COMMITTED"}:
        raise ValueError("all Council v3 evidence acquisition must finish before first-pass commits")
    plan = v3.get("plans", {}).get(seat_id)
    if plan is None:
        raise KeyError(seat_id)
    baseline = v3["baseline"][seat_id]
    expected_evidence = set(baseline.get("evidence_ids", []))
    expected_provenance = set(baseline.get("provenance_groups", []))
    receipt_row = v3.get("receipts", {}).get(seat_id)
    if plan.get("selected_bundle_id") is not None:
        if receipt_row is None:
            raise ValueError("selected seat bundle lacks an evidence receipt")
        expected_evidence.update(receipt_row.get("admitted_evidence_ids", []))
        expected_provenance.update(receipt_row.get("provenance_groups", []))
    elif receipt_row is not None:
        raise ValueError("stand-down seat cannot carry acquired tool evidence")

    if set(submission.evidence_ids) != expected_evidence:
        raise ValueError("submission evidence_ids do not match the frozen v3 evidence partition")
    if set(submission.provenance_groups) != expected_provenance:
        raise ValueError("submission provenance_groups do not match the frozen v3 evidence partition")

    commitment, actual_nonce = council.commit(
        root,
        council_id,
        seat_id,
        submission,
        nonce=nonce,
    )
    v3 = _v3_row(root, council_id)
    committed = set(v3.get("committed_seats", []))
    committed.add(seat_id)
    v3["committed_seats"] = sorted(committed)
    if committed == set(v3.get("plans", {})):
        v3["phase"] = "COMMITTED"
    _write_v3(root, council_id, v3)
    return commitment, actual_nonce


def evidence_overlap_matrix(root: Path, council_id: str) -> dict[str, Any]:
    """Measure shared sources/tools across seat partitions; never infer independence."""
    v3 = _v3_row(root, council_id)
    seat_ids = sorted(v3.get("plans", {}))
    rows: list[dict[str, Any]] = []

    def jaccard(left: set[str], right: set[str]) -> float | None:
        if not left and not right:
            return None
        union = left | right
        return len(left & right) / len(union) if union else None

    for index, left in enumerate(seat_ids):
        for right in seat_ids[index + 1 :]:
            left_receipt = v3.get("receipts", {}).get(left, {})
            right_receipt = v3.get("receipts", {}).get(right, {})
            left_plan = selected_bundle(root, council_id, left) or {}
            right_plan = selected_bundle(root, council_id, right) or {}
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "source_overlap": jaccard(
                        set(left_receipt.get("source_artifact_digests", [])),
                        set(right_receipt.get("source_artifact_digests", [])),
                    ),
                    "tool_overlap": jaccard(
                        set(left_plan.get("tool_ids", [])),
                        set(right_plan.get("tool_ids", [])),
                    ),
                    "independence_status": "NOT_ESTABLISHED",
                }
            )
    return {
        "pairs": rows,
        "diagnostics": {
            "seat_count": len(seat_ids),
            "independence_status": "NOT_ESTABLISHED_BY_SEAT_COUNT",
            "interpretation": (
                "Shared source and tool usage are common-cause diagnostics. "
                "Separate seat executions never establish statistical independence by count."
            ),
        },
    }


def _audit(root: Path, council_id: str) -> dict[str, Any]:
    v3 = _v3_row(root, council_id)
    total = _budget_from_row(v3["total_budget"])
    receipts = list(v3.get("receipts", {}).values())
    totals = {
        "token_used": sum(int(row.get("token_used", 0)) for row in receipts),
        "money_microunits_used": sum(int(row.get("money_microunits_used", 0)) for row in receipts),
        "calls_attempted": sum(int(row.get("calls_attempted", 0)) for row in receipts),
        "critical_path_latency_ms": max(
            (int(row.get("latency_ms", 0)) for row in receipts),
            default=0,
        ),
    }
    violations: list[str] = []
    if totals["token_used"] > total.token_limit:
        violations.append("TOTAL_TOKEN_BUDGET_EXCEEDED")
    if totals["money_microunits_used"] > total.money_microunits_limit:
        violations.append("TOTAL_MONEY_BUDGET_EXCEEDED")
    if totals["calls_attempted"] > total.tool_call_limit:
        violations.append("TOTAL_TOOL_CALL_BUDGET_EXCEEDED")
    if totals["critical_path_latency_ms"] > total.latency_ms_limit:
        violations.append("TOTAL_LATENCY_BUDGET_EXCEEDED")
    for row in receipts:
        if row.get("reused_from_seat_ids"):
            violations.append(f"CROSS_SEAT_REUSE:{row.get('seat_id')}")
        if row.get("side_effect_class") != "READ_ONLY":
            violations.append(f"NON_READ_ONLY:{row.get('seat_id')}")
    audit = {
        "schema": SCHEMA_VERSION,
        "council_id": council_id,
        "plan_freeze_hash": v3.get("plan_freeze_hash"),
        "all_plans_frozen_before_commit": True,
        "all_evidence_acquired_before_commit": True,
        "cross_seat_budget_transfer_authorized": False,
        "cross_seat_result_reuse_before_reveal_authorized": False,
        "totals": totals,
        "overlap": evidence_overlap_matrix(root, council_id),
        "violations": sorted(set(violations)),
        "authority": "EVIDENCE_ACQUISITION_ONLY",
        "domain_clearance_authorized": False,
        "created_at": utcnow(),
    }
    audit["audit_hash"] = digest(audit)
    return audit


def finalize_v3(
    root: Path,
    council_id: str,
    obligation_id: str,
    *,
    synthesis_hash: str,
    supported_findings: list[str],
    unresolved: list[str] | None = None,
    direct_control_receipt: str | None = None,
    vote_control_receipt: str | None = None,
) -> Receipt:
    """Bind the v3 evidence audit into the ordinary REVIEW-only Council receipt."""
    v3 = _v3_row(root, council_id)
    if v3.get("phase") != "COMMITTED":
        raise ValueError("Council v3 requires all seat commits before finalization")
    audit = _audit(root, council_id)
    missing = list(unresolved or [])
    missing.extend(f"council-v3-evidence:{item}" for item in audit["violations"])
    bound_synthesis_hash = digest(
        {
            "council_synthesis_hash": synthesis_hash,
            "council_v3_evidence_audit_hash": audit["audit_hash"],
        }
    )
    receipt = council.finalize(
        root,
        council_id,
        obligation_id,
        synthesis_hash=bound_synthesis_hash,
        supported_findings=supported_findings,
        unresolved=missing,
        direct_control_receipt=direct_control_receipt,
        vote_control_receipt=vote_control_receipt,
    )
    v3 = _v3_row(root, council_id)
    audit["review_receipt_id"] = receipt.receipt_id
    v3["audit"] = audit
    v3["phase"] = "CLOSED"
    _write_v3(root, council_id, v3)
    return receipt
