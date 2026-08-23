# Changelog

All notable changes to the Evidence-Governed Research Toolkit are documented here.

The project follows semantic versioning for public releases.

## [Unreleased]

### Planned
- Prospective behavioral evaluation of FOIL against direct-assistance and static-scaffolding baselines.
- Layer 1 vs Layer 1 + Layer 2A vs full Layer 2B personalization ablation.
- Empirical calibration of profile-maturity thresholds and item difficulty.
- Isolated same-item randomized benchmark A/B runs with confidence intervals and mechanism ablations.
- Independent reproduction reports.
- Archival DOI integration after the first evidence-bearing stable release.

## [0.5.1] - 2026-08-23

Research-repair release. It closes measured defects in FOIL's evidence
estimator, vocabulary, ledger, budget guard, and model layer. It closes **no**
efficacy question: retrieval and personalization quality remain `NOT_MEASURED`,
and no result in this release licenses a superiority claim.

### D1–D11 defect disposition

| ID | Defect | Disposition |
|---|---|---|
| D1 | Classification was a non-monotone count rule — one verified miss permanently blocked a strength verdict (`correct=20, incorrect=1 → UNCERTAIN`) | **CLOSED.** Beta posterior with a Jeffreys prior in `tools/foil_evidence.py`; monotonicity proved by exhaustive enumeration over a finite grid in `tests/test_foil_evidence.py`. Measured: 20/1 now yields `PROMISING_STRENGTH`, `P(θ>0.70)=0.997999`. |
| D2 | No stated evidence floor and no way to check what a screen length buys | **CLOSED.** `EvidenceTier` (`REAL_WORK`/`SCREEN`/`ASSISTED`/`UNVERIFIED`) with weights 1.0/0.4/0.0/0.0; `min_effective_n` expressed in `REAL_WORK` units so a screen alone can never be load-bearing; exact rate calculators `false_classification_rates` and `items_for_target_error` tabulated in `docs/FOIL_EVIDENCE_ESTIMATOR.md`. `items_for_target_error` reports honest non-convergence at the module defaults rather than a fabricated k. |
| D3 | `skills/foil/SKILL.md` and the runtime enums could drift silently; the documented `A0..A4` ladder and the runtime's `{"none","independent"}` check had an empty intersection, so conforming records were discarded | **CLOSED.** `foil_assistance.ladder_contract_block()` and `foil_interventions.gap_kinds_contract_block()` are pasted verbatim into `SKILL.md` sections 7 and 5; both drift tests are live gates (the two `@unittest.expectedFailure` decorators are removed and the tests pass). |
| D4 | Stale evidence retained full authority; a superseded pass could be reported as a transfer | **CLOSED (recency weight + freshness gate; horizon UNRESOLVED).** Two mechanisms, because the weight alone was insufficient: (a) exponential recency decay with a `min_weight = 0.05` floor, and (b) a `freshness_horizon_days = 360.0` gate requiring one admissible `REAL_WORK` observation inside the horizon before any verdict is offered, exposed as `stale_only` / `freshest_age_days` on the summary. The decay floor is a floor, not a cutoff, so on weight alone 80 verified misses aged 3600 days still summed past `min_effective_n` and classified `POSSIBLE_GAP` — measured, now a pinned regression in `FreshnessGateTests`. Old evidence still contributes its decayed weight whenever one fresh observation exists, so supersession is unaffected; `intervention_status()` remains time-ordered so a later verified failure supersedes an earlier pass. **Both time constants are UNRESOLVED** — the 180-day half-life and the 360-day horizon are engineering choices, not measured forgetting laws. |
| D5 | Capability/profile writes could fail silently | **CLOSED.** `CapabilityWriteError` raised on write failure instead of a silent no-op. |
| D6 | The task guard was described as "mechanically enforced" when it counted `authorize()` calls, not tool calls | **CLOSED ONLY UNDER THE PreToolUse BROKER, ADVISORY ELSEWHERE.** `tools/foil_task_guard.py` is a tamper-evident SHA-256 hash-chained ledger; enforcement exists only via `tools/foil_tool_broker.py` when `FOIL_TASK_RUN` is set, and only for tools the broker budgets. Outside that path the budget is advisory. Budget is charged at reservation, so a receipt records attempts admitted, not successful retrievals. |
| D7 | The concurrency lock was not a lock: an `O_EXCL` sentinel serialised nothing once created, and its PID/TTL liveness heuristic refused live contenders (12 workers against a budget of 5 produced 2 grants and 10 `LockTimeout`s) | **CLOSED.** Real kernel locks — `fcntl.flock` on POSIX, `msvcrt.locking` with `LK_NBLCK` byte-range locks on Windows — released by the kernel on close or crash. The timeout-forwarding bug that dropped the caller's timeout is fixed; the descriptor is closed exactly once. |
| D8 | Semantic repairs existed only as prose | **CLOSED.** Applied as tested commits: one assistance/ownership vocabulary, `ExecutionOwner` as an axis separate from assistance, and `independent_mastery_eligible = verified AND assistance == A0_INDEPENDENT AND execution_owner == USER`. |
| D9 | The V2 policy kernel lived only on an experiment ref and was cited by a commit id that resolves on no ref | **CLOSED BY RELOCATION.** Ported verbatim in substance as `tools/foil_policy.py` from `origin/experiment/foil-vnext5-vnext@9540860`; exhaustive enumeration of 14 invariants with a `routed_states` positive control, so a suite that refuses everything cannot pass. Invariant I10 ("at most one targeted complement per decision") is recorded as **tautological**: its predicate asserts only that `targeted_complement` is `None` or a `str`, which the field's type already guarantees, so it proves nothing about the property it names. It is left in place and labelled rather than counted as evidence. |
| D10 | "Underpowered benchmark comparison" | **NOT A CODE DEFECT.** A power table is supplied in `docs/FOIL_EVIDENCE_ESTIMATOR.md`; the protocol change belongs to Phase 5 and is not in this release. |
| D11 | The language model was a build-time assumption, so anything built on FOIL inherited the harness's hard-coded model | **CLOSED.** Model-agnostic adapters in `tools/foil_models.py` (`openai_chat`, `anthropic_messages`, `ollama_chat`, `cli`, `mock`) with a `claude_json` output parser, role-based resolution (`primary`/`reviewer`/`verifier`/`benchmark`), declared determinism classes, and secrets referenced by environment-variable name only. An unfilled role reports `NOT-MEASURED` rather than substituting the primary for the reviewer. |

