"""Reality / Method Synthesis: evidence-bound candidate attack and admission runtime.

Candidate admission is SYNTHESIS_ONLY: it establishes that a candidate is specified
well enough to evaluate. It never establishes global novelty, formal truth,
engineering correctness, empirical efficacy, evaluation clearance, execution
authority, or host-write authority.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from egrt_challenge import (
    ChallengeError,
    ChallengePolicy,
    ChallengeSelectionError,
    propose_challenge,
    record_resolution,
    resolution_for_receipt,
    select_minimum_discriminator,
)
from egrt_challenge_types import (
    ChallengeKind,
    ChallengeOrigin,
    ChallengeRequest,
    ChallengeState,
    DiscriminatorPlan,
    ResolutionOutcome,
)
from egrt_store import RuntimeStore, new_id, utcnow
from egrt_types import EvidenceClass, EvidenceRef, Receipt, Verdict, digest

REALITY_SCHEMA = "egrt.reality.attack.v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MEANINGLESS_ASSUMPTIONS = {
    "",
    "none",
    "no change",
    "same",
    "same assumption",
    "rename only",
    "renamed only",
    "reword only",
    "reworded only",
    "wording only",
    "terminology only",
    "label only",
    "presentation only",
    "cosmetic change",
    "cosmetic only",
}


@dataclass(frozen=True)
class MethodCandidate:
    """Backward-compatible candidate shape.

    New binding information is additive and may be carried in ``metadata``. The
    historical constructor remains unchanged.
    """

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


@dataclass(frozen=True)
class CandidateAttackBundle:
    bundle_id: str
    task_id: str | None
    obligation_id: str
    candidate_id: str
    candidate_hash: str
    scope_hash: str
    obligation_set_hash: str
    challenge_ids: tuple[str, ...]
    selected_discriminator_ids: tuple[str, ...]
    nearest_prior_art_receipt_ids: tuple[str, ...]
    status: Verdict
    unresolved: tuple[str, ...]
    metadata: dict[str, Any]
    metadata_hash: str
    content_hash: str
    schema: str = REALITY_SCHEMA

    def __post_init__(self) -> None:
        for name in ("bundle_id", "obligation_id", "candidate_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.task_id is not None and (
            not isinstance(self.task_id, str) or not self.task_id.strip()
        ):
            raise ValueError("task_id must be non-empty or None")
        for name in (
            "candidate_hash",
            "scope_hash",
            "obligation_set_hash",
            "metadata_hash",
            "content_hash",
        ):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.status, Verdict):
            raise TypeError("status must be Verdict")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be dict")
        if self.metadata_hash != digest(self.metadata):
            raise ValueError("metadata_hash mismatch")
        if self.content_hash != _bundle_content_hash(self):
            raise ValueError("content_hash mismatch")
        if self.schema != REALITY_SCHEMA:
            raise ValueError(f"schema must be {REALITY_SCHEMA}")


@dataclass(frozen=True)
class _TaskContext:
    task_id: str
    obligation_set_hash: str
    dependency_ids: tuple[str, ...]
    discovery_dependency_ids: tuple[str, ...]
    load_bearing: bool


@dataclass(frozen=True)
class _PriorArtState:
    receipt_ids: tuple[str, ...]
    discovery_obligation_id: str | None
    scope_hash: str | None
    claim_scope_hash: str | None
    independence_group_count: int
    derivative_evidence_count: int
    unresolved: tuple[str, ...]
    issues: tuple[str, ...]
    unavailable: tuple[str, ...]


REQUIRED_TEXT = (
    "gap",
    "failed_constraint",
    "changed_assumption",
    "mechanism",
    "actual_delta",
    "negative_control",
    "transfer_target",
    "ablation_plan",
    "verifier_plan",
)


def _require_hash(name: str, value: object) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


def candidate_hash(candidate: MethodCandidate) -> str:
    if not isinstance(candidate, MethodCandidate):
        raise TypeError("candidate must be MethodCandidate")
    return digest(candidate)


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


def _normalize_collection(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({_normalize_text(value) for value in values if _normalize_text(value)}))


def meaningful_changed_assumption(candidate: MethodCandidate) -> bool:
    value = _normalize_text(candidate.changed_assumption)
    if value in _MEANINGLESS_ASSUMPTIONS:
        return False
    if len(value) < 4:
        return False
    baseline = candidate.metadata.get("baseline_assumption")
    if isinstance(baseline, str) and _normalize_text(baseline) == value:
        return False
    cosmetic = candidate.metadata.get("change_class")
    if isinstance(cosmetic, str) and _normalize_text(cosmetic) in {
        "wording",
        "terminology",
        "label",
        "presentation",
        "cosmetic",
    }:
        return False
    return True


def mechanism_signature(candidate: MethodCandidate) -> str:
    """Deterministic structural signature; different signatures are not novelty proof."""
    metadata = candidate.metadata
    causal_route = metadata.get("causal_route", candidate.mechanism)
    intervention = metadata.get("intervention", candidate.negative_control)
    required_information = metadata.get("required_information", candidate.inputs)
    predicted_behavior = metadata.get("predicted_behavior", candidate.outputs)
    if isinstance(required_information, str):
        required_information = (required_information,)
    if isinstance(predicted_behavior, str):
        predicted_behavior = (predicted_behavior,)
    if not isinstance(required_information, (list, tuple, set)):
        required_information = candidate.inputs
    if not isinstance(predicted_behavior, (list, tuple, set)):
        predicted_behavior = candidate.outputs
    return digest(
        {
            "changed_assumption": _normalize_text(candidate.changed_assumption),
            "mechanism": _normalize_text(candidate.mechanism),
            "causal_route": _normalize_text(str(causal_route)),
            "intervention": _normalize_text(str(intervention)),
            "dependencies": _normalize_collection(candidate.dependencies),
            "required_information": _normalize_collection(
                tuple(str(item) for item in required_information)
            ),
            "failure_modes": _normalize_collection(candidate.failure_modes),
            "predicted_behavior": _normalize_collection(
                tuple(str(item) for item in predicted_behavior)
            ),
        }
    )


def diversity_matrix(candidates: Sequence[MethodCandidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            left_tags = {_normalize_text(tag) for tag in left.tags}
            right_tags = {_normalize_text(tag) for tag in right.tags}
            union = left_tags | right_tags
            assumption_same = _normalize_text(left.changed_assumption) == _normalize_text(
                right.changed_assumption
            )
            mechanism_same = _normalize_text(left.mechanism) == _normalize_text(
                right.mechanism
            )
            signature_same = mechanism_signature(left) == mechanism_signature(right)
            rows.append(
                {
                    "left": left.candidate_id,
                    "right": right.candidate_id,
                    "changed_assumption_same": assumption_same,
                    "mechanism_same": mechanism_same,
                    "mechanism_signature_same": signature_same,
                    "meaningfully_distinct": not signature_same,
                    "tag_jaccard": (len(left_tags & right_tags) / len(union)) if union else 1.0,
                    "diagnostic_only": True,
                    "novelty_established": False,
                }
            )
    return rows


def _basic_candidate_errors(candidate: MethodCandidate) -> list[str]:
    errors: list[str] = []
    if not isinstance(candidate, MethodCandidate):
        return ["candidate must be MethodCandidate"]
    for name in REQUIRED_TEXT:
        value = getattr(candidate, name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{name} is required")
    for name in (
        "candidate_id",
        "obligation_id",
    ):
        value = getattr(candidate, name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{name} is required")
    if not candidate.nearest_prior_art:
        errors.append("nearest_prior_art is required")
    if not candidate.failure_modes:
        errors.append("failure_modes are required")
    if not candidate.inputs:
        errors.append("inputs are required")
    if not candidate.outputs:
        errors.append("outputs are required")
    return errors


def _task_context(store: RuntimeStore, candidate: MethodCandidate) -> _TaskContext | None:
    task_id = candidate.metadata.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        task_id = store.task_for_obligation(candidate.obligation_id)
    if not isinstance(task_id, str) or not task_id:
        return None
    task = store.read_task(task_id)
    if task is None:
        return None
    obligations = task.get("obligations")
    if not isinstance(obligations, list):
        return None
    row: Mapping[str, Any] | None = None
    by_id: dict[str, Mapping[str, Any]] = {}
    for item in obligations:
        if not isinstance(item, Mapping):
            continue
        ident = str(item.get("obligation_id") or "")
        if ident:
            by_id[ident] = item
        if ident == candidate.obligation_id:
            row = item
    if row is None:
        return None
    if str(row.get("kind")) != "SYNTHESIS":
        return None
    metadata = row.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    raw_dependencies = metadata.get("depends_on", [])
    dependencies = tuple(
        str(item) for item in raw_dependencies if isinstance(item, str) and item
    ) if isinstance(raw_dependencies, (list, tuple)) else ()
    discovery = tuple(
        dep
        for dep in dependencies
        if dep in by_id and str(by_id[dep].get("kind")) == "DISCOVERY"
    )
    task_metadata = task.get("metadata")
    task_metadata = task_metadata if isinstance(task_metadata, Mapping) else {}
    obligation_set_hash = task_metadata.get("soul_obligation_set_hash")
    if not isinstance(obligation_set_hash, str) or not _SHA256.fullmatch(
        obligation_set_hash
    ):
        obligation_set_hash = digest(
            {
                "task_id": task_id,
                "obligations": obligations,
            }
        )
    return _TaskContext(
        task_id=task_id,
        obligation_set_hash=obligation_set_hash,
        dependency_ids=dependencies,
        discovery_dependency_ids=discovery,
        load_bearing=bool(row.get("load_bearing", True)),
    )


def _receipt_evidence(receipt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = receipt.get("evidence", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _search_receipt_state(
    store: RuntimeStore,
    assessment: Mapping[str, Any],
    *,
    expected_candidate_hash: str,
    expected_task_id: str | None,
) -> tuple[Mapping[str, Any] | None, list[str], list[str]]:
    unresolved: list[str] = []
    issues: list[str] = []
    notes = assessment.get("notes")
    parsed: Mapping[str, Any] = {}
    if isinstance(notes, str):
        try:
            loaded = json.loads(notes)
            if isinstance(loaded, Mapping):
                parsed = loaded
        except json.JSONDecodeError:
            issues.append("Space source-assessment notes are not valid JSON")
    search_receipt_id = parsed.get("search_receipt_id")
    if not isinstance(search_receipt_id, str) or not search_receipt_id:
        unresolved.append("Space source-assessment lacks bound search_receipt_id")
        return None, unresolved, issues
    search = store.read_receipt(search_receipt_id)
    if search is None:
        unresolved.append("bound Space retrieval receipt is missing or corrupt")
        return None, unresolved, issues
    if search.get("module") != "space" or search.get("action") != "multi-index-retrieval":
        issues.append("source-assessment does not bind a Space retrieval receipt")
        return search, unresolved, issues
    if search.get("obligation_id") != assessment.get("obligation_id"):
        issues.append("source-assessment and retrieval obligation bindings differ")
    if expected_task_id is not None and search.get("task_id") not in (
        None,
        expected_task_id,
    ):
        issues.append("Space retrieval task binding mismatch")
    evidence = _receipt_evidence(search)
    metadata = evidence[0].get("metadata") if evidence else None
    metadata = metadata if isinstance(metadata, Mapping) else {}
    bound_candidate_hash = metadata.get("candidate_hash")
    if bound_candidate_hash != expected_candidate_hash:
        issues.append("Space retrieval candidate_hash does not bind this candidate")
    return search, unresolved, issues


def _space_scope_hash(search: Mapping[str, Any] | None) -> str | None:
    if search is None:
        return None
    for evidence in _receipt_evidence(search):
        metadata = evidence.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        value = metadata.get("registered_search_scope_hash")
        if isinstance(value, str) and _SHA256.fullmatch(value):
            return value
    return None


def _assessed_claim_scopes(assessment: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for evidence in _receipt_evidence(assessment):
        if str(evidence.get("evidence_class")) != EvidenceClass.CITED.value:
            continue
        metadata = evidence.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        value = metadata.get("claim_scope")
        if isinstance(value, str) and value.strip():
            values.add(_normalize_text(value))
    return tuple(sorted(values))


def _space_prior_art_state(
    store: RuntimeStore,
    candidate: MethodCandidate,
    receipt_ids: Sequence[str],
    context: _TaskContext | None,
) -> _PriorArtState:
    unresolved: list[str] = []
    issues: list[str] = []
    unavailable: list[str] = []
    valid_ids: list[str] = []
    scopes: set[str] = set()
    claim_scopes: set[str] = set()
    discovery_obligations: set[str] = set()
    independence_groups: set[str] = set()
    evidence_count = 0
    expected_candidate_hash = candidate_hash(candidate)

    if not receipt_ids:
        unresolved.append("no stored Space source-assessment receipt supplied")
    explicit_prior_art_obligation = candidate.metadata.get("prior_art_obligation_id")
    allowed_dependencies: set[str] = set()
    if context is not None:
        allowed_dependencies.update(context.discovery_dependency_ids)
        if not allowed_dependencies:
            unresolved.append(
                "SYNTHESIS obligation has no dependency-ready DISCOVERY prior-art obligation"
            )
    elif isinstance(explicit_prior_art_obligation, str) and explicit_prior_art_obligation:
        allowed_dependencies.add(explicit_prior_art_obligation)

    for receipt_id in receipt_ids:
        if not isinstance(receipt_id, str) or not receipt_id:
            issues.append("prior-art receipt identifier must be non-empty")
            continue
        receipt = store.read_receipt(receipt_id)
        if receipt is None:
            unresolved.append(f"prior-art receipt {receipt_id} is missing or corrupt")
            continue
        if receipt.get("module") != "space":
            issues.append(f"{receipt_id} is not a Space receipt")
            continue
        if receipt.get("action") != "source-assessment":
            unresolved.append(f"{receipt_id} is retrieval-only, not source-assessment")
            continue
        if receipt.get("verdict") == Verdict.UNAVAILABLE.value:
            unavailable.append(f"{receipt_id} Space assessment is unavailable")
            continue
        if receipt.get("verdict") != Verdict.CLEARED.value:
            unresolved.append(f"{receipt_id} Space source-assessment is not CLEARED")
            continue
        obligation_id = str(receipt.get("obligation_id") or "")
        if allowed_dependencies and obligation_id not in allowed_dependencies:
            issues.append(
                f"{receipt_id} is bound to the wrong prior-art obligation {obligation_id}"
            )
            continue
        if context is not None and receipt.get("task_id") not in (None, context.task_id):
            issues.append(f"{receipt_id} Space assessment task binding mismatch")
            continue
        search, search_unresolved, search_issues = _search_receipt_state(
            store,
            receipt,
            expected_candidate_hash=expected_candidate_hash,
            expected_task_id=context.task_id if context else None,
        )
        unresolved.extend(search_unresolved)
        issues.extend(search_issues)
        if search_unresolved or search_issues:
            continue
        scope_hash = _space_scope_hash(search)
        if scope_hash is None:
            unresolved.append(f"{receipt_id} lacks a registered Space scope hash")
            continue
        explicit_scope = candidate.metadata.get("scope_hash")
        if isinstance(explicit_scope, str):
            if not _SHA256.fullmatch(explicit_scope):
                issues.append("candidate metadata scope_hash is malformed")
                continue
            if explicit_scope != scope_hash:
                issues.append("candidate scope_hash does not match assessed Space scope")
                continue
        scopes.add(scope_hash)
        scopes_for_receipt = _assessed_claim_scopes(receipt)
        if not scopes_for_receipt:
            unresolved.append(f"{receipt_id} has no claim-scoped cited evidence")
            continue
        expected_claim_scope = candidate.metadata.get("prior_art_claim_scope")
        if isinstance(expected_claim_scope, str) and _normalize_text(
            expected_claim_scope
        ) not in scopes_for_receipt:
            issues.append("Space assessment claim scope does not match candidate prior-art scope")
            continue
        claim_scopes.update(scopes_for_receipt)
        for evidence in _receipt_evidence(receipt):
            if str(evidence.get("evidence_class")) != EvidenceClass.CITED.value:
                continue
            artifact = evidence.get("artifact")
            if not isinstance(artifact, Mapping) or not artifact.get("sha256"):
                unresolved.append(f"{receipt_id} contains uncontent-addressed cited evidence")
                continue
            metadata = evidence.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            group = metadata.get("independence_group_hash")
            if isinstance(group, str) and group:
                independence_groups.add(group)
            evidence_count += 1
        valid_ids.append(receipt_id)
        discovery_obligations.add(obligation_id)

    if len(scopes) > 1:
        unresolved.append("prior-art assessments span incomparable registered Space scopes")
    if len(discovery_obligations) > 1:
        unresolved.append("prior-art assessments span multiple discovery obligations")
    return _PriorArtState(
        receipt_ids=tuple(valid_ids),
        discovery_obligation_id=(
            next(iter(discovery_obligations)) if len(discovery_obligations) == 1 else None
        ),
        scope_hash=(next(iter(scopes)) if len(scopes) == 1 else None),
        claim_scope_hash=(digest(tuple(sorted(claim_scopes))) if claim_scopes else None),
        independence_group_count=len(independence_groups),
        derivative_evidence_count=max(0, evidence_count - len(independence_groups)),
        unresolved=tuple(dict.fromkeys(unresolved)),
        issues=tuple(dict.fromkeys(issues)),
        unavailable=tuple(dict.fromkeys(unavailable)),
    )


def admission(
    candidate: MethodCandidate,
    prior_art_receipts: Sequence[Mapping[str, Any]],
) -> tuple[Verdict, list[str]]:
    """Compatibility preflight.

    Raw/caller-supplied receipt dictionaries can never clear Reality. Stored receipt
    integrity and cross-receipt bindings are resolved only by ``record_candidate`` or
    ``evaluate_admission``.
    """
    errors = _basic_candidate_errors(candidate)
    if errors:
        return Verdict.UNKNOWN, errors
    if not meaningful_changed_assumption(candidate):
        return Verdict.ISSUE, ["candidate has no meaningful changed assumption"]
    if prior_art_receipts:
        return Verdict.UNKNOWN, [
            "caller-supplied prior-art dictionaries have no evidence authority; "
            "resolve receipt ids through RuntimeStore"
        ]
    return Verdict.UNKNOWN, ["stored Space source-assessment evidence is required"]


def _challenge_request(
    *,
    task_id: str,
    obligation_id: str,
    kind: ChallengeKind,
    candidate: MethodCandidate,
    scope_hash: str,
    obligation_set_hash: str,
    hypothesis: str,
    alternative: str | None,
    refuter: str,
    consequence: str,
    load_bearing: bool,
    capability: str,
    metadata: dict[str, Any],
) -> ChallengeRequest:
    return ChallengeRequest(
        challenge_id=new_id("chal"),
        task_id=task_id,
        obligation_id=obligation_id,
        target_module="reality",
        origin=ChallengeOrigin.MODULE_NATIVE,
        kind=kind,
        hypothesis=hypothesis,
        alternative=alternative,
        refuter=refuter,
        consequence_if_true=consequence,
        load_bearing=load_bearing,
        required_capability=capability,
        candidate_hash=candidate_hash(candidate),
        scope_hash=scope_hash,
        obligation_set_hash=obligation_set_hash,
        proposer="reality_runtime:auto-challenge",
        proposer_provenance=REALITY_SCHEMA,
        information_rank=5 if load_bearing else 4,
        risk_rank=5 if load_bearing else 3,
        cost_rank=1 if kind is ChallengeKind.NOVELTY_COSTUME else 2,
        metadata=metadata,
    )


def _propose(
    root: Path,
    request: ChallengeRequest,
) -> str:
    propose_challenge(root, request)
    return request.challenge_id


def _select_one(
    root: Path,
    challenge_id: str,
    *,
    action: str,
    verifier_module: str,
    capability: str,
    support: str,
    refute: str,
    cost: int = 1,
) -> str:
    plan = DiscriminatorPlan(
        plan_id=new_id("dplan"),
        challenge_id=challenge_id,
        mode="NATIVE",
        action=action,
        verifier_module=verifier_module,
        required_capability=capability,
        expected_support_signal=support,
        expected_refute_signal=refute,
        max_cost_rank=cost,
        metadata={
            "capability_available": True,
            "discrimination_rank": 5,
            "information_rank": 5,
            "risk_reduction_rank": 5,
            "irreversibility_rank": 0,
            "global_cost_optimality_established": False,
        },
    )
    selected = select_minimum_discriminator(
        root,
        challenge_id,
        [plan],
        policy=ChallengePolicy.from_root(root),
    )
    return selected.plan_id


def _objective_override(candidate: MethodCandidate, name: str) -> dict[str, int | bool]:
    raw_all = candidate.metadata.get("discriminator_objectives")
    if not isinstance(raw_all, Mapping):
        return {}
    raw = raw_all.get(name)
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, int | bool] = {}
    for key in (
        "capability_available",
        "discrimination_rank",
        "information_rank",
        "risk_reduction_rank",
        "cost_rank",
        "irreversibility_rank",
    ):
        value = raw.get(key)
        if isinstance(value, bool) and key == "capability_available":
            out[key] = value
        elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[key] = value
    return out


def _discriminator_plans(
    candidate: MethodCandidate,
    challenge_id: str,
) -> list[DiscriminatorPlan]:
    defaults = {
        "negative_control": {
            "discrimination_rank": 5,
            "information_rank": 5,
            "risk_reduction_rank": 5,
            "cost_rank": 1,
            "irreversibility_rank": 0,
        },
        "ablation": {
            "discrimination_rank": 5,
            "information_rank": 5,
            "risk_reduction_rank": 5,
            "cost_rank": 2,
            "irreversibility_rank": 0,
        },
        "transfer": {
            "discrimination_rank": 5,
            "information_rank": 5,
            "risk_reduction_rank": 5,
            "cost_rank": 3,
            "irreversibility_rank": 0,
        },
    }
    actions = {
        "negative_control": candidate.negative_control,
        "ablation": candidate.ablation_plan,
        "transfer": candidate.transfer_target,
    }
    support = {
        "negative_control": "removing the claimed mechanism removes or materially changes the predicted advantage",
        "ablation": "component-specific ablation produces the predeclared differentiating signal",
        "transfer": "the mechanism survives the declared meaningful context change",
    }
    refute = {
        "negative_control": "claimed advantage survives removal of the alleged mechanism",
        "ablation": "component-specific ablation leaves the predicted behavior materially unchanged",
        "transfer": "the claimed mechanism fails under the declared transfer target",
    }
    plans: list[DiscriminatorPlan] = []
    for name in ("negative_control", "ablation", "transfer"):
        objective = dict(defaults[name])
        objective.update(_objective_override(candidate, name))
        cost = int(objective.pop("cost_rank"))
        plans.append(
            DiscriminatorPlan(
                plan_id=new_id(f"dplan-{name}"),
                challenge_id=challenge_id,
                mode="NATIVE",
                action=actions[name],
                verifier_module="time",
                required_capability="BOUNDED_EMPIRICAL_DISCRIMINATOR",
                expected_support_signal=support[name],
                expected_refute_signal=refute[name],
                max_cost_rank=cost,
                metadata={
                    "family": name,
                    "capability_available": objective.pop("capability_available", True),
                    **objective,
                    "global_cost_optimality_established": False,
                },
            )
        )
    return plans


def _bundle_payload(
    *,
    bundle_id: str,
    task_id: str | None,
    obligation_id: str,
    candidate_id: str,
    candidate_hash_value: str,
    scope_hash: str,
    obligation_set_hash: str,
    challenge_ids: tuple[str, ...],
    selected_discriminator_ids: tuple[str, ...],
    nearest_prior_art_receipt_ids: tuple[str, ...],
    status: Verdict,
    unresolved: tuple[str, ...],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "bundle_id": bundle_id,
        "task_id": task_id,
        "obligation_id": obligation_id,
        "candidate_id": candidate_id,
        "candidate_hash": candidate_hash_value,
        "scope_hash": scope_hash,
        "obligation_set_hash": obligation_set_hash,
        "challenge_ids": challenge_ids,
        "selected_discriminator_ids": selected_discriminator_ids,
        "nearest_prior_art_receipt_ids": nearest_prior_art_receipt_ids,
        "status": status,
        "unresolved": unresolved,
        "metadata": metadata,
        "metadata_hash": digest(metadata),
        "schema": REALITY_SCHEMA,
    }


def _bundle_content_hash(bundle: CandidateAttackBundle) -> str:
    return digest(
        _bundle_payload(
            bundle_id=bundle.bundle_id,
            task_id=bundle.task_id,
            obligation_id=bundle.obligation_id,
            candidate_id=bundle.candidate_id,
            candidate_hash_value=bundle.candidate_hash,
            scope_hash=bundle.scope_hash,
            obligation_set_hash=bundle.obligation_set_hash,
            challenge_ids=bundle.challenge_ids,
            selected_discriminator_ids=bundle.selected_discriminator_ids,
            nearest_prior_art_receipt_ids=bundle.nearest_prior_art_receipt_ids,
            status=bundle.status,
            unresolved=bundle.unresolved,
            metadata=bundle.metadata,
        )
    )


def _make_bundle(**kwargs: Any) -> CandidateAttackBundle:
    payload = _bundle_payload(**kwargs)
    return CandidateAttackBundle(**payload, content_hash=digest(payload))


def _bundle_to_state(bundle: CandidateAttackBundle) -> dict[str, Any]:
    row = asdict(bundle)
    row["status"] = bundle.status.value
    return row


def _bundle_from_state(row: Mapping[str, Any]) -> CandidateAttackBundle:
    return CandidateAttackBundle(
        bundle_id=str(row["bundle_id"]),
        task_id=str(row["task_id"]) if row.get("task_id") is not None else None,
        obligation_id=str(row["obligation_id"]),
        candidate_id=str(row["candidate_id"]),
        candidate_hash=str(row["candidate_hash"]),
        scope_hash=str(row["scope_hash"]),
        obligation_set_hash=str(row["obligation_set_hash"]),
        challenge_ids=tuple(str(item) for item in row.get("challenge_ids", [])),
        selected_discriminator_ids=tuple(
            str(item) for item in row.get("selected_discriminator_ids", [])
        ),
        nearest_prior_art_receipt_ids=tuple(
            str(item) for item in row.get("nearest_prior_art_receipt_ids", [])
        ),
        status=Verdict(str(row["status"])),
        unresolved=tuple(str(item) for item in row.get("unresolved", [])),
        metadata=dict(row.get("metadata") or {}),
        metadata_hash=str(row["metadata_hash"]),
        content_hash=str(row["content_hash"]),
        schema=str(row.get("schema") or REALITY_SCHEMA),
    )


def load_attack_bundle(root: Path, candidate_id: str) -> CandidateAttackBundle | None:
    row = RuntimeStore(root).read_named_state("reality_attack_bundles", candidate_id)
    if row is None:
        return None
    try:
        return _bundle_from_state(row)
    except (KeyError, TypeError, ValueError):
        return None


def create_attack_bundle(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> CandidateAttackBundle:
    store = RuntimeStore(root)
    existing = load_attack_bundle(root, candidate.candidate_id)
    if existing is not None:
        if existing.candidate_hash != candidate_hash(candidate):
            raise ValueError("stored attack bundle is bound to a different candidate hash")
        return existing

    context = _task_context(store, candidate)
    prior = _space_prior_art_state(store, candidate, prior_art_receipt_ids, context)
    fallback_scope = candidate.metadata.get("scope_hash")
    if not isinstance(fallback_scope, str) or not _SHA256.fullmatch(fallback_scope):
        fallback_scope = digest(
            {
                "candidate_hash": candidate_hash(candidate),
                "obligation_id": candidate.obligation_id,
                "gap": candidate.gap,
                "failed_constraint": candidate.failed_constraint,
            }
        )
    scope_hash = prior.scope_hash or fallback_scope
    obligation_set_hash = (
        context.obligation_set_hash
        if context is not None
        else digest({"unbound_obligation": candidate.obligation_id})
    )
    task_id = context.task_id if context is not None else None
    challenges: list[str] = []
    selected: list[str] = []
    unresolved: list[str] = [*prior.unresolved, *prior.issues, *prior.unavailable]
    metadata: dict[str, Any] = {
        "authority": "SYNTHESIS_ONLY",
        "candidate_mechanism_signature": mechanism_signature(candidate),
        "meaningful_changed_assumption": meaningful_changed_assumption(candidate),
        "prior_art_claim_scope_hash": prior.claim_scope_hash,
        "prior_art_independence_group_count": prior.independence_group_count,
        "prior_art_derivative_evidence_count": prior.derivative_evidence_count,
        "registered_space_scope_hash": prior.scope_hash,
        "competing_mechanism_required": bool(
            candidate.metadata.get("competing_mechanism_required")
        ),
        "global_novelty_established": False,
        "behavioral_efficacy_established": False,
    }

    if context is None:
        unresolved.append("candidate is not bound to a live SYNTHESIS task")
        status = Verdict.ISSUE if prior.issues else (
            Verdict.UNAVAILABLE if prior.unavailable else Verdict.UNKNOWN
        )
        bundle = _make_bundle(
            bundle_id=new_id("rab"),
            task_id=None,
            obligation_id=candidate.obligation_id,
            candidate_id=candidate.candidate_id,
            candidate_hash_value=candidate_hash(candidate),
            scope_hash=scope_hash,
            obligation_set_hash=obligation_set_hash,
            challenge_ids=(),
            selected_discriminator_ids=(),
            nearest_prior_art_receipt_ids=prior.receipt_ids,
            status=status,
            unresolved=tuple(dict.fromkeys(unresolved)),
            metadata=metadata,
        )
        store.write_named_state(
            "reality_attack_bundles", candidate.candidate_id, _bundle_to_state(bundle)
        )
        return bundle

    policy = ChallengePolicy.from_root(root)
    if policy.mode == "off":
        unresolved.append("neutral challenge layer is OFF")
        bundle = _make_bundle(
            bundle_id=new_id("rab"),
            task_id=context.task_id,
            obligation_id=candidate.obligation_id,
            candidate_id=candidate.candidate_id,
            candidate_hash_value=candidate_hash(candidate),
            scope_hash=scope_hash,
            obligation_set_hash=obligation_set_hash,
            challenge_ids=(),
            selected_discriminator_ids=(),
            nearest_prior_art_receipt_ids=prior.receipt_ids,
            status=Verdict.UNAVAILABLE,
            unresolved=tuple(dict.fromkeys(unresolved)),
            metadata=metadata,
        )
        store.write_named_state(
            "reality_attack_bundles", candidate.candidate_id, _bundle_to_state(bundle)
        )
        return bundle

    costume_obligation = prior.discovery_obligation_id or (
        context.discovery_dependency_ids[0] if len(context.discovery_dependency_ids) == 1 else None
    )
    if costume_obligation is not None:
        costume = _challenge_request(
            task_id=context.task_id,
            obligation_id=costume_obligation,
            kind=ChallengeKind.NOVELTY_COSTUME,
            candidate=candidate,
            scope_hash=scope_hash,
            obligation_set_hash=obligation_set_hash,
            hypothesis=(
                "the concrete candidate has a mechanism/assumption delta not matched "
                "by the nearest assessed prior art within the registered Space scope"
            ),
            alternative=(
                "the candidate is a known mechanism in new terminology, packaging, "
                "decomposition, or naming"
            ),
            refuter="claim-scoped current Space source-assessment showing a mechanism match",
            consequence=(
                "a costume match blocks SYNTHESIS admission; a scoped non-match supports "
                "testability only and is not global novelty"
            ),
            load_bearing=True,
            capability="ASSESSED_PRIOR_ART",
            metadata={
                "changed_assumption_hash": digest(_normalize_text(candidate.changed_assumption)),
                "mechanism_signature": mechanism_signature(candidate),
                "nearest_prior_art": list(candidate.nearest_prior_art),
                "candidate_prior_art_receipt_ids": list(prior.receipt_ids),
                "global_novelty_established": False,
            },
        )
        try:
            challenges.append(_propose(root, costume))
            if prior.receipt_ids and prior.scope_hash is not None and not prior.issues:
                resolution = resolution_for_receipt(
                    root,
                    costume.challenge_id,
                    prior.receipt_ids[0],
                    outcome=ResolutionOutcome.SUPPORTS_BASE,
                    resolver="reality_runtime:space-binding",
                    resolver_provenance=REALITY_SCHEMA,
                    reason=(
                        "current integrity-valid claim-scoped Space assessment grounds "
                        "the costume decision within registered scope only"
                    ),
                )
                record_resolution(root, resolution)
        except ChallengeError as exc:
            unresolved.append(f"NOVELTY_COSTUME challenge unavailable: {exc}")
    else:
        unresolved.append("NOVELTY_COSTUME lacks a unique discovery obligation binding")

    assumption = _challenge_request(
        task_id=context.task_id,
        obligation_id=candidate.obligation_id,
        kind=ChallengeKind.ASSUMPTION_KNOCKOUT,
        candidate=candidate,
        scope_hash=scope_hash,
        obligation_set_hash=obligation_set_hash,
        hypothesis="the claimed changed assumption is load-bearing for the candidate mechanism",
        alternative="the candidate behaves materially the same when the assumption is restored or neutralized",
        refuter=candidate.negative_control,
        consequence="cosmetic or incorrectly attributed assumption change blocks admission",
        load_bearing=True,
        capability="ASSUMPTION_KNOCKOUT",
        metadata={
            "changed_assumption": candidate.changed_assumption,
            "knockout_intervention": candidate.negative_control,
            "expected_symptom": candidate.metadata.get(
                "assumption_knockout_expected_symptom",
                "predicted mechanism-specific behavior materially changes",
            ),
            "empirical_result_established": False,
        },
    )
    try:
        challenges.append(_propose(root, assumption))
        if meaningful_changed_assumption(candidate):
            selected.append(
                _select_one(
                    root,
                    assumption.challenge_id,
                    action=(
                        "restore or neutralize the claimed changed assumption; "
                        + candidate.negative_control
                    ),
                    verifier_module="time",
                    capability="ASSUMPTION_KNOCKOUT",
                    support=(
                        "neutralizing the changed assumption removes or materially "
                        "changes the mechanism-specific behavior"
                    ),
                    refute="candidate behavior remains materially identical",
                )
            )
        else:
            store.update_challenge_state(
                assumption.challenge_id,
                ChallengeState.UNRESOLVED.value,
                reason="no meaningful changed assumption is specified",
                component="reality",
            )
            unresolved.append("candidate has no meaningful changed assumption")
    except ChallengeError as exc:
        unresolved.append(f"ASSUMPTION_KNOCKOUT challenge unavailable: {exc}")

    competing_value = candidate.metadata.get("competing_mechanism")
    competing = competing_value.strip() if isinstance(competing_value, str) else ""
    competing_required = bool(candidate.metadata.get("competing_mechanism_required"))
    competing_challenge = _challenge_request(
        task_id=context.task_id,
        obligation_id=candidate.obligation_id,
        kind=ChallengeKind.COMPETING_MECHANISM,
        candidate=candidate,
        scope_hash=scope_hash,
        obligation_set_hash=obligation_set_hash,
        hypothesis="candidate mechanism A is the best represented explanation for the named gap",
        alternative=competing or None,
        refuter=str(
            candidate.metadata.get(
                "competing_discriminator",
                "one bounded discriminator that predicts different behavior under A versus B",
            )
        ),
        consequence="a credible competing explanation must remain explicit until distinguished",
        load_bearing=False,
        capability="MECHANISM_COMPARISON",
        metadata={
            "mechanism_a": candidate.mechanism,
            "mechanism_b": competing or None,
            "mechanism_family": candidate.metadata.get("competing_mechanism_family"),
            "alternative_assumptions": candidate.metadata.get(
                "competing_mechanism_assumptions"
            ),
            "expected_differing_behavior": candidate.metadata.get(
                "competing_expected_differing_behavior"
            ),
            "bundle_gate_required": competing_required or bool(competing),
        },
    )
    try:
        challenges.append(_propose(root, competing_challenge))
        if competing:
            # The bounded MINIMUM_DISCRIMINATOR challenge below owns the one selected
            # empirical plan. Keeping this comparison proposed avoids double-counting
            # the same experiment against the neutral selected-discriminator budget.
            pass
        elif competing_required:
            store.update_challenge_state(
                competing_challenge.challenge_id,
                ChallengeState.UNRESOLVED.value,
                reason="competing mechanism required but no credible alternative is bound",
                component="reality",
            )
            unresolved.append("required competing mechanism is missing")
        else:
            store.update_challenge_state(
                competing_challenge.challenge_id,
                ChallengeState.DISMISSED_NOT_APPLICABLE.value,
                reason="no credible competing mechanism recorded after scoped prior-art work",
                component="reality",
            )
    except ChallengeError as exc:
        unresolved.append(f"COMPETING_MECHANISM challenge unavailable: {exc}")

    discriminator = _challenge_request(
        task_id=context.task_id,
        obligation_id=candidate.obligation_id,
        kind=ChallengeKind.MINIMUM_DISCRIMINATOR,
        candidate=candidate,
        scope_hash=scope_hash,
        obligation_set_hash=obligation_set_hash,
        hypothesis="one smallest useful registered discriminator can distinguish the candidate mechanism",
        alternative="available discriminators are incomparable or unavailable",
        refuter="Pareto selection over discrimination/information/risk versus cost/irreversibility",
        consequence="incomparable discriminator choice remains explicitly unresolved",
        load_bearing=False,
        capability="DISCRIMINATOR_SELECTION",
        metadata={
            "families": ["negative_control", "ablation", "transfer"],
            "global_cost_optimality_established": False,
            "execution_authorized": False,
        },
    )
    try:
        challenges.append(_propose(root, discriminator))
        try:
            chosen = select_minimum_discriminator(
                root,
                discriminator.challenge_id,
                _discriminator_plans(candidate, discriminator.challenge_id),
                policy=policy,
            )
            selected.append(chosen.plan_id)
            metadata["minimum_discriminator_family"] = chosen.metadata.get("family")
            metadata["minimum_discriminator_plan_id"] = chosen.plan_id
        except ChallengeSelectionError as exc:
            unresolved.append(f"minimum discriminator unresolved: {exc}")
    except ChallengeError as exc:
        unresolved.append(f"MINIMUM_DISCRIMINATOR challenge unavailable: {exc}")

    status = Verdict.CLEARED
    if prior.unavailable:
        status = Verdict.UNAVAILABLE
    if prior.unresolved or not prior.receipt_ids or prior.scope_hash is None:
        status = Verdict.UNKNOWN
    if prior.issues or not meaningful_changed_assumption(candidate):
        status = Verdict.ISSUE
    if any("unresolved" in item.lower() for item in unresolved) and status is Verdict.CLEARED:
        status = Verdict.UNKNOWN

    bundle = _make_bundle(
        bundle_id=new_id("rab"),
        task_id=context.task_id,
        obligation_id=candidate.obligation_id,
        candidate_id=candidate.candidate_id,
        candidate_hash_value=candidate_hash(candidate),
        scope_hash=scope_hash,
        obligation_set_hash=obligation_set_hash,
        challenge_ids=tuple(challenges),
        selected_discriminator_ids=tuple(selected),
        nearest_prior_art_receipt_ids=prior.receipt_ids,
        status=status,
        unresolved=tuple(dict.fromkeys(unresolved)),
        metadata=metadata,
    )
    store.write_named_state(
        "reality_attack_bundles", candidate.candidate_id, _bundle_to_state(bundle)
    )
    return bundle


def _challenge_by_kind(
    store: RuntimeStore,
    bundle: CandidateAttackBundle,
) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for challenge_id in bundle.challenge_ids:
        row = store.read_challenge(challenge_id)
        if row is None:
            continue
        kind = str(row.get("kind") or "")
        out[kind] = row
    return out


def _challenge_binding_errors(
    bundle: CandidateAttackBundle,
    challenge: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if challenge.get("candidate_hash") != bundle.candidate_hash:
        errors.append("challenge candidate_hash mismatch")
    if challenge.get("scope_hash") != bundle.scope_hash:
        errors.append("challenge scope_hash mismatch")
    if challenge.get("obligation_set_hash") != bundle.obligation_set_hash:
        errors.append("challenge obligation_set_hash mismatch")
    if bundle.task_id is not None and challenge.get("task_id") != bundle.task_id:
        errors.append("challenge task_id mismatch")
    return errors


def _self_certification_present(
    store: RuntimeStore,
    challenges: Mapping[str, Mapping[str, Any]],
) -> bool:
    for challenge in challenges.values():
        resolution = store.latest_resolution(str(challenge.get("challenge_id") or ""))
        if not isinstance(resolution, Mapping):
            continue
        if (
            resolution.get("state") == ChallengeState.RESOLVED.value
            and resolution.get("outcome") == ResolutionOutcome.SUPPORTS_BASE.value
            and resolution.get("verifier_module") == "reality"
        ):
            return True
    return False


def evaluate_admission(
    root: Path,
    candidate: MethodCandidate,
    bundle: CandidateAttackBundle | None = None,
) -> tuple[Verdict, list[str]]:
    store = RuntimeStore(root)
    reasons = _basic_candidate_errors(candidate)
    if reasons:
        return Verdict.UNKNOWN, reasons
    if bundle is None:
        bundle = load_attack_bundle(root, candidate.candidate_id)
    if bundle is None:
        return Verdict.UNKNOWN, ["CandidateAttackBundle is required"]
    try:
        CandidateAttackBundle(**{
            **asdict(bundle),
            "status": bundle.status,
        })
    except (TypeError, ValueError):
        return Verdict.ISSUE, ["CandidateAttackBundle integrity validation failed"]
    expected_candidate_hash = candidate_hash(candidate)
    if bundle.candidate_hash != expected_candidate_hash:
        return Verdict.ISSUE, ["CandidateAttackBundle candidate_hash mismatch"]
    if bundle.obligation_id != candidate.obligation_id:
        return Verdict.ISSUE, ["CandidateAttackBundle obligation_id mismatch"]
    context = _task_context(store, candidate)
    if context is None:
        return Verdict.UNKNOWN, ["candidate is not bound to a live SYNTHESIS task"]
    if bundle.task_id != context.task_id:
        return Verdict.ISSUE, ["CandidateAttackBundle task_id mismatch"]
    if bundle.obligation_set_hash != context.obligation_set_hash:
        return Verdict.ISSUE, ["CandidateAttackBundle obligation_set_hash mismatch"]
    explicit_scope = candidate.metadata.get("scope_hash")
    if isinstance(explicit_scope, str) and explicit_scope != bundle.scope_hash:
        return Verdict.ISSUE, ["CandidateAttackBundle scope_hash mismatch"]
    if not bundle.nearest_prior_art_receipt_ids:
        return Verdict.UNKNOWN, ["stored cleared Space source-assessment evidence is required"]
    prior = _space_prior_art_state(
        store,
        candidate,
        bundle.nearest_prior_art_receipt_ids,
        context,
    )
    if prior.issues:
        return Verdict.ISSUE, list(prior.issues)
    if prior.unavailable:
        return Verdict.UNAVAILABLE, list(prior.unavailable)
    if prior.unresolved or not prior.receipt_ids or prior.scope_hash is None:
        return Verdict.UNKNOWN, list(prior.unresolved) or ["prior-art state unresolved"]
    if prior.scope_hash != bundle.scope_hash:
        return Verdict.ISSUE, ["bundle scope does not match current Space assessed scope"]
    if not meaningful_changed_assumption(candidate):
        return Verdict.ISSUE, ["candidate has no meaningful changed assumption"]

    challenges = _challenge_by_kind(store, bundle)
    required = (
        ChallengeKind.NOVELTY_COSTUME.value,
        ChallengeKind.ASSUMPTION_KNOCKOUT.value,
        ChallengeKind.COMPETING_MECHANISM.value,
        ChallengeKind.MINIMUM_DISCRIMINATOR.value,
    )
    missing = [kind for kind in required if kind not in challenges]
    if missing:
        return Verdict.UNKNOWN, [f"missing native Reality challenges: {', '.join(missing)}"]
    binding_errors: list[str] = []
    for challenge in challenges.values():
        binding_errors.extend(_challenge_binding_errors(bundle, challenge))
    if binding_errors:
        return Verdict.ISSUE, binding_errors
    if _self_certification_present(store, challenges):
        return Verdict.ISSUE, ["Reality self-certification cannot satisfy native challenge evidence"]

    costume = challenges[ChallengeKind.NOVELTY_COSTUME.value]
    if costume.get("obligation_id") != prior.discovery_obligation_id:
        return Verdict.ISSUE, ["NOVELTY_COSTUME prior-art obligation binding mismatch"]
    costume_state = str(costume.get("state") or "")
    if costume_state == ChallengeState.UNAVAILABLE.value:
        return Verdict.UNAVAILABLE, ["NOVELTY_COSTUME evidence capability unavailable"]
    if costume_state != ChallengeState.RESOLVED.value:
        return Verdict.UNKNOWN, ["NOVELTY_COSTUME remains unresolved"]
    costume_resolution = store.latest_resolution(str(costume.get("challenge_id")))
    if costume_resolution is None:
        return Verdict.UNKNOWN, ["NOVELTY_COSTUME lacks an integrity-valid resolution"]
    if costume_resolution.get("outcome") == ResolutionOutcome.REFUTES_BASE.value:
        return Verdict.ISSUE, ["NOVELTY_COSTUME refutes candidate admission"]
    if costume_resolution.get("verifier_module") != "space":
        return Verdict.ISSUE, ["NOVELTY_COSTUME must be resolved by Space evidence"]
    if costume_resolution.get("verifier_receipt_id") not in prior.receipt_ids:
        return Verdict.ISSUE, ["NOVELTY_COSTUME resolved by unrelated Space receipt"]

    assumption = challenges[ChallengeKind.ASSUMPTION_KNOCKOUT.value]
    assumption_state = str(assumption.get("state") or "")
    if assumption_state == ChallengeState.UNAVAILABLE.value:
        return Verdict.UNAVAILABLE, ["ASSUMPTION_KNOCKOUT unavailable"]
    if assumption_state == ChallengeState.UNRESOLVED.value:
        return Verdict.UNKNOWN, ["ASSUMPTION_KNOCKOUT remains unresolved"]
    if assumption_state == ChallengeState.RESOLVED.value:
        resolution = store.latest_resolution(str(assumption.get("challenge_id")))
        if resolution and resolution.get("outcome") == ResolutionOutcome.REFUTES_BASE.value:
            return Verdict.ISSUE, ["ASSUMPTION_KNOCKOUT refutes candidate mechanism claim"]
    elif assumption_state != ChallengeState.SELECTED.value or not assumption.get(
        "selected_plan_id"
    ):
        return Verdict.UNKNOWN, ["ASSUMPTION_KNOCKOUT lacks a bound discriminator"]

    competing = challenges[ChallengeKind.COMPETING_MECHANISM.value]
    competing_state = str(competing.get("state") or "")
    competing_required = bool(
        (competing.get("metadata") or {}).get("bundle_gate_required")
        if isinstance(competing.get("metadata"), Mapping)
        else False
    )
    if competing_required:
        if competing_state == ChallengeState.UNAVAILABLE.value:
            return Verdict.UNAVAILABLE, ["required competing mechanism discriminator unavailable"]
        if competing_state == ChallengeState.UNRESOLVED.value:
            return Verdict.UNKNOWN, ["required competing mechanism remains unresolved"]
        competing_metadata = (
            competing.get("metadata") if isinstance(competing.get("metadata"), Mapping) else {}
        )
        if not competing_metadata.get("mechanism_b"):
            return Verdict.UNKNOWN, ["required competing mechanism is not bound"]
    elif competing_state not in {
        ChallengeState.DISMISSED_NOT_APPLICABLE.value,
        ChallengeState.PROPOSED.value,
        ChallengeState.SELECTED.value,
        ChallengeState.RESOLVED.value,
    }:
        return Verdict.UNKNOWN, ["competing-mechanism applicability remains unresolved"]

    minimum = challenges[ChallengeKind.MINIMUM_DISCRIMINATOR.value]
    minimum_state = str(minimum.get("state") or "")
    if minimum_state == ChallengeState.UNAVAILABLE.value:
        return Verdict.UNAVAILABLE, ["minimum discriminator capability unavailable"]
    if minimum_state == ChallengeState.UNRESOLVED.value:
        return Verdict.UNKNOWN, ["minimum discriminator selection is incomparable"]
    if minimum_state != ChallengeState.SELECTED.value or not minimum.get("selected_plan_id"):
        return Verdict.UNKNOWN, ["minimum useful discriminator has not been selected"]

    return Verdict.CLEARED, []


def _admission_evidence(
    bundle: CandidateAttackBundle,
    verdict: Verdict,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_class=EvidenceClass.DERIVED,
        verifier="reality_runtime:v2",
        provenance_group="reality-synthesis-admission",
        metadata={
            "schema": REALITY_SCHEMA,
            "bundle_id": bundle.bundle_id,
            "bundle_content_hash": bundle.content_hash,
            "authority": "SYNTHESIS_ONLY",
            "admission_only": True,
            "testable_candidate": verdict is Verdict.CLEARED,
            "novelty_established": False,
            "efficacy_established": False,
            "engineering_verified": False,
            "evaluation_cleared": False,
            "execution_authorized": False,
            "host_write_authorized": False,
            "global_cost_optimality_established": False,
        },
    )


def record_candidate(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> Receipt:
    """Persist candidate + attack bundle and emit a bounded SYNTHESIS admission receipt."""
    if not isinstance(candidate, MethodCandidate):
        raise TypeError("candidate must be MethodCandidate")
    store = RuntimeStore(root)
    c_hash = candidate_hash(candidate)
    candidate_state = asdict(candidate)
    candidate_state["candidate_hash"] = c_hash
    candidate_state["mechanism_signature"] = mechanism_signature(candidate)
    candidate_state["content_hash"] = digest(candidate_state)
    store.write_named_state("reality", candidate.candidate_id, candidate_state)

    basic = _basic_candidate_errors(candidate)
    if basic:
        bundle = load_attack_bundle(root, candidate.candidate_id)
        if bundle is None:
            context = _task_context(store, candidate)
            scope_hash = digest(
                {"candidate_hash": c_hash, "obligation_id": candidate.obligation_id}
            )
            bundle = _make_bundle(
                bundle_id=new_id("rab"),
                task_id=context.task_id if context else None,
                obligation_id=candidate.obligation_id,
                candidate_id=candidate.candidate_id,
                candidate_hash_value=c_hash,
                scope_hash=scope_hash,
                obligation_set_hash=(
                    context.obligation_set_hash
                    if context
                    else digest({"unbound_obligation": candidate.obligation_id})
                ),
                challenge_ids=(),
                selected_discriminator_ids=(),
                nearest_prior_art_receipt_ids=(),
                status=Verdict.UNKNOWN,
                unresolved=tuple(basic),
                metadata={
                    "authority": "SYNTHESIS_ONLY",
                    "global_novelty_established": False,
                    "behavioral_efficacy_established": False,
                },
            )
            store.write_named_state(
                "reality_attack_bundles",
                candidate.candidate_id,
                _bundle_to_state(bundle),
            )
        verdict, reasons = Verdict.UNKNOWN, basic
    else:
        bundle = create_attack_bundle(root, candidate, prior_art_receipt_ids)
        verdict, reasons = evaluate_admission(root, candidate, bundle)

    evidence = _admission_evidence(bundle, verdict)
    notes = {
        "schema": REALITY_SCHEMA,
        "authority": "SYNTHESIS_ONLY",
        "admission_only": True,
        "testable_candidate": verdict is Verdict.CLEARED,
        "novelty_established": False,
        "efficacy_established": False,
        "engineering_verified": False,
        "evaluation_cleared": False,
        "execution_authorized": False,
        "host_write_authorized": False,
        "candidate_admission_boundary": (
            "CLEARED means sufficiently specified/testable for SYNTHESIS scope only; "
            "it is not proof of novelty, truth, engineering correctness, efficacy, "
            "benchmark superiority, evaluation clearance, execution authority, or write authority"
        ),
        "prior_art_boundary": (
            "no matching prior mechanism may be stated only within registered assessed "
            "Space scope; global nonexistence is not established"
        ),
        "bundle_id": bundle.bundle_id,
        "bundle_content_hash": bundle.content_hash,
        "selected_discriminator_ids": list(bundle.selected_discriminator_ids),
        "unresolved": reasons,
    }
    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        module="reality",
        obligation_id=candidate.obligation_id,
        verdict=verdict,
        action="candidate-admission",
        input_hash=c_hash,
        output_hash=bundle.content_hash,
        evidence=(evidence,),
        verifier="reality_runtime:v2",
        tool_version=REALITY_SCHEMA,
        started_at=utcnow(),
        finished_at=utcnow(),
        unresolved=tuple(reasons),
        notes=json.dumps(notes, sort_keys=True),
        task_id=bundle.task_id,
    )
    store.write_receipt(receipt)
    return receipt


def run_automatic_synthesis(
    root: Path,
    candidate: MethodCandidate,
    prior_art_receipt_ids: Sequence[str],
) -> Receipt:
    """Soul-routed compatibility alias for automatic Reality synthesis admission."""
    return record_candidate(root, candidate, prior_art_receipt_ids)


__all__ = [
    "CandidateAttackBundle",
    "MethodCandidate",
    "REALITY_SCHEMA",
    "admission",
    "candidate_hash",
    "create_attack_bundle",
    "diversity_matrix",
    "evaluate_admission",
    "load_attack_bundle",
    "meaningful_changed_assumption",
    "mechanism_signature",
    "record_candidate",
    "run_automatic_synthesis",
]
