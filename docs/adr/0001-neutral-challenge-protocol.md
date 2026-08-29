# ADR-0001: Neutral challenge protocol; no FOIL imports in domain modules

- Status: accepted for SHADOW implementation
- Date: 2026-08-26
- Baseline: `main@4f088d688fa9e25b4608f44000a5d9812efa45f9`
- Source decision: EGR-FOIL-INT-001

## Context

FOIL contains useful task-local gap, minimum-discriminator, binding, fail-closed, and
authority-separation mechanisms. Importing FOIL directly into each domain module
would couple factual verification to personalization/adaptation state and make the
incremental value of FOIL unidentifiable.

## Decision

Create additive `egrt.challenge.v1` contracts and storage. Domain modules own native
challenge adapters against that neutral protocol. FOIL may later translate at most one
non-redundant task-local proposal through the same interface, but it remains optional
and shadow-only.

No non-FOIL module may import `foil_*`. Challenge proposals and resolutions never
replace domain receipts or grant write/commit authority.

## Consequences

- Existing runtime receipts remain valid.
- Candidate/scope/obligation bindings become mechanically testable.
- Native module benefit can be measured before FOIL is composed.
- Soul and Gauntlet wiring is a later work order; Mind is implemented first.
- Enforcement requires prospective evidence and an explicit rollback criterion.