### Added

- `tools/foil_evidence.py` — Beta-posterior competence estimator, evidence tiers, recency weighting, a freshness gate (`freshness_horizon_days`, with `stale_only` / `freshest_age_days` on the summary and `PosteriorSummary.as_dict()`), exact false-classification-rate calculators, and an SPRT diagnostic cross-check. No third-party dependencies: the regularized incomplete beta is implemented in-module.
- `tools/foil_assistance.py` — single-source assistance ladder and `ExecutionOwner` axis, with generated contract blocks.
- `tools/foil_policy.py` — ported V2 evidence-gated routing kernel; regime is derived from task properties, never from a benchmark name.
- `tools/foil_tool_broker.py` — PreToolUse enforcement boundary for frozen-run tool budgets.
- `tools/foil_models.py`, `tools/foil_setup.py` — provider-neutral model layer and `foil setup` CLI.
- `docs/FOIL_EVIDENCE_ESTIMATOR.md` — measured operating characteristics, the SPRT cross-check table, and the UNRESOLVED list.
- `research/FOIL_RESEARCH_BASIS.md` — 2026-08-23 locator ledger separating fetched sources from unverified report locators.
- `validation/FOIL_LEDGER_AUDIT_2026-08-23.md` — claim-by-claim audit of the 2026-08-22 evidence ledger.

### Changed

- `skills/foil/SKILL.md` restructured task-model-first, with generated vocabulary blocks, the Beta-posterior classification section, the `ExecutionOwner` rule, and honest budget/broker scope wording.
- `tools/foil_interventions.py` and `tools/foil_profile.py` record execution ownership and verification status; profile payloads are sanitized, closed-vocabulary, and length-capped.

### Not adopted

Pydantic, Sybil, LibCST, lm-eval, Hypothesis, Z3, and Lean were evaluated and **not
adopted**. The repository is stdlib-only with a hash-locked dependency graph, and
each of these would add a runtime or CI dependency for a capability the existing
code already covers. This is a scope decision, not a judgement about those tools.

