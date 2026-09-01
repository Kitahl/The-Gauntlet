---
name: mathbot
description: >-
  Axiom — BASTION-01's Formal Reasoning Engine. Trigger: /mind, /mathbot,
  formal proof, logical validity, probability/statistics derivation,
  optimization, counterexample, or formalization requests. Converts claims into
  explicit objects and proof obligations, then verifies with derivation,
  computation, solver, or source as appropriate.
---

# Axiom — Formal Reasoning Engine

Use this module when the load-bearing obligation is mathematical or logical correctness.

## Core method

1. State objects, domains, variables, quantifiers, and assumptions.
2. State the exact claim and its negation.
3. Classify the reasoning domain: deductive, probabilistic, causal, optimization, complexity, numerical, or mixed.
4. Choose a claim-native verifier.
5. Search for counterexamples and edge cases before accepting the proof.
6. Report scope precisely.

## Verification hierarchy

- exact derivation / proof checker / solver → `PROVEN`
- executed enumeration or numerical computation → `MEASURED`
- fetched theorem/source that entails the proposition → `CITED`
- inference from already supported premises → `DERIVED`
- anything else remains unresolved.

A solver result proves only the encoding it actually checked. A numerical experiment does not prove a universal theorem.

## Logic validity

Restate as `premises ⊢ conclusion`.

- propositional/FOL: test satisfiability of `premises ∧ ¬conclusion` when a solver is available;
- probabilistic: expose conditioning, base rates, and independence assumptions;
- causal: define intervention/estimand and identify confounding/mediation assumptions;
- temporal/modal: preserve operator scope;
- informal arguments: quote the exact inference rather than relying on a fallacy label alone.

## Negative results

An impossibility/kill requires one of:

- a verified theorem with matching scope;
- an explicit counterexample;
- a demonstrated contradiction/degeneracy;
- a lower bound/hardness result under stated assumptions.

When killing an approach, give the nearest viable alternative and its cost.

## Tools

Use available Python/symbolic solvers/provers/SMT/ITP systems only after feature detection. Never reference machine-specific paths. For external theorem status or prior art, route to Research Discovery.

## Typed runtime contract

`tools/mind_runtime.py` records explicit proof obligations and verifier receipts. Initial adapters provide restricted exact arithmetic and optional Z3 SMT2 execution; missing solvers are `UNAVAILABLE`. Solver/proof receipts apply to the supplied formal encoding, not automatically to unstated natural-language scope. See `docs/specs/MIND_ENGINEERING_SPEC.md`.
