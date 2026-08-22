# FOIL deep calibration — Layer 2

Layer 1 (`tools/foil_assessment.py`) is a broad cold-start domain screen. Layer 2 exists because a short questionnaire cannot recover the depth of a profile built from repeated real work.

Layer 2 now has **two stages**:

1. **Layer 2A — structured cross-cutting screen** (`tools/foil_layer2.py`): concrete scored scenarios that sample how the person reasons across domains.
2. **Layer 2B — adaptive real-work calibration** (`tools/foil_calibration.py`): changed-representation, adversarial, real-artifact, transfer, design, creative, and explanation probes selected from the saved profile.

The design goal is not to make every stranger look alike. It is to give every stranger a route to the same *kind* of evidence-rich FOIL profile: domain evidence + cross-cutting reasoning evidence + confidence calibration + transfer + real-work updates.

## Layer 2A — structured stranger screen

After applying Layer 1 to a saved profile:

```bash
python tools/foil_layer2.py start --profile alice \
  --mode standard \
  --out foil_layer2.json \
  --responses foil_layer2_responses.json
```

The standard screen contains:

- 24 objective micro-scenarios;
- 12 cross-cutting facets with two changed-surface observations each;
- confidence on every objective response;
- blank self-estimates for the same facets;
- open design, creative-search, and explanation tasks.

The 12 objective facets are:

- formalization precision;
- decomposition/systems thinking;
- error detection;
- evidence discipline;
- causal reasoning;
- quantitative reasoning;
- implementation/execution;
- planning/prioritization;
- metacognitive calibration;
- transfer/adaptation;
- tool/verifier selection;
- uncertainty management.

A shorter one-item-per-facet mode is available:

```bash
python tools/foil_layer2.py start --profile alice --mode short
```

Short mode is **screening only**. One response per facet cannot create a `PROMISING_STRENGTH` or `POSSIBLE_GAP` classification.

Fill the generated response file, then score and apply it:

```bash
python tools/foil_layer2.py score \
  foil_layer2.json foil_layer2_responses.json \
  --profile alice --out foil_layer2_report.json
```

Objective items are deterministically verifiable, but their public session payload contains no answer/correct/key fields. Open responses are **not** automatically written into the saved profile and remain `NEEDS_RUBRIC_REVIEW` until a real rubric, artifact check, or independent reviewer supplies evidence.

Layer 2A classifications are still provisional. Two micro-scenarios can justify a routing hypothesis; they cannot establish durable ownership or deep expertise.

## Layer 2B — adaptive real-work calibration

After Layer 2A, generate a profile-dependent plan:

```bash
python tools/foil_calibration.py start --profile alice --out foil_deep_calibration.json
```

The adaptive plan prioritizes:

- `POSSIBLE_GAP` domains with discriminating changed-representation probes;
- `UNCERTAIN` domains with fresh independent probes;
- `PROMISING_STRENGTH` domains with harder transfer tests;
- real-work and adversarial probes in the most relevant domains;
- cross-cutting probes for formalization, evidence discipline, systems decomposition, design reasoning, creative search, explanation, planning, and verifier selection.

The plan contains **instructions and review contracts, not answer keys**.

## Record real evidence

A result should be marked `--verified` only when an appropriate reviewer, artifact, proof, execution, rubric, or other claim-native check supports the outcome.

Example:

```bash
python tools/foil_calibration.py record \
  --profile alice \
  --probe-id formal_reasoning:harder_transfer:1 \
  --domain formal_reasoning \
  --facet transfer_adaptation \
  --kind harder_transfer \
  --outcome pass \
  --assistance none \
  --verified \
  --confidence 85 \
  --representation "changed notation"
```

Assisted or unverified success is retained as evidence history but cannot create an independent strength. Duplicate probe IDs are rejected so the same result cannot be counted twice.

## Profile maturity

```bash
python tools/foil_calibration.py status --profile alice
```

The runtime uses four engineering states:

