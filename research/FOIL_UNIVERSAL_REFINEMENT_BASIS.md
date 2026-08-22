# FOIL universal-refinement research basis

This note records the research basis for Layer 2B (`tools/foil_equalizer.py`). The literature supports several component ideas; it does **not** validate FOIL's exact family taxonomy, thresholds, or policy compiler.

## 1. Do not equate one error with one stable weakness

Knowledge-tracing research treats observed correctness as noisy evidence about latent competence, with slip, guessing, item properties, temporal context, and forgetting affecting interpretation.

- *Knowledge Tracing: A Survey*, ACM Computing Surveys, DOI: 10.1145/3569576.
- Piech et al., *Deep Knowledge Tracing*, arXiv:1506.05908.

**Layer 2B implication:** use competing explanations plus changed-representation/discriminating probes. A repeated wrong answer in one surface form is not sufficient evidence of a stable weakness.

## 2. Sample multiple representations and balance content

Broad cognitive-assessment work such as the public-domain ICAR family uses different representations rather than inferring broad ability from one puzzle type. Multidimensional adaptive-testing work likewise treats content/domain balancing as a distinct constraint from simply choosing the statistically most informative next item.

- Condon & Revelle, *The International Cognitive Ability Resource and the development of the International Cognitive Ability Resource*, 2014.
- ICAR project: https://icar-project.com/
- Recent multidimensional computerized-adaptive-testing literature motivates balancing information across dimensions rather than over-sampling a single high-information domain.

**Layer 2B implication:** family gates require distinct facets; repeated success on one facet cannot satisfy an entire family.

**Boundary:** FOIL items are not ICAR items and inherit none of ICAR's norms, validity, or score interpretation.

## 3. Immediate AI-assisted success is not independent competence

Experimental work on generative-AI assistance has found that better immediate output does not necessarily imply corresponding gains in knowledge or transfer.

- Fan et al., *Beware of metacognitive laziness: Effects of generative artificial intelligence on learning motivation, processes, and performance*, British Journal of Educational Technology, DOI: 10.1111/bjet.13544.

**Layer 2B implication:** assisted or unverified success cannot satisfy independent evidence gates.

## 4. Transfer must be tested, not narrated

Retrieval-practice research shows positive transfer on average, but transfer is heterogeneous and depends on the relation between practice and criterion tasks.

- Pan & Rickard, *Transfer of test-enhanced learning: Meta-analytic review and synthesis*, Psychological Bulletin 2018, PMID 29733621.

**Layer 2B implication:** apparent strengths receive changed-context/harder-transfer probes before FOIL relies strongly on them.

## 5. Retention requires time-separated evidence

Spacing/retrieval research supports repeated retrieval over time rather than immediate re-exposure as evidence of durable access.

- Latimier, Peyre & Ramus, *A Meta-Analytic Review of the Benefit of Spacing out Retrieval Practice Episodes on Retention*, Educational Psychology Review 2021.

**Layer 2B implication:** the highest-fidelity profile requires at least one delayed, unassisted, non-identical retrieval event. The 24-hour `not_before` is an engineering minimum, not a scientifically optimal universal interval.

## 6. Assistance should fade from performance evidence

Worked-example research and adaptive tutoring show that guidance appropriate for novices can become unnecessary as expertise rises, and that assistance-responsive sequencing can outperform a fixed sequence.

- Najar, Mitrovic & McLaren, *Learning with intelligent tutors and worked examples: selecting learning activities adaptively leads to better learning outcomes than a fixed curriculum*, User Modeling and User-Adapted Interaction 2016.

**Layer 2B implication:** policy compilation considers whether a strength/gap is independently supported before choosing independent-first, worked-example, or minimal-diagnostic behavior.

## 7. Verification intensity and learner friction are different controls

Cognitive-forcing interventions can reduce overreliance but can also increase burden or reduce preference for the interface.

- Buçinca, Malaya & Gajos, *To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-assisted Decision-making*, arXiv:2102.09692.

**Layer 2B implication:** high-stakes urgent work can use maximum system verification with minimal pedagogical friction. FOIL should not make a user solve everything independently merely because verification needs are high.

## 8. Current/executable/formal claims need claim-native verification

Research on LLM self-correction finds generic same-model reflection unreliable outside special self-verifiable settings, while reliable external feedback is more consistently useful.

- Kamoi et al., *When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs*, TACL 2024.

**Layer 2B implication:** the policy compiler routes current facts to current authoritative sources, executable software claims to execution/tests, and formal claims to formal/exhaustive checks when available.

## 9. Preferences must not become unsupported learning-style prescriptions

Educational research has not established that matching instruction to declared visual/auditory learning styles improves learning outcomes in the way popular "learning styles" claims imply.

**Layer 2B implication:** presentation preferences may tune interaction style, but competence and learning policy are updated from performance evidence, not from a personality-style label.

## 10. Real work remains essential

A short artificial battery cannot reproduce the ecological evidence accumulated from months of actual projects. Layer 2B therefore includes relevant-domain real-work samples and continues to update from naturalistic use.

**Layer 2B implication:** `HIGH_FIDELITY_PROFILE` is an evidence-coverage state, not a claim that onboarding equals a long observation history. Newer verified real-work evidence overrides onboarding priors.

## Unvalidated architecture decisions

The following are deliberately labeled engineering hypotheses:

- the six Layer 2B evidence families;
- the number of distinct facets required per family;
- the 24-hour minimum delayed-retrieval interval;
- the maturity state thresholds;
- the exact task-policy rules;
- automatic domain-registry keywords.

They should be calibrated prospectively and simplified if they fail to predict better assistance decisions.

## Decisive validation programme

A future evaluation should compare at least:

1. strong direct AI assistance;
2. static FOIL rules;
3. Layer 1 + Layer 2A;
4. Layer 1 + Layer 2A + Layer 2B universal refinement.

The primary outcome should be **delayed independent transfer after the relevant AI assistance is unavailable**, with secondary measures for task quality, near/far transfer, retention, error detection, confidence calibration, completion time, verification cost, and user burden.
