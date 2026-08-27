"""Evidence Review Panel state machine with challenge-derived seats.

Council measures rather than assumes review diversity. A cleared Council receipt
requires complete commit/reveal, cross-critique participation, and a same-artifact,
same-budget DIRECT control receipt. Council findings may propose neutral challenges,
but they never clear the target module's domain obligation.
"""
from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from egrt_challenge import ChallengeError, propose_challenge
from egrt_challenge_types import ChallengeKind, ChallengeOrigin, ChallengeRequest
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, ObligationKind, Receipt, Verdict, digest

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_CHALLENGE_STATES = {"RESOLVED", "DISMISSED_NOT_APPLICABLE"}
_GENERIC_REFUTERS = {"be critical", "review critically", "what breaks it", "look for problems"}

_RESIDUAL_SEAT_CLASSES: dict[ChallengeKind, tuple[str, str, str, str | None]] = {
    ChallengeKind.ALTERNATE_FORMALIZATION: (
        "formal correctness",
        "proof",
        "compare formalizations with a claim-native derivation or counterexample",
        "FORMAL_PROOF",
    ),
    ChallengeKind.CLAIM_NEGATION: (
        "formal correctness",
        "proof",
        "attempt the bound negation or contradiction check",
        "FORMAL_PROOF",
    ),
    ChallengeKind.COUNTEREXAMPLE: (
        "skeptic",
        "adversarial",
        "produce or rule out a concrete counterexample",
        "FORMAL_PROOF",
    ),
    ChallengeKind.ASSUMPTION_KNOCKOUT: (
        "novelty / costume",
        "ablation",
        "remove the named assumption and compare the bound result",
        None,
    ),
    ChallengeKind.REPRESENTATION_SWAP: (
        "formal correctness",
        "alternate representation",
        "re-express the claim and compare the exact scoped result",
        "REASONING",
    ),
    ChallengeKind.SOURCE_CONFLICT: (
        "evidence / provenance",
        "source assessment",
        "resolve the conflict using source quality and provenance",
        "SCHOLARLY_SEARCH",
    ),
    ChallengeKind.RETRIEVAL_REFRAME: (
        "evidence / provenance",
        "retrieval reframe",
        "run the non-redundant mechanism-level query reframe",
        "WEB_SEARCH",
    ),
    ChallengeKind.NOVELTY_COSTUME: (
        "novelty / costume",
        "prior-art comparison",
        "compare against the strongest known costume with assessed sources",
        "SCHOLARLY_SEARCH",
    ),
    ChallengeKind.FAILURE_CLASS: (
        "executable behavior",
        "targeted execution",
        "run the smallest check that exposes the named failure class",
        "CODE_EXECUTION",
    ),
    ChallengeKind.METAMORPHIC_RELATION: (
        "executable behavior",
        "metamorphic check",
        "execute the declared relation and compare outputs",
        "CODE_EXECUTION",
    ),
    ChallengeKind.BASELINE_OR_ESTIMAND: (
        "measurement validity",
        "design comparison",
        "compare the frozen baseline or estimand before interpreting outcomes",
        "STATISTICAL_ANALYSIS",
    ),
    ChallengeKind.CONTAMINATION: (
        "measurement validity",
        "contamination audit",
        "audit the frozen item, context, and exclusion boundary",
        "STATISTICAL_ANALYSIS",
    ),
    ChallengeKind.STATE_DRIFT: (
        "operational feasibility",
        "state audit",
        "replay the bound state and detect drift",
        "REPOSITORY",
    ),
    ChallengeKind.DECISION_REVERSAL: (
        "operational feasibility",
        "reversal check",
        "run the smallest information action that could reverse the decision",
        None,
    ),
    ChallengeKind.REVIEW_DIVERSITY: (
        "review diversity",
        "overlap audit",
        "compare method, evidence, provenance, and finding overlap",
        None,
    ),
    ChallengeKind.OUTPUT_CONTRACT: (
        "executable behavior",
        "contract check",
        "execute the output contract against the real entrypoint",
        "CODE_EXECUTION",
    ),
}


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _optional_text(name: str, value: object) -> None:
    if value is not None:
        _require_text(name, value)


