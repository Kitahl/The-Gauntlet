# Changelog

All notable changes to the Evidence-Governed Research Toolkit are documented here.

The project follows semantic versioning for public releases.

## [Unreleased]

### Added
- Portable Claude Code Process Assurance hooks in `.claude/settings.json`.
- Config-driven assurance runtime under `tools/` with state outside `.git/`.
- Environment-only OpenRouter adapter plus optional independent red-team and SNAP helpers.
- Persistent multi-user FOIL profiles stored outside the repository by default.
- Automatic blank-profile bootstrap and prompt-time domain-relevance adaptation without raw prompt storage.
- Adaptive FOIL onboarding questionnaire with 20 generated objective probes plus design, creativity, and explanation tasks.
- Open-ended FOIL domain registry and optional science/hardware/policy/product/human-factors domains.
- Private-lineage, runtime, questionnaire, and `SKILL.md`-only regression tests.
- `research/FOIL_PERSONALIZATION_BASIS.md` and `validation/RUNTIME_FOIL_MASTERMIND_AUDIT.md`.

### Changed
- Public specialist skills are portable research specifications rather than private workstation/model-routing configurations.
- Evidence Review Panel no longer bundles named-persona/private-project roster material.
- FOIL no longer embeds any specific user's assessment priors or strengths.

### Planned
- Prospective behavioral evaluation of FOIL against direct-assistance and static-scaffolding baselines.
- Reproducible benchmark harnesses and ablation results.
- Archival DOI integration after the first evidence-bearing stable release.

## [0.1.0] - 2026-08-21

### Added
- Research Orchestrator control plane.
- Formal Reasoning, Research Discovery, Method Synthesis, Engineering Verification, and Evaluation & Benchmarking modules.
- Process Assurance Framework with ten portable audit operations.
- Decision Preflight Protocol and Evidence Review Panel.
- FOIL adaptive complementary-reasoning specification and research basis.
- GitHub Pages technical showcase and provenance mapping.
- Structural/specification validation artifacts and release-boundary audit.

### Evidence boundary
This release establishes a public research-software specification and mechanical validation package. It does not establish that the full system improves human reasoning or research outcomes in deployment.
