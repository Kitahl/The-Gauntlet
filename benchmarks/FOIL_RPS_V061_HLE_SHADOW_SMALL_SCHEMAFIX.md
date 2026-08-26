# FOIL RPS v0.6.1 — small hinge-gate benchmark, schema-fixed revision

Date: 2026-08-25

Status: preregistered tiny shadow smoke; no calibration or promotion authority.

This revision supersedes only the execution compatibility of
`FOIL_RPS_V061_HLE_SHADOW_SMALL.md`. The first attempt stopped at its first
positive control because the live structured-output API rejected the
`uniqueItems` keyword. It produced no answer and no benchmark prediction.

The sole schema change is removal of `uniqueItems` from the JSON Schema. The
closed Python parser still rejects duplicate hinge identifiers. All questions,
frozen BASE candidates, prompts, model configurations, scoring rules, authority
boundaries, six-call cap, metrics, and non-claims remain unchanged.

This revision uses a new output directory and never retries or overwrites the
failed attempt. Across both revisions there may be at most seven provider request
attempts: one rejected-schema control plus six calls in this revision.
