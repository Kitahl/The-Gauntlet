"""Neutral challenge lifecycle, selection, resolution, and gate logic.

Challenge proposals carry no factual authority. Only a receipt from the declared
claim-native verifier may resolve a challenge, and the resolution never substitutes
for the original domain receipt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Sequence

from egrt_challenge_types import (
    ChallengeOrigin,
    ChallengeRequest,
    ChallengeResolution,
    ChallengeState,
    DiscriminatorPlan,
    ResolutionOutcome,
)
from egrt_store import RuntimeStore, new_id
from egrt_types import Verdict, digest
from gauntlet_config import challenge_config


class ChallengeError(ValueError):
    """Base error for invalid challenge operations."""


class ChallengeSelectionError(ChallengeError):
    """Raised when no unique minimum discriminator is defensible."""


@dataclass(frozen=True)
class ChallengePolicy:
    mode: str = "shadow"
    max_total_per_obligation: int = 4
    max_load_bearing_per_obligation: int = 2
    max_selected_discriminators: int = 2
    allow_foil_proposals: bool = True
    require_claim_native_receipt: bool = True
    block_on_unavailable_load_bearing: bool = True
    persist_raw_text: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"off", "shadow", "enforced"}:
            raise ValueError("mode must be off, shadow, or enforced")
        for name in (
            "max_total_per_obligation",
            "max_load_bearing_per_obligation",
            "max_selected_discriminators",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in (
            "allow_foil_proposals",
            "require_claim_native_receipt",
            "block_on_unavailable_load_bearing",
            "persist_raw_text",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")

    @classmethod
    def from_root(cls, root: Path) -> "ChallengePolicy":
        raw = challenge_config(root)
        names = {item.name for item in fields(cls)}
        return cls(**{name: raw[name] for name in names if name in raw})


def _plain(value: Any) -> dict[str, Any]:
    return asdict(value) if hasattr(value, "__dataclass_fields__") else dict(value)


def _dedupe_key(request: ChallengeRequest | dict[str, Any]) -> str:
    row = _plain(request)
    return digest({
        "task_id": row.get("task_id"),
        "obligation_id": row.get("obligation_id"),
        "candidate_hash": row.get("candidate_hash"),
        "scope_hash": row.get("scope_hash"),
        "kind": getattr(row.get("kind"), "value", row.get("kind")),
        "refuter": row.get("refuter"),
    })


def propose_challenge(root: Path, request: ChallengeRequest) -> Path:
    policy = ChallengePolicy.from_root(root)
    if policy.mode == "off":
        raise ChallengeError("challenge layer is OFF")
    if request.origin is ChallengeOrigin.FOIL and not policy.allow_foil_proposals:
        raise ChallengeError("FOIL proposals are disabled")
    store = RuntimeStore(root)
    existing = store.challenges_for(request.task_id, request.obligation_id)
    if len(existing) >= policy.max_total_per_obligation:
        raise ChallengeError("challenge budget exhausted for obligation")
    load_bearing = [row for row in existing if row.get("load_bearing")]
    if request.load_bearing and len(load_bearing) >= policy.max_load_bearing_per_obligation:
        raise ChallengeError("load-bearing challenge budget exhausted")
    key = _dedupe_key(request)
    if any(_dedupe_key(row) == key for row in existing):
        raise ChallengeError("duplicate challenge for candidate, scope, kind, and refuter")
    return store.write_challenge(request)


def _objective(plan: DiscriminatorPlan) -> tuple[int, int, int, int, int, int]:
    metadata = plan.metadata
    available = 1 if metadata.get("capability_available", True) else 0
    discrimination = int(metadata.get("discrimination_rank", 0))
    information = int(metadata.get("information_rank", 0))
    risk_reduction = int(metadata.get("risk_reduction_rank", 0))
    cost = plan.max_cost_rank if plan.max_cost_rank is not None else int(metadata.get("cost_rank", 0))
    irreversibility = int(metadata.get("irreversibility_rank", 0))
    return available, discrimination, information, risk_reduction, cost, irreversibility


def _dominates(left: DiscriminatorPlan, right: DiscriminatorPlan) -> bool:
    la, ld, li, lr, lc, lx = _objective(left)
    ra, rd, ri, rr, rc, rx = _objective(right)
    weak = la >= ra and ld >= rd and li >= ri and lr >= rr and lc <= rc and lx <= rx
    strict = la > ra or ld > rd or li > ri or lr > rr or lc < rc or lx < rx
    return weak and strict


def _plan_dedupe_key(plan: DiscriminatorPlan) -> str:
    return digest({
        "challenge_id": plan.challenge_id,
        "mode": plan.mode,
        "action": plan.action,
        "verifier_module": plan.verifier_module,
        "required_capability": plan.required_capability,
        "support": plan.expected_support_signal,
        "refute": plan.expected_refute_signal,
        "inputs": plan.input_artifacts,
    })


def select_minimum_discriminator(
    root: Path,
    challenge_id: str,
    plans: Sequence[DiscriminatorPlan],
    *,
    policy: ChallengePolicy,
) -> DiscriminatorPlan:
    store = RuntimeStore(root)
    challenge = store.read_challenge(challenge_id)
    if challenge is None:
        raise ChallengeSelectionError("challenge not found or corrupt")
    if not plans:
        raise ChallengeSelectionError("no discriminator plans supplied")
    if challenge.get("state") in {"RESOLVED", "DISMISSED_NOT_APPLICABLE"}:
        raise ChallengeSelectionError("terminal challenge cannot select a discriminator")

    unique: dict[str, DiscriminatorPlan] = {}
    for plan in plans:
        if plan.challenge_id != challenge_id:
            raise ChallengeSelectionError("plan is bound to a different challenge")
        key = _plan_dedupe_key(plan)
        current = unique.get(key)
        if current is None or plan.plan_id < current.plan_id:
            unique[key] = plan
    candidates = list(unique.values())
    available = [plan for plan in candidates if _objective(plan)[0] == 1]
    if available:
        candidates = available
    survivors = [
        plan for plan in candidates
        if not any(other is not plan and _dominates(other, plan) for other in candidates)
    ]
    if len(survivors) > 1:
        objectives = {_objective(plan) for plan in survivors}
        if len(objectives) == 1:
            survivors.sort(key=lambda item: item.plan_id)
            selected = survivors[0]
        else:
            store.update_challenge_state(
                challenge_id,
                "UNRESOLVED",
                reason="no_unique_dominating_discriminator",
            )
            raise ChallengeSelectionError("no unique dominating discriminator; host/module choice required")
    elif survivors:
        selected = survivors[0]
    else:  # pragma: no cover - defensive; finite non-empty Pareto set always exists
        raise ChallengeSelectionError("no admissible discriminator")

    selected_count = sum(
        1 for row in store.challenges_for(str(challenge["task_id"]), str(challenge["obligation_id"]))
        if row.get("selected_plan_id")
    )
    if selected_count >= policy.max_selected_discriminators and not challenge.get("selected_plan_id"):
        raise ChallengeSelectionError("selected discriminator budget exhausted")
    store.update_challenge_state(challenge_id, "SELECTED", selected_plan=_plain(selected))
    return selected


def record_resolution(root: Path, resolution: ChallengeResolution) -> Path:
    store = RuntimeStore(root)
    challenge = store.read_challenge(resolution.challenge_id)
    if challenge is None:
        raise ChallengeError("challenge not found or corrupt")
    valid, reason = validate_resolution_binding(store, challenge, _plain(resolution))
    if not valid:
        raise ChallengeError(reason)
    return store.write_challenge_resolution(resolution)


def open_challenges(
    root: Path,
    task_id: str,
    obligation_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = RuntimeStore(root).challenges_for(task_id, obligation_id)
    return [
        row for row in rows
        if row.get("state") not in {"RESOLVED", "DISMISSED_NOT_APPLICABLE"}
    ]


def validate_resolution_binding(
    store: RuntimeStore,
    challenge: dict[str, Any],
    resolution: dict[str, Any],
) -> tuple[bool, str]:
    if resolution.get("challenge_id") != challenge.get("challenge_id"):
        return False, "resolution challenge_id mismatch"
    for key in ("candidate_hash", "scope_hash", "obligation_set_hash"):
        if resolution.get(key) != challenge.get(key):
            return False, f"resolution {key} binding mismatch"
    state = getattr(resolution.get("state"), "value", resolution.get("state"))
    outcome = getattr(resolution.get("outcome"), "value", resolution.get("outcome"))
    receipt_id = resolution.get("verifier_receipt_id")
    verifier_module = resolution.get("verifier_module")
    if state == ChallengeState.RESOLVED.value:
        if not receipt_id or not verifier_module:
            return False, "resolved challenge requires claim-native receipt"
        receipt = store.read_receipt(str(receipt_id))
        if receipt is None:
            return False, "linked verifier receipt is missing or corrupt"
        if receipt.get("module") != verifier_module:
            return False, "linked verifier module mismatch"
        if receipt.get("obligation_id") != challenge.get("obligation_id"):
            return False, "linked verifier obligation mismatch"
        if receipt.get("task_id") not in (None, challenge.get("task_id")):
            return False, "linked verifier task mismatch"
        if outcome == ResolutionOutcome.SUPPORTS_BASE.value and receipt.get("verdict") != Verdict.CLEARED.value:
            return False, "SUPPORTS_BASE requires a CLEARED verifier receipt"
        if outcome == ResolutionOutcome.REFUTES_BASE.value and receipt.get("verdict") != Verdict.ISSUE.value:
            return False, "REFUTES_BASE requires an ISSUE verifier receipt"
        expected_hash = receipt.get("content_hash")
        evidence_hash = resolution.get("evidence_hash")
        if evidence_hash is not None and evidence_hash != expected_hash:
            return False, "resolution evidence_hash mismatch"
    elif receipt_id is not None or verifier_module is not None:
        receipt = store.read_receipt(str(receipt_id)) if receipt_id else None
        if receipt is None or receipt.get("module") != verifier_module:
            return False, "invalid optional linked verifier receipt"
    return True, "ok"


def _challenge_effect(store: RuntimeStore, challenge: dict[str, Any], policy: ChallengePolicy) -> tuple[Verdict, dict[str, Any]]:
    state = str(challenge.get("state") or ChallengeState.PROPOSED.value)
    detail: dict[str, Any] = {
        "challenge_id": challenge.get("challenge_id"),
        "kind": challenge.get("kind"),
        "state": state,
        "load_bearing": bool(challenge.get("load_bearing")),
    }
    if state == ChallengeState.DISMISSED_NOT_APPLICABLE.value:
        detail["outcome"] = "DISMISSED_NOT_APPLICABLE"
        return Verdict.CLEARED, detail
    resolution = store.latest_resolution(str(challenge.get("challenge_id")))
    if state == ChallengeState.RESOLVED.value:
        if resolution is None:
            detail["reason"] = "resolved_state_without_valid_resolution"
            return Verdict.UNKNOWN, detail
        valid, reason = validate_resolution_binding(store, challenge, resolution)
        if not valid:
            detail["reason"] = reason
            return Verdict.ISSUE, detail
        outcome = str(resolution.get("outcome"))
        detail.update({"outcome": outcome, "resolution_id": resolution.get("resolution_id")})
        if outcome == ResolutionOutcome.REFUTES_BASE.value:
            return Verdict.ISSUE, detail
        if outcome == ResolutionOutcome.SCOPE_SPLIT.value:
            return Verdict.UNKNOWN, detail
        if outcome == ResolutionOutcome.SUPPORTS_BASE.value:
            return Verdict.CLEARED, detail
        return Verdict.UNKNOWN, detail
    if state == ChallengeState.UNAVAILABLE.value:
        mandatory = bool(challenge.get("load_bearing")) and policy.block_on_unavailable_load_bearing
        detail["mandatory"] = mandatory
        return (Verdict.UNAVAILABLE if mandatory else Verdict.UNKNOWN), detail
    return Verdict.UNKNOWN, detail


def challenge_gate(
    root: Path,
    task_id: str,
    obligation_id: str,
    *,
    mode: str,
) -> tuple[Verdict, dict[str, Any]]:
    mode = mode.lower()
    if mode not in {"off", "shadow", "enforced"}:
        raise ValueError("mode must be off, shadow, or enforced")
    policy = ChallengePolicy.from_root(root)
    policy = ChallengePolicy(**{**asdict(policy), "mode": mode})
    if mode == "off":
        return Verdict.CLEARED, {
            "mode": "off", "applied": False, "status": "NOT_APPLICABLE",
            "task_id": task_id, "obligation_id": obligation_id, "challenges": [],
        }
    store = RuntimeStore(root)
    rows = [row for row in store.challenges_for(task_id, obligation_id) if row.get("load_bearing")]
    effects: list[tuple[Verdict, dict[str, Any]]] = [_challenge_effect(store, row, policy) for row in rows]
    verdict = Verdict.CLEARED
    severity = {Verdict.CLEARED: 0, Verdict.UNKNOWN: 1, Verdict.UNAVAILABLE: 2, Verdict.ISSUE: 3}
    for effect, _ in effects:
        if severity[effect] > severity[verdict]:
            verdict = effect
    detail = {
        "mode": mode,
        "applied": mode == "enforced",
        "task_id": task_id,
        "obligation_id": obligation_id,
        "load_bearing_count": len(rows),
        "challenges": [item for _, item in effects],
        "counterfactual_verdict": verdict.value,
    }
    if mode == "shadow":
        return Verdict.CLEARED, detail
    return verdict, detail


def resolution_for_receipt(
    root: Path,
    challenge_id: str,
    receipt_id: str,
    *,
    outcome: ResolutionOutcome,
    resolver: str,
    resolver_provenance: str | None = None,
    reason: str | None = None,
) -> ChallengeResolution:
    """Build a hash-bound resolution from an existing claim-native receipt."""
    store = RuntimeStore(root)
    challenge = store.read_challenge(challenge_id)
    if challenge is None:
        raise ChallengeError("challenge not found or corrupt")
    receipt = store.read_receipt(receipt_id)
    if receipt is None:
        raise ChallengeError("receipt not found or corrupt")
    return ChallengeResolution(
        resolution_id=new_id("cres"),
        challenge_id=challenge_id,
        state=ChallengeState.RESOLVED,
        outcome=outcome,
        verifier_receipt_id=receipt_id,
        verifier_module=str(receipt.get("module")),
        evidence_hash=str(receipt.get("content_hash")),
        candidate_hash=str(challenge.get("candidate_hash")),
        scope_hash=str(challenge.get("scope_hash")),
        obligation_set_hash=str(challenge.get("obligation_set_hash")),
        resolver=resolver,
        resolver_provenance=resolver_provenance,
        reason=reason,
    )
