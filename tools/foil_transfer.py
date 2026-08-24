"""Fail-closed, receipt-safe FOIL P2 transfer and presentation-refinement controls.

This module deliberately has no model, tool, network, or evidence-estimator
dependency.  It only evaluates host-supplied, intervention-ledger-shaped
mappings.  In particular, it never stores a reflection, prompt, draft, answer,
or verifier prose: the public result is a compact control receipt made from
validated SHA-256 digests and counters.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from foil_assistance import Assistance, ExecutionOwner, parse_assistance, parse_execution_owner
from foil_interventions import GAP_KINDS
from foil_signal_boundary import SignalAuthority

SCHEMA = "egrt.foil-transfer.v1"
TRANSFER_PHASES = frozenset(("transfer", "defense"))
BLOCKING_EFFECTS = frozenset(("harmful_assistance", "takeover_event", "redundant_assistance"))
PRESENTATION_GAPS = frozenset(("PRESENTATION_GAP", "COMMUNICATION_GAP"))
FEEDBACK_CATEGORIES = frozenset(
    ("clarity", "structure", "style", "formatting", "tone", "audience_fit")
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TransferInputError(ValueError):
    """A host result is malformed, ambiguous, or would widen controller authority."""


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TransferInputError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _stable_digest(value: object) -> str:
    """Hash public structure without retaining the underlying source mapping."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _assistance_is_a0(value: object) -> bool:
    try:
        return parse_assistance(value) is Assistance.A0_INDEPENDENT
    except (TypeError, ValueError):
        return False


def _assistance_label(value: object) -> str:
    try:
        return parse_assistance(value).value
    except (TypeError, ValueError):
        return "unknown"


def _owner_is_user(value: object) -> bool:
    try:
        return parse_execution_owner(value) is ExecutionOwner.USER
    except (TypeError, ValueError):
        return False


def _owner_label(value: object) -> str:
    try:
        return parse_execution_owner(value).value
    except (TypeError, ValueError):
        return "unknown"


def _row_time(row: Mapping[str, Any]) -> datetime:
    return _time(row.get("observed_at") or row.get("time"))


