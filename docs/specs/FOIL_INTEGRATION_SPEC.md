# FOIL integration with typed runtime

FOIL already has persistent profiles, structured onboarding and transfer evidence. vNext does not replace that machinery.

## Role

FOIL is an **adaptation/routing input**. It may recommend which representation, verifier or complement is useful for the current user/task.

## Typed integration

- FOIL observations may produce `ADAPTATION` receipts about profile/calibration state.
- Soul may use those receipts/active profile state to alter routing priority.
- A FOIL-assisted success does not automatically satisfy PROOF, DISCOVERY, ENGINEERING, EVALUATION or other factual obligations.
- Independent transfer remains separate from assisted task success.
- Raw prompts remain outside saved profiles and generic runtime state.

## Boundary

Mastermind remains an external development/audit procedure and is not imported, installed, hooked or persisted in The-Gauntlet runtime.
