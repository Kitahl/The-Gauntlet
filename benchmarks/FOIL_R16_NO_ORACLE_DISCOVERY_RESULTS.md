# FOIL R1.6 no-oracle discovery pilot — results

Status: **COMPLETE; FAIL / NO PROMOTION**

- Protocol commit: `0ad3e3ec47f96d44e7ea8bb8acec90049192efd1`.
- Frozen-label commit: `e6290a922f7814c79f727138fdaf3b8a9229bee6`.
- Report SHA-256:
  `312ddf961c808ec11779b981a7f6a7d34b67987c9e88170d7ebc0ea252a40c52`.
- Classification: `HISTORICAL_MODEL_NO_ORACLE_SMOKE`.
- Association status: `ESTIMABLE_SMOKE_ONLY`.

The experiment was estimable, but it did not support mutation kill rate as a
predictor of natural-miss detection. Spearman was `-0.20`; its exact two-sided
permutation p-value over six common classes was `1.0`. Descriptive Pearson was
also `-0.20`.

More importantly, the route falsely fired on 7 of 14 correct controls: 50%, with
a named two-sided Wilson 95% interval of 26.8%–73.2%. This is disqualifying even
though 10 of 11 selected historical natural misses were detected. R1.6 therefore
creates no calibration, admission, promotion, frontier-recall, or efficacy claim.

## Per-class results

| Class | Mutants detected | Wilson 95% | Natural misses detected | Wilson 95% |
|---|---:|---:|---:|---:|
| `RESULT` | 8/8 | 67.6%–100% | 1/1 | 20.7%–100% |
| `FINAL` | 8/8 | 67.6%–100% | 0/0 | not estimable |
| `OPERAND` | 8/8 | 67.6%–100% | 1/2 | 9.5%–90.5% |
| `DROPSTEP` | 8/8 | 67.6%–100% | 2/2 | 34.2%–100% |
| `SWAPOP` | 8/8 | 67.6%–100% | 2/2 | 34.2%–100% |
| `CONSISTENT_LOCAL` | 7/8 | 52.9%–97.8% | 2/2 | 34.2%–100% |
| `CONSISTENT_GLOBAL` | 8/8 | 67.6%–100% | 2/2 | 34.2%–100% |

All 56 planned mutants executed. Global and per-operator conservation passed;
there were no equivalent, invalid, or unsupported selected attempts. The source
digest, required positive controls, A0 preservation, closed raw-row schemas, and
report rederivation all passed.

## False-fire diagnosis

Every correct-control false fire came from `builtin.numeric_provenance`, not
exact arithmetic or final-result consistency. The literal-membership model is
too strict for ordinary valid derivations. It rejects, among other cases:

- values derived in prose without their own `<<...>>` annotation;
- `20%` in the question versus `.20` in an expression;
- a fraction such as `1/4` when AST traversal exposes literal `1` and `4`;
- implicit unit counts such as multiplying one ream by price; and
- correctly derived intermediate constants not present verbatim in the prompt.

This also explains why semantically consistent mutants were frequently killed:
the provenance predicate is acting as a brittle lexical-origin alarm rather than
a sound dependency proof. High mutant kill rate is therefore not evidence of
useful semantic detection.

## Boundary and next action

The route remains default off and `GENERATED_UNADMITTED`. It made zero provider,
external-bot, or runtime-model calls; spent zero tokens; mutated no answer; wrote
no profile; authorized no action; and changed no promotion state.

Any successor must replace literal-membership provenance with an explicit typed
dependency graph that represents conversions, percentages, fractions, implicit
unit constants, and unannotated derived quantities. That would be a new frozen
route/version and a new preregistered pilot; these R1.6 rows and outcomes must not
be used to tune and then rescore R1.6 as if they were held out.
