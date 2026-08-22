# FOIL Research Basis and Adoption Ledger

Cut-off: 2026-08-21. This file records evidence used to redesign FOIL. It distinguishes what a source actually supports from the additional architecture inference made for FOIL. A citation is not proof that the FOIL-specific mechanism works.

## RB-KT-2023 — Knowledge tracing is latent and observation-noisy

**Source:** Abdelrahman, Wang, Nunes. *Knowledge Tracing: A Survey*. ACM Computing Surveys 55(11), 2023. DOI: `10.1145/3569576`.

**Source-supported:** knowledge tracing estimates changing latent knowledge from interaction history; surveyed models include prior knowledge, material difficulty, temporal context, forgetting, slip, and guess behavior.

**Does not establish:** that a general-purpose LLM can diagnose a persistent person's weakness from a few unconstrained messages.

**FOIL adoption:** competing learner-state hypotheses, assistance/context conditioning, prospective calibration. **Status: PROVISIONAL ARCHITECTURE.**

## RB-AI-LEARNING-2025 — Better assisted output is not necessarily better learning

**Source:** Fan et al. *Beware of metacognitive laziness: Effects of generative artificial intelligence on learning motivation, processes, and performance*. British Journal of Educational Technology 56, 489–530, 2025. DOI: `10.1111/bjet.13544`.

**Source-supported:** randomized study, N=117; ChatGPT group improved essay scores, while knowledge gain and transfer were not significantly different across support groups.

**FOIL adoption:** separate task value from learning value; primary validation removes relevant AI assistance. **Status: ADOPTED DESIGN PRINCIPLE; FOIL effect untested.**

## RB-ADAPTIVE-2016 — Assistance-responsive worked/faded/problem selection

**Source:** Shareghi Najar, Mitrovic, McLaren. *Learning with intelligent tutors and worked examples: selecting learning activities adaptively leads to better learning outcomes than a fixed curriculum*. User Modeling and User-Adapted Interaction 26(5), 459–491, 2016. DOI: `10.1007/s11257-016-9181-y`.

**Source-supported:** in the studied tutor/domain, adaptive selection among worked examples, faded examples, and problems based on prior assistance produced better learning than the fixed comparison sequence.

**Does not establish:** FOIL's exact fading table or optimal thresholds.

**FOIL adoption:** assistance-responsive fading with hysteresis. **Status: PROVISIONAL TRANSPORT.**

## RB-TRANSFER-2018 — Retrieval transfer is real but heterogeneous

**Source:** Pan & Rickard. *Transfer of test-enhanced learning: Meta-analytic review and synthesis*. Psychological Bulletin 144(7), 710–756, 2018. DOI: `10.1037/bul0000151`.

**Source-supported:** 192 effect sizes from 122 experiments; overall transfer advantage relative to re-exposure `d=0.40`, with substantial moderators.

**FOIL adoption:** OWNED does not imply TRANSFERRED; use non-identical and varied transfer tests. **Status: ADOPTED DESIGN PRINCIPLE.**

## RB-SPACING-2021 — Spaced retrieval helps; one expanding schedule is not universally superior

**Source:** Latimier, Peyre, Ramus. *A Meta-Analytic Review of the Benefit of Spacing out Retrieval Practice Episodes on Retention*. Educational Psychology Review 33, 959–987, 2021. DOI: `10.1007/s10648-020-09572-8`.

**Source-supported:** spaced retrieval outperformed massed retrieval in the analyzed studies (`g=0.74`); expanding intervals were not generally superior to uniform intervals.

**FOIL adoption:** retention probes and adaptive spacing; no universal hard-coded schedule. **Status: ADOPTED DESIGN PRINCIPLE.**

## RB-FORCING-2021 — Cognitive forcing can reduce overreliance with subjective costs

**Source:** Buçinca, Malaya, Gajos. *To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-Assisted Decision-Making*. PACM HCI 5(CSCW1), 2021. DOI: `10.1145/3449287`.

**Source-supported:** N=199; forcing interventions reduced overreliance compared with simpler explanation interfaces; more effective interventions received less favorable subjective ratings; effects varied with need for cognition.

**FOIL adoption:** event-triggered forcing ladder; separate friction from verification. **Status: PROVISIONAL TRANSPORT.**

## RB-SELF-CORRECTION-2024 — Generic prompted self-correction is not a universal verifier

**Source:** Kamoi et al. *When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs*. TACL 12, 1417–1440, 2024. DOI: `10.1162/tacl_a_00713`.

