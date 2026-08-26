# FOIL RPS v0.6.1 — small hinge-gate benchmark

Date: 2026-08-25

Status: preregistered tiny shadow smoke; no calibration or promotion authority.

## Question

Does the v0.6.1 decisive-hinge gate prevent the v0.6.0 failure mode in which a
generic check passed but did not distinguish a wrong candidate from a plausible
challenger?

## Benchmark A: deterministic gate conformance

Run six fixed state-machine cases:

1. non-discriminating pass -> `RUN_P2`;
2. decisive pass -> `FAST_ACCEPT`;
3. decisive failure -> `LOCAL_REPAIR`;
4. pass on the wrong hinge -> `RUN_P2`;
5. supporting P1 plus orthogonal decisive P2 -> `FAST_ACCEPT`;
6. repeated check kind at P2 -> `ABSTAIN`.

This establishes control-law conformance only, not model efficacy.

## Benchmark B: HLE hard-two shadow replay

- Reuse the two frozen HLE-Verified Gold questions from RPS v0.6.0.
- Reuse the exact four frozen `BASE` candidates: Terra Low and Terra High on
  both questions. Do not make new BASE calls.
- Make one observation-only RPS call per frozen candidate: four calls total.
- Make one positive-control call per configuration: two calls total.
- Hard cap: six provider calls. No retries after a raw attempt exists.
- The observer receives question text and the frozen candidate only. It never
  receives gold, correctness, the old RPS output, or scorer labels.
- The observer emits one to three compact hinge identifiers, a fragile-hinge
  index, a challenger label, and typed P1/P2 observations. Expected and observed
  values use only `HOLDS` or `FAILS`, avoiding free-text equality comparisons.
- The host hashes those values and runs the committed v0.6.1 controller through
  `RuntimePolicyV2.observe_residual_parity`.
- The host always preserves the frozen BASE answer.
- Predictions and public receipts must be committed with a clean worktree before
  the scorer opens the frozen v0.6.0 result file containing gold.

## Primary counts

- wrong BASE candidates receiving unsafe `FAST_ACCEPT`;
- wrong BASE candidates not fast-accepted;
- correct BASE candidates receiving `FAST_ACCEPT`;
- correct BASE candidates receiving false `LOCAL_REPAIR`;
- `RUN_P2` / `ABSTAIN` counts;
- observer token overhead relative to the frozen BASE call.

No inferential statistics are reported at n=4. A zero count is an observed count,
not a population bound.

## Non-claims

The run is not calibration, promotion evidence, a safety bound, HLE population
efficacy, frontier-model recall, proof that the model selected the right hinge,
proof that its predicted check outcomes were faithful, or evidence that the
production token target is met.
