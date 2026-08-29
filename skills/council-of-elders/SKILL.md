---
name: council-of-elders
description: Evidence Review Panel v3. Trigger: /council, /forum, "independent review", or equivalent. Selectively convenes challenge-derived review seats around a concrete artifact, freezes seat-local evidence plans and budgets, acquires only bounded read-only evidence before first-pass commits, then uses commit-reveal, cross-critique, overlap diagnostics, and a matched direct control. Agreement is not truth.
---

# Evidence Review Panel v3

Use artifact-derived review seats, not named personalities or simulated authority.

Council v3 is additive. It preserves Council vNext's challenge-derived seats and REVIEW-only authority, then adds a seat-local smart-evidence acquisition layer before commit-reveal.

## When to convene

Default: **off**.

Convene only when:

- there is a concrete artifact, claim, design, or candidate to review;
- a strong direct analysis already exists;
- at least three genuinely different challenge questions, discriminators, or evidence partitions are available;
- the total review and evidence-acquisition budget can be frozen before work begins;
- marginal value can be compared against a same-artifact, same-total-budget direct control.

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

Duplicate challenge kinds or discriminators are allowed only when the evidence partitions are explicitly different. Include a skeptic/adversarial seat with a concrete refuter; "be critical" is not a discriminator.

## Council v3 smart-evidence phase

Council v3 does **not** import `foil_*` and does not let FOIL decide Council truth. A future FOIL smart-tool controller may propose neutral bundle candidates, but the native Council v3 contract remains independent and deterministic.

Before any seat acquires new evidence or commits a first pass:

1. freeze a caller-supplied total evidence budget;
2. freeze one non-transferable budget for every seat;
3. freeze one utility/risk policy for every seat;
4. freeze each seat's baseline evidence and provenance;
5. enumerate only task-local, dependency-complete bundle candidates;
6. require bundle estimates to cite frozen scored receipts;
7. reject hidden-gold-dependent, over-budget, capability-mismatched, cyclic, or non-read-only bundles;
8. remove dominated bundles;
9. select the greatest conservative-utility bundle only when it exceeds the frozen minimum margin;
10. otherwise stand down and use only the frozen baseline evidence.

The utility policy is frozen outside candidate bundles so a candidate cannot choose its own prices or risk weights.

Council v3 initial acquisition is read-only. Consequential or reversible external actions remain outside Council authority.

## Evidence-partition isolation

All seat evidence plans freeze before acquisition. All acquisition finishes before **any** first-pass commitment.

During this phase:

- a seat may use only its frozen baseline evidence plus evidence admitted from its selected bundle;
- cross-seat result reuse is forbidden before reveal;
- unused budget is not transferred between seats;
- invalid or unresolved tool evidence contributes no admitted evidence ID;
- source, tool, and provenance overlap remain measurable common causes, not evidence of independence.

A seat submission must exactly match its frozen evidence partition and admitted provenance set.

## Commit-reveal and cross-critique

After every seat's evidence-acquisition phase is complete:

1. each seat independently commits its structured first-pass submission;
2. reveal only after all commitments are frozen;
3. reject altered submissions or wrong nonces;
4. compute method, evidence, provenance, reviewer-provenance, source, tool, and finding overlap;
5. require every seat to cross-critique another revealed seat;
6. synthesize by claim and evidence, preserving disagreement.

Do not call seats independent because there are several of them or because they produced separate messages. Same-model, shared-source, shared-tool, and shared-evidence common causes remain explicit.

## Supported findings

A load-bearing supported finding remains a review finding until the target module checks it.

The Council runtime may convert a supported structured finding into an additive neutral challenge with `origin=COUNCIL`. That challenge is proposal-only. It cannot resolve itself, replace a domain receipt, clear the target obligation, apply a repair, or authorize a write.

## Control and authority

Run a strong direct analysis against the same frozen artifact and matching total budget. Without that `DIRECT` control, Council's review verdict remains `UNKNOWN`.

A Council receipt may clear only a `REVIEW` obligation. It never clears proof, discovery, synthesis, engineering, evaluation, assurance, preflight, adaptation, or adversary obligations. User or host authority remains required for adoption or writes.

## Typed runtime contract

`tools/council_runtime.py` remains the Council vNext state machine.

`tools/council_v3_evidence/__init__.py` adds:

- `EvidenceBudget`;
- `EvidenceUtilityPolicy`;
- `EvidenceBundleCandidate`;
- `SeatEvidenceReceipt`;
- `create_council_v3()`;
- frozen seat-local budget and utility partitions;
- deterministic positive-utility bundle selection with dominance pruning;
- dependency-DAG and task-only frontier checks;
- read-only and hidden-gold exclusion;
- evidence admission and exact cost conservation;
- no cross-seat result reuse before reveal;
- source/tool overlap diagnostics;
- `commit_v3()` evidence-partition binding;
- `finalize_v3()` evidence-audit binding into the ordinary REVIEW-only Council receipt.

Council v3 makes no behavioral-efficacy claim. Its marginal value must be measured prospectively against Council vNext and matched-budget direct analysis. See `docs/specs/COUNCIL_ENGINEERING_SPEC.md`.