def _changed_context(row: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Return a privacy-safe changed-context proof from a transfer outcome.

    The controller admits only explicit digests.  A human-readable legacy
    ``representation`` string is intentionally not treated as a confirmation:
    guessing that two labels differ both leaks content and manufactures transfer.
    This is an experimental, digest-only ledger extension: hosts may provide either
    digest-only ``representation`` mapping.
    """
    proof = row.get("changed_context")
    if proof is None and isinstance(row.get("representation"), Mapping):
        proof = row["representation"]
    if not isinstance(proof, Mapping):
        return False, None
    current = proof.get("context_sha256", proof.get("representation_sha256"))
    prior = proof.get("prior_context_sha256", proof.get("baseline_sha256"))
    try:
        current = _digest(current, "context_sha256")
        prior = _digest(prior, "prior_context_sha256")
    except TransferInputError:
        return False, None
    return current != prior, current


@dataclass(frozen=True)
class _JoinedOutcome:
    gap_kind: str
    capability_sha256: str
    intervention_sha256: str
    complement_sha256: str
    outcome: Mapping[str, Any]


def _hash_text_or_digest(value: object, field: str) -> str:
    """Convert an input identifier to a receipt-safe digest without returning it."""
    if not isinstance(value, str) or not value.strip():
        raise TransferInputError(f"{field} is required")
    return value if _SHA256.fullmatch(value) else hashlib.sha256(value.encode("utf-8")).hexdigest()


def _join_ledger(ledger: Mapping[str, Any]) -> list[_JoinedOutcome]:
    if not isinstance(ledger, Mapping):
        raise TransferInputError("ledger must be a mapping")
    gaps = ledger.get("gaps", [])
    interventions = ledger.get("interventions", [])
    outcomes = ledger.get("outcomes", [])
    if not all(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        for value in (gaps, interventions, outcomes)
    ):
        raise TransferInputError("ledger gaps, interventions, and outcomes must be lists")
    gap_by_id = {row.get("id"): row for row in gaps if isinstance(row, Mapping)}
    intervention_by_id = {row.get("id"): row for row in interventions if isinstance(row, Mapping)}
    joined: list[_JoinedOutcome] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        intervention = intervention_by_id.get(outcome.get("intervention_id"))
        if intervention is None:
            continue
        gap = gap_by_id.get(intervention.get("gap_id"))
        if gap is None:
            continue
        try:
            joined.append(
                _JoinedOutcome(
                    gap_kind=(gap.get("kind") if gap.get("kind") in GAP_KINDS else "UNKNOWN"),
                    capability_sha256=_hash_text_or_digest(gap.get("capability"), "capability"),
                    intervention_sha256=_hash_text_or_digest(
                        intervention.get("id"), "intervention id"
                    ),
                    complement_sha256=_hash_text_or_digest(
                        intervention.get("complement"), "complement"
                    ),
                    outcome=outcome,
                )
            )
        except TransferInputError:
            # A malformed row supplies no competence claim and therefore cannot
            # make an otherwise valid row eligible through accidental joining.
            continue
    return joined


def structured_transfer_history(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project a ledger into an ordered, raw-content-free Reflexion history.

    This is deliberately not natural-language reflection.  It contains only
    controlled categories, hashed identifiers, verification/ownership facts, a
    changed-context bit, and the explicit result already recorded by the host.
    """
    records: list[dict[str, Any]] = []
    for joined in _join_ledger(ledger):
        outcome = joined.outcome
        changed, context = _changed_context(outcome)
        result = outcome.get("result")
        records.append(
            {
                "gap_kind": joined.gap_kind,
                "capability_sha256": joined.capability_sha256,
                "intervention_sha256": joined.intervention_sha256,
                "complement_sha256": joined.complement_sha256,
                "phase": outcome.get("phase")
                if outcome.get("phase") in TRANSFER_PHASES | {"immediate", "independent"}
                else "unknown",
                "verified": bool(outcome.get("verified")),
                "assistance": _assistance_label(outcome.get("assistance")),
                "execution_owner": _owner_label(outcome.get("execution_owner")),
                "changed_context_confirmed": changed,
                "context_sha256": context,
                "transfer_result": result
                if result in {"pass", "fail", "mixed", "unknown"}
                else "unknown",
                "outcome_time": (outcome.get("observed_at") or outcome.get("time"))
                if isinstance(outcome.get("observed_at") or outcome.get("time"), str)
                else None,
            }
        )
    return sorted(records, key=lambda row: _time(row["outcome_time"]))


def _admissible_transfer(row: _JoinedOutcome) -> bool:
    outcome = row.outcome
    changed, _ = _changed_context(outcome)
    return (
        outcome.get("phase") in TRANSFER_PHASES
        and outcome.get("result") == "pass"
        and bool(outcome.get("verified"))
        and isinstance(outcome.get("verifier"), str)
        and bool(outcome["verifier"].strip())
        and _assistance_is_a0(outcome.get("assistance"))
        and _owner_is_user(outcome.get("execution_owner"))
        and changed
    )


def _blocked(rows: Sequence[_JoinedOutcome]) -> str | None:
    for row in rows:
        effect = row.outcome.get("effect")
        if isinstance(effect, str) and effect in BLOCKING_EFFECTS:
            return effect
    return None


def select_transfer(
    ledger: Mapping[str, Any],
    *,
    capability: str | None = None,
    max_age_days: float = 90.0,
    reference_time: datetime | None = None,
) -> dict[str, Any]:
    """Return a control-only transfer selection receipt.

    A selection is possible only after the latest admissible transfer/defense
    pass for a capability.  Any later verified failure for that capability
    supersedes it.  Assistance/takeover harms block the capability outright.
    """
    if (
        isinstance(max_age_days, bool)
        or not isinstance(max_age_days, (int, float))
        or max_age_days < 0
    ):
        raise TransferInputError("max_age_days must be a non-negative number")
    reference = reference_time or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    joined = _join_ledger(ledger)
    wanted = _hash_text_or_digest(capability, "capability") if capability is not None else None
    if wanted is not None:
        joined = [row for row in joined if row.capability_sha256 == wanted]
    history = structured_transfer_history(ledger)
    if wanted is not None:
        history = [row for row in history if row["capability_sha256"] == wanted]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "authority": SignalAuthority.CONTROL_ONLY.value,
        "selection": "NOT_SELECTED",
        "reason": "NO_ADMISSIBLE_TRANSFER_PASS",
        "capability_sha256": wanted,
        "history_count": len(history),
        "admissible_pass_count": 0,
        "changed_context_confirmation_count": 0,
        "raw_content_stored": False,
    }
    if not joined:
        receipt["receipt_sha256"] = _stable_digest(receipt)
        return receipt
    block = _blocked(joined)
    if block:
        receipt["reason"] = f"BLOCKED_{block.upper()}"
        receipt["receipt_sha256"] = _stable_digest(receipt)
        return receipt
    eligible = [row for row in joined if _admissible_transfer(row)]
    receipt["admissible_pass_count"] = len(eligible)
    receipt["changed_context_confirmation_count"] = sum(
        _changed_context(row.outcome)[0] for row in eligible
    )
    if not eligible:
        receipt["receipt_sha256"] = _stable_digest(receipt)
        return receipt
    latest = max(eligible, key=lambda row: _row_time(row.outcome))
    if (reference - _row_time(latest.outcome)).total_seconds() > float(max_age_days) * 86400:
        receipt["reason"] = "STALE_ADMISSIBLE_TRANSFER_PASS"
        receipt["receipt_sha256"] = _stable_digest(receipt)
        return receipt
    later_failure = any(
        bool(row.outcome.get("verified"))
        and row.outcome.get("result") == "fail"
        and _row_time(row.outcome) > _row_time(latest.outcome)
        for row in joined
    )
    if later_failure:
        receipt["reason"] = "SUPERSEDED_BY_LATER_VERIFIED_FAILURE"
        receipt["receipt_sha256"] = _stable_digest(receipt)
        return receipt
    receipt.update(
        {
            "selection": "SELECTED",
            "reason": "LATEST_ADMISSIBLE_CHANGED_CONTEXT_PASS",
            "capability_sha256": latest.capability_sha256,
            "intervention_sha256": latest.intervention_sha256,
            "complement_sha256": latest.complement_sha256,
            "phase": latest.outcome.get("phase"),
        }
    )
    receipt["receipt_sha256"] = _stable_digest(receipt)
    return receipt


