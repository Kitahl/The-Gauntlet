"""Experimental FOIL vNext runtime policy.

This module is deliberately independent of the permanent FOIL implementation.
It turns task/profile evidence into a small, deterministic runtime policy.
It records policy state only; it does not store hidden reasoning.
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
    APPLY_PROFILE_SUPPORT = "apply_profile_support"
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


BENCHMARK_REGIMES: Mapping[str, TaskRegime] = {
    "browsecomp": TaskRegime.EXTERNAL_RETRIEVAL,
    "freshqa": TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL,
    "gpqa": TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING,
    "gpqadiamond": TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING,
    "arcagi2": TaskRegime.ABSTRACT_TRANSFORMATION,
    "hotpotqa": TaskRegime.CLOSED_CONTEXT_MULTI_HOP,
}


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


@dataclass(frozen=True)
class LoadBearingUncertainty:
    """An unresolved fact/check that could change the final answer."""

    label: str
    claim_kind: ClaimKind = ClaimKind.LOGICAL
    decisive: bool = True
    resolved: bool = False


@dataclass(frozen=True)
class ProfileSignal:
    """Compact evidence gate for profile influence.

    Relevance and support are separate on purpose: high topical relevance is not
    evidence of competence. `independent_observations` and
    `transfer_confirmations` refer only to independently demonstrated evidence.
    """

    relevance: float = 0.0
    support: float = 0.0
    independent_observations: int = 0
    transfer_confirmations: int = 0
    stale: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.relevance <= 1.0:
            raise ValueError("relevance must be in [0, 1]")
        if not 0.0 <= self.support <= 1.0:
            raise ValueError("support must be in [0, 1]")
        if self.independent_observations < 0 or self.transfer_confirmations < 0:
            raise ValueError("profile evidence counts must be non-negative")


@dataclass(frozen=True)
class TaskContext:
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
    unresolved_uncertainties: tuple[LoadBearingUncertainty, ...]
    required_verifiers: tuple[VerifierKind, ...]
    pending_verifiers: tuple[VerifierKind, ...]
    actions: tuple[PolicyAction, ...]
    resource_allocation: ResourceAllocation
    should_stop: bool
    stop_reason: str

    def trace(self) -> dict[str, object]:
        """Public policy trace. It intentionally excludes hidden reasoning."""

        return {
            "task_regime": self.task_regime.value,
            "load_bearing_uncertainty_count": len(self.unresolved_uncertainties),
            "profile_influence": self.profile_influence.value,
            "primary_effort_mode": self.primary_effort_mode.value,
            "stop_reason": self.stop_reason,
        }


class RuntimePolicy:
    """Deterministic FOIL_vNEXT_CANDIDATE_V1 controller."""

    version = "FOIL_vNEXT_CANDIDATE_V1"

    def classify_regime(self, task: TaskContext) -> TaskRegime:
        if task.benchmark:
            key = _norm(task.benchmark)
            for alias, regime in BENCHMARK_REGIMES.items():
                if alias in key or key in alias:
                    return regime

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

    def profile_gate(self, profile: ProfileSignal | None) -> tuple[ProfileInfluence, bool]:
        if profile is None or profile.stale:
            return ProfileInfluence.NONE, False

        # Weak relevance/support never changes routing. A small LOW trace is
        # allowed only to record that evidence existed but was not actionable.
        if (
            profile.relevance < 0.60
            or profile.support < 0.60
            or profile.independent_observations < 2
        ):
            if profile.relevance >= 0.35 and profile.support >= 0.35:
                return ProfileInfluence.LOW, False
            return ProfileInfluence.NONE, False

        if (
            profile.relevance >= 0.90
            and profile.support >= 0.85
            and profile.independent_observations >= 5
            and profile.transfer_confirmations >= 2
        ):
            return ProfileInfluence.HIGH, True

        if (
            profile.relevance >= 0.75
            and profile.support >= 0.70
            and profile.independent_observations >= 3
        ):
            return ProfileInfluence.MODERATE, True

        return ProfileInfluence.LOW, False

    def required_verifiers(
        self, task: TaskContext, regime: TaskRegime
    ) -> tuple[VerifierKind, ...]:
        required: set[VerifierKind] = set()
        for uncertainty in task.uncertainties:
            if uncertainty.decisive and not uncertainty.resolved:
                required.add(CLAIM_VERIFIER[uncertainty.claim_kind])

        # Regime-level hard obligations cannot be optimized away by confidence.
        if regime is TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL:
            required.add(VerifierKind.CURRENT_SOURCE)
        if regime is TaskRegime.ABSTRACT_TRANSFORMATION and task.supplied_example_count:
            required.add(VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY)
        if task.output_contract_required:
            required.add(VerifierKind.OUTPUT_CONTRACT)

        return tuple(sorted(required, key=lambda v: v.value))

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
        influence, route_allowed = self.profile_gate(profile)
        unresolved = tuple(
            u for u in task.uncertainties if u.decisive and not u.resolved
        )
        required = self.required_verifiers(task, regime)
        pending = tuple(v for v in required if v not in task.completed_verifiers)

        mandatory_complete = not pending
        should_stop = (
            task.has_viable_candidate
            and not unresolved
            and mandatory_complete
        )

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

        # A high confidence number is not a stop condition. Unresolved decisive
        # uncertainty and mandatory verifiers control stopping.
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
        if route_allowed:
            actions.append(PolicyAction.APPLY_PROFILE_SUPPORT)
        if should_stop:
            actions.append(PolicyAction.STOP)

        allocation = self._resource_allocation(regime, mode, task.has_viable_candidate)
        return PolicyDecision(
            task_regime=regime,
            primary_effort_mode=mode,
            profile_influence=influence,
            profile_route_allowed=route_allowed,
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
        """Choose the next external-resource action under a fixed ceiling.

        This function allocates an already-fixed benchmark budget; it never
        increases the ceiling.
        """

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
