# FOIL Layer 2 stranger calibration — Mastermind audit

Date: 2026-08-21 (America/Vancouver)
Branch: `feature/foil-layer2-calibration-v2`

## Target

Give a previously unknown user a path from a blank profile to the same **kind of evidence-rich personalization** that previously required prolonged naturalistic interaction, without copying another person's answers/history or claiming that a questionnaire can replace real-work evidence.

## Loop 1 — domain knowledge is not working style

### Failure mode

Layer 1 primarily samples broad domains. Two people can have similar topic knowledge while differing in formalization, evidence discipline, error detection, tool choice, decomposition, transfer, and confidence calibration.

### Mechanism

Add Layer 2A with separately tracked cross-cutting reasoning facets. Domain relevance and facet evidence remain distinct profile objects.

### Negative control

Prompt-time mention of a facet may mark it relevant but cannot create facet competence evidence.

## Loop 2 — reviewer-authored probes are not a stranger-facing test

### Failure mode

The existing Layer 2B planner generated good probe *instructions*, but a new user still depended on a reviewer to construct the actual tasks.

### Mechanism

Add `tools/foil_layer2.py`: 24 concrete objective micro-scenarios, two per 12 cross-cutting facets, plus open production tasks.

### Negative controls

- generated session contains no answer/correct/key fields;
- every objective item has exactly one derived answer;
- short mode uses one item/facet and cannot classify a facet;
- assisted success cannot create a promising strength.

## Loop 3 — fixed creativity score is too narrow

### Failure mode

A divergent-word task alone cannot represent design or creative problem solving, and automatic LLM scoring risks self-confirmation.

### Mechanism

Layer 2A open production separately samples design reasoning, mechanism-distinct creative search, and explanation. These responses remain `NEEDS_RUBRIC_REVIEW` and are not copied into persistent profiles automatically.

### Research support

The design basis records PISA creative-thinking process separation and Consensual Assessment Technique literature as motivation for multidimensional/open-product assessment.

## Loop 4 — questionnaire depth can become false depth

### Failure mode

Twenty-four correct micro-scenarios could make a profile look deep despite having no evidence from the person's actual work or changed contexts.

### Mechanism

Keep Layer 2B and the existing `DEEP_PROFILE_READY` gate. Layer 2A records only cross-domain microprobes, so it cannot satisfy distinct real-work-domain or real-work-sample gates by itself.

### Regression

A perfect Layer 2A run must still fail `DEEP_PROFILE_READY` for missing real-work/domain evidence.

## Loop 5 — narrow domain registry does not fit arbitrary strangers

### Failure mode

The original registry covered many technical/research areas but missed common professional families and could under-route unfamiliar users.

### Mechanism

Expand relevance recognition beyond forty domain families while retaining arbitrary custom-domain creation. Registry membership affects relevance only, never competence.

### Negative control

Registry tests verify representative phrases and explicitly reject strength/weakness semantics in the registry.

## Loop 6 — phrasing fragility

### Failure found by CI

The first candidate recognized `integer programming` but failed the natural phrase `integer programs` in an optimization/operations-research test.

### General repair

Broaden domain keyword families to common morphological/surface variants (`optimize`, `integer program`, `scheduling model`, etc.) rather than adding a one-off exact benchmark sentence.

## Current scientific boundary

This candidate can establish:

- a reproducible second-stage stranger screen;
- separate domain and cross-cutting facet evidence;
- conservative assistance-aware classifications;
- confidence-calibration data;
- broader automatic relevance recognition;
- a required continuation into real-work/transfer calibration.

It does **not** establish:

- psychometric validity or population norms;
- IQ/personality/aptitude measurement;
- that the facet item set is optimally discriminating;
- that `DEEP_PROFILE_READY` is an empirically calibrated cutoff;
- that a newly calibrated stranger profile is immediately as informative as months of naturalistic use;
- that profile-driven FOIL improves downstream outcomes versus a matched non-profile baseline.

The intended equivalence target is **profile structure, evidence discipline, and access to comparable depth**, not fabricated equality of evidence quantity.
