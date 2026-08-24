# FOIL real-claim coverage — tiny development pilot

Status: **preregistered development procedure; not calibration or promotion**

## Purpose

Before any large formalization audit, hand-classify a few existing load-bearing
claims to learn whether the measurement scheme is usable and whether routable
coverage is visibly nonzero. This is a procedure smoke test, not an estimate with
useful precision.

## Frozen sample

Select exactly five de-identified, low-stakes claims from already-existing project
artifacts before classifying them:

1. one arithmetic or numeric claim;
2. one executable software-behavior claim;
3. one exact repository/configuration claim;
4. one semantic scope/quantifier claim;
5. one underspecified or genuinely undecidable claim.

Record source-artifact digest, claim locator, why the claim is load-bearing, and a
digest of the adjudication sheet. Do not add convenient claims after seeing the
route labels.

## Labels

Each claim receives exactly one primary route label:

- `EXECUTION_CLASS`: exact calculation, schema, test, or exact local query;
- `TRANSLATION_CLASS`: a decidable check exists but needs semantic translation;
- `SEMANTIC_ONLY`: no admitted mechanical predicate is available;
- `UNDECIDABLE_OR_UNDERSPECIFIED`;
- `UNKNOWN`.

Separately record whether a hypothetical extractor noticed the claim. Missing
claims count against extraction recall and cannot be rescued by compiler coverage.

## Report

Report raw counts only:

- routable claims / 5;
- execution-class / translation-class / semantic-only / unknown counts;
- observed-error routability when an independently known error exists;
- extraction noticed / omitted counts;
- adjudication minutes and disagreements.

Do not report confidence bounds, a fidelity floor, population recall, expected
residual reduction, or return on a large audit budget. The only permitted result
is a descriptive five-row table plus measurement-procedure defects found.
