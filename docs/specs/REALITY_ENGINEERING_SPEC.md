# Foundry / Reality — Method Synthesis Engine specification

## Obligation

Generate genuinely distinct candidate mechanisms only after verified prior art leaves a named constraint/gap; produce candidates that are sufficiently explicit to falsify.

## Current workflow

Strong specification, little dedicated runtime state.

## vNext candidate object

Must contain gap, failed constraint, changed assumption, mechanism, nearest prior art, actual delta, inputs, outputs, invariants, dependencies, failure modes, negative control, transfer target, ablation plan and verifier plan.

## vNext workflow

1. Require a Space prior-art obligation/receipt.
2. Write the failed constraint/gap.
3. Generate candidates that change different assumptions/mechanisms, not just wording.
4. Persist each as `MethodCandidate`.
5. Run admission checks.
6. Compare candidates for changed-assumption/mechanism/tag overlap.
7. Candidate admission means **testable**, not novel or effective.
8. Novelty remains UNKNOWN until search scope supports the claimed delta.
9. Promotion requires later negative control, transfer, ablation and regression receipts.

## Runtime

`tools/reality_runtime.py`

## Mechanical tests

- no prior-art receipt -> UNKNOWN;
- missing negative control/ablation/verifier -> UNKNOWN;
- complete candidate + cleared Space receipt -> admitted for testing;
- diversity diagnostics identify same mechanism/assumption.
