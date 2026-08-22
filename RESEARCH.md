# Research Statement

## Project

**Evidence-Governed Research Toolkit (EGRT)** is a modular research-software system for structuring AI-assisted research work around explicit epistemic obligations: formal reasoning, prior-art search, implementation, evaluation, process assurance, and adaptive complementary assistance.

## Research question

The current research question is:

> Can an evidence-governed modular reasoning workflow improve the traceability, verification discipline, and independent usefulness of AI-assisted research without confusing model agreement, stylistic confidence, or passing software checks with scientific validity?

This repository currently implements the **research architecture and its mechanical/specification checks**. It does not yet establish a positive answer to the full behavioral question.

## Method

The system separates work by the type of evidence needed rather than by topic alone:

- **Research Orchestrator** — decomposes tasks into obligations and integrates results.
- **Formal Reasoning** — proofs, counterexamples, probability/statistics, and formalization.
- **Research Discovery** — literature, prior art, existing software, and terminology transfer.
- **Method Synthesis** — new mechanisms only after existing methods fail a named constraint.
- **Engineering Verification** — implementation, execution, integration, tests, and software verification.
- **Evaluation & Benchmarking** — capability measurement, baselines, ceilings, cost, and stop/go decisions.
- **Process Assurance** — audits frames, inherited assumptions, stale state, false-green verification, and repeated failure patterns.
- **Decision Preflight** — grounding before consequential dispatch or after failure.
- **Evidence Review Panel** — selective multi-perspective review with evidence and control comparisons.
- **FOIL — Adaptive Reasoning Complement** — models uncertain user/task gaps and supplies the missing method while separating assisted performance from independent competence.

Technical IDs and command aliases are retained for compatibility; public documentation uses the professional display names above.

## Current evidence

Existing repository evidence supports narrower claims:

- public source/package invariants for the Research Orchestrator and Process Assurance modules;
- structural/source/regression checks for the FOIL specification;
- explicit separation of specification validation from behavioral efficacy;
- provenance mapping from public-facing claims to source artifacts.

See `validation/`, `research/FOIL_RESEARCH_BASIS.md`, and `REPRODUCIBILITY.md`.

## Planned evaluation

The planned behavioral study compares:

1. strong direct AI assistance;
2. static evidence/scaffolding rules;
3. adaptive FOIL plus modular routing;
4. low/no-AI learning control where feasible.

Primary endpoint: **delayed independent transfer with relevant AI assistance unavailable**.

Secondary endpoints include immediate task quality, error detection, calibration, near/far transfer, retention, completion time, tool/compute cost, false blockers, and missed verification obligations.

## Baselines and ablations

Required comparisons include:

- orchestrated workflow vs strong direct model;
- FOIL learner-state adaptation vs fixed scaffolding;
- evidence-native verifier vs same-model self-critique;
- Evidence Review Panel vs matched-evidence direct control;
- each promoted mechanism with and without the mechanism where practical.

## Research integrity boundary

A software test, citation, multi-agent consensus, or benchmark score is never promoted beyond the property it actually observes. Negative results and failed mechanisms are valid outputs and should be retained when they change the credible search space.
