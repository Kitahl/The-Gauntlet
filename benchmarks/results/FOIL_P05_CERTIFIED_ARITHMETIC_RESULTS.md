# FOIL P0.5 — Certified arithmetic on ProcessBench

**Classification:** `PROCESSBENCH_P05_DETERMINISTIC_ARITHMETIC_SMOKE`
**Admission:** `NOT_ADMITTED_PER_SUBSET_CERTIFICATE`
**Final language:** `certified-v2`

## Baseline audit

The original `latex_eq.py` and `p0_processbench.py` named by the brief were absent
from the checkout and reachable history. The rebuilt audit-compatible extractor
found **21** false-fire rows, not the brief's 27;
therefore the 27-row baseline is not claimed as reproduced.

| Failure mode | Rows | Example |
|---|---:|---|
| `CORPUS_LABEL_FALSE_NEGATIVE_GENUINE_ERROR` | 2 | `olympiadbench-529`: `\[ P(5, 3) = \frac{5!}{(5-3)!} = \frac{5!}{2!} = \frac{5 \times 4 \times 3}{2 \times 1} = 60 \]` |
| `CURRENCY_PROSE_CONTEXT_DROPPED` | 1 | `olympiadbench-987`: `$\$1.50 = 0.10 \times \$1.50 = \$0.15$` |
| `CURRENCY_SPAN_CROSSED_DELIMITER` | 1 | `gsm8k-368`: `$80 = \frac{25}{100} \times \$80 = \$20\). So, the discounted rate per lesson = $` |
| `DECIMAL_APPROXIMATION` | 5 | `math-883`: `\[ x^2 = (2.8284)^2 = 8 \]` |
| `EXPLICIT_COUNTEREXAMPLE_OR_REJECTED_TRIAL` | 2 | `olympiadbench-783`: `\[ 2 + 1 = 1 \]` |
| `INTEGER_QUOTIENT_WITH_REMAINDER` | 1 | `olympiadbench-892`: `\(49 \div 9 = 5\)` |
| `PERCENT_DIMENSION_COLLAPSE` | 3 | `gsm8k-278`: `\[ \left( \frac{2}{4} \right) \times 100 = 50\% \]` |
| `SYMBOLIC_CHAIN_FRAGMENT` | 2 | `gsm8k-292`: `\[ \text{Alyana's Age} = \text{Chenny's Age} - 4 = 10 - 4 = 6 \]` |
| `UNIT_CONVERSION_AS_EQUAL_MAGNITUDE` | 4 | `gsm8k-375`: `\[2 \text{ dozen} = 2 \times 12 = 24 \text{ cups}\]` |

The complete per-row dump (source span, extracted sides, exact values, and step context)
is in the JSON report and the separate audit artifact.

## Final per-subset results

| Subset | Applicability | α (Wilson 95%) | Recall | Lift | Localisation | Certificate |
|---|---:|---:|---:|---:|---:|---|
| gsm8k | 25.50% (102/400) | 0.00% [0.00%, 1.95%] | 0.48% (1/207) | INFINITE_ZERO_FALSE_FIRE | 1/0/0 (underpowered) | `INSUFFICIENT_CLEAN_NEGATIVES` |
| math | 23.30% (233/1000) | 0.00% [0.00%, 0.94%] | 2.36% (14/594) | INFINITE_ZERO_FALSE_FIRE | 7/0/7 (underpowered) | `ADMIT` |
| olympiadbench | 19.90% (199/1000) | 0.00% [0.00%, 1.12%] | 2.87% (19/661) | INFINITE_ZERO_FALSE_FIRE | 4/0/15 (underpowered) | `REJECT_WILSON_UPPER_ABOVE_1_PERCENT` |
| omnimath | 22.10% (221/1000) | 0.00% [0.00%, 1.57%] | 2.90% (22/759) | INFINITE_ZERO_FALSE_FIRE | 6/2/14 (underpowered) | `INSUFFICIENT_CLEAN_NEGATIVES` |

Localisation is `exact / earlier / later` for the earliest violating equality.
Every split has fewer than 30 detected error rows, so localisation is underpowered.

## Coverage cost of cumulative narrowing

