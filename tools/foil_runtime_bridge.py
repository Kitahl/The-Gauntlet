"""Bridge existing FOIL profile/routing state into typed ADAPTATION evidence.

FOIL remains the owner of profile/calibration semantics. This bridge only records
that adaptation state or an actual routing adaptation was observed. It cannot
satisfy PROOF/DISCOVERY/ENGINEERING/EVALUATION obligations.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import foil_profile
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import (
    EvidenceClass,
    EvidenceRef,
    Receipt,
    RuntimeEvent,
    Verdict,
    digest,
    text_digest,
)

#: Attack axes that are always in scope. FOIL routing ADDS emphasis; it can never
#: remove a baseline axis, so no profile state can narrow what gets attacked.
BASELINE_AXES = (
    "classic-technique-disguise",
    "circularity",
    "instrument-vs-reality",
    "unmandated-flaw-sweep",
)


def _active_task(store: RuntimeStore) -> str | None:
    path = store.base / "active_task"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def _adaptation_obligations(store: RuntimeStore, task_id: str | None) -> list[str]:
    if not task_id:
        return []
    task = store.read_task(task_id) or {}
    return [
        str(row["obligation_id"])
        for row in task.get("obligations", [])
        if row.get("required_module") == "foil" and row.get("load_bearing", True)
    ]


def _profile_summary(profile: dict) -> dict:
    domains = profile.get("domains") or {}
    observation_count = sum(len((row or {}).get("observations") or []) for row in domains.values())
    return {
        "profile_id_hash": text_digest(str(profile.get("id") or "")),
        "profile_schema": profile.get("schema"),
        "profile_status": profile.get("profile_status"),
        "domain_count": len(domains),
        "domain_observations": observation_count,
        "calibration_observations": (profile.get("calibration") or {}).get("observations", 0),
        "raw_prompts_stored": (profile.get("privacy") or {}).get("raw_prompts_stored"),
        "profile_hash": digest(profile),
    }


def snapshot_adaptation(root: Path, obligation_id: str, profile_name: str | None = None) -> Receipt:
    """Record profile state only; snapshot alone does not clear ADAPTATION."""
    store = RuntimeStore(root)
    try:
        profile = foil_profile.load(profile_name)
    except FileNotFoundError as exc:
        receipt = Receipt(
            receipt_id=new_id("rcpt"), module="foil", obligation_id=obligation_id,
            verdict=Verdict.UNAVAILABLE, action="adaptation-state-snapshot",
            input_hash=digest({"profile_name_hash": text_digest(profile_name or "active")}),
            output_hash=None, verifier="foil_runtime_bridge", started_at=utcnow(), finished_at=utcnow(),
            unresolved=(str(exc),), notes="No FOIL profile state was available; no adaptation claim is inferred.",
        )
        store.write_receipt(receipt)
        return receipt

    summary = _profile_summary(profile)
    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="foil", obligation_id=obligation_id,
        verdict=Verdict.UNKNOWN, action="adaptation-state-snapshot",
        input_hash=summary["profile_hash"], output_hash=digest(summary),
        evidence=(EvidenceRef(evidence_class=EvidenceClass.OBSERVED, verifier="foil_runtime_bridge", metadata={
            "scope": "FOIL adaptation/profile state only; profile presence is not evidence that task routing adaptation was applied",
            **{k: v for k, v in summary.items() if k != "profile_hash"},
        }),),
        verifier="foil_runtime_bridge", started_at=utcnow(), finished_at=utcnow(),
        unresolved=("profile state observed but no task-specific adaptation action is represented",),
        notes="Snapshot is diagnostic state, not an adaptation-completion receipt and never factual warrant.",
    )
    store.write_receipt(receipt)
    return receipt


def record_prompt_adaptation(
    root: Path,
    profile: dict,
    domains: list[str],
    facets: list[str],
    *,
    prompt_text: str = "",
    foil_alias: bool = False,
) -> list[Receipt]:
    """Record that FOIL applied prompt-time relevance routing metadata.

    A load-bearing ADAPTATION obligation is CLEARED only when the user's prompt
    explicitly asked for it: it named the obligation id, or it carried the `/foil`
    alias. Otherwise the routing metadata is still recorded, but the obligation stays
    UNKNOWN so an ambient prompt cannot silently satisfy a load-bearing obligation.
    `prompt_text` is used transiently for that membership check and never persisted.
    """
    store = RuntimeStore(root)
    task_id = _active_task(store)
    low = (prompt_text or "").lower()
    summary = _profile_summary(profile)
    routing = {
        "domain_count": len(domains),
        "facet_count": len(facets),
        "domain_set_hash": digest(sorted(domains)),
        "facet_set_hash": digest(sorted(facets)),
        "profile_hash": summary["profile_hash"],
    }
    store.append_event(RuntimeEvent(
        event_id=new_id("evt"), event_type="adaptation.applied", component="foil",
        task_id=task_id, payload_hash=digest(routing), timestamp=utcnow(),
        metadata={
            "domain_count": len(domains), "facet_count": len(facets),
            "domain_set_hash": routing["domain_set_hash"], "facet_set_hash": routing["facet_set_hash"],
        },
    ))
    receipts: list[Receipt] = []
    for obligation_id in _adaptation_obligations(store, task_id):
        explicit = foil_alias or obligation_id.lower() in low
        verdict = Verdict.CLEARED if explicit else Verdict.UNKNOWN
        if explicit:
            action = "prompt-routing-adaptation"
            notes = "CLEARED means the requested FOIL routing/adaptation action ran. It cannot clear non-ADAPTATION obligations."
            unresolved: tuple[str, ...] = ()
        else:
            action = "prompt-routing-adaptation-unrequested"
            notes = (
                "Routing metadata recorded, but the prompt did not explicitly request adaptation "
                "(no /foil alias and no obligation id named), so this load-bearing ADAPTATION "
                "obligation is not cleared without user action."
            )
            unresolved = ("adaptation not explicitly requested by the prompt; awaiting /foil or an obligation-id reference",)
        receipt = Receipt(
            receipt_id=new_id("rcpt"), module="foil", obligation_id=obligation_id,
            verdict=verdict, action=action,
            input_hash=summary["profile_hash"], output_hash=digest(routing),
            evidence=(EvidenceRef(
                evidence_class=EvidenceClass.OBSERVED,
                verifier="foil_runtime_bridge",
                metadata={
                    "scope": "FOIL task-relevance adaptation only; no competence or factual correctness inference",
                    "explicit_request": explicit,
                    "domain_count": len(domains), "facet_count": len(facets),
                    "domain_set_hash": routing["domain_set_hash"], "facet_set_hash": routing["facet_set_hash"],
                    "raw_prompts_stored": summary["raw_prompts_stored"],
                },
            ),),
            verifier="foil_runtime_bridge", started_at=utcnow(), finished_at=utcnow(),
            unresolved=unresolved,
            notes=notes,
            task_id=task_id,
        )
        store.write_receipt(receipt)
        receipts.append(receipt)
    return receipts



# --------------------------------------------------------------- red-team routing


@dataclass(frozen=True)
class RedteamRoutingDecision:
    """Pure routing metadata for an adversarial strike.

    This is emphasis and seat assignment, never a verdict input and never a
    competence judgment about a seat. The A/B mandate split is a deterministic
    permutation of the axis list keyed on the domain-set hash: it distributes
    work reproducibly, and says nothing about which seat is better at what.
    """

    available: bool
    axes: tuple[str, ...]
    seat_a_axes: tuple[str, ...]
    seat_b_axes: tuple[str, ...]
    domain_set_hash: str
    facet_set_hash: str
    canary_id: str | None
    canary_hash: str | None
    decision_hash: str
    profile_status: str | None = None


def select_redteam_profile(
    domains: Sequence[str],
    facets: Sequence[str],
    *,
    canary_bank: Mapping[str, str] | None = None,
    profile: dict | None = None,
) -> RedteamRoutingDecision:
    """Deterministically derive attack emphasis from FOIL domain/facet state."""
    domain_list = sorted({str(item) for item in domains if str(item).strip()})
    facet_list = sorted({str(item) for item in facets if str(item).strip()})
    domain_set_hash = digest(domain_list)
    facet_set_hash = digest(facet_list)

    axes = list(BASELINE_AXES)
    for domain in domain_list:
        axes.append("domain-emphasis:" + domain)
    for facet in facet_list:
        axes.append("facet-emphasis:" + facet)

    offset = int(domain_set_hash[:8], 16) % len(axes)
    rotated = axes[offset:] + axes[:offset]
    seat_a = tuple(rotated[0::2])
    seat_b = tuple(rotated[1::2])

    canary_id: str | None = None
    canary_hash: str | None = None
    if canary_bank:
        keys = sorted(canary_bank)
        canary_id = keys[int(domain_set_hash[8:16], 16) % len(keys)]
        canary_hash = text_digest(str(canary_bank[canary_id]))

    available = profile is not None
    decision_hash = digest({
        "axes": axes,
        "seat_a": list(seat_a),
        "seat_b": list(seat_b),
        "domain_set_hash": domain_set_hash,
        "facet_set_hash": facet_set_hash,
        "canary_id": canary_id,
        "canary_hash": canary_hash,
        "available": available,
    })
    return RedteamRoutingDecision(
        available=available,
        axes=tuple(axes),
        seat_a_axes=seat_a,
        seat_b_axes=seat_b,
        domain_set_hash=domain_set_hash,
        facet_set_hash=facet_set_hash,
        canary_id=canary_id,
        canary_hash=canary_hash,
        decision_hash=decision_hash,
        profile_status=(profile or {}).get("profile_status") if profile else None,
    )


def routing_metadata(decision: RedteamRoutingDecision) -> dict:
    """Hashes, counts and enums only. Axis text never reaches a receipt."""
    return {
        "available": decision.available,
        "axis_count": len(decision.axes),
        "baseline_axis_count": len(BASELINE_AXES),
        "baseline_axes_included": set(BASELINE_AXES).issubset(set(decision.axes)),
        "seat_a_axis_count": len(decision.seat_a_axes),
        "seat_b_axis_count": len(decision.seat_b_axes),
        "domain_set_hash": decision.domain_set_hash,
        "facet_set_hash": decision.facet_set_hash,
        "canary_id": decision.canary_id,
        "canary_hash": decision.canary_hash,
        "decision_hash": decision.decision_hash,
        "profile_status": decision.profile_status,
        "scope": "routing metadata on a Black Gem receipt; never a verdict input",
    }


def _obligation_module(store: RuntimeStore, obligation_id: str) -> str | None:
    task_id = store.task_for_obligation(obligation_id)
    if not task_id:
        return None
    task = store.read_task(task_id) or {}
    for row in task.get("obligations", []):
        if row.get("obligation_id") == obligation_id:
            return row.get("required_module")
    return None


def record_redteam_routing(
    root: Path,
    decision: RedteamRoutingDecision,
    obligation_id: str | None = None,
) -> Receipt:
    """Record the routing decision. Only a FOIL-owned obligation can be cleared."""
    store = RuntimeStore(root)
    task_id = _active_task(store)
    if obligation_id is None:
        candidates = _adaptation_obligations(store, task_id)
        obligation_id = candidates[0] if candidates else "unassigned"
        module = "foil" if candidates else None
    else:
        module = _obligation_module(store, obligation_id)

    metadata = routing_metadata(decision)
    unresolved: list[str] = []
    if not decision.available:
        verdict = Verdict.UNAVAILABLE
        unresolved.append("no-foil-profile-available-for-redteam-routing")
    elif module != "foil":
        verdict = Verdict.UNKNOWN
        unresolved.append("obligation-not-owned-by-foil")
    else:
        verdict = Verdict.CLEARED

    receipt = Receipt(
        receipt_id=new_id("rcpt"), module="foil", obligation_id=obligation_id,
        verdict=verdict, action="redteam-routing-selection",
        input_hash=digest({
            "domain_set_hash": decision.domain_set_hash,
            "facet_set_hash": decision.facet_set_hash,
        }),
        output_hash=decision.decision_hash,
        evidence=(EvidenceRef(
            evidence_class=EvidenceClass.OBSERVED,
            verifier="foil_runtime_bridge",
            metadata=metadata,
        ),),
        verifier="foil_runtime_bridge", started_at=utcnow(), finished_at=utcnow(),
        unresolved=tuple(unresolved),
        notes=(
            "FOIL output is routing metadata on the Black Gem receipt; never a verdict input."
            " This receipt can clear an ADAPTATION obligation only."
        ),
        task_id=task_id,
    )
    store.write_receipt(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--obligation", required=True)
    snap.add_argument("--profile")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "snapshot":
        receipt = snapshot_adaptation(root, args.obligation, args.profile)
        print(json.dumps({"receipt_id": receipt.receipt_id, "verdict": receipt.verdict.value}, indent=2))
        return 0 if receipt.verdict == Verdict.CLEARED else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