def _kind(value: ChallengeKind | str | None) -> ChallengeKind | None:
    if value is None:
        return None
    if isinstance(value, ChallengeKind):
        return value
    if not isinstance(value, str):
        raise TypeError("challenge_kind must be ChallengeKind, str, or None")
    try:
        return ChallengeKind(value)
    except ValueError as error:
        raise ValueError(f"unknown challenge_kind: {value}") from error


def _infer_kind(role: str) -> ChallengeKind:
    value = role.lower()
    if "skeptic" in value or "adversarial" in value:
        return ChallengeKind.COUNTEREXAMPLE
    if "formal" in value or "logic" in value or "proof" in value:
        return ChallengeKind.ALTERNATE_FORMALIZATION
    if "evidence" in value or "provenance" in value or "source" in value:
        return ChallengeKind.SOURCE_CONFLICT
    if "empirical" in value or "measurement" in value or "evaluation" in value:
        return ChallengeKind.BASELINE_OR_ESTIMAND
    if "implementation" in value or "integration" in value or "executable" in value:
        return ChallengeKind.FAILURE_CLASS
    if "novel" in value or "prior art" in value or "costume" in value:
        return ChallengeKind.NOVELTY_COSTUME
    if "operat" in value or "feasib" in value or "cost" in value or "ops" in value:
        return ChallengeKind.STATE_DRIFT
    return ChallengeKind.REVIEW_DIVERSITY


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


@dataclass(frozen=True)
class SeatChallengeSpec:
    challenge_kind: ChallengeKind | str
    discriminator: str
    required_capability: str | None
    target_obligation_id: str
    refuter: str
    evidence_partition: str | None = None

    def __post_init__(self) -> None:
        challenge_kind = _kind(self.challenge_kind)
        if challenge_kind is None:
            raise ValueError("challenge_kind is required")
        object.__setattr__(self, "challenge_kind", challenge_kind)
        for name in ("discriminator", "target_obligation_id", "refuter"):
            _require_text(name, getattr(self, name))
        for name in ("required_capability", "evidence_partition"):
            _optional_text(name, getattr(self, name))


@dataclass(frozen=True)
class CouncilSeat:
    seat_id: str
    role: str
    question: str
    method: str
    evidence_partition: str | None = None
    challenge_kind: ChallengeKind | str | None = None
    discriminator: str | None = None
    required_capability: str | None = None
    target_obligation_id: str | None = None
    refuter: str | None = None
    reviewer_provenance: str | None = None
    challenge_contract: str = "auto"

    def __post_init__(self) -> None:
        for name in ("seat_id", "role", "question", "method"):
            _require_text(name, getattr(self, name))
        for name in (
            "evidence_partition",
            "discriminator",
            "required_capability",
            "target_obligation_id",
            "refuter",
            "reviewer_provenance",
        ):
            _optional_text(name, getattr(self, name))
        if self.challenge_contract not in {"auto", "legacy", "vnext"}:
            raise ValueError("challenge_contract must be auto, legacy, or vnext")

        explicit = any(
            value is not None
            for value in (
                self.challenge_kind,
                self.discriminator,
                self.required_capability,
                self.target_obligation_id,
                self.refuter,
            )
        )
        contract = "vnext" if self.challenge_contract == "auto" and explicit else self.challenge_contract
        if contract == "auto":
            contract = "legacy"
        object.__setattr__(self, "challenge_contract", contract)

        challenge_kind = _kind(self.challenge_kind) or _infer_kind(self.role)
        object.__setattr__(self, "challenge_kind", challenge_kind)
        object.__setattr__(self, "discriminator", self.discriminator or self.method)
        object.__setattr__(self, "refuter", self.refuter or self.discriminator or self.question)

        if contract == "vnext":
            if not self.target_obligation_id:
                raise ValueError("vNext Council seat requires target_obligation_id")
            if not self.discriminator:
                raise ValueError("vNext Council seat requires a discriminator")
            if not self.refuter:
                raise ValueError("vNext Council seat requires a concrete refuter")
            if (
                ("skeptic" in self.role.lower() or "adversarial" in self.role.lower())
                and _norm(self.refuter) in _GENERIC_REFUTERS
            ):
                raise ValueError("vNext skeptic seat requires a concrete refuter")


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


