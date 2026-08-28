"""Automatic, authority-bounded Decision Preflight runtime.

Meditate runs only on represented decision state. Quantitative value-of-computation is
used only for complete, finite probability/utility/cost models. Otherwise the module
uses explicit ordinal dominance or remains UNKNOWN. It can clear only a PREFLIGHT
obligation; it never authorizes the selected action or clears a target-domain claim.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from numbers import Real
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    EvidenceClass,
    EvidenceRef,
    ObligationKind,
    Receipt,
    Verdict,
    canonical_json,
    digest,
    text_digest,
)
from gauntlet_config import load_config

MEDITATE_SCHEMA = "egrt.meditate.preflight.v2"
_TIE_TOLERANCE = 1e-12
_RANK_MIN = 0
_RANK_MAX = 5
_TRIGGER_FIELDS = (
    "high_stakes",
    "irreversible",
    "stale_authority",
    "repeated_failure",
    "decision_sensitive_unknowns",
    "major_disagreement",
)


class MeditateAuthorityError(ValueError):
    """Raised when Meditate is asked to act outside PREFLIGHT authority."""


def _nonempty_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite_real(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _rank(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer or None")
    if not _RANK_MIN <= value <= _RANK_MAX:
        raise ValueError(f"{name} must be between {_RANK_MIN} and {_RANK_MAX}")
    return value


@dataclass(frozen=True)
class PreflightTriggers:
    high_stakes: bool = False
    irreversible: bool = False
    stale_authority: bool = False
    repeated_failure: bool = False
    decision_sensitive_unknowns: bool = False
    major_disagreement: bool = False

    def __post_init__(self) -> None:
        for name in _TRIGGER_FIELDS:
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")

    def should_run(self) -> bool:
        return any(getattr(self, name) for name in _TRIGGER_FIELDS)

    def merged(self, *others: PreflightTriggers) -> PreflightTriggers:
        return PreflightTriggers(
            **{
                name: any(getattr(item, name) for item in (self, *others))
                for name in _TRIGGER_FIELDS
            }
        )


@dataclass(frozen=True)
class QuantitativeOutcome:
    probability: float
    best_eu_after: float

    def __post_init__(self) -> None:
        probability = _finite_real(self.probability, "probability")
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        _finite_real(self.best_eu_after, "best_eu_after")


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    label: str
    cost: float | None = None
    outcomes: tuple[QuantitativeOutcome, ...] = ()
    info_rank: int | None = None
    progress_rank: int | None = None
    risk_reduction_rank: int | None = None
    cost_rank: int | None = None
    reversible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nonempty_text(self.action_id, "action_id")
        _nonempty_text(self.label, "label")
        if self.cost is not None:
            cost = _finite_real(self.cost, "cost")
            if cost < 0:
                raise ValueError("quantitative action cost must be non-negative")
        if not isinstance(self.outcomes, tuple):
            raise TypeError("outcomes must be a tuple")
        if any(not isinstance(outcome, QuantitativeOutcome) for outcome in self.outcomes):
            raise TypeError("outcomes must contain QuantitativeOutcome values")
        _rank(self.info_rank, "info_rank")
        _rank(self.progress_rank, "progress_rank")
        _rank(self.risk_reduction_rank, "risk_reduction_rank")
        _rank(self.cost_rank, "cost_rank")
        if not isinstance(self.reversible, bool):
            raise TypeError("reversible must be bool")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")

    @property
    def quantitative_declared(self) -> bool:
        return self.cost is not None or bool(self.outcomes)

    @property
    def quantitative_complete(self) -> bool:
        return self.cost is not None and bool(self.outcomes)

    @property
    def ordinal_declared(self) -> bool:
        return any(
            value is not None
            for value in (
                self.info_rank,
                self.progress_rank,
                self.risk_reduction_rank,
                self.cost_rank,
            )
        )

    @property
    def ordinal_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.info_rank,
                self.progress_rank,
                self.risk_reduction_rank,
                self.cost_rank,
            )
        )

    def voc(self, current_best_eu: float | None) -> float | None:
        if not self.quantitative_complete or current_best_eu is None:
            return None
        baseline = _finite_real(current_best_eu, "current_best_eu")
        total_probability = sum(outcome.probability for outcome in self.outcomes)
        if abs(total_probability - 1.0) > 1e-9:
            raise ValueError("quantitative outcome probabilities must sum to 1")
        expected_after = sum(
            outcome.probability * outcome.best_eu_after for outcome in self.outcomes
        )
        expected_after = _finite_real(expected_after, "expected_after")
        value = expected_after - baseline - float(self.cost)
        return _finite_real(value, "value_of_computation")


@dataclass
class DecisionState:
    decision_id: str
    task_id: str | None
    goal: str
    success_condition: str
    authoritative_artifacts: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[dict[str, Any]] = field(default_factory=list)
    actions: list[CandidateAction] = field(default_factory=list)
    current_blocker: str | None = None
    current_best_eu: float | None = None
    triggers: PreflightTriggers = field(default_factory=PreflightTriggers)

    def __post_init__(self) -> None:
        _nonempty_text(self.decision_id, "decision_id")
        if self.task_id is not None:
            _nonempty_text(self.task_id, "task_id")
        _nonempty_text(self.goal, "goal")
        _nonempty_text(self.success_condition, "success_condition")
        for name in (
            "authoritative_artifacts",
            "facts",
            "assumptions",
            "unknowns",
        ):
            rows = getattr(self, name)
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise TypeError(f"{name} must be a list of dict values")
        if not isinstance(self.actions, list) or any(
            not isinstance(action, CandidateAction) for action in self.actions
        ):
            raise TypeError("actions must be a list of CandidateAction values")
        identifiers = [action.action_id for action in self.actions]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("candidate action IDs must be unique")
        if self.current_blocker is not None:
            _nonempty_text(self.current_blocker, "current_blocker")
        if self.current_best_eu is not None:
            _finite_real(self.current_best_eu, "current_best_eu")
        if not isinstance(self.triggers, PreflightTriggers):
            raise TypeError("triggers must be PreflightTriggers")


def _dominates(a: CandidateAction, b: CandidateAction) -> bool:
    if not a.ordinal_complete or not b.ordinal_complete:
        return False
    a_benefits = (a.info_rank, a.progress_rank, a.risk_reduction_rank)
    b_benefits = (b.info_rank, b.progress_rank, b.risk_reduction_rank)
    benefits_ge = all(x >= y for x, y in zip(a_benefits, b_benefits))
    cost_le = a.cost_rank <= b.cost_rank
    strict = any(x > y for x, y in zip(a_benefits, b_benefits)) or (
        a.cost_rank < b.cost_rank
    )
    return benefits_ge and cost_le and strict


def _result(
    verdict: Verdict,
    decision: str,
    mode: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "verdict": verdict.value,
        "decision": decision,
        "mode": mode,
        "authority": "PREFLIGHT_ONLY",
        "execution_authorized": False,
        "target_domain_clearance_authorized": False,
        "trigger_scope": "TYPED_REPRESENTED_STATE_ONLY",
        "trigger_completeness_established": False,
        **extra,
    }


def _effective_triggers(state: DecisionState) -> PreflightTriggers:
    irreversible = PreflightTriggers(
        irreversible=any(not action.reversible for action in state.actions)
    )
    return state.triggers.merged(irreversible)


def recommend(state: DecisionState) -> dict[str, Any]:
    if not isinstance(state, DecisionState):
        raise TypeError("state must be DecisionState")
    triggers = _effective_triggers(state)
    trigger_record = asdict(triggers)
    if not triggers.should_run():
        return _result(
            Verdict.CLEARED,
            "SKIP",
            "NOT_TRIGGERED",
            reason="preflight trigger absent",
            effective_triggers=trigger_record,
        )
    if not state.actions:
        return _result(
            Verdict.UNKNOWN,
            "CONTINUE",
            "NO_ACTIONS",
            reason="no candidate action represented",
            effective_triggers=trigger_record,
        )

    quantitative_declared = any(action.quantitative_declared for action in state.actions)
    if quantitative_declared:
        if state.current_best_eu is None or not all(
            action.quantitative_complete for action in state.actions
        ):
            return _result(
                Verdict.UNKNOWN,
                "CONTINUE",
                "PARTIAL_QUANTITATIVE_MODEL",
                reason=(
                    "quantitative comparison requires one shared finite baseline and "
                    "complete cost/outcome models for every candidate"
                ),
                effective_triggers=trigger_record,
            )
        vocs = sorted(
            (
                (float(action.voc(state.current_best_eu)), action.action_id)
                for action in state.actions
            ),
            key=lambda row: row[1],
        )
        max_voc = max(value for value, _ in vocs)
        if max_voc <= 0:
            return _result(
                Verdict.CLEARED,
                "RELEASE",
                "QUANTITATIVE_VOC",
                max_voc=max_voc,
                effective_triggers=trigger_record,
            )
        best_ids = sorted(
            action_id
            for value, action_id in vocs
            if math.isclose(value, max_voc, rel_tol=0.0, abs_tol=_TIE_TOLERANCE)
        )
        if len(best_ids) != 1:
            return _result(
                Verdict.UNKNOWN,
                "CONTINUE",
                "QUANTITATIVE_TIE",
                max_voc=max_voc,
                nondominated=best_ids,
                reason="multiple candidate actions share the maximum represented VOC",
                effective_triggers=trigger_record,
            )
        return _result(
            Verdict.CLEARED,
            "ACT",
            "QUANTITATIVE_VOC",
            action_id=best_ids[0],
            max_voc=max_voc,
            effective_triggers=trigger_record,
        )

    ordinal_declared = any(action.ordinal_declared for action in state.actions)
    if not ordinal_declared:
        return _result(
            Verdict.UNKNOWN,
            "CONTINUE",
            "INSUFFICIENT_MODEL",
            reason="neither a quantitative model nor ordinal ranks are represented",
            effective_triggers=trigger_record,
        )
    if not all(action.ordinal_complete for action in state.actions):
        return _result(
            Verdict.UNKNOWN,
            "CONTINUE",
            "PARTIAL_ORDINAL_MODEL",
            reason="ordinal comparison requires all four ranks for every candidate",
            effective_triggers=trigger_record,
        )
    if all(
        action.info_rank == 0
        and action.progress_rank == 0
        and action.risk_reduction_rank == 0
        for action in state.actions
    ):
        return _result(
            Verdict.CLEARED,
            "RELEASE",
            "ORDINAL_HEURISTIC",
            evidence_class=EvidenceClass.HEURISTIC.value,
            effective_triggers=trigger_record,
        )

    nondominated = sorted(
        action.action_id
        for action in state.actions
        if not any(
            _dominates(other, action)
            for other in state.actions
            if other.action_id != action.action_id
        )
    )
    if len(nondominated) == 1:
        return _result(
            Verdict.CLEARED,
            "ACT",
            "ORDINAL_HEURISTIC",
            evidence_class=EvidenceClass.HEURISTIC.value,
            action_id=nondominated[0],
            effective_triggers=trigger_record,
        )
    return _result(
        Verdict.UNKNOWN,
        "CONTINUE",
        "ORDINAL_HEURISTIC",
        evidence_class=EvidenceClass.HEURISTIC.value,
        nondominated=nondominated,
        reason="represented ordinal model does not identify one action",
        effective_triggers=trigger_record,
    )


def _explicit_true(metadata: Mapping[str, Any], key: str) -> bool:
    return metadata.get(key) is True


def _task_metadata_flags(task: Mapping[str, Any]) -> PreflightTriggers:
    metadata = task.get("metadata")
    task_metadata = metadata if isinstance(metadata, Mapping) else {}
    obligation_metadata = [
        row.get("metadata")
        for row in task.get("obligations", [])
        if isinstance(row, Mapping) and isinstance(row.get("metadata"), Mapping)
    ]

    def represented(key: str) -> bool:
        return _explicit_true(task_metadata, key) or any(
            _explicit_true(row, key) for row in obligation_metadata
        )

    return PreflightTriggers(
        high_stakes=represented("high_stakes"),
        irreversible=represented("irreversible"),
        decision_sensitive_unknowns=represented("decision_sensitive_unknowns"),
        major_disagreement=represented("major_disagreement"),
    )


def _event_flags(events: Sequence[Mapping[str, Any]]) -> PreflightTriggers:
    latest_snapshot: str | None = None
    latest_changed: str | None = None
    failure_signatures: list[str] = []
    major_disagreement = False
    for event in events:
        event_type = event.get("event_type")
        metadata = event.get("metadata")
        event_metadata = metadata if isinstance(metadata, Mapping) else {}
        stamp = str(event.get("timestamp") or "")
        if event_type == "authority.snapshot":
            latest_snapshot = max(latest_snapshot or "", stamp)
        elif event_type == "authority.changed":
            latest_changed = max(latest_changed or "", stamp)
        elif event_type == "action.failed":
            signature = event_metadata.get("failure_signature")
            failure_signatures.append(
                str(
                    signature
                    or event.get("payload_hash")
                    or event.get("event_id")
                    or "unidentified-failure"
                )
            )
        elif event_type in {"review.disagreement", "council.disagreement"}:
            major_disagreement = (
                major_disagreement or event_metadata.get("major") is True
            )

    counts = Counter(failure_signatures)
    repeated_failure = len(failure_signatures) >= 3 or any(
        count >= 2 for count in counts.values()
    )
    stale_authority = bool(latest_changed) and (
        not latest_snapshot or latest_changed >= latest_snapshot
    )
    return PreflightTriggers(
        stale_authority=stale_authority,
        repeated_failure=repeated_failure,
        major_disagreement=major_disagreement,
    )


def derive_triggers(
    root: Path,
    task_id: str,
    state: DecisionState | None = None,
) -> PreflightTriggers:
    """Derive conservative triggers from typed task/event state only."""

    _nonempty_text(task_id, "task_id")
    store = RuntimeStore(root)
    task = store.read_task(task_id)
    if task is None:
        raise KeyError(f"unknown or integrity-invalid task {task_id}")
    unknown_trigger = PreflightTriggers(
        decision_sensitive_unknowns=bool(
            state
            and any(row.get("decision_sensitive") is True for row in state.unknowns)
        ),
        irreversible=bool(
            state and any(not action.reversible for action in state.actions)
        ),
    )
    return _task_metadata_flags(task).merged(
        _event_flags(store.iter_events(task_id)),
        unknown_trigger,
    )


def _obligation_row(
    task: Mapping[str, Any],
    obligation_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            item
            for item in task.get("obligations", [])
            if isinstance(item, Mapping) and item.get("obligation_id") == obligation_id
        ),
        None,
    )


def _candidate_task_bindings(
    store: RuntimeStore,
    obligation_id: str,
) -> list[tuple[str, dict[str, Any], Mapping[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
    for task_path in sorted(store.tasks.glob("*.json")):
        task_id = task_path.stem
        task = store.read_task(task_id)
        if task is None:
            continue
        row = _obligation_row(task, obligation_id)
        if row is not None:
            candidates.append((task_id, task, row))
    return candidates


def _resolve_task_binding(
    store: RuntimeStore,
    state: DecisionState,
    obligation_id: str,
) -> tuple[str | None, dict[str, Any] | None, Mapping[str, Any] | None]:
    """Resolve one current open task without importing Soul's control plane."""

    _nonempty_text(obligation_id, "obligation_id")
    candidates = _candidate_task_bindings(store, obligation_id)

    if state.task_id is not None:
        task = store.read_task(state.task_id)
        if task is None:
            raise MeditateAuthorityError("bound task is missing or integrity-invalid")
        row = _obligation_row(task, obligation_id)
        if row is None:
            raise MeditateAuthorityError(
                "preflight obligation is not present on the bound task"
            )
        selected = (state.task_id, task, row)
    else:
        active = [
            candidate
            for candidate in candidates
            if candidate[1].get("active", True) is True
            and candidate[1].get("released", False) is False
        ]
        if len(active) == 1:
            selected = active[0]
        elif len(active) > 1:
            raise MeditateAuthorityError(
                "preflight obligation is ambiguously bound to multiple active tasks"
            )
        elif len(candidates) == 1:
            selected = candidates[0]
        elif len(candidates) > 1:
            raise MeditateAuthorityError(
                "preflight obligation is ambiguously bound to multiple task revisions"
            )
        else:
            return None, None, None

    task_id, task, row = selected
    if task.get("released", False) is True or task.get("active", True) is not True:
        raise MeditateAuthorityError("preflight task is not an active open task")
    return task_id, task, row


