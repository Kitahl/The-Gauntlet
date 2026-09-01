# BASTION-01 Research Statement

## Project

**BASTION-01** is Rookframe Research's first open-source product line: a modular research-software system for structuring AI-assisted work around explicit epistemic obligations—formal reasoning, prior-art search, implementation, evaluation, process assurance, and adaptive complementary assistance. Rookframe Research is a working identity for a planned company, not a claim of incorporation.

## Research question

The current research question is:

> Can an evidence-governed modular reasoning workflow improve the traceability, verification discipline, and independent usefulness of AI-assisted research without confusing model agreement, stylistic confidence, or passing software checks with scientific validity?

This repository currently implements the **research architecture and its mechanical/specification checks**. It does not yet establish a positive answer to the full behavioral question.

## Method

The system separates work by the type of evidence needed rather than by topic alone:

- **Crown — Orchestration Core** — decomposes tasks into obligations and integrates results.
- **Axiom — Formal Reasoning Engine** — proofs, counterexamples, probability/statistics, and formalization.
- **Farfield — Research Discovery Array** — literature, prior art, existing software, and terminology transfer.
- **Foundry — Method Synthesis Engine** — new mechanisms only after existing methods fail a named constraint.
- **Proofrig — Engineering Verification System** — implementation, execution, integration, tests, and software verification.
- **Caliper — Evaluation and Benchmarking System** — capability measurement, baselines, ceilings, cost, and stop/go decisions.
- **Aegis — Process Assurance Layer** — audits frames, inherited assumptions, stale state, false-green verification, and repeated failure patterns.
- **Stillpoint — Decision Preflight Protocol** — grounding before consequential dispatch or after failure.
- **Conclave — Evidence Review System** — selective multi-perspective review with evidence and control comparisons.
- **Counterform — Adaptive Reasoning Complement** — models uncertain user/task gaps and supplies the missing method while separating assisted performance from independent competence.

Technical IDs and command aliases are retained for compatibility; public documentation uses the professional display names above.

## Current evidence

Existing repository evidence supports narrower claims:

- public source/package invariants for Crown and Aegis;
- structural/source/regression checks for the FOIL specification;
- explicit separation of specification validation from behavioral efficacy;
- provenance mapping from public-facing claims to source artifacts.

See `validation/`, `research/FOIL_RESEARCH_BASIS.md`, and `REPRODUCIBILITY.md`.

## Planned evaluation

The planned behavioral study compares:

1. strong direct AI assistance;
2. static evidence/scaffolding rules;
3. adaptive Counterform (technical ID: FOIL) plus modular routing;
4. low/no-AI learning control where feasible.

Primary endpoint: **delayed independent transfer with relevant AI assistance unavailable**.

Secondary endpoints include immediate task quality, error detection, calibration, near/far transfer, retention, completion time, tool/compute cost, false blockers, and missed verification obligations.

## Baselines and ablations

Required comparisons include:

- Crown-orchestrated workflow vs strong direct model;
- Counterform/FOIL learner-state adaptation vs fixed scaffolding;
- evidence-native verifier vs same-model self-critique;
- Conclave vs matched-evidence direct control;
- each promoted mechanism with and without the mechanism where practical.

## Research integrity boundary

A software test, citation, multi-agent consensus, or benchmark score is never promoted beyond the property it actually observes. Negative results and failed mechanisms are valid outputs and should be retained when they change the credible search space.