| Stage | Subset | Applicable | False fires | Detected errors |
|---|---|---:|---:|---:|
| `audit-legacy-v0` | gsm8k | 206 (51.50%) | 7 | 12 (5.80%) |
| `audit-legacy-v0` | math | 525 (52.50%) | 3 | 58 (9.76%) |
| `audit-legacy-v0` | olympiadbench | 528 (52.80%) | 7 | 53 (8.02%) |
| `audit-legacy-v0` | omnimath | 465 (46.50%) | 4 | 65 (8.56%) |
| `certified-v1` | gsm8k | 103 (25.75%) | 0 | 2 (0.97%) |
| `certified-v1` | math | 305 (30.50%) | 0 | 35 (5.89%) |
| `certified-v1` | olympiadbench | 291 (29.10%) | 4 | 29 (4.39%) |
| `certified-v1` | omnimath | 285 (28.50%) | 4 | 38 (5.01%) |
| `certified-v1-assertive` | gsm8k | 103 (25.75%) | 0 | 1 (0.48%) |
| `certified-v1-assertive` | math | 285 (28.50%) | 0 | 28 (4.71%) |
| `certified-v1-assertive` | olympiadbench | 277 (27.70%) | 0 | 26 (3.93%) |
| `certified-v1-assertive` | omnimath | 273 (27.30%) | 2 | 31 (4.08%) |
| `certified-v1-division-safe` | gsm8k | 103 (25.75%) | 0 | 1 (0.48%) |
| `certified-v1-division-safe` | math | 285 (28.50%) | 0 | 27 (4.55%) |
| `certified-v1-division-safe` | olympiadbench | 277 (27.70%) | 0 | 24 (3.63%) |
| `certified-v1-division-safe` | omnimath | 273 (27.30%) | 1 | 29 (3.82%) |
| `certified-v2` | gsm8k | 102 (25.50%) | 0 | 1 (0.48%) |
| `certified-v2` | math | 233 (23.30%) | 0 | 14 (2.36%) |
| `certified-v2` | olympiadbench | 199 (19.90%) | 0 | 19 (2.87%) |
| `certified-v2` | omnimath | 221 (22.10%) | 0 | 22 (2.90%) |

## Generator stratification

| Generator | B | clean/error | Applicability | α | Recall | Lift | Included? |
|---|---:|---:|---:|---:|---:|---:|---|
| Llama-3.1-70B-Instruct | 70 | 79/195 | 13.87% | 0.00% | 3.59% | INFINITE_ZERO_FALSE_FIRE | yes |
| Llama-3.1-8B-Instruct | 8 | 155/371 | 11.41% | 0.00% | 1.08% | INFINITE_ZERO_FALSE_FIRE | yes |
| Meta-Llama-3-70B-Instruct | 70 | 64/108 | 15.12% | 0.00% | 3.70% | INFINITE_ZERO_FALSE_FIRE | yes |
| Meta-Llama-3-8B-Instruct | 8 | 27/67 | 9.57% | 0.00% | 1.49% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2-1.5B-Instruct | 1.5 | 15/73 | 30.68% | 0.00% | 1.37% | INFINITE_ZERO_FALSE_FIRE | no |
| Qwen2-72B-Instruct | 72 | 135/200 | 26.57% | 0.00% | 2.50% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2-7B-Instruct | 7 | 143/279 | 24.17% | 0.00% | 3.23% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2.5-1.5B-Instruct | 1.5 | 53/63 | 38.79% | 0.00% | 1.59% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2.5-72B-Instruct | 72 | 97/157 | 28.74% | 0.00% | 2.55% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2.5-7B-Instruct | 7 | 116/235 | 27.64% | 0.00% | 2.98% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2.5-Math-72B-Instruct | 72 | 155/216 | 26.42% | 0.00% | 2.31% | INFINITE_ZERO_FALSE_FIRE | yes |
| Qwen2.5-Math-7B-Instruct | 7 | 140/257 | 22.92% | 0.00% | 3.11% | INFINITE_ZERO_FALSE_FIRE | yes |

Spearman association with log parameter size:

- applicability: ρ=-0.0558, p=0.8705, n=11 (Student-t approximation with n-2 degrees of freedom).
- alpha: `NOT_IDENTIFIABLE` — correlation is undefined for a constant vector.
- recall: ρ=0.0279, p=0.9351, n=11 (Student-t approximation with n-2 degrees of freedom).
- lift: `NOT_IDENTIFIABLE` — ZERO_ALPHA_MAKES_LIFT_NONFINITE.

Excluded generators:
- Qwen2-1.5B-Instruct: clean<20.

## Verdict

The point estimate is zero false fires on all four subsets, but the rule is **not admissible**: the maximum Wilson two-sided 95% upper bound is 1.95% and the maximum one-sided exact 95% upper bound is 1.54%. GSM8K and OmniMath have fewer than 299 clean negatives. OlympiadBench clears 299
but its two-sided Wilson upper bound is still above 1%; the brief's 299-case rule is
sufficient for its one-sided exact formula, not for its separately stated two-sided Wilson bar.
No subsets were pooled.

This is deterministic historical/open-model smoke evidence only. It spent zero model tokens
and granted no answer, execution, or promotion authority.

Report SHA-256: `443006095044143a9028ceeb272cd1b5a37719167b6f9a2a47968c5af7b193f2`