- `NOT_STARTED`
- `CALIBRATING`
- `BROAD_PROFILE`
- `DEEP_PROFILE_READY`

`DEEP_PROFILE_READY` is a **minimum evidence-coverage gate for stronger routing**, not a claim that a questionnaire has recreated months of naturalistic evidence. The current gate requires broad evidence coverage across multiple domains and facets, changed representations/transfer, real-work samples, adversarial/error-detection evidence, confidence-bearing results, and open production.

A stranger who completes Layer 1 + Layer 2A can therefore obtain a useful, broad starting profile quickly. Reaching the evidentiary depth of a long-used FOIL still requires Layer 2B and normal usage-time evidence.

## Cross-domain facets

The deeper runtime can maintain evidence about:

- formalization precision;
- decomposition/systems thinking;
- error detection;
- evidence discipline;
- causal reasoning;
- quantitative reasoning;
- implementation/execution;
- design reasoning;
- creative search;
- communication/explanation;
- planning/prioritization;
- metacognitive calibration;
- transfer/adaptation;
- tool/verifier selection;
- uncertainty management.

Facet results are hypotheses. They are useful for routing because two people with similar domain knowledge may need different complementary support.

## Automatic widening

`tools/foil_domains.py` recognizes a broad set of work families in addition to the core profile domains. Current coverage includes, among others:

- pure mathematics, theorem proving/formal methods, optimization/operations research;
- databases/data engineering, cloud/devops/platform, computer vision/graphics, NLP/language technology, AI safety/evaluation;
- healthcare, bioinformatics/computational biology, neuroscience/cognitive science, psychology/behavior;
- education, social sciences, humanities/history, philosophy/ethics;
- business, marketing/sales, accounting/finance, econometrics;
- mechanical, electrical, chemical-process, civil/environmental, aerospace, robotics/control, industrial engineering;
- geospatial/earth science, architecture, manufacturing/fabrication, energy/power, agriculture/food;
- visual media, game design, music/audio, translation/linguistics, technical writing, journalism;
- law/policy, public administration, organizational management, project/program management, product management, entrepreneurship, human factors, operations/logistics, and geopolitics.

The registry only marks **relevance**. It never assigns competence. Arbitrary domains remain supported through explicit observations and custom assessment domains even when no keyword entry exists.

## Prompt-time facet adaptation

The `UserPromptSubmit` hook can now infer both domain relevance and cross-cutting facet relevance. For example, a request to "formalize and red-team this proof, then run a test" can mark formalization, error detection, and execution as currently relevant.

This changes routing context only. A user asking for proof help does not become weak at proof; a user asking for design help does not become strong at design.

## Research rationale

Layer 2 follows several measurement principles rather than one personality typology:

- Evidence-Centered Design treats complex performance tasks as sources of multiple observable features that support proficiency inferences.
- PISA creative-thinking assessment separates generating diverse ideas, generating creative ideas, and evaluating/improving ideas across multiple contexts rather than treating creativity as one scalar trait.
- Consensual Assessment Technique research supports evaluating actual creative products with appropriate independent judgment when fixed answer keys are inappropriate.
- Metacognitive-calibration research supports treating confidence/correctness alignment as separate from first-order task accuracy and testing whether calibration transfers.

See `research/FOIL_PERSONALIZATION_BASIS.md` for references and boundaries.

## When to stop active calibration

Stop asking calibration questions when:

1. the profile is deep enough for the person's actual goals;
2. new probes are no longer changing FOIL's routing or support level materially;
3. remaining coverage gaps are low-value for that person's work;
4. the user wants normal task completion instead of continued assessment.

Naturalistic usage should continue updating the profile after active calibration ends.

## Scientific boundary

Layer 2 is designed to reduce cold-start uncertainty and force transfer/verification evidence. It is **not** a validated intelligence, personality, aptitude, employment, clinical, or diagnostic instrument.

The project still needs prospective validation showing that these profile states predict useful future assistance decisions and outperform a strong non-profile baseline at matched model/tool budget.
