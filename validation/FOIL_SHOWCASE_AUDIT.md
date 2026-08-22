# FOIL showcase audit

## Supported / source-traceable

- The repository combines nine skill modules: five specialist stones plus Infinity Gauntlet, Meditate, Council, and FOIL. Source: `skills/*/SKILL.md`.
- FOIL is described as a personalized complementary operator that mirrors the user's current method, not personality. Source: `skills/foil/SKILL.md`.
- FOIL separates user agency from factual warrant and requires task-relevant claims to face evidence/proof obligations. Source: `skills/foil/SKILL.md`.
- FOIL's current learner-state architecture uses competing hypotheses rather than a single weakness score. Source: `skills/foil/SKILL.md`; research boundary documented in `research/FOIL_RESEARCH_BASIS.md`.
- The static showcase has no required JavaScript, analytics, trackers, remote fonts, or remote runtime assets. Source: `validation/showcase-validation.json`.
- The current deterministic showcase checks cover semantic landmarks, deployment-safe links, keyboard entry point, focus styling, reduced-motion CSS, principal contrast, source presence, viewport overflow, and console errors. Source: `validation/showcase-validation.json`.

## Further evidence / proof required

- Whether FOIL actually improves delayed independent human competence compared with equally capable ordinary AI assistance.
- Whether FOIL's learner-state probabilities are calibrated in deployment.
- Whether Council or any multi-agent route improves outcomes under matched evidence/compute for a given task.
- Human aesthetic acceptance of the showcase. Mastermind/FOIL can produce and test a candidate, but should not represent model taste as the user's acceptance.

## Decision

The showcase may state what the repository implements and what its mechanical validators passed. It must not state that FOIL has been scientifically proven to improve learning, reasoning, or research performance.
