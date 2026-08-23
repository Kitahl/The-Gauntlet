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

---

# 2026-08-23 research report — locator ledger

This section records the sources supplied by the 2026-08-23 research report that
informed the FOIL 0.5.1 repairs. It follows the same rule as the rest of this
file: a citation is not proof that the FOIL-specific mechanism works.

**Provenance flags are load-bearing.** Locators marked `(from report; not
re-fetched)` were copied verbatim from the report and have **not** been resolved,
opened, or checked against the publisher in this pass. They are therefore
**UNVERIFIED locators**: neither the identifier, nor the claim attributed to it,
nor the scope of that claim may be relied on as `CITED` evidence until fetched.
They are listed so the provenance of a design influence is traceable, not so it
can be quoted. Sources marked **FETCHED** were checked against the primary source
and may be cited as verified at the stated scope.

## Not re-fetched — UNVERIFIED locators

### Fagerland, Lydersen & Laake 2013 — DOI `10.1186/1471-2288-13-91` (from report; not re-fetched)

Reported to concern recommended tests for paired binary data. **FOIL takes:** the
choice to report an *exact* McNemar-style paired comparison rather than an
asymptotic one on the very small discordant counts in this repository's benchmark
records, which is what `validation/FOIL_LEDGER_AUDIT_2026-08-23.md` did. **Does
not license:** any claim that a paired test on 36 pooled items establishes
superiority of one FOIL configuration over another; the test says nothing about
the confounds (disjoint historical subsets, later same-item re-run, public
questions) that make those runs directional at best.

### Settles & Meeder 2016 — DOI `10.18653/v1/P16-1174` (from report; not re-fetched)

Reported to present a trainable spaced-repetition model (half-life regression).
**FOIL takes:** the framing that a forgetting horizon is a *fitted* quantity, which
is exactly why `EvidencePolicy.half_life_days = 180.0` is documented as an
engineering choice and listed UNRESOLVED in `docs/FOIL_EVIDENCE_ESTIMATOR.md`.
**Does not license:** treating 180 days as calibrated, or importing a half-life
fitted on vocabulary review into competence evidence for research tasks.

### Choffin et al. 2019 — arXiv `1905.06873` (from report; not re-fetched)

Reported to concern a memory-aware, skill-tagged student model for spacing.
**FOIL takes:** the general point that per-skill decay differs, supporting the
per-domain half-life question raised in the UNRESOLVED list. **Does not license:**
adding a knowledge-tracing model to FOIL; section 18 of the skill explicitly
rejects an RL/KT tutoring policy before clean outcome data exists, and no such
data exists.

### Salden et al. 2010 — DOI `10.1007/s11251-009-9107-8` (from report; not re-fetched)

Reported to concern adaptive versus fixed fading of worked examples. **FOIL
takes:** support for the assistance-ladder fading rules in skill section 7 (start
low under `/foil teach`, reduce assistance on ownership probes). **Does not
license:** FOIL's specific five-rung ladder, its thresholds, or a claim that
fading improves outcomes for FOIL's users — the ladder is an implemented
hypothesis with no prospective evidence.

### Han et al. 2021 — DOI `10.1007/978-3-030-80504-3_27` (from report; not re-fetched)

Reported to concern learner modelling in an intelligent-tutoring context. **FOIL
takes:** nothing load-bearing. It is recorded as an influence on the competing-
hypothesis framing in skill section 5. **Does not license:** any FOIL
classification threshold or gap-kind boundary.

### Gu & Yan 2025 — DOI `10.1177/07356331251349620` (from report; not re-fetched)

Reported to concern generative-AI use and learning outcomes. **FOIL takes:**
reinforcement of the existing separation between task value and learning value
already adopted from RB-AI-LEARNING-2025. **Does not license:** a quantitative
effect size, or any claim about FOIL's own effect on learning.

### Barcauí 2025 — DOI `10.1016/j.ssaho.2025.102287` (from report; not re-fetched)

Reported to concern AI assistance in professional/knowledge work. **FOIL takes:**
context for the section 1 boundary that a deliverable request is not an
invitation to tutor. **Does not license:** any competence, productivity, or
adoption claim.

