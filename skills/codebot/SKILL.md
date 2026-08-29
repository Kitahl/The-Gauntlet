---
name: codebot
description: Engineering Verification module. Trigger: /power, /codebot, implement, debug, integrate, test, benchmark software behavior, review architecture, or verify an executable claim. Converts software claims into bound failure hypotheses, runnable checks, adversarial discriminators, and scoped receipts.
---

# Engineering Verification

Executable claims should be executed against named failure hypotheses.

## Workflow

1. Inspect the actual repository, interfaces, entrypoints, and prior receipts.
2. Freeze the task, obligation, plan, candidate, scope, invariants, and residual boundary.
3. Derive concrete `FailureHypothesis` records; each needs a trigger, expected symptom,
   failure class, and executable refuter.
4. Reject duplicate semantic hypotheses instead of spending duplicate rounds.
5. Implement the smallest complete change consistent with known invariants.
6. For a substantial change, run direct targeted and regression checks, the real
   entrypoint when applicable, and one selected adversarial discriminator.
7. Record one relevant residual failure class outside the current gate.
8. Emit a claim-scoped receipt containing hashes and verdicts, never trusted prose.

## Adversarial discriminators

Use a discriminator only when it targets a named failure class:

- negative control or mutation;
- property-generated case;
- metamorphic relation;
- differential implementation; or
- environment/integration probe.

A surviving mutation or negative control blocks “fixed.” A passing metamorphic check
establishes only its named relation and scope. Generic fuzzing does not count merely
because it ran.

## Real entrypoint

Exercise the actual CLI, API, hook, service, build invocation, or repository workflow
when relevant. Bind it into the plan. When no real surface exists, record
`NOT_APPLICABLE` with a reason; do not invent one.

## Failure location

Distinguish `TASK_ARTIFACT`, `AGENT_HARNESS`, `TOOL_ENVIRONMENT`, `TEST_ORACLE`, and
`UNKNOWN` through an explicit discriminator. Do not rewrite source merely because a
harness failed, and do not relax an oracle merely because source failed. A changed
harness or oracle creates a new evidence identity.

## Repair boundary

Prefer a local typed repair only when localization is credible, invariants are known,
and the intervention can be independently verified. Otherwise defer for broader
review. Use the neutral candidate gate for exact base/candidate/scope/obligation
binding and independent structural plus semantic verification. Power cannot promote
its own patch; host write/commit authority remains separate.

## Security boundary

Retain constrained known verifier families, trusted executable resolution, active
Python binding, per-check timeouts, `shell=False`, disabled custom commands unless the
outer environment explicitly opts in, and hashed stdout/stderr. An unavailable
mandatory verifier is `UNAVAILABLE`, never omitted or converted to a pass.

## Typed runtime contract

`tools/power_runtime.py` implements `egrt.power.v2` while preserving historical Power
constructors and `verification-plan` receipts. Soul continues to route `ENGINEERING`
automatically to `power`. A green plan covers only its named checks, relations, and
failure classes; it does not establish exhaustive software correctness or benchmark
efficacy. See `docs/specs/POWER_ENGINEERING_SPEC.md`.
