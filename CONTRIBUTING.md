# Contributing

Contributions are welcome when they improve correctness, reproducibility, evidence quality, portability, or research value.

## Before opening a change

1. Read `RESEARCH.md`, `REPRODUCIBILITY.md`, and the relevant skill specification.
2. Open or reference an issue for non-trivial behavioral changes.
3. State the claim or failure mode the change addresses.
4. Prefer the smallest general mechanism over project-specific rules.

## Development expectations

- Preserve backwards-compatible command aliases unless a breaking change is justified.
- Do not introduce unsupported factual, novelty, capability, or performance claims.
- Add or update deterministic checks for mechanically testable behavior.
- For stochastic experiments, report seeds, sample counts, baselines, and uncertainty.
- For research claims, cite primary/official sources where practical and separate source-supported facts from project-specific inference.
- Update `CHANGELOG.md` for user-visible changes.

## Pull requests

A strong PR explains:

- problem / research obligation;
- proposed mechanism;
- alternatives considered;
- evidence or tests;
- limitations and residual risk;
- reproducibility instructions;
- whether public behavior, claims, or compatibility change.

All required CI checks should pass before merge. A green suite certifies only what the suite observes.

## Research-mechanism admission

New core mechanisms should demonstrate, where applicable:

- causal adequacy for the triggering failure;
- identifier independence;
- robustness to equivalent representations;
- a negative control;
- cross-domain usefulness;
- preference for extending an existing primitive over adding another layer;
- ablation sensitivity;
- regression safety.

## Conduct

Participation is governed by `CODE_OF_CONDUCT.md`. Security issues should follow `SECURITY.md` rather than public issue disclosure.
