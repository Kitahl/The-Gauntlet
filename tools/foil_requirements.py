"""Task requirements -> user-evidence coverage -> minimum FOIL complement.

This is the post-0.5.1 P0 bridge.  It keeps three concepts separate:

* a task requirement says what the task needs;
* :mod:`foil_evidence` says what the observations support about the user;
* :mod:`foil_policy` decides whether one minimum complement may be routed.

Absence of evidence is represented as ``UNKNOWN`` and is never promoted to a
gap.  Fresh, task-matched evidence has explicit precedence over historical
profile evidence.  Public receipts contain classifications and hashes/counts,
never raw observations or profile text.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

import foil_evidence
import foil_profile
from foil_policy import (
    ComplementKind,
    EvidenceDirection,
    PolicyDecision,
    ProfileSignal,
    RuntimePolicyV2,
    TaskContext,
)
from foil_signal_boundary import SignalAuthority

SCHEMA = "egrt.foil-requirement-routing.v1"
CANDIDATE_VERSION = "FOIL_POST_0_5_1_P0_CANDIDATE_V1"

__all__ = [
    "SCHEMA",
    "CANDIDATE_VERSION",
    "CAPABILITY_COMPLEMENTS",
    "RequirementImportance",
    "RequiredLevel",
    "CoverageState",
    "EvidenceSource",
    "TaskCapabilityRequirement",
    "CapabilityEvidence",
    "RequirementCoverage",
    "RequirementRoutingDecision",
    "normalize_capability",
    "complement_for_capability",
    "merge_requirements",
    "profile_evidence_from_snapshot",
    "resolve_requirement",
    "resolve_requirements",
    "route_requirements",
]


class RequirementImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def priority(self) -> int:
        return {
            RequirementImportance.CRITICAL: 0,
            RequirementImportance.HIGH: 1,
            RequirementImportance.MEDIUM: 2,
            RequirementImportance.LOW: 3,
        }[self]


class RequiredLevel(str, Enum):
    MINIMAL = "MINIMAL"
    WORKING = "WORKING"
    STRONG = "STRONG"


class CoverageState(str, Enum):
    COVERED_STRONG = "COVERED_STRONG"
    COVERED_WORKING = "COVERED_WORKING"
    UNCERTAIN = "UNCERTAIN"
    PROBABLE_GAP = "PROBABLE_GAP"
    UNKNOWN = "UNKNOWN"


class EvidenceSource(str, Enum):
    CURRENT_TASK = "CURRENT_TASK"
    PROFILE = "PROFILE"
    NONE = "NONE"


def normalize_capability(value: str) -> str:
    """Normalize an explicit capability identifier, not free task text."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    if not normalized:
        raise ValueError("capability must contain at least one letter or digit")
    return normalized


# This is an explicit, reviewable bridge between user-capability labels and the
# existing complement vocabulary.  Unknown capability labels remain valid task
# requirements, but are not silently guessed into a complement.
CAPABILITY_COMPLEMENTS: dict[str, ComplementKind] = {kind.value: kind for kind in ComplementKind}
CAPABILITY_COMPLEMENTS.update(
    {
        "formal_reasoning": ComplementKind.FORMALIZATION,
        "causal_inference": ComplementKind.CAUSAL_REASONING,
        "causal_reasoning": ComplementKind.CAUSAL_REASONING,
        "quantitative_reasoning": ComplementKind.QUANTITATIVE_CHECK,
        "quantitative_checking": ComplementKind.QUANTITATIVE_CHECK,
        "research_evidence": ComplementKind.EVIDENCE_DISCIPLINE,
        "source_checking": ComplementKind.EVIDENCE_DISCIPLINE,
        "verification_discipline": ComplementKind.EVIDENCE_DISCIPLINE,
        "prior_art_search": ComplementKind.TOOL_SELECTION,
        "retrieval": ComplementKind.TOOL_SELECTION,
        "software_engineering": ComplementKind.IMPLEMENTATION_EXECUTION,
        "planning_decision_making": ComplementKind.PLANNING_PRIORITIZATION,
    }
)


def complement_for_capability(capability: str) -> ComplementKind | None:
    return CAPABILITY_COMPLEMENTS.get(normalize_capability(capability))


