# FOIL onboarding and saved profiles

FOIL personalization is runtime data, not part of the public skill specification.

## First use

Claude Code project hooks automatically create a blank local `default` profile when no active profile exists. The profile begins with no assumed strengths or weaknesses.

## Layer 1 — broad questionnaire

Run:

```bash
python tools/foil_assessment.py start --out foil_assessment.json --responses foil_responses.json
```

The screen contains 20 generated objective probes across ten core domains plus open design/UX, creativity, and explanation tasks. Fill `foil_responses.json`, then apply it to the active or named profile:

```bash
python tools/foil_assessment.py score foil_assessment.json foil_responses.json --profile default --out foil_assessment_report.json
```

Layer 1 is a cold-start screen. Its output is intentionally provisional.

## Layer 2 — deep calibration

Build a profile-specific second-stage plan:

```bash
python tools/foil_calibration.py start --profile default --out foil_deep_calibration.json
```

Layer 2 focuses on the domains and uncertainties actually present in the profile and adds:

- changed-representation discriminators;
- harder transfer probes for apparent strengths;
- adversarial/error-detection tasks;
- real-work samples;
- design/creative production;
- explanation/teach-back;
- verifier/tool selection;
- confidence-before-feedback;
- cross-domain reasoning facets.

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

to see whether the profile is still `CALIBRATING`, has broad evidence (`BROAD_PROFILE`), or meets the engineering evidence-coverage gate `DEEP_PROFILE_READY`.

These states are not psychometric scores.

## Profile semantics

- topic/domain relevance is not competence evidence;
- one independent miss cannot create a stable gap;
- assisted or unverified success cannot create an independent strength;
- apparent strengths need harder/changed-representation transfer evidence;
- open tasks require rubric/artifact/proof/execution or independent review before being marked verified;
- newer task-diagnostic evidence overrides stale onboarding evidence;
- many observations from one narrow domain cannot by themselves create a deep profile.

## Automatic adaptation

`UserPromptSubmit` infers current domain relevance from the prompt and saves only inferred domain metadata. Raw prompt text is not stored.

The runtime now recognizes a wider set of common professional/research domains in addition to the original core domains, while still allowing arbitrary custom domains. Relevance recognition never changes competence by itself.

Arbitrary domains can also be created explicitly through `tools/foil_profile.py observe`, questionnaire `--domain` arguments, or Layer 2 real-work calibration.

See `docs/FOIL_DEEP_CALIBRATION.md`, `docs/RUNTIME_SETUP.md`, and `research/FOIL_PERSONALIZATION_BASIS.md` for the full contract and research boundary.
