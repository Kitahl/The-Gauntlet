# FOIL deterministic persona and assistance validation v1

**Date:** 2026-08-26
**Classification:** `DETERMINISTIC_SIMULATED_PERSONA_CONFORMANCE_ONLY`

## Question

Does the PERSON-side software obey the current FOIL contract when evidence,
execution ownership, recency, task intent, and required assistance are known?
This is a software/specification test. It is not a claim that FOIL improves
human learning or that scripted people represent production users.

## Frozen design

- Six scripted personas, 15 sessions each (90 rows total).
- Each persona declares a ground-truth competence trajectory, independent-task
  outcomes, a minimum effective assistance rung per session, execution owner,
  and verifier availability.
- The selector receives no answer text and no claimed-strength field.
- Teaching starts at `A1_MICRO_HINT`.
- A failed non-probe attempt raises the persistent floor by one rung.
- An A0 ownership probe temporarily lowers assistance but preserves the floor.
- Only verified, user-owned A0 outcomes can change the load-bearing competence
  estimate. Assisted, unverified, and tool-owned successes have weight zero.
- Provider calls, external bot calls, tokens, profile writes, and answer
  mutations are all fixed at zero.

Artifacts:

- `benchmarks/fixtures/foil_personas_v1.json`
- `benchmarks/harness/foil_persona_simulation.py`
- `tests/test_foil_persona_simulation.py`
- `tools/foil_assistance_policy.py`

## Kill conditions

The run exits nonzero if any adversarial persona earns a false strength, profile
distance diverges, the final fade contract fails, over-assistance persists after
an earned strength classification, or under-assistance occurs outside a declared
ladder/probe trial.

## Result

The deterministic run passed all five named kill conditions. Report SHA-256:
`fbcd6c202606f79e991a2b5407e9a6b294f7284c99f75ca0d80980e0ee1bc465`.

| Metric | Result |
|---|---:|
| Personas / sessions | 6 / 90 |
| Adversarial fooled rate | 0.00% |
| Fade-contract correctness | 100.00% |
| Mean profile distance, initial → final | 0.2417 → 0.1267 |
| Persona distance non-increasing | 100.00% |
| Brier score | 0.1338 |
| Overall over-assistance | 22.22% |
| Over-assistance after earned strength | 0.00% |
| Raw under-assistance | 26.67% |
| Declared ladder/probe-trial under-assistance | 26.67% |
| Unplanned under-assistance | 0.00% |
| Provider calls / tokens / mutations | 0 / 0 / 0 |

The 22.22% overall over-assistance is not hidden or certified as acceptable. It
is the synthetic cost of cold-start conservatism while the estimator waits for
four independent outcomes, plus assistance retained between ownership probes.
The benchmark only establishes that this excess does not persist after the
configured strength gate. A real-user pilot is still required to decide whether
the cold-start/probe schedule is useful.

An earlier exploratory selector started hard tasks at A3 and measured 62.22%
over-assistance. That design was rejected. Its fixture and state semantics were
then strengthened to encode a per-session minimum effective rung, so 62.22% and
22.22% are defect-discovery measurements, not a controlled efficacy comparison.

## Reproduction

```powershell
python -m unittest tests.test_foil_assistance_policy tests.test_foil_assistance_replay tests.test_foil_persona_simulation
python benchmarks/harness/foil_persona_simulation.py
```

## Non-claims

- No evidence that FOIL improves human learning.
- No calibration on real people or production traffic.
- No authority to write a real profile or change a user's answer.
- No claim that the scripted outcome sequences are behaviorally realistic.
