"""Automatic-first Process Assurance controller.

The low-level :mod:`gauntlet_runtime` registry and typed monitors remain the factual
mechanism. This controller preserves automatic full applicable coverage and adds an
opt-in evidence-context gate without reinterpreting historical ``egrt.runtime.v1``
receipts. Selective or early-stop execution remains explicitly experimental.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import gauntlet_runtime as low_level
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest
from gauntlet_evidence_context import (
    EVIDENCE_CONTEXT_SCHEMA,
    TaskEvidenceContextAssessment,
    assess_task_evidence_context,
)

AUTOMATIC_ASSURANCE_SCHEMA = "egrt.gauntlet.automatic.v1"
_POLICY_MODES = {
    "AUTOMATIC_FULL",
    "DIAGNOSTIC_FULL",
    "SELECTIVE_EXPERIMENTAL",
    "FAST_BLOCK_EXPERIMENTAL",
}
_SEVERITY = {
    Verdict.CLEARED: 0,
    Verdict.UNKNOWN: 1,
    Verdict.UNAVAILABLE: 2,
    Verdict.ISSUE: 3,
}


@dataclass(frozen=True)
class AutomaticAssurancePolicy:
    """Frozen automatic-assurance policy.

    ``AUTOMATIC_FULL`` is the production default. Structural budgets are advisory in
    full modes so they cannot reduce release coverage. They become hard limits only in
    explicitly experimental selective modes.
    """

    mode: str = "AUTOMATIC_FULL"
    max_cost_units: int | None = None
    max_operations: int | None = None
    stop_on_issue: bool = False

    def __post_init__(self) -> None:
        if self.mode not in _POLICY_MODES:
            raise ValueError(f"mode must be one of {sorted(_POLICY_MODES)}")
        for name in ("max_cost_units", "max_operations"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative int or None")
        if not isinstance(self.stop_on_issue, bool):
            raise TypeError("stop_on_issue must be bool")
        if self.mode in {"AUTOMATIC_FULL", "DIAGNOSTIC_FULL"} and self.stop_on_issue:
            raise ValueError("full automatic modes do not stop after the first issue")


@dataclass(frozen=True)
class AutomaticAssurancePlan:
    task_id: str | None
    obligation_id: str
    policy: AutomaticAssurancePolicy
    input_hash: str
    applicable_operations: tuple[str, ...]
    selected_operations: tuple[str, ...]
    deferred_operations: tuple[tuple[str, str], ...]
    triggered_operations: tuple[str, ...]
    planned_cost_units: int
    registry_cost_units: int
    advisory_budget_exceeded: bool
    runtime_event_coverage_status: str
    runtime_event_coverage_gaps: tuple[str, ...]
    coverage_scope: str
    selection_certificate_hash: str
    plan_hash: str
    schema: str = AUTOMATIC_ASSURANCE_SCHEMA


def _event_types(events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(event.get("event_type") or "") for event in events]


def _receipt_order(row: Mapping[str, Any]) -> tuple[int, int, str]:
    """Prefer the monotonic store sequence over caller-controlled wall-clock text."""

    sequence = row.get("seq")
    stamp = str(
        row.get("stored_at")
        or row.get("finished_at")
        or row.get("started_at")
        or ""
    )
    if isinstance(sequence, int) and not isinstance(sequence, bool):
        return 1, sequence, stamp
    return 0, 0, stamp


def _ordered_receipts(
    receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [dict(receipt) for receipt in receipts]
    rows.sort(key=_receipt_order)
    return rows


def _is_applicable(
    operation: str,
    events: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
) -> bool:
    types = _event_types(events)
    if operation == "frame":
        return types.count("action.failed") >= 3
    if operation == "audit":
        return "release.attempted" in types
    if operation == "costume":
        return "novelty.claim" in types
    if operation == "derive":
        return any(
            event.get("event_type") == "claim.adopted"
            and bool(event.get("metadata", {}).get("inherited"))
            for event in events
        )
    if operation == "self":
        return (
            "release.attempted" in types
            or "evidence.attached" in types
            or any(bool(receipt.get("evidence")) for receipt in receipts)
        )
    if operation == "redirect":
        return types.count("action.attempted") >= 3
    if operation == "refresh":
        return bool(
            {"release.attempted", "authority.snapshot", "authority.changed"}
            & set(types)
        )
    if operation == "boundary":
        return "handoff.started" in types
    if operation == "explain":
        return "explanation.claim" in types
    if operation == "oob":
        return "release.attempted" in types
    return False


def _operation_order(operation: str) -> tuple[int, int, int, str]:
    spec = low_level.OPERATIONS[operation]
    return (-spec.risk_rank, -spec.information_rank, spec.cost_units, operation)


def _runtime_event_coverage(
    events: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
) -> tuple[str, tuple[str, ...]]:
    """Check the RuntimeStore event chain used by the typed monitors.

    This is not a proof that the external world emitted every event it should have.
    It detects internal omissions or content-binding substitutions between persisted
    receipts and their corresponding typed events, so a damaged event chain cannot be
    treated as green.
    """

    gaps: list[str] = []
    event_ids: set[str] = set()
    for event in events:
        event_id = event.get("event_id")
        event_type = event.get("event_type")
        content_hash = event.get("content_hash")
        if not isinstance(event_id, str) or not event_id:
            gaps.append("event-missing-id")
        elif event_id in event_ids:
            gaps.append(f"duplicate-event-id:{event_id}")
        else:
            event_ids.add(event_id)
        if not isinstance(event_type, str) or not event_type:
            gaps.append(f"event-missing-type:{event_id or 'unknown'}")
        if not isinstance(content_hash, str) or not content_hash:
            gaps.append(f"event-missing-content-hash:{event_id or 'unknown'}")

    actual_receipt_events: Counter[tuple[str, str]] = Counter()
    actual_state_events: Counter[tuple[str, str, str]] = Counter()
    actual_evidence_events: Counter[tuple[str, str]] = Counter()
    for event in events:
        metadata = event.get("metadata", {})
        metadata = metadata if isinstance(metadata, Mapping) else {}
        event_type = event.get("event_type")
        payload_hash = str(event.get("payload_hash") or "")
        if event_type == "receipt.written":
            actual_receipt_events[
                (str(metadata.get("receipt_id") or ""), payload_hash)
            ] += 1
        elif event_type == "obligation.state":
            actual_state_events[
                (
                    str(metadata.get("obligation_id") or ""),
                    str(metadata.get("state") or ""),
                    payload_hash,
                )
            ] += 1
        elif event_type == "evidence.attached":
            actual_evidence_events[
                (str(metadata.get("obligation_id") or ""), payload_hash)
            ] += 1

    required_receipt_events: Counter[tuple[str, str]] = Counter()
    required_state_events: Counter[tuple[str, str, str]] = Counter()
    required_evidence_events: Counter[tuple[str, str]] = Counter()
    for receipt in receipts:
        receipt_id = str(receipt.get("receipt_id") or "")
        receipt_hash = str(receipt.get("content_hash") or "")
        obligation_id = str(receipt.get("obligation_id") or "")
        verdict = str(receipt.get("verdict") or "")
        required_receipt_events[(receipt_id, receipt_hash)] += 1
        required_state_events[(obligation_id, verdict, receipt_hash)] += 1
        for evidence in receipt.get("evidence", []):
            if isinstance(evidence, Mapping):
                required_evidence_events[(obligation_id, digest(evidence))] += 1

    for key, required in required_receipt_events.items():
        if actual_receipt_events[key] < required:
            gaps.append(f"receipt-event-missing-or-unbound:{key[0] or 'unknown'}")
    for key, required in required_state_events.items():
        if actual_state_events[key] < required:
            gaps.append(
                f"obligation-state-event-missing-or-unbound:{key[0] or 'unknown'}"
            )
    for key, required in required_evidence_events.items():
        if actual_evidence_events[key] < required:
            gaps.append(f"evidence-event-missing-or-unbound:{key[0] or 'unknown'}")

    unique = tuple(sorted(set(gaps)))
    if unique:
        return "UNKNOWN_RUNTIME_EVENT_CHAIN", unique
    return "ESTABLISHED_RUNTIME_EVENT_CHAIN", ()


def _latest_receipt(
    receipts: Sequence[Mapping[str, Any]],
    obligation_id: str,
    *,
    module: str | None,
    task_id: str | None,
) -> Mapping[str, Any] | None:
    rows = [
        receipt
        for receipt in receipts
        if receipt.get("obligation_id") == obligation_id
        and (module is None or receipt.get("module") == module)
        and (task_id is None or receipt.get("task_id") == task_id)
    ]
    return rows[-1] if rows else None


def _current_receipt_self_check(
    task: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]],
    *,
    task_id: str | None,
    assurance_obligation_id: str,
) -> tuple[Verdict, str]:
    """Bind independence checks to every current load-bearing domain receipt."""

    if task is None:
        return Verdict.UNKNOWN, "bound task is unavailable for current-receipt provenance"
    observed = 0
    for obligation in task.get("obligations", []):
        if not isinstance(obligation, Mapping) or not obligation.get("load_bearing", True):
            continue
        obligation_id = str(obligation.get("obligation_id") or "")
        if not obligation_id or obligation_id == assurance_obligation_id:
            continue
        receipt = _latest_receipt(
            receipts,
            obligation_id,
            module=(
                str(obligation.get("required_module"))
                if obligation.get("required_module")
                else None
            ),
            task_id=task_id,
        )
        if receipt is None:
            continue
        observed += 1
        evidence_rows = [
            evidence
            for evidence in receipt.get("evidence", [])
            if isinstance(evidence, Mapping)
        ]
        if not evidence_rows:
            return (
                Verdict.UNKNOWN,
                f"current load-bearing receipt {receipt.get('receipt_id')} lacks an evidence envelope",
            )
        producer = str(receipt.get("module") or "")
        for evidence in evidence_rows:
            metadata = evidence.get("metadata", {})
            metadata = metadata if isinstance(metadata, Mapping) else {}
            verifier = str(evidence.get("verifier") or receipt.get("verifier") or "")
            if not producer or not verifier:
                return Verdict.UNKNOWN, "current receipt evidence lacks producer or verifier identity"
            if producer == verifier:
                return Verdict.ISSUE, "current receipt producer and verifier are identical"
            producer_provenance = metadata.get("producer_provenance")
            verifier_provenance = (
                evidence.get("provenance_group")
                or metadata.get("verifier_provenance")
            )
            if not producer_provenance or not verifier_provenance:
                return Verdict.UNKNOWN, "current receipt evidence lacks independence provenance"
            if producer_provenance == verifier_provenance:
                return Verdict.UNKNOWN, "current receipt producer and verifier share provenance"
    if observed == 0:
        return Verdict.UNKNOWN, "no current load-bearing domain receipt is observable"
    return Verdict.CLEARED, "current load-bearing receipts have distinct bound evidence provenance"


def _worse(
    left: tuple[Verdict, str],
    right: tuple[Verdict, str],
) -> tuple[Verdict, str]:
    left_severity = _SEVERITY[left[0]]
    right_severity = _SEVERITY[right[0]]
    if right_severity > left_severity:
        return right
    # At equal non-green severity prefer the later, more task-specific discriminator.
    if right_severity == left_severity and right[0] != Verdict.CLEARED:
        return right
    return left


def _monitor_operation(
    operation: str,
    events: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    task: Mapping[str, Any] | None,
    task_id: str | None,
    assurance_obligation_id: str,
    evidence_context: TaskEvidenceContextAssessment | None = None,
) -> tuple[Verdict, str]:
    low_level_result = low_level.monitor_structured(
        operation,
        events,
        receipts,
        task=task,
        task_id=task_id,
        assurance_obligation_id=assurance_obligation_id,
    )
    if operation == "audit":
        context_result = evidence_context or assess_task_evidence_context(
            task,
            receipts,
            task_id=task_id,
            assurance_obligation_id=assurance_obligation_id,
        )
        return _worse(
            low_level_result,
            (context_result.verdict, context_result.summary),
        )
    if operation != "self":
        return low_level_result
    current_result = _current_receipt_self_check(
        task,
        receipts,
        task_id=task_id,
        assurance_obligation_id=assurance_obligation_id,
    )
    return _worse(low_level_result, current_result)


def _hard_selective_schedule(
    operations: Sequence[str],
    policy: AutomaticAssurancePolicy,
) -> tuple[list[str], list[tuple[str, str]]]:
    selected: list[str] = []
    deferred: list[tuple[str, str]] = []
    cost = 0
    for operation in operations:
        spec = low_level.OPERATIONS[operation]
        if policy.max_operations is not None and len(selected) >= policy.max_operations:
            deferred.append((operation, "MAX_OPERATIONS_EXPERIMENTAL"))
            continue
        if (
            policy.max_cost_units is not None
            and cost + spec.cost_units > policy.max_cost_units
        ):
            deferred.append((operation, "MAX_COST_UNITS_EXPERIMENTAL"))
            continue
        selected.append(operation)
        cost += spec.cost_units
    return selected, deferred


def _plan_from_snapshot(
    *,
    task_id: str | None,
    obligation_id: str,
    policy: AutomaticAssurancePolicy,
    task: Mapping[str, Any] | None,
    events: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> AutomaticAssurancePlan:
    applicable = tuple(
        sorted(
            (
                operation
                for operation in low_level.OPERATIONS
                if _is_applicable(operation, events, receipts)
            ),
            key=_operation_order,
        )
    )
    triggered = tuple(
        candidate.operation for candidate in low_level._triggered_candidates(events)
    )
    experimental = policy.mode in {
        "SELECTIVE_EXPERIMENTAL",
        "FAST_BLOCK_EXPERIMENTAL",
    }
    candidate_operations = (
        tuple(operation for operation in applicable if operation in set(triggered))
        if experimental
        else applicable
    )
    if experimental:
        selected, deferred = _hard_selective_schedule(candidate_operations, policy)
    else:
        selected = list(candidate_operations)
        deferred = []

    planned_cost = sum(low_level.OPERATIONS[name].cost_units for name in selected)
    advisory_exceeded = bool(
        not experimental
        and (
            (
                policy.max_cost_units is not None
                and planned_cost > policy.max_cost_units
            )
            or (
                policy.max_operations is not None
                and len(selected) > policy.max_operations
            )
        )
    )
    event_status, event_gaps = _runtime_event_coverage(events, receipts)
    input_hash = digest(
        {
            "task_id": task_id,
            "task_hash": task.get("content_hash") if task else None,
            "event_hashes": [row.get("content_hash") for row in events],
            "receipt_hashes": [row.get("content_hash") for row in receipts],
            "policy": asdict(policy),
        }
    )
    selection_certificate_hash = digest(
        {
            "rule": (
                "all_applicable_operations_in_full_modes;"
                "triggered_risk_ordered_budgeted_operations_in_explicit_experimental_modes"
            ),
            "applicable": applicable,
            "triggered": triggered,
            "selected": selected,
            "deferred": deferred,
            "policy": asdict(policy),
            "optimality_claimed": False,
            "coverage_reduction_authorized": experimental,
        }
    )
    payload = {
        "task_id": task_id,
        "obligation_id": obligation_id,
        "policy": asdict(policy),
        "input_hash": input_hash,
        "applicable": applicable,
        "triggered": triggered,
        "selected": selected,
        "deferred": deferred,
        "planned_cost_units": planned_cost,
        "registry_cost_units": sum(
            spec.cost_units for spec in low_level.OPERATIONS.values()
        ),
        "advisory_budget_exceeded": advisory_exceeded,
        "runtime_event_coverage_status": event_status,
        "runtime_event_coverage_gaps": event_gaps,
        "coverage_scope": "RUNTIME_STORE_REPRESENTED_HAZARDS",
        "selection_certificate_hash": selection_certificate_hash,
        "schema": AUTOMATIC_ASSURANCE_SCHEMA,
    }
    return AutomaticAssurancePlan(
        task_id=task_id,
        obligation_id=obligation_id,
        policy=policy,
        input_hash=input_hash,
        applicable_operations=applicable,
        selected_operations=tuple(selected),
        deferred_operations=tuple(deferred),
        triggered_operations=triggered,
        planned_cost_units=planned_cost,
        registry_cost_units=payload["registry_cost_units"],
        advisory_budget_exceeded=advisory_exceeded,
        runtime_event_coverage_status=event_status,
        runtime_event_coverage_gaps=event_gaps,
        coverage_scope=payload["coverage_scope"],
        selection_certificate_hash=selection_certificate_hash,
        plan_hash=digest(payload),
    )


def plan_automatic_assurance(
    root: Path,
    obligation_id: str,
    *,
    task_id: str | None = None,
    policy: AutomaticAssurancePolicy | None = None,
) -> AutomaticAssurancePlan:
    policy = policy or AutomaticAssurancePolicy()
    _, resolved, task, events, receipts = low_level._snapshot(
        root, obligation_id, task_id
    )
    receipts = _ordered_receipts(receipts)
    return _plan_from_snapshot(
        task_id=resolved,
        obligation_id=obligation_id,
        policy=policy,
        task=task,
        events=events,
        receipts=receipts,
    )


def _aggregate(
    results: Sequence[tuple[str, Verdict, str]],
    plan: AutomaticAssurancePlan,
) -> Verdict:
    verdicts = [verdict for _, verdict, _ in results]
    if Verdict.ISSUE in verdicts:
        return Verdict.ISSUE
    if Verdict.UNAVAILABLE in verdicts:
        return Verdict.UNAVAILABLE
    if (
        plan.runtime_event_coverage_status != "ESTABLISHED_RUNTIME_EVENT_CHAIN"
        or plan.deferred_operations
        or Verdict.UNKNOWN in verdicts
        or not results
    ):
        return Verdict.UNKNOWN
    return Verdict.CLEARED


def run_automatic_assurance(
    root: Path,
    obligation_id: str,
    *,
    task_id: str | None = None,
    policy: AutomaticAssurancePolicy | None = None,
) -> Receipt:
    """Run automatic assurance and emit one compact ``ASSURANCE_ONLY`` receipt."""

    policy = policy or AutomaticAssurancePolicy()
    store, resolved, task, events, receipts = low_level._snapshot(
        root, obligation_id, task_id
    )
    receipts = _ordered_receipts(receipts)
    plan = _plan_from_snapshot(
        task_id=resolved,
        obligation_id=obligation_id,
        policy=policy,
        task=task,
        events=events,
        receipts=receipts,
    )
    evidence_context = assess_task_evidence_context(
        task,
        receipts,
        task_id=resolved,
        assurance_obligation_id=obligation_id,
    )
    results: list[tuple[str, Verdict, str]] = []
    for operation in plan.selected_operations:
        verdict, reason = _monitor_operation(
            operation,
            events,
            receipts,
            task=task,
            task_id=resolved,
            assurance_obligation_id=obligation_id,
            evidence_context=evidence_context,
        )
        results.append((operation, verdict, reason))
        if (
            policy.mode == "FAST_BLOCK_EXPERIMENTAL"
            and policy.stop_on_issue
            and verdict == Verdict.ISSUE
        ):
            break

    verdict = _aggregate(results, plan)
    result_rows = [
        {"operation": name, "verdict": value.value, "reason": reason}
        for name, value, reason in results
    ]
    unresolved = [
        f"{name}:{reason}"
        for name, value, reason in results
        if value in {Verdict.UNKNOWN, Verdict.UNAVAILABLE}
    ]
    unresolved.extend(
        f"deferred:{name}:{reason}" for name, reason in plan.deferred_operations
    )
    unresolved.extend(
        f"event-chain:{gap}" for gap in plan.runtime_event_coverage_gaps
    )
    for row in evidence_context.rows:
        assessment = row.get("assessment", {})
        if assessment.get("verdict") == Verdict.CLEARED.value:
            continue
        for reason in assessment.get("reasons", []):
            unresolved.append(
                f"evidence-context:{row.get('obligation_id')}:{reason}"
            )
    metrics = {
        "registry_operation_count": len(low_level.OPERATIONS),
        "applicable_operation_count": len(plan.applicable_operations),
        "triggered_operation_count": len(plan.triggered_operations),
        "selected_operation_count": len(plan.selected_operations),
        "executed_operation_count": len(results),
        "planned_cost_units": plan.planned_cost_units,
        "registry_cost_units": plan.registry_cost_units,
        "advisory_budget_exceeded": plan.advisory_budget_exceeded,
        "evidence_context_obligation_count": len(evidence_context.rows),
        "semantic_tool_calls": 0,
        "cost_unit_status": "UNCALIBRATED_ORDERING_PROXY",
        "efficacy_status": "NOT_ESTABLISHED",
    }
    output = {
        "plan_hash": plan.plan_hash,
        "results": result_rows,
        "deferred_operations": list(plan.deferred_operations),
        "runtime_event_coverage_status": plan.runtime_event_coverage_status,
        "runtime_event_coverage_gaps": list(plan.runtime_event_coverage_gaps),
        "evidence_context": evidence_context.to_dict(),
        "metrics": metrics,
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="gauntlet",
        obligation_id=obligation_id,
        verdict=verdict,
        action=(
            "assure:automatic-full"
            if "FULL" in policy.mode
            else "assure:experimental-selective"
        ),
        input_hash=plan.input_hash,
        output_hash=digest(output),
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.DERIVED,
                verifier="gauntlet:automatic-controller",
                metadata={
                    "schema": AUTOMATIC_ASSURANCE_SCHEMA,
                    "plan_hash": plan.plan_hash,
                    "selection_certificate_hash": plan.selection_certificate_hash,
                    "coverage_scope": plan.coverage_scope,
                    "runtime_event_coverage_status": plan.runtime_event_coverage_status,
                    "selected_operations": list(plan.selected_operations),
                    "executed_operations": [row["operation"] for row in result_rows],
                    "deferred_operations": list(plan.deferred_operations),
                    "metrics": metrics,
                    "automatic": True,
                    "coverage_reduction_experimental": policy.mode.endswith(
                        "EXPERIMENTAL"
                    ),
                    "evidence_context_schema": EVIDENCE_CONTEXT_SCHEMA,
                    "evidence_context_status": evidence_context.status,
                    "evidence_context_verdict": evidence_context.verdict.value,
                    "evidence_context_rows": [
                        dict(row) for row in evidence_context.rows
                    ],
                    "authority": "ASSURANCE_ONLY",
                    "target_domain_clearance_authorized": False,
                },
            ),
        ),
        verifier="gauntlet:automatic-controller",
        tool_version="gauntlet-automatic-v1",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(unresolved),
        notes=json.dumps(
            {
                "boundary": (
                    "Automatic full mode preserves every currently applicable canonical "
                    "monitor. Evidence-context admission is opt-in and never replaces "
                    "claim-native verification. Coverage remains scoped to hazards "
                    "represented through the RuntimeStore event/task/receipt model."
                ),
                "evidence_context_status": evidence_context.status,
                "results": result_rows,
            },
            sort_keys=True,
        ),
        task_id=resolved,
    )
    store.write_receipt(receipt)
    return receipt


def assurance_obligation_id(root: Path, task_id: str) -> str | None:
    task = RuntimeStore(root).read_task(task_id)
    if task is None:
        return None
    for row in task.get("obligations", []):
        if (
            row.get("kind") == "ASSURANCE"
            and row.get("required_module") in (None, "gauntlet")
            and row.get("load_bearing", True)
        ):
            value = str(row.get("obligation_id") or "")
            return value or None
    return None


__all__ = [
    "AUTOMATIC_ASSURANCE_SCHEMA",
    "AutomaticAssurancePlan",
    "AutomaticAssurancePolicy",
    "assurance_obligation_id",
    "plan_automatic_assurance",
    "run_automatic_assurance",
]