@dataclass(frozen=True)
class CouncilFinding:
    finding_id: str
    seat_id: str
    target_module: str
    target_obligation_id: str
    challenge_kind: ChallengeKind | str
    hypothesis: str
    refuter: str
    consequence_if_true: str
    candidate_hash: str
    scope_hash: str
    obligation_set_hash: str
    alternative: str | None = None
    load_bearing: bool = True
    required_capability: str | None = None
    evidence_partition: str | None = None
    proposer_provenance: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "finding_id",
            "seat_id",
            "target_module",
            "target_obligation_id",
            "hypothesis",
            "refuter",
            "consequence_if_true",
        ):
            _require_text(name, getattr(self, name))
        for name in ("alternative", "required_capability", "evidence_partition", "proposer_provenance"):
            _optional_text(name, getattr(self, name))
        challenge_kind = _kind(self.challenge_kind)
        if challenge_kind is None:
            raise ValueError("challenge_kind is required")
        object.__setattr__(self, "challenge_kind", challenge_kind)
        if not isinstance(self.load_bearing, bool):
            raise TypeError("load_bearing must be bool")
        if not isinstance(self.metadata, dict) or any(not isinstance(key, str) for key in self.metadata):
            raise TypeError("metadata must be a dict with string keys")
        for name in ("candidate_hash", "scope_hash", "obligation_set_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


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
    findings: dict[str, dict[str, Any]] = field(default_factory=dict)
    supported_finding_ids: list[str] = field(default_factory=list)
    review_receipt_id: str | None = None


class CouncilAuthorityError(ValueError):
    """Raised when Council attempts to exercise authority outside REVIEW."""


def _row(value: ChallengeRequest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, ChallengeRequest):
        return json.loads(json.dumps(value, default=lambda item: item.__dict__, sort_keys=True))
    return dict(value)


def derive_challenge_seats(
    challenges: Sequence[ChallengeRequest | Mapping[str, Any]],
    *,
    max_seats: int = 6,
    reviewer_provenance: str | None = None,
) -> list[CouncilSeat]:
    """Derive deterministic residual-gap seats from open neutral challenges.

    One seat is created per bound challenge until ``max_seats``. Resolved and
    dismissed challenges are ignored. Seat count never establishes independence.
    """
    if not 3 <= max_seats <= 6:
        raise ValueError("max_seats must be between 3 and 6")
    rows = [
        _row(challenge)
        for challenge in challenges
        if str(_row(challenge).get("state") or "PROPOSED") not in _TERMINAL_CHALLENGE_STATES
    ]
    rows.sort(
        key=lambda item: (
            not bool(item.get("load_bearing")),
            -int(item.get("risk_rank") or 0),
            -int(item.get("information_rank") or 0),
            int(item.get("cost_rank") or 0),
            str(item.get("challenge_id") or ""),
        )
    )
    seats: list[CouncilSeat] = []
    for row in rows[:max_seats]:
        challenge_kind = _kind(row.get("kind"))
        if challenge_kind is None:
            continue
        role, method, fallback_discriminator, fallback_capability = _RESIDUAL_SEAT_CLASSES[challenge_kind]
        selected_plan = row.get("selected_plan") if isinstance(row.get("selected_plan"), dict) else {}
        discriminator = str(
            selected_plan.get("action")
            or row.get("refuter")
            or fallback_discriminator
        )
        challenge_id = str(row.get("challenge_id") or digest(row)[:16])
        evidence_partition = f"challenge:{challenge_id}"
        seats.append(
            CouncilSeat(
                seat_id=f"seat-{digest({'challenge_id': challenge_id, 'role': role})[:12]}",
                role=role,
                question=str(row.get("hypothesis") or f"Resolve {challenge_kind.value}"),
                method=method,
                evidence_partition=evidence_partition,
                challenge_kind=challenge_kind,
                discriminator=discriminator,
                required_capability=(
                    str(row.get("required_capability"))
                    if row.get("required_capability")
                    else fallback_capability
                ),
                target_obligation_id=str(row.get("obligation_id") or ""),
                refuter=str(row.get("refuter") or discriminator),
                reviewer_provenance=reviewer_provenance,
                challenge_contract="vnext",
            )
        )
    if seats and not any("skeptic" in seat.role.lower() or "adversarial" in seat.role.lower() for seat in seats):
        first = seats[0]
        seats[0] = CouncilSeat(
            seat_id=first.seat_id,
            role=f"skeptic / {first.role}",
            question=first.question,
            method=first.method,
            evidence_partition=first.evidence_partition,
            challenge_kind=first.challenge_kind,
            discriminator=first.discriminator,
            required_capability=first.required_capability,
            target_obligation_id=first.target_obligation_id,
            refuter=first.refuter,
            reviewer_provenance=first.reviewer_provenance,
            challenge_contract="vnext",
        )
    return seats


def _distinct_partition(left: CouncilSeat, right: CouncilSeat) -> bool:
    return bool(
        left.evidence_partition
        and right.evidence_partition
        and _norm(left.evidence_partition) != _norm(right.evidence_partition)
    )


def _validate_challenge_seats(seats: Sequence[CouncilSeat]) -> None:
    vnext = [seat for seat in seats if seat.challenge_contract == "vnext"]
    if vnext and len(vnext) != len(seats):
        raise ValueError("Council cannot mix legacy and vNext challenge seats")
    if not vnext:
        return
    for index, left in enumerate(seats):
        for right in seats[index + 1 :]:
            duplicate_kind = left.challenge_kind == right.challenge_kind
            duplicate_discriminator = _norm(left.discriminator) == _norm(right.discriminator)
            if (duplicate_kind or duplicate_discriminator) and not _distinct_partition(left, right):
                raise ValueError(
                    "duplicate Council challenge kind/discriminator requires explicit distinct evidence partitions"
                )


def create_council(
    root: Path,
    artifact_hash: str,
    budget_hash: str,
    seats: list[CouncilSeat],
    *,
    task_id: str | None = None,
) -> CouncilState:
    if not 3 <= len(seats) <= 6:
        raise ValueError("Council requires 3-6 seats")
    if len({seat.seat_id for seat in seats}) != len(seats):
        raise ValueError("Council seat IDs must be unique")
    if len({_norm(seat.question) for seat in seats}) != len(seats):
        raise ValueError("each Council seat must own a distinct question")
    if not any("skeptic" in seat.role.lower() or "adversarial" in seat.role.lower() for seat in seats):
        raise ValueError("Council requires at least one skeptic/adversarial seat")
    if not artifact_hash.strip():
        raise ValueError("Council requires a frozen artifact hash")
    if not budget_hash.strip():
        raise ValueError("Council requires a frozen total-budget hash")
    _validate_challenge_seats(seats)
    state = CouncilState(new_id("council"), task_id, artifact_hash, budget_hash, seats)
    RuntimeStore(root).write_named_state("councils", state.council_id, _plain_state(state))
    return state


def _plain_state(state: CouncilState) -> dict[str, Any]:
    return json.loads(json.dumps(state, default=lambda value: value.__dict__, sort_keys=True))


def _load(root: Path, council_id: str) -> CouncilState:
    raw = RuntimeStore(root).read_named_state("councils", council_id)
    if raw is None:
        raise KeyError(council_id)
    raw["seats"] = [CouncilSeat(**seat) for seat in raw["seats"]]
    return CouncilState(**raw)


def commitment_digest(seat_id: str, nonce: str, submission: SeatSubmission) -> str:
    """Hiding + binding commitment over one seat's submission."""
    return digest({"seat_id": seat_id, "nonce": nonce, "submission": submission})


def commit(
    root: Path,
    council_id: str,
    seat_id: str,
    submission: SeatSubmission,
    *,
    nonce: str | None = None,
) -> tuple[str, str]:
    """Record a seat commitment. Returns ``(commitment, nonce)``."""
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "COMMIT":
        raise ValueError("Council is not accepting initial commits")
    if seat_id not in {seat.seat_id for seat in state.seats}:
        raise KeyError(seat_id)
    if seat_id in state.commitments:
        raise ValueError("seat already committed")
    nonce = nonce or secrets.token_hex(16)
    commitment = commitment_digest(seat_id, nonce, submission)
    state.commitments[seat_id] = commitment
    if len(state.commitments) == len(state.seats):
        state.phase = "REVEAL"
    store.write_named_state("councils", council_id, _plain_state(state))
    return commitment, nonce


def reveal(
    root: Path,
    council_id: str,
    seat_id: str,
    submission: SeatSubmission,
    nonce: str | None = None,
) -> bool:
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase not in ("REVEAL", "CROSS_CRITIQUE"):
        raise ValueError("Council is not in reveal phase")
    expected = state.commitments.get(seat_id)
    if not expected or not nonce:
        return False
    if commitment_digest(seat_id, nonce, submission) != expected:
        return False
    state.sealed[seat_id] = {"commitment": expected}
    state.revealed[seat_id] = json.loads(json.dumps(submission, default=lambda value: value.__dict__))
    if len(state.revealed) == len(state.seats):
        state.phase = "CROSS_CRITIQUE"
    store.write_named_state("councils", council_id, _plain_state(state))
    return True


def record_cross_critique(root: Path, council_id: str, critique: CrossCritique) -> None:
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "CROSS_CRITIQUE":
        raise ValueError("cross-critique is allowed only after all reveals")
    seat_ids = {seat.seat_id for seat in state.seats}
    if critique.critic_seat_id not in seat_ids or critique.target_seat_id not in seat_ids:
        raise KeyError("unknown Council seat in cross-critique")
    if any(
        row.get("critic_seat_id") == critique.critic_seat_id
        and row.get("target_seat_id") == critique.target_seat_id
        for row in state.cross_critiques
    ):
        raise ValueError("duplicate critic-target cross-critique")
    state.cross_critiques.append(
        json.loads(json.dumps(critique, default=lambda value: value.__dict__))
    )
    store.write_named_state("councils", council_id, _plain_state(state))


def record_finding(root: Path, council_id: str, finding: CouncilFinding) -> None:
    """Register a structured finding after reveal and before synthesis."""
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "CROSS_CRITIQUE":
        raise ValueError("Council findings are recorded only after all reveals")
    if finding.finding_id in state.findings:
        raise ValueError("duplicate Council finding_id")
    seat_map = {seat.seat_id: seat for seat in state.seats}
    seat = seat_map.get(finding.seat_id)
    if seat is None:
        raise KeyError(finding.seat_id)
    revealed = state.revealed.get(finding.seat_id, {})
    if finding.finding_id not in revealed.get("findings", []):
        raise ValueError("structured finding must be named in the seat's revealed submission")
    if seat.challenge_contract == "vnext":
        if finding.challenge_kind != seat.challenge_kind:
            raise ValueError("finding challenge_kind does not match its Council seat")
        if finding.target_obligation_id != seat.target_obligation_id:
            raise ValueError("finding target_obligation_id does not match its Council seat")
        if seat.required_capability and finding.required_capability != seat.required_capability:
            raise ValueError("finding required_capability does not match its Council seat")
        if _norm(finding.refuter) != _norm(seat.refuter):
            raise ValueError("finding refuter does not match its Council seat")
        if _norm(finding.evidence_partition) != _norm(seat.evidence_partition):
            raise ValueError("finding evidence_partition does not match its Council seat")
    state.findings[finding.finding_id] = json.loads(
        json.dumps(finding, default=lambda value: value.__dict__, sort_keys=True)
    )
    store.write_named_state("councils", council_id, _plain_state(state))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def overlap_matrix(state: CouncilState) -> dict[str, Any]:
    if not state.revealed:
        return {
            "pairs": [],
            "diagnostics": {
                "seat_count": len(state.seats),
                "distinct_methods": len({seat.method for seat in state.seats}),
                "independence_status": "NOT_ESTABLISHED_BY_SEAT_COUNT",
            },
        }
    pairs: list[dict[str, Any]] = []
    ids = sorted(state.revealed)
    seat_map = {seat.seat_id: seat for seat in state.seats}
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            a = state.revealed[left]
            b = state.revealed[right]
            left_seat = seat_map[left]
            right_seat = seat_map[right]
            same_reviewer = bool(
                left_seat.reviewer_provenance
                and right_seat.reviewer_provenance
                and left_seat.reviewer_provenance == right_seat.reviewer_provenance
            )
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "evidence_overlap": _jaccard(
                        set(a.get("evidence_ids", [])),
                        set(b.get("evidence_ids", [])),
                    ),
                    "provenance_overlap": _jaccard(
                        set(a.get("provenance_groups", [])),
                        set(b.get("provenance_groups", [])),
                    ),
                    "method_same": left_seat.method == right_seat.method,
                    "reviewer_provenance_same": same_reviewer,
                    "finding_overlap": _jaccard(
                        set(a.get("findings", [])),
                        set(b.get("findings", [])),
                    ),
                    "independence_status": "NOT_ESTABLISHED",
                }
            )

    def mean(key: str) -> float | None:
        values = [float(row[key]) for row in pairs]
        return sum(values) / len(values) if values else None

    return {
        "pairs": pairs,
        "diagnostics": {
            "seat_count": len(state.seats),
            "distinct_methods": len({seat.method for seat in state.seats}),
            "same_reviewer_provenance_pairs": sum(
                bool(row["reviewer_provenance_same"]) for row in pairs
            ),
            "mean_evidence_overlap": mean("evidence_overlap"),
            "mean_provenance_overlap": mean("provenance_overlap"),
            "mean_finding_overlap": mean("finding_overlap"),
            "independence_status": "NOT_ESTABLISHED_BY_SEAT_COUNT",
            "interpretation": (
                "Overlap and reviewer provenance are common-cause diagnostics; "
                "nominal seat count never establishes statistical independence."
            ),
        },
    }


