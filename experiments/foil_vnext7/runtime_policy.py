"""Evidence-typed post-vNext6 FOIL controller.

vNext7 is an additive repair over the vNext6 composable controller. It keeps the
frozen vNext epistemic policy and vNext6 operator library, but makes verifier
targets explicit, preserves the verifier identity during independent-review
escalation, targets ReAct discovery at load-bearing information gaps, and
permits already-captured claim-native evidence to be re-used without repeating
an external tool call.

Public traces contain controller state only; never private reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from experiments.foil_vnext.runtime_policy import (
    CLAIM_VERIFIER,
    ProfileSignal,
    VerifierKind,
)
from experiments.foil_vnext6.runtime_policy import (
    EXACT_VERIFIERS,
    OPERATOR_LINEAGE,
    VERIFIER_PRIORITY,
    ComposableRuntimePolicy,
    EvidenceAuthority,
    OperatorCost,
    StrategyBudget,
    StrategyDecision,
    StrategyOperator,
    StrategyTaskContext,
)


class DiscoveryObjective(str, Enum):
    """Public objective for non-verifying information acquisition."""

    LOAD_BEARING_INFORMATION_GAIN_PER_COST = (
        "load_bearing_information_gain_per_cost"
    )


@dataclass(frozen=True)
class VerificationTarget:
    """A stable public target for one verifier obligation.

    `target_id` may name an atomic claim (for example C3) or a synthetic
    obligation such as O:current_source when the frozen policy imposes a
    regime-level verifier that is not attached to a user-authored claim.
    """

    target_id: str
    verifier: VerifierKind
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("verification target_id is required")


@dataclass(frozen=True)
class CachedEvidenceHint:
    """Receipt-safe metadata saying prior task-local material may be reusable.

    This hint is never evidence by itself. The execution contract must still
    validate the referenced basis, verdict, freshness, content fingerprint, and
    task scope.
    """

    task_instance_id: str
    target_id: str
    verifier: VerifierKind
    stale: bool = False
    freshness_checked: bool = False

    def __post_init__(self) -> None:
        if not self.task_instance_id.strip():
            raise ValueError("cached task_instance_id is required")
        if not self.target_id.strip():
            raise ValueError("cached target_id is required")

    def eligible_for(
        self,
        target: VerificationTarget,
        *,
        task_instance_id: str,
    ) -> bool:
        if self.task_instance_id != task_instance_id:
            return False
        if self.target_id != target.target_id or self.verifier is not target.verifier:
            return False
        if self.stale:
            return False
        if (
            target.verifier is VerifierKind.CURRENT_SOURCE
            and not self.freshness_checked
        ):
            return False
        return True


@dataclass(frozen=True)
class EvidenceTypedTaskContext:
    strategy: StrategyTaskContext
    task_instance_id: str
    cached_evidence: tuple[CachedEvidenceHint, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_instance_id.strip():
            raise ValueError("task_instance_id is required")


@dataclass(frozen=True)
class EvidenceTypedDecision:
    controller_version: str
    task_instance_id: str
    strategy: StrategyDecision
    verification_targets: tuple[VerificationTarget, ...]
    discovery_target_ids: tuple[str, ...] = ()
    discovery_objective: DiscoveryObjective | None = None
    reuse_cached_evidence: bool = False

    @property
    def operator(self) -> StrategyOperator:
        return self.strategy.operator

    @property
    def required_verifier(self) -> VerifierKind | None:
        return self.strategy.required_verifier

    @property
    def should_stop(self) -> bool:
        return self.strategy.should_stop

    @property
    def blocked(self) -> bool:
        return self.strategy.blocked

    @property
    def cost(self) -> OperatorCost:
        return self.strategy.cost

    @property
    def budget_after(self) -> StrategyBudget:
        return self.strategy.budget_after

    def trace(self) -> dict[str, object]:
        trace = dict(self.strategy.trace())
        trace["controller_version"] = self.controller_version
        trace["task_instance_id"] = self.task_instance_id
        trace["verification_target_count"] = len(self.verification_targets)
        trace["discovery_target_count"] = len(self.discovery_target_ids)
        trace["discovery_objective"] = (
            self.discovery_objective.value if self.discovery_objective else None
        )
        trace["cached_evidence_reused"] = self.reuse_cached_evidence
        return trace


class EvidenceTypedRuntimePolicy:
    """FOIL vNext7 evidence-target and cache-reuse layer."""

    version = "FOIL_vNEXT7_EVIDENCE_TYPED_POLICY_V1"

    def __init__(self, parent: ComposableRuntimePolicy | None = None) -> None:
        self.parent = parent or ComposableRuntimePolicy()

    @staticmethod
    def _residual_verifier(decision: StrategyDecision) -> VerifierKind | None:
        candidates = {
            CLAIM_VERIFIER[uncertainty.claim_kind]
            for uncertainty in decision.base_decision.unresolved_uncertainties
        }
        if not candidates:
            return None
        return min(candidates, key=lambda item: VERIFIER_PRIORITY[item])

    @staticmethod
    def _pending_targets(decision: StrategyDecision) -> tuple[VerificationTarget, ...]:
        """Derive the targets a pending verifier would need if it could run."""

        verifier = decision.required_verifier
        if verifier is None:
            return ()

        targets = [
            VerificationTarget(
                target_id=uncertainty.label,
                verifier=verifier,
                synthetic=False,
            )
            for uncertainty in decision.base_decision.unresolved_uncertainties
            if CLAIM_VERIFIER[uncertainty.claim_kind] is verifier
        ]
        if targets:
            # Preserve order while removing duplicate labels.
            seen: set[str] = set()
            unique: list[VerificationTarget] = []
            for target in targets:
                if target.target_id not in seen:
                    seen.add(target.target_id)
                    unique.append(target)
            return tuple(unique)

        # Frozen V1 can impose verifier obligations at the regime/output level
        # even when no unresolved LoadBearingUncertainty names them.
        return (
            VerificationTarget(
                target_id=f"O:{verifier.value}",
                verifier=verifier,
                synthetic=True,
            ),
        )

    @staticmethod
    def _targets(decision: StrategyDecision) -> tuple[VerificationTarget, ...]:
        # Discovery and blocked operators may carry the verifier they are
        # gathering or waiting for, but only authorized verifier operators may
        # expose executable verification targets.
        if not decision.may_discharge_load_bearing_uncertainty:
            return ()
        return EvidenceTypedRuntimePolicy._pending_targets(decision)

    @staticmethod
    def _discovery_targets(decision: StrategyDecision) -> tuple[str, ...]:
        if decision.operator is not StrategyOperator.REACT:
            return ()

        labels = [
            uncertainty.label
            for uncertainty in decision.base_decision.unresolved_uncertainties
            if CLAIM_VERIFIER[uncertainty.claim_kind]
            in {
                VerifierKind.SOURCE_EVIDENCE,
                VerifierKind.CURRENT_SOURCE,
            }
        ]
        if labels:
            return tuple(dict.fromkeys(labels))

        # Some mixed/sequential tool tasks require an observation before a
        # stable atomic claim exists. Give the acquisition step a public target
        # without pretending that target is already a verifiable claim.
        return ("D:external_observation",)

    @staticmethod
    def _cache_covers(
        targets: tuple[VerificationTarget, ...],
        cached: tuple[CachedEvidenceHint, ...],
        *,
        task_instance_id: str,
    ) -> bool:
        if not targets:
            return False
        return all(
            any(
                hint.eligible_for(target, task_instance_id=task_instance_id)
                for hint in cached
            )
            for target in targets
        )

    @staticmethod
    def _native_cached_decision(
        decision: StrategyDecision,
        *,
        verifier: VerifierKind,
        budget: StrategyBudget,
    ) -> StrategyDecision:
        cost = OperatorCost(deliberation_units=1)
        if not budget.can_afford(cost):
            return replace(
                decision,
                operator=StrategyOperator.BLOCKED,
                operator_lineage=OPERATOR_LINEAGE[StrategyOperator.BLOCKED],
                reason_code="cached_evidence_admission_budget_exhausted",
                minimum_evidence_authority=EvidenceAuthority.NONE,
                required_verifier=verifier,
                may_discharge_load_bearing_uncertainty=False,
                cost=OperatorCost(),
                budget_before=budget,
                budget_after=budget,
                should_stop=False,
                blocked=True,
            )

        operator = (
            StrategyOperator.EXACT_EXECUTION
            if verifier in EXACT_VERIFIERS
            else StrategyOperator.CLAIM_NATIVE_VERIFY
        )
        return replace(
            decision,
            operator=operator,
            operator_lineage=OPERATOR_LINEAGE[operator],
            reason_code="admit_cached_claim_native_evidence",
            minimum_evidence_authority=EvidenceAuthority.CLAIM_NATIVE,
            required_verifier=verifier,
            may_discharge_load_bearing_uncertainty=True,
            cost=cost,
            budget_before=budget,
            budget_after=budget.spend(cost),
            should_stop=False,
            blocked=False,
        )

    @staticmethod
    def _decorate(
        decision: StrategyDecision,
        *,
        task_instance_id: str,
        reuse_cached_evidence: bool,
    ) -> EvidenceTypedDecision:
        discovery_targets = EvidenceTypedRuntimePolicy._discovery_targets(decision)
        objective = (
            DiscoveryObjective.LOAD_BEARING_INFORMATION_GAIN_PER_COST
            if discovery_targets
            else None
        )
        return EvidenceTypedDecision(
            controller_version=EvidenceTypedRuntimePolicy.version,
            task_instance_id=task_instance_id,
            strategy=decision,
            verification_targets=EvidenceTypedRuntimePolicy._targets(decision),
            discovery_target_ids=discovery_targets,
            discovery_objective=objective,
            reuse_cached_evidence=reuse_cached_evidence,
        )

    def decide(
        self,
        context: EvidenceTypedTaskContext,
        budget: StrategyBudget,
        profile: ProfileSignal | None = None,
    ) -> EvidenceTypedDecision:
        decision = self.parent.decide(context.strategy, budget, profile)

        # vNext6 can escalate a residual uncertainty to independent review after
        # the native verifier has run, but in that path the verifier field can
        # be None. Preserve the claim-native verifier identity so the review has
        # a machine-checkable evidentiary obligation.
        if (
            decision.operator is StrategyOperator.INDEPENDENT_REVIEW
            and decision.required_verifier is None
        ):
            verifier = self._residual_verifier(decision)
            if verifier is not None:
                decision = replace(
                    decision,
                    reason_code=(
                        "residual_uncertainty_independent_review_with_native_verifier"
                    ),
                    required_verifier=verifier,
                )

        pending_targets = self._pending_targets(decision)
        verifier = decision.required_verifier
        cache_covers = self._cache_covers(
            pending_targets,
            context.cached_evidence,
            task_instance_id=context.task_instance_id,
        )

        # Cached receipt-backed evidence never closes a claim directly. It only
        # removes a repeat external tool call from ordinary claim-native
        # verification. It must never downgrade an explicitly selected
        # independent-review escalation.
        recoverable_block = (
            decision.operator is StrategyOperator.BLOCKED
            and decision.reason_code
            in {
                "required_verifier_budget_exhausted",
                "required_verifier_unavailable",
            }
        )
        native_verifying_operator = decision.operator in {
            StrategyOperator.CLAIM_NATIVE_VERIFY,
            StrategyOperator.EXACT_EXECUTION,
        }

        if (
            verifier is not None
            and cache_covers
            and (recoverable_block or native_verifying_operator)
        ):
            decision = self._native_cached_decision(
                decision,
                verifier=verifier,
                budget=budget,
            )
            return self._decorate(
                decision,
                task_instance_id=context.task_instance_id,
                reuse_cached_evidence=True,
            )

        return self._decorate(
            decision,
            task_instance_id=context.task_instance_id,
            reuse_cached_evidence=False,
        )


def evidence_typed_trace(decision: EvidenceTypedDecision) -> dict[str, object]:
    return decision.trace()
