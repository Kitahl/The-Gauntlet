# FOIL RPS v0.6.2 build-order audit and active-gate amendment

Date: 2026-08-25
Status: implementation evidence, not promotion evidence

## Verdict

AMEND. The order is directionally sound, but following it literally cannot
improve an answer because items 18–21 prohibit every answer change. A benchmark
that is intended to measure score improvement needs one narrowly bounded active
path. RPS v0.6.3 therefore adds benchmark-only selection when a precommitted
deterministic host check contradicts A and confirms one unique replacement.
Production and promotion authority remain off.

Two other corrections are binding:

1. Known DIRECT misses are a diagnostic stratum, not the primary paired-accuracy
   sample. A primary efficacy estimate needs a frozen or held-out denominator.
2. `abstention above your ceiling` is not a kill condition until the ceiling is
   numeric and preregistered.

## Itemized status

| Items | Status | Evidence or correction |
|---|---|---|
| 1–2 | VERIFIED | Total-token cost is governing and the fail-closed scorer contracts pass 13/13 targeted tests. |
| 3–6 | BUILT | `foil_rps_host_verifier.py` selects before A and implements closed arithmetic, power arithmetic, JSON schema, structured unit, and ProcessBench first-error checks. Declines are never passes. |
| 7 | DEVELOPMENT GATE ONLY | On 3,400 ProcessBench rows: 0 observed false fires among 1,178 adjudicated controls and 82 genuine-error detections. The rules were developed on this corpus, so this is not fresh authority evidence. |
| 8 | WIRED | A Stage-1 decline requests a blind rival. Risk is not derived from A. |
| 9–12 | PARTIAL | Blind-rival receipt and fail-closed authority types exist. A real fresh-call executor, comparator, and full raw prompt/answer benchmark receipt have not been run. |
| 13–17 | NOT RUN AS A PROMOTION BENCHMARK | A two-question frozen-output diagnostic replay was run instead. It cannot calibrate or promote. |
| 18–19 | AMENDED | A host contradiction with a unique host-confirmed result may change only a benchmark answer. Production and promotion remain false. A non-unique contradiction abstains. |
| 20 | ENFORCED ON ACTIVE PATH | The model does not emit the decisive verdict; the host computes it. |
| 21 | AMENDED | v0.6.2 remains default-off/shadow. v0.6.3 is active only inside an explicitly enabled benchmark policy. |
| 22 | ENFORCED | Both new reports are typed as development/diagnostic only and state non-claims. |
| 23 | ENFORCED | Work is uncommitted pending review. |
| 24 | CORRECT BUT UNSATISFIED | `n >= 381` is the two-sided Wilson zero-fire threshold for an upper bound below 1%. The current evidence does not meet that per split and is not fresh. |

## Measured results

### Arithmetic alarm gate

- Rows: 3,400
- Adjudicated controls: 1,178
- Observed false fires: 0
- Genuine-error detections across the three closed rules: 82
- Provider calls and model tokens: 0
- Classification: `DEVELOPMENT_SMOKE_ONLY`

One apparent power-rule false fire, `omnimath-805`, is content-bound and
mechanically adjudicated as a corpus false-negative: the step asserts
`1404 = 2^2 * 3^2 * 13`, whose right side is 468.

### Frozen two-question active replay

Two ProcessBench questions were replayed across Terra low, Terra high, and Sol
low using already-frozen A0 outputs:

| Arm | Correct |
|---|---:|
| DIRECT A0 | 4/6 |
| Previous full pass | 5/6 |
| Host-verified active gate | 6/6 |

The active gate recorded 2 rescues, 0 damages, 2 authorized benchmark-only
mutations, 0 provider calls, 0 added tokens, and a 1.0 total-token multiplier.
Stage 1 declined on the three clean-item rows; Stage 2 was not run and A0 was
preserved. This result proves the active wiring can improve these frozen rows.
It does not estimate future accuracy.

## Remaining gates

1. Implement and freeze the true fresh-call blind-rival harness with the
   incumbent absent by construction, not asserted by a boolean.
2. Add narrow comparators: exact multiple-choice and mechanically checkable
   numeric equivalence. Unsupported semantic comparison must abstain.
3. Preregister numeric abstention and cost ceilings.
4. Run a held-out paired benchmark with DIRECT, v0.6.1, and v0.6.3.
5. Keep production answer-changing off until the Stage-B rescue/damage/cost
   gates pass on fresh evidence.

## Strongest untested assumption

The deterministic host route covers enough naturally occurring model mistakes
to matter outside the two-question diagnostic. The replay demonstrates a real
correction channel and zero damage on six frozen outputs; it does not establish
coverage, generalization, or blind-rival value.
