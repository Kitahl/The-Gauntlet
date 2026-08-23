# Mind / Formal Reasoning — engineering specification

## Obligation

Convert mathematical/logical claims into explicit formal obligations and verify them with a claim-native derivation, computation, solver or proof checker.

## Current workflow

Specification requires objects/domains/quantifiers/assumptions, exact claim and negation, domain classification, native verifier, counterexample search and scoped reporting.

## vNext state

`ProofObligation(natural_claim, formal_claim, assumptions, domain, encoding_artifact, metadata)`.

## vNext workflow

1. State natural claim and assumptions.
2. Construct explicit formal encoding.
3. Hash encoding and link it to obligation.
4. Select verifier by domain.
5. Feature-detect the verifier; missing tool -> UNAVAILABLE.
6. Execute.
7. Preserve proof/counterexample as an artifact when applicable; generic receipt stores artifact/output hash.
8. Report solver/proof result only for the supplied encoding.
9. If English->formal entailment is load-bearing, represent that as a separate obligation rather than assuming it.

## Initial adapters

- exact arithmetic via restricted Python AST + `Fraction`;
- Z3 SMT2 when `z3` exists;
- later Lean/Coq adapters with machine-checkable proof artifact receipts.

## Runtime

`tools/mind_runtime.py`

## Mechanical tests

- unsupported AST rejected;
- arithmetic exactness for fractions;
- missing Z3 -> UNAVAILABLE;
- solver output scope explicitly limited to encoding.
