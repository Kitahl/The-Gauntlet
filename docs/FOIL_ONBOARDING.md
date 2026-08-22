# FOIL onboarding and saved profiles

FOIL personalization is runtime data, not part of the public skill specification.

## First use

Claude Code project hooks automatically create a blank local `default` profile when no active profile exists. The profile begins with no assumed strengths or weaknesses.

## Layer 1 — broad domain questionnaire

Run:

```bash
python tools/foil_assessment.py start --out foil_assessment.json --responses foil_responses.json
```

The screen contains 20 generated objective probes across ten core domains plus context, work-style preferences, self-estimates, confidence, and open design/UX, creativity, and explanation tasks. Fill `foil_responses.json`, then apply it:

```bash
python tools/foil_assessment.py score \
  foil_assessment.json foil_responses.json \
  --profile default --out foil_assessment_report.json
```

Layer 1 is a cold-start screen. Its output is intentionally provisional.

## Layer 2A — structured cross-cutting calibration

Run the concrete second-layer test:

```bash
python tools/foil_layer2.py start \
  --profile default --mode standard \
  --out foil_layer2.json --responses foil_layer2_responses.json
```

The standard Layer 2A screen contains **24 objective scenarios across 12 cross-cutting facets**, plus open design, creative-search, and explanation tasks.

It tests how the person approaches:

- formalization;
- decomposition/systems boundaries;
- error detection;
- evidence scope/independence;
- causal reasoning;
- quantitative structure;
- implementation/execution;
- planning/prioritization;
- confidence calibration;
- transfer/adaptation;
- verifier/tool selection;
- uncertainty management.

After answering:

```bash
python tools/foil_layer2.py score \
  foil_layer2.json foil_layer2_responses.json \
  --profile default --out foil_layer2_report.json
```

Objective outcomes are mechanically scored and written as provisional deep-calibration evidence. Open responses are not stored in the profile and remain `NEEDS_RUBRIC_REVIEW` until genuinely reviewed.

A `short` mode uses one item per facet and is screening-only:

```bash
python tools/foil_layer2.py start --profile default --mode short
```

## Layer 2B — adaptive real-work calibration

Now build the profile-specific plan:

```bash
python tools/foil_calibration.py start --profile default --out foil_deep_calibration.json
```

Layer 2B focuses on the domains and uncertainties actually present in the profile and adds:

- changed-representation discriminators;
- harder transfer probes for apparent strengths;
- adversarial/error-detection tasks;
- real-work/artifact samples;
- design/creative production;
- explanation/teach-back;
- verifier/tool selection;
- confidence-before-feedback;
- domain-specific follow-ups.

Record a result only after the outcome is actually checked:

```bash
python tools/foil_calibration.py record \
  --profile default \
  --probe-id formal_reasoning:harder_transfer:1 \
  --domain formal_reasoning \
  --facet transfer_adaptation \
  --kind harder_transfer \
  --outcome pass \
  --assistance none \
  --verified \
  --confidence 85
```

Use:

```bash
python tools/foil_calibration.py status --profile default
```

to see whether the profile is still `CALIBRATING`, has broad evidence (`BROAD_PROFILE`), or meets the minimum engineering evidence-coverage gate `DEEP_PROFILE_READY`.

These states are not psychometric scores. A long-used profile with verified real-work evidence can remain more informative than a newly completed questionnaire even after the new profile reaches the minimum gate.

## Profile semantics

- topic/domain/facet relevance is not competence evidence;
- one independent miss cannot create a stable gap;
- assisted or unverified success cannot create an independent strength;
- apparent strengths need harder/changed-representation transfer evidence;
- open tasks require rubric/artifact/proof/execution or independent review before being marked verified;
- newer task-diagnostic evidence overrides stale onboarding evidence;
- many observations from one narrow domain cannot by themselves create a deep profile.

## Automatic adaptation

`UserPromptSubmit` now infers **both domain relevance and cross-cutting facet relevance** from the current request and stores only compact routing metadata. Raw prompt text is not stored.

The extended registry recognizes more than forty common professional/research domain families and still allows arbitrary custom domains. Relevance recognition never changes competence by itself.

Arbitrary domains can also be created explicitly through `tools/foil_profile.py observe`, questionnaire `--domain` arguments, or Layer 2 real-work calibration.

## Recommended stranger path

```text
blank profile
  → Layer 1 domain screen
  → Layer 2A cross-cutting screen
  → Layer 2B real-work / transfer calibration
  → normal usage-time updates
  → increasingly evidence-rich personal FOIL
```

This is the path intended to let a stranger reach the same **kind of personalization depth** as a profile built through long interaction, without copying anyone else's answers or history.

See `docs/FOIL_DEEP_CALIBRATION.md`, `docs/RUNTIME_SETUP.md`, and `research/FOIL_PERSONALIZATION_BASIS.md` for the full contract and research boundary.