def brier_score(confidence: float, outcome_correct: bool) -> float:
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return (confidence - (1.0 if outcome_correct else 0.0)) ** 2


def record_control(
    root: Path,
    obligation_id: str,
    *,
    artifact_hash: str,
    budget_hash: str,
    kind: str,
    output_hash: str,
    verdict: Verdict,
    verifier: str,
) -> Receipt:
    kind = kind.upper()
    if kind not in {"DIRECT", "VOTE"}:
        raise ValueError("Council control kind must be DIRECT or VOTE")
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="council",
        obligation_id=obligation_id,
        verdict=verdict,
        action=f"control:{kind.lower()}",
        input_hash=digest(
            {"artifact_hash": artifact_hash, "budget_hash": budget_hash, "kind": kind}
        ),
        output_hash=output_hash,
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.MEASURED,
                verifier=verifier,
                metadata={
                    "control_kind": kind,
                    "artifact_hash": artifact_hash,
                    "budget_hash": budget_hash,
                },
            ),
        ),
        verifier=verifier,
        started_at=utcnow(),
        finished_at=utcnow(),
        notes=(
            "Control receipt records comparability metadata; it does not itself "
            "establish Council benefit."
        ),
    )
    RuntimeStore(root).write_receipt(receipt)
    return receipt


