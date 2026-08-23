# vNext research and tool basis

This document records the external research/tool basis for the pre-benchmark engineering design. It is not evidence that the resulting implementation improves outcomes; those efficacy claims remain prospective.

## Meditate — metareasoning and decision control

- Russell & Wefald, **Principles of metareasoning**, *Artificial Intelligence* 49 (1991), DOI `10.1016/0004-3702(91)90015-C`. The paper formalizes selecting computational actions using probability/decision theory and the expected utility of computations. This motivates quantitative VOC only when the needed probabilities/utilities/costs are represented.
- Lieder & Griffiths, **Resource-rational analysis: Understanding human cognition as the optimal use of limited computational resources**, *Behavioral and Brain Sciences* (2019/2020). This motivates explicit resource costs and bounded-control decisions instead of unconditional extra reflection.
- Harmon & Walden, **A General-Purpose IT Intervention to Improve Human Decision Making, Strengthen Passwords, and Reduce Receptivity to Misinformation**, *Information Systems Research* (2025), DOI `10.1287/isre.2023.0372`. Their experiments report a useful boundary condition: latency can improve decision accuracy when task-relevant information is present during the pause and hurt when it is absent. Meditate therefore treats `STILL` as a control handoff directly into `GROUND`, not idle waiting.

## Gauntlet — runtime verification and assurance

- Goodloe & Havelund, **High-Integrity Runtime Verification** (2024). Runtime verification is positioned as one component of an assurance case, not a universal proof of system correctness. This motivates scoped monitor receipts and explicit monitorability limits.
- Gautham et al., **STPA-driven Multilevel Runtime Monitoring for In-time Hazard Detection** (2022), arXiv `2204.08999`. The workflow connects identified hazards to what/where/context of runtime monitoring and evaluates monitors with injected hazards. This motivates operation-specific hazard tests for Gauntlet.
- Rushby, **Runtime Certification** (2008). The assurance-case pattern of explicit goals, evidence and arguments motivates moving the evidence ledger beyond path-existence checks.
- Ferrando & Cardoso, **Towards Partial Monitoring: It is Always too Soon to Give Up** (2021/2022), DOI `10.4204/EPTCS.348.3`. Partial monitorability motivates `UNKNOWN`/`UNAVAILABLE` rather than pretending every open-world research-process property can be automatically decided.

Reference implementations to inspect before adding dependencies:

- R2U2 runtime verification: `https://github.com/R2U2/r2u2`
- RTAMT temporal-logic monitoring: `https://github.com/nickovic/rtamt`

These are reference architectures, not proposed hard dependencies.

## Council — correlated review, debate and confidence

- Choi, Zhu & Li, **Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?**, NeurIPS 2025 / arXiv `2508.17536`. Across seven NLP benchmarks, the authors report that majority voting accounts for most gains commonly attributed to vanilla MAD and formalize why ordinary debate need not improve expected correctness. This motivates DIRECT and VOTE controls.
- **CONSENSAGENT**, ACL Findings 2025, studies sycophancy in multi-agent debate and proposes a trigger-based mitigation. This motivates explicit anti-sycophancy/correlation diagnostics rather than treating multiple agents as independent.
- Zhu et al., **Demystifying Multi-Agent Debate: The Role of Confidence and Diversity** (2026), arXiv `2601.19921`. The paper identifies diverse initial viewpoints and calibrated confidence communication as key mechanisms and reports gains over vanilla MAD/majority vote. This motivates hypothesis/method diversity and prospective calibration.
- Human collective-decision work on correlated information and deliberation failures motivates measuring common evidence/provenance instead of forcing superficial persona diversity.

Baseline code to reproduce rather than reinvent:

- Debate-or-Vote: `https://github.com/deeplearning-wisc/debate-or-vote`

## Mind — proof engineering

- Thompson et al., **Rango: Adaptive Retrieval-Augmented Proving for Automated Software Verification** (2024), arXiv `2412.14063`. Rango retrieves relevant premises and similar proofs during Coq proof synthesis; the paper reports a 32% theorem proof rate on its benchmark, 29% more theorems than the prior comparison tool, and a 47% increase from adding relevant proofs to context. This motivates future premise-retrieval adapters rather than treating a prover as a context-free oracle.
- Proof-engineering surveys emphasize proof organization, automation and machine-checked artifacts. Mind therefore records the formal encoding and verifier scope separately from natural-language claims.

Candidate tools:

- Z3: `https://github.com/Z3Prover/z3`
- Lean 4: `https://github.com/leanprover/lean4`
- Coq/Rocq ecosystem as a future adapter target.

## Space — systematic discovery

- van de Schoot et al., **An open source machine learning framework for efficient and transparent systematic reviews**, *Nature Machine Intelligence* (2021), DOI `10.1038/s42256-020-00287-7`. ASReview provides an open-source active-learning framework for systematic-review screening. It is a candidate future screening adapter, not a completeness guarantee.
- Haddaway, Grainger & Gray, **Citationchaser: A tool for transparent and efficient forward and backward citation chasing in systematic searching**, *Research Synthesis Methods* (2022), DOI `10.1002/jrsm.1563`. Citation chasing can recover relevant studies missed by keyword combinations; this motivates explicit citation-chasing stages and starting-record provenance.

Candidate tools:

- ASReview: `https://github.com/asreview/asreview`
- CitationChaser: `https://github.com/nealhaddaway/citationchaser`
- OpenAlex, Crossref and OpenCitations APIs.

## Reality — structured mechanism search

The immediate engineering change is not to adopt one external optimizer. It is to make candidates explicit enough to compare by changed assumption/mechanism, prior art, negative control, transfer and ablation. Quality-diversity/novelty-search and design-by-analogy literatures are research targets for a later fixed-budget candidate-generation study; no such method is admitted until it beats simpler generation under matched verification budget.

## Power — verification diversity

Candidate tools to inspect and feature-detect rather than bundle indiscriminately:

- Hypothesis property-based testing: `https://github.com/HypothesisWorks/hypothesis`
- mutmut mutation testing: `https://github.com/boxed/mutmut`
- Semgrep static analysis: `https://github.com/semgrep/semgrep`
- existing Ruff, tests and CodeQL.

The design consequence is a coverage matrix: each check must name the defect classes it can observe, and mutation/hazard injection is used to test whether green gates can actually turn red on plausible faults.

## Time — paired and sequential inference

- Howard, Ramdas, McAuliffe & Sekhon, **Time-uniform, nonparametric, nonasymptotic confidence sequences**, *Annals of Statistics* 49(2), 2021, DOI `10.1214/20-AOS1991`. Confidence sequences remain valid uniformly over time and are appropriate when results are repeatedly inspected or stopping is data-dependent.
- Their open-source `confseq` implementation supports uniform boundaries, confidence sequences and always-valid p-values: `https://github.com/gostevehoward/confseq`.

The stdlib vNext baseline intentionally implements only fixed-n paired statistics and explicitly marks anytime-valid inference unresolved until a separately reviewed implementation is used.

## Admission rule for external tools

An external package is not added merely because it appears in this research basis. Before becoming a dependency it must have:

1. a named obligation it uniquely or materially improves;
2. a maintained/open implementation and acceptable license;
3. deterministic or well-characterized behavior for the target claim;
4. a version pin/lock strategy;
5. targeted tests plus a failure/unavailable path;
6. evidence that it improves coverage or correctness under a matched resource budget, when that is the reason for adding it.
