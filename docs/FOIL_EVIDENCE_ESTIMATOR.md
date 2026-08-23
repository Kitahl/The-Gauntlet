# FOIL Evidence Estimator — measured operating characteristics

**Module:** `tools/foil_evidence.py` (`SCHEMA = egrt.foil-evidence.v1`)
**Status:** every number below was produced by running the shipped code. The
commands are given so any reader can reproduce them.
**Boundary:** these are the *operating characteristics of the estimator*, not
evidence that the estimator measures human competence well. The bands, the
confidence level, the sufficiency floor, and the half-life are **engineering
choices and are UNCALIBRATED**. No study in this repository fixes any of them.

## 1. What the estimator does

Competence on a capability is a latent success probability `theta`. Admissible
observations are Bernoulli draws. The posterior is Beta with a Jeffreys prior
(`prior_a = prior_b = 0.5`). Classification is a decision on that posterior:

| Label | Condition |
|---|---|
| `PROMISING_STRENGTH` | `P(theta > theta_hi \| data) >= confidence` |
| `POSSIBLE_GAP` | `P(theta < theta_lo \| data) >= confidence` |
| `UNCERTAIN` | neither, and the evidence passes both sufficiency and freshness |
| `INSUFFICIENT_EVIDENCE` | effective real-work evidence `< min_effective_n`, **or** no load-bearing observation inside `freshness_horizon_days` (`stale_only = True`) |

Both gates must pass before any verdict is offered. See §5 for the freshness
gate, which is a separate mechanism from the decay weight.

This replaces a count rule that was non-monotone: 20 verified successes and 1
verified miss classified as `UNCERTAIN`, because a single miss permanently
blocked a strength verdict.

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import *
rows=[Observation(correct=True)]*20+[Observation(correct=False)]
s=summarize(rows)
print(s.classification.value, s.p_above_hi, s.posterior_mean)"
```

```
PROMISING_STRENGTH 0.9979994... 0.9318181818181818
```

Measured: `20/1` now reaches `PROMISING_STRENGTH` with
`P(theta > 0.70) = 0.997999` and posterior mean `0.931818`.

## 2. Default policy constants — all engineering choices

`EvidencePolicy()` defaults, printed from the module:

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import EvidencePolicy
P=EvidencePolicy()
print(P.theta_lo, P.theta_hi, P.confidence, P.min_effective_n, P.prior_a, P.prior_b, P.half_life_days, P.min_weight, P.freshness_horizon_days)"
```

```
0.45 0.7 0.8 4.0 0.5 0.5 180.0 0.05 360.0
```

| Constant | Default | Basis |
|---|---|---|
| `theta_lo` | 0.45 | **engineering choice, UNCALIBRATED** — no item bank fixes the weak band edge |
| `theta_hi` | 0.70 | **engineering choice, UNCALIBRATED** |
| `confidence` | 0.80 | **engineering choice, UNCALIBRATED** — chosen to be decisive without a large item bank |
| `min_effective_n` | 4.0 real-work units | **engineering choice, UNCALIBRATED** |
| `prior_a`/`prior_b` | 0.5 / 0.5 | Jeffreys reference prior for a binomial rate — the one principled default here |
| `half_life_days` | 180.0 | **engineering choice, UNCALIBRATED** — not a measured forgetting law |
| `min_weight` | 0.05 | decay floor: history is downweighted, never erased |
| `freshness_horizon_days` | 360.0 | **engineering choice, UNCALIBRATED** — two default half-lives, not a measured staleness threshold |

Tier weights: `REAL_WORK = 1.0`, `SCREEN = 0.4`, `ASSISTED = 0.0`,
`UNVERIFIED = 0.0`. `min_effective_n` is measured in `REAL_WORK` units only.

## 3. Measured false-classification rates

Command:

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import false_classification_rates as f
for k in (4,9,17,30):
    for th in (0.25,0.40,0.60,0.80,0.90):
        r=f(k,th)
        print(k, th, round(r['INSUFFICIENT_EVIDENCE'],4), round(r['UNCERTAIN'],4),
              round(r['POSSIBLE_GAP'],4), round(r['PROMISING_STRENGTH'],4),
              round(r['false_gap'],4), round(r['false_strength'],4))"
