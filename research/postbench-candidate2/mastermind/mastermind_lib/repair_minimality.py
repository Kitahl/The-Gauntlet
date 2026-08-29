from __future__ import annotations

"""Exact bounded repair-minimality over a frozen finite edit universe.

This is PRE_REVIEW_ONLY.  "Global" means exhaustive over every edit combination
in the content-bound finite search space under the declared edit-count cap.  It
never implies global minimality outside that universe.
"""

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping, Sequence

from .intervention_boundary import (
    AUTHORITY,
    FailureGraph,
    InterventionPlan,
    InterventionPolicy,
    TypedEdit,
    ValidationStatus,
    build_intervention_plan,
    canonical_sha256,
    validate_intervention_plan,
)

SUCCESS = "SUCCESS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
OUTCOMES = {SUCCESS, FAIL, UNKNOWN}

EXHAUSTIVE_MINIMUM_PASS = "EXHAUSTIVE_MINIMUM_PASS"
EXHAUSTIVE_MINIMUM_FAIL = "EXHAUSTIVE_MINIMUM_FAIL"
EXHAUSTIVE_MINIMUM_UNKNOWN = "EXHAUSTIVE_MINIMUM_UNKNOWN"


def _hex64(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class RepairSearchSpace:
    failure_graph_id: str
    frozen_target_sha256: str
    primitive_edit_ids: tuple[str, ...]
    max_edit_count: int
    discriminating_probe_ids: tuple[str, ...]
    plan_ids: tuple[str, ...]
    search_space_id: str = ""

    def bound(self) -> "RepairSearchSpace":
        if not _hex64(self.failure_graph_id) or not _hex64(self.frozen_target_sha256):
            raise ValueError("REPAIR_SEARCH_SPACE_BINDING_INVALID")
        edits = tuple(sorted(set(self.primitive_edit_ids)))
        probes = tuple(sorted(set(self.discriminating_probe_ids)))
        plans = tuple(sorted(set(self.plan_ids)))
        if not edits or not probes or not plans:
            raise ValueError("REPAIR_SEARCH_SPACE_EMPTY")
        if self.max_edit_count < 1 or self.max_edit_count > len(edits):
            raise ValueError("REPAIR_SEARCH_SPACE_EDIT_CAP_INVALID")
        if not all(_hex64(value) for value in plans):
            raise ValueError("REPAIR_SEARCH_SPACE_PLAN_ID_INVALID")
        core = {
            "failure_graph_id": self.failure_graph_id,
            "frozen_target_sha256": self.frozen_target_sha256,
            "primitive_edit_ids": edits,
            "max_edit_count": int(self.max_edit_count),
            "discriminating_probe_ids": probes,
            "plan_ids": plans,
            "authority": AUTHORITY,
        }
        return RepairSearchSpace(**{k: v for k, v in core.items() if k != "authority"}, search_space_id=canonical_sha256(core))


@dataclass(frozen=True)
class RepairOutcome:
    search_space_id: str
    plan_id: str
    status: str
    executor_id: str
    verifier_id: str
    evidence_digests: tuple[str, ...]
    outcome_id: str = ""

    def bound(self) -> "RepairOutcome":
        if not _hex64(self.search_space_id) or not _hex64(self.plan_id):
            raise ValueError("REPAIR_OUTCOME_BINDING_INVALID")
        if self.status not in OUTCOMES:
            raise ValueError("REPAIR_OUTCOME_STATUS_INVALID")
        if not self.executor_id.strip() or not self.verifier_id.strip() or self.executor_id == self.verifier_id:
            raise ValueError("REPAIR_OUTCOME_INDEPENDENT_IDENTITIES_REQUIRED")
        evidence = tuple(sorted(set(self.evidence_digests)))
        if not evidence or not all(_hex64(value) for value in evidence):
            raise ValueError("REPAIR_OUTCOME_EVIDENCE_INVALID")
        core = {
            "search_space_id": self.search_space_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "executor_id": self.executor_id,
            "verifier_id": self.verifier_id,
            "evidence_digests": evidence,
            "authority": AUTHORITY,
            "promotion_authority": "NONE",
        }
        return RepairOutcome(
            self.search_space_id,
            self.plan_id,
            self.status,
            self.executor_id,
            self.verifier_id,
            evidence,
            canonical_sha256(core),
        )


def enumerate_repair_search_space(
    *,
    graph: FailureGraph,
    primitive_edits: Sequence[TypedEdit],
    discriminating_probe_ids: Sequence[str],
    max_edit_count: int,
    max_primitive_edits: int = 12,
) -> tuple[RepairSearchSpace, tuple[InterventionPlan, ...]]:
    edits = tuple(sorted((edit.normalized() for edit in primitive_edits), key=lambda row: row.edit_id))
    if not edits or len(edits) > max_primitive_edits:
        raise ValueError("REPAIR_PRIMITIVE_EDIT_UNIVERSE_LIMIT_EXCEEDED")
    if len({edit.edit_id for edit in edits}) != len(edits):
        raise ValueError("REPAIR_PRIMITIVE_EDIT_ID_DUPLICATE")
    cap = int(max_edit_count)
    if cap < 1 or cap > len(edits):
        raise ValueError("REPAIR_EDIT_COUNT_CAP_INVALID")
    probes = tuple(sorted({str(value).strip() for value in discriminating_probe_ids if str(value).strip()}))
    if not probes:
        raise ValueError("REPAIR_SEARCH_SPACE_PROBES_REQUIRED")
    plans: list[InterventionPlan] = []
    for size in range(1, cap + 1):
        for combo in combinations(edits, size):
            plans.append(build_intervention_plan(
                graph=graph,
                edits=combo,
                discriminating_probe_ids=probes,
                rationale="EXHAUSTIVE_FINITE_REPAIR_UNIVERSE",
            ))
    space = RepairSearchSpace(
        failure_graph_id=graph.graph_id,
        frozen_target_sha256=graph.frozen_target_sha256,
        primitive_edit_ids=tuple(edit.edit_id for edit in edits),
        max_edit_count=cap,
        discriminating_probe_ids=probes,
        plan_ids=tuple(plan.plan_id for plan in plans),
    ).bound()
    return space, tuple(plans)


def select_exhaustive_minimum_successful_repair(
    *,
    search_space: RepairSearchSpace,
    graph: FailureGraph,
    plans: Sequence[InterventionPlan],
    policy: InterventionPolicy,
    known_obligation_ids: Sequence[str],
    current_span_hashes: Mapping[str, str],
    required_obligation_ids: Sequence[str],
    outcomes: Sequence[RepairOutcome],
) -> dict[str, Any]:
    failures: list[str] = []
    if search_space != search_space.bound():
        failures.append("REPAIR_SEARCH_SPACE_NOT_CONTENT_BOUND")
    plan_map = {plan.plan_id: plan for plan in plans}
    if set(plan_map) != set(search_space.plan_ids):
        failures.append("REPAIR_SEARCH_SPACE_PLAN_COVERAGE_MISMATCH")
    if any(plan.failure_graph_id != graph.graph_id or plan.frozen_target_sha256 != graph.frozen_target_sha256 for plan in plans):
        failures.append("REPAIR_SEARCH_SPACE_SCOPE_MISMATCH")

    validation: dict[str, dict[str, Any]] = {}
    for plan in plans:
        validation[plan.plan_id] = validate_intervention_plan(
            plan,
            graph,
            policy,
            known_obligation_ids=known_obligation_ids,
            current_span_hashes=current_span_hashes,
            required_obligation_ids=required_obligation_ids,
        )
    valid_ids = {plan_id for plan_id, row in validation.items() if row.get("status") == ValidationStatus.PASS.value}

    outcome_map: dict[str, RepairOutcome] = {}
    for raw in outcomes:
        try:
            row = raw.bound()
        except ValueError as exc:
            failures.append(f"INVALID_REPAIR_OUTCOME:{exc}")
            continue
        if row.search_space_id != search_space.search_space_id:
            failures.append(f"REPAIR_OUTCOME_SEARCH_SPACE_MISMATCH:{row.plan_id}")
            continue
        if row.plan_id in outcome_map:
            failures.append(f"DUPLICATE_REPAIR_OUTCOME:{row.plan_id}")
            continue
        outcome_map[row.plan_id] = row

    if set(outcome_map) != valid_ids:
        failures.append(f"EXHAUSTIVE_VALID_PLAN_OUTCOME_COVERAGE_MISMATCH:expected={len(valid_ids)}:observed={len(outcome_map)}")

    unknown_ids = sorted(plan_id for plan_id, row in outcome_map.items() if row.status == UNKNOWN)
    successful = []
    for plan_id, row in outcome_map.items():
        if row.status != SUCCESS:
            continue
        receipt = validation[plan_id]
        key = (
            int(receipt.get("semantic_delta_units", 10**18)),
            int(receipt.get("touched_lines", 10**18)),
            int(receipt.get("edit_count", 10**18)),
            plan_id,
        )
        successful.append((key, plan_id))

    if failures or unknown_ids:
        status = EXHAUSTIVE_MINIMUM_UNKNOWN
        selected = None
        if unknown_ids:
            failures.append("EXHAUSTIVE_REPAIR_OUTCOME_CONTAINS_UNKNOWN:" + ",".join(unknown_ids))
    elif not successful:
        status = EXHAUSTIVE_MINIMUM_FAIL
        selected = None
        failures.append("NO_SUCCESSFUL_REPAIR_IN_FROZEN_UNIVERSE")
    else:
        status = EXHAUSTIVE_MINIMUM_PASS
        selected = min(successful)[1]

    result = {
        "schema": "mastermind/exhaustive-repair-minimality/1",
        "status": status,
        "search_space_id": search_space.search_space_id,
        "enumerated_plan_count": len(search_space.plan_ids),
        "valid_plan_count": len(valid_ids),
        "successful_plan_count": len(successful),
        "selected_plan_id": selected,
        "ranking": [
            {"plan_id": plan_id, "semantic_delta_units": key[0], "touched_lines": key[1], "edit_count": key[2]}
            for key, plan_id in sorted(successful)
        ],
        "failures": sorted(set(failures)),
        "minimality_scope": "global only within the exhaustive frozen primitive-edit universe and edit-count cap; no unbounded/global repair claim",
        "authority": AUTHORITY,
        "promotion_authority": "NONE",
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
