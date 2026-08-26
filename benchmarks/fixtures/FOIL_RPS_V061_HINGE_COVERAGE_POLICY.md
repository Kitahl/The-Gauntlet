# FOIL RPS v0.6.1 hinge-coverage experiment policy

Status: `PROPOSED / DEFAULT-OFF / SHADOW-ONLY / NOT PROMOTED`

This policy supplements, but does not modify, the frozen v0.6.0 prompt fixture.
It addresses the hard-two benchmark failure where a shallow invariant passed for
both the correct and incorrect option and RPS fast-accepted the wrong option.

## Decisive-pass rule

A primary-check `PASS` may recommend `FAST_ACCEPT` only when:

1. the check targets the capsule's named fragile hinge; and
2. either the check is an exact candidate relation, or its expected result for
   the candidate differs from its expected result for a live challenger; and
3. the observed result matches the candidate's expected result.

If both candidates predict the same observation, the check is `SUPPORTING`, not
`DECISIVE`, even when it passes. A supporting pass must request an orthogonal P2
or abstain; it must never fast-accept.

## Authority boundary

The controller returns recommendations only. It cannot mutate the base answer,
authorize execution, call a provider, use a tool, write a profile, or promote
itself. The host must preserve the base answer during this experiment.

The candidate/challenger predictions and hinge designation are supplied inputs.
This policy proves structural discrimination only; it does not prove that those
inputs faithfully capture the semantic decision hinge.

## Frozen stop law

- one P1 observation;
- at most one P2 observation of a different check kind;
- at most one local-repair recommendation;
- zero full restarts.

No production route opens without a new preregistered paired benchmark.
