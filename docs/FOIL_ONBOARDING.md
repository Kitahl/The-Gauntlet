# FOIL onboarding and saved profiles

FOIL personalization is runtime data, not part of the public skill specification.

## First use

Claude Code project hooks automatically create a blank local `default` profile when no active profile exists. The profile begins with no assumed strengths or weaknesses.

## Questionnaire

Run:

```bash
python tools/foil_assessment.py start --out foil_assessment.json --responses foil_responses.json
```

The screen contains 20 generated objective probes across ten core domains plus open design/UX, creativity, and explanation tasks. Fill `foil_responses.json`, then apply it to the active or named profile:

```bash
python tools/foil_assessment.py score foil_assessment.json foil_responses.json --profile default --out foil_assessment_report.json
```

## Profile semantics

- topic/domain relevance is not competence evidence;
- one independent miss cannot create a stable gap;
- assisted success cannot create an independent strength;
- apparent strengths need harder/changed-representation transfer evidence;
- open tasks require rubric/independent review;
- newer task-diagnostic evidence overrides stale onboarding evidence.

## Automatic adaptation

`UserPromptSubmit` infers current domain relevance from the prompt and saves only the inferred domain metadata. Raw prompt text is not stored. Arbitrary domains can also be created explicitly through `tools/foil_profile.py observe` or questionnaire `--domain` arguments.

See `docs/RUNTIME_SETUP.md` and `research/FOIL_PERSONALIZATION_BASIS.md` for the full contract and research boundary.
