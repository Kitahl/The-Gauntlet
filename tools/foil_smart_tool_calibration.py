"""Target-derived calibration for FOIL's bounded tool and interjection routes.

The benchmark owner supplies the score target and total token envelope.  This
module converts those values into token-equivalent utility weights; it does not
embed a product-wide token ceiling.  Historical route outcomes are admitted
only when their evidence is explicitly marked auditable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from foil_smart_tool_value import (
    PPM,
    UtilityWeights,
    ValueGatePolicy,
    jeffreys_bound_ppm,
)


class CalibrationStatus(str, Enum):
    EXECUTE = "EXECUTE"
    STAND_DOWN = "STAND_DOWN"
    UNCALIBRATED = "UNCALIBRATED"


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _ppm(name: str, value: object) -> int:
    result = _non_negative_int(name, value)
    if result > PPM:
        raise ValueError(f"{name} must be in [0, {PPM}]")
    return result


@dataclass(frozen=True)
class BenchmarkTarget:
    benchmark_rows: int
    baseline_correct: int
    target_correct: int
    maximum_total_tokens: int
    maximum_damage_to_rescue_ppm: int = 500_000
    invalid_loss_fraction_ppm: int = 500_000
    utility_margin_ppm: int = 50_000
    minimum_observations: int = 20
    interval_mass_ppm: int = 950_000

    def __post_init__(self) -> None:
        for name in (
            "benchmark_rows",
            "baseline_correct",
            "target_correct",
            "maximum_total_tokens",
            "minimum_observations",
        ):
            _non_negative_int(name, getattr(self, name))
        for name in (
            "maximum_damage_to_rescue_ppm",
            "invalid_loss_fraction_ppm",
            "utility_margin_ppm",
            "interval_mass_ppm",
        ):
            _ppm(name, getattr(self, name))
        if self.benchmark_rows == 0:
            raise ValueError("benchmark_rows must be positive")
        if not 0 <= self.baseline_correct < self.target_correct <= self.benchmark_rows:
            raise ValueError(
                "score target must satisfy 0 <= baseline < target <= rows"
            )
        if self.maximum_total_tokens == 0:
            raise ValueError("maximum_total_tokens must be positive")
        if self.maximum_damage_to_rescue_ppm == 0:
            raise ValueError("maximum_damage_to_rescue_ppm must be positive")
        if not 0 < self.interval_mass_ppm < PPM:
            raise ValueError("interval_mass_ppm must be strictly inside (0, PPM)")

    @property
    def required_net_rescues(self) -> int:
        return self.target_correct - self.baseline_correct

    @property
    def target_tokens_per_net_rescue(self) -> int:
        return self.maximum_total_tokens // self.required_net_rescues


@dataclass(frozen=True)
class TargetCalibration:
    target: BenchmarkTarget
    weights: UtilityWeights
    value_gate: ValueGatePolicy

    def trace(self) -> dict[str, object]:
        return {
            "schema": "foil.smart-tool-target-calibration.v1",
            "benchmark_rows": self.target.benchmark_rows,
            "baseline_correct": self.target.baseline_correct,
            "target_correct": self.target.target_correct,
            "required_net_rescues": self.target.required_net_rescues,
            "caller_maximum_total_tokens": self.target.maximum_total_tokens,
            "target_tokens_per_net_rescue": self.target.target_tokens_per_net_rescue,
            "rescue_value_microunits": self.weights.rescue_value_microunits,
            "damage_loss_microunits": self.weights.damage_loss_microunits,
            "invalid_loss_microunits": self.weights.invalid_loss_microunits,
            "token_price_microunits": self.weights.token_price_microunits,
            "minimum_utility_microunits": self.value_gate.minimum_utility_microunits,
            "minimum_observations": self.value_gate.minimum_observations,
            "interval_mass_ppm": self.value_gate.interval_mass_ppm,
            "hard_limit_embedded_in_foil": False,
            "cost_varies_by_tool_contract": True,
        }


@dataclass(frozen=True)
class HistoricalRouteEvidence:
    route_id: str
    attempts: int
    rescues: int
    damages: int
    invalid_outcomes: int
    total_extra_tokens: int
    auditable: bool
    evidence_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.route_id, str) or not self.route_id.strip():
            raise ValueError("route_id must be non-empty text")
        if not isinstance(self.evidence_reason, str) or not self.evidence_reason.strip():
            raise ValueError("evidence_reason must be non-empty text")
        for name in (
            "attempts",
            "rescues",
            "damages",
            "invalid_outcomes",
            "total_extra_tokens",
        ):
            _non_negative_int(name, getattr(self, name))
        if self.rescues + self.damages > self.attempts:
            raise ValueError("rescues plus damages cannot exceed attempts")
        if self.invalid_outcomes > self.attempts:
            raise ValueError("invalid_outcomes cannot exceed attempts")
        if not isinstance(self.auditable, bool):
            raise TypeError("auditable must be bool")

    @property
    def observed_mean_extra_tokens(self) -> int:
        if self.attempts == 0:
            return 0
        return math.ceil(self.total_extra_tokens / self.attempts)


@dataclass(frozen=True)
class HistoricalRouteDecision:
    route_id: str
    status: CalibrationStatus
    reason: str
    attempts: int
    rescue_lcb_ppm: int | None
    damage_ucb_ppm: int | None
    invalid_ucb_ppm: int | None
    observed_mean_extra_tokens: int
    utility_lower_bound_microunits: int | None

    def trace(self) -> dict[str, object]:
        return {
            "route_id": self.route_id,
            "status": self.status.value,
            "reason": self.reason,
            "attempts": self.attempts,
            "rescue_lcb_ppm": self.rescue_lcb_ppm,
            "damage_ucb_ppm": self.damage_ucb_ppm,
            "invalid_ucb_ppm": self.invalid_ucb_ppm,
            "observed_mean_extra_tokens": self.observed_mean_extra_tokens,
            "utility_lower_bound_microunits": self.utility_lower_bound_microunits,
        }


def calibrate_target(target: BenchmarkTarget) -> TargetCalibration:
    """Derive the value gate from a caller target, not a fixed FOIL ceiling."""

    if not isinstance(target, BenchmarkTarget):
        raise TypeError("target must be BenchmarkTarget")
    rescue_value = target.target_tokens_per_net_rescue
    if rescue_value == 0:
        raise ValueError("token envelope is smaller than required net rescues")
    damage_loss = math.ceil(
        rescue_value * PPM / target.maximum_damage_to_rescue_ppm
    )
    invalid_loss = math.ceil(
        rescue_value * target.invalid_loss_fraction_ppm / PPM
    )
    margin = math.ceil(rescue_value * target.utility_margin_ppm / PPM)
    return TargetCalibration(
        target=target,
        weights=UtilityWeights(
            rescue_value_microunits=rescue_value,
            damage_loss_microunits=damage_loss,
            invalid_loss_microunits=invalid_loss,
            token_price_microunits=1,
        ),
        value_gate=ValueGatePolicy(
            enabled=True,
            benchmark_exploration=False,
            minimum_observations=target.minimum_observations,
            interval_mass_ppm=target.interval_mass_ppm,
            minimum_utility_microunits=margin,
        ),
    )


def build_calibrated_runtime_policy(
    calibration: TargetCalibration,
    *,
    allow_unadmitted_benchmark_selection: bool = False,
):
    """Wire a target calibration into the active runtime without exploration."""

    if not isinstance(calibration, TargetCalibration):
        raise TypeError("calibration must be TargetCalibration")
    from foil_smart_tool_runtime import SmartToolRuntimePolicy

    return SmartToolRuntimePolicy(
        enabled=True,
        value_gate=calibration.value_gate,
        weights=calibration.weights,
        allow_unadmitted_benchmark_selection=allow_unadmitted_benchmark_selection,
    )


def assess_historical_route(
    evidence: HistoricalRouteEvidence,
    calibration: TargetCalibration,
) -> HistoricalRouteDecision:
    """Apply the same conservative economics to one frozen route history."""

    if not isinstance(evidence, HistoricalRouteEvidence):
        raise TypeError("evidence must be HistoricalRouteEvidence")
    if not isinstance(calibration, TargetCalibration):
        raise TypeError("calibration must be TargetCalibration")
    mean_cost = evidence.observed_mean_extra_tokens
    if not evidence.auditable:
        return HistoricalRouteDecision(
            evidence.route_id,
            CalibrationStatus.UNCALIBRATED,
            evidence.evidence_reason,
            evidence.attempts,
            None,
            None,
            None,
            mean_cost,
            None,
        )
    if evidence.attempts < calibration.value_gate.minimum_observations:
        return HistoricalRouteDecision(
            evidence.route_id,
            CalibrationStatus.UNCALIBRATED,
            "insufficient_auditable_observations",
            evidence.attempts,
            None,
            None,
            None,
            mean_cost,
            None,
        )
    tail_ppm = (PPM - calibration.value_gate.interval_mass_ppm) // 2
    rescue_lcb = jeffreys_bound_ppm(
        successes=evidence.rescues,
        attempts=evidence.attempts,
        quantile_ppm=tail_ppm,
    )
    damage_ucb = jeffreys_bound_ppm(
        successes=evidence.damages,
        attempts=evidence.attempts,
        quantile_ppm=PPM - tail_ppm,
    )
    invalid_ucb = jeffreys_bound_ppm(
        successes=evidence.invalid_outcomes,
        attempts=evidence.attempts,
        quantile_ppm=PPM - tail_ppm,
    )
    weights = calibration.weights
    utility = math.floor(
        (
            rescue_lcb * weights.rescue_value_microunits
            - damage_ucb * weights.damage_loss_microunits
            - invalid_ucb * weights.invalid_loss_microunits
        )
        / PPM
    ) - mean_cost
    if utility > calibration.value_gate.minimum_utility_microunits:
        status = CalibrationStatus.EXECUTE
        reason = "conservative_historical_utility_above_target_margin"
    else:
        status = CalibrationStatus.STAND_DOWN
        reason = "conservative_historical_utility_not_above_target_margin"
    return HistoricalRouteDecision(
        evidence.route_id,
        status,
        reason,
        evidence.attempts,
        rescue_lcb,
        damage_ucb,
        invalid_ucb,
        mean_cost,
        utility,
    )
