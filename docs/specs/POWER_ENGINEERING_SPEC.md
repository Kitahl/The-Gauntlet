# Power / Engineering Verification — vNext engineering specification

## 1. Authority boundary

Power owns executable engineering evidence for implementation correctness, regression
behavior, real entrypoints, integration/environment behavior, software invariants, and
named adversarial failure classes. Power does not own factual research conclusions,
proof authority, benchmark efficacy, host writes, merges, or self-promotion of a repair.

Soul continues to route `ENGINEERING` obligations to `power`. The host supplies a frozen
`VerificationPlan`; Power executes that plan and emits a claim-scoped `power` receipt.
The receipt has `execution_authorized = false` and cannot commit or adopt a candidate.

## 2. Typed failure hypotheses

`FailureHypothesis` binds the following fields into a canonical SHA-256 content hash:

- `hypothesis_id`, `task_id`, `obligation_id`, and `plan_id`;
- optional `candidate_hash` and `scope_hash`;
- `failure_class`, trigger, expected symptom, and concrete refuter;
- load-bearing status, declared status, and canonical metadata.

Power validates the content hash immediately before execution. Task, obligation, plan,
candidate, and scope bindings must exactly match the enclosing plan. A mismatch fails
closed. Semantically duplicate hypotheses are rejected using normalized failure class,
trigger, symptom, refuter, and binding fields; changing an ID or cosmetic metadata does
not create another adversarial round.

## 3. Typed check contract

`VerificationCheckType` supports:

- `DIRECT_TARGETED`
- `REGRESSION`
- `REAL_ENTRYPOINT`
- `NEGATIVE_CONTROL`
- `MUTATION`
- `PROPERTY_GENERATED`
- `METAMORPHIC`
- `DIFFERENTIAL`
- `ENVIRONMENT_INTEGRATION`

Every Power v2 check names its failure hypothesis and failure class, executable oracle,
expected invariant, expected support signal, and expected failure/refutation signal.
Checks against load-bearing hypotheses are mandatory when applicable. A generic fuzz,
mutation, or property run without that binding is not an admitted Power v2 check.

Historical `VerificationCheck` and `VerificationPlan` positional constructors remain
accepted. Historical plans retain the `power` module and `verification-plan` receipt
action, output hashes, coverage matrix, and four-verdict behavior.

## 4. Substantial-change minimum

A plan declaring `substantial_change = true` must include:

1. an applicable direct targeted check;
2. an applicable regression check;
3. an applicable real-entrypoint check when a real runtime surface exists;
4. at least one applicable adversarial discriminator from mutation, negative control,
   property generation, metamorphic, differential, or environment integration; and
5. at least one named residual failure class outside the current gate.

Entrypoint applicability is explicit. A relevant entrypoint is bound by exact label to
the plan and check. When no real entrypoint exists, Power requires both a reason and a
`REAL_ENTRYPOINT` check recorded as `NOT_APPLICABLE`; it does not invent a surface.
Trivial/non-substantial changes do not automatically inherit this minimum.

## 5. Metamorphic verification

A `METAMORPHIC` check additionally binds:

- `relation_id`;
- input transform;
- expected output relation; and
- applicable scope.

A successful execution records `HOLDS` only for that relation and scope. A failed
load-bearing relation records `VIOLATED`, supports the named failure hypothesis, and
produces `ISSUE`. Power never emits a generic “metamorphic tested” badge.

## 6. Mutation and negative controls

Mutation and negative-control checks declare a discriminator-success exit separately
from the normal success exit. When the deliberately broken target reaches the
specified discriminator exit, Power records `KILLED`. When it instead reaches the
normal success exit, Power records `SURVIVED` and produces `ISSUE` for a load-bearing
claim.

Power rejects a negative control that silently assigns the same exit to normal success
and discriminator success. An external mutation harness may use a shared exit only
when that harness is explicitly bound in metadata. This prevents:

