# Mind / Formal Reasoning — engineering specification

## Obligation

Convert mathematical or logical claims into explicit formal candidates and verify the
load-bearing proposition with claim-native derivation, exact computation, solver,
enumeration, or proof-checker receipts.

## Candidate-directed workflow

1. State the natural claim, objects, domains, assumptions, and quantifier scope.
2. Construct one explicit base `FormalizationCandidate` and preserve any plausible
   alternate formalizations supplied by the task.
3. Bind the candidate to the task, obligation, scope, and obligation-set hashes.
4. Generate native `ALTERNATE_FORMALIZATION` and `COUNTEREXAMPLE` challenges.
5. Select the weakest load-bearing hinge and at most two minimum discriminators.
6. Feature-detect and execute a claim-native verifier.
7. Store the domain receipt, then a separate `ChallengeResolution` linked to that
   receipt and the repeated binding hashes.
8. Require an explicit natural-language-to-formal scope receipt.
9. Finalize the proof bundle only when all load-bearing challenges support the base
   and the scope receipt is valid.

A challenge is never proof. A challenge resolution is never a replacement for the
Mind domain receipt.

## Runtime objects

### `FormalizationCandidate`

`candidate_id`, `obligation_id`, `natural_claim_hash`, `formal_claim`, `assumptions`,
`quantifier_map`, `representation`, `producer`, `candidate_hash`, and typed metadata.
The candidate hash covers the formal claim, assumptions, quantifiers,
representation, producer, obligation, and natural-claim hash.

### `ProofChallengeBundle`

`bundle_id`, `obligation_id`, base/alternate candidate IDs, challenge IDs, selected
plan IDs, task ID, candidate/scope/obligation-set hashes, and the separate
natural-scope receipt ID.

## Initial verifier adapters

- restricted exact arithmetic using Python AST and `Fraction`;
- built-in exact polynomial normalization, including the bounded relation
  `sin(x)^2 + cos(x)^2 = 1`;
- optional feature-detected SymPy subprocess for expressions outside the built-in
  fragment, with a hard timeout and restricted syntax;
- complete bounded finite-domain enumeration with predicate-code, domain, result,
  and witness hashes;
- existing Z3 SMT2 execution with expected solver-status and negation binding;
- explicit counterexample validation through a callable code hash;
- future Lean/Coq proof-artifact adapters only after real implementation.

A complete finite-domain proof and an exact symbolic normalization may emit
`PROVEN` for their declared formal scope. A numerical experiment or model-only review
must not emit `PROVEN`. A model-proposed witness without a claim-native validator is
`HEURISTIC/UNKNOWN`.

## Release rule

| Condition | Mind result |
|---|---|
| No formal encoding or binding hashes | `UNKNOWN` |
| Plausible formalizations differ and no discriminator resolves them | `UNKNOWN` |
| Mandatory selected verifier is absent | `UNAVAILABLE` |
| Exact check or verified counterexample refutes the base | `ISSUE` |
| Formal checks support the base but natural/formal scope is unverified | `UNKNOWN` for the natural claim |
| Every load-bearing challenge supports the base and the scope receipt is bound | `CLEARED` for the stated scope |

The module remains additive and SHADOW by default. Existing `ProofObligation`, exact
arithmetic, and Z3 entry points remain available.

## Files

- `tools/egrt_challenge_types.py`
- `tools/egrt_challenge.py`
- `tools/egrt_candidate_gate.py`
- `tools/mind_runtime.py`
- `tests/test_egrt_challenge_*.py`
- `tests/test_candidate_gate.py`
- `tests/test_mind_challenge_runtime.py`
- `tests/test_no_nonfoil_imports_foil_modules.py`

## Mechanical acceptance

- content hashes detect tampering;
- duplicate IDs, invalid transitions, and binding mismatches are rejected;
- shadow mode records but does not block;
- enforced unresolved, unavailable, and refuted states remain distinct;
- exact polynomial/trigonometric equivalence is deterministic;
- a finite-domain counterexample refutes a universal candidate;
- model-only evidence cannot become `PROVEN`;
- competing formalizations block finalization until resolved;
- natural/formal scope remains a separate receipt;
- legacy FOIL candidate-gate imports and existing exact arithmetic/Z3 behavior remain
  compatible.
