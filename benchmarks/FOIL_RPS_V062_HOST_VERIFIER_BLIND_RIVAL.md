# FOIL RPS v0.6.2 — host verifier and blind rival

Status: `PROPOSED / IMPLEMENTED SHADOW CONTRACT / NOT CALIBRATED / NOT PROMOTED`

This protocol supersedes v0.6.1 for new RPS experiments. It does not rewrite
the frozen v0.6.0 or v0.6.1 benchmark artifacts.

## Scope correction

RPS v0.6.2 is not an independent general reasoner. It is a bounded routing
contract:

1. the host freezes a candidate-independent check specification bound to the
   task;
2. a deterministic host verifier returns exactly one typed outcome;
3. `CONFIRMED` stands down and `CONTRADICTED` abstains in shadow mode;
4. only `NOT_APPLICABLE` or `UNCERTAIN` may request one blind rival;
5. the rival request contains the task and answer form, never the incumbent;
6. agreement is `CORRELATED_AGREEMENT`, never proof or promotion evidence;
7. disagreement is `ABSTAIN`;
8. no route mutates the frozen base answer or authorizes execution/promotion.

The check commitment proves content binding and absence of a candidate field.
It does not prove wall-clock ordering. A benchmark claiming precommitment must
persist the check commitment before the candidate receipt and include both
digests in its immutable manifest.

## Risk and cost gate

"High risk" is not inferred from answer prose, confidence, style, or model
self-report. The only rival trigger is the host-verifier outcome:

- `CONFIRMED`: no rival;
- `CONTRADICTED`: no rival, abstain;
- `NOT_APPLICABLE`: request one rival;
- `UNCERTAIN`: request one rival.

Abstention rate is a primary benchmark metric. Report it by task family and in
aggregate with its numerator and denominator.

For all new promotion decisions, the primary token denominator is:

`input_tokens + output_tokens`

Report output-only tokens separately for diagnosis. Missing input tokens make
the total-cost gate `NOT_EVALUABLE`; they never silently fall back to output
tokens. Historical v0.6.0 targets used both total- and output-token language in
different sections. v0.6.2 resolves that ambiguity prospectively rather than
editing the frozen protocol.

Initial experimental targets remain hypotheses:

- Stage A mean total-token multiplier: at most `1.50x` BASE;
- Stage A median total-token multiplier: at most `1.35x` BASE;
- eventual release target: mean total-token multiplier at most `1.10x` BASE;
- zero observed answer mutations;
- zero execution or promotion authorizations.

## Scorer contract

The hardened historical scorer is `benchmarks/harness/foil_rps_score.py`.
The v0.6.2 trace scorer is `benchmarks/harness/foil_rps_v062_score.py`; it
reports abstention and rival-trigger rates directly. Both must fail closed on:

- non-boolean correctness/validity fields;
- duplicate JSON keys or duplicate unit identities;
- negative or boolean token counts;
- missing/unknown telemetry fields;
- `P1 FAIL` without conflict, repair, and rollback binding;
- missing input tokens when evaluating a total-cost gate.

At zero observed false fires, a two-sided 95% Wilson upper bound is below 1%
only at `n >= 381`. That is a future calibration boundary, not a requirement
for this small structural pilot.

## Small matched benchmark

Freeze prompts and BASE answers before any v0.6.2 observation. Compare:

- `DIRECT`;
- v0.6.1 incumbent-conditioned shadow observer;
- v0.6.2 host-verifier-first shadow observer.

Report accuracy, rescues, damage, host coverage, rival-trigger rate, correlated
agreement, disagreement, abstention, and total-token multiplier. A small run is
only a structural/behavioral smoke test and cannot calibrate or promote a route.