### Kerimbayev et al. 2025 — DOI `10.1109/icai67591.2025.11324568` (from report; not re-fetched)

Reported to concern AI in education. **FOIL takes:** nothing load-bearing;
recorded for provenance. **Does not license:** any FOIL mechanism, threshold, or
efficacy statement.

### Liu et al. 2026 — DOI `10.3389/fpsyg.2026.1848745` (from report; not re-fetched)

Reported to concern psychological outcomes of AI-assisted learning. **FOIL
takes:** nothing load-bearing; recorded for provenance. **Does not license:** any
inference about FOIL users, and specifically no clinical or psychological
characterization — skill section 1 forbids that regardless of source.

### Shen & Tamkin 2026 — arXiv `2601.20245` (from report; not re-fetched)

Reported to concern LLM behavior relevant to assistance and evaluation. **FOIL
takes:** nothing load-bearing; recorded for provenance. **Does not license:** any
routing rule or evaluation conclusion.

### Burnett & Richmond — DOI `10.3758/s13421-025-01743-8` (from report; not re-fetched)

Reported to concern memory research. **FOIL takes:** general support for treating
retention as a distinct, separately probed property (skill section 6, delayed
no-help attempt). **Does not license:** a retention schedule, an interval, or the
180-day half-life.

### Bowyer, Aitchison & Ivanova 2025 — arXiv `2503.01747` (from report; not re-fetched)

Reported to concern uncertainty and variance in LLM benchmark evaluation. **FOIL
takes:** support for the standing position that a small-n benchmark difference is
not superiority evidence, and for `foil_models.Determinism` forcing replicates
when a model's determinism class is weaker than `SEEDED`. **Does not license:**
any specific confidence interval, variance estimate, or sample-size rule used in
this repository's benchmark records.

## FETCHED — verified at the stated scope

### AgentPoison — arXiv `2407.12784` — FETCHED

Verified (abstract, and re-checked as claim A12 in
`validation/FOIL_LEDGER_AUDIT_2026-08-23.md`): the paper reports **">80% average
attack success, <0.1% poison rate"** for backdoor attacks on LLM agents via
memory/knowledge-base poisoning. **FOIL takes:** the justification for hardening
`foil_profile.compact_context()` and `foil_hook.py` — a stored profile is an
injection surface, so competence-bearing fields use a closed vocabulary, free
text is sanitized and length-capped, and the payload is bounded well under the
host cap. **Does not license:** a claim that FOIL's profile store is secure, that
the hardening is sufficient against this attack class, or that the attack's
success rate transfers to FOIL's payload shape — none of that has been tested
here.

### Persona prompting study — arXiv `2311.10054` — FETCHED

Verified (abstract, and re-checked as claim A13 in the same audit): **162
personas, 4 model families, 2,410 factual questions**; adding a persona did not
improve performance, and automatic persona selection performed about as well as
random selection. **FOIL takes:** direct support for the section 1 and section 18
prohibition on treating FOIL as a personality/persona layer — a profile earns
influence only by describing a *verified gap matching a capability the current
task requires* (`tools/foil_policy.py`), never by describing a person. **Does not
license:** a claim that FOIL's evidence-gated personalization *does* help; that is
exactly the open question, and the negative-control tests in
`tests/test_foil_policy_v2.py` establish only that a wrong or stale profile cannot
route.

### Claude Code hooks documentation — FETCHED

Verified (re-checked as claim A10 in the same audit, against the published hooks
documentation): hook output including `additionalContext` is **capped at 10,000
characters**, and `UserPromptSubmit` has a **30-second default timeout**. **FOIL
takes:** the concrete budget for `foil_hook.py` — the profile payload is capped
well below 10,000 characters so a large profile degrades explicitly instead of
being silently truncated by the host. **Does not license:** the adjacent ledger
claim that "resume can replay stale injected values", which the audit recorded as
**UNVERIFIED** — it is not stated in the documentation, and no FOIL behavior
depends on it.

## What this section does not add

No source here establishes that FOIL identifies real gaps, that its
classifications predict anything about a person, or that its complements improve
independent performance. The open evidence requirements listed above this section
are unchanged.
