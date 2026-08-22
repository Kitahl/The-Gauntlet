# FOIL universal refinement — Layer 2B

Layer 1 (`tools/foil_assessment.py`) provides a broad cold start. Layer 2A (`tools/foil_calibration.py`) deepens the most relevant domains and cross-cutting facets. Layer 2B (`tools/foil_equalizer.py`) exists to reduce a remaining cold-start problem: two strangers can finish the same onboarding process with very different **evidence breadth**.

Layer 2B therefore does two jobs:

1. **profile equalization** — actively fill missing evidence families without repeatedly testing the same narrow ability;
2. **task policy compilation** — turn profile evidence into how FOIL should help on the current task.

It does not attempt to create an IQ, personality, aptitude, employment, clinical, or diagnostic score.

## Capability families

The equalizer balances independent, verified evidence across six transferable families:

| Family | Examples |
|---|---|
| reasoning / representation | formalization, quantitative reasoning, verbal qualifier preservation, structural/spatial transformation, data interpretation |
| epistemic / scientific | evidence scope, causality, experimental design, benchmark validity, uncertainty, error detection |
| systems / execution | decomposition, implementation, integration, verifier/tool choice |
| creation / communication | design, mechanism-diverse creativity, explanation/self-explanation |
| strategy / integration | prioritization, conflicting-requirement synthesis |
| learning / metacognition | calibration, transfer, learning diagnosis, delayed retrieval |

A family gate counts **distinct verified facets**, not repeated success on one question type.

## Why this is different from a longer questionnaire

The equalizer is adaptive:

- `PROMISING_STRENGTH` → harder changed-context transfer;
- `POSSIBLE_GAP` → discriminator designed to separate knowledge, retrieval, ambiguity, and execution-slip explanations;
- `UNCERTAIN` → changed-representation independent probe;
- relevant but unsampled domain → real-work probe;
- missing capability family → content-balanced cross-domain probe.

A self-estimate/performance mismatch generates a **neutral** fresh probe. FOIL does not tell the person that it expects them to be overconfident or underconfident.

## Highest-fidelity gate

`HIGH_FIDELITY_PROFILE` is intentionally impossible to earn from one immediate questionnaire session alone. It requires:

- required evidence-family coverage;
- evidence in relevant work domains;
- multiple representations;
- transfer evidence;
- real-work samples when relevant domains exist;
- adversarial/error-detection evidence;
- confidence-bearing results;
- at least one **delayed unassisted retrieval** event.

The delayed retrieval probe is issued with a `not_before` timestamp. Recording it early is rejected.

These are engineering coverage gates, not validated psychometric cutoffs.

## Start

After Layer 1 and optionally Layer 2A:

```bash
python tools/foil_equalizer.py start \
  --profile alice \
  --assessment-report foil_assessment_report.json \
  --out foil_equalizer_plan.json
```

Inspect current coverage:

```bash
python tools/foil_equalizer.py status --profile alice
```

Record an evidence-backed result:

```bash
python tools/foil_equalizer.py record \
  --profile alice \
  --probe-id cross_domain:experiment_design:1 \
  --family epistemic_scientific \
  --facet experimental_design \
  --domain cross_domain \
  --kind experiment_design \
  --outcome pass \
  --assistance none \
  --verified \
  --confidence 80 \
  --representation preregistered-design
```

The metadata must match the issued probe contract. Assisted or unverified results are retained as history but do not satisfy independent evidence gates.

## Task policy

The equalizer compiles profile evidence into a current-task policy:

```bash
python tools/foil_equalizer.py policy \
  --profile alice \
  --task "Check the latest library version and repair the failing build" \
  --stakes high --goal learning --urgency urgent
```

The policy separates two controls that must not be conflated:

- **verification intensity** — how strongly the system must check the answer;
- **pedagogical friction** — how much independent work FOIL should require from the person before helping.

A high-stakes urgent task can therefore request `maximum` verification while imposing `minimal` learner friction.

## Preferences are not aptitude

Style/self-report answers may tune presentation and workflow. They do not become claims such as “visual learner” or evidence that a matching presentation style will improve learning. Competence updates require performance evidence.

## Automatic widening

`tools/foil_domains.py` provides relevance recognition across scientific, engineering, computing, business, creative, public-sector, legal/compliance, operational, and other work families. The registry is open-ended: arbitrary domains remain supported through explicit observations even when no keyword rule exists.

Domain relevance is routing metadata, not competence.

## Stop condition

Active refinement should stop when:

1. the profile is broad enough for the person's actual goals;
2. new probes no longer materially change support/routing policy;
3. remaining missing families are irrelevant to the person's work;
4. the person wants normal task completion rather than active assessment.

Naturalistic real-work evidence continues updating FOIL afterward and outranks older onboarding priors.

## Scientific boundary

Layer 2B is designed to make stranger profiles more comparable in **evidence coverage** and to force transfer/retention evidence before strong personalization. It does not establish psychometric validity or that a stranger profile is equivalent to months of naturalistic observation.

The decisive future experiment remains whether the personalized system improves delayed, independent transfer relative to equally capable AI assistance without the profile mechanisms.
