"""FOIL evidence estimator — monotone, tiered, recency-aware competence classification.

Replaces the all-or-nothing rule in `foil_profile._classification` /
`foil_profile_migrate_v2._classification`, which was non-monotone: a single
verified miss permanently blocked PROMISING_STRENGTH regardless of how much
later verified evidence accumulated (`correct=20, incorrect=1 -> UNCERTAIN`).

Model
-----
Competence on a capability is a latent success probability `theta`.  Verified
independent observations are Bernoulli draws.  The posterior is Beta with a
Jeffreys prior, which is the standard reference prior for a binomial rate and
is well behaved at n = 0.

Classification is a *decision* on that posterior, not a count rule:

    PROMISING_STRENGTH   P(theta > theta_hi | data) >= confidence
    POSSIBLE_GAP         P(theta < theta_lo | data) >= confidence
    UNCERTAIN            neither, and effective evidence >= min_effective_n
    INSUFFICIENT_EVIDENCE  otherwise

Monotonicity is structural: the Beta posterior tail P(theta > t) is
non-decreasing in the success count and non-increasing in the failure count, so
adding a verified correct observation can never lower the classification rank.
`tests/test_foil_evidence.py::EvidenceEstimatorTests` proves this by exhaustive
enumeration over a finite grid.

Evidence tiers
--------------
Not all verified evidence is equal.  A mechanically key-scored onboarding screen
is verified but is *not* real-work evidence, and treating the two identically is
what made a two-item screen able to manufacture a load-bearing classification.
Each tier carries a weight; screen evidence is admissible but cannot on its own
reach a load-bearing state, because `min_effective_n` is expressed in REAL_WORK
units.

Recency
-------
Observations decay by an exponential half-life at *routing* time.  History is
never erased; its authority decreases.  Decay produces fractional effective
counts, which the Beta posterior accepts natively.

No third-party dependencies: the regularized incomplete beta function is
implemented here with the standard continued-fraction expansion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Sequence

SCHEMA = "egrt.foil-evidence.v1"

#: Tolerance for the `load_bearing >= min_effective_n` comparison.
#:
#: Recency decay is evaluated against `now`, which is strictly later than an
#: observation recorded moments earlier, so a *fresh* observation weighs
#: `0.5 ** (epsilon / half_life)` - one or two ULPs below 1.0, not 1.0. Without a
#: tolerance, exactly `min_effective_n` brand-new observations land on either
#: side of the gate depending on sub-microsecond scheduling, which makes the
#: verdict irreproducible for the most ordinary case there is. The tolerance is
#: far smaller than any weight the decay can produce for genuinely aged
#: evidence, so it cannot admit evidence the policy meant to exclude.
SUFFICIENCY_TOLERANCE = 1e-9

__all__ = [
    "SCHEMA",
    "SUFFICIENCY_TOLERANCE",
    "Classification",
    "EvidenceTier",
    "EvidencePolicy",
    "Observation",
    "PosteriorSummary",
    "classify",
    "summarize",
    "false_classification_rates",
    "items_for_target_error",
    "regularized_incomplete_beta",
    "sprt_boundaries",
    "sprt_decision",
    "sprt_log_likelihood_ratio",
]


class Classification(str, Enum):
    """Ordered from weakest to strongest claim about the person."""

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNCERTAIN = "UNCERTAIN"
    POSSIBLE_GAP = "POSSIBLE_GAP"
    PROMISING_STRENGTH = "PROMISING_STRENGTH"

    @property
    def is_load_bearing(self) -> bool:
        return self in {Classification.POSSIBLE_GAP, Classification.PROMISING_STRENGTH}


class EvidenceTier(str, Enum):
    """Where an observation came from. Weight is set by EvidencePolicy."""

    REAL_WORK = "REAL_WORK"          # verified independent performance on actual work
    SCREEN = "SCREEN"                # mechanically key-scored onboarding/calibration item
    ASSISTED = "ASSISTED"            # succeeded with material help -> never competence evidence
    UNVERIFIED = "UNVERIFIED"        # no verifier ran -> never competence evidence


@dataclass(frozen=True)
class Observation:
    """One performance event.

    `correct` is the outcome.  `tier` decides admissibility and weight.
    `time` is used only for recency weighting and may be omitted.
    """

    correct: bool
    tier: EvidenceTier = EvidenceTier.REAL_WORK
    time: datetime | None = None
    representation: str | None = None
    verifier: str | None = None
    capability: str | None = None

    def __post_init__(self) -> None:
        if self.time is not None and self.time.tzinfo is None:
            raise ValueError("observation time must be timezone-aware")


@dataclass(frozen=True)
class EvidencePolicy:
    """Every threshold that governs a competence claim, in one place.

    Defaults are deliberately conservative.  `theta_lo`/`theta_hi` are the
    capability bands the classification is *about*; a claim is only made when the
    posterior puts `confidence` mass beyond the band edge.

    Decay-floor boundary, stated explicitly
    ---------------------------------------
    `min_weight` is a floor, not a cutoff: arbitrarily old evidence keeps
    `min_weight` of its authority forever.  That means a large enough pile of
    fully decayed REAL_WORK observations can still cross `min_effective_n`,
    because `min_weight * N >= min_effective_n` once `N >= min_effective_n /
    min_weight` (with the defaults, N >= 80).  This is deliberate - history is
    downweighted, never erased - but it is a real boundary, so a claim that
    "old evidence cannot decide" holds only for N < 80 at the defaults.
    `tests/test_foil_evidence.py::DecayFloorTests` pins the small-N behaviour
    and names the boundary.
    """

    theta_lo: float = 0.45
    theta_hi: float = 0.70
    confidence: float = 0.80
    min_effective_n: float = 4.0
    prior_a: float = 0.5              # Jeffreys
    prior_b: float = 0.5
    #: Freshness weight; an engineering choice, not a learned forgetting law.
    #: The horizon is UNRESOLVED: no study here fixes 180 days as the right
    #: half-life for competence evidence. Callers may override or disable it
    #: (None) and should not read the default as a measured constant.
    half_life_days: float | None = 180.0
    min_weight: float = 0.05          # decay floor: old evidence loses authority, never vanishes
    tier_weights: dict[str, float] = field(
        default_factory=lambda: {
            EvidenceTier.REAL_WORK.value: 1.0,
            EvidenceTier.SCREEN.value: 0.4,
            EvidenceTier.ASSISTED.value: 0.0,
            EvidenceTier.UNVERIFIED.value: 0.0,
        }
    )

    def __post_init__(self) -> None:
        if not 0.0 < self.theta_lo <= self.theta_hi < 1.0:
            raise ValueError("require 0 < theta_lo <= theta_hi < 1")
        if not 0.5 <= self.confidence < 1.0:
            raise ValueError("confidence must be in [0.5, 1)")
        if self.prior_a <= 0 or self.prior_b <= 0:
            raise ValueError("prior parameters must be positive")
        if self.half_life_days is not None and self.half_life_days <= 0:
            raise ValueError("half_life_days must be positive or None")
        if not 0.0 <= self.min_weight <= 1.0:
            raise ValueError("min_weight must be in [0, 1]")

    def weight_for(self, tier: EvidenceTier) -> float:
        return float(self.tier_weights.get(tier.value, 0.0))


@dataclass(frozen=True)
class PosteriorSummary:
    classification: Classification
    effective_correct: float
    effective_incorrect: float
    effective_n: float
    load_bearing_n: float
    posterior_mean: float
    p_above_hi: float
    p_below_lo: float
    reason: str


# --------------------------------------------------------------------------- #
# regularized incomplete beta, I_x(a, b)                                       #
# --------------------------------------------------------------------------- #

def _betacf(a: float, b: float, x: float, *, max_iter: int = 300, eps: float = 3e-16) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b) = P(Beta(a, b) <= x). Accurate to ~1e-12 for the range used here."""
    if not 0.0 <= x <= 1.0:
        raise ValueError("x must be in [0, 1]")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return min(1.0, max(0.0, front * _betacf(a, b, x) / a))
    return min(1.0, max(0.0, 1.0 - front * _betacf(b, a, 1.0 - x) / b))