def _text_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TaskCapabilityRequirement:
    requirement_id: str
    capability: str
    importance: RequirementImportance = RequirementImportance.MEDIUM
    required_level: RequiredLevel = RequiredLevel.WORKING
    evidence_obligation: str | None = None
    representation: str | None = None
    context: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.requirement_id, str):
            raise ValueError("requirement_id must be a string")
        if not isinstance(self.capability, str):
            raise ValueError("capability must be a string")
        requirement_id = self.requirement_id.strip()
        if not requirement_id:
            raise ValueError("requirement_id is required")
        object.__setattr__(self, "requirement_id", requirement_id)
        object.__setattr__(self, "capability", normalize_capability(self.capability))
        object.__setattr__(self, "importance", RequirementImportance(self.importance))
        object.__setattr__(self, "required_level", RequiredLevel(self.required_level))
        if self.evidence_obligation is not None:
            obligation = str(self.evidence_obligation).strip()
            object.__setattr__(self, "evidence_obligation", obligation or None)
        for field in ("representation", "context"):
            value = getattr(self, field)
            if value is not None:
                normalized = str(value).strip()
                object.__setattr__(self, field, normalized or None)


@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence already classified by the shared estimator at routing time.

    ``transfer_confirmations`` is explicit because representation diversity is
    not equivalent to verified transfer. Snapshot adaptation reads only an
    explicit persisted confirmation count and otherwise supplies zero.
    """

    observations: tuple[foil_evidence.Observation, ...] = ()
    transfer_confirmations: int = 0
    context: str | None = None
    stale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        if (
            isinstance(self.transfer_confirmations, bool)
            or not isinstance(self.transfer_confirmations, int)
            or self.transfer_confirmations < 0
        ):
            raise ValueError("transfer_confirmations must be a non-negative integer")
        if any(not isinstance(row, foil_evidence.Observation) for row in self.observations):
            raise TypeError("observations must contain foil_evidence.Observation values")


@dataclass(frozen=True)
class RequirementCoverage:
    requirement: TaskCapabilityRequirement
    state: CoverageState
    evidence_source: EvidenceSource
    meets_required_level: bool
    complement: ComplementKind | None
    classification: foil_evidence.Classification | None
    profile_classification: foil_evidence.Classification | None
    current_task_classification: foil_evidence.Classification | None
    independent_observations: int
    transfer_confirmations: int
    reason: str

    def trace(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement.requirement_id,
            "capability": self.requirement.capability,
            "importance": self.requirement.importance.value,
            "required_level": self.requirement.required_level.value,
            "evidence_obligation_sha256": _text_sha256(self.requirement.evidence_obligation),
            "representation": self.requirement.representation,
            "context_sha256": _text_sha256(self.requirement.context),
            "coverage": self.state.value,
            "evidence_source": self.evidence_source.value,
            "meets_required_level": self.meets_required_level,
            "complement": self.complement.value if self.complement else None,
            "classification": self.classification.value if self.classification else None,
            "profile_classification": (
                self.profile_classification.value if self.profile_classification else None
            ),
            "current_task_classification": (
                self.current_task_classification.value if self.current_task_classification else None
            ),
            "independent_observations": self.independent_observations,
            "transfer_confirmations": self.transfer_confirmations,
            "reason": self.reason,
            "routing_signal_authority": SignalAuthority.CONTROL_ONLY.value,
        }


@dataclass(frozen=True)
class RequirementRoutingDecision:
    coverages: tuple[RequirementCoverage, ...]
    policy_decision: PolicyDecision
    selected_requirement_id: str | None

    @property
    def selected_complement(self) -> ComplementKind | None:
        return self.policy_decision.targeted_complement

    def trace(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": SCHEMA,
            "controller_version": CANDIDATE_VERSION,
            "requirements": [coverage.trace() for coverage in self.coverages],
            "selected_requirement_id": self.selected_requirement_id,
            "selected_complement": (
                self.selected_complement.value if self.selected_complement else None
            ),
            "route_basis": self.policy_decision.route_basis,
            "routing_signal_authority": SignalAuthority.CONTROL_ONLY.value,
            "policy": self.policy_decision.trace(),
            "raw_observations_stored": False,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["decision_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload


def _coerce_bundle(
    value: CapabilityEvidence | Sequence[foil_evidence.Observation] | None,
) -> CapabilityEvidence:
    if value is None:
        return CapabilityEvidence()
    if isinstance(value, CapabilityEvidence):
        return value
    return CapabilityEvidence(tuple(value))


def _bundle_for(
    evidence: Mapping[str, CapabilityEvidence | Sequence[foil_evidence.Observation]] | None,
    capability: str,
) -> CapabilityEvidence:
    if not evidence:
        return CapabilityEvidence()
    normalized = normalize_capability(capability)
    for key, value in evidence.items():
        if normalize_capability(key) == normalized:
            return _coerce_bundle(value)
    return CapabilityEvidence()


def _compatible_observations(
    requirement: TaskCapabilityRequirement,
    evidence: CapabilityEvidence,
) -> tuple[foil_evidence.Observation, ...]:
    if requirement.context:
        if not evidence.context:
            return ()
        if requirement.context.strip().casefold() != evidence.context.strip().casefold():
            return ()
    rows: list[foil_evidence.Observation] = []
    for row in evidence.observations:
        if row.capability and normalize_capability(row.capability) != requirement.capability:
            continue
        if requirement.representation:
            if not row.representation:
                continue
            if (
                requirement.representation.strip().casefold()
                != row.representation.strip().casefold()
            ):
                continue
        rows.append(row)
    return tuple(rows)


def _state_for_classification(
    classification: foil_evidence.Classification,
) -> CoverageState:
    return {
        foil_evidence.Classification.PROMISING_STRENGTH: CoverageState.COVERED_STRONG,
        foil_evidence.Classification.POSSIBLE_GAP: CoverageState.PROBABLE_GAP,
        foil_evidence.Classification.UNCERTAIN: CoverageState.UNCERTAIN,
        foil_evidence.Classification.INSUFFICIENT_EVIDENCE: CoverageState.UNKNOWN,
    }[classification]


def _meets_level(state: CoverageState, level: RequiredLevel) -> bool:
    if state is CoverageState.COVERED_STRONG:
        return True
    return state is CoverageState.COVERED_WORKING and level is not RequiredLevel.STRONG


def _real_work_count(rows: Sequence[foil_evidence.Observation]) -> int:
    return sum(row.tier is foil_evidence.EvidenceTier.REAL_WORK for row in rows)


def resolve_requirement(
    requirement: TaskCapabilityRequirement,
    *,
    profile_evidence: CapabilityEvidence | Sequence[foil_evidence.Observation] | None = None,
    current_task_evidence: CapabilityEvidence | Sequence[foil_evidence.Observation] | None = None,
    evidence_policy: foil_evidence.EvidencePolicy | None = None,
    now: datetime | None = None,
) -> RequirementCoverage:
    """Resolve one requirement with current-task evidence taking precedence."""
    policy = evidence_policy or foil_evidence.EvidencePolicy()
    profile_bundle = _coerce_bundle(profile_evidence)
    current_bundle = _coerce_bundle(current_task_evidence)
    profile_rows = _compatible_observations(requirement, profile_bundle)
    current_rows = _compatible_observations(requirement, current_bundle)
    profile_summary = foil_evidence.summarize(profile_rows, policy, now=now)
    current_summary = foil_evidence.summarize(current_rows, policy, now=now)

    chosen_state: CoverageState | None = None
    chosen_source = EvidenceSource.NONE
    chosen_summary: foil_evidence.PosteriorSummary | None = None
    chosen_rows: tuple[foil_evidence.Observation, ...] = ()
    chosen_bundle = CapabilityEvidence()
    reason = "no compatible load-bearing evidence"

    # Decisive or sufficiently ambiguous evidence on this task is the closest
    # evidence to the requirement and therefore outranks profile history.
    if current_rows and not current_summary.stale_only:
        if current_summary.classification is not foil_evidence.Classification.INSUFFICIENT_EVIDENCE:
            chosen_state = _state_for_classification(current_summary.classification)
            reason = "current-task classification controls"
        else:
            admissible = [
                row
                for row in current_rows
                if row.tier is foil_evidence.EvidenceTier.REAL_WORK
                and policy.weight_for(row.tier) > 0.0
            ]
            if any(row.correct for row in admissible):
                chosen_state = CoverageState.COVERED_WORKING
                reason = "fresh verified task-local success supports working coverage only"
            elif admissible:
                chosen_state = CoverageState.UNCERTAIN
                reason = "task-local misses are insufficient to manufacture a gap"
        if chosen_state is not None:
            chosen_source = EvidenceSource.CURRENT_TASK
            chosen_summary = current_summary
            chosen_rows = current_rows
            chosen_bundle = current_bundle

    if (
        chosen_state is None
        and profile_rows
        and not profile_bundle.stale
        and not profile_summary.stale_only
    ):
        chosen_state = _state_for_classification(profile_summary.classification)
        chosen_source = EvidenceSource.PROFILE
        chosen_summary = profile_summary
        chosen_rows = profile_rows
        chosen_bundle = profile_bundle
        reason = "compatible profile classification controls"

    if chosen_state is None:
        chosen_state = CoverageState.UNKNOWN
        if profile_bundle.stale or profile_summary.stale_only:
            reason = "profile evidence is stale; UNKNOWN is not a gap"
        chosen_summary = None

    return RequirementCoverage(
        requirement=requirement,
        state=chosen_state,
        evidence_source=chosen_source,
        meets_required_level=_meets_level(chosen_state, requirement.required_level),
        complement=complement_for_capability(requirement.capability),
        classification=chosen_summary.classification if chosen_summary else None,
        profile_classification=profile_summary.classification if profile_rows else None,
        current_task_classification=current_summary.classification if current_rows else None,
        independent_observations=_real_work_count(chosen_rows),
        transfer_confirmations=chosen_bundle.transfer_confirmations,
        reason=reason,
    )


def _merge_optional(field: str, left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None or right == left:
        return left
    raise ValueError(
        f"duplicate capability requirements disagree on {field}: {left!r} != {right!r}"
    )


def merge_requirements(
    requirements: Sequence[TaskCapabilityRequirement],
) -> tuple[TaskCapabilityRequirement, ...]:
    """Merge duplicate capabilities without inventing task semantics.

    The strongest importance and required level win. Optional qualifiers may be
    filled from either duplicate, but contradictory representation, context, or
    evidence obligations fail closed. Requirement ids remain globally unique;
    the lexicographically smallest id identifies a merged capability so the
    receipt is independent of input order.
    """
    rows = tuple(requirements)
    identifiers = [row.requirement_id for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("requirement_id values must be unique")
    by_capability: dict[str, TaskCapabilityRequirement] = {}
    order: list[str] = []
    level_rank = {
        RequiredLevel.MINIMAL: 0,
        RequiredLevel.WORKING: 1,
        RequiredLevel.STRONG: 2,
    }
    for row in rows:
        existing = by_capability.get(row.capability)
        if existing is None:
            by_capability[row.capability] = row
            order.append(row.capability)
            continue
        importance = min((existing.importance, row.importance), key=lambda item: item.priority)
        required_level = max(
            (existing.required_level, row.required_level),
            key=lambda item: level_rank[item],
        )
        by_capability[row.capability] = TaskCapabilityRequirement(
            requirement_id=min(existing.requirement_id, row.requirement_id),
            capability=row.capability,
            importance=importance,
            required_level=required_level,
            evidence_obligation=_merge_optional(
                "evidence_obligation", existing.evidence_obligation, row.evidence_obligation
            ),
            representation=_merge_optional(
                "representation", existing.representation, row.representation
            ),
            context=_merge_optional("context", existing.context, row.context),
        )
    return tuple(by_capability[capability] for capability in order)


def resolve_requirements(
    requirements: Sequence[TaskCapabilityRequirement],
    *,
    profile_evidence: Mapping[str, CapabilityEvidence | Sequence[foil_evidence.Observation]]
    | None = None,
    current_task_evidence: Mapping[str, CapabilityEvidence | Sequence[foil_evidence.Observation]]
    | None = None,
    evidence_policy: foil_evidence.EvidencePolicy | None = None,
    now: datetime | None = None,
) -> tuple[RequirementCoverage, ...]:
    requirements = merge_requirements(requirements)
    return tuple(
        resolve_requirement(
            requirement,
            profile_evidence=_bundle_for(profile_evidence, requirement.capability),
            current_task_evidence=_bundle_for(current_task_evidence, requirement.capability),
            evidence_policy=evidence_policy,
            now=now,
        )
        for requirement in requirements
    )


def profile_evidence_from_snapshot(
    profile: Mapping[str, Any],
    requirements: Sequence[TaskCapabilityRequirement],
) -> dict[str, CapabilityEvidence]:
    """Adapt an exact or unambiguous explicit-alias FOIL profile row."""
    domains = profile.get("domains") or {}
    stale = str(profile.get("profile_status") or "").upper() == "STALE"
    out: dict[str, CapabilityEvidence] = {}
    for requirement in requirements:
        row = domains.get(requirement.capability)
        if not isinstance(row, dict):
            complement = complement_for_capability(requirement.capability)
            aliases = [
                candidate
                for domain, candidate in domains.items()
                if isinstance(candidate, dict)
                and complement is not None
                and complement_for_capability(domain) is complement
            ]
            # An explicit one-to-one complement alias is safe. Multiple rows
            # are ambiguous and must not be silently aggregated.
            if len(aliases) == 1:
                row = aliases[0]
        if not isinstance(row, dict):
            continue
        observations = tuple(foil_profile.observations_for(row))
        transfer_confirmations = row.get("transfer_confirmations", 0)
        if (
            isinstance(transfer_confirmations, bool)
            or not isinstance(transfer_confirmations, int)
            or transfer_confirmations < 0
        ):
            raise ValueError("profile transfer_confirmations must be a non-negative integer")
        out[requirement.capability] = CapabilityEvidence(
            observations=observations,
            transfer_confirmations=transfer_confirmations,
            stale=stale,
        )
    return out


def _profile_relevance(importance: RequirementImportance) -> float:
    return {
        RequirementImportance.CRITICAL: 1.0,
        RequirementImportance.HIGH: 1.0,
        RequirementImportance.MEDIUM: 0.80,
        RequirementImportance.LOW: 0.60,
    }[importance]


def route_requirements(
    task: TaskContext,
    requirements: Sequence[TaskCapabilityRequirement],
    *,
    profile: Mapping[str, Any] | None = None,
    profile_evidence: Mapping[str, CapabilityEvidence | Sequence[foil_evidence.Observation]]
    | None = None,
    current_task_evidence: Mapping[str, CapabilityEvidence | Sequence[foil_evidence.Observation]]
    | None = None,
    evidence_policy: foil_evidence.EvidencePolicy | None = None,
    now: datetime | None = None,
    policy: RuntimePolicyV2 | None = None,
) -> RequirementRoutingDecision:
    """Route at most one auditable, minimum task-relevant complement."""
    if profile is not None and profile_evidence is not None:
        raise ValueError("pass profile or profile_evidence, not both")
    requirements = merge_requirements(requirements)
    if profile is not None:
        profile_evidence = profile_evidence_from_snapshot(profile, requirements)
    coverages = resolve_requirements(
        requirements,
        profile_evidence=profile_evidence,
        current_task_evidence=current_task_evidence,
        evidence_policy=evidence_policy,
        now=now,
    )
    required = {coverage.complement for coverage in coverages if coverage.complement is not None}
    enriched_task = replace(
        task,
        required_complements=frozenset(set(task.required_complements) | required),
    )
    candidates = sorted(
        (
            coverage
            for coverage in coverages
            if coverage.state is CoverageState.PROBABLE_GAP and coverage.complement is not None
        ),
        key=lambda coverage: (
            coverage.requirement.importance.priority,
            coverage.requirement.requirement_id,
        ),
    )
    controller = policy or RuntimePolicyV2()
    decision = controller.decide(enriched_task)
    selected = None
    for candidate in candidates:
        if candidate.evidence_source is EvidenceSource.CURRENT_TASK:
            candidate_decision = controller.decide(
                enriched_task, current_task_gap=candidate.complement
            )
        else:
            evidence = _bundle_for(profile_evidence, candidate.requirement.capability)
            profile_summary = foil_evidence.summarize(
                _compatible_observations(candidate.requirement, evidence),
                evidence_policy,
                now=now,
            )
            signal = ProfileSignal(
                relevance=_profile_relevance(candidate.requirement.importance),
                support=profile_summary.p_below_lo,
                independent_observations=candidate.independent_observations,
                transfer_confirmations=candidate.transfer_confirmations,
                stale=False,
                direction=EvidenceDirection.GAP,
                complement=candidate.complement,
            )
            candidate_decision = controller.decide(enriched_task, signal)
        if candidate_decision.targeted_complement is not None:
            decision = candidate_decision
            selected = candidate.requirement.requirement_id
            break
    return RequirementRoutingDecision(coverages, decision, selected)