**Source-supported:** the survey found no general demonstrated success for prompted intrinsic self-correction outside specially self-verifiable tasks; reliable external feedback is substantially more effective.

**FOIL adoption:** claim-native escalation to independent evidence/execution/formal checks. **Status: ADOPTED DESIGN PRINCIPLE.**

## RB-FACTSCORE-2023 — Atomic claims improve factuality auditing

**Source:** Min et al. *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation*. EMNLP 2023. DOI: `10.18653/v1/2023.emnlp-main.741`.

**Source-supported:** long-form text can mix supported and unsupported information; FActScore decomposes generations into atomic facts and checks support against a knowledge source.

**Does not establish:** that any particular automatic decomposition preserves every qualifier or scope.

**FOIL adoption:** atomic claim graph plus an independent decomposition audit. **Status: ADOPTED MECHANICAL PRINCIPLE; decomposition audit remains provisional.**

## RB-ROUTING-SURVEY-2025 — Routing is a performance–cost selection problem

**Source:** Varangot-Reille et al. *Doing More with Less — Implementing Routing Strategies in Large Language Model-Based Systems: An Extended Survey*. arXiv:2502.00409, 2025.

**Source-supported:** LLM-system routing can select among models, experts, retrieval, and other components according to task requirements and resource constraints; the survey organizes routing strategies around relevance, performance, and cost.

**Does not establish:** that FOIL can already estimate the marginal value of a route, or that any one learned router generalizes to FOIL's mixed research tasks.

**FOIL adoption:** a two-layer router with hard epistemic obligations and a provisional, outcome-calibrated discretionary layer. **Status: SUPPORTING ARCHITECTURE EVIDENCE; FOIL estimator unvalidated.**

## RB-DECOMPOSITION-2024 — Claim decomposition changes factuality results

**Source:** Wanner, Ebner, Jiang, Dredze, Van Durme. *A Closer Look at Claim Decomposition*. Proceedings of *SEM 2024, 153–175. DOI: `10.18653/v1/2024.starsem-1.13`.

**Source-supported:** factual-support evaluations such as FActScore are sensitive to the claim-decomposition method; decomposition quality is a distinct source of evaluation error.

**Does not establish:** that FOIL's proposed decomposition audit is sufficient or optimal.

**FOIL adoption:** audit decomposition for coverage, scope preservation, non-invention, non-merger, dependencies, and recomposition before claim-level evidence status is trusted. **Status: ADOPTED CONTROL PRINCIPLE; exact audit unvalidated.**

## RB-MAS-2026 — Multi-agent gains can disappear under equal reasoning budgets

**Source:** Tran & Kiela. *Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal Thinking Token Budgets*. arXiv:2604.02460v2, 2026.

**Source-supported:** on the tested multi-hop tasks/models, matched reasoning-token comparisons found single-agent systems consistently matched or outperformed tested multi-agent architectures; authors identified budget-control and benchmark artifacts.

**Does not establish:** Council is always useless, or that all domains/protocols behave identically.

**FOIL adoption:** Council default OFF, matched-budget direct control, activate only for independent information/verification. **Status: ADOPTED CONTROL PRINCIPLE.**

## RB-SYCOPHANCY-2026 — Speaker agreement can distort judgment while increasing preference

**Source:** Cheng et al. *Sycophantic AI decreases prosocial intentions and promotes dependence*. Science 391(6792), 2026. DOI: `10.1126/science.aec8352`.

**Source-supported:** across 11 models and three preregistered experiments (N=2405), sycophantic responses were preferred/trusted while reducing responsibility-taking and increasing conviction in being right in the studied interpersonal contexts.

**Does not establish:** identical effects for technical research disputes.

**FOIL adoption:** agency and factual warrant remain separate; disagreement triggers evidence investigation rather than deference. **Status: SUPPORTING ADJACENT EVIDENCE.**

## Open evidence requirements

1. Direct validation that an LLM can distinguish stable knowledge gaps from fatigue, ambiguity, retrieval failure, and communication style for this user.
2. Calibration of FOIL's learner-state predictions.
3. Causal evidence that FOIL's ownership states have incremental predictive validity.
4. A validated policy for friction intensity and assistance fading in FOIL's domains.
5. A calibrated marginal-value estimator for skill/tool/Council routing.
6. Prospective matched-budget evidence that Council adds independent information on FOIL tasks.
7. Delayed AI-free transfer evidence showing FOIL improves independent competence over ordinary strong AI assistance.
