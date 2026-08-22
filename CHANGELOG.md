# Changelog

All notable changes to the Evidence-Governed Research Toolkit are documented here.

The project follows semantic versioning for public releases.

## [Unreleased]

### Added
- Reproducible blinded benchmark harnesses for HLE/ARC-AGI-1, GPQA-Diamond, and BrowseComp under `benchmarks/harness/`.
- Benchmark-only `Frontier-Exam FOIL` protocol combining the existing FOIL verification behavior with a final Mastermind causal-defect pass without changing the permanent FOIL architecture.
- Permanent machine-readable benchmark receipt at `benchmarks/results/2026-08-22-blinded-pilot.json`.
- Public benchmark methodology and evidence-boundary report in `docs/BENCHMARKS.md`.
- Scoped benchmark evidence on the repository README and public Pages showcase, including the GPQA-Diamond null result.

### Changed
- Benchmark workflows publish blinded questions and public score receipts only; decrypted BrowseComp reference answers are not uploaded as public artifacts.
- Superseded experimental benchmark harness revisions were consolidated into three canonical runners.

### Evidence boundary
The current HLE, ARC-AGI-1, and GPQA results are exploratory deterministic disjoint-subset pilots using GPT-5.6 Sol, not official benchmark submissions or isolated same-item randomized A/B evidence. The GPQA-Diamond pilot produced no accuracy gain and is retained as a null result. Legacy SimpleBench and freshness-routing results have weaker/manual evidence labels.

### Planned
- Prospective behavioral evaluation of FOIL against direct-assistance and static-scaffolding baselines.
- Layer 1 vs Layer 1 + Layer 2A vs full Layer 2B personalization ablation.
- Empirical calibration of profile-maturity thresholds and item difficulty.
- Isolated same-item randomized benchmark A/B runs with confidence intervals and mechanism ablations.
- Independent reproduction reports.
- Archival DOI integration after the first evidence-bearing stable release.

## [0.4.0] - 2026-08-21

### Added
- Structured stranger-facing Layer 2A screen (`tools/foil_layer2.py`) with 24 objective scenarios across 12 cross-cutting reasoning facets.
- Short Layer 2A screening mode with one item per facet and no premature facet classification.
- Open Layer 2A design, mechanism-diversity/creativity, and explanation tasks that remain rubric-reviewed rather than auto-scored.
- Prompt-time cross-cutting facet relevance alongside domain relevance, without competence updates from topic mentions.
- Expanded relevance registry spanning more than forty professional/research domain families, including formal methods, data engineering, cloud/platform, AI safety/evaluation, bioinformatics, neuroscience, additional engineering disciplines, technical writing, product/organizational work, and more.
- Evidence-Centered Design, PISA creative-thinking, Consensual Assessment Technique, and metacognitive-transfer rationale in the personalization research basis.
- `validation/FOIL_LAYER2_MASTERMIND_AUDIT.md` preserving the structured-calibration falsification loops and CI-discovered vocabulary failure.

### Changed
- FOIL's stranger path is now explicit: Layer 1 broad domain screen → Layer 2A structured cross-cutting screen → Layer 2B adaptive real-work/transfer calibration → normal usage-time updating.
- Layer 2A objective responses can seed cross-cutting facet hypotheses, while open responses are not copied into profiles automatically.
- Prompt-time routing may recognize relevant reasoning facets such as formalization, error detection, evidence discipline, design, execution, or prioritization while keeping relevance separate from competence.

### Evidence boundary
This release establishes a reproducible structured second-stage screen and its integration with the deeper profile runtime. It does not establish psychometric validity, calibrated ability estimates, or that a newly screened profile is immediately as informative as months of real-work evidence.

## [0.3.0] - 2026-08-21

### Added
- Second-stage FOIL deep-calibration engine (`tools/foil_calibration.py`).
- Profile-dependent transfer, discriminator, adversarial, real-work, open-production, and verifier-selection probes.
- Cross-domain facet evidence for formalization, systems decomposition, error detection, evidence discipline, causal/quantitative reasoning, execution, design, creativity, explanation, planning, calibration, transfer, tool selection, and uncertainty management.
- Engineering profile-maturity states: `NOT_STARTED`, `CALIBRATING`, `BROAD_PROFILE`, and `DEEP_PROFILE_READY`.
- Extended automatic domain-relevance registry covering additional professional, scientific, engineering, business, creative, and public-sector work families.
- Deep-calibration context injection into the FOIL hook.
- `docs/FOIL_DEEP_CALIBRATION.md` and expanded research basis for cold-start, multidimensional assessment, and transfer.
- Regression tests for deep-profile gating, duplicate-probe protection, assistance/verification boundaries, transfer confirmation, and extended domain discovery.

### Changed
- FOIL uses broad cold start followed by evidence-driven deep calibration and continued usage-time updating.
- Apparent strengths are confirmed with changed-representation/transfer evidence before FOIL relies on them strongly.
- Open-ended deep probes require rubric/artifact/proof/execution or independent review before being marked verified.

### Evidence boundary
This release establishes the mechanics and explicit evidence gates for second-stage calibration. It does not establish psychometric validity, calibrated ability estimates, or causal improvement in downstream learning/research performance.

## [0.2.0] - 2026-08-21

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

### Evidence boundary
This release establishes portable runtime/profile mechanics and conservative cold-start personalization rules. It does not establish that profile-driven FOIL improves future outcomes.

## [0.1.0] - 2026-08-21

### Added
- Research Orchestrator control plane.
- Formal Reasoning, Research Discovery, Method Synthesis, Engineering Verification, and Evaluation & Benchmarking modules.
- Process Assurance Framework and Decision Preflight Protocol.
- Evidence Review Panel and FOIL adaptive complement.
- Public FOIL research integration validation records.
- Professional research-software README, architecture, evaluator quickstart, research/reproducibility/roadmap documents, MIT license, citation metadata, governance, CodeQL, CI, Dependabot, issue forms, and pull-request evidence gates.

### Evidence boundary
This release establishes the public software/specification baseline. It does not establish behavioral efficacy.
