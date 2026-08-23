"""Decision Preflight runtime grounded in explicit state and value-of-computation.

Quantitative VOC is used only when the caller supplies probabilities/utilities/costs.
Otherwise the module uses ordinal dominance and labels the result HEURISTIC/UNKNOWN;
it never fabricates pseudo-precise numerical values.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest


@dataclass(frozen=True)
class PreflightTriggers:
    high_stakes: bool = False
    irreversible: bool = False
    stale_authority: bool = False
    repeated_failure: bool = False
    decision_sensitive_unknowns: bool = False
    major_disagreement: bool = False

    def should_run(self) -> bool:
        return any(self.__dict__.values())


@dataclass(frozen=True)
class QuantitativeOutcome:
    probability: float
    best_eu_after: float


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

    def voc(self, current_best_eu: float | None) -> float | None:
        if self.cost is None or current_best_eu is None or not self.outcomes:
            return None
        if self.cost < 0:
            raise ValueError("quantitative action cost must be non-negative")
        total_p = sum(o.probability for o in self.outcomes)
        if abs(total_p - 1.0) > 1e-9 or any(not 0 <= o.probability <= 1 for o in self.outcomes):
            raise ValueError("quantitative outcome probabilities must be in [0,1] and sum to 1")
        return sum(o.probability * o.best_eu_after for o in self.outcomes) - current_best_eu - self.cost


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


def _dominates(a: CandidateAction, b: CandidateAction) -> bool:
    av = (a.info_rank, a.progress_rank, a.risk_reduction_rank)
    bv = (b.info_rank, b.progress_rank, b.risk_reduction_rank)
    if any(v is None for v in (*av, *bv, a.cost_rank, b.cost_rank)):
        return False
    benefits_ge = all(x >= y for x, y in zip(av, bv))
    cost_le = a.cost_rank <= b.cost_rank
    strict = any(x > y for x, y in zip(av, bv)) or a.cost_rank < b.cost_rank
    return benefits_ge and cost_le and strict


def recommend(state: DecisionState) -> dict[str, Any]:
    if not state.triggers.should_run():
        return {"verdict": Verdict.CLEARED.value, "decision": "SKIP", "mode": "NOT_TRIGGERED", "reason": "preflight trigger absent"}
    if not state.actions:
        return {"verdict": Verdict.UNKNOWN.value, "decision": "CONTINUE", "mode": "NO_ACTIONS", "reason": "no candidate action represented"}

    vocs = []
    quantitative = True
    for action in state.actions:
        value = action.voc(state.current_best_eu)
        if value is None:
            quantitative = False
            break
        vocs.append((value, action))
    if quantitative:
        best_voc, best = max(vocs, key=lambda x: x[0])
        if best_voc <= 0:
            return {"verdict": Verdict.CLEARED.value, "decision": "RELEASE", "mode": "QUANTITATIVE_VOC", "max_voc": best_voc}
        return {"verdict": Verdict.CLEARED.value, "decision": "ACT", "mode": "QUANTITATIVE_VOC", "action_id": best.action_id, "max_voc": best_voc}

    complete_ordinal = all(
        all(v is not None for v in (a.info_rank, a.progress_rank, a.risk_reduction_rank, a.cost_rank))
        for a in state.actions
    )
    if not complete_ordinal:
        return {"verdict": Verdict.UNKNOWN.value, "decision": "CONTINUE", "mode": "INSUFFICIENT_MODEL", "reason": "neither quantitative VOC nor complete ordinal comparison is available"}

    if all((a.info_rank or 0) == 0 and (a.progress_rank or 0) == 0 and (a.risk_reduction_rank or 0) == 0 for a in state.actions):
        return {"verdict": Verdict.CLEARED.value, "decision": "RELEASE", "mode": "ORDINAL_HEURISTIC", "evidence_class": EvidenceClass.HEURISTIC.value}

    nondominated = [a for a in state.actions if not any(_dominates(other, a) for other in state.actions if other.action_id != a.action_id)]
    if len(nondominated) == 1:
        return {"verdict": Verdict.CLEARED.value, "decision": "ACT", "mode": "ORDINAL_HEURISTIC", "evidence_class": EvidenceClass.HEURISTIC.value, "action_id": nondominated[0].action_id}
    return {"verdict": Verdict.UNKNOWN.value, "decision": "CONTINUE", "mode": "ORDINAL_HEURISTIC", "evidence_class": EvidenceClass.HEURISTIC.value, "nondominated": [a.action_id for a in nondominated]}


def run_preflight(root: Path, state: DecisionState, obligation_id: str) -> Receipt:
    store = RuntimeStore(root)
    result = recommend(state)
    store.write_named_state("meditate", state.decision_id, json.loads(json.dumps(state, default=lambda o: o.__dict__)))
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="meditate",
        obligation_id=obligation_id,
        verdict=Verdict(result["verdict"]),
        action=f"preflight:{result['decision']}",
        input_hash=digest(state),
        output_hash=digest(result),
        evidence=(EvidenceRef(evidence_class=EvidenceClass.HEURISTIC if "HEURISTIC" in result.get("mode", "") else EvidenceClass.DERIVED, verifier="meditate_runtime"),),
        verifier="meditate_runtime",
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(result.get("nondominated", [])) if result["verdict"] == Verdict.UNKNOWN.value else (),
        notes=json.dumps(result, sort_keys=True),
    )
    store.write_receipt(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("state_file")
    p.add_argument("--root", default=".")
    p.add_argument("--obligation", required=True)
    args = p.parse_args(argv)
    raw = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
    raw["triggers"] = PreflightTriggers(**raw.get("triggers", {}))
    raw["actions"] = [CandidateAction(**{**a, "outcomes": tuple(QuantitativeOutcome(**o) for o in a.get("outcomes", []))}) for a in raw.get("actions", [])]
    state = DecisionState(**raw)
    receipt = run_preflight(Path(args.root).resolve(), state, args.obligation)
    print(json.dumps({"receipt_id": receipt.receipt_id, "verdict": receipt.verdict.value, "notes": receipt.notes}, indent=2))
    return 0 if receipt.verdict == Verdict.CLEARED else 2


if __name__ == "__main__":
    raise SystemExit(main())
