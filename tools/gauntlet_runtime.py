"""Typed Process Assurance registry and partial-observability runtime monitors.

The ten named operations are not falsely presented as equally automatable. Each has
an explicit support mode and required typed state. UNKNOWN/UNAVAILABLE are first-
class outcomes when the available event trace cannot justify a binary verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    EvidenceClass,
    EvidenceRef,
    Receipt,
    RuntimeEvent,
    SupportMode,
    Verdict,
    digest,
)


@dataclass(frozen=True)
class OperationSpec:
    name: str
    mode: SupportMode
    required_state: tuple[str, ...]
    limitation: str | None = None


OPERATIONS = {
    "frame": OperationSpec("frame", SupportMode.AUTOMATIC, ("action.failed", "action.attempted"), "typed failures plus legacy tool-loop monitor cover only observed repetition"),
    "audit": OperationSpec("audit", SupportMode.AUTOMATIC, ("release.attempted", "obligation.state")),
    "costume": OperationSpec("costume", SupportMode.ASSISTED, ("novelty.claim", "receipt.written"), "free-text novelty detection still requires an assisted semantic classifier; explicitly typed novelty claims can be checked mechanically"),
    "derive": OperationSpec("derive", SupportMode.AUTOMATIC, ("claim.adopted", "receipt.written")),
    "self": OperationSpec("self", SupportMode.AUTOMATIC, ("evidence.attached",), "requires producer/verifier/provenance metadata"),
    "redirect": OperationSpec("redirect", SupportMode.AUTOMATIC, ("action.attempted",), "requires caller-supplied blocker_hash and progress_hash to detect stagnation"),
    "refresh": OperationSpec("refresh", SupportMode.AUTOMATIC, ("authority.snapshot", "authority.changed"), "only registered governing authorities are observable"),
    "boundary": OperationSpec("boundary", SupportMode.AUTOMATIC, ("handoff.started", "contract.bound")),
    "explain": OperationSpec("explain", SupportMode.ASSISTED, ("explanation.claim", "artifact.claim"), "free-text semantic contradiction checking is assisted; matching typed claim IDs/hashes can be compared mechanically"),
    "oob": OperationSpec("oob", SupportMode.AUTOMATIC, ("release.attempted", "coverage.probe"), "a named probe demonstrates coverage of that probe only, never exhaustion of unknown failure classes"),
}


def coverage_registry() -> list[dict[str, Any]]:
    return [
        {"operation": op.name, "mode": op.mode.value, "required_state": list(op.required_state), "limitation": op.limitation}
        for op in OPERATIONS.values()
    ]


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


def monitor_structured(operation: str, events: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> tuple[Verdict, str]:
    if operation not in OPERATIONS:
        return Verdict.UNAVAILABLE, "unknown operation"
    spec = OPERATIONS[operation]
    types = [e.get("event_type") for e in events]

    if operation == "audit":
        if "release.attempted" not in types:
            return Verdict.UNKNOWN, "not-applicable: audit trigger absent: no release attempt in typed trace"
        states = _latest_obligation_states(events)
        if not states:
            return Verdict.UNKNOWN, "release was attempted but no typed obligation-state evidence is observable"
        unresolved = {oid: state for oid, state in states.items() if state != Verdict.CLEARED.value}
        if unresolved:
            return Verdict.ISSUE, f"release attempted with unresolved obligation states: {sorted(unresolved.values())}"
        return Verdict.CLEARED, "current typed load-bearing obligation states are cleared"

    if operation == "derive":
        inherited = [e for e in events if e.get("event_type") == "claim.adopted" and e.get("metadata", {}).get("inherited")]
        if not inherited:
            return Verdict.UNKNOWN, "not-applicable: derive trigger absent: no typed inherited claim"
        derivations = {
            r.get("obligation_id")
            for r in receipts
            if r.get("module") == "mind" and r.get("verdict") == Verdict.CLEARED.value
        }
        bad = [e for e in inherited if e.get("metadata", {}).get("derivation_obligation") not in derivations]
        return (Verdict.ISSUE, "inherited claim lacks current cleared Mind derivation receipt") if bad else (Verdict.CLEARED, "typed inherited claims have derivation coverage")

    if operation == "self":
        evidence_events = [e for e in events if e.get("event_type") == "evidence.attached"]
        if not evidence_events:
            if "release.attempted" in types:
                return Verdict.UNKNOWN, "release attempted without observable evidence-provenance events"
            return Verdict.UNKNOWN, "not-applicable: self trigger absent: no typed evidence attachment"
        for event in evidence_events:
            metadata = event.get("metadata", {})
            if metadata.get("producer") and metadata.get("producer") == metadata.get("verifier"):
                return Verdict.ISSUE, "producer and verifier are identical for typed evidence"
            if metadata.get("producer_provenance") and metadata.get("producer_provenance") == metadata.get("verifier_provenance"):
                return Verdict.UNKNOWN, "evidence and verifier share provenance; independence is not established"
        return Verdict.CLEARED, "no typed self-verification/provenance collision observed"

    if operation == "redirect":
        attempts = [e for e in events if e.get("event_type") == "action.attempted"][-6:]
        if len(attempts) < 3:
            return Verdict.UNKNOWN, "not-applicable: redirect trigger absent: fewer than three recent typed attempts"
        recent = attempts[-3:]
        blockers = [e.get("metadata", {}).get("blocker_hash") for e in recent]
        progress = [e.get("metadata", {}).get("progress_hash") for e in recent]
        if any(value is None for value in blockers + progress):
            return Verdict.UNKNOWN, "recent attempts lack blocker_hash/progress_hash required for redirect monitoring"
        if len(set(blockers)) == 1 and len(set(progress)) == 1:
            return Verdict.ISSUE, "three recent actions left the same blocker and progress state unchanged"
        return Verdict.CLEARED, "recent typed attempts changed blocker or progress state"

    if operation == "boundary":
        handoffs = [e for e in events if e.get("event_type") == "handoff.started"]
        if not handoffs:
            return Verdict.UNKNOWN, "not-applicable: boundary trigger absent: no typed handoff"
        contracts = {e.get("metadata", {}).get("handoff_id") for e in events if e.get("event_type") == "contract.bound"}
        if any(e.get("metadata", {}).get("handoff_id") not in contracts for e in handoffs):
            return Verdict.ISSUE, "handoff lacks a bound contract"
        return Verdict.CLEARED, "typed handoffs have contract bindings"

    if operation == "oob":
        if "release.attempted" not in types:
            return Verdict.UNKNOWN, "not-applicable: oob trigger absent: no release attempt"
        probes = [e for e in events if e.get("event_type") == "coverage.probe"]
        if not probes:
            return Verdict.UNKNOWN, "release has no named out-of-band coverage probe"
        if any(not e.get("metadata", {}).get("failure_class") for e in probes):
            return Verdict.UNKNOWN, "coverage probe lacks a named failure_class"
        return Verdict.CLEARED, "named out-of-band probe(s) recorded; unknown failure classes remain outside this verdict"

    if operation == "costume":
        novelty = [e for e in events if e.get("event_type") == "novelty.claim"]
        if not novelty:
            return Verdict.UNAVAILABLE, spec.limitation or "untyped novelty semantics unavailable"
        cleared_space = {
            e.get("metadata", {}).get("obligation_id")
            for e in events
            if e.get("event_type") == "receipt.written"
            and e.get("component") == "space"
            and e.get("metadata", {}).get("verdict") == Verdict.CLEARED.value
            and e.get("metadata", {}).get("action") == "source-assessment"
        }
        missing = [e for e in novelty if e.get("metadata", {}).get("discovery_obligation") not in cleared_space]
        return (Verdict.ISSUE, "typed novelty claim lacks cleared source-assessed prior-art obligation") if missing else (Verdict.CLEARED, "typed novelty claims have source-assessed discovery coverage")

    if operation == "explain":
        explanations = [e for e in events if e.get("event_type") == "explanation.claim"]
        artifacts = [e for e in events if e.get("event_type") == "artifact.claim"]
        if not explanations:
            return Verdict.UNAVAILABLE, spec.limitation or "untyped explanation semantics unavailable"
        by_id = {e.get("metadata", {}).get("claim_id"): e.get("metadata", {}).get("claim_hash") for e in artifacts if e.get("metadata", {}).get("claim_id")}
        unresolved = False
        for e in explanations:
            metadata = e.get("metadata", {})
            claim_id, claim_hash = metadata.get("claim_id"), metadata.get("claim_hash")
            if not claim_id or claim_id not in by_id:
                unresolved = True
                continue
            if claim_hash and by_id[claim_id] and claim_hash != by_id[claim_id]:
                return Verdict.ISSUE, "typed explanation claim hash contradicts artifact claim hash"
        return (Verdict.UNKNOWN, "one or more explanation claims lack a typed artifact counterpart") if unresolved else (Verdict.CLEARED, "typed explanation claims match artifact claim hashes")

    if operation == "refresh":
        if "authority.changed" in types:
            return Verdict.ISSUE, "registered authority changed; refresh/re-read required"
        if "authority.snapshot" not in types:
            return Verdict.UNKNOWN, "no registered authority snapshot is observable"
        return Verdict.CLEARED, "no typed drift from registered authority snapshot observed"

    if operation == "frame":
        failures = [e for e in events if e.get("event_type") == "action.failed"][-4:]
        if len(failures) < 3:
            return Verdict.UNKNOWN, "not-applicable: frame trigger absent: fewer than three recent typed failures"
        signatures = [e.get("metadata", {}).get("failure_signature") for e in failures[-3:]]
        if any(signature is None for signature in signatures):
            return Verdict.UNKNOWN, "recent failures lack failure_signature required for structural repetition check"
        if len(set(signatures)) == 1:
            return Verdict.ISSUE, "repeated typed failure signature requires reframing"
        return Verdict.CLEARED, "recent typed failures are structurally distinct"

    return Verdict.UNKNOWN, "monitor not implemented"


def emit_probe(root: Path, task_id: str, failure_class: str, *, probe_hash: str, verifier: str) -> None:
    if not failure_class.strip() or not probe_hash.strip() or not verifier.strip():
        raise ValueError("coverage probe requires failure_class, probe_hash and verifier")
    store = RuntimeStore(root)
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type="coverage.probe", component="gauntlet",
        task_id=task_id, payload_hash=probe_hash, timestamp=utcnow(),
        metadata={"failure_class": failure_class, "verifier": verifier},
    ))


def run_monitor(root: Path, operation: str, obligation_id: str, task_id: str | None = None) -> Receipt:
    if operation not in OPERATIONS:
        raise KeyError(operation)
    store = RuntimeStore(root)
    events = store.iter_events(task_id)
    receipts: list[dict[str, Any]] = []
    for path in store.receipts.glob("*.json"):
        receipt = store.read_receipt(path.stem)
        if receipt is not None:
            receipts.append(receipt)
    verdict, reason = monitor_structured(operation, events, receipts)
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="gauntlet", obligation_id=obligation_id,
        verdict=verdict, action=f"monitor:{operation}",
        input_hash=digest({"events": [e.get("content_hash") for e in events], "receipts": [r.get("content_hash") for r in receipts]}),
        output_hash=digest({"verdict": verdict.value, "reason": reason}),
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.OBSERVED,
            verifier=f"gauntlet:{operation}",
            metadata={"support_mode": OPERATIONS[operation].mode.value, "monitorability_boundary": OPERATIONS[operation].limitation},
        ),),
        verifier=f"gauntlet:{operation}", started_at=utcnow(), finished_at=utcnow(), notes=reason,
        unresolved=(reason,) if verdict in (Verdict.UNKNOWN, Verdict.UNAVAILABLE) else (),
        task_id=task_id,
    )
    store.write_receipt(receipt)
    return receipt