def _task_binding(
    store: RuntimeStore,
    state: DecisionState,
    obligation_id: str,
) -> tuple[str | None, bool, str | None, str | None]:
    task_id, task, row = _resolve_task_binding(store, state, obligation_id)
    if task_id is None or task is None or row is None:
        return None, False, None, None
    if row.get("kind") != ObligationKind.PREFLIGHT.value:
        raise MeditateAuthorityError("Meditate may clear only a PREFLIGHT obligation")
    if row.get("required_module") not in (None, "meditate"):
        raise MeditateAuthorityError("preflight obligation is assigned to another module")
    return (
        task_id,
        True,
        str(task.get("content_hash") or digest(task)),
        digest(row),
    )


def _sanitized_state_record(
    state: DecisionState,
    result: Mapping[str, Any],
    task_id: str | None,
    bound: bool,
    task_content_hash: str | None,
    obligation_binding_hash: str | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": MEDITATE_SCHEMA,
        "decision_id": state.decision_id,
        "task_id": task_id,
        "goal_hash": text_digest(state.goal),
        "success_condition_hash": text_digest(state.success_condition),
        "authoritative_artifact_hashes": [
            digest(row) for row in state.authoritative_artifacts
        ],
        "fact_hashes": [digest(row) for row in state.facts],
        "assumption_hashes": [digest(row) for row in state.assumptions],
        "unknown_hashes": [digest(row) for row in state.unknowns],
        "actions": [
            {
                "action_id": action.action_id,
                "label_hash": text_digest(action.label),
                "model_hash": digest(action),
                "quantitative_declared": action.quantitative_declared,
                "ordinal_declared": action.ordinal_declared,
                "reversible": action.reversible,
            }
            for action in state.actions
        ],
        "current_blocker_hash": (
            text_digest(state.current_blocker) if state.current_blocker else None
        ),
        "current_best_eu_present": state.current_best_eu is not None,
        "triggers": asdict(state.triggers),
        "result": dict(result),
        "authority": "PREFLIGHT_ONLY",
        "task_binding_established": bound,
        "task_content_hash": task_content_hash,
        "obligation_binding_hash": obligation_binding_hash,
        "represented_state_completeness_established": False,
        "execution_authorized": False,
        "target_domain_clearance_authorized": False,
        "raw_goal_persisted": False,
        "raw_success_condition_persisted": False,
        "raw_action_labels_persisted": False,
    }
    record["content_hash"] = digest(record)
    return record


