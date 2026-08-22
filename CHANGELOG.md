# Changelog

All notable changes to the Evidence-Governed Research Toolkit are documented here.

The project follows semantic versioning for public releases.

## [Unreleased]

### Planned
- Prospective behavioral evaluation of FOIL against direct-assistance and static-scaffolding baselines.
- Layer 1 vs Layer 1 + Layer 2A vs Layer 2A + Layer 2B vs full Layer 2C personalization ablation.
- Empirical calibration of profile-maturity thresholds, item difficulty, and policy decisions.
- Reproducible benchmark harnesses and independent reproduction reports.
- Archival DOI integration after the first evidence-bearing stable release.

## [0.5.0] - 2026-08-21

### Added
- Layer 2C universal evidence equalizer (`tools/foil_equalizer.py`) for balancing stranger-profile evidence across transferable capability families rather than over-sampling one narrow ability.
- Additional evidence facets covering verbal qualifier preservation, structural/spatial transformation, data interpretation, experimental design, benchmark/construct validity, interface integration, strategy synthesis, learning diagnosis, delayed retention, and decision calibration.
- Evidence-family coverage gates requiring distinct independently verified facets across reasoning/representation, epistemic/scientific judgment, systems/execution, creation/communication, strategy/integration, and learning/metacognition.
- Relevant-domain, representation-diversity, transfer, real-work, adversarial/error-detection, confidence, and delayed-retrieval coverage gates.
- A hard time-separated unassisted retrieval requirement before `HIGH_FIDELITY_PROFILE` can be reached.
- Issued-probe contract validation so recorded results cannot silently change family/facet/domain/kind after issuance.
- Neutral self-estimate/performance follow-up probes that do not tell the person which direction FOIL expects.
- Current-task policy compiler separating system verification intensity from pedagogical friction.
- Automatic prompt-hook injection of Layer 2C coverage and current-task policy context.
- `docs/FOIL_UNIVERSAL_REFINEMENT.md` and `research/FOIL_UNIVERSAL_REFINEMENT_BASIS.md`.
- Regression tests for evidence-family balancing, assistance/verification non-credit, arbitrary domains, delayed retrieval, issued-probe integrity, high-stakes direct verification, and current-fact routing.

### Changed
- FOIL's stranger path is now explicit: Layer 1 broad domain screen → Layer 2A structured cross-cutting screen → Layer 2B adaptive real-work/transfer calibration → Layer 2C universal evidence equalization/policy compilation → continued naturalistic updating.
- `tools/foil_hook.py` compiles profile evidence into task-specific assistance/verification behavior during normal use.
- Highest-fidelity personalization can no longer be achieved from a single immediate questionnaire session.

### Evidence boundary
This release improves stranger-profile **evidence coverage and runtime adaptation**. It does not establish psychometric validity, equalize people onto one intelligence/personality scale, or prove that onboarding becomes equivalent to months of naturalistic observation. The decisive behavioral endpoint remains delayed independent transfer relative to equally capable AI assistance without the personalization mechanisms.

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
- FOIL's stranger path became explicit: Layer 1 broad domain screen → Layer 2A structured cross-cutting screen → Layer 2B adaptive real-work/transfer calibration → normal usage-time updating.
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
- Process Assurance Framework with ten portable audit operations.
- Decision Preflight Protocol and Evidence Review Panel.
- FOIL adaptive complementary-reasoning specification and research basis.
- GitHub Pages technical showcase and provenance mapping.
- Structural/specification validation artifacts and release-boundary audit.

### Evidence boundary
This release establishes a public research-software specification and mechanical validation package. It does not establish that the full system improves human reasoning or research outcomes in deployment.