def _tail_above(a: float, b: float, t: float) -> float:
    """P(theta > t) for theta ~ Beta(a, b)."""
    return 1.0 - regularized_incomplete_beta(a, b, t)


# --------------------------------------------------------------------------- #
# weighting                                                                    #
# --------------------------------------------------------------------------- #

def _recency_weight(policy: EvidencePolicy, obs_time: datetime | None, now: datetime) -> float:
    if policy.half_life_days is None or obs_time is None:
        return 1.0
    age_days = max(0.0, (now - obs_time).total_seconds() / 86400.0)
    decayed = 0.5 ** (age_days / policy.half_life_days)
    return max(policy.min_weight, decayed)


def _effective_counts(
    observations: Sequence[Observation],
    policy: EvidencePolicy,
    now: datetime,
) -> tuple[float, float, float]:
    """Return (effective_correct, effective_incorrect, load_bearing_n).

    `load_bearing_n` counts REAL_WORK weight only; it is what `min_effective_n`
    is measured against, so a screen alone cannot reach a load-bearing state.
    """
    correct = incorrect = load_bearing = 0.0
    for obs in observations:
        weight = policy.weight_for(obs.tier) * _recency_weight(policy, obs.time, now)
        if weight <= 0.0:
            continue
        if obs.correct:
            correct += weight
        else:
            incorrect += weight
        if obs.tier is EvidenceTier.REAL_WORK:
            load_bearing += weight
    return correct, incorrect, load_bearing