def _parse_state(raw: Mapping[str, Any]) -> DecisionState:
    if not isinstance(raw, Mapping):
        raise TypeError("state must be a mapping")
    raw_triggers = raw.get("triggers") or {}
    if not isinstance(raw_triggers, Mapping):
        raise TypeError("triggers must be a mapping")
    raw_actions = raw.get("actions") or []
    if not isinstance(raw_actions, list):
        raise TypeError("actions must be a list")
    triggers = PreflightTriggers(**dict(raw_triggers))
    actions: list[CandidateAction] = []
    for raw_action in raw_actions:
        if not isinstance(raw_action, Mapping):
            raise TypeError("each action must be a mapping")
        raw_outcomes = raw_action.get("outcomes") or []
        if not isinstance(raw_outcomes, (list, tuple)):
            raise TypeError("action outcomes must be a list or tuple")
        outcomes: list[QuantitativeOutcome] = []
        for raw_outcome in raw_outcomes:
            if not isinstance(raw_outcome, Mapping):
                raise TypeError("each quantitative outcome must be a mapping")
            outcomes.append(QuantitativeOutcome(**dict(raw_outcome)))
        actions.append(
            CandidateAction(
                **{
                    **dict(raw_action),
                    "outcomes": tuple(outcomes),
                }
            )
        )
    return DecisionState(**{**dict(raw), "triggers": triggers, "actions": actions})