```

`false_classification_rates` enumerates all `k+1` outcome counts under
`Binomial(k, theta)` exactly — no simulation, no sampling error. Observations are
`REAL_WORK` tier and undecayed. `undecided = INSUFFICIENT_EVIDENCE + UNCERTAIN`.

| k | θ | INSUFFICIENT | UNCERTAIN | POSSIBLE_GAP | PROMISING_STRENGTH | false_gap | false_strength | undecided |
|---|---|---|---|---|---|---|---|---|
| 4 | 0.25 | 0.0000 | 0.6797 | 0.3164 | 0.0039 | 0.0000 | **0.0039** | 0.6797 |
| 4 | 0.40 | 0.0000 | 0.8448 | 0.1296 | 0.0256 | 0.0000 | **0.0256** | 0.8448 |
| 4 | 0.60 | 0.0000 | 0.8448 | 0.0256 | 0.1296 | 0.0000 | 0.0000 | 0.8448 |
| 4 | 0.80 | 0.0000 | 0.5888 | 0.0016 | 0.4096 | **0.0016** | 0.0000 | 0.5888 |
| 4 | 0.90 | 0.0000 | 0.3438 | 0.0001 | 0.6561 | **0.0001** | 0.0000 | 0.3438 |
| 9 | 0.25 | 0.0000 | 0.3992 | 0.6007 | 0.0001 | 0.0000 | **0.0001** | 0.3992 |
| 9 | 0.40 | 0.0000 | 0.7644 | 0.2318 | 0.0038 | 0.0000 | **0.0038** | 0.7644 |
| 9 | 0.60 | 0.0000 | 0.9044 | 0.0250 | 0.0705 | 0.0000 | 0.0000 | 0.9044 |
| 9 | 0.80 | 0.0000 | 0.5635 | 0.0003 | 0.4362 | **0.0003** | 0.0000 | 0.5635 |
| 9 | 0.90 | 0.0000 | 0.2252 | 0.0000 | 0.7748 | **0.0000** | 0.0000 | 0.2252 |
| 17 | 0.25 | 0.0000 | 0.2347 | 0.7653 | 0.0000 | 0.0000 | **0.0000** | 0.2347 |
| 17 | 0.40 | 0.0000 | 0.7356 | 0.2639 | 0.0005 | 0.0000 | **0.0005** | 0.7356 |
| 17 | 0.60 | 0.0000 | 0.9430 | 0.0106 | 0.0464 | 0.0000 | 0.0000 | 0.9430 |
| 17 | 0.80 | 0.0000 | 0.4511 | 0.0000 | 0.5489 | **0.0000** | 0.0000 | 0.4511 |
| 17 | 0.90 | 0.0000 | 0.0826 | 0.0000 | 0.9174 | **0.0000** | 0.0000 | 0.0826 |
| 30 | 0.25 | 0.0000 | 0.0507 | 0.9493 | 0.0000 | 0.0000 | **0.0000** | 0.0507 |
| 30 | 0.40 | 0.0000 | 0.5689 | 0.4311 | 0.0000 | 0.0000 | **0.0000** | 0.5689 |
| 30 | 0.60 | 0.0000 | 0.9745 | 0.0083 | 0.0172 | 0.0000 | 0.0000 | 0.9745 |
| 30 | 0.80 | 0.0000 | 0.3930 | 0.0000 | 0.6070 | **0.0000** | 0.0000 | 0.3930 |
| 30 | 0.90 | 0.0000 | 0.0258 | 0.0000 | 0.9742 | **0.0000** | 0.0000 | 0.0258 |

`false_gap` is reported only where `theta >= theta_hi`, and `false_strength` only
where `theta <= theta_lo`; the mid-band rows (θ = 0.60) are inside the bands, so
neither verdict is "false" there by construction and both columns read 0.

Readings that matter:

1. **The error rates are small and shrink fast.** The worst false-strength rate in
   the table is `0.0256` at `k = 4, theta = 0.40` — a genuinely weak capability
   called a strength about 1 time in 39 on a four-item screen. By `k = 17` it is
   `0.0005`.
2. **The dominant outcome is refusal to decide, not error.** At `k = 4` the
   estimator declines a verdict 34–84 % of the time. That is the intended
   conservative direction, but it is also the main cost: a short screen mostly
   produces `UNCERTAIN`.
3. **`INSUFFICIENT_EVIDENCE` is 0.0000 everywhere in this table** because every
   row uses `k >= 4` undecayed `REAL_WORK` observations, which is exactly
   `min_effective_n`. It is not evidence that the floor never fires — see §5.
4. **The estimator is markedly readier to call a gap than a strength.** At
   `k = 9, theta = 0.25` it says `POSSIBLE_GAP` 60 % of the time; at
   `k = 9, theta = 0.90` it says `PROMISING_STRENGTH` 77 %. The asymmetry follows
   from `theta_hi = 0.70` being further from 0.9 than `theta_lo = 0.45` is
   from 0.25 — it is a consequence of the chosen bands, not a measured property
   of learners.

## 4. Screen length for a target error rate

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import items_for_target_error as t
for target in (0.10,0.05,0.01): print(target, t(target))"
```

