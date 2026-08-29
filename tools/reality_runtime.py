"""Reality vNext front-end with bounded historical direct-call compatibility.

The vNext implementation lives in ``reality_runtime_vnext``. This front-end preserves
one pre-vNext API contract: unbound direct ``record_candidate`` calls may still consume
an integrity-valid stored Space source-assessment receipt. That compatibility receipt
has no live task binding and cannot satisfy the strict Soul-routed vNext admission gate.
"""
from __future__ import annotations

import json
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
_original_evaluate_admission = _core.evaluate_admission
_original_record_candidate = _core.record_candidate


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
