---
name: novelbot
description: >-
  Foundry — BASTION-01's Method Synthesis Engine. Trigger: /reality,
  /novelbot, invent a method, find a new mechanism, or when verified prior art
  fails a named constraint. Produces novel candidates only after the
  existing-method boundary is explicit.
---

# Foundry — Method Synthesis Engine

Novelty is a **last-mile obligation**, not the default mode.

## Entry gate

Do not synthesize a new mechanism until:

- Farfield has identified the nearest known approaches;
- the relevant approaches fail a named constraint or leave a concrete gap;
- the success criterion is explicit.

## Synthesis protocol

1. Write the gap as a constraint table.
2. Identify which assumptions existing approaches share.
3. Generate candidates that change different assumptions/representations.
4. Separate mechanism from branding/naming.
5. For each candidate state: inputs, outputs, invariants, dependencies, failure modes, verification plan.
6. Run a costume/prior-art check again after the candidate becomes concrete.
7. Prefer the simplest candidate that satisfies the gap.

## Admission

A candidate is not promoted because it is creative. Require:

- causal adequacy for the observed gap;
- identifier/domain independence when claiming generality;
- negative control;
- transfer to at least one changed representation/domain when relevant;
- ablation showing the new component matters;
- regression against existing supported behavior.

Unverified novelty remains `NOVELTY UNKNOWN`.

## Typed runtime contract

`tools/reality_runtime.py` represents every candidate as a falsifiable machine-readable mechanism object with prior art, actual delta, negative control, transfer, ablation and verifier plan. A candidate can be admitted for testing only with a real stored cleared Space receipt; admission does not prove novelty or efficacy. See `docs/specs/REALITY_ENGINEERING_SPEC.md`.