```
0.1  {'k': None, ..., 'reason': 'no k in 1..60 is simultaneously safe (false rates <= 0.1) and powerful (detection >= 0.8) for competent_theta=0.85 vs weak_theta=0.4', 'best_achieved_power': 0.514515993155021, 'best_k_for_power': 56}
0.05 {'k': None, ..., 'reason': 'no k in 1..60 is simultaneously safe (false rates <= 0.05) and powerful (detection >= 0.8) ...', 'best_achieved_power': 0.514515993155021, 'best_k_for_power': 56}
0.01 {'k': None, ..., 'reason': 'no k in 1..60 is simultaneously safe (false rates <= 0.01) and powerful (detection >= 0.8) ...', 'best_achieved_power': 0.514515993155021, 'best_k_for_power': 56}
```

**MEASURED NEGATIVE RESULT.** At the module defaults (`competent_theta = 0.85`
vs `weak_theta = 0.40`, `detection_power = 0.80`, `max_k = 60`) **no admissible
screen length exists** at any of the three targets. The binding constraint is
power, not safety: the best power reached anywhere in `1..60` is `0.5145` at
`k = 56`, and it is the same for all three targets because the safety condition
is already satisfied long before power runs out.

This is reported rather than papered over. The practical readings are: a screen
built on these bands cannot both stay safe and reliably detect a `theta = 0.85`
learner against a `theta = 0.40` learner; a caller must widen the separation,
lower the power requirement, or accept that the screen does not decide.

Widening the separation and relaxing power does converge:

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import items_for_target_error as t
print(t(0.05, competent_theta=0.90, weak_theta=0.25, detection_power=0.70))"
```

```
{'k': 7, 'target_error': 0.05, 'detection_power': 0.7,
 'false_gap': 0.00017649999999999982, 'false_strength': 0.0013427734375,
 'detect_strength': 0.8503056, 'detect_gap': 0.75640869140625,
 'reason': None, 'best_achieved_power': 0.75640869140625, 'best_k_for_power': 7}
```

Measured: `k = 7` items are safe (false-gap `0.000176`, false-strength `0.001343`)
and detect at `0.850` / `0.756`. This is a *conditional* answer — it holds for
θ = 0.90 vs θ = 0.25, which is a wider true separation than the module defaults
assume, and it is not a recommendation to adopt those numbers.

## 5. Tier and recency behavior

Recency is enforced by **two** mechanisms, not one:

1. **Decay** — an exponential half-life weight, floored at `min_weight`.
2. **Freshness gate** — a verdict additionally requires at least one admissible
   `REAL_WORK` observation newer than `freshness_horizon_days`. When load-bearing
   evidence exists but none of it is inside the horizon, the result is
   `INSUFFICIENT_EVIDENCE` with `stale_only = True`.

The gate exists because decay alone did not deliver "stale evidence cannot
decide". `min_weight = 0.05` is a floor, not a cutoff, so
`N >= min_effective_n / min_weight = 80` fully decayed observations summed past
the sufficiency floor and produced a verdict from decade-old evidence. That
behavior was measured, and is now a pinned regression test rather than a
documented caveat.

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import *
from datetime import datetime, timedelta, timezone
now=datetime.now(timezone.utc)
cases=[('20 correct SCREEN',[Observation(correct=True,tier=EvidenceTier.SCREEN)]*20),
 ('20 correct ASSISTED',[Observation(correct=True,tier=EvidenceTier.ASSISTED)]*20),
 ('6 misses aged 720d',[Observation(correct=False,time=now-timedelta(days=720))]*6),
 ('6 misses fresh',[Observation(correct=False,time=now)]*6),
 ('80 misses aged 3600d',[Observation(correct=False,time=now-timedelta(days=3600))]*80),
 ('80 misses aged 3600d + 1 fresh',[Observation(correct=False,time=now-timedelta(days=3600))]*80+[Observation(correct=False,time=now)]),
 ('1 fresh pass + 79 aged 3650d',[Observation(correct=True,time=now)]+[Observation(correct=True,time=now-timedelta(days=3650))]*79)]
for name,rows in cases:
    s=summarize(rows, now=now)
    print(name, s.classification.value, round(s.load_bearing_n,4), s.stale_only, s.freshest_age_days)"
```