def _matched_control(
    store: RuntimeStore,
    receipt_id: str | None,
    kind: str,
    artifact_hash: str,
    budget_hash: str,
    obligation_id: str | None = None,
) -> bool:
    if not receipt_id:
        return False
    receipt = store.read_receipt(receipt_id)
    if not receipt or receipt.get("module") != "council":
        return False
    if obligation_id is not None and receipt.get("obligation_id") != obligation_id:
        return False
    for evidence in receipt.get("evidence", []):
        metadata = evidence.get("metadata", {}) if isinstance(evidence, dict) else {}
        if (
            metadata.get("control_kind") == kind
            and metadata.get("artifact_hash") == artifact_hash
            and metadata.get("budget_hash") == budget_hash
        ):
            return receipt.get("verdict") == Verdict.CLEARED.value
    return False


def _cross_critique_complete(state: CouncilState) -> bool:
    critics = {row.get("critic_seat_id") for row in state.cross_critiques}
    return critics == {seat.seat_id for seat in state.seats}


def _obligation_row(store: RuntimeStore, state: CouncilState, obligation_id: str) -> dict[str, Any] | None:
    task_id = state.task_id or store.task_for_obligation(obligation_id)
    if task_id is None:
        return None
    task = store.read_task(task_id)
    if task is None:
        raise CouncilAuthorityError("Council task is missing or corrupt")
    for obligation in task.get("obligations", []):
        if obligation.get("obligation_id") == obligation_id:
            return obligation
    raise CouncilAuthorityError("Council receipt obligation is not part of the bound task")


