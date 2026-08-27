---
name: mathbot
description: Formal Reasoning module. Trigger: /mind, /mathbot, formal proof, logical validity, probability/statistics derivation, optimization, counterexample, or formalization requests. Converts claims into explicit objects and proof obligations, then verifies with derivation, computation, solver, or source as appropriate.
---

# Formal Reasoning

Use this module when the load-bearing obligation is mathematical or logical
correctness.

## Core method

1. State objects, domains, variables, quantifiers, and assumptions.
2. State the exact natural claim, formal encoding, and negation.
3. Preserve plausible alternate formalizations when scope or quantifiers are
   ambiguous.
4. Bind the candidate to the task, obligation, scope, and obligation-set hashes.
5. Create a load-bearing alternate-formalization or counterexample challenge when
   applicable.
6. Select the minimum claim-native discriminator, not a generic second review.
7. Execute the verifier and store its domain receipt.
8. Resolve the challenge only through that linked receipt.
9. Verify natural-language-to-formal scope separately and report the exact boundary.

At most two load-bearing discriminators are selected for one obligation by default.
An unavailable mandatory solver/prover is `UNAVAILABLE`, not permission to silently
replace it with model reasoning.

## Verification hierarchy

- exact derivation, proof checker, solver, complete finite enumeration, or supported
  exact symbolic normalization → `PROVEN` within the declared formal scope;
- bounded numerical computation → `MEASURED`;
- fetched theorem/source that entails the proposition → `CITED`;
- inference from already supported premises → `DERIVED`;
- model-only witness or review → `HEURISTIC` and unresolved.

A solver result proves only the encoding it checked. A numerical experiment does not
prove a universal theorem. Agreement between repeated model passes is not independent
evidence.

## Logic validity

Restate as `premises ⊢ conclusion`.

- propositional/FOL: test satisfiability of `premises ∧ ¬conclusion` when a solver is
  available;
- finite universal claims: use complete declared-domain enumeration where feasible;
- probabilistic: expose conditioning, base rates, and independence assumptions;
- causal: define intervention/estimand and identify confounding/mediation assumptions;
- temporal/modal: preserve operator scope;
- informal arguments: quote the exact inference rather than relying on a fallacy
  label alone.

## Negative results

An impossibility or kill requires one of:

- a verified theorem with matching scope;
- a verified explicit counterexample;
- a demonstrated contradiction or degeneracy;
- a lower bound or hardness result under stated assumptions.

When killing an approach, give the nearest viable alternative and its cost.

## Tools

Use available Python/symbolic solvers/provers/SMT/ITP systems only after feature
detection. Never reference machine-specific paths. For external theorem status or
prior art, route to Research Discovery.

## Typed runtime contract

`tools/mind_runtime.py` implements `FormalizationCandidate`, native proof challenges,
minimum-discriminator selection, exact symbolic equivalence, finite enumeration,
counterexample receipts, explicit natural/formal scope receipts, and
`finalize_proof_bundle()`.

The neutral contracts live in `tools/egrt_challenge_types.py` and
`tools/egrt_challenge.py`. Mind does not import FOIL. Challenge state is additive and
SHADOW by default. See `docs/specs/CHALLENGE_ENGINEERING_SPEC.md` and
`docs/specs/MIND_ENGINEERING_SPEC.md`.