| Case | `load_bearing_n` | `stale_only` | `freshest_age_days` | Classification |
|---|---|---|---|---|
| 20 correct, `SCREEN` tier | 0.0000 | False | `None` | `INSUFFICIENT_EVIDENCE` |
| 20 correct, `ASSISTED` tier | 0.0000 | False | `None` | `INSUFFICIENT_EVIDENCE` |
| 6 verified misses aged 720 d | 0.3750 | **True** | 720.0 | `INSUFFICIENT_EVIDENCE` |
| 6 verified misses, fresh *(positive control)* | 6.0000 | False | 0.0 | `POSSIBLE_GAP` |
| 80 verified misses aged 3600 d | 4.0000 | **True** | 3600.0 | `INSUFFICIENT_EVIDENCE` |
| 80 aged 3600 d **+ 1 fresh** *(positive control)* | 5.0000 | False | 0.0 | `POSSIBLE_GAP` |
| 1 fresh pass + 79 passes aged 3650 d | 4.9500 | False | 0.0 | `PROMISING_STRENGTH` |

Four things these rows establish:

1. **The N = 80 case is closed at every N.** 80 verified misses aged 3600 days
   now report `INSUFFICIENT_EVIDENCE` with `stale_only = True`, despite
   `load_bearing_n = 4.0000` clearing the sufficiency floor on decayed weight
   alone. The gate, not the weight, is what withholds the verdict.
2. **Absence and staleness are different states.** The `SCREEN` and `ASSISTED`
   rows also report `INSUFFICIENT_EVIDENCE`, but with `stale_only = False` and
   `freshest_age_days = None` — there is no load-bearing evidence to be stale.
   A consumer that needs to tell "never measured" from "measured long ago" reads
   the flag, not the label.
3. **One fresh observation reopens the verdict.** The identical 80-row ancient
   pile plus a single current verified miss decides `POSSIBLE_GAP`. Supersession
   is intact: the gate controls whether a verdict may be offered, never whether
   old evidence counts.
4. **Old evidence still contributes weight.** 1 fresh pass + 79 ancient passes
   gives `load_bearing_n = 4.9500` = `1.0 + 0.05 × 79`, and decides
   `PROMISING_STRENGTH`. The fresh observation alone
   (`load_bearing_n = 1.0000`) cannot — so the decayed history did the work
   rather than riding along.

The gate can be disabled with `EvidencePolicy(freshness_horizon_days=None)`,
which restores the pre-gate behavior; `tests/test_foil_evidence.py::FreshnessGateTests`
uses that as the negative control proving the gate is what changes the verdict.

**The horizon is UNRESOLVED.** 360 days is two default half-lives. Nothing here
measures how long capability evidence stays valid, and the right horizon almost
certainly differs by domain.

## 6. SPRT cross-check

Wald's sequential probability ratio test is implemented as an independent
decision rule so that a disagreement with the Beta-posterior classifier is
visible instead of silent. **It is a diagnostic. Nothing in FOIL routes on it.**
It uses point hypotheses where the classifier uses bands, and it carries no
evidence tiers, no recency decay, and no real-work sufficiency gate.

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import sprt_log_likelihood_ratio as llr, sprt_boundaries, sprt_decision
print(sprt_boundaries(0.05,0.05))
for c,i in ((4,0),(9,0),(3,1),(7,2),(20,1),(2,7),(5,12),(1,8)):
    print(c, i, llr(c,i,0.4,0.8), sprt_decision(c,i))"
```

Parameters: `p_L = 0.4`, `p_U = 0.8`, `alpha = beta = 0.05`.
Measured boundaries: `A = +2.944439`, `B = -2.944439`.

The Beta-classifier column was measured separately with `summarize()` on the same
counts as fresh undecayed `REAL_WORK` observations:

```
$ python -c "
import sys; sys.path.insert(0,'tools')
from foil_evidence import *
for c,i in ((4,0),(9,0),(3,1),(7,2),(20,1),(2,7),(5,12),(1,8)):
    s=summarize([Observation(correct=True)]*c+[Observation(correct=False)]*i)
    print(c,i,s.classification.value,round(s.p_above_hi,6),round(s.p_below_lo,6))"