`original passes + mutation also passes = CLEARED`.

## 7. Artifact, harness, environment, and oracle diagnosis

Checks may record one evidence-conditioned origin candidate:

- `TASK_ARTIFACT`
- `AGENT_HARNESS`
- `TOOL_ENVIRONMENT`
- `TEST_ORACLE`
- `UNKNOWN`

A non-`UNKNOWN` origin requires an explicit attribution discriminator. The resulting
receipt labels this as a declared diagnostic candidate, not an automatically proven
fact. Changing a command, harness metadata, oracle, entrypoint, relation, or expected
signal changes the check and plan evidence identities.

## 8. Local typed repair principle

`select_repair_strategy` returns `LOCAL_TYPED` only when fault localization is credible,
invariants are known, and the proposed local intervention can be independently
verified. Otherwise it returns `DEFER_OR_BROADER_REVIEW`. This preference is bounded;
it is not a universal claim that local edits are always correct.

## 9. Neutral repair admission

`verify_repair_candidate` delegates to `egrt_candidate_gate.decide_admission`. Admission
requires exact base, candidate, scope, obligation-set, and environment bindings;
independent producer, structural-verifier, and semantic-verifier identities; and both
structural and semantic passes. Even `COMMITTABLE` retains:

- `execution_authorized = false`;
- `host_commit_required = true`; and
- no automatic source write or promotion.

Power may propose or verify a candidate but cannot certify and promote its own repair.

## 10. Execution security

Power preserves the existing execution boundary:

- `shell=False` for every subprocess;
- constrained known verifier kinds and command shapes;
- active `sys.executable` binding for Python verifier families;
- trusted PATH resolution for direct tools;
- custom commands disabled unless the outer environment explicitly sets
  `EGR_POWER_ALLOW_CUSTOM_COMMANDS=1`;
- `-c`, warning-module imports, and plugin-loading flags blocked in constrained Python
  module families;
- per-check timeouts;
- `UNAVAILABLE` when a mandatory verifier cannot safely execute; and
- SHA-256 stdout/stderr hashes instead of trusting prose output.

`python-script` is a constrained family for a real `.py` entrypoint. It requires the
active interpreter and an existing script path; arbitrary module names and shell
interpretation remain unavailable.

## 11. Verdict and receipt semantics

Power evaluates each named failure hypothesis from its bound checks:

- all applicable checks clear → `REFUTED`;
- any check issues → `SUPPORTED`;
- missing capability → `UNAVAILABLE`;
- timeout or insufficient discrimination → `INCONCLUSIVE`; and
- explicit irrelevance → `NOT_APPLICABLE`.

A supported load-bearing hypothesis forces `ISSUE`. An unavailable load-bearing
hypothesis forces `UNAVAILABLE` unless a stronger `ISSUE` exists. An inconclusive
load-bearing hypothesis forces `UNKNOWN`.

Receipts persist plan identity, evidence identity, check/environment identities,
coverage, hypothesis outcomes, substantial-change applicability, residual failure
classes, exit/timing data, and stdout/stderr hashes. They do not persist raw process
output. A green receipt covers only its named checks, relations, and failure classes.

## 12. Automatic production path

The bounded production path remains:

`Soul ENGINEERING route → frozen VerificationPlan → named FailureHypothesis set →`
`direct/regression/entrypoint checks → selected adversarial discriminator → residual`
`coverage record → claim-scoped Power receipt → host-controlled release decision`.

Power performs no unbounded test expansion and does not silently omit an expensive
mandatory verifier. Tool absence is `UNAVAILABLE`, not a synthetic pass.

## 13. Efficacy boundary

The typed runtime establishes mechanical binding, execution, discrimination semantics,
and authority separation. It does not establish that a chosen test suite is complete,
that a chosen oracle is semantically correct, that mutation score predicts production
reliability, or that the local-repair preference improves outcomes across repositories.
Those remain unproven efficacy claims requiring separate evaluation.
