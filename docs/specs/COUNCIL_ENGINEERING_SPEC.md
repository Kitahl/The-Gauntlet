# Evidence Review Panel / Council — engineering specification

## Obligation

Provide selective independent review of a concrete artifact after a strong direct pass, while measuring rather than assuming diversity/independence.

## Current workflow

Specification: 3–6 artifact-derived seats, skeptic, frozen independent first passes, disjoint evidence where feasible, reveal/cross-critique, evidence-ranked synthesis, matched direct control.

Closest executable helper currently uses generic paired red-team prompts and synthesis; it does not enforce the full Council contract.

## vNext state machine

`COMMIT -> REVEAL -> CROSS_CRITIQUE -> CLOSED`

A Council has:

- artifact hash and frozen total-budget hash;
- 3–6 distinct seat questions;
- role/method/evidence partition per seat;
- first-pass commitment hashes;
- sealed submissions;
- revealed submissions;
- provenance/evidence/method/finding overlap diagnostics;
- structured cross-critique records, with every seat contributing after reveal;
- DIRECT and optional VOTE control receipt IDs.

## vNext workflow

1. Confirm concrete artifact and existing direct analysis.
2. Derive 3–6 seats from distinct failure/verification obligations.
3. Freeze seat role/question/method/evidence partition.
4. Each seat commits first-pass submission hash before reveal.
5. Reveal only when all commits are frozen; tampered reveals fail hash verification.
6. Compute evidence/provenance/method/finding overlap.
7. Cross-critique only after reveal.
8. Require each seat to contribute a structured cross-critique against another revealed seat.
9. Synthesize by claims/evidence, preserving disagreement.
10. Compare against a DIRECT control on the same frozen artifact and matching total-budget hash; optionally compare VOTE.
11. Council's *marginal-value* claim remains UNKNOWN without same-artifact/same-budget direct-control evidence.
12. Record confidence as uncalibrated unless prospective Brier/log-score calibration exists.

## Runtime

`tools/council_runtime.py`

## Mechanical tests

- reject <3 or >6 seats;
- reject duplicate seat questions;
- double commit forbidden;
- tampered reveal rejected;
- overlap matrix correct;
- missing direct control keeps marginal-value verdict UNKNOWN.
