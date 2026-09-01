"""Foundry method-synthesis candidate schema and evidence-gated admission."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest


@dataclass(frozen=True)
class MethodCandidate:
    candidate_id: str
    obligation_id: str
    gap: str
    failed_constraint: str
    changed_assumption: str
    mechanism: str
    nearest_prior_art: tuple[str, ...]
    actual_delta: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    invariants: tuple[str, ...]
    dependencies: tuple[str, ...]
    failure_modes: tuple[str, ...]
    negative_control: str
    transfer_target: str
    ablation_plan: str
    verifier_plan: str
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


REQUIRED_TEXT = (
    "gap", "failed_constraint", "changed_assumption", "mechanism", "actual_delta",
    "negative_control", "transfer_target", "ablation_plan", "verifier_plan",
)


def admission(candidate: MethodCandidate, prior_art_receipts: list[dict[str, Any]]) -> tuple[Verdict, list[str]]:
    errors = [name for name in REQUIRED_TEXT if not str(getattr(candidate, name)).strip()]
    if not candidate.nearest_prior_art:
        errors.append("nearest_prior_art")
    if not candidate.failure_modes:
        errors.append("failure_modes")
    def is_assessed_discovery(r: dict[str, Any]) -> bool:
        if r.get("module") != "space" or r.get("verdict") != Verdict.CLEARED.value or r.get("action") != "source-assessment":
            return False
        evidence = r.get("evidence") or []
        return any(
            isinstance(e, dict)
            and e.get("evidence_class") == EvidenceClass.CITED.value
            and isinstance(e.get("artifact"), dict)
            and bool(e["artifact"].get("sha256"))
            for e in evidence
        )
    cleared_discovery = any(is_assessed_discovery(r) for r in prior_art_receipts)
    if not cleared_discovery:
        errors.append("cleared source-assessment prior-art receipt with hashed cited evidence")
    if errors:
        return Verdict.UNKNOWN, errors
    return Verdict.CLEARED, []


def diversity_matrix(candidates: list[MethodCandidate]) -> dict[str, Any]:
    pairs = []
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            tags_a, tags_b = set(a.tags), set(b.tags)
            union = tags_a | tags_b
            pairs.append({
                "a": a.candidate_id, "b": b.candidate_id,
                "changed_assumption_same": a.changed_assumption.strip().lower() == b.changed_assumption.strip().lower(),
                "mechanism_same": a.mechanism.strip().lower() == b.mechanism.strip().lower(),
                "tag_jaccard": len(tags_a & tags_b) / len(union) if union else 1.0,
            })
    return {"pairs": pairs}


def record_candidate(root: Path, candidate: MethodCandidate, prior_art_receipt_ids: list[str]) -> Receipt:
    store = RuntimeStore(root)
    prior_art_receipts = [r for rid in prior_art_receipt_ids if (r := store.read_receipt(rid)) is not None]
    verdict, missing = admission(candidate, prior_art_receipts)
    store.write_named_state("reality", candidate.candidate_id, json.loads(json.dumps(candidate, default=lambda o: o.__dict__)))
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="reality", obligation_id=candidate.obligation_id,
        verdict=verdict, action="candidate-admission", input_hash=digest(candidate), output_hash=digest({"missing": missing, "verdict": verdict.value}),
        evidence=(EvidenceRef(evidence_class=EvidenceClass.DERIVED, verifier="reality_runtime", metadata={
            "admission_only": True,
            "novelty_status": "UNKNOWN_UNTIL_SEARCH_SCOPE_SUPPORTS_DELTA",
            "prior_art_receipt_ids": prior_art_receipt_ids,
        }),),
        verifier="reality_runtime", started_at=utcnow(), finished_at=utcnow(), unresolved=tuple(missing),
        notes="Admission means the candidate is well-specified enough to test; it does not prove novelty or efficacy. Prior-art receipts are resolved from the private receipt store, not caller-supplied dicts.",
    )
    store.write_receipt(receipt)
    return receipt
