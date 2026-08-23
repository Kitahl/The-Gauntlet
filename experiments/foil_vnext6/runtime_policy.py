"""Composable post-freeze strategy controller for FOIL.

This module extends the frozen FOIL vNext V1 epistemic controller without
modifying it. V1 still decides the task regime, mandatory verifier obligations,
profile influence, and stopping state. This module chooses exactly one next
reasoning/acting operator under explicit budgets.

The public trace records controller state only. It never records private
scratchpads or chain-of-thought.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from experiments.foil_vnext.runtime_policy import (
    PolicyDecision,
    ProfileSignal,
    RuntimePolicy,
    TaskContext,
    TaskRegime,
    VerifierKind,
)


class TaskComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyOperator(str, Enum):
    """One-step operators available to the composable controller."""

    STOP = "stop"
    DIRECT = "direct"
    DECOMPOSE = "decompose"
    REACT = "react"
    EXACT_EXECUTION = "exact_execution"
    CLAIM_NATIVE_VERIFY = "claim_native_verify"
    BOUNDED_CHALLENGER_SEARCH = "bounded_challenger_search"
    EVIDENCE_TRIGGERED_REFLECTION = "evidence_triggered_reflection"
    INDEPENDENT_REVIEW = "independent_review"
    MASTERMIND_CAUSAL_AUDIT = "mastermind_causal_audit"
    BLOCKED = "blocked"


class EvidenceAuthority(str, Enum):
    """Authority of information produced by an operator.

    INTERNAL_HEURISTIC includes CoT, same-model critique, self-consistency,
    branching, reflection, and Mastermind process diagnosis. Those signals may
    guide the next action but do not by themselves discharge a load-bearing
    factual or technical uncertainty.
    """

    NONE = "none"
    INTERNAL_HEURISTIC = "internal_heuristic"
    EXTERNAL_OBSERVATION = "external_observation"
    CLAIM_NATIVE = "claim_native"
    INDEPENDENT_REVIEW = "independent_review"


OPERATOR_LINEAGE: Mapping[StrategyOperator, str] = {
    StrategyOperator.STOP: "FOIL stop/no-op",
    StrategyOperator.DIRECT: "direct baseline",
    StrategyOperator.DECOMPOSE: "CoT / least-to-most",
    StrategyOperator.REACT: "ReAct",
    StrategyOperator.EXACT_EXECUTION: "PAL / PoT / CodeSteer-like exact route",
    StrategyOperator.CLAIM_NATIVE_VERIFY: "CoVe + CRITIC",
    StrategyOperator.BOUNDED_CHALLENGER_SEARCH: (
        "self-consistency / ToT challenger search"
    ),
    StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION: "Reflexion, failure-gated",
    StrategyOperator.INDEPENDENT_REVIEW: "cross-family or independent reviewer",
    StrategyOperator.MASTERMIND_CAUSAL_AUDIT: "Mastermind causal-defect audit",
    StrategyOperator.BLOCKED: "FOIL unresolved-state release",
}


VERIFIER_PRIORITY: Mapping[VerifierKind, int] = {
    VerifierKind.CURRENT_SOURCE: 0,
    VerifierKind.SOURCE_EVIDENCE: 1,
    VerifierKind.EXECUTION_TEST: 2,
    VerifierKind.EXACT_CALCULATION: 3,
    VerifierKind.SUPPLIED_EXAMPLE_CONSISTENCY: 4,
    VerifierKind.CONTRADICTION_COUNTEREXAMPLE: 5,
    VerifierKind.OUTPUT_CONTRACT: 6,
}


TOOL_VERIFIERS = frozenset(
    {
        VerifierKind.CURRENT_SOURCE,
        VerifierKind.SOURCE_EVIDENCE,
        VerifierKind.EXECUTION_TEST,
        VerifierKind.EXACT_CALCULATION,
    }
)


EXACT_VERIFIERS = frozenset(
    {
        VerifierKind.EXECUTION_TEST,
        VerifierKind.EXACT_CALCULATION,
    }
)


@dataclass(frozen=True)
class OperatorCost:
    deliberation_units: int = 0
    tool_calls: int = 0
    branch_slots: int = 0
    revision_slots: int = 0
    independent_reviews: int = 0
    mastermind_loops: int = 0

    def __post_init__(self) -> None:
        values = (
            self.deliberation_units,
            self.tool_calls,
            self.branch_slots,
            self.revision_slots,
            self.independent_reviews,
            self.mastermind_loops,
        )
        if any(value < 0 for value in values):
            raise ValueError("operator costs must be non-negative")


@dataclass(frozen=True)
class StrategyBudget:
    """Explicit remaining budget supplied by the surrounding runner.

    The controller may spend this budget but cannot increase any component.
    `mastermind_loops_remaining` is capped at three by contract.
    """

    deliberation_units_remaining: int = 4
    tool_calls_remaining: int = 4
    branch_slots_remaining: int = 2
    revision_slots_remaining: int = 1
    independent_reviews_remaining: int = 0
    mastermind_loops_remaining: int = 3

    def __post_init__(self) -> None:
        values = (
            self.deliberation_units_remaining,
            self.tool_calls_remaining,
            self.branch_slots_remaining,
            self.revision_slots_remaining,
            self.independent_reviews_remaining,
            self.mastermind_loops_remaining,
        )
        if any(value < 0 for value in values):
            raise ValueError("remaining budgets must be non-negative")
        if self.mastermind_loops_remaining > 3:
            raise ValueError("Mastermind is capped at three loops")

    def can_afford(self, cost: OperatorCost) -> bool:
        return (
            self.deliberation_units_remaining >= cost.deliberation_units
            and self.tool_calls_remaining >= cost.tool_calls
            and self.branch_slots_remaining >= cost.branch_slots
            and self.revision_slots_remaining >= cost.revision_slots
            and self.independent_reviews_remaining >= cost.independent_reviews
            and self.mastermind_loops_remaining >= cost.mastermind_loops
        )

    def spend(self, cost: OperatorCost) -> "StrategyBudget":
        if not self.can_afford(cost):
            raise ValueError("operator cost exceeds the remaining budget")
        return StrategyBudget(
            deliberation_units_remaining=(
                self.deliberation_units_remaining - cost.deliberation_units
            ),
            tool_calls_remaining=self.tool_calls_remaining - cost.tool_calls,
            branch_slots_remaining=self.branch_slots_remaining - cost.branch_slots,
            revision_slots_remaining=(
                self.revision_slots_remaining - cost.revision_slots
            ),
            independent_reviews_remaining=(
                self.independent_reviews_remaining - cost.independent_reviews
            ),
            mastermind_loops_remaining=(
                self.mastermind_loops_remaining - cost.mastermind_loops
            ),
        )


@dataclass(frozen=True)
class StrategyTaskContext:
    """Task-local signals used only for strategy selection.

    These fields do not update the persistent FOIL profile. They describe the
    current task state and must be supplied or derived before the operator is
    selected.
    """

    task: TaskContext
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    subproblem_count: int = 1
    sequential_tool_interaction: bool = False
    candidate_count: int = 0
    candidate_disagreement: bool = False
    demonstrated_failure: bool = False
    failure_target_identified: bool = False
    reflection_attempts: int = 0
    repeated_route_failures: int = 0
    high_impact: bool = False
    causal_or_process_defect: bool = False
    independent_reviewer_available: bool = False
    unavailable_verifiers: frozenset[VerifierKind] = frozenset()

    def __post_init__(self) -> None:
        counts = (
            self.subproblem_count,
            self.candidate_count,
            self.reflection_attempts,
            self.repeated_route_failures,
        )
        if any(value < 0 for value in counts):
            raise ValueError("strategy-state counts must be non-negative")
        if self.subproblem_count < 1:
            raise ValueError("subproblem_count must be at least one")


@dataclass(frozen=True)
class StrategyDecision:
    controller_version: str
    base_decision: PolicyDecision
    operator: StrategyOperator
    operator_lineage: str
    reason_code: str
    minimum_evidence_authority: EvidenceAuthority
    required_verifier: VerifierKind | None
    may_discharge_load_bearing_uncertainty: bool
    cost: OperatorCost
    budget_before: StrategyBudget
    budget_after: StrategyBudget
    should_stop: bool
    blocked: bool

    def trace(self) -> dict[str, object]:
        """Receipt-safe public trace with no private reasoning."""

        return {
            "controller_version": self.controller_version,
            "task_regime": self.base_decision.task_regime.value,
            "strategy_operator": self.operator.value,
            "strategy_lineage": self.operator_lineage,
            "reason_code": self.reason_code,
            "minimum_evidence_authority": self.minimum_evidence_authority.value,
            "required_verifier": (
                self.required_verifier.value if self.required_verifier else None
            ),
            "may_discharge_load_bearing_uncertainty": (
                self.may_discharge_load_bearing_uncertainty
            ),
            "load_bearing_uncertainty_count": len(
                self.base_decision.unresolved_uncertainties
            ),
            "profile_influence": self.base_decision.profile_influence.value,
            "deliberation_units_remaining": (
                self.budget_after.deliberation_units_remaining
            ),
            "tool_calls_remaining": self.budget_after.tool_calls_remaining,
            "branch_slots_remaining": self.budget_after.branch_slots_remaining,
            "revision_slots_remaining": self.budget_after.revision_slots_remaining,
            "independent_reviews_remaining": (
                self.budget_after.independent_reviews_remaining
            ),
            "mastermind_loops_remaining": (
                self.budget_after.mastermind_loops_remaining
            ),
            "stop_reason": self.base_decision.stop_reason,
        }


class ComposableRuntimePolicy:
    """FOIL vNext6 one-operator-at-a-time strategy composer.

    The frozen V1 policy remains authoritative for regime classification,
    profile gating, mandatory verifier selection, and stopping. This composer
    supplies only the smallest eligible next operator. The caller must update
    task/evidence state and invoke the controller again after the operator runs.
    """

    version = "FOIL_vNEXT6_COMPOSABLE_POLICY_V1"

    def __init__(self, base_policy: RuntimePolicy | None = None) -> None:
        self.base_policy = base_policy or RuntimePolicy()

    @staticmethod
    def _pending_verifier(base: PolicyDecision) -> VerifierKind | None:
        if not base.pending_verifiers:
            return None
        return min(base.pending_verifiers, key=lambda item: VERIFIER_PRIORITY[item])

    @staticmethod
    def _cost_for_verifier(verifier: VerifierKind) -> OperatorCost:
        return OperatorCost(
            deliberation_units=1,
            tool_calls=1 if verifier in TOOL_VERIFIERS else 0,
        )

    @staticmethod
    def _effective_candidate_count(context: StrategyTaskContext) -> int:
        if context.candidate_count:
            return context.candidate_count
        return 1 if context.task.has_viable_candidate else 0

    @staticmethod
    def _mastermind_eligible(
        context: StrategyTaskContext, budget: StrategyBudget
    ) -> bool:
        return (
            context.high_impact
            and context.causal_or_process_defect
            and context.repeated_route_failures >= 2
            and budget.mastermind_loops_remaining > 0
            and budget.deliberation_units_remaining > 0
        )

    def _emit(
        self,
        *,
        base: PolicyDecision,
        operator: StrategyOperator,
        reason_code: str,
        authority: EvidenceAuthority,
        verifier: VerifierKind | None,
        may_discharge: bool,
        cost: OperatorCost,
        budget: StrategyBudget,
        should_stop: bool = False,
        blocked: bool = False,
    ) -> StrategyDecision:
        after = budget.spend(cost)
        return StrategyDecision(
            controller_version=self.version,
            base_decision=base,
            operator=operator,
            operator_lineage=OPERATOR_LINEAGE[operator],
            reason_code=reason_code,
            minimum_evidence_authority=authority,
            required_verifier=verifier,
            may_discharge_load_bearing_uncertainty=may_discharge,
            cost=cost,
            budget_before=budget,
            budget_after=after,
            should_stop=should_stop,
            blocked=blocked,
        )

    def _blocked(
        self,
        *,
        base: PolicyDecision,
        reason_code: str,
        verifier: VerifierKind | None,
        budget: StrategyBudget,
    ) -> StrategyDecision:
        return self._emit(
            base=base,
            operator=StrategyOperator.BLOCKED,
            reason_code=reason_code,
            authority=EvidenceAuthority.NONE,
            verifier=verifier,
            may_discharge=False,
            cost=OperatorCost(),
            budget=budget,
            blocked=True,
        )

    def _native_verification(
        self,
        *,
        base: PolicyDecision,
        context: StrategyTaskContext,
        verifier: VerifierKind,
        budget: StrategyBudget,
    ) -> StrategyDecision:
        if verifier in context.unavailable_verifiers:
            if (
                context.high_impact
                and context.independent_reviewer_available
                and budget.independent_reviews_remaining > 0
            ):
                cost = OperatorCost(
                    deliberation_units=1,
                    independent_reviews=1,
                )
                if not budget.can_afford(cost):
                    return self._blocked(
                        base=base,
                        reason_code="independent_review_budget_exhausted",
                        verifier=verifier,
                        budget=budget,
                    )
                return self._emit(
                    base=base,
                    operator=StrategyOperator.INDEPENDENT_REVIEW,
                    reason_code="native_verifier_unavailable_use_independent_review",
                    authority=EvidenceAuthority.INDEPENDENT_REVIEW,
                    verifier=verifier,
                    may_discharge=True,
                    cost=cost,
                    budget=budget,
                )
            return self._blocked(
                base=base,
                reason_code="required_verifier_unavailable",
                verifier=verifier,
                budget=budget,
            )

        cost = self._cost_for_verifier(verifier)
        if not budget.can_afford(cost):
            return self._blocked(
                base=base,
                reason_code="required_verifier_budget_exhausted",
                verifier=verifier,
                budget=budget,
            )

        operator = (
            StrategyOperator.EXACT_EXECUTION
            if verifier in EXACT_VERIFIERS
            else StrategyOperator.CLAIM_NATIVE_VERIFY
        )
        return self._emit(
            base=base,
            operator=operator,
            reason_code="execute_mandatory_claim_native_verifier",
            authority=EvidenceAuthority.CLAIM_NATIVE,
            verifier=verifier,
            may_discharge=True,
            cost=cost,
            budget=budget,
        )

    def decide(
        self,
        context: StrategyTaskContext,
        budget: StrategyBudget,
        profile: ProfileSignal | None = None,
    ) -> StrategyDecision:
        base = self.base_policy.decide(context.task, profile)

        # V1's release condition is final. No review, reflection, branching, or
        # Mastermind pass is appended after mandatory obligations are complete.
        if base.should_stop:
            return self._emit(
                base=base,
                operator=StrategyOperator.STOP,
                reason_code="v1_release_condition_satisfied",
                authority=EvidenceAuthority.NONE,
                verifier=None,
                may_discharge=False,
                cost=OperatorCost(),
                budget=budget,
                should_stop=True,
            )

        pending = self._pending_verifier(base)
        has_candidate = context.task.has_viable_candidate

        # Candidate generation and discovery precede candidate verification.
        # Exact calculation/execution is the exception because it may itself
        # construct the candidate.
        if not has_candidate:
            exact_pending = next(
                (item for item in base.pending_verifiers if item in EXACT_VERIFIERS),
                None,
            )
            if exact_pending is not None:
                return self._native_verification(
                    base=base,
                    context=context,
                    verifier=exact_pending,
                    budget=budget,
                )

            if self._mastermind_eligible(context, budget):
                cost = OperatorCost(deliberation_units=1, mastermind_loops=1)
                return self._emit(
                    base=base,
                    operator=StrategyOperator.MASTERMIND_CAUSAL_AUDIT,
                    reason_code="repeated_route_failure_find_smallest_causal_defect",
                    authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                    verifier=None,
                    may_discharge=False,
                    cost=cost,
                    budget=budget,
                )

            candidate_count = self._effective_candidate_count(context)
            if (
                candidate_count >= 2
                and context.candidate_disagreement
                and budget.branch_slots_remaining >= 2
                and budget.deliberation_units_remaining >= 1
            ):
                cost = OperatorCost(deliberation_units=1, branch_slots=2)
                return self._emit(
                    base=base,
                    operator=StrategyOperator.BOUNDED_CHALLENGER_SEARCH,
                    reason_code=(
                        "multiple_plausible_candidates_generate_bounded_challenger"
                    ),
                    authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                    verifier=None,
                    may_discharge=False,
                    cost=cost,
                    budget=budget,
                )

            if base.task_regime in {
                TaskRegime.EXTERNAL_RETRIEVAL,
                TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL,
                TaskRegime.MIXED_TOOL_TASK,
            } and (
                context.sequential_tool_interaction
                or context.task.requires_external_retrieval
                or context.task.freshness_sensitive
                or pending
                in {
                    VerifierKind.CURRENT_SOURCE,
                    VerifierKind.SOURCE_EVIDENCE,
                }
                or base.task_regime
                in {
                    TaskRegime.EXTERNAL_RETRIEVAL,
                    TaskRegime.FRESHNESS_SENSITIVE_RETRIEVAL,
                }
            ):
                cost = OperatorCost(deliberation_units=1, tool_calls=1)
                if not budget.can_afford(cost):
                    return self._blocked(
                        base=base,
                        reason_code="required_discovery_budget_exhausted",
                        verifier=pending,
                        budget=budget,
                    )
                return self._emit(
                    base=base,
                    operator=StrategyOperator.REACT,
                    reason_code="interleave_reasoning_with_task_required_observations",
                    authority=EvidenceAuthority.EXTERNAL_OBSERVATION,
                    verifier=pending,
                    may_discharge=False,
                    cost=cost,
                    budget=budget,
                )

            if (
                context.complexity is TaskComplexity.HIGH
                or context.subproblem_count > 1
                or base.task_regime
                in {
                    TaskRegime.CLOSED_BOOK_TECHNICAL_REASONING,
                    TaskRegime.ABSTRACT_TRANSFORMATION,
                    TaskRegime.CLOSED_CONTEXT_MULTI_HOP,
                }
            ):
                cost = OperatorCost(deliberation_units=1)
                if budget.can_afford(cost):
                    return self._emit(
                        base=base,
                        operator=StrategyOperator.DECOMPOSE,
                        reason_code="structured_reasoning_needed_before_candidate",
                        authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                        verifier=None,
                        may_discharge=False,
                        cost=cost,
                        budget=budget,
                    )

            return self._emit(
                base=base,
                operator=StrategyOperator.DIRECT,
                reason_code="lowest_cost_candidate_generation",
                authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                verifier=None,
                may_discharge=False,
                cost=OperatorCost(),
                budget=budget,
            )

        # Once a viable candidate exists, mandatory claim-native verification
        # outranks all generic review, reflection, branching, and audit methods.
        if pending is not None:
            return self._native_verification(
                base=base,
                context=context,
                verifier=pending,
                budget=budget,
            )

        # Reflection is allowed only after externally demonstrated failure, with
        # a specific correction target, and at most once for the current task.
        if (
            context.demonstrated_failure
            and context.failure_target_identified
            and context.reflection_attempts == 0
        ):
            cost = OperatorCost(deliberation_units=1, revision_slots=1)
            if budget.can_afford(cost):
                return self._emit(
                    base=base,
                    operator=StrategyOperator.EVIDENCE_TRIGGERED_REFLECTION,
                    reason_code="verified_failure_with_specific_revision_target",
                    authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                    verifier=None,
                    may_discharge=False,
                    cost=cost,
                    budget=budget,
                )

        # Independent review is an optional high-impact escalation when native
        # verification has completed but the decisive uncertainty remains.
        if (
            base.unresolved_uncertainties
            and context.high_impact
            and context.independent_reviewer_available
        ):
            cost = OperatorCost(deliberation_units=1, independent_reviews=1)
            if budget.can_afford(cost):
                return self._emit(
                    base=base,
                    operator=StrategyOperator.INDEPENDENT_REVIEW,
                    reason_code=(
                        "native_check_inconclusive_high_impact_independent_review"
                    ),
                    authority=EvidenceAuthority.INDEPENDENT_REVIEW,
                    verifier=None,
                    may_discharge=True,
                    cost=cost,
                    budget=budget,
                )

        # Mastermind is a late process/causal audit, not a default final pass and
        # not an independent verifier.
        if self._mastermind_eligible(context, budget):
            cost = OperatorCost(deliberation_units=1, mastermind_loops=1)
            return self._emit(
                base=base,
                operator=StrategyOperator.MASTERMIND_CAUSAL_AUDIT,
                reason_code="distinct_causal_or_process_defect_after_cheaper_routes",
                authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                verifier=None,
                may_discharge=False,
                cost=cost,
                budget=budget,
            )

        candidate_count = self._effective_candidate_count(context)
        if (
            base.unresolved_uncertainties
            and candidate_count >= 2
            and context.candidate_disagreement
        ):
            cost = OperatorCost(deliberation_units=1, branch_slots=2)
            if budget.can_afford(cost):
                return self._emit(
                    base=base,
                    operator=StrategyOperator.BOUNDED_CHALLENGER_SEARCH,
                    reason_code="inconclusive_candidates_need_one_bounded_challenger",
                    authority=EvidenceAuthority.INTERNAL_HEURISTIC,
                    verifier=None,
                    may_discharge=False,
                    cost=cost,
                    budget=budget,
                )

        # Do not loop generic self-critique after the available verifier has
        # already run. Preserve the unresolved state instead.
        return self._blocked(
            base=base,
            reason_code="no_distinct_evidence_bearing_action_available",
            verifier=None,
            budget=budget,
        )


def strategy_trace(decision: StrategyDecision) -> dict[str, object]:
    return decision.trace()