# --------------------------------------------------------------------------- #
# classification                                                               #
# --------------------------------------------------------------------------- #

def summarize(
    observations: Iterable[Observation],
    policy: EvidencePolicy | None = None,
    *,
    now: datetime | None = None,
) -> PosteriorSummary:
    policy = policy or EvidencePolicy()
    now = now or datetime.now(timezone.utc)
    rows = list(observations)
    correct, incorrect, load_bearing = _effective_counts(rows, policy, now)

    a = policy.prior_a + correct
    b = policy.prior_b + incorrect
    p_above = _tail_above(a, b, policy.theta_hi)
    p_below = 1.0 - _tail_above(a, b, policy.theta_lo)
    mean = a / (a + b)
    total = correct + incorrect

    sufficient = load_bearing >= policy.min_effective_n - SUFFICIENCY_TOLERANCE
    if sufficient and p_above >= policy.confidence:
        cls, reason = (
            Classification.PROMISING_STRENGTH,
            f"P(theta>{policy.theta_hi:.2f})={p_above:.3f} >= {policy.confidence:.2f}",
        )
    elif sufficient and p_below >= policy.confidence:
        cls, reason = (
            Classification.POSSIBLE_GAP,
            f"P(theta<{policy.theta_lo:.2f})={p_below:.3f} >= {policy.confidence:.2f}",
        )
    elif sufficient:
        cls, reason = (
            Classification.UNCERTAIN,
            "sufficient real-work evidence, but neither band edge is decided",
        )
    else:
        cls, reason = (
            Classification.INSUFFICIENT_EVIDENCE,
            f"effective real-work evidence {load_bearing:.2f} < {policy.min_effective_n:.2f}",
        )

    return PosteriorSummary(
        classification=cls,
        effective_correct=correct,
        effective_incorrect=incorrect,
        effective_n=total,
        load_bearing_n=load_bearing,
        posterior_mean=mean,
        p_above_hi=p_above,
        p_below_lo=p_below,
        reason=reason,
    )


def classify(
    observations: Iterable[Observation],
    policy: EvidencePolicy | None = None,
    *,
    now: datetime | None = None,
) -> Classification:
    return summarize(observations, policy, now=now).classification


# --------------------------------------------------------------------------- #
# design calculators — make the false-classification target checkable          #
# --------------------------------------------------------------------------- #

def false_classification_rates(
    k: int,
    true_theta: float,
    policy: EvidencePolicy | None = None,
    *,
    tier: EvidenceTier = EvidenceTier.REAL_WORK,
) -> dict[str, float]:
    """Exact per-capability misclassification rates for a k-item undecayed screen.

    Enumerates all k+1 outcome counts under Binomial(k, true_theta) and reports
    the probability of each classification.  `false_gap` / `false_strength` are
    the rates that contradict `true_theta` relative to the policy bands.
    """
    policy = policy or EvidencePolicy()
    if k < 0:
        raise ValueError("k must be non-negative")
    probs = {c.value: 0.0 for c in Classification}
    for c in range(k + 1):
        pmf = math.comb(k, c) * (true_theta ** c) * ((1.0 - true_theta) ** (k - c))
        rows = [Observation(correct=True, tier=tier)] * c + [Observation(correct=False, tier=tier)] * (k - c)
        probs[classify(rows, policy).value] += pmf
    return {
        **probs,
        "false_gap": probs[Classification.POSSIBLE_GAP.value] if true_theta >= policy.theta_hi else 0.0,
        "false_strength": probs[Classification.PROMISING_STRENGTH.value] if true_theta <= policy.theta_lo else 0.0,
    }


