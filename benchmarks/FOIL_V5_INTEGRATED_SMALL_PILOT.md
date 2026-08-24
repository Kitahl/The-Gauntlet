# FOIL v5 Integrated Small Pilot

Status: **preregistered synthetic integration check; not yet run**

## Purpose

This deliberately small pilot checks the completed v5 wiring without model,
network, tool-provider, token, candidate-generation, or answer-mutation cost. It
does not estimate real-claim coverage, formalization fidelity, repair benefit,
human complementarity, or production efficacy.

## Frozen cases

1. A host-declared failing deterministic predicate yields `DEFECT/FULL`, keeps
   the exact A0 object, and records one observational RouteVector row.
2. A passing predicate yields `CLEARED/DIRECT` and keeps the exact A0 object.
3. A generated obligation with a complete synthetic admission receipt is routed
   while its `ADMITTED_GENERATED` origin remains visible.
4. A generated obligation with an incomplete mutation suite stands down before
   compilation.
5. Complete development-only gate evidence may report `PASS` but cannot promote.
6. A complete development-only RQ-26 study topology remains non-promoting.

All six cases must pass. Any mismatch exits nonzero.

## Fixed boundaries

- The three formalization rows are synthetic development fixtures, not audited
  human labels and not a calibrated production route.
- Gate and study development rows are structural smoke evidence only.
- No result from this pilot may advance Gate 1B, 1C, 2, 3, profile P0, RQ-26,
  model-ladder, history-policy, or human-complement promotion state.
- External empirical evaluation remains separately preregistered and unrun.

## Command

Run only after this protocol and its harness are committed:

```powershell
python benchmarks/harness/foil_v5_integrated_small_pilot.py `
  --output benchmark_runs/2026-08-24/integrated_small_pilot/report.json
```
