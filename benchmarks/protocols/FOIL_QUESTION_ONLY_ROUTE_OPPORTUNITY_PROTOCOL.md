# FOIL question-only route-opportunity replay

**Status:** development diagnostic; no efficacy or promotion claim

## Question

Before paying for another model benchmark, can FOIL identify from the question
alone which existing evidence-producing capability *might* apply to each of the
20 historical HLE tasks? This is an opportunity/coverage diagnostic, not a test
that a tool would produce the correct answer.

## Information boundary

The predictor receives exactly `id` and `question` from the sealed item
manifest. Its closed runtime input schema accepts only `schema`, `task_id`, and
`question`. It rejects A0, gold, expected output, correctness, labels, and all
unknown fields. The frozen artifact stores question digests rather than raw
question text.

Only after the prediction artifact is written and content-hashed may the scorer
read `independent_audit.json`. The scorer cannot alter the frozen predictions.
The known 20 questions are development data and are not a holdout.

## v1 route signatures

The deterministic predictor uses positive question-structure signatures for:

- executable program semantics -> `CODE_EXECUTION`;
- explicit mathematical computation -> `SYMBOLIC_COMPUTATION`, with
  `CODE_EXECUTION` as an execution fallback;
- versioned/legal facts -> `WEB_SEARCH`;
- specialized named results -> `SCHOLARLY_SEARCH`;
- proof/universal constraints -> `FORMAL_PROOF`.

Every candidate remains `QUESTION_STRUCTURE_ONLY`, requires a runtime probe,
and has no execution or promotion authority. No provider or tool is called.

## Conservation and failure rules

- Every unique question has exactly one `FOUND | UNSUPPORTED` status.
- All 20 questions must bind to at least one audit row.
- Duplicate task IDs, duplicate audit unit IDs, missing questions, unknown
  question-input fields, or artifact-hash mismatches fail closed.
- The 60 model/configuration rows are reported separately from the 20 distinct
  questions and are not treated as 60 independent questions.
- Capability buckets may overlap and must not be summed.

## Outputs and interpretation

`predictions.json` records the frozen question-only hypotheses. `report.json`
reports overlap with historical base misses and historical rescues. Overlap is
not causal tool effect, verifier applicability, expected rescue probability,
calibration, or promotion evidence.

The decision after this diagnostic is narrow: if the question-only predictor
finds almost no relevant opportunity among historical misses, stop expanding
answer-side verifiers for HLE. If it finds meaningful opportunity, implement
and test the smallest claim-native probes on a new holdout before any live
model benchmark.
