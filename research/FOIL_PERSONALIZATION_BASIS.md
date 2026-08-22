# FOIL personalization research basis

This file records the public research used to design FOIL onboarding and persistent profiles. It supports design components and cautions; it does **not** establish that FOIL's combined profile system is psychometrically validated.

## Broad reasoning coverage

The International Cognitive Ability Resource (ICAR) is a public-domain assessment family spanning multiple reasoning representations, including verbal, matrix/spatial, and sequence tasks. Recent validation work continues to find useful reliability/construct-validity evidence for selected ICAR measures.

- Condon & Revelle, *International Cognitive Ability Resource* (2014): https://icar-project.com/attachments/download/58/condon121312.pdf
- 2025 Mobile Toolbox validation of ICAR measures: https://pmc.ncbi.nlm.nih.gov/articles/PMC12733510/

**Design implication:** sample multiple reasoning representations rather than inferring general capability from one puzzle.

**Boundary:** FOIL's generated items are not ICAR items and inherit none of ICAR's norms or psychometric calibration.

## Adaptive testing

Computerized adaptive testing selects later items based on current evidence, but rigorous CAT depends on calibrated item parameters/IRT or MIRT models.

- irtQ / IRT calibration overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC11561393/
- Multidimensional adaptive cognitive measurement: https://pmc.ncbi.nlm.nih.gov/articles/PMC11694520/

**Design implication:** FOIL starts broad, then directs follow-up toward uncertain/gap domains and confirms apparent strengths on changed representations.

**Boundary:** the current FOIL selector is heuristic and must not be called a calibrated CAT until item parameters are estimated and validated.

## Cold-start learner modeling

Knowledge-state models are least reliable for a new learner when interaction history is sparse. Recent cold-start studies explicitly evaluate models on previously unseen students and find that prediction improves as more interactions become available.

- Bhattacharjee & Wayllace (2025), *Cold Start Problem: An Experimental Study of Knowledge Tracing Models with New Students*: https://arxiv.org/abs/2505.21517
- Bhattacharjee & Wayllace (2026), *MAML-KT: Addressing Cold Start Problem in Knowledge Tracing for New Students via Few-Shot Model-Agnostic Meta Learning*: https://arxiv.org/abs/2603.00137

**Design implication:** a one-shot onboarding result should be treated as a shallow prior. FOIL therefore separates Layer 1 cold start from Layer 2 evidence accumulation and continues to update during natural usage.

**Boundary:** these papers study student-performance prediction in tutoring datasets. They do not validate FOIL's exact profile schema, thresholds, domains, or probe policy.

## Learner-state models and longitudinal updates

Knowledge tracing treats competence as latent and changing over repeated interactions rather than as a fixed trait inferred from one response.

- Piech et al., *Deep Knowledge Tracing*: https://arxiv.org/abs/1506.05908
- 2024 systematic review of knowledge tracing + LLMs: https://arxiv.org/abs/2412.09248
- 2025 TASA persona/memory/forgetting-aware tutoring: https://arxiv.org/abs/2511.15163

**Design implication:** persist event history, assistance level, representation, and later performance; let newer diagnostic evidence update the profile.

**Boundary:** FOIL does not implement a trained KT model. Its ordinal classifications are explicit engineering heuristics until calibrated against real longitudinal data.

## Multidimensional deep calibration

Multidimensional adaptive assessment treats cognition/capability as a set of partially separable dimensions and selects items to improve uncertainty in those dimensions rather than relying on one total score.

- *Adaptive measurement of cognitive function based on multidimensional item response theory* (2024/2025): https://pmc.ncbi.nlm.nih.gov/articles/PMC11694520/
- *Combining Cognitive Diagnostic Computerized Adaptive Testing With Multidimensional Item Response Theory* (2022): https://pmc.ncbi.nlm.nih.gov/articles/PMC9118931/

**Design implication:** FOIL's second layer tracks both domain evidence and cross-domain working facets such as formalization, error detection, evidence discipline, transfer, design reasoning, and verifier selection.

**Boundary:** FOIL's facet counts are not MIRT parameters and the current readiness gates are not psychometric cut scores.

## Transfer is a separate target

