"""Evidence Review Panel state machine with commit/reveal and control matching.

Council measures rather than assumes review diversity. A cleared Council receipt
requires complete commit/reveal, cross-critique participation, and a same-artifact,
same-budget DIRECT control receipt. Agreement alone never clears the obligation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest


@dataclass(frozen=True)
class CouncilSeat:
    seat_id: str
    role: str
    question: str
    method: str
    evidence_partition: str | None = None


@dataclass(frozen=True)
class SeatSubmission:
    hypothesis: str
    claims: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_groups: tuple[str, ...]
    confidence: float | None = None
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class CrossCritique:
    critic_seat_id: str
    target_seat_id: str
    surviving_findings: tuple[str, ...] = ()
    challenged_findings: tuple[str, ...] = ()
    critique_hash: str | None = None

    def __post_init__(self) -> None:
        if self.critic_seat_id == self.target_seat_id:
            raise ValueError("Council seat cannot cross-critique itself")
        if not self.critique_hash and not (self.surviving_findings or self.challenged_findings):
            raise ValueError("cross-critique must contain structured finding IDs or a critique hash")


@dataclass
class CouncilState:
    council_id: str
    task_id: str | None
    artifact_hash: str
    budget_hash: str
    seats: list[CouncilSeat]
    phase: str = "COMMIT"
    commitments: dict[str, str] = field(default_factory=dict)
    sealed: dict[str, dict[str, Any]] = field(default_factory=dict)
    revealed: dict[str, dict[str, Any]] = field(default_factory=dict)
    cross_critiques: list[dict[str, Any]] = field(default_factory=list)
    direct_control_receipt: str | None = None
    vote_control_receipt: str | None = None


def create_council(root: Path, artifact_hash: str, budget_hash: str, seats: list[CouncilSeat], *, task_id: str | None = None) -> CouncilState:
    if not 3 <= len(seats) <= 6:
        raise ValueError("Council requires 3-6 seats")
    if len({s.seat_id for s in seats}) != len(seats):
        raise ValueError("Council seat IDs must be unique")
    if len({s.question for s in seats}) != len(seats):
        raise ValueError("each Council seat must own a distinct question")
    if not any("skeptic" in s.role.lower() or "adversarial" in s.role.lower() for s in seats):
        raise ValueError("Council requires at least one skeptic/adversarial seat")
    if not artifact_hash.strip():
        raise ValueError("Council requires a frozen artifact hash")
    if not budget_hash.strip():
        raise ValueError("Council requires a frozen total-budget hash")
    state = CouncilState(new_id("council"), task_id, artifact_hash, budget_hash, seats)
    RuntimeStore(root).write_named_state("councils", state.council_id, _plain_state(state))
    return state


def _plain_state(state: CouncilState) -> dict[str, Any]:
    return json.loads(json.dumps(state, default=lambda o: o.__dict__, sort_keys=True))


def _load(root: Path, council_id: str) -> CouncilState:
    raw = RuntimeStore(root).read_named_state("councils", council_id)
    if raw is None:
        raise KeyError(council_id)
    raw["seats"] = [CouncilSeat(**s) for s in raw["seats"]]
    return CouncilState(**raw)


def commit(root: Path, council_id: str, seat_id: str, submission: SeatSubmission) -> str:
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "COMMIT":
        raise ValueError("Council is not accepting initial commits")
    if seat_id not in {s.seat_id for s in state.seats}:
        raise KeyError(seat_id)
    if seat_id in state.commitments:
        raise ValueError("seat already committed")
    commitment = digest(submission)
    state.commitments[seat_id] = commitment
    state.sealed[seat_id] = json.loads(json.dumps(submission, default=lambda o: o.__dict__))
    if len(state.commitments) == len(state.seats):
        state.phase = "REVEAL"
    store.write_named_state("councils", council_id, _plain_state(state))
    return commitment


def reveal(root: Path, council_id: str, seat_id: str, submission: SeatSubmission) -> bool:
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase not in ("REVEAL", "CROSS_CRITIQUE"):
        raise ValueError("Council is not in reveal phase")
    expected = state.commitments.get(seat_id)
    if not expected or digest(submission) != expected:
        return False
    state.revealed[seat_id] = json.loads(json.dumps(submission, default=lambda o: o.__dict__))
    if len(state.revealed) == len(state.seats):
        state.phase = "CROSS_CRITIQUE"
    store.write_named_state("councils", council_id, _plain_state(state))
    return True


def record_cross_critique(root: Path, council_id: str, critique: CrossCritique) -> None:
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "CROSS_CRITIQUE":
        raise ValueError("cross-critique is allowed only after all reveals")
    seat_ids = {s.seat_id for s in state.seats}
    if critique.critic_seat_id not in seat_ids or critique.target_seat_id not in seat_ids:
        raise KeyError("unknown Council seat in cross-critique")
    if any(row.get("critic_seat_id") == critique.critic_seat_id and row.get("target_seat_id") == critique.target_seat_id for row in state.cross_critiques):
        raise ValueError("duplicate critic-target cross-critique")
    state.cross_critiques.append(json.loads(json.dumps(critique, default=lambda o: o.__dict__)))
    store.write_named_state("councils", council_id, _plain_state(state))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def overlap_matrix(state: CouncilState) -> dict[str, Any]:
    if not state.revealed:
        return {"pairs": [], "diagnostics": {"seat_count": len(state.seats), "distinct_methods": len({s.method for s in state.seats})}}
    pairs = []
    ids = sorted(state.revealed)
    seat_map = {s.seat_id: s for s in state.seats}
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            a = state.revealed[left]
            b = state.revealed[right]
            pairs.append({
                "left": left,
                "right": right,
                "evidence_overlap": _jaccard(set(a.get("evidence_ids", [])), set(b.get("evidence_ids", []))),
                "provenance_overlap": _jaccard(set(a.get("provenance_groups", [])), set(b.get("provenance_groups", []))),
                "method_same": seat_map[left].method == seat_map[right].method,
                "finding_overlap": _jaccard(set(a.get("findings", [])), set(b.get("findings", []))),
            })
    def mean(key: str) -> float | None:
        values = [float(row[key]) for row in pairs]
        return sum(values) / len(values) if values else None
    return {
        "pairs": pairs,
        "diagnostics": {
            "seat_count": len(state.seats),
            "distinct_methods": len({s.method for s in state.seats}),
            "mean_evidence_overlap": mean("evidence_overlap"),
            "mean_provenance_overlap": mean("provenance_overlap"),
            "mean_finding_overlap": mean("finding_overlap"),
            "interpretation": "Overlap is a correlation/common-cause diagnostic, not a proof of statistical independence.",
        },
    }


def brier_score(confidence: float, outcome_correct: bool) -> float:
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return (confidence - (1.0 if outcome_correct else 0.0)) ** 2


def record_control(root: Path, obligation_id: str, *, artifact_hash: str, budget_hash: str, kind: str, output_hash: str, verdict: Verdict, verifier: str) -> Receipt:
    kind = kind.upper()
    if kind not in {"DIRECT", "VOTE"}:
        raise ValueError("Council control kind must be DIRECT or VOTE")
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="council", obligation_id=obligation_id,
        verdict=verdict, action=f"control:{kind.lower()}",
        input_hash=digest({"artifact_hash": artifact_hash, "budget_hash": budget_hash, "kind": kind}),
        output_hash=output_hash,
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.MEASURED,
            verifier=verifier,
            metadata={"control_kind": kind, "artifact_hash": artifact_hash, "budget_hash": budget_hash},
        ),),
        verifier=verifier, started_at=utcnow(), finished_at=utcnow(),
        notes="Control receipt records comparability metadata; it does not itself establish Council benefit.",
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def _matched_control(store: RuntimeStore, receipt_id: str | None, kind: str, artifact_hash: str, budget_hash: str) -> bool:
    if not receipt_id:
        return False
    receipt = store.read_receipt(receipt_id)
    if not receipt or receipt.get("module") != "council":
        return False
    for evidence in receipt.get("evidence", []):
        meta = evidence.get("metadata", {}) if isinstance(evidence, dict) else {}
        if (
            meta.get("control_kind") == kind
            and meta.get("artifact_hash") == artifact_hash
            and meta.get("budget_hash") == budget_hash
        ):
            return receipt.get("verdict") == Verdict.CLEARED.value
    return False


def _cross_critique_complete(state: CouncilState) -> bool:
    critics = {row.get("critic_seat_id") for row in state.cross_critiques}
    return critics == {seat.seat_id for seat in state.seats}


def finalize(
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
    store = RuntimeStore(root)
    state = _load(root, council_id)
    direct_exists = _matched_control(store, direct_control_receipt, "DIRECT", state.artifact_hash, state.budget_hash)
    vote_exists = _matched_control(store, vote_control_receipt, "VOTE", state.artifact_hash, state.budget_hash)
    reveal_complete = len(state.revealed) == len(state.seats)
    critique_complete = _cross_critique_complete(state)
    missing: list[str] = list(unresolved or [])
    if not reveal_complete:
        missing.append("all-seat-reveal-incomplete")
    if reveal_complete and not critique_complete:
        missing.append("cross-critique-participation-incomplete")
    if not direct_exists:
        missing.append("same-artifact-same-budget-direct-control-missing-invalid-or-mismatched")

    if missing:
        verdict = Verdict.UNKNOWN
    else:
        # This clears the REVIEW obligation only: the panel executed its frozen
        # method and produced supported finding IDs under a valid control. It does
        # not imply that Council is globally superior to DIRECT or VOTE.
        verdict = Verdict.CLEARED if supported_findings else Verdict.UNKNOWN
        if not supported_findings:
            missing.append("no-supported-finding-after-synthesis")

    state.phase = "CLOSED"
    state.direct_control_receipt = direct_control_receipt
    state.vote_control_receipt = vote_control_receipt
    store.write_named_state("councils", council_id, _plain_state(state))
    matrix = overlap_matrix(state)
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="council", obligation_id=obligation_id,
        verdict=verdict, action="commit-reveal-controlled-evidence-review",
        input_hash=digest({"artifact_hash": state.artifact_hash, "budget_hash": state.budget_hash, "commitments": state.commitments}),
        output_hash=synthesis_hash,
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.DERIVED,
            verifier="council_runtime",
            metadata={
                "overlap": matrix,
                "confidence_status": "UNCALIBRATED_UNLESS_PROSPECTIVELY_SCORED",
                "direct_control_matched": direct_exists,
                "vote_control_matched": vote_exists,
                "cross_critique_complete": critique_complete,
            },
        ),),
        verifier="council_runtime", started_at=utcnow(), finished_at=utcnow(),
        unresolved=tuple(dict.fromkeys(missing)),
        notes=json.dumps({
            "supported_finding_hashes": [digest(finding) for finding in supported_findings],
            "overlap_diagnostics": matrix.get("diagnostics", {}),
            "boundary": "CLEARED means the frozen Council review protocol completed; it is not a claim that Council outperforms controls.",
        }, sort_keys=True),
        task_id=state.task_id,
    )
    store.write_receipt(receipt)
    return receipt
