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

## Black Gem — adversarial review, judge reliability, and injection

Black Gem is the producer for the `ADVERSARY` obligation: an independent multi-seat
attack panel with a planted-costume canary and whole-run participation accounting. The
research basis below motivates the design; it is not evidence that the implementation
improves outcomes, and several results below are cited specifically for what they do
*not* license.

### Debate and adversarial oversight

- Irving, Christiano & Amodei, **AI safety via debate** (2018), arXiv `1805.00899`. Frames adversarial debate between agents as a mechanism for a weaker judge to extract more reliable answers. This motivates an attack panel with a separate adjudication step rather than a single reviewer.
- Michael, Mahdi, Rein, Petty, Dirani, Padmakumar & Bowman, **Debate Helps Supervise Unreliable Experts** (2023), arXiv `2311.08702`. Reports that debate can help a non-expert judge reach correct answers more often than consultancy. This motivates cross-critique between seats before synthesis.
- Khan, Hughes, Valentine, Ruis, Sachan, Radhakrishnan, Grefenstette, Bowman, Rocktaeschel & Perez, **Debating with More Persuasive LLMs Leads to More Truthful Answers** (2024), arXiv `2402.06782`. Finds optimizing debaters for persuasiveness can raise judge accuracy. This motivates keeping the graded rubric and adjudication frozen and independent of the attackers.
- Kenton, Siegel, Kramar, Brown-Cohen, Albanie, Bulian, Agarwal, Lindner, Tomasev, Farquhar, Shah & Everitt, **On scalable oversight with weak LLMs judging strong LLMs** (2024), arXiv `2407.04622`. Compares debate, consultancy and direct question-answering and finds debate is not uniformly best across task types. This is a NON-SUPPORT: it does not establish that two breakers beat one breaker plus a verifier, which is why a single-breaker DIRECT control is kept permanently.
- Du, Li, Torralba, Tenenbaum & Mordatch, **Improving Factuality and Reasoning in Language Models through Multiagent Debate** (2023), arXiv `2305.14325`. Reports multi-agent rounds improving factuality on several tasks. This motivates multiple independent passes but not agreement-as-evidence.
- Liang, Feng, He, Wang, Chen, Fu, Yang, Zhu, Yang & Shi, **Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate** (2023), arXiv `2305.19118`. Argues plain debate degenerates toward consensus without a diversity-preserving mechanism. This motivates off-diagonal cross-critique and preserved disagreement over averaging.
- Smit, Grinsztajn, Duckworth, Barrett & Pretorius, **Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs** (2024), arXiv `2311.17371`. Finds several debate strategies fail to beat simpler baselines under matched budget. This is a NON-SUPPORT alongside Kenton: it argues against assuming more debaters beat a strong single reviewer with verification, reinforcing the permanent single-breaker DIRECT control.
- Choi, Zhu & Li, **Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?** (2025), arXiv `2508.17536`. Reports majority voting explains most gains attributed to vanilla debate. This is a NON-SUPPORT: two-breaker panels are not shown superior to a single breaker with a verifier, so the DIRECT control stays in place and marginal value remains `NOT_MEASURED`.

### Judge reliability, self-preference, and correlated error

- Zheng, Chiang, Sheng, Zhuang, Wu, Zhuang, Lin, Li, Li, Xing, Zhang, Gonzalez & Stoica, **Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena** (2023), arXiv `2306.05685`. Documents systematic biases (position, verbosity, self-enhancement) in LLM judges. This motivates a frozen structured rubric and structured triples rather than a free-form judge score.
- Panickssery, Bowman & Feng, **LLM Evaluators Recognize and Favor Their Own Generations** (2024), arXiv `2404.13076`. Reports evaluators prefer their own outputs. This motivates keeping breakers distinct from the author under review and recording each seat's provenance.
- Goel, Struber, Auzina, Chandra, Kumaraguru, Kiela, Prabhu, Bethge & Geirhos, **Great Models Think Alike and this Undermines AI Oversight** (2025), arXiv `2502.04313`. Reports capable models share correlated errors, so apparent agreement overstates independence. This is a NON-SUPPORT for the common shortcut that a cross-family pairing implies independence: distinct `provenance_group` is recorded as a diagnostic, never as proof of independence.
- Kuncheva & Whitaker, **Measures of Diversity in Classifier Ensembles and Their Relationship with the Ensemble Accuracy** (2003), *Machine Learning* 51, DOI `10.1023/A:1022859003006`. Shows ensemble diversity measures relate only weakly and inconsistently to accuracy. This motivates treating seat diversity as descriptive metadata, not as a warrant.
- Ladha, **The Condorcet Jury Theorem, Free Speech, and Correlated Votes** (1992), *American Journal of Political Science* 36(3), DOI `10.2307/2111584`. Shows the jury theorem's guarantees weaken sharply once votes are correlated. This motivates measuring, not assuming, independence before counting concurring attacks.
- Lorenz, Rauhut, Schweitzer & Helbing, **How social influence can undermine the wisdom of crowd effect** (2011), *PNAS* 108(22), DOI `10.1073/pnas.1008636108`. Shows social information collapses the diversity that makes aggregation useful. This motivates the blind independent first pass, in which no seat sees another's output before committing.

