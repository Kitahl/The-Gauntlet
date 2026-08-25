# FOIL RPS v0.6.0 — HLE-Verified Gold hard-two challenge

Classification: **HLE_VERIFIED_GOLD_HARD_TWO_CHALLENGE**

| Slice | BASE | RPS | Rescue | Damage | Conflict | Output × | Total × |
|---|---:|---:|---:|---:|---:|---:|---:|
| TERRA_LOW | 0/2 | 0/2 | 0 | 0 | 0 | 0.488 | 1.326 |
| TERRA_HIGH | 2/2 | 0/2 | 0 | 2 | 0 | 0.995 | 1.302 |
| HLE_VERIFIED_GOLD_TEXT | 2/4 | 0/4 | 0 | 2 | 0 | 0.842 | 1.313 |
| OVERALL | 2/4 | 0/4 | 0 | 2 | 0 | 0.842 | 1.313 |

Trace-integrity failures: **0**.

## Gold-key audit

The score table above is keyed to the pinned corpus's answer field. A
post-score audit found an important split:

- hle-verified-673668e658bad7ba89d4ad54 (array transformations): the
  pinned row marks problem, answer, and rationale valid. An independent
  simulator executed all six public choices and found **E** to be the unique
  exact match (zero visible-cell and zero hidden-cell mismatches). On this
  independently checkable item, Terra High was **BASE 1/1, RPS 0/1**; Terra
  Low was **BASE 0/1, RPS 0/1**.
- hle-verified-6725a933e10373a976b7e2a2 (neural-network code): the
  pinned row marks the answer valid but the rationale invalid (**S3**,
  empirical-soundness violation). Its verifier says the rationale's claimed
  stable >90% behavior for option A lacks support and does not match the code's
  actual behavior. The item remains in the frozen run—there was no
  post-outcome replacement—but its A key is reported only as a **source key**,
  not as independently established ground truth.

This qualification weakens the aggregate source-keyed score; it does not
remove the independently verified array-item damage.

The conflict/repair fields are model self-reports and are compared with an independent BASE run; they are not causal observations of RPS's private provisional answer.
Two questions cannot calibrate, promote, establish safety, or estimate HLE population efficacy.