def _snapshot_state(state: DecisionState) -> DecisionState:
    """Copy caller-owned mutable structures before evaluation and content binding."""

    return _parse_state(json.loads(canonical_json(state)))


def run_preflight(root: Path, state: DecisionState, obligation_id: str) -> Receipt:
    if not isinstance(state, DecisionState):
        raise TypeError("state must be DecisionState")
    state = _snapshot_state(state)
    store = RuntimeStore(root)
    task_id, bound, task_content_hash, obligation_binding_hash = _task_binding(
        store,
        state,
        obligation_id,
    )
    if bound and task_id is not None:
        state = replace(
            state,
            task_id=task_id,
            triggers=state.triggers.merged(derive_triggers(root, task_id, state)),
        )
    result = recommend(state)
    if not bound and result["verdict"] == Verdict.CLEARED.value:
        result = _result(
            Verdict.UNKNOWN,
            "CONTINUE",
            "UNBOUND_PREFLIGHT",
            reason="a clearing preflight verdict requires a task-bound PREFLIGHT obligation",
            original_mode=result["mode"],
        )
    state_record = _sanitized_state_record(
        state,
        result,
        task_id,
        bound,
        task_content_hash,
        obligation_binding_hash,
    )
    store.write_named_state("meditate", state.decision_id, state_record)
    evidence_class = (
        EvidenceClass.HEURISTIC
        if result.get("mode") == "ORDINAL_HEURISTIC"
        else EvidenceClass.DERIVED
    )
    unresolved = tuple(
        str(value)
        for value in result.get("nondominated", [])
        if isinstance(value, str)
    )
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="meditate",
        obligation_id=obligation_id,
        verdict=Verdict(result["verdict"]),
        action=f"preflight:{result['decision']}",
        input_hash=digest(state),
        output_hash=digest(result),
        evidence=(
            EvidenceRef(
                evidence_class=evidence_class,
                verifier="meditate_runtime:v2",
                provenance_group="meditate-control",
                metadata={
                    "decision_state_hash": state_record["content_hash"],
                    "authority": "PREFLIGHT_ONLY",
                    "execution_authorized": False,
                    "trigger_scope": "TYPED_REPRESENTED_STATE_ONLY",
                    "trigger_completeness_established": False,
                    "task_content_hash": task_content_hash,
                    "obligation_binding_hash": obligation_binding_hash,
                },
            ),
        ),
        verifier="meditate_runtime:v2",
        tool_version=MEDITATE_SCHEMA,
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=unresolved,
        notes=json.dumps(result, sort_keys=True),
        task_id=task_id,
    )
    store.write_receipt(receipt)
    return receipt


