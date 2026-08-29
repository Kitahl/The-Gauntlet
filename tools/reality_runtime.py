"""Reality vNext front-end with bounded historical direct-call compatibility.

The vNext implementation lives in ``reality_runtime_vnext``. This front-end preserves
one pre-vNext API contract: unbound direct ``record_candidate`` calls may still consume
an integrity-valid stored Space source-assessment receipt. That compatibility receipt
has no live task binding and cannot satisfy the strict Soul-routed vNext admission gate.

The front-end also owns compatibility hardening that must be applied without widening
Reality authority: current Space assessment state outranks stale caller-selected state,
Space refutation cannot be interpreted as a novelty-costume pass, and documented
candidate fields remain mechanically required.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import reality_runtime_vnext as _core

CandidateAttackBundle = _core.CandidateAttackBundle
MethodCandidate = _core.MethodCandidate
Verdict = _core.Verdict
Receipt = _core.Receipt
REALITY_SCHEMA = _core.REALITY_SCHEMA
admission = _core.admission
candidate_hash = _core.candidate_hash
create_attack_bundle = _core.create_attack_bundle
diversity_matrix = _core.diversity_matrix
load_attack_bundle = _core.load_attack_bundle
meaningful_changed_assumption = _core.meaningful_changed_assumption
mechanism_signature = _core.mechanism_signature

# Preserve the private helper used by the adversarial binding regression.
_make_bundle = _core._make_bundle
_original_basic_candidate_errors = _core._basic_candidate_errors
_original_space_prior_art_state = _core._space_prior_art_state
_original_evaluate_admission = _core.evaluate_admission
_original_record_candidate = _core.record_candidate

_SUPPORTED_OUTCOMES = {
    "SUPPORTED",
    "SUPPORTED_WITH_DERIVATIVE_COLLISION",
}
_REFUTED_OUTCOMES = {
    "REFUTED",
    "REFUTED_WITH_DERIVATIVE_COLLISION",
}


def _claim_outcome(receipt: Mapping[str, Any]) -> str | None:
    notes = receipt.get("notes")
    if not isinstance(notes, str):
        return None
    try:
        parsed = json.loads(notes)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, Mapping):
        return None
    value = parsed.get("claim_outcome")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().upper()


def _hardened_basic_candidate_errors(candidate: MethodCandidate) -> list[str]:
    errors = list(_original_basic_candidate_errors(candidate))
    if isinstance(candidate, _core.MethodCandidate):
        if not candidate.invariants:
            errors.append("invariants are required")
        if not candidate.dependencies:
            errors.append("dependencies are required")
    return list(dict.fromkeys(errors))


def _assessment_matches_candidate(
    store: Any,
    receipt: Mapping[str, Any],
    candidate: MethodCandidate,
    context: Any,
) -> bool:
    if receipt.get("module") != "space" or receipt.get("action") != "source-assessment":
        return False
    if context is not None and receipt.get("task_id") not in (None, context.task_id):
        return False
    search, unresolved, issues = _core._search_receipt_state(
        store,
        receipt,
        expected_candidate_hash=_core.candidate_hash(candidate),
        expected_task_id=context.task_id if context is not None else None,
    )
    if search is None or unresolved or issues:
        return False
    explicit_scope = candidate.metadata.get("scope_hash")
    scope_hash = _core._space_scope_hash(search)
    if isinstance(explicit_scope, str) and explicit_scope:
        if scope_hash != explicit_scope:
            return False
    expected_claim_scope = candidate.metadata.get("prior_art_claim_scope")
    if isinstance(expected_claim_scope, str) and expected_claim_scope.strip():
        scopes = _core._assessed_claim_scopes(receipt)
        if _core._normalize_text(expected_claim_scope) not in scopes:
            return False
    return True


def _current_candidate_bound_assessment_ids(
    store: Any,
    candidate: MethodCandidate,
    context: Any,
) -> tuple[str, ...]:
    if context is None:
        return ()
    current: list[str] = []
    for discovery_id in context.discovery_dependency_ids:
        for receipt in reversed(store.receipts_for(discovery_id)):
            if not _assessment_matches_candidate(store, receipt, candidate, context):
                continue
            receipt_id = receipt.get("receipt_id")
            if isinstance(receipt_id, str) and receipt_id:
                current.append(receipt_id)
            break
    return tuple(current)


def _directional_prior_art_reasons(
    store: Any,
    receipt_ids: Sequence[str],
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    unresolved: list[str] = []
    for receipt_id in receipt_ids:
        receipt = store.read_receipt(receipt_id)
        if receipt is None:
            continue
        outcome = _claim_outcome(receipt)
        if outcome in _REFUTED_OUTCOMES:
            issues.append(
                "current Space assessment refutes the candidate prior-art non-match claim"
            )
            continue
        if outcome in _SUPPORTED_OUTCOMES:
            continue
        tool_version = str(receipt.get("tool_version") or "")
        verifier = str(receipt.get("verifier") or "")
        if tool_version.startswith("egrt.space.v2") or verifier.endswith(":v2"):
            if receipt.get("verdict") == _core.Verdict.CLEARED.value:
                unresolved.append(
                    "current Space assessment is CLEARED but lacks a recognized directional claim_outcome"
                )
    return issues, unresolved


def _hardened_space_prior_art_state(
    store: Any,
    candidate: MethodCandidate,
    receipt_ids: Sequence[str],
    context: Any,
) -> Any:
    """Make current candidate-bound Space assessment authoritative over stale IDs."""
    current_ids = _current_candidate_bound_assessment_ids(store, candidate, context)
    if current_ids:
        current_state = _original_space_prior_art_state(
            store,
            candidate,
            current_ids,
            context,
        )
        historical_state = _original_space_prior_art_state(
            store,
            candidate,
            receipt_ids,
            context,
        )
        # Historical valid ids remain visible only so an already-resolved costume
        # challenge can keep its immutable verifier-receipt binding. Their verdict or
        # unresolved state does not override the newest candidate-bound assessment.
        compatible_ids = tuple(
            dict.fromkeys((*current_state.receipt_ids, *historical_state.receipt_ids))
        )
        state = replace(current_state, receipt_ids=compatible_ids)
        directional_ids = current_ids
    else:
        state = _original_space_prior_art_state(
            store,
            candidate,
            receipt_ids,
            context,
        )
        directional_ids = state.receipt_ids

    directional_issues, directional_unresolved = _directional_prior_art_reasons(
        store,
        directional_ids,
    )
    return replace(
        state,
        issues=tuple(dict.fromkeys((*state.issues, *directional_issues))),
        unresolved=tuple(
            dict.fromkeys((*state.unresolved, *directional_unresolved))
        ),
    )


def _competing_discriminator_reasons(candidate: MethodCandidate) -> list[str]:
    competing = candidate.metadata.get("competing_mechanism")
    if not isinstance(competing, str) or not competing.strip():
        return []
    discriminator = candidate.metadata.get("competing_discriminator")
    if not isinstance(discriminator, str) or not discriminator.strip():
        return [
            "named competing mechanism requires an explicit A-vs-B discriminator specification"
        ]
    return []


# Core functions resolve these helpers from their module globals at call time.
_core._basic_candidate_errors = _hardened_basic_candidate_errors
_core._space_prior_art_state = _hardened_space_prior_art_state


def evaluate_admission(
    root: Path,
    candidate: MethodCandidate,
    bundle: CandidateAttackBundle | None = None,
) -> tuple[Verdict, list[str]]:
    """Apply the strict vNext gate while preserving recorded ISSUE/UNAVAILABLE severity."""
    actual_bundle = bundle or _core.load_attack_bundle(root, candidate.candidate_id)
    verdict, reasons = _original_evaluate_admission(root, candidate, actual_bundle)
    missing_prior_art = reasons == [
        "stored cleared Space source-assessment evidence is required"
    ]
    if actual_bundle is not None and verdict is _core.Verdict.UNKNOWN and missing_prior_art:
        if actual_bundle.status is _core.Verdict.ISSUE:
            return _core.Verdict.ISSUE, list(actual_bundle.unresolved) or [
                "CandidateAttackBundle records an admission issue"
            ]
        if actual_bundle.status is _core.Verdict.UNAVAILABLE:
            return _core.Verdict.UNAVAILABLE, list(actual_bundle.unresolved) or [
                "required prior-art evidence is unavailable"
            ]
    if verdict is _core.Verdict.CLEARED:
        competing_reasons = _competing_discriminator_reasons(candidate)
        if competing_reasons:
            return _core.Verdict.UNKNOWN, competing_reasons
    return verdict, reasons


# Core record_candidate resolves this name from its module globals at call time.
_core.evaluate_admission = evaluate_admission


def _legacy_unbound_prior_art(
    store: Any,
    receipt_ids: Sequence[str],
) -> tuple[Verdict, list[str], tuple[str, ...], str | None]:
    """Validate only the historical stored-Space receipt shape; never caller dicts."""
    reasons: list[str] = []
    valid_ids: list[str] = []
    scopes: set[str] = set()
    explicit_refutation = False
    if not receipt_ids:
        return (
            _core.Verdict.UNKNOWN,
            ["stored Space source-assessment evidence is required"],
            (),
            None,
        )
    for receipt_id in receipt_ids:
        if not isinstance(receipt_id, str) or not receipt_id:
            reasons.append("prior-art receipt identifier must be non-empty")
            continue
        receipt = store.read_receipt(receipt_id)
        if receipt is None:
            reasons.append(f"prior-art receipt {receipt_id} is missing or corrupt")
            continue
        if receipt.get("module") != "space" or receipt.get("action") != "source-assessment":
            reasons.append(f"{receipt_id} is not a stored Space source-assessment receipt")
            continue
        if receipt.get("verdict") != _core.Verdict.CLEARED.value:
            reasons.append(f"{receipt_id} Space source-assessment is not CLEARED")
            continue
        if _claim_outcome(receipt) in _REFUTED_OUTCOMES:
            explicit_refutation = True
            reasons.append(
                "Space assessment explicitly refutes the candidate prior-art non-match claim"
            )
            continue
        cited = [
            evidence
            for evidence in _core._receipt_evidence(receipt)
            if str(evidence.get("evidence_class")) == _core.EvidenceClass.CITED.value
            and isinstance(evidence.get("artifact"), Mapping)
            and bool(evidence["artifact"].get("sha256"))
        ]
        if not cited:
            reasons.append(f"{receipt_id} lacks hashed claim-scoped cited evidence")
            continue
        notes = receipt.get("notes")
        parsed: Mapping[str, Any] = {}
        if isinstance(notes, str):
            try:
                loaded = json.loads(notes)
                if isinstance(loaded, Mapping):
                    parsed = loaded
            except json.JSONDecodeError:
                reasons.append(f"{receipt_id} source-assessment notes are not valid JSON")
                continue
        search_receipt_id = parsed.get("search_receipt_id")
        if not isinstance(search_receipt_id, str) or not search_receipt_id:
            reasons.append(f"{receipt_id} lacks its stored Space retrieval binding")
            continue
        search = store.read_receipt(search_receipt_id)
        if search is None:
            reasons.append(f"{receipt_id} references a missing/corrupt Space retrieval receipt")
            continue
        if search.get("module") != "space" or search.get("action") != "multi-index-retrieval":
            reasons.append(f"{receipt_id} does not bind a Space retrieval receipt")
            continue
        if search.get("obligation_id") != receipt.get("obligation_id"):
            reasons.append(f"{receipt_id} assessment/retrieval obligation binding mismatch")
            continue
        scope_hash = _core._space_scope_hash(search)
        if scope_hash is not None:
            scopes.add(scope_hash)
        valid_ids.append(receipt_id)
    if explicit_refutation and not valid_ids:
        return _core.Verdict.ISSUE, list(dict.fromkeys(reasons)), (), None
    if not valid_ids:
        return _core.Verdict.UNKNOWN, list(dict.fromkeys(reasons)), (), None
    if len(scopes) > 1:
        return (
            _core.Verdict.UNKNOWN,
            ["historical Space assessments span incomparable registered scopes"],
            tuple(valid_ids),
            None,
        )
    return (
        _core.Verdict.CLEARED,
        [],
        tuple(valid_ids),
        next(iter(scopes)) if len(scopes) == 1 else None,
    )


def _legacy_receipt(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> Receipt:
    """Emit the historical direct-call result without granting live-task authority."""
    store = _core.RuntimeStore(root)
    c_hash = _core.candidate_hash(candidate)
    candidate_state = _core.asdict(candidate)
    candidate_state["candidate_hash"] = c_hash
    candidate_state["mechanism_signature"] = _core.mechanism_signature(candidate)
    candidate_state["content_hash"] = _core.digest(candidate_state)
    store.write_named_state("reality", candidate.candidate_id, candidate_state)

    basic = _core._basic_candidate_errors(candidate)
    if basic:
        verdict = _core.Verdict.UNKNOWN
        reasons = basic
        legacy_ids: tuple[str, ...] = ()
        legacy_scope = None
    else:
        verdict, reasons, legacy_ids, legacy_scope = _legacy_unbound_prior_art(
            store, prior_art_receipt_ids
        )
    metadata = {
        "authority": "SYNTHESIS_ONLY",
        "legacy_unbound_compatibility": True,
        "live_task_bound": False,
        "vnext_attack_bundle_complete": False,
        "release_authority": "NONE_WITHOUT_LIVE_TASK_BINDING",
        "global_novelty_established": False,
        "behavioral_efficacy_established": False,
    }
    bundle = _core._make_bundle(
        bundle_id=_core.new_id("rab"),
        task_id=None,
        obligation_id=candidate.obligation_id,
        candidate_id=candidate.candidate_id,
        candidate_hash_value=c_hash,
        scope_hash=legacy_scope
        or _core.digest(
            {"legacy_candidate_hash": c_hash, "obligation_id": candidate.obligation_id}
        ),
        obligation_set_hash=_core.digest(
            {"legacy_unbound_obligation": candidate.obligation_id}
        ),
        challenge_ids=(),
        selected_discriminator_ids=(),
        nearest_prior_art_receipt_ids=legacy_ids,
        status=verdict,
        unresolved=tuple(reasons),
        metadata=metadata,
    )
    store.write_named_state(
        "reality_attack_bundles", candidate.candidate_id, _core._bundle_to_state(bundle)
    )
    evidence = _core.EvidenceRef(
        evidence_class=_core.EvidenceClass.DERIVED,
        verifier="reality_runtime:v2-legacy-compat",
        provenance_group="reality-synthesis-admission",
        metadata={
            "schema": _core.REALITY_SCHEMA,
            "bundle_id": bundle.bundle_id,
            "bundle_content_hash": bundle.content_hash,
            "authority": "SYNTHESIS_ONLY",
            "admission_only": True,
            "testable_candidate": verdict is _core.Verdict.CLEARED,
            "novelty_established": False,
            "efficacy_established": False,
            "engineering_verified": False,
            "evaluation_cleared": False,
            "execution_authorized": False,
            "host_write_authorized": False,
            "legacy_unbound_compatibility": True,
            "live_task_bound": False,
            "vnext_attack_bundle_complete": False,
            "release_authority": "NONE_WITHOUT_LIVE_TASK_BINDING",
        },
    )
    notes = {
        "schema": _core.REALITY_SCHEMA,
        "authority": "SYNTHESIS_ONLY",
        "admission_only": True,
        "testable_candidate": verdict is _core.Verdict.CLEARED,
        "novelty_established": False,
        "efficacy_established": False,
        "engineering_verified": False,
        "evaluation_cleared": False,
        "execution_authorized": False,
        "host_write_authorized": False,
        "legacy_unbound_compatibility": True,
        "live_task_bound": False,
        "vnext_attack_bundle_complete": False,
        "release_authority": "NONE_WITHOUT_LIVE_TASK_BINDING",
        "candidate_admission_boundary": (
            "legacy direct-call CLEARED preserves the historical API only; it cannot "
            "satisfy a live Soul-routed vNext SYNTHESIS obligation"
        ),
        "prior_art_boundary": (
            "stored Space source-assessment only; global novelty is not established"
        ),
        "bundle_id": bundle.bundle_id,
        "bundle_content_hash": bundle.content_hash,
        "selected_discriminator_ids": [],
        "unresolved": reasons,
    }
    receipt = _core.Receipt(
        receipt_id=_core.new_id("rcpt"),
        module="reality",
        obligation_id=candidate.obligation_id,
        verdict=verdict,
        action="candidate-admission",
        input_hash=c_hash,
        output_hash=bundle.content_hash,
        evidence=(evidence,),
        verifier="reality_runtime:v2-legacy-compat",
        tool_version=_core.REALITY_SCHEMA,
        started_at=_core.utcnow(),
        finished_at=_core.utcnow(),
        unresolved=tuple(reasons),
        notes=json.dumps(notes, sort_keys=True),
        task_id=None,
    )
    store.write_receipt(receipt)
    return receipt


def record_candidate(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> Receipt:
    """Use strict vNext admission for live tasks; isolate historical unbound calls."""
    if not isinstance(candidate, _core.MethodCandidate):
        raise TypeError("candidate must be MethodCandidate")
    if _core._task_context(_core.RuntimeStore(root), candidate) is None:
        return _legacy_receipt(root, candidate, prior_art_receipt_ids)
    return _original_record_candidate(root, candidate, prior_art_receipt_ids)


def run_automatic_synthesis(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> Receipt:
    """Run only the live task-bound Soul-routed vNext path."""
    if _core._task_context(_core.RuntimeStore(root), candidate) is None:
        raise ValueError("automatic synthesis requires a live task-bound SYNTHESIS obligation")
    return record_candidate(root, candidate, prior_art_receipt_ids)


_core.record_candidate = record_candidate
_core.run_automatic_synthesis = run_automatic_synthesis

__all__ = list(_core.__all__)