def _require_review_authority(store: RuntimeStore, state: CouncilState, obligation_id: str) -> None:
    obligation = _obligation_row(store, state, obligation_id)
    if obligation is None:
        return
    if obligation.get("kind") != ObligationKind.REVIEW.value:
        raise CouncilAuthorityError(
            "Council can clear only a REVIEW obligation, never the target domain obligation"
        )
    required = obligation.get("required_module")
    if required not in (None, "council"):
        raise CouncilAuthorityError("REVIEW obligation is bound to a different module")


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
    if state.phase == "CLOSED":
        raise ValueError("Council is already CLOSED; finalize is not re-callable")
    _require_review_authority(store, state, obligation_id)

    direct_exists = _matched_control(
        store,
        direct_control_receipt,
        "DIRECT",
        state.artifact_hash,
        state.budget_hash,
        obligation_id,
    )
    vote_exists = _matched_control(
        store,
        vote_control_receipt,
        "VOTE",
        state.artifact_hash,
        state.budget_hash,
        obligation_id,
    )
    reveal_complete = len(state.revealed) == len(state.seats)
    critique_complete = _cross_critique_complete(state)
    missing: list[str] = list(unresolved or [])
    if not reveal_complete:
        missing.append("all-seat-reveal-incomplete")
    if reveal_complete and not critique_complete:
        missing.append("cross-critique-participation-incomplete")
    if not direct_exists:
        missing.append("same-artifact-same-budget-direct-control-missing-invalid-or-mismatched")
    if all(seat.challenge_contract == "vnext" for seat in state.seats):
        for finding_id in supported_findings:
            if finding_id not in state.findings:
                missing.append(f"supported-finding-missing-structured-record:{finding_id}")

    if missing:
        verdict = Verdict.UNKNOWN
    else:
        verdict = Verdict.CLEARED if supported_findings else Verdict.UNKNOWN
        if not supported_findings:
            missing.append("no-supported-finding-after-synthesis")

    state.phase = "CLOSED"
    state.direct_control_receipt = direct_control_receipt
    state.vote_control_receipt = vote_control_receipt
    state.supported_finding_ids = list(dict.fromkeys(supported_findings))
    matrix = overlap_matrix(state)
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="council",
        obligation_id=obligation_id,
        verdict=verdict,
        action="commit-reveal-controlled-evidence-review",
        input_hash=digest(
            {
                "artifact_hash": state.artifact_hash,
                "budget_hash": state.budget_hash,
                "commitments": state.commitments,
            }
        ),
        output_hash=synthesis_hash,
        evidence=(
            EvidenceRef(
                evidence_class=EvidenceClass.DERIVED,
                verifier="council_runtime",
                metadata={
                    "overlap": matrix,
                    "confidence_status": "UNCALIBRATED_UNLESS_PROSPECTIVELY_SCORED",
                    "direct_control_matched": direct_exists,
                    "vote_control_matched": vote_exists,
                    "cross_critique_complete": critique_complete,
                    "authority": "REVIEW_ONLY",
                    "target_domain_clearance_authorized": False,
                },
            ),
        ),
        verifier="council_runtime",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(dict.fromkeys(missing)),
        notes=json.dumps(
            {
                "supported_finding_hashes": [
                    digest(finding) for finding in supported_findings
                ],
                "overlap_diagnostics": matrix.get("diagnostics", {}),
                "boundary": (
                    "CLEARED means the frozen Council REVIEW protocol completed. "
                    "Council findings are proposal-only and cannot clear target domain obligations."
                ),
            },
            sort_keys=True,
        ),
        task_id=state.task_id,
    )
    state.review_receipt_id = receipt.receipt_id
    store.write_named_state("councils", council_id, _plain_state(state))
    store.write_receipt(receipt)
    return receipt


