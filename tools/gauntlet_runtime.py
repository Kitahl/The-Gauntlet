"""Typed Process Assurance monitors with minimal, frozen hazard planning.

Gauntlet owns process assurance only. It inspects a frozen, task-scoped snapshot,
selects the smallest budget-feasible set of triggered hazard monitors, and can stop
a release-gate schedule as soon as a blocking issue is established. UNKNOWN and
UNAVAILABLE remain first-class outcomes; no Gauntlet receipt clears a domain claim.

The planner borrows general mechanisms without importing their runtimes:

* FOIL: task-local gaps, minimum discriminators, and conservative stand-down;
* Math Foundry: explicit route availability, AUTO scheduling, and complete cost units;
* Mastermind: frozen mechanisms, coverage/minimality certificates, negative controls,
  and no self-promotion.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    EvidenceClass,
    EvidenceRef,
    ObligationKind,
    Receipt,
    RuntimeEvent,
    SupportMode,
    Verdict,
    digest,
)

ASSURANCE_SCHEMA = "egrt.gauntlet.assurance.v1"
_POLICY_MODES = {"RELEASE_GATE", "DIAGNOSTIC"}


@dataclass(frozen=True)
class OperationSpec:
    name: str
    mode: SupportMode
    required_state: tuple[str, ...]
    limitation: str | None = None
    hazard_class: str = "PROCESS_HAZARD"
    cost_units: int = 1
    risk_rank: int = 1
    information_rank: int = 1
    required_capability: str | None = None

    def __post_init__(self) -> None:
        if self.cost_units < 1:
            raise ValueError("operation cost_units must be positive")
        if not 1 <= self.risk_rank <= 5:
            raise ValueError("operation risk_rank must be between 1 and 5")
        if not 1 <= self.information_rank <= 5:
            raise ValueError("operation information_rank must be between 1 and 5")


OPERATIONS = {
    "frame": OperationSpec(
        "frame",
        SupportMode.AUTOMATIC,
        ("action.failed", "action.attempted"),
        "typed failures cover only represented failure signatures; free-text framing remains assisted",
        "REPEATED_FAILURE_FRAME",
        1,
        4,
        4,
        "STRUCTURAL_COMPARISON",
    ),
    "audit": OperationSpec(
        "audit",
        SupportMode.AUTOMATIC,
        ("release.attempted", "obligation.state"),
        "valid receipts establish recorded obligation state, not semantic truth",
        "PREMATURE_RELEASE",
        1,
        5,
        5,
    ),
    "costume": OperationSpec(
        "costume",
        SupportMode.ASSISTED,
        ("novelty.claim", "receipt.written"),
        "typed novelty claims can be checked against source-assessed Space receipts; global novelty cannot be proven",
        "NOVELTY_COSTUME",
        2,
        3,
        4,
        "SCHOLARLY_SEARCH",
    ),
    "derive": OperationSpec(
        "derive",
        SupportMode.AUTOMATIC,
        ("claim.adopted", "receipt.written"),
        "requires an explicitly typed inherited claim and task-scoped Mind receipt",
        "INHERITED_VALUE_WITHOUT_DERIVATION",
        1,
        5,
        5,
        "FORMAL_DERIVATION",
    ),
    "self": OperationSpec(
        "self",
        SupportMode.AUTOMATIC,
        ("evidence.attached",),
        "missing producer/verifier provenance cannot establish independence",
        "SELF_VERIFICATION",
        1,
        5,
        5,
        "PROVENANCE_CHECK",
    ),
    "redirect": OperationSpec(
        "redirect",
        SupportMode.AUTOMATIC,
        ("action.attempted",),
        "requires stable caller-supplied blocker_hash and progress_hash",
        "STAGNANT_WORK",
        1,
        3,
        4,
        "STATE_COMPARISON",
    ),
    "refresh": OperationSpec(
        "refresh",
        SupportMode.AUTOMATIC,
        ("authority.snapshot", "authority.changed"),
        "only registered governing authorities are observable",
        "STALE_AUTHORITY",
        1,
        5,
        5,
        "REPOSITORY_STATE",
    ),
    "boundary": OperationSpec(
        "boundary",
        SupportMode.AUTOMATIC,
        ("handoff.started", "contract.bound"),
        "only typed handoffs with content-bound contracts are observable",
        "UNBOUND_HANDOFF",
        1,
        4,
        4,
        "CONTRACT_CHECK",
    ),
    "explain": OperationSpec(
        "explain",
        SupportMode.ASSISTED,
        ("explanation.claim", "artifact.claim"),
        "typed claim hashes are mechanically comparable; free-text entailment remains assisted",
        "EXPLANATION_ARTIFACT_DRIFT",
        2,
        3,
        4,
        "SEMANTIC_COMPARISON",
    ),
    "oob": OperationSpec(
        "oob",
        SupportMode.AUTOMATIC,
        ("release.attempted", "coverage.probe"),
        "a valid named probe covers only its bound failure class and scope",
        "UNCOVERED_FAILURE_CLASS",
        1,
        4,
        4,
        "ADVERSARIAL_PROBE",
    ),
}


@dataclass(frozen=True)
class AssurancePolicy:
    """Caller-frozen budget and stopping policy for one assurance run."""

    mode: str = "RELEASE_GATE"
    max_cost_units: int = 8
    max_operations: int = 6
    stop_on_issue: bool = True

    def __post_init__(self) -> None:
        if self.mode not in _POLICY_MODES:
            raise ValueError(f"mode must be one of {sorted(_POLICY_MODES)}")
        if not isinstance(self.max_cost_units, int) or isinstance(self.max_cost_units, bool):
            raise TypeError("max_cost_units must be int")
        if not isinstance(self.max_operations, int) or isinstance(self.max_operations, bool):
            raise TypeError("max_operations must be int")
        if self.max_cost_units < 0 or self.max_operations < 0:
            raise ValueError("assurance budgets must be non-negative")
        if not isinstance(self.stop_on_issue, bool):
            raise TypeError("stop_on_issue must be bool")


@dataclass(frozen=True)
class HazardCandidate:
    operation: str
    hazard_class: str
    trigger_event_ids: tuple[str, ...]
    reason_code: str
    cost_units: int
    risk_rank: int
    information_rank: int
    required_capability: str | None


@dataclass(frozen=True)
class AssurancePlan:
    task_id: str | None
    obligation_id: str
    policy: AssurancePolicy
    input_hash: str
    candidates: tuple[HazardCandidate, ...]
    selected_operations: tuple[str, ...]
    excluded_operations: tuple[tuple[str, str], ...]
    planned_cost_units: int
    registry_cost_units: int
    coverage_certificate_hash: str
    minimality_certificate_hash: str
    plan_hash: str
    schema: str = ASSURANCE_SCHEMA


class GauntletAuthorityError(ValueError):
    """Raised when Process Assurance is asked to clear a non-ASSURANCE obligation."""


def coverage_registry() -> list[dict[str, Any]]:
    return [
        {
            "operation": op.name,
            "mode": op.mode.value,
            "required_state": list(op.required_state),
            "limitation": op.limitation,
            "hazard_class": op.hazard_class,
            "cost_units": op.cost_units,
            "risk_rank": op.risk_rank,
            "information_rank": op.information_rank,
            "required_capability": op.required_capability,
        }
        for op in OPERATIONS.values()
    ]


def _event_ids(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(
        str(row.get("event_id"))
        for row in rows
        if isinstance(row.get("event_id"), str) and row.get("event_id")
    )


def _latest_obligation_states(events: list[dict[str, Any]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for event in events:
        if event.get("event_type") != "obligation.state":
            continue
        metadata = event.get("metadata", {})
        obligation_id = metadata.get("obligation_id")
        state = metadata.get("state")
        if obligation_id and state:
            latest[str(obligation_id)] = str(state)
    return latest


def _latest_receipt(
    receipts: Sequence[Mapping[str, Any]],
    obligation_id: str,
    *,
    module: str | None = None,
    task_id: str | None = None,
) -> Mapping[str, Any] | None:
    rows = [
        receipt
        for receipt in receipts
        if receipt.get("obligation_id") == obligation_id
        and (module is None or receipt.get("module") == module)
        and (task_id is None or receipt.get("task_id") == task_id)
    ]
    return rows[-1] if rows else None


def _task_audit(
    task: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    *,
    task_id: str | None,
    assurance_obligation_id: str | None,
) -> tuple[Verdict, str]:
    unresolved: list[str] = []
    for obligation in task.get("obligations", []):
        if not isinstance(obligation, dict) or not obligation.get("load_bearing", True):
            continue
        obligation_id = str(obligation.get("obligation_id") or "")
        if not obligation_id or obligation_id == assurance_obligation_id:
            continue
        expected = obligation.get("required_module")
        current = _latest_receipt(
            receipts,
            obligation_id,
            module=str(expected) if expected else None,
            task_id=task_id,
        )
        if current is None:
            unresolved.append(f"{obligation_id}:MISSING")
            continue
        try:
            verdict = Verdict(str(current.get("verdict")))
        except ValueError:
            verdict = Verdict.UNKNOWN
        if verdict != Verdict.CLEARED:
            unresolved.append(f"{obligation_id}:{verdict.value}")
    if unresolved:
        return Verdict.ISSUE, f"release attempted with unresolved task obligations: {unresolved}"
    return Verdict.CLEARED, "current valid task-scoped load-bearing receipts are cleared"


def monitor_structured(
    operation: str,
    events: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    task: Mapping[str, Any] | None = None,
    task_id: str | None = None,
    assurance_obligation_id: str | None = None,
) -> tuple[Verdict, str]:
    """Evaluate one operation against an already-frozen, task-scoped snapshot."""
    if operation not in OPERATIONS:
        return Verdict.UNAVAILABLE, "unknown operation"
    spec = OPERATIONS[operation]
    types = [event.get("event_type") for event in events]

    if operation == "audit":
        if "release.attempted" not in types:
            return Verdict.UNKNOWN, "not-applicable: audit trigger absent: no release attempt"
        if task is not None:
            return _task_audit(
                task,
                receipts,
                task_id=task_id,
                assurance_obligation_id=assurance_obligation_id,
            )
        states = _latest_obligation_states(events)
        if not states:
            return Verdict.UNKNOWN, "release attempted but no typed obligation state is observable"
        unresolved = {
            obligation_id: state
            for obligation_id, state in states.items()
            if obligation_id != assurance_obligation_id and state != Verdict.CLEARED.value
        }
        if unresolved:
            return Verdict.ISSUE, f"release attempted with unresolved obligation states: {unresolved}"
        return Verdict.CLEARED, "current typed load-bearing obligation states are cleared"

    if operation == "derive":
        inherited = [
            event
            for event in events
            if event.get("event_type") == "claim.adopted"
            and event.get("metadata", {}).get("inherited")
        ]
        if not inherited:
            return Verdict.UNKNOWN, "not-applicable: derive trigger absent: no typed inherited claim"
        for event in inherited:
            obligation_id = event.get("metadata", {}).get("derivation_obligation")
            if not obligation_id:
                return Verdict.UNKNOWN, "inherited claim lacks a derivation_obligation binding"
            receipt = _latest_receipt(
                receipts,
                str(obligation_id),
                module="mind",
                task_id=task_id,
            )
            if receipt is None or receipt.get("verdict") != Verdict.CLEARED.value:
                return Verdict.ISSUE, "inherited claim lacks current task-scoped Mind derivation"
        return Verdict.CLEARED, "typed inherited claims have task-scoped derivation coverage"

    if operation == "self":
        evidence_events = [
            event for event in events if event.get("event_type") == "evidence.attached"
        ]
        if not evidence_events:
            if "release.attempted" in types:
                return Verdict.UNKNOWN, "release attempted without observable evidence provenance"
            return Verdict.UNKNOWN, "not-applicable: self trigger absent: no evidence attachment"
        missing_identity = False
        missing_provenance = False
        for event in evidence_events:
            metadata = event.get("metadata", {})
            producer = metadata.get("producer")
            verifier = metadata.get("verifier")
            if not producer or not verifier:
                missing_identity = True
                continue
            if producer == verifier:
                return Verdict.ISSUE, "producer and verifier are identical for typed evidence"
            producer_provenance = metadata.get("producer_provenance")
            verifier_provenance = metadata.get("verifier_provenance")
            if not producer_provenance or not verifier_provenance:
                missing_provenance = True
                continue
            if producer_provenance == verifier_provenance:
                return Verdict.UNKNOWN, "producer and verifier share provenance; independence is unresolved"
        if missing_identity:
            return Verdict.UNKNOWN, "evidence lacks producer or verifier identity"
        if missing_provenance:
            return Verdict.UNKNOWN, "evidence lacks provenance needed to assess independence"
        return Verdict.CLEARED, "no typed self-verification or provenance collision observed"

    if operation == "redirect":
        attempts = [
            event for event in events if event.get("event_type") == "action.attempted"
        ][-6:]
        if len(attempts) < 3:
            return Verdict.UNKNOWN, "not-applicable: redirect trigger absent: fewer than three attempts"
        recent = attempts[-3:]
        blockers = [event.get("metadata", {}).get("blocker_hash") for event in recent]
        progress = [event.get("metadata", {}).get("progress_hash") for event in recent]
        if any(value is None for value in blockers + progress):
            return Verdict.UNKNOWN, "recent attempts lack blocker_hash or progress_hash"
        if len(set(blockers)) == 1 and len(set(progress)) == 1:
            return Verdict.ISSUE, "three recent actions left blocker and progress unchanged"
        return Verdict.CLEARED, "recent typed attempts changed blocker or progress state"

    if operation == "boundary":
        handoffs = [event for event in events if event.get("event_type") == "handoff.started"]
        if not handoffs:
            return Verdict.UNKNOWN, "not-applicable: boundary trigger absent: no typed handoff"
        contracts: dict[str, Mapping[str, Any]] = {}
        for event in events:
            if event.get("event_type") != "contract.bound":
                continue
            metadata = event.get("metadata", {})
            handoff_id = metadata.get("handoff_id")
            if handoff_id:
                contracts[str(handoff_id)] = metadata
        for event in handoffs:
            metadata = event.get("metadata", {})
            handoff_id = metadata.get("handoff_id")
            if not handoff_id:
                return Verdict.ISSUE, "handoff lacks a non-empty handoff_id"
            contract = contracts.get(str(handoff_id))
            if contract is None:
                return Verdict.ISSUE, "handoff lacks a bound contract"
            contract_hash = contract.get("contract_hash")
            if not contract_hash:
                return Verdict.UNKNOWN, "bound handoff contract lacks a content hash"
            expected = metadata.get("expected_contract_hash")
            if expected and expected != contract_hash:
                return Verdict.ISSUE, "handoff expected_contract_hash mismatches bound contract"
        return Verdict.CLEARED, "typed handoffs have content-bound contracts"

    if operation == "oob":
        if "release.attempted" not in types:
            return Verdict.UNKNOWN, "not-applicable: oob trigger absent: no release attempt"
        probes = [event for event in events if event.get("event_type") == "coverage.probe"]
        if not probes:
            return Verdict.UNKNOWN, "release has no named out-of-band coverage probe"
        for event in probes:
            metadata = event.get("metadata", {})
            if not metadata.get("failure_class"):
                return Verdict.UNKNOWN, "coverage probe lacks a named failure_class"
            if metadata.get("status") not in {"VALID", "PASS", Verdict.CLEARED.value}:
                return Verdict.UNKNOWN, "coverage probe lacks a valid measured status"
            if not metadata.get("artifact_hash") or not metadata.get("scope_hash"):
                return Verdict.UNKNOWN, "coverage probe lacks artifact/scope binding"
            if not metadata.get("verifier"):
                return Verdict.UNKNOWN, "coverage probe lacks verifier identity"
        return Verdict.CLEARED, "valid bound out-of-band probe(s) cover named failure classes"

    if operation == "costume":
        novelty = [event for event in events if event.get("event_type") == "novelty.claim"]
        if not novelty:
            return Verdict.UNAVAILABLE, spec.limitation or "untyped novelty unavailable"
        for event in novelty:
            obligation_id = event.get("metadata", {}).get("discovery_obligation")
            if not obligation_id:
                return Verdict.UNKNOWN, "typed novelty claim lacks discovery_obligation binding"
            receipt = _latest_receipt(
                receipts,
                str(obligation_id),
                module="space",
                task_id=task_id,
            )
            if (
                receipt is None
                or receipt.get("verdict") != Verdict.CLEARED.value
                or receipt.get("action") != "source-assessment"
            ):
                return Verdict.ISSUE, "novelty claim lacks a valid source-assessed Space receipt"
        return Verdict.CLEARED, "typed novelty claims have source-assessed prior-art coverage"

    if operation == "explain":
        explanations = [
            event for event in events if event.get("event_type") == "explanation.claim"
        ]
        artifacts = [event for event in events if event.get("event_type") == "artifact.claim"]
        if not explanations:
            return Verdict.UNAVAILABLE, spec.limitation or "untyped explanation unavailable"
        by_id: dict[str, str] = {}
        for event in artifacts:
            metadata = event.get("metadata", {})
            claim_id = metadata.get("claim_id")
            claim_hash = metadata.get("claim_hash")
            if claim_id and claim_hash:
                by_id[str(claim_id)] = str(claim_hash)
        unresolved = False
        for event in explanations:
            metadata = event.get("metadata", {})
            claim_id = metadata.get("claim_id")
            claim_hash = metadata.get("claim_hash")
            if not claim_id or not claim_hash or str(claim_id) not in by_id:
                unresolved = True
                continue
            if str(claim_hash) != by_id[str(claim_id)]:
                return Verdict.ISSUE, "typed explanation claim contradicts artifact claim hash"
        if unresolved:
            return Verdict.UNKNOWN, "explanation lacks a fully hash-bound artifact counterpart"
        return Verdict.CLEARED, "typed explanation claims match artifact claim hashes"

    if operation == "refresh":
        authority_events = [
            event
            for event in events
            if event.get("event_type") in {"authority.snapshot", "authority.changed"}
        ]
        if not authority_events:
            return Verdict.UNKNOWN, "no registered authority snapshot is observable"
        latest = authority_events[-1]
        if latest.get("event_type") == "authority.changed":
            return Verdict.ISSUE, "registered authority changed; a fresh snapshot/re-read is required"
        return Verdict.CLEARED, "latest registered authority event is a fresh snapshot"

    if operation == "frame":
        failures = [event for event in events if event.get("event_type") == "action.failed"][-4:]
        if len(failures) < 3:
            return Verdict.UNKNOWN, "not-applicable: frame trigger absent: fewer than three failures"
        signatures = [event.get("metadata", {}).get("failure_signature") for event in failures[-3:]]
        if any(signature is None for signature in signatures):
            return Verdict.UNKNOWN, "recent failures lack failure_signature"
        if len(set(signatures)) == 1:
            return Verdict.ISSUE, "repeated typed failure signature requires reframing"
        return Verdict.CLEARED, "recent typed failures are structurally distinct"

    return Verdict.UNKNOWN, "monitor not implemented"


def _triggered_candidates(events: list[dict[str, Any]]) -> tuple[HazardCandidate, ...]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_type.setdefault(str(event.get("event_type") or ""), []).append(event)

    triggered: list[tuple[str, Sequence[Mapping[str, Any]], str]] = []
    if len(by_type.get("action.failed", [])) >= 3:
        triggered.append(("frame", by_type["action.failed"][-3:], "THREE_RECENT_FAILURES"))
    if by_type.get("release.attempted"):
        release = by_type["release.attempted"][-1:]
        triggered.extend(
            (
                ("audit", release, "RELEASE_ATTEMPT"),
                ("refresh", release, "RELEASE_REQUIRES_CURRENT_AUTHORITY"),
                ("oob", release, "RELEASE_REQUIRES_OOB_COVERAGE"),
            )
        )
    elif by_type.get("authority.changed"):
        triggered.append(
            ("refresh", by_type["authority.changed"][-1:], "AUTHORITY_CHANGED")
        )
    if by_type.get("novelty.claim"):
        triggered.append(("costume", by_type["novelty.claim"], "NOVELTY_CLAIM"))
    inherited = [
        event
        for event in by_type.get("claim.adopted", [])
        if event.get("metadata", {}).get("inherited")
    ]
    if inherited:
        triggered.append(("derive", inherited, "INHERITED_CLAIM"))
    if by_type.get("evidence.attached"):
        triggered.append(("self", by_type["evidence.attached"], "EVIDENCE_ATTACHED"))
    if len(by_type.get("action.attempted", [])) >= 3:
        triggered.append(
            ("redirect", by_type["action.attempted"][-3:], "THREE_RECENT_ATTEMPTS")
        )
    if by_type.get("handoff.started"):
        triggered.append(("boundary", by_type["handoff.started"], "HANDOFF_STARTED"))
    if by_type.get("explanation.claim"):
        triggered.append(
            ("explain", by_type["explanation.claim"], "EXPLANATION_CLAIM")
        )

    candidates: list[HazardCandidate] = []
    seen: set[str] = set()
    for operation, rows, reason_code in triggered:
        if operation in seen:
            continue
        seen.add(operation)
        spec = OPERATIONS[operation]
        candidates.append(
            HazardCandidate(
                operation=operation,
                hazard_class=spec.hazard_class,
                trigger_event_ids=_event_ids(rows),
                reason_code=reason_code,
                cost_units=spec.cost_units,
                risk_rank=spec.risk_rank,
                information_rank=spec.information_rank,
                required_capability=spec.required_capability,
            )
        )
    candidates.sort(
        key=lambda candidate: (
            -candidate.risk_rank,
            -candidate.information_rank,
            candidate.cost_units,
            candidate.operation,
        )
    )
    return tuple(candidates)


def _plan_from_snapshot(
    *,
    task_id: str | None,
    obligation_id: str,
    policy: AssurancePolicy,
    events: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    task: Mapping[str, Any] | None,
) -> AssurancePlan:
    input_hash = digest(
        {
            "task_id": task_id,
            "task_hash": task.get("content_hash") if task else None,
            "event_hashes": [event.get("content_hash") for event in events],
            "receipt_hashes": [receipt.get("content_hash") for receipt in receipts],
            "policy": asdict(policy),
        }
    )
    candidates = _triggered_candidates(events)
    selected: list[str] = []
    excluded: list[tuple[str, str]] = []
    used = 0
    for candidate in candidates:
        if len(selected) >= policy.max_operations:
            excluded.append((candidate.operation, "MAX_OPERATIONS"))
            continue
        if used + candidate.cost_units > policy.max_cost_units:
            excluded.append((candidate.operation, "MAX_COST_UNITS"))
            continue
        selected.append(candidate.operation)
        used += candidate.cost_units

    triggered_classes = [candidate.hazard_class for candidate in candidates]
    selected_classes = [OPERATIONS[operation].hazard_class for operation in selected]
    coverage_certificate_hash = digest(
        {
            "triggered_hazard_classes": triggered_classes,
            "selected_hazard_classes": selected_classes,
            "uncovered_hazard_classes": [
                OPERATIONS[operation].hazard_class for operation, _ in excluded
            ],
        }
    )
    minimality_certificate_hash = digest(
        {
            "selection_order": [candidate.operation for candidate in candidates],
            "selected_operations": selected,
            "excluded_operations": excluded,
            "policy": asdict(policy),
            "rule": "risk_desc_information_desc_cost_asc_name_asc_prefix_under_budget",
        }
    )
    payload = {
        "task_id": task_id,
        "obligation_id": obligation_id,
        "policy": asdict(policy),
        "input_hash": input_hash,
        "candidates": [asdict(candidate) for candidate in candidates],
        "selected_operations": selected,
        "excluded_operations": excluded,
        "planned_cost_units": used,
        "registry_cost_units": sum(spec.cost_units for spec in OPERATIONS.values()),
        "coverage_certificate_hash": coverage_certificate_hash,
        "minimality_certificate_hash": minimality_certificate_hash,
        "schema": ASSURANCE_SCHEMA,
    }
    return AssurancePlan(
        task_id=task_id,
        obligation_id=obligation_id,
        policy=policy,
        input_hash=input_hash,
        candidates=candidates,
        selected_operations=tuple(selected),
        excluded_operations=tuple(excluded),
        planned_cost_units=used,
        registry_cost_units=payload["registry_cost_units"],
        coverage_certificate_hash=coverage_certificate_hash,
        minimality_certificate_hash=minimality_certificate_hash,
        plan_hash=digest(payload),
    )


def _resolve_task(
    store: RuntimeStore,
    obligation_id: str,
    task_id: str | None,
) -> tuple[str | None, Mapping[str, Any] | None]:
    resolved = task_id or store.task_for_obligation(obligation_id)
    if resolved is None:
        return None, None
    task = store.read_task(resolved)
    if task is None:
        raise GauntletAuthorityError("bound task is missing or corrupt")
    return resolved, task


def _require_assurance_authority(
    task: Mapping[str, Any] | None,
    obligation_id: str,
) -> None:
    if task is None:
        return
    for obligation in task.get("obligations", []):
        if obligation.get("obligation_id") != obligation_id:
            continue
        if obligation.get("kind") != ObligationKind.ASSURANCE.value:
            raise GauntletAuthorityError("Gauntlet can clear only an ASSURANCE obligation")
        if obligation.get("required_module") not in (None, "gauntlet"):
            raise GauntletAuthorityError("ASSURANCE obligation is bound to another module")
        return
    raise GauntletAuthorityError("Gauntlet obligation is outside the bound task")


def _task_receipts(
    store: RuntimeStore,
    task_id: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(store.receipts.glob("*.json")):
        receipt = store.read_receipt(path.stem)
        if receipt is None:
            continue
        if task_id is None or receipt.get("task_id") == task_id:
            rows.append(receipt)
    rows.sort(
        key=lambda row: (
            str(row.get("stored_at") or row.get("finished_at") or ""),
            int(row.get("seq")) if isinstance(row.get("seq"), int) else -1,
        )
    )
    return rows


def _snapshot(
    root: Path,
    obligation_id: str,
    task_id: str | None,
) -> tuple[
    RuntimeStore,
    str | None,
    Mapping[str, Any] | None,
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    store = RuntimeStore(root)
    resolved_task_id, task = _resolve_task(store, obligation_id, task_id)
    _require_assurance_authority(task, obligation_id)
    events = store.iter_events(resolved_task_id)
    receipts = _task_receipts(store, resolved_task_id)
    return store, resolved_task_id, task, events, receipts


def plan_assurance(
    root: Path,
    obligation_id: str,
    *,
    task_id: str | None = None,
    policy: AssurancePolicy | None = None,
) -> AssurancePlan:
    """Create a deterministic plan from one task-scoped event/receipt snapshot."""
    policy = policy or AssurancePolicy()
    _, resolved, task, events, receipts = _snapshot(root, obligation_id, task_id)
    return _plan_from_snapshot(
        task_id=resolved,
        obligation_id=obligation_id,
        policy=policy,
        events=events,
        receipts=receipts,
        task=task,
    )


def _aggregate(
    results: Sequence[tuple[str, Verdict, str]],
    excluded: Sequence[tuple[str, str]],
) -> Verdict:
    verdicts = [verdict for _, verdict, _ in results]
    if Verdict.ISSUE in verdicts:
        return Verdict.ISSUE
    if excluded:
        return Verdict.UNKNOWN
    if Verdict.UNAVAILABLE in verdicts:
        return Verdict.UNAVAILABLE
    if Verdict.UNKNOWN in verdicts or not verdicts:
        return Verdict.UNKNOWN
    return Verdict.CLEARED


def run_assurance(
    root: Path,
    obligation_id: str,
    *,
    task_id: str | None = None,
    policy: AssurancePolicy | None = None,
) -> Receipt:
    """Run one frozen minimal assurance schedule and emit one compact receipt."""
    policy = policy or AssurancePolicy()
    store, resolved, task, events, receipts = _snapshot(root, obligation_id, task_id)
    plan = _plan_from_snapshot(
        task_id=resolved,
        obligation_id=obligation_id,
        policy=policy,
        events=events,
        receipts=receipts,
        task=task,
    )
    results: list[tuple[str, Verdict, str]] = []
    for operation in plan.selected_operations:
        verdict, reason = monitor_structured(
            operation,
            events,
            receipts,
            task=task,
            task_id=resolved,
            assurance_obligation_id=obligation_id,
        )
        results.append((operation, verdict, reason))
        if (
            policy.mode == "RELEASE_GATE"
            and policy.stop_on_issue
            and verdict == Verdict.ISSUE
        ):
            break

    verdict = _aggregate(results, plan.excluded_operations)
    unresolved = [
        f"{operation}:{reason}"
        for operation, result, reason in results
        if result in {Verdict.UNKNOWN, Verdict.UNAVAILABLE}
    ]
    unresolved.extend(
        f"uncovered:{operation}:{reason}"
        for operation, reason in plan.excluded_operations
    )
    result_rows = [
        {"operation": operation, "verdict": result.value, "reason": reason}
        for operation, result, reason in results
    ]
    executed_cost = sum(
        OPERATIONS[operation].cost_units for operation, _, _ in results
    )
    metrics = {
        "registry_operation_count": len(OPERATIONS),
        "triggered_operation_count": len(plan.candidates),
        "selected_operation_count": len(plan.selected_operations),
        "executed_operation_count": len(results),
        "registry_cost_units": plan.registry_cost_units,
        "planned_cost_units": plan.planned_cost_units,
        "executed_cost_units": executed_cost,
        "avoided_registry_cost_units": plan.registry_cost_units - executed_cost,
        "events_scanned_once": len(events),
        "receipts_scanned_once": len(receipts),
        "semantic_tool_calls": 0,
        "cost_unit_status": "DERIVED_NOT_TOKENS",
        "efficacy_status": "NOT_ESTABLISHED",
    }
    output = {
        "plan_hash": plan.plan_hash,
        "results": result_rows,
        "excluded_operations": list(plan.excluded_operations),
        "metrics": metrics,
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="gauntlet",
        obligation_id=obligation_id,
        verdict=verdict,
        action="assure:minimal-frozen-plan",
        input_hash=plan.input_hash,
        output_hash=digest(output),
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.DERIVED,
                verifier="gauntlet:minimal-planner",
                metadata={
                    "schema": ASSURANCE_SCHEMA,
                    "plan_hash": plan.plan_hash,
                    "coverage_certificate_hash": plan.coverage_certificate_hash,
                    "minimality_certificate_hash": plan.minimality_certificate_hash,
                    "selected_operations": list(plan.selected_operations),
                    "executed_operations": [row["operation"] for row in result_rows],
                    "excluded_operations": list(plan.excluded_operations),
                    "metrics": metrics,
                    "authority": "ASSURANCE_ONLY",
                    "target_domain_clearance_authorized": False,
                },
            ),
        ),
        verifier="gauntlet:minimal-planner",
        tool_version="gauntlet-assurance-v1",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(unresolved),
        notes=json.dumps(
            {
                "boundary": (
                    "Gauntlet evaluates represented process hazards only; it does not "
                    "replace claim-native verification or establish benchmark efficacy."
                ),
                "results": result_rows,
            },
            sort_keys=True,
        ),
        task_id=resolved,
    )
    store.write_receipt(receipt)
    return receipt


def emit_probe(
    root: Path,
    task_id: str,
    failure_class: str,
    *,
    probe_hash: str,
    verifier: str,
    status: str = "VALID",
    artifact_hash: str | None = None,
    scope_hash: str | None = None,
) -> None:
    """Record a content-bound, named OOB probe without claiming exhaustive coverage."""
    if not failure_class.strip() or not probe_hash.strip() or not verifier.strip():
        raise ValueError("coverage probe requires failure_class, probe_hash and verifier")
    if status not in {"VALID", "PASS", Verdict.CLEARED.value}:
        raise ValueError("coverage probe status must be VALID, PASS, or CLEARED")
    artifact_hash = artifact_hash or probe_hash
    scope_hash = scope_hash or digest(
        {"task_id": task_id, "failure_class": failure_class}
    )
    store = RuntimeStore(root)
    store.append_event(
        RuntimeEvent(
            event_id=new_id("evt"),
            event_type="coverage.probe",
            component="gauntlet",
            task_id=task_id,
            payload_hash=probe_hash,
            timestamp=utcnow(),
            metadata={
                "failure_class": failure_class,
                "verifier": verifier,
                "status": status,
                "artifact_hash": artifact_hash,
                "scope_hash": scope_hash,
            },
        )
    )


def run_monitor(
    root: Path,
    operation: str,
    obligation_id: str,
    task_id: str | None = None,
) -> Receipt:
    """Compatibility path for one explicitly requested operation."""
    if operation not in OPERATIONS:
        raise KeyError(operation)
    store, resolved, task, events, receipts = _snapshot(root, obligation_id, task_id)
    verdict, reason = monitor_structured(
        operation,
        events,
        receipts,
        task=task,
        task_id=resolved,
        assurance_obligation_id=obligation_id,
    )
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="gauntlet",
        obligation_id=obligation_id,
        verdict=verdict,
        action=f"monitor:{operation}",
        input_hash=digest(
            {
                "operation": operation,
                "events": [event.get("content_hash") for event in events],
                "receipts": [receipt.get("content_hash") for receipt in receipts],
                "task_hash": task.get("content_hash") if task else None,
            }
        ),
        output_hash=digest({"verdict": verdict.value, "reason": reason}),
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.OBSERVED,
                verifier=f"gauntlet:{operation}",
                metadata={
                    "support_mode": OPERATIONS[operation].mode.value,
                    "monitorability_boundary": OPERATIONS[operation].limitation,
                    "hazard_class": OPERATIONS[operation].hazard_class,
                    "authority": "ASSURANCE_ONLY",
                    "target_domain_clearance_authorized": False,
                },
            ),
        ),
        verifier=f"gauntlet:{operation}",
        started_at=utcnow(),
        finished_at=utcnow(),
        notes=reason,
        unresolved=(reason,)
        if verdict in {Verdict.UNKNOWN, Verdict.UNAVAILABLE}
        else (),
        task_id=resolved,
    )
    store.write_receipt(receipt)
    return receipt
