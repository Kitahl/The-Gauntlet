---
name: council-of-elders
description: Evidence Review Panel. Trigger: /council, /forum, "independent review", or equivalent. Selectively convenes challenge-derived, evidence-grounded review seats around a concrete artifact after a strong direct pass exists. Uses commit-reveal, distinct discriminators or evidence partitions, a concrete skeptic refuter, cross-critique, overlap diagnostics, and a matched direct control. Agreement is not truth.
---

# Evidence Review Panel

Use artifact-derived review seats, not named personalities or simulated authority.

## When to convene

Default: **off**.

Convene only when:

- there is a concrete artifact, claim, design, or candidate to review;
- a strong direct analysis already exists;
- at least three genuinely different challenge questions, discriminators, or evidence partitions are available;
- the total artifact and review budget can be frozen;
- marginal value can be compared against a same-artifact, same-budget direct control.

Do not convene merely because a problem is difficult or additional opinions sound reassuring.

## Construct challenge-derived seats

Prefer 3–6 seats derived from unresolved load-bearing gaps:

- formal correctness;
- evidence and provenance;
- executable behavior or integration;
- measurement validity;
- novelty or strongest costume;
- operational feasibility.

Every seat must own:

- one distinct challenge question;
- one concrete discriminator or refuter;
- one required capability when applicable;
- one target obligation;
- one method or explicit evidence partition.

Duplicate challenge kinds or discriminators are allowed only when the evidence partitions are explicitly different. Include a skeptic/adversarial seat with a concrete refuter; “be critical” is not a discriminator.

## Commit–reveal and cross-critique

1. Freeze the artifact hash, total-budget hash, seats, methods, challenge bindings, evidence partitions, and reviewer provenance.
2. Each seat independently commits its first-pass structured submission before seeing another seat’s result.
3. Reveal only after all commitments are frozen.
4. Reject altered submissions or wrong nonces.
5. Compute method, evidence, provenance, reviewer-provenance, and finding overlap.
6. Require every seat to cross-critique another revealed seat.
7. Synthesize by claim and evidence, preserving disagreement.

Do not call seats independent because there are several of them or because they produced separate messages. Same-model and shared-evidence common causes remain explicit.

## Supported findings

A load-bearing supported finding remains a review finding until the target module checks it.

The Council runtime may convert a supported structured finding into an additive neutral challenge with `origin=COUNCIL`. That challenge is proposal-only. It cannot resolve itself, replace a domain receipt, clear the target obligation, apply a repair, or authorize a write.

## Control and authority

Run a strong direct analysis against the same frozen artifact and matching total budget. Without that `DIRECT` control, Council’s review verdict remains `UNKNOWN`.

A Council receipt may clear only a `REVIEW` obligation. It never clears proof, discovery, synthesis, engineering, evaluation, assurance, preflight, adaptation, or adversary obligations. User or host authority remains required for adoption or writes.

## Typed runtime contract

`tools/council_runtime.py` enforces:

- 3–6 seats and a skeptic/adversarial seat;
- challenge kind, discriminator, capability, target obligation, refuter, and evidence partition for vNext seats;
- rejection of duplicate challenge/discriminator seats without distinct partitions;
- commitment hiding and reveal integrity;
- complete cross-critique participation;
- overlap diagnostics with `NOT_ESTABLISHED_BY_SEAT_COUNT`;
- structured `CouncilFinding` binding;
- proposal-only `COUNCIL` challenge emission;
- `REVIEW_ONLY` receipt authority;
- a same-artifact, same-total-budget `DIRECT` control.

Confidence remains uncalibrated unless scored prospectively. See `docs/specs/COUNCIL_ENGINEERING_SPEC.md`.