### Adversarial collaboration, red-teaming, and mutation

- Perez, Huang, Song, Cai, Ring, Aslanides, Glaese, McAleese & Irving, **Red Teaming Language Models with Language Models** (2022), arXiv `2202.03286`. Uses models to elicit failures from other models. This motivates an automated attack rubric that actively searches for breaks.
- Mellers, Hertwig & Kahneman, **Do Frequency Representations Eliminate Conjunction Effects? An Exercise in Adversarial Collaboration** (2001), *Psychological Science* 12(4), DOI `10.1111/1467-9280.00350`. Establishes adversarial collaboration: parties who disagree pre-commit to a joint discriminating test. This motivates the mechanically-checkable KILL-TEST field on each strike.
- Saunders, Yeh, Wu, Bills, Ouyang, Ward & Leike, **Self-critiquing models for assisting human evaluators** (2022), arXiv `2206.05802`. Reports model-written critiques help humans find flaws they would otherwise miss. This motivates emitting structured break triples for downstream human review rather than a bare verdict.
- DeMillo, Lipton & Sayward, **Hints on Test Data Selection: Help for the Practicing Programmer** (1978), *Computer* 11(4), DOI `10.1109/C-M.1978.218136`. Introduces mutation testing: seed a known fault and require the test suite to catch it. This is the direct antecedent of the planted-costume canary.
- Jia & Harman, **An Analysis and Survey of the Development of Mutation Testing** (2011), *IEEE TSE* 37(5), DOI `10.1109/TSE.2010.62`. Surveys mutation testing and the equivalent-mutant problem. This motivates treating a rubber-stamped canary as a live BAD signal distinct from an absent seat.

### Contamination, injection, and preregistration

- Greshake, Abdelnabi, Mishra, Endres, Holz & Fritz, **Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection** (2023), arXiv `2302.12173`. Documents indirect prompt injection through untrusted content. This motivates the embedded injection canary and treating candidate text strictly as data.
- Hines, Lopez, Hall, Zarfati, Zunger & Kiciman, **Defending Against Indirect Prompt Injection Attacks With Spotlighting** (2024), arXiv `2403.14720`. Introduces spotlighting: delimit and mark untrusted content so the model does not follow instructions inside it. This is the direct basis for the delimited data block and the data-not-instructions preamble.
- Jacovi, Caciularu, Goldman & Goldberg, **Stop Uploading Test Data in Plain Text: Practical Strategies for Mitigating Data Contamination by Evaluation Benchmarks** (2023), arXiv `2305.10160`. Motivates content-hashed, frozen candidate/rubric/budget inputs so a moved goalpost is visible.
- Nosek, Ebersole, DeHaven & Mellor, **The preregistration revolution** (2018), *PNAS* 115(11), DOI `10.1073/pnas.1708274114`. Argues pre-committing analysis before seeing outcomes controls researcher degrees of freedom. This motivates freezing `rubric_hash` and `budget_hash` at strike creation, before any seat runs.

### What the evidence does NOT support

1. **Two breakers are not shown to beat one breaker plus a verifier.** Kenton et al. 2024, Smit et al. 2024 and Choi/Zhu/Li 2025 each find multi-agent debate/voting failing to beat simpler baselines under matched budget. A single-breaker DIRECT control is therefore kept permanently, and Black Gem's marginal value over it stays `NOT_MEASURED`.
2. **Cross-family pairing does not imply independence.** Goel et al. 2025 shows capable models share correlated errors. Distinct `provenance_group` counts are recorded as a diagnostic only; two distinct groups is a necessary bookkeeping condition for `trusted`, never a proof of statistical independence.
3. **No canary pass-rate threshold is empirically grounded.** Any cutoff for how many seats must catch the costume is an owner engineering choice, not a value this basis establishes.

### Novel construction

Using a planted-costume canary as a **per-run detector of breaker competence** — with the three-outcome CAUGHT / RUBBER_STAMP / ABSENT taxonomy, and `probe_trusted` kept separate from whole-run `trusted` — is a **novel construction** adapted from mutation testing (DeMillo/Lipton/Sayward 1978; Jia & Harman 2011). It is unvalidated: the receipt labels its detector status `NOVEL_CONSTRUCTION_UNVALIDATED`, and its discriminative power against real rubber-stamping is not measured here.