def _validate_target_binding(
    store: RuntimeStore,
    task_id: str,
    finding: CouncilFinding,
) -> None:
    task = store.read_task(task_id)
    if task is None:
        raise CouncilAuthorityError("Council target task is missing or corrupt")
    for obligation in task.get("obligations", []):
        if obligation.get("obligation_id") != finding.target_obligation_id:
            continue
        required = obligation.get("required_module")
        if required and required != finding.target_module:
            raise CouncilAuthorityError(
                "Council finding target_module does not match the target obligation"
            )
        return
    raise CouncilAuthorityError("Council finding targets an obligation outside the bound task")


def propose_supported_finding_challenge(
    root: Path,
    council_id: str,
    finding_id: str,
    *,
    proposer: str = "council_runtime",
) -> ChallengeRequest:
    """Convert one supported structured finding into a neutral proposal.

    The returned ``ChallengeRequest`` has ``origin=COUNCIL`` and proposal-only
    authority. This function never writes a Council receipt for the target obligation
    and never resolves the emitted challenge.
    """
    store = RuntimeStore(root)
    state = _load(root, council_id)
    if state.phase != "CLOSED":
        raise ChallengeError("Council must be finalized before emitting a supported challenge")
    if finding_id not in state.supported_finding_ids:
        raise ChallengeError("Council finding was not supported by final synthesis")
    raw = state.findings.get(finding_id)
    if raw is None:
        raise ChallengeError("supported finding lacks a structured challenge record")
    finding = CouncilFinding(**raw)
    if state.task_id is None:
        raise ChallengeError("Council challenge emission requires a bound task_id")
    _validate_target_binding(store, state.task_id, finding)

    seat = next(
        (candidate for candidate in state.seats if candidate.seat_id == finding.seat_id),
        None,
    )
    if seat is None:
        raise ChallengeError("supported finding references an unknown Council seat")

    request = ChallengeRequest(
        challenge_id=new_id("chal"),
        task_id=state.task_id,
        obligation_id=finding.target_obligation_id,
        target_module=finding.target_module,
        origin=ChallengeOrigin.COUNCIL,
        kind=finding.challenge_kind,
        hypothesis=finding.hypothesis,
        alternative=finding.alternative,
        refuter=finding.refuter,
        consequence_if_true=finding.consequence_if_true,
        load_bearing=finding.load_bearing,
        required_capability=finding.required_capability,
        candidate_hash=finding.candidate_hash,
        scope_hash=finding.scope_hash,
        obligation_set_hash=finding.obligation_set_hash,
        proposer=proposer,
        proposer_provenance=finding.proposer_provenance or state.review_receipt_id,
        metadata={
            **finding.metadata,
            "council_id": council_id,
            "review_receipt_id": state.review_receipt_id,
            "finding_id": finding.finding_id,
            "seat_id": finding.seat_id,
            "seat_discriminator": seat.discriminator,
            "evidence_partition": finding.evidence_partition,
            "authority": "PROPOSAL_ONLY",
            "domain_clearance_authorized": False,
        },
    )
    propose_challenge(root, request)
    return request
