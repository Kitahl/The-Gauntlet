"""Experimental FOIL vNext V2 evidence-gated runtime policy.

This candidate leaves permanent FOIL v0.4.0 untouched. It converts current-task
signals plus independently supported profile evidence into a small deterministic
policy. A profile can trigger help only when it describes a verified gap that
matches a capability the current task actually requires. Public traces contain
policy state only and never hidden reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class TaskRegime(str, Enum):
    EXTERNAL_RETRIEVAL = "external_retrieval"
    FRESHNESS_SENSITIVE_RETRIEVAL = "freshness_sensitive_retrieval"
    CLOSED_BOOK_TECHNICAL_REASONING = "closed_book_technical_reasoning"
    ABSTRACT_TRANSFORMATION = "abstract_transformation"
    CLOSED_CONTEXT_MULTI_HOP = "closed_context_multi_hop"
    MIXED_TOOL_TASK = "mixed_tool_task"


class EffortMode(str, Enum):
    DISCOVERY = "discovery"
    REASONING = "reasoning"
    VERIFICATION = "verification"
    MIXED = "mixed"


class ProfileInfluence(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class EvidenceDirection(str, Enum):
    UNCERTAIN = "uncertain"
    STRENGTH = "strength"
    GAP = "gap"


class ComplementKind(str, Enum):
    FORMALIZATION = "formalization"
    DECOMPOSITION = "decomposition"
    ERROR_DETECTION = "error_detection"
    EVIDENCE_DISCIPLINE = "evidence_discipline"
    CAUSAL_REASONING = "causal_reasoning"
    QUANTITATIVE_CHECK = "quantitative_check"
    IMPLEMENTATION_EXECUTION = "implementation_execution"
    PLANNING_PRIORITIZATION = "planning_prioritization"
    CALIBRATION = "calibration"
    TRANSFER_ADAPTATION = "transfer_adaptation"
    TOOL_SELECTION = "tool_selection"
    UNCERTAINTY_MANAGEMENT = "uncertainty_management"


class ClaimKind(str, Enum):
    EXTERNAL_FACT = "external_fact"
    FRESH_FACT = "fresh_fact"
    NUMERIC = "numeric"
    SUPPLIED_EXAMPLES = "supplied_examples"
    EXECUTABLE = "executable"
    LOGICAL = "logical"
    OUTPUT_CONTRACT = "output_contract"


class VerifierKind(str, Enum):
    SOURCE_EVIDENCE = "source_evidence"
    CURRENT_SOURCE = "current_source"
    EXACT_CALCULATION = "exact_calculation"
    SUPPLIED_EXAMPLE_CONSISTENCY = "supplied_example_consistency"
    EXECUTION_TEST = "execution_test"
    CONTRADICTION_COUNTEREXAMPLE = "contradiction_counterexample"
    OUTPUT_CONTRACT = "output_contract"


class PolicyAction(str, Enum):
    DISCOVER_CANDIDATES = "discover_candidates"
    VERIFY_CANDIDATE = "verify_candidate"
    PREFER_CURRENT_SOURCE = "prefer_current_source"
    REASON_CLOSED_BOOK = "reason_closed_book"
    INDUCE_RULE = "induce_rule"
    CHECK_RULE_AGAINST_ALL_EXAMPLES = "check_rule_against_all_examples"
    DECOMPOSE_SUPPLIED_EVIDENCE = "decompose_supplied_evidence"
    MIX_TOOLS_AND_REASONING = "mix_tools_and_reasoning"
    APPLY_TARGETED_COMPLEMENT = "apply_targeted_complement"
    CHECK_OUTPUT_CONTRACT = "check_output_contract"
    STOP = "stop"


CLAIM_VERIFIER: Mapping[ClaimKind, VerifierKind] = {
    ClaimKind.EXTERNAL_FACT: VerifierKind.SOURCE_EVIDENCE,
    ClaimKind.FRESH_FACT: VerifierKind.CURRENT_SOURCE,
    ClaimKind.NUMERIC: VerifierKind.EXACT_CALCULATION,
    ClaimKind.SUPPLIED_EXAMPLES: VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY,
    ClaimKind.EXECUTABLE: VerifierKind.EXECUTION_TEST,
    ClaimKind.LOGICAL: VerifierKind.CONTRADICTION_COUNTEREXAMPLE,
    ClaimKind.OUTPUT_CONTRACT: VerifierKind.OUTPUT_CONTRACT,
}


CLAIM_COMPLEMENTS: Mapping[ClaimKind, frozenset[ComplementKind]] = {
    ClaimKind.EXTERNAL_FACT: frozenset(
        {ComplementKind.EVIDENCE_DISCIPLINE, ComplementKind.TOOL_SELECTION}
    ),
    ClaimKind.FRESH_FACT: frozenset(
        {ComplementKind.EVIDENCE_DISCIPLINE, ComplementKind.TOOL_SELECTION}
    ),
    ClaimKind.NUMERIC: frozenset({ComplementKind.QUANTITATIVE_CHECK}),
    ClaimKind.SUPPLIED_EXAMPLES: frozenset(
        {ComplementKind.TRANSFER_ADAPTATION, ComplementKind.ERROR_DETECTION}
    ),
    ClaimKind.EXECUTABLE: frozenset({ComplementKind.IMPLEMENTATION_EXECUTION}),
    ClaimKind.LOGICAL: frozenset(
        {ComplementKind.FORMALIZATION, ComplementKind.ERROR_DETECTION}
    ),
    ClaimKind.OUTPUT_CONTRACT: frozenset({ComplementKind.ERROR_DETECTION}),
}


@dataclass(frozen=True)
class LoadBearingUncertainty:
    """An unresolved fact/check that could change the final answer."""

    label: str
    claim_kind: ClaimKind = ClaimKind.LOGICAL
    decisive: bool = True
    resolved: bool = False


@dataclass(frozen=True)
class ProfileSignal:
    """Evidence about one possible task-relevant strength or gap.

    `support` is confidence in the evidence classification, not competence.
    A profile can affect routing only for a supported GAP, never merely because
    the profile is detailed or topically relevant.
    """

    relevance: float = 0.0
    support: float = 0.0
    independent_observations: int = 0
    transfer_confirmations: int = 0
    stale: bool = False
    direction: EvidenceDirection = EvidenceDirection.UNCERTAIN
    complement: ComplementKind | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.relevance <= 1.0:
            raise ValueError("relevance must be in [0, 1]")
        if not 0.0 <= self.support <= 1.0:
            raise ValueError("support must be in [0, 1]")
        if self.independent_observations < 0 or self.transfer_confirmations < 0:
            raise ValueError("profile evidence counts must be non-negative")
        if self.direction is EvidenceDirection.GAP and self.complement is None:
            raise ValueError("gap evidence requires a concrete complement")


@dataclass(frozen=True)
class TaskContext:
    # `benchmark` is receipt metadata only. Runtime behavior is derived from
    # task properties so benchmark names cannot silently select a policy.
    benchmark: str | None = None
    requires_external_retrieval: bool = False
    freshness_sensitive: bool = False
    closed_book: bool = False
    technical_reasoning: bool = False
    abstract_transformation: bool = False
    closed_context: bool = False
    multi_hop: bool = False
    mixed_tool_task: bool = False
    has_viable_candidate: bool = False
    answer_confidence: float = 0.0
    supplied_example_count: int = 0
    output_contract_required: bool = False
    uncertainties: tuple[LoadBearingUncertainty, ...] = ()
    completed_verifiers: frozenset[VerifierKind] = frozenset()
    required_complements: frozenset[ComplementKind] = frozenset()

    def __post_init__(self) -> None:
        if not 0.0 <= self.answer_confidence <= 1.0:
            raise ValueError("answer_confidence must be in [0, 1]")
        if self.supplied_example_count < 0:
            raise ValueError("supplied_example_count must be non-negative")


@dataclass(frozen=True)
class ResourceAllocation:
    retrieval_allowed: bool
    search_query_priority: int
    source_followup_priority: int
    rationale: str


@dataclass(frozen=True)
class PolicyDecision:
    task_regime: TaskRegime
    primary_effort_mode: EffortMode
    profile_influence: ProfileInfluence
    profile_route_allowed: bool
    targeted_complement: ComplementKind | None
    task_complements: frozenset[ComplementKind]
    unresolved_uncertainties: tuple[LoadBearingUncertainty, ...]
    required_verifiers: tuple[VerifierKind, ...]
    pending_verifiers: tuple[VerifierKind, ...]
    actions: tuple[PolicyAction, ...]
    resource_allocation: ResourceAllocation
    should_stop: bool
    stop_reason: str

    def trace(self) -> dict[str, object]:
        """Public policy trace; excludes private reasoning and raw profile data."""

        return {
            "task_regime": self.task_regime.value,
            "load_bearing_uncertainty_count": len(self.unresolved_uncertainties),
            "profile_influence": self.profile_influence.value,
            "profile_route_allowed": self.profile_route_allowed,
            "targeted_complement": (
                self.targeted_complement.value if self.targeted_complement else None
            ),
            "primary_effort_mode": self.primary_effort_mode.value,
            "stop_reason": self.stop_reason,
        }


class RuntimePolicyV2:
    """Deterministic FOIL_vNEXT_CANDIDATE_V2 controller."""

    version = "FOIL_vNEXT_CANDIDATE_V2"

    def classify_regime(self, task: TaskContext) -> TaskRegime:
        # Benchmark names are intentionally ignored. The same task properties
        # must yield the same policy inside and outside a benchmark.
        if task.freshness_sensitive:
            return TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL
        if task.closed_context and task.multi_hop:
            return TaskRegime.CLOSED_CONTEXT_MULTI_HOP
        if task.abstract_transformation:
            return TaskRegime.ABSTRACT_TRANSFORMATION
        if task.closed_book and task.technical_reasoning:
            return TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING
        if task.requires_external_retrieval:
            return TaskRegime.EXTERNAL_RETRIEVAL
        return TaskRegime.MIXED_TOOL_TASK

    def task_complements(
        self, task: TaskContext, regime: TaskRegime
    ) -> frozenset[ComplementKind]:
        required = set(task.required_complements)
        for uncertainty in task.uncertainties:
            if uncertainty.decisive and not uncertainty.resolved:
                required.update(CLAIM_COMPLEMENTS[uncertainty.claim_kind])

        if regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL:
            required.update(
                {ComplementKind.EVIDENCE_DISCIPLINE, ComplementKind.TOOL_SELECTION}
            )
        elif regime is TaskRegime.EXTERNAL_RETRIEVAL:
            required.add(ComplementKind.TOOL_SELECTION)
        elif regime is TaskRegime.CLOSED_CONTEXT_MULTI_HOP:
            required.add(ComplementKind.DECOMPOSITION)
        elif regime is TaskRegime.ABSTRACT_TRANSFORMATION:
            required.update(
                {ComplementKind.TRANSFER_ADAPTATION, ComplementKind.ERROR_DETECTION}
            )
        return frozenset(required)

    def _profile_evidence_tier(self, profile: ProfileSignal) -> ProfileInfluence:
        if profile.stale:
            return ProfileInfluence.NONE
        if (
            profile.relevance < 0.60
            or profile.support < 0.60
            or profile.independent_observations < 2
        ):
            if profile.relevance >= 0.35 and profile.support >= 0.35:
                return ProfileInfluence.LOW
            return ProfileInfluence.NONE
        if (
            profile.relevance >= 0.90
            and profile.support >= 0.85
            and profile.independent_observations >= 5
            and profile.transfer_confirmations >= 2
        ):
            return ProfileInfluence.HIGH
        if (
            profile.relevance >= 0.75
            and profile.support >= 0.70
            and profile.independent_observations >= 3
        ):
            return ProfileInfluence.MODERATE
        return ProfileInfluence.LOW

    def profile_gate(
        self,
        task: TaskContext,
        regime: TaskRegime,
        profile: ProfileSignal | None,
    ) -> tuple[ProfileInfluence, bool, ComplementKind | None]:
        if profile is None:
            return ProfileInfluence.NONE, False, None

        influence = self._profile_evidence_tier(profile)
        if influence not in {ProfileInfluence.MODERATE, ProfileInfluence.HIGH}:
            return influence, False, None

        # Detailed profile != useful profile. Only a verified gap can trigger a
        # complement, and at least one changed-context confirmation is required.
        if profile.direction is not EvidenceDirection.GAP:
            return influence, False, None
        if profile.transfer_confirmations < 1 or profile.complement is None:
            return influence, False, None

        task_needs = self.task_complements(task, regime)
        if profile.complement not in task_needs:
            return influence, False, None

        return influence, True, profile.complement

    def required_verifiers(
        self, task: TaskContext, regime: TaskRegime
    ) -> tuple[VerifierKind, ...]:
        required: set[VerifierKind] = set()
        for uncertainty in task.uncertainties:
            if uncertainty.decisive and not uncertainty.resolved:
                required.add(CLAIM_VERIFIER[uncertainty.claim_kind])

        if regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL:
            required.add(VerifierKind.CURRENT_SOURCE)
        if regime is TaskRegime.ABSTRACT_TRANSFORMATION and task.supplied_example_count:
            required.add(VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY)
        if task.output_contract_required:
            required.add(VerifierKind.OUTPUT_CONTRACT)

        return tuple(sorted(required, key=lambda verifier: verifier.value))

    def _resource_allocation(
        self, regime: TaskRegime, mode: EffortMode, has_candidate: bool
    ) -> ResourceAllocation:
        if regime in {
            TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING,
            TaskRegime.ABSTRACT_TRANSFORMATION,
            TaskRegime.CLOSED_CONTEXT_MULTI_HOP,
        }:
            return ResourceAllocation(False, 0, 0, "task-evidence-only")
        if mode is EffortMode.DISCOVERY:
            return ResourceAllocation(True, 3, 1, "candidate-discovery-first")
        if mode is EffortMode.VERIFICATION:
            return ResourceAllocation(True, 1, 3, "decisive-verification-first")
        if mode is EffortMode.MIXED:
            return ResourceAllocation(True, 2, 2, "mixed-tool-balance")
        return ResourceAllocation(has_candidate, 0, 0, "reasoning-first")

    def decide(
        self, task: TaskContext, profile: ProfileSignal | None = None
    ) -> PolicyDecision:
        regime = self.classify_regime(task)
        influence, route_allowed, targeted = self.profile_gate(task, regime, profile)
        task_needs = self.task_complements(task, regime)
        unresolved = tuple(
            uncertainty
            for uncertainty in task.uncertainties
            if uncertainty.decisive and not uncertainty.resolved
        )
        required = self.required_verifiers(task, regime)
        pending = tuple(
            verifier
            for verifier in required
            if verifier not in task.completed_verifiers
        )

        should_stop = task.has_viable_candidate and not unresolved and not pending

        if should_stop:
            if regime in {
                TaskRegime.EXTERNAL_RETRIEVAL,
                TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL,
                TaskRegime.ABSTRACT_TRANSFORMATION,
            }:
                mode = EffortMode.VERIFICATION
            else:
                mode = EffortMode.REASONING
            stop_reason = "all_decisive_uncertainties_resolved"
        elif regime in {
            TaskRegime.EXTERNAL_RETRIEVAL,
            TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL,
        }:
            if not task.has_viable_candidate:
                mode = EffortMode.DISCOVERY
                stop_reason = "continue_discovery"
            else:
                mode = EffortMode.VERIFICATION
                stop_reason = "continue_verification"
        elif regime is TaskRegime.ABSTRACT_TRANSFORMATION:
            if task.has_viable_candidate and (unresolved or pending):
                mode = EffortMode.VERIFICATION
                stop_reason = "continue_example_verification"
            else:
                mode = EffortMode.REASONING
                stop_reason = "continue_rule_induction"
        elif regime in {
            TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING,
            TaskRegime.CLOSED_CONTEXT_MULTI_HOP,
        }:
            mode = EffortMode.REASONING
            stop_reason = "continue_reasoning"
        else:
            mode = EffortMode.MIXED
            stop_reason = "continue_mixed_work"

        actions: list[PolicyAction] = []
        if regime is TaskRegime.EXTERNAL_RETRIEVAL:
            actions.append(
                PolicyAction.DISCOVER_CANDIDATES
                if not task.has_viable_candidate
                else PolicyAction.VERIFY_CANDIDATE
            )
        elif regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL:
            actions.append(PolicyAction.PREFER_CURRENT_SOURCE)
            actions.append(
                PolicyAction.DISCOVER_CANDIDATES
                if not task.has_viable_candidate
                else PolicyAction.VERIFY_CANDIDATE
            )
        elif regime is TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING:
            actions.append(PolicyAction.REASON_CLOSED_BOOK)
        elif regime is TaskRegime.ABSTRACT_TRANSFORMATION:
            actions.append(PolicyAction.INDUCE_RULE)
            if task.has_viable_candidate and task.supplied_example_count:
                actions.append(PolicyAction.CHECK_RULE_AGAINST_ALL_EXAMPLES)
        elif regime is TaskRegime.CLOSED_CONTEXT_MULTI_HOP:
            actions.append(PolicyAction.DECOMPOSE_SUPPLIED_EVIDENCE)
        else:
            actions.append(PolicyAction.MIX_TOOLS_AND_REASONING)

        if task.output_contract_required and VerifierKind.OUTPUT_CONTRACT in pending:
            actions.append(PolicyAction.CHECK_OUTPUT_CONTRACT)

        # Minimal-complement rule: never add profile friction after the task is
        # already complete, and never emit more than one targeted complement.
        effective_route = route_allowed and not should_stop
        effective_target = targeted if effective_route else None
        if effective_route:
            actions.append(PolicyAction.APPLY_TARGETED_COMPLEMENT)
        if should_stop:
            actions.append(PolicyAction.STOP)

        allocation = self._resource_allocation(regime, mode, task.has_viable_candidate)
        return PolicyDecision(
            task_regime=regime,
            primary_effort_mode=mode,
            profile_influence=influence,
            profile_route_allowed=effective_route,
            targeted_complement=effective_target,
            task_complements=task_needs,
            unresolved_uncertainties=unresolved,
            required_verifiers=required,
            pending_verifiers=pending,
            actions=tuple(actions),
            resource_allocation=allocation,
            should_stop=should_stop,
            stop_reason=stop_reason,
        )

    def next_external_action(
        self,
        decision: PolicyDecision,
        *,
        search_queries_used: int,
        source_followups_used: int,
        max_search_queries: int,
        max_source_followups: int,
    ) -> str | None:
        """Choose the next external action without increasing a fixed ceiling."""

        if decision.should_stop or not decision.resource_allocation.retrieval_allowed:
            return None

        queries_left = search_queries_used < max_search_queries
        followups_left = source_followups_used < max_source_followups

        if decision.primary_effort_mode is EffortMode.DISCOVERY:
            if queries_left:
                return "search_query"
            if followups_left:
                return "source_followup"
            return None

        if decision.primary_effort_mode is EffortMode.VERIFICATION:
            if followups_left:
                return "source_followup"
            if queries_left:
                return "search_query"
            return None

        if queries_left:
            return "search_query"
        if followups_left:
            return "source_followup"
        return None


def policy_trace(decision: PolicyDecision) -> dict[str, object]:
    return decision.trace()
