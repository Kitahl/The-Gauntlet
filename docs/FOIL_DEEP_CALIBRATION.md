# FOIL deep calibration — Layer 2

Layer 1 (`tools/foil_assessment.py`) is a broad cold-start screen. Layer 2 (`tools/foil_calibration.py`) exists because a short questionnaire cannot recover the depth of a profile built from repeated real work.

The second layer samples **how the person works** across changed representations, error detection, evidence handling, real artifacts, design, creativity, explanation, tool choice, and confidence—not just which topics they know.

## Start

After applying Layer 1 to a saved profile:

```bash
python tools/foil_calibration.py start --profile alice --out foil_deep_calibration.json
```

The generated plan is profile-dependent. It prioritizes:

- `POSSIBLE_GAP` domains with discriminating changed-representation probes;
- `UNCERTAIN` domains with fresh independent probes;
- `PROMISING_STRENGTH` domains with harder transfer tests;
- real-work and adversarial probes in the most relevant domains;
- cross-cutting probes for formalization, evidence discipline, systems decomposition, design reasoning, creative search, explanation, planning, and verifier selection.

The plan contains **instructions and review contracts, not answer keys**.

## Record evidence

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

Assisted or unverified success is retained as evidence history but cannot create an independent strength.

Duplicate probe IDs are rejected so the same result cannot be counted twice.

## Profile maturity

```bash
python tools/foil_calibration.py status --profile alice
```

The runtime uses four engineering states:

- `NOT_STARTED`
- `CALIBRATING`
- `BROAD_PROFILE`
- `DEEP_PROFILE_READY`

`DEEP_PROFILE_READY` currently requires broad evidence coverage, including:

- 14 independent verified deep probes;
- 4 distinct task domains;
- 8 cross-cutting facets;
- 3 transfer/changed-representation results;
- 2 real-work samples;
- 2 adversarial/error-detection results;
- 8 confidence-bearing results;
- 3 open-production results.

These thresholds are **engineering release gates**, not validated psychometric cutoffs. They exist to stop FOIL from claiming a deep profile based on repeated success in one narrow task family.

## Cross-domain facets

The second layer can maintain evidence about:

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

`tools/foil_domains.py` adds relevance recognition for a wider set of work domains, including healthcare, psychology/behavior, education, social science, humanities/history, philosophy/ethics, business, marketing/sales, finance/accounting, engineering disciplines, robotics/control, geospatial/earth science, architecture, visual media, music/audio, translation/linguistics, journalism, public administration, project/program management, entrepreneurship, manufacturing, agriculture/food, energy/power, and geopolitics.

This registry only marks **relevance**. It never assigns competence.

Arbitrary domains remain supported through explicit profile observations and custom assessment domains even when no keyword registry entry exists.

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
