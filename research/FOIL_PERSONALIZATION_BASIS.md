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

## Learner-state models and longitudinal updates

Knowledge tracing treats competence as latent and changing over repeated interactions rather than as a fixed trait inferred from one response.

- Piech et al., *Deep Knowledge Tracing*: https://arxiv.org/abs/1506.05908
- 2024 systematic review of knowledge tracing + LLMs: https://arxiv.org/abs/2412.09248
- 2025 TASA persona/memory/forgetting-aware tutoring: https://arxiv.org/abs/2511.15163

**Design implication:** persist event history, assistance level, representation, and later performance; let newer diagnostic evidence update the profile.

**Boundary:** FOIL does not implement a trained KT model. Its ordinal classifications are explicit engineering heuristics until calibrated against real longitudinal data.

## Assistance matters

Tutoring research shows that assistance policy and help-seeking can affect subsequent learning/performance; success after help is not equivalent to independent mastery.

- Assistance action/policy evaluation at large scale: https://link.springer.com/chapter/10.1007/978-3-031-42682-7_26

**Design implication:** FOIL records whether an observation was independent, hinted, partial, or fully assisted. Assisted success cannot by itself create a `PROMISING_STRENGTH` or ownership claim.

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

This is an engineering extension motivated by learner-modeling research; no source above establishes FOIL's exact domain-promotion rule. The promotion rule is therefore a falsifiable design choice, not an empirical fact.

## Validation needed

Before claiming a validated personalizer, the project needs:

1. item difficulty/discrimination calibration on a sufficiently large, diverse sample;
2. test-retest reliability;
3. convergent/discriminant validity against established measures;
4. accessibility/fairness analysis;
5. prospective prediction of later independent task performance;
6. an ablation showing profile-driven assistance beats a strong non-profile baseline at matched model/tool budget;
7. evidence that dynamic domain expansion improves routing rather than creating noisy labels.
