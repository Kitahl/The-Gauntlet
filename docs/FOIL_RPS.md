# FOIL Residual Parity Search (RPS)

Status: v0.6.0 benchmarked as a frozen prompt; v0.6.1 implemented as a
default-off, observation-only controller; neither is promoted.

## Plain-language explanation

RPS is a small second look, not a second full answer.

Imagine solving a problem by crossing a few stepping stones. Before committing,
FOIL writes down the one to three stones carrying most of the answer and marks
the shakiest one. It then asks one cheap question whose answer should differ if
that stone is wrong. If the check truly separates the leading answer from a live
alternative, it can recommend keeping the answer or repairing only the reasoning
after that stone. If the check does not separate them, FOIL gets one different
check and then stops or abstains. It does not loop through full rewrites.

The purpose is to catch a wrong reasoning route for much less than the token cost
of solving the entire problem again.

## Whole system versus subparts

The v0.6.0 experiments used RPS **as one whole prompt procedure**:

1. retain a compact candidate and one to three hinges;
2. run one P1 parity check;
3. fast-accept on a pass, or make one local repair on a failure;
4. run P2 only when P1 is uncertain, inapplicable, or the repair creates a new
   hinge;
5. use one discriminator if two candidates remain;
6. stop without a full restart.

The logged subparts were telemetry inside that prompt. They were not separately
implemented or independently ablated, so the previous benchmark cannot say
which subpart helped or hurt.

v0.6.1 begins separating one load-bearing subpart into deterministic code:
**hinge coverage and fast-accept admission**. A passing check is now:

- `SUPPORTING` if the candidate and challenger predict the same result;
- `DECISIVE` only if it targets the fragile hinge and distinguishes the two
  predictions, or tests an exact candidate relation.

Only `DECISIVE + PASS` can produce a non-authoritative `FAST_ACCEPT`
recommendation. `DECISIVE + FAIL` can recommend one local repair. Everything
else requests P2 or abstains.

## Runtime boundary

[foil_rps.py](../tools/foil_rps.py) is a pure state machine. It receives digests
for a reasoning capsule and already-performed observations. It does not create
checks, solve a task, call a model, use the network, run code, edit an answer, or
write a profile.

[foil_policy.py](../tools/foil_policy.py) exposes the controller through an
append-only `OBSERVE_RESIDUAL_PARITY` action. The action appears only when:

- the explicit feature flag is enabled;
- the ordinary FOIL policy has already decided it can stop;
- the task is closed-book technical reasoning with a viable candidate; and
- no stronger completed claim-native verifier is present.

The ordinary `STOP` remains in force. Shadow RPS cannot bypass it or change the
base answer. The host-facing `observe_residual_parity` method rejects calls whose
policy decision does not contain that explicit action, so declaring the module
enabled is not enough to bypass runtime admission.

## What this implementation does not prove

The state machine can prove that its transition law is followed. It cannot prove
that a model or host named the correct fragile hinge or supplied semantically
faithful candidate/challenger predictions. That upstream binding remains the
strongest untested assumption and needs a prospective benchmark.

Lean is not used. A later Lean model could formally prove the finite transition
invariant (for example, that fast accept implies `DECISIVE + PASS`), but Lean
would still not establish that a natural-language hinge was the right one unless
the semantic mapping were independently formalized.

## Promotion rule

The frozen v0.6.0 benchmark remains history. v0.6.1 needs a new preregistered,
paired benchmark with token accounting, answer-identity checks, failure-class
labels, and an ablation of hinge coverage before any active routing or answer
mutation is considered.
