"""Paired-design statistics for same-item BASE vs FOIL comparisons. Stdlib only.

Why this module exists
----------------------
A four-config paired benchmark produces, per configuration, a 2x2 table of item
outcomes: how many items both conditions got right, how many only one got right,
how many both missed. The only cells that carry information about the contrast
are the two discordant ones, and the test that uses exactly those is McNemar's.
Everything here is the arithmetic of that table and nothing else - no data
loading, no scoring, no I/O - so every number can be checked against a hand
computation and reused by any harness.

Three tests, deliberately reported together
-------------------------------------------
* `exact_mcnemar` - the exact conditional (binomial) test. It conditions on the
  number of discordant pairs and asks whether the split is fairer than chance.
  It is *conservative*: with a discrete null it spends less than the nominal
  alpha, so at small sample sizes it can be unable to reach alpha at all. Six
  discordant pairs is the minimum at which a two-sided exact test reaches 0.05.
* `midp_mcnemar` - the mid-p variant, which counts half of the observed point
  mass instead of all of it. It is less conservative and closer to nominal size,
  at the cost of not being guaranteed to hold alpha in every finite case.
  Preregistered as *primary* with the exact test reported alongside as
  sensitivity, so neither can be selected after seeing which one looks better.
* `wilson_interval` - a per-arm coverage interval that does not collapse to zero
  width at 0/n or n/n the way the normal-approximation interval does.

`holm_adjust` controls the family-wise error rate across the four
configurations. It is step-down and enforces monotonicity, so an adjusted value
is never smaller than one earlier in the sorted order.

Conventions
-----------
`b` is the count of items the *first* arm got right and the second missed; `c`
is the reverse. Concordant cells (`a` and `d`) never enter the test - they are
reported because a reader needs the denominator, not because the test uses them.
Every p-value returned is two-sided.
"""
from __future__ import annotations

from math import comb
from statistics import NormalDist
from typing import Any, Iterable, Sequence

SCHEMA = "egrt.foil-paired-stats.v1"

__all__ = [
    "SCHEMA", "discordance", "exact_mcnemar", "midp_mcnemar",
    "wilson_interval", "holm_adjust", "paired_report",
]


def _binom_pmf(k: int, n: int) -> float:
    """P(X = k) for X ~ Binomial(n, 1/2)."""
    if n < 0 or k < 0 or k > n:
        return 0.0
    return comb(n, k) * 0.5 ** n


def _binom_cdf(k: int, n: int) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(_binom_pmf(i, n) for i in range(k + 1))


def discordance(pairs: Iterable[tuple[bool, bool]]) -> dict[str, int]:
    """Count the 2x2 paired table from (first_correct, second_correct) pairs.

    Pairs whose outcome is unknown on either side must be excluded by the caller
    *before* this point and counted separately; silently dropping them here would
    shrink the denominator without leaving a trace.
    """
    a = b = c = d = 0
    for first, second in pairs:
        if first and second:
            a += 1
        elif first and not second:
            b += 1
        elif not first and second:
            c += 1
        else:
            d += 1
    return {
        "both_correct": a, "first_only": b, "second_only": c, "both_wrong": d,
        "n": a + b + c + d, "discordant": b + c,
    }


def exact_mcnemar(b: int, c: int) -> float:
    """Two-sided exact conditional McNemar p-value.

    Conditional on `n = b + c` discordant pairs, the null is Binomial(n, 1/2).
    The two-sided p-value is `min(1, 2 * P(X <= min(b, c)))`. Because that null is
    symmetric, this is identical to the "sum of all outcomes at most as probable
    as the observed one" construction; the test suite checks that equivalence
    over a grid rather than assuming it.

    `b = c = 0` (no discordant pairs) returns 1.0: absence of evidence, never to
    be reported as evidence of agreement.
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2.0 * _binom_cdf(min(b, c), n))


def midp_mcnemar(b: int, c: int) -> float:
    """Two-sided mid-p McNemar p-value.

    `2 * (P(X < k) + 0.5 * P(X = k))` with `k = min(b, c)`, equivalently the exact
    p-value minus the observed point mass. Bounded to [0, 1]; `b == c` yields
    exactly 1.0.
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    value = 2.0 * (_binom_cdf(k - 1, n) + 0.5 * _binom_pmf(k, n))
    return min(1.0, max(0.0, value))


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Chosen over the normal-approximation ("Wald") interval because Wald degenerates
    to zero width at 0/n and n/n - exactly the cells a small benchmark hits - and
    undercovers badly near the boundary.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("need 0 <= successes <= n")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")
    if n == 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    p = successes / n
    c = z * z / n
    centre = (p + c / 2.0) / (1.0 + c)
    half = (z / (1.0 + c)) * ((p * (1.0 - p) / n + c / (4.0 * n)) ** 0.5)
    return (max(0.0, centre - half), min(1.0, centre + half))


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values, returned in the input order.

    Adjusted value at ascending rank j is `(m - j) * p_j`, capped at 1, carried
    forward as a running maximum. The running maximum is what enforces
    monotonicity: without it a later, larger raw p-value could come back smaller
    than an earlier one, and a reader comparing two adjusted values would draw
    the wrong ordering.
    """
    values = [float(value) for value in p_values]
    if not values:
        return []
    for value in values:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"p-value out of range: {value}")
    m = len(values)
    order = sorted(range(m), key=lambda i: values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * values[index]))
        adjusted[index] = running
    return adjusted


def paired_report(pairs: Iterable[tuple[bool, bool]], *,
                  first_label: str = "A", second_label: str = "B",
                  confidence: float = 0.95) -> dict[str, Any]:
    """One configuration's complete paired result: table, per-arm CIs, both tests.

    Which test is primary and which is sensitivity is named in the payload, not
    left for a reader to choose after the fact.
    """
    rows = [(bool(first), bool(second)) for first, second in pairs]
    table = discordance(rows)
    n = table["n"]
    first_correct = table["both_correct"] + table["first_only"]
    second_correct = table["both_correct"] + table["second_only"]
    b, c = table["first_only"], table["second_only"]
    return {
        "schema": SCHEMA,
        "arms": {"first": first_label, "second": second_label},
        "n_pairs": n,
        "discordance": dict(table),
        "arm_accuracy": {
            first_label: {
                "correct": first_correct, "n": n,
                "accuracy": (first_correct / n) if n else None,
                "wilson95": list(wilson_interval(first_correct, n, confidence)),
            },
            second_label: {
                "correct": second_correct, "n": n,
                "accuracy": (second_correct / n) if n else None,
                "wilson95": list(wilson_interval(second_correct, n, confidence)),
            },
        },
        "primary_test": {
            "name": "mid-p McNemar (two-sided)",
            "p_value": midp_mcnemar(b, c),
        },
        "sensitivity_test": {
            "name": "exact conditional McNemar (two-sided)",
            "p_value": exact_mcnemar(b, c),
        },
        "interpretation_limit": (
            "With no discordant pairs the p-value is 1.0 by construction; that is "
            "absence of evidence, not evidence of equivalence."
        ),
    }