def _costs(*, feedback_rounds: int = 0, revisions: int = 0) -> dict[str, int]:
    return {
        "model_calls": 0,
        "tool_calls": 0,
        "network_calls": 0,
        "feedback_rounds": feedback_rounds,
        "revisions": revisions,
    }


def self_refine_ablation_trace(*, draft_sha256: str, enabled: bool) -> dict[str, Any]:
    """Produce an independently attributable, digest-only disabled/enabled trace."""
    _digest(draft_sha256, "draft_sha256")
    return {
        "schema": SCHEMA,
        "authority": SignalAuthority.CONTROL_ONLY.value,
        "arm": "self_refine_enabled" if enabled else "self_refine_disabled",
        "draft_sha256": draft_sha256,
        "enabled": enabled,
        "costs": _costs(),
        "raw_content_stored": False,
    }


def _feedback_categories(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TransferInputError("feedback_categories must be a sequence")
    categories = tuple(value)
    if not categories or any(
        not isinstance(item, str) or item not in FEEDBACK_CATEGORIES for item in categories
    ):
        raise TransferInputError(
            "feedback categories must be non-empty controlled presentation categories"
        )
    return categories


def run_self_refine(
    *,
    enabled: bool = False,
    gap_kind: str,
    draft_sha256: str,
    feedback_categories: Sequence[str] = (),
    feedback: Mapping[str, Any] | None = None,
    revision: Mapping[str, Any] | None = None,
    recheck: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the bounded presentation-only Self-Refine gate on host attestations.

    ``feedback``, ``revision``, and ``recheck`` are typed host results, not
    prompts or text.  A caller may supply exactly one revision and must provide
    an independent verifier digest for the final contract/style recheck.
    """
    _digest(draft_sha256, "draft_sha256")
    base = {
        "schema": SCHEMA,
        "authority": SignalAuthority.CONTROL_ONLY.value,
        "draft_sha256": draft_sha256,
        "gap_kind": gap_kind if gap_kind in PRESENTATION_GAPS else "NON_PRESENTATION",
        "enabled": bool(enabled),
        "status": "REJECTED",
        "reason": "DISABLED",
        "raw_content_stored": False,
        "ablation": self_refine_ablation_trace(draft_sha256=draft_sha256, enabled=bool(enabled)),
        "costs": _costs(),
    }
    if enabled is not True:
        base["receipt_sha256"] = _stable_digest(base)
        return base
    if gap_kind not in PRESENTATION_GAPS:
        base["reason"] = "NON_PRESENTATION_GAP"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    try:
        categories = _feedback_categories(feedback_categories)
    except TransferInputError:
        base["reason"] = "INVALID_FEEDBACK_CATEGORIES"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    base["feedback_categories"] = categories
    base["costs"] = _costs(feedback_rounds=1)
    if not isinstance(feedback, Mapping) or feedback.get("presentation_only") is not True:
        base["reason"] = "INVALID_OR_NON_PRESENTATION_FEEDBACK"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    if not isinstance(revision, Mapping):
        base["reason"] = "MISSING_REVISION"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    if revision.get("revision_count") != 1:
        base["reason"] = "REVISION_BUDGET_EXCEEDED"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    if any(
        revision.get(flag) is not False
        for flag in ("factual_changed", "evidence_changed", "claim_changed", "content_changed")
    ):
        base["reason"] = "CONTENT_OR_EVIDENCE_MUTATION"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    try:
        revision_sha256 = _digest(revision.get("revision_sha256"), "revision_sha256")
    except TransferInputError:
        base["reason"] = "INVALID_REVISION_DIGEST"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    base["revision_sha256"] = revision_sha256
    base["costs"] = _costs(feedback_rounds=1, revisions=1)
    if not isinstance(recheck, Mapping):
        base["reason"] = "MISSING_RECHECK"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    try:
        _digest(recheck.get("verifier_sha256"), "verifier_sha256")
    except TransferInputError:
        base["reason"] = "MISSING_VERIFIER"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    required = ("contract_pass", "style_pass", "content_unchanged", "evidence_unchanged")
    if not all(recheck.get(flag) is True for flag in required):
        base["reason"] = "CONTRACT_STYLE_OR_INTEGRITY_RECHECK_FAILED"
        base["receipt_sha256"] = _stable_digest(base)
        return base
    base.update({"status": "ACCEPTED", "reason": "PRESENTATION_ONLY_REFINEMENT_RECHECKED"})
    base["receipt_sha256"] = _stable_digest(base)
    return base