def run_automatic_preflight(
    root: Path,
    state: DecisionState,
    obligation_id: str,
) -> Receipt:
    """Merge represented automatic triggers and execute one bounded preflight."""

    if not isinstance(state, DecisionState):
        raise TypeError("state must be DecisionState")
    state = _snapshot_state(state)
    store = RuntimeStore(root)
    inferred, _, _ = _resolve_task_binding(store, state, obligation_id)
    if inferred is None:
        return run_preflight(root, state, obligation_id)
    derived = derive_triggers(root, inferred, state)
    automatic_state = replace(
        state,
        task_id=inferred,
        triggers=state.triggers.merged(derived),
    )
    return run_preflight(root, automatic_state, obligation_id)


def _automatic_enabled(root: Path) -> bool:
    runtime = load_config(root).get("runtime") or {}
    if not isinstance(runtime, Mapping):
        return False
    value = runtime.get("automatic_preflight", False)
    return value is True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state_file")
    parser.add_argument("--root", default=".")
    parser.add_argument("--obligation", required=True)
    parser.add_argument("--automatic", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    raw = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("state file must contain a JSON object")
    state = _parse_state(raw)
    automatic = args.automatic or _automatic_enabled(root)
    runner = run_automatic_preflight if automatic else run_preflight
    receipt = runner(root, state, args.obligation)
    print(
        json.dumps(
            {
                "receipt_id": receipt.receipt_id,
                "verdict": receipt.verdict.value,
                "notes": receipt.notes,
            },
            indent=2,
        )
    )
    return 0 if receipt.verdict == Verdict.CLEARED else 2


__all__ = [
    "CandidateAction",
    "DecisionState",
    "MEDITATE_SCHEMA",
    "MeditateAuthorityError",
    "PreflightTriggers",
    "QuantitativeOutcome",
    "derive_triggers",
    "recommend",
    "run_automatic_preflight",
    "run_preflight",
]


if __name__ == "__main__":
    raise SystemExit(main())