PROV / RO-Crate provenance export is **DEFERRED**. Trigger: an external consumer
that actually needs machine-readable provenance interchange. Until then the
receipts in `benchmark_runs/` and the hash-chained guard ledger are the
provenance record.

### Evidence boundary

Corrected vNext evidence is recorded in
[`validation/FOIL_LEDGER_AUDIT_2026-08-23.md`](validation/FOIL_LEDGER_AUDIT_2026-08-23.md).
Two corrections carry forward:

- The ledger's frozen-V2 locator `8a44d68...` resolves on no ref and is **REFUTED as a locator**. The correct locator is **`9540860`** on `origin/experiment/foil-vnext5-vnext`.
- The ledger's vNext figure of 32/36 is refuted by mechanical re-score. The re-score gives ARC 12/12, GPQA 23/24, **pooled 35/36**, discordant 8 vNext-only / 0 historical-only, exact two-sided McNemar p = 0.0078. **This 35/36 re-score is DESCRIPTIVE ONLY.** It is not superiority evidence: the historical predictions came from earlier disjoint-subset sessions, the vNext run was a later same-item re-run with the questions already public, and gold-blindness rests on a question-only pack rather than a verifiable receipt. It must never be presented as validated.

Retrieval and personalization quality remain `NOT_MEASURED`. No prospective,
matched-budget, same-item randomized comparison exists for any FOIL
configuration.

## [0.5.0] - 2026-08-22

### Added
- Reproducible blinded benchmark harnesses for HLE/ARC-AGI-1, GPQA-Diamond, and BrowseComp under `benchmarks/harness/`.
- Benchmark-only `Frontier-Exam FOIL` protocol combining the existing FOIL verification behavior with a final Mastermind causal-defect pass without changing the permanent FOIL architecture.
- Permanent machine-readable benchmark receipt at `benchmarks/results/2026-08-22-blinded-pilot.json`.
- Public benchmark methodology and evidence-boundary report in `docs/BENCHMARKS.md`.
- Scoped benchmark evidence on the repository README and public Pages showcase, including the GPQA-Diamond null result.
- Full-history Gitleaks and Python dependency-audit CI gates.
- Deterministic `pip-tools`-generated dependency lock with package hashes, clean-regeneration verification, and `--require-hashes` installation.
- Linux, Windows, and macOS runtime portability CI using the locked dependency graph.
- Owner-restricted atomic persistence helper for local Gauntlet state and FOIL profiles.
- Release regression checks requiring immutable GitHub Action SHAs, generic secret-file ignores, documented external-model egress, and a Gauntlet/FOIL-only runtime boundary.
- Stable LF normalization for release/source text and the dependency lock across platforms.

### Changed
- Benchmark workflows publish blinded questions and public score receipts only; decrypted BrowseComp reference answers are not uploaded as public artifacts.
- Superseded experimental benchmark harness revisions were consolidated into three canonical runners.
- GitHub Actions are pinned to verified immutable full commit SHAs; CodeQL uses the supported v4 line.
- FOIL profile/state storage uses owner-only POSIX modes (`0700` directories, `0600` files) where supported.
- Process Assurance turn history persists only lossy similarity fingerprints, not assistant-message text.
- Optional OpenRouter data egress and local privacy behavior are now explicit in runtime/security documentation.
- Ruff development pin advanced from 0.16.2 to 0.16.3.
- Research Discovery's OpenAlex user agent derives the toolkit version from `VERSION` rather than a stale hard-coded release number.
- Mastermind implementation/runtime/control material is explicitly forbidden from tracked Gauntlet runtime paths; historical audit prose remains evidence only.
- Reachable branch/tag commit history was rewritten to use the GitHub private `noreply` identity instead of a personal author/committer email.

### Evidence boundary
The current HLE, ARC-AGI-1, and GPQA results are exploratory deterministic disjoint-subset pilots using GPT-5.6 Sol, not official benchmark submissions or isolated same-item randomized A/B evidence. The GPQA-Diamond pilot produced no accuracy gain and is retained as a null result. Legacy SimpleBench and freshness-routing results have weaker/manual evidence labels. Security-tool passes reduce specific known risks but do not prove the absence of all vulnerabilities or undiscoverable secrets.

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