def items_for_target_error(
    target: float,
    competent_theta: float = 0.85,
    weak_theta: float = 0.40,
    policy: EvidencePolicy | None = None,
    *,
    detection_power: float = 0.80,
    max_k: int = 60,
) -> dict[str, Any]:
    """Smallest k that is both *safe* and *useful*.

    Safe:   false-gap and false-strength rates are at or below `target`.
    Useful: the screen actually detects the truth at least `detection_power` of
            the time.  Without this second condition the answer is trivially
            k = 1, because a classifier that never decides is never wrong.
    """
    policy = policy or EvidencePolicy()
    best_power = 0.0
    best_k_for_power: int | None = None
    for k in range(1, max_k + 1):
        strong = false_classification_rates(k, competent_theta, policy)
        weak = false_classification_rates(k, weak_theta, policy)
        detect_strength = strong[Classification.PROMISING_STRENGTH.value]
        detect_gap = weak[Classification.POSSIBLE_GAP.value]
        safe = strong["false_gap"] <= target and weak["false_strength"] <= target
        power = min(detect_strength, detect_gap)
        if safe and power > best_power:
            best_power = power
            best_k_for_power = k
        if safe and detect_strength >= detection_power and detect_gap >= detection_power:
            return {
                "k": k,
                "target_error": target,
                "detection_power": detection_power,
                "false_gap": strong["false_gap"],
                "false_strength": weak["false_strength"],
                "detect_strength": detect_strength,
                "detect_gap": detect_gap,
                "reason": None,
                "best_achieved_power": power,
                "best_k_for_power": k,
            }
    # Non-convergence is reported honestly rather than papered over. With the
    # module defaults (competent 0.85, weak 0.40) no k <= max_k separates the two
    # bands at the requested power, so there is no admissible screen length; the
    # caller must widen the bands, lower the power, or accept that the screen
    # cannot decide.
    return {
        "k": None,
        "target_error": target,
        "detection_power": detection_power,
        "reason": (
            f"no k in 1..{max_k} is simultaneously safe (false rates <= {target}) and "
            f"powerful (detection >= {detection_power}) for competent_theta="
            f"{competent_theta} vs weak_theta={weak_theta}"
        ),
        "best_achieved_power": best_power,
        "best_k_for_power": best_k_for_power,
    }


# --------------------------------------------------------------------------- #
# SPRT cross-check - diagnostic only, never the classifier                     #
# --------------------------------------------------------------------------- #

def sprt_log_likelihood_ratio(
    correct: int,
    incorrect: int,
    p_lo: float = 0.4,
    p_hi: float = 0.8,
) -> float:
    """Wald log-likelihood ratio for H1: theta = `p_hi` against H0: theta = `p_lo`.

    Positive values favour the competent hypothesis. This is a *diagnostic
    cross-check* on the Beta-posterior decision in `summarize()`, not the
    classifier: nothing in this module routes on it, and it deliberately uses
    point hypotheses where the classifier uses bands.
    """
    if correct < 0 or incorrect < 0:
        raise ValueError("counts must be non-negative")
    if not 0.0 < p_lo < 1.0 or not 0.0 < p_hi < 1.0:
        raise ValueError("p_lo and p_hi must be in (0, 1)")
    return correct * math.log(p_hi / p_lo) + incorrect * math.log((1.0 - p_hi) / (1.0 - p_lo))


def sprt_boundaries(alpha: float = 0.05, beta: float = 0.05) -> tuple[float, float]:
    """Wald's (upper, lower) log-ratio boundaries for error rates `alpha`/`beta`."""
    if not 0.0 < alpha < 1.0 or not 0.0 < beta < 1.0:
        raise ValueError("alpha and beta must be in (0, 1)")
    return math.log((1.0 - beta) / alpha), math.log(beta / (1.0 - alpha))


def sprt_decision(
    correct: int,
    incorrect: int,
    *,
    p_lo: float = 0.4,
    p_hi: float = 0.8,
    alpha: float = 0.05,
    beta: float = 0.05,
) -> str:
    """Sequential-test verdict as a DIAGNOSTIC cross-check, not the classifier.

    `summarize()` remains the only classifier FOIL routes on. This function
    exists so a disagreement between two independent decision rules is visible
    instead of silent; it does not carry evidence tiers, recency decay, or the
    real-work sufficiency gate, so it must never be substituted for
    `classify()`.
    """
    upper, lower = sprt_boundaries(alpha, beta)
    llr = sprt_log_likelihood_ratio(correct, incorrect, p_lo, p_hi)
    if llr >= upper:
        return Classification.PROMISING_STRENGTH.value
    if llr <= lower:
        return Classification.POSSIBLE_GAP.value
    return Classification.UNCERTAIN.value
