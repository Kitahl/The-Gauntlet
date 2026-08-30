"""FOIL complement/intervention ledger — v2.

Records the chain from a task-local gap hypothesis to the complement FOIL
supplied and the outcomes that followed.  It is deliberately descriptive: a
linked observational sequence does not establish a causal treatment effect.

Changes from v1
---------------
0. The optional ``effect`` field records whether assistance was useful,
   necessary, redundant, harmful, a takeover, insufficient, or missed the gap.
   It is additive: legacy v2 rows without the field remain readable, and the
   outcome phase/ownership rules below remain the authority for transfer.
1. Assistance levels come from `foil_assistance.Assistance`, so the ledger and
   `skills/foil/SKILL.md` share one vocabulary.  v1 accepted any free string for
   `assistance_level` and recognised independence only from `{"none",
   "independent"}`, which silently discarded every record that used the
   documented `A0..A4` labels.
2. `intervention_status()` is time-ordered and refutable.  v1 returned
   `TRANSFER_OBSERVED` for one old pass followed by five later verified
   failures.  Status is now computed from the most recent verified outcome in
   each phase, and a superseded pass is reported rather than hidden.
3. Identifiers are content-addressed rather than derived from list length, so
   removing a row cannot cause an id collision.
4. `summary()` reports evidence age, so a caller can downgrade stale routing
   without reading every row.
5. Every outcome records an `execution_owner`. Assistance intensity alone could
   not distinguish "the person solved it unaided" from "a tool solved it and
   nobody hinted", so tool-executed work could accumulate as ownership evidence.
   Outcomes owned by TOOL or SHARED are inadmissible above the `immediate`
   phase, exactly as assisted outcomes are.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from foil_assistance import (
    Assistance,
    ExecutionOwner,
    parse_assistance,
    parse_execution_owner,
)

SCHEMA = "egrt.foil-interventions.v2"

GAP_KINDS = {
    "MISSING_KNOWLEDGE",
    "INCORRECT_KNOWLEDGE",
    "MISSING_PROCEDURE",
    "COMMUNICATION_GAP",
    "PREREQUISITE_GAP",
    "REPRESENTATION_MISMATCH",
    "RETRIEVAL_FAILURE",
    "EVIDENCE_GAP",
    "VERIFICATION_GAP",
    "PRESENTATION_GAP",
    "TOOL_OR_ARTIFACT_GAP",
    "EXECUTION_SLIP",
    "AMBIGUOUS_TASK",
    "TEMPORARY_STATE_OR_TIME_PRESSURE",
    "GENUINELY_NOVEL_TASK",
    "UNKNOWN",
}
OUTCOME_PHASES = ("immediate", "independent", "transfer", "defense")
RESULTS = {"pass", "fail", "mixed", "unknown"}


class OutcomeEffect(str, Enum):
    """Append-only intervention-effect vocabulary for persisted rows."""

    USEFUL_COMPLEMENT = "useful_complement"
    NECESSARY_COMPLEMENT = "necessary_complement"
    REDUNDANT_ASSISTANCE = "redundant_assistance"
    HARMFUL_ASSISTANCE = "harmful_assistance"
    TAKEOVER_EVENT = "takeover_event"
    INSUFFICIENT_ASSISTANCE = "insufficient_assistance"
    MISSED_GAP = "missed_gap"
    INDEPENDENT_AFTER_ASSISTANCE = "independent_after_assistance"
    LATER_TRANSFER = "later_transfer"


OUTCOME_EFFECTS = tuple(effect.value for effect in OutcomeEffect)

#: Phases ordered weakest to strongest claim about the person.
_PHASE_STATUS = {
    "defense": "DEFENSIBLE_OBSERVED",
    "transfer": "TRANSFER_OBSERVED",
    "independent": "INDEPENDENT_SUCCESS_OBSERVED",
    "immediate": "IMMEDIATE_SUCCESS_ONLY",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _content_id(prefix: str, payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]}"


GAP_KINDS_MARKER = "<!-- generated from tools/foil_interventions.py: do not edit by hand -->"


def gap_kinds_contract_block() -> str:
    """The exact Markdown block `skills/foil/SKILL.md` must contain.

    Same mechanism as `foil_assistance.ladder_contract_block`: the documented
    gap/bottleneck vocabulary and the vocabulary `add_gap` actually accepts
    cannot drift apart silently, because the drift test asserts the file
    contains this verbatim. `add_gap` rejects any kind outside `GAP_KINDS`, so a
    label that appears only in the skill text is a label the runtime refuses at
    write time - a failure the person would meet mid-task instead of in CI.
    """
    lines = [GAP_KINDS_MARKER]
    for kind in sorted(GAP_KINDS):
        lines.append(f"- `{kind}`")
    lines.append("")
    lines.append(GAP_KINDS_MARKER)
    return "\n".join(lines)


def new_ledger(profile_id: str) -> dict[str, Any]:
    stamp = now()
    return {
        "schema": SCHEMA,
        "profile_id": profile_id,
        "created_at": stamp,
        "updated_at": stamp,
        "gaps": [],
        "interventions": [],
        "outcomes": [],
    }


def _confidence(value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return value


def _changed_context_proof(
    context_sha256: str | None,
    prior_context_sha256: str | None,
) -> dict[str, str] | None:
    """Validate an optional digest-only proof of a representation change."""
    if context_sha256 is None and prior_context_sha256 is None:
        return None
    values = {
        "context_sha256": context_sha256,
        "prior_context_sha256": prior_context_sha256,
    }
    for name, value in values.items():
        if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError(f"{name} must be a lowercase SHA-256 digest") from exc
    if context_sha256 == prior_context_sha256:
        raise ValueError("changed-context digests must be different")
    return values  # type: ignore[return-value]


def add_gap(
    ledger: dict[str, Any],
    *,
    task_id: str,
    capability: str,
    kind: str,
    confidence: float,
    evidence_refs: list[str] | None = None,
    alternatives: list[str] | None = None,
    domain: str | None = None,
    facet: str | None = None,
) -> str:
    if kind not in GAP_KINDS:
        raise ValueError(f"unknown gap kind: {kind}")
    stamp = now()
    row = {
        "time": stamp,
        "task_id": task_id,
        "capability": capability.strip(),
        "kind": kind,
        "confidence": _confidence(confidence),
        "evidence_refs": list(evidence_refs or []),
        "alternatives": list(alternatives or []),
        "domain": domain,
        "facet": facet,
    }
    gid = _content_id("g", row)
    ledger.setdefault("gaps", []).append({"id": gid, **row})
    ledger["updated_at"] = stamp
    return gid


def add_intervention(
    ledger: dict[str, Any],
    *,
    gap_id: str,
    complement: str,
    assistance_level: str | Assistance,
    tool_capability: str | None = None,
    rationale: str | None = None,
    expected_signal: str | None = None,
) -> str:
    if not any(row.get("id") == gap_id for row in ledger.get("gaps", [])):
        raise KeyError(f"unknown gap_id: {gap_id}")
    level = parse_assistance(assistance_level)  # raises on an unknown label
    stamp = now()
    row = {
        "time": stamp,
        "gap_id": gap_id,
        "complement": complement.strip(),
        "assistance_level": level.value,
        "tool_capability": tool_capability,
        "rationale": rationale,
        "expected_signal": expected_signal,
    }
    iid = _content_id("i", row)
    ledger.setdefault("interventions", []).append({"id": iid, **row})
    ledger["updated_at"] = stamp
    return iid


def add_outcome(
    ledger: dict[str, Any],
    *,
    intervention_id: str,
    phase: str,
    result: str,
    verified: bool,
    assistance: str | Assistance,
    representation: str | None = None,
    context_sha256: str | None = None,
    prior_context_sha256: str | None = None,
    verifier: str | None = None,
    evidence_ref: str | None = None,
    observed_at: str | None = None,
    execution_owner: str | ExecutionOwner = ExecutionOwner.USER,
    effect: str | OutcomeEffect | None = None,
) -> str:
    if phase not in OUTCOME_PHASES:
        raise ValueError(f"unknown outcome phase: {phase}")
    if result not in RESULTS:
        raise ValueError(f"unknown result: {result}")
    if not any(row.get("id") == intervention_id for row in ledger.get("interventions", [])):
        raise KeyError(f"unknown intervention_id: {intervention_id}")
    level = parse_assistance(assistance)
    owner = parse_execution_owner(execution_owner)
    parsed_effect: OutcomeEffect | None = None
    if effect is not None:
        try:
            parsed_effect = OutcomeEffect(effect)
        except ValueError as exc:
            raise ValueError(f"unknown outcome effect: {effect}") from exc
    if verified and not verifier:
        raise ValueError("a verified outcome must name its verifier")
    changed_context = _changed_context_proof(context_sha256, prior_context_sha256)
    stamp = now()
    row = {
        "time": stamp,
        "observed_at": observed_at or stamp,
        "intervention_id": intervention_id,
        "phase": phase,
        "result": result,
        "verified": bool(verified),
        "assistance": level.value,
        "execution_owner": owner.value,
        "representation": representation,
        "changed_context": changed_context,
        "verifier": verifier,
        "evidence_ref": evidence_ref,
        "effect": parsed_effect.value if parsed_effect else None,
    }
    oid = _content_id("o", row)
    ledger.setdefault("outcomes", []).append({"id": oid, **row})
    ledger["updated_at"] = stamp
    return oid


def _admissible(row: dict[str, Any], phase: str) -> bool:
    """Only verified outcomes count.

    Phases above `immediate` additionally require both A0 assistance and
    USER execution ownership. A tool- or pair-executed pass says something about
    the task, never about the person's independent capability, so it is
    inadmissible for `independent`, `transfer`, and `defense` on exactly the same
    grounds as an assisted pass. Legacy rows without the field are read as
    USER-owned, because that is what the field meant before it existed.
    """
    if not row.get("verified"):
        return False
    if row.get("phase") != phase:
        return False
    if phase == "immediate":
        return True
    try:
        if not parse_assistance(row.get("assistance", "")).is_independent:
            return False
        owner = parse_execution_owner(row.get("execution_owner") or ExecutionOwner.USER)
    except ValueError:
        return False
    return owner is ExecutionOwner.USER


def intervention_status(ledger: dict[str, Any], intervention_id: str) -> dict[str, Any]:
    """Time-ordered, refutable status for one intervention.

    Returns the strongest phase whose **most recent** admissible outcome passed.
    A later verified failure supersedes an earlier pass instead of being ignored.
    """
    rows = sorted(
        (r for r in ledger.get("outcomes", []) if r.get("intervention_id") == intervention_id),
        key=lambda r: _parse_time(r.get("observed_at") or r.get("time")),
    )
    superseded: list[str] = []
    latest_by_phase: dict[str, dict[str, Any]] = {}
    for phase in OUTCOME_PHASES:
        admissible = [r for r in rows if _admissible(r, phase)]
        if not admissible:
            continue
        latest = admissible[-1]
        latest_by_phase[phase] = latest
        if latest.get("result") != "pass" and any(
            r.get("result") == "pass" for r in admissible[:-1]
        ):
            superseded.append(phase)

    for phase in ("defense", "transfer", "independent", "immediate"):
        latest = latest_by_phase.get(phase)
        if latest and latest.get("result") == "pass":
            return {
                "status": _PHASE_STATUS[phase],
                "phase": phase,
                "as_of": latest.get("observed_at") or latest.get("time"),
                "superseded_phases": superseded,
                "verifier": latest.get("verifier"),
            }
    if any(r.get("verified") and r.get("result") == "fail" for r in rows):
        return {
            "status": "VERIFIED_FAILURE_OBSERVED",
            "phase": None,
            "as_of": (rows[-1].get("observed_at") or rows[-1].get("time")) if rows else None,
            "superseded_phases": superseded,
            "verifier": None,
        }
    return {
        "status": "NO_VERIFIED_OUTCOME",
        "phase": None,
        "as_of": None,
        "superseded_phases": superseded,
        "verifier": None,
    }


def intervention_effect_metrics(ledger: dict[str, Any]) -> dict[str, Any]:
    """Compute auditable intervention-level rates from tagged outcomes.

    An intervention may have more than one effect over time (for example an
    immediately useful complement followed by later transfer), so every rate
    is a separate proportion and the rates are not expected to sum to one.
    """
    known_interventions = {row.get("id") for row in ledger.get("interventions", [])}
    by_intervention: dict[str, set[OutcomeEffect]] = {}
    for row in ledger.get("outcomes", []):
        intervention_id = row.get("intervention_id")
        if intervention_id not in known_interventions or not row.get("effect"):
            continue
        try:
            effect = OutcomeEffect(row["effect"])
        except ValueError:
            continue
        by_intervention.setdefault(intervention_id, set()).add(effect)
    assessed = len(by_intervention)

    def count(*effects: OutcomeEffect) -> int:
        wanted = set(effects)
        return sum(bool(values & wanted) for values in by_intervention.values())

    def rate(value: int) -> float | None:
        return round(value / assessed, 6) if assessed else None

    hits = count(OutcomeEffect.USEFUL_COMPLEMENT, OutcomeEffect.NECESSARY_COMPLEMENT)
    redundant = count(OutcomeEffect.REDUNDANT_ASSISTANCE)
    harmful = count(OutcomeEffect.HARMFUL_ASSISTANCE)
    takeover = count(OutcomeEffect.TAKEOVER_EVENT)
    harmful_or_takeover = count(OutcomeEffect.HARMFUL_ASSISTANCE, OutcomeEffect.TAKEOVER_EVENT)
    missed = count(OutcomeEffect.MISSED_GAP)
    insufficient = count(OutcomeEffect.INSUFFICIENT_ASSISTANCE)
    return {
        "assessed_interventions": assessed,
        "complement_hit_rate": rate(hits),
        "redundant_assistance_rate": rate(redundant),
        "harmful_assistance_rate": rate(harmful),
        "takeover_rate": rate(takeover),
        "harmful_or_takeover_rate": rate(harmful_or_takeover),
        "missed_gap_rate": rate(missed),
        "insufficient_assistance_rate": rate(insufficient),
    }


def summary(ledger: dict[str, Any]) -> dict[str, Any]:
    statuses = {
        row["id"]: intervention_status(ledger, row["id"]) for row in ledger.get("interventions", [])
    }
    ages: list[float] = []
    reference = datetime.now(timezone.utc)
    for row in statuses.values():
        if row.get("as_of"):
            ages.append((reference - _parse_time(row["as_of"])).total_seconds() / 86400.0)
    return {
        "schema": SCHEMA,
        "profile_id": ledger.get("profile_id"),
        "gaps": len(ledger.get("gaps", [])),
        "interventions": len(ledger.get("interventions", [])),
        "outcomes": len(ledger.get("outcomes", [])),
        "statuses": statuses,
        "newest_evidence_age_days": round(min(ages), 2) if ages else None,
        "oldest_evidence_age_days": round(max(ages), 2) if ages else None,
        "superseded_count": sum(1 for row in statuses.values() if row["superseded_phases"]),
        "effect_metrics": intervention_effect_metrics(ledger),
        "causal_boundary": (
            "These are descriptive linked observations. Do not infer that an intervention caused "
            "an outcome without a controlled comparison or randomized design."
        ),
    }


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOIL complement/intervention ledger v2")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("path", type=Path)
    init.add_argument("--profile", required=True)

    gap = sub.add_parser("gap")
    gap.add_argument("path", type=Path)
    gap.add_argument("--task-id", required=True)
    gap.add_argument("--capability", required=True)
    gap.add_argument("--kind", required=True, choices=sorted(GAP_KINDS))
    gap.add_argument("--confidence", required=True, type=float)
    gap.add_argument("--alternative", action="append", default=[])
    gap.add_argument("--evidence-ref", action="append", default=[])

    intervene = sub.add_parser("intervene")
    intervene.add_argument("path", type=Path)
    intervene.add_argument("--gap-id", required=True)
    intervene.add_argument("--complement", required=True)
    intervene.add_argument(
        "--assistance-level", required=True, choices=[a.value for a in Assistance]
    )
    intervene.add_argument("--tool-capability")
    intervene.add_argument("--rationale")
    intervene.add_argument("--expected-signal")

    outcome = sub.add_parser("outcome")
    outcome.add_argument("path", type=Path)
    outcome.add_argument("--intervention-id", required=True)
    outcome.add_argument("--phase", required=True, choices=list(OUTCOME_PHASES))
    outcome.add_argument("--result", required=True, choices=sorted(RESULTS))
    outcome.add_argument("--verified", action="store_true")
    outcome.add_argument("--assistance", required=True, choices=[a.value for a in Assistance])
    outcome.add_argument("--representation")
    outcome.add_argument("--context-sha256")
    outcome.add_argument("--prior-context-sha256")
    outcome.add_argument("--verifier")
    outcome.add_argument("--evidence-ref")
    outcome.add_argument(
        "--execution-owner",
        default=ExecutionOwner.USER.value,
        choices=[o.value for o in ExecutionOwner],
    )
    outcome.add_argument("--effect", choices=list(OUTCOME_EFFECTS))

    status = sub.add_parser("summary")
    status.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    if args.cmd == "init":
        save(args.path, new_ledger(args.profile))
        print(args.path)
        return 0

    ledger = load(args.path)
    if args.cmd == "gap":
        ident = add_gap(
            ledger,
            task_id=args.task_id,
            capability=args.capability,
            kind=args.kind,
            confidence=args.confidence,
            alternatives=args.alternative,
            evidence_refs=args.evidence_ref,
        )
    elif args.cmd == "intervene":
        ident = add_intervention(
            ledger,
            gap_id=args.gap_id,
            complement=args.complement,
            assistance_level=args.assistance_level,
            tool_capability=args.tool_capability,
            rationale=args.rationale,
            expected_signal=args.expected_signal,
        )
    elif args.cmd == "outcome":
        ident = add_outcome(
            ledger,
            intervention_id=args.intervention_id,
            phase=args.phase,
            result=args.result,
            verified=args.verified,
            assistance=args.assistance,
            representation=args.representation,
            verifier=args.verifier,
            context_sha256=args.context_sha256,
            prior_context_sha256=args.prior_context_sha256,
            evidence_ref=args.evidence_ref,
            execution_owner=args.execution_owner,
            effect=args.effect,
        )
    else:
        print(json.dumps(summary(ledger), indent=2, ensure_ascii=False))
        return 0
    save(args.path, ledger)
    print(ident)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