```

| correct / incorrect | Λ (log-likelihood ratio) | vs A = 2.944439 | SPRT verdict | Beta classifier verdict | `P(θ>0.70)` | `P(θ<0.45)` |
|---|---|---|---|---|---|---|
| 4 / 0 | 2.772589 | below A | `UNCERTAIN` | `PROMISING_STRENGTH` | 0.918874 | 0.008989 |
| 9 / 0 | 6.238325 | above A | `PROMISING_STRENGTH` | `PROMISING_STRENGTH` | 0.989837 | 0.000119 |
| 3 / 1 | 0.980829 | inside | `UNCERTAIN` | `UNCERTAIN` | 0.552920 | 0.114536 |
| 7 / 2 | 2.654806 | inside | `UNCERTAIN` | `UNCERTAIN` | 0.678943 | 0.022878 |
| **20 / 1** | **12.764331** | **above A** | `PROMISING_STRENGTH` | `PROMISING_STRENGTH` | 0.997999 | 0.000000 |
| 2 / 7 | -6.303992 | below B | `POSSIBLE_GAP` | `POSSIBLE_GAP` | 0.001470 | 0.918535 |
| 5 / 12 | -9.717612 | below B | `POSSIBLE_GAP` | `POSSIBLE_GAP` | 0.000269 | 0.903501 |
| 1 / 8 | -8.095751 | below B | `POSSIBLE_GAP` | `POSSIBLE_GAP` | 0.000105 | 0.984828 |

The headline cross-check is the row the old count rule got wrong: at 20 correct
and 1 incorrect, `Λ = 12.764331` exceeds `A = 2.944439` by a factor of 4.3, and
the Beta posterior independently gives `P(theta > 0.70) = 0.997999`. Two decision
rules with different machinery agree that this is a strength. The old rule called
it `UNCERTAIN`.

**One measured disagreement: `4 / 0`.** SPRT stops short (`Λ = 2.772589 < A`) while
the Beta classifier calls `PROMISING_STRENGTH` at `P(θ > 0.70) = 0.918874`. Both
rules are behaving correctly for what they are: SPRT is testing the point
hypothesis θ = 0.8 against θ = 0.4 at α = β = 0.05, which is a stricter demand
than the classifier's `confidence = 0.80` mass above a 0.70 band edge. The
disagreement is a direct measurement of how permissive `confidence = 0.80` is —
a four-for-four run clears the classifier and does not clear a 5 %-error
sequential test. That is a reason to treat `confidence` as the tunable it is
(§7.4), not a defect in either rule.

Agreement between the two is evidence about the *decision boundary* only. SPRT
has no tier, recency, or sufficiency concept, so it answers on any counts at all;
it can never corroborate the admissibility rules the classifier adds on top.

## 7. UNRESOLVED

These are open, and no number in this document closes them.

1. **Cut-points.** `theta_lo = 0.45` and `theta_hi = 0.70` are not derived from a
   calibrated item bank, a domain difficulty model, or an outcome criterion.
   Nothing here establishes that a person at θ = 0.68 should be treated
   differently from one at θ = 0.72.
2. **Freshness horizon.** Both time constants are asserted, not measured: the
   180-day half-life and the 360-day `freshness_horizon_days` gate. No study in
   this repository estimates a forgetting or drift rate for capability evidence,
   and the right horizon almost certainly differs by domain (a syntax detail
   versus a proof technique). `min_weight = 0.05` is likewise chosen. The gate
   makes the *direction* of the error safe — it refuses rather than decides —
   but a horizon set too short discards usable evidence, and nothing here says
   where the line belongs.
3. **Item exchangeability.** The Beta-Bernoulli model treats observations as
   exchangeable draws from one `theta`. Real tasks differ in difficulty, share
   content, and arrive in a correlated order, all of which violate that
   assumption. Every rate in §3 is computed *under* exchangeability and is
   therefore an upper bound on how well the estimator behaves on real streams,
   not a prediction about them.
4. **Confidence level.** `confidence = 0.80` is a decisiveness/safety tradeoff
   with no external justification.
5. **The classifier has never been validated against an outcome.** It has been
   proved monotone and its error rates under its own model are tabulated above.
   Neither is evidence that its labels predict anything about a person.

## 8. Reproducing everything here

```
$ python -m unittest tests.test_foil_evidence
```

The exhaustive monotonicity enumeration, the decay-floor boundary, and the
sufficiency-tolerance behavior are pinned there.