Success on repeated or near-identical tasks does not by itself establish that a method transfers to a changed context. Work on metacognitive regulation also treats near/far transfer as a separate empirical question.

- Wirth et al. (2025), *Far Transfer of Metacognitive Regulation: From Cognitive Learning Strategy Use to Mental Effort Regulation*: https://link.springer.com/article/10.1007/s10648-024-09983-x

**Design implication:** Layer 2 explicitly requires changed-representation/transfer probes before FOIL relies strongly on an apparent strength.

**Boundary:** this study concerns school-age learners and metacognitive-regulation training. It supports measuring transfer separately, not FOIL's exact transfer threshold.

## Assistance matters

Tutoring research shows that assistance policy and help-seeking can affect subsequent learning/performance; success after help is not equivalent to independent mastery.

- Assistance action/policy evaluation at large scale: https://link.springer.com/chapter/10.1007/978-3-031-42682-7_26

**Design implication:** FOIL records whether an observation was independent, hinted, partial, or fully assisted. Assisted success cannot by itself create a `PROMISING_STRENGTH` or ownership claim.

## Adaptive feedback and self-regulation

Adaptive feedback systems can influence self-regulated learning behavior over time, and metacognitive activity can vary with motivational/contextual state.

- Mejeh, Sarbach & Hascher (2024), *Effects of adaptive feedback through a digital tool – a mixed-methods study on the course of self-regulated learning*: https://pmc.ncbi.nlm.nih.gov/articles/PMC11511727/

**Design implication:** FOIL should not interpret every miss as stable competence. Assistance, confidence, context, representation, and later evidence remain separate fields.

**Boundary:** this does not establish that FOIL's adaptive feedback policy improves learning.

## Creativity and open production

The Divergent Association Task (DAT) uses semantic distance among generated words as one quick measure of divergent verbal creativity while explicitly covering only a slice of creativity.

- DAT project / method: https://www.datcreativity.com/about

**Design implication:** include an open creativity probe but keep design, writing, explanation, and creativity tasks rubric-reviewed rather than forcing them into a single objective score.

## Confidence calibration

Item-level confidence can be compared with correctness using proper scoring rules such as Brier-style squared error.

- Metacognitive calibration example: https://pmc.ncbi.nlm.nih.gov/articles/PMC6192381/

**Design implication:** confidence is stored separately from correctness. High-confidence misses may justify stronger prediction-before-reveal and verification, but a short-screen score is not a stable personality trait.

## Dynamic domain expansion

FOIL's domain registry is open-ended. The fixed core domains exist only to provide coverage at cold start. During setup and use, new task-relevant domains may be created as `CANDIDATE`, promoted to `ACTIVE` only after explicit relevance or repeated observations, and revised by later evidence.

The extended public registry adds common work families only to improve automatic **relevance recognition**. Presence in that registry never establishes competence. Arbitrary custom domains remain allowed.

This is an engineering extension motivated by learner-modeling research; no source above establishes FOIL's exact domain-promotion rule. The promotion rule is therefore a falsifiable design choice, not an empirical fact.

## Layer 2 readiness gate

`tools/foil_calibration.py` uses an engineering coverage gate before labeling a profile `DEEP_PROFILE_READY`. It requires evidence diversity across domains, facets, transfer, real work, adversarial/error-detection probes, confidence-bearing outcomes, and open production.

The purpose is to prevent a false-deep profile caused by many repeated successes in one narrow task family.

**Boundary:** the thresholds are intentionally explicit and testable, but they are not empirically calibrated. Prospective work must compare alternative thresholds against future task-prediction and routing outcomes.

## Validation needed

Before claiming a validated personalizer, the project needs:

1. item difficulty/discrimination calibration on a sufficiently large, diverse sample;
2. test-retest reliability;
3. convergent/discriminant validity against established measures;
4. accessibility/fairness analysis;
5. prospective prediction of later independent task performance;
6. an ablation showing profile-driven assistance beats a strong non-profile baseline at matched model/tool budget;
7. evidence that dynamic domain expansion improves routing rather than creating noisy labels;
8. an ablation of Layer 1 alone vs Layer 1 + Layer 2 deep calibration;
9. evidence that the `DEEP_PROFILE_READY` thresholds predict better downstream personalization rather than merely more collected data.
