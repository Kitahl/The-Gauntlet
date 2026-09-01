# Counterform / FOIL integration with the typed runtime

Counterform, whose stable technical ID is `foil`, already has persistent
profiles, structured onboarding, and transfer evidence. vNext does not replace
that machinery.

## Role

Counterform is an **adaptation/routing input**. It may recommend which
representation, verifier, or complement is useful for the current user/task.

## Typed integration

- Counterform observations may produce `ADAPTATION` receipts about profile/calibration state.
- Crown may use those receipts/active profile state to alter routing priority.
- A Counterform-assisted success does not automatically satisfy PROOF, DISCOVERY, ENGINEERING, EVALUATION, or other factual obligations.
- Independent transfer remains separate from assisted task success.
- Raw prompts remain outside saved profiles and generic runtime state.

## Boundary

Mastermind remains an external development/audit procedure and is not imported,
installed, hooked, or persisted in the BASTION-01 runtime.
