---
name: council-of-elders
description: Evidence Review Panel. Trigger: /council, /forum, "independent review", or equivalent. Selectively convenes independent, evidence-grounded review roles around a concrete artifact after a strong direct pass exists. Uses commit-reveal, disjoint evidence where possible, a skeptic, and a matched direct control. Agreement is not truth.
---

# Evidence Review Panel

The public panel uses **artifact-derived review roles**, not simulated authority from named personalities.

## When to convene

Default: **off**.

Convene only when:

- there is a concrete artifact/claim/design to review;
- a strong direct analysis already exists;
- independent evidence/methods are plausibly available;
- the marginal value can be compared against a direct control.

Do not convene merely because the problem is hard or more opinions sound reassuring.

## Seat construction

Prefer 3–6 roles derived from the artifact, for example:

- formal correctness;
- empirical/measurement validity;
- implementation/integration;
- adversarial failure modes;
- prior art/novelty;
- cost/operational feasibility.

Include a skeptic role. Add a role only when it has a distinct question, evidence pack, verifier, or method.

## Commit-reveal

1. Each role independently freezes its first-pass conclusion before seeing other roles.
2. Use disjoint searches/evidence where feasible.
3. Reveal and cross-critique after independent commits.
4. Normalize claims to the same scope.
5. Rank by evidence, not identity or vote count.
6. Preserve unresolved disagreement.

## Control

Run one strong direct analysis with access to the same combined evidence budget when feasible. Attribute panel value only to findings the control did not produce or to stronger verification/coverage.

Panel output remains a claim until independently checked when the conclusion is load-bearing.

## Typed runtime contract

`tools/council_runtime.py` enforces 3–6 distinct seat questions, a skeptic/adversarial seat, frozen commitment hashes before reveal, reveal integrity, and evidence/provenance overlap diagnostics. Council's REVIEW verdict remains `UNKNOWN` until commit/reveal is complete, every seat contributes cross-critique, and a real DIRECT control matches the same frozen artifact and total-budget hashes. Confidence is recorded as uncalibrated unless later scored prospectively. See `docs/specs/COUNCIL_ENGINEERING_SPEC.md`.
