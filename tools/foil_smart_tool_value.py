"""Conservative pre-launch value gate for one bounded FOIL tool call.

Probabilities come from counted outcomes, never model self-confidence.  The
gate uses Jeffreys-Beta posterior bounds: a lower bound for rescue and upper
bounds for damage and invalid evidence.  Sparse or stale evidence declines in
admitted mode; an explicit benchmark exploration policy may still acquire one
read-only observation without granting it promotion authority.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from foil_evidence import regularized_incomplete_beta
from foil_tool_contract import ToolCost, ToolFamily


PPM = 1_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DifficultyBand(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class PrelaunchStatus(str, Enum):
    EXECUTE = "EXECUTE"
    EXECUTE_EXPLORATION = "EXECUTE_EXPLORATION"
    DECLINE_DISABLED = "DECLINE_DISABLED"
    DECLINE_UNCALIBRATED = "DECLINE_UNCALIBRATED"
    DECLINE_STALE = "DECLINE_STALE"
    DECLINE_NONPOSITIVE_VALUE = "DECLINE_NONPOSITIVE_VALUE"
    DECLINE_BUDGET = "DECLINE_BUDGET"


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _ppm(name: str, value: object) -> int:
    result = _count(name, value)
    if result > PPM:
        raise ValueError(f"{name} must be in [0, {PPM}]")
    return result


def _beta_quantile(probability: float, a: float, b: float) -> float:
    """Invert the regularized incomplete beta by bounded bisection."""

    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    if not all(math.isfinite(value) and value > 0.0 for value in (a, b)):
        raise ValueError("beta parameters must be finite and positive")
    if probability == 0.0:
        return 0.0
    if probability == 1.0:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        if regularized_incomplete_beta(a, b, midpoint) < probability:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0


@dataclass(frozen=True)
class RouteEvidence:
    family: ToolFamily
    difficulty: DifficultyBand
    attempts: int
    rescues: int
    damages: int
    valid_evidence: int
    evidence_digest: str
    fresh: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", ToolFamily(self.family))
        object.__setattr__(self, "difficulty", DifficultyBand(self.difficulty))
        for name in ("attempts", "rescues", "damages", "valid_evidence"):
            _count(name, getattr(self, name))
        if any(
            value > self.attempts
            for value in (self.rescues, self.damages, self.valid_evidence)
        ):
            raise ValueError("evidence event counts cannot exceed attempts")
        if self.rescues + self.damages > self.attempts:
            raise ValueError("one attempt cannot be both rescue and damage")
        if not isinstance(self.evidence_digest, str) or _SHA256.fullmatch(
            self.evidence_digest
        ) is None:
            raise ValueError("evidence_digest must be lowercase SHA-256 hex")
        if not isinstance(self.fresh, bool):
            raise TypeError("fresh must be bool")


@dataclass(frozen=True)
class UtilityWeights:
    rescue_value_microunits: int
    damage_loss_microunits: int
    invalid_loss_microunits: int
    token_price_microunits: int = 0
    latency_price_microunits_per_ms: int = 0

    def __post_init__(self) -> None:
        for name in (
            "rescue_value_microunits",
            "damage_loss_microunits",
            "invalid_loss_microunits",
            "token_price_microunits",
            "latency_price_microunits_per_ms",
        ):
            _count(name, getattr(self, name))
        if self.rescue_value_microunits == 0:
            raise ValueError("rescue_value_microunits must be positive")


@dataclass(frozen=True)
class ValueGatePolicy:
    enabled: bool = False
    benchmark_exploration: bool = False
    minimum_observations: int = 0
    interval_mass_ppm: int = 950_000
    minimum_utility_microunits: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(
            self.benchmark_exploration, bool
        ):
            raise TypeError("enabled and benchmark_exploration must be bool")
        _count("minimum_observations", self.minimum_observations)
        mass = _ppm("interval_mass_ppm", self.interval_mass_ppm)
        if not 0 < mass < PPM:
            raise ValueError("interval_mass_ppm must be strictly inside (0, PPM)")
        _count("minimum_utility_microunits", self.minimum_utility_microunits)


@dataclass(frozen=True)
class PrelaunchDecision:
    status: PrelaunchStatus
    reason: str
    utility_lower_bound_microunits: int | None
    rescue_lcb_ppm: int | None
    damage_ucb_ppm: int | None
    invalid_ucb_ppm: int | None
    maximum_total_tokens: int
    difficulty: DifficultyBand
    family: ToolFamily
    observations: int

    @property
    def executes(self) -> bool:
        return self.status in {
            PrelaunchStatus.EXECUTE,
            PrelaunchStatus.EXECUTE_EXPLORATION,
        }

    def trace(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "utility_lower_bound_microunits": self.utility_lower_bound_microunits,
            "rescue_lcb_ppm": self.rescue_lcb_ppm,
            "damage_ucb_ppm": self.damage_ucb_ppm,
            "invalid_ucb_ppm": self.invalid_ucb_ppm,
            "maximum_total_tokens": self.maximum_total_tokens,
            "difficulty": self.difficulty.value,
            "family": self.family.value,
            "observations": self.observations,
            "probabilities_from_model_self_report": False,
        }


def _bound_ppm(successes: int, attempts: int, probability: float) -> int:
    value = _beta_quantile(
        probability,
        successes + 0.5,
        attempts - successes + 0.5,
    )
    return max(0, min(PPM, int(math.floor(value * PPM))))


def jeffreys_bound_ppm(
    *, successes: int, attempts: int, quantile_ppm: int
) -> int:
    """Return a closed, integer Jeffreys-Beta quantile for shared calibrators."""

    _count("successes", successes)
    _count("attempts", attempts)
    if successes > attempts:
        raise ValueError("successes cannot exceed attempts")
    quantile = _ppm("quantile_ppm", quantile_ppm)
    return _bound_ppm(successes, attempts, quantile / PPM)


def decide_prelaunch(
    *,
    family: ToolFamily,
    difficulty: DifficultyBand,
    cost: ToolCost,
    remaining_unreserved_tokens: int,
    weights: UtilityWeights,
    policy: ValueGatePolicy,
    evidence: RouteEvidence | None,
) -> PrelaunchDecision:
    """Return one typed launch decision without inspecting A0 text or gold."""

    family = ToolFamily(family)
    difficulty = DifficultyBand(difficulty)
    if not isinstance(cost, ToolCost):
        raise TypeError("cost must be ToolCost")
    _count("remaining_unreserved_tokens", remaining_unreserved_tokens)
    if not isinstance(weights, UtilityWeights):
        raise TypeError("weights must be UtilityWeights")
    if not isinstance(policy, ValueGatePolicy):
        raise TypeError("policy must be ValueGatePolicy")
    base = dict(
        maximum_total_tokens=cost.maximum_total_tokens,
        difficulty=difficulty,
        family=family,
        observations=0 if evidence is None else evidence.attempts,
    )
    if not policy.enabled:
        return PrelaunchDecision(
            PrelaunchStatus.DECLINE_DISABLED,
            "value_gate_disabled",
            None,
            None,
            None,
            None,
            **base,
        )
    if cost.maximum_total_tokens > remaining_unreserved_tokens:
        return PrelaunchDecision(
            PrelaunchStatus.DECLINE_BUDGET,
            "caller_token_budget_insufficient",
            None,
            None,
            None,
            None,
            **base,
        )
    evidence_matches = bool(
        evidence is not None
        and evidence.family is family
        and evidence.difficulty is difficulty
    )
    if not evidence_matches or evidence is None or evidence.attempts < policy.minimum_observations:
        if policy.benchmark_exploration:
            return PrelaunchDecision(
                PrelaunchStatus.EXECUTE_EXPLORATION,
                "explicit_single_tool_benchmark_exploration",
                None,
                None,
                None,
                None,
                **base,
            )
        return PrelaunchDecision(
            PrelaunchStatus.DECLINE_UNCALIBRATED,
            "no_matching_minimum_evidence",
            None,
            None,
            None,
            None,
            **base,
        )
    if not evidence.fresh:
        return PrelaunchDecision(
            PrelaunchStatus.DECLINE_STALE,
            "route_evidence_stale",
            None,
            None,
            None,
            None,
            **base,
        )

    tail = (1.0 - policy.interval_mass_ppm / PPM) / 2.0
    rescue_lcb = _bound_ppm(evidence.rescues, evidence.attempts, tail)
    damage_ucb = _bound_ppm(evidence.damages, evidence.attempts, 1.0 - tail)
    invalid_count = evidence.attempts - evidence.valid_evidence
    invalid_ucb = _bound_ppm(invalid_count, evidence.attempts, 1.0 - tail)
    cost_microunits = (
        cost.maximum_total_tokens * weights.token_price_microunits
        + cost.maximum_latency_ms * weights.latency_price_microunits_per_ms
        + cost.maximum_monetary_microunits
        + cost.privacy_cost_microunits
    )
    utility_numerator = (
        rescue_lcb * weights.rescue_value_microunits
        - damage_ucb * weights.damage_loss_microunits
        - invalid_ucb * weights.invalid_loss_microunits
    )
    utility = math.floor(utility_numerator / PPM) - cost_microunits
    if utility <= policy.minimum_utility_microunits:
        status = PrelaunchStatus.DECLINE_NONPOSITIVE_VALUE
        reason = "conservative_utility_not_above_margin"
    else:
        status = PrelaunchStatus.EXECUTE
        reason = "conservative_utility_positive"
    return PrelaunchDecision(
        status,
        reason,
        utility,
        rescue_lcb,
        damage_ucb,
        invalid_ucb,
        **base,
    )
