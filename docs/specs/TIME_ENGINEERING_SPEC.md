# Caliper / Time — Evaluation and Benchmarking System specification

## Obligation

Design and execute comparisons that distinguish mechanism gain from model/tool/data/compute changes and retain uncertainty, exclusions and negative results.

## Current workflow

Project benchmark harnesses already freeze items/protocols and preserve scoped receipts, but there is no single reusable statistical runtime.

## vNext state

Analysis plan + exclusions/contamination ledger + paired observations + analysis receipt.

## Initial vNext workflow

1. Freeze construct, primary endpoint and comparison unit.
2. Freeze model/tool/data/compute budget and item-addressed exclusions.
3. Preserve item pairing where causal comparison needs it.
4. For paired binary outcomes compute full discordance table.
5. Use exact conditional McNemar p-value and Wilson accuracy intervals in the stdlib baseline implementation.
6. Apply a preregistered multiplicity rule (Holm helper available) when multiple claims form a family.
7. If results will be repeatedly monitored/adaptively stopped, fixed-n inference is insufficient: require an anytime-valid confidence-sequence/e-process implementation and mark it UNAVAILABLE until installed/validated.
8. Preserve contamination/exclusion events as first-class data. A contaminated item without an explicit frozen exclusion is an error; vector-only APIs cannot silently apply exclusions.
9. Do not combine heterogeneous benchmarks into one headline accuracy without a preregistered construct/weighting rule.

## Runtime

`tools/time_runtime.py`

## Mechanical tests

- known McNemar cases;
- zero discordance gives p=1;
- Wilson bounds in [0,1];
- vector length mismatch rejected;
- Holm monotonic step-down behavior;
- sequential inference absence explicitly unresolved.
