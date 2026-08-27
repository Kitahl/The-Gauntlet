# Neutral challenge layer — engineering specification

Status: **SHADOW / mechanical implementation only**  
Schema: `egrt.challenge.v1`  
Baseline: `main@4f088d688fa9e25b4608f44000a5d9812efa45f9`

## Decision

Every domain module may own a small, candidate-directed challenge adapter. The
adapters and optional FOIL controller communicate only through the neutral challenge
contract. A non-FOIL module must not import a `foil_*` module.

A challenge is a proposal, not evidence. It cannot satisfy `PROOF`, `DISCOVERY`,
`SYNTHESIS`, `ENGINEERING`, `EVALUATION`, `ASSURANCE`, `PREFLIGHT`, or `REVIEW`.
Only a valid receipt from the declared claim-native module may resolve it. A
resolution affects the challenge gate but never replaces the original domain receipt.
External writes and candidate adoption remain host actions.

## Additive compatibility

`egrt.runtime.v1` remains unchanged. Existing `TaskState`, `Obligation`, `Receipt`,
`RuntimeEvent`, `ArtifactRef`, `EvidenceRef`, and four-state verdict semantics remain
valid. New state is stored separately under:

- `runtime/challenges/<challenge_id>.json`
- `runtime/challenge_resolutions/<resolution_id>.json`

Old tasks and receipts require no migration. Setting challenge mode to `off` ignores
the additive state.

## Objects

### `ChallengeRequest`

Required fields:

`challenge_id`, `task_id`, `obligation_id`, `target_module`, `origin`, `kind`,
`hypothesis`, `alternative`, `refuter`, `consequence_if_true`, `load_bearing`,
`required_capability`, `candidate_hash`, `scope_hash`, `obligation_set_hash`,
`proposer`, `proposer_provenance`, `information_rank`, `risk_rank`, `cost_rank`,
`metadata`, and `schema`.

Origins are `USER`, `MODULE_NATIVE`, `FOIL`, `GAUNTLET`, and `COUNCIL`.

Kinds are:

- `ALTERNATE_FORMALIZATION`
- `CLAIM_NEGATION`
- `COUNTEREXAMPLE`
- `ASSUMPTION_KNOCKOUT`
- `REPRESENTATION_SWAP`
- `SOURCE_CONFLICT`
- `RETRIEVAL_REFRAME`
- `NOVELTY_COSTUME`
- `FAILURE_CLASS`
- `METAMORPHIC_RELATION`
- `BASELINE_OR_ESTIMAND`
- `CONTAMINATION`
- `STATE_DRIFT`
- `DECISION_REVERSAL`
- `REVIEW_DIVERSITY`
- `OUTPUT_CONTRACT`

### `DiscriminatorPlan`

Required fields:

`plan_id`, `challenge_id`, `mode`, `action`, `verifier_module`,
`required_capability`, `expected_support_signal`, `expected_refute_signal`,
`input_artifacts`, `timeout_seconds`, `max_cost_rank`, `metadata`, and `schema`.

Selection uses ordinal/Pareto dominance. Available, more discriminating,
higher-information and higher-risk-reduction plans dominate only when they are no
more costly or irreversible. Incomparable plans remain unresolved for a module/host
choice. Duplicate plans with the same action, capability, signals, and inputs do not
consume another challenge round.

### `ChallengeResolution`

Required fields:

`resolution_id`, `challenge_id`, `state`, `outcome`, `verifier_receipt_id`,
`verifier_module`, `evidence_hash`, repeated candidate/scope/obligation-set hashes,
`resolver`, `resolver_provenance`, `reason`, `metadata`, and `schema`.

States are `PROPOSED`, `SELECTED`, `RUNNING`, `RESOLVED`, `UNRESOLVED`,
`UNAVAILABLE`, and `DISMISSED_NOT_APPLICABLE`. Outcomes are `SUPPORTS_BASE`,
`REFUTES_BASE`, `SCOPE_SPLIT`, and `INCONCLUSIVE`.

A `RESOLVED` record must reference an integrity-valid receipt from the declared
verifier module for the same task/obligation. `SUPPORTS_BASE` requires a `CLEARED`
receipt. `REFUTES_BASE` requires an `ISSUE` receipt. All three binding hashes must
match exactly.

## Modes

| Mode | Storage and execution | Release effect |
|---|---|---|
| `off` | Challenge state is ignored. | Existing behavior. |
| `shadow` | Store proposals/resolutions and calculate the counterfactual gate. | Never blocks. Default. |
| `enforced` | Apply load-bearing challenge severity. | `ISSUE`, `UNAVAILABLE`, or `UNKNOWN` as below. |

`EGR_CHALLENGE_MODE=off|shadow|enforced` overrides repository configuration.

Default configuration:

```json
{
  "challenge": {
    "mode": "shadow",
    "max_total_per_obligation": 4,
    "max_load_bearing_per_obligation": 2,
    "max_selected_discriminators": 2,
    "allow_foil_proposals": true,
    "require_claim_native_receipt": true,
    "block_on_unavailable_load_bearing": true,
    "persist_raw_text": false
  }
}
```

## Gate truth table

For the challenge gate alone:

| Worst load-bearing state/outcome | Enforced result |
|---|---|
| none, dismissed, or all `SUPPORTS_BASE` | `CLEARED` |
| proposed, selected, running, unresolved, inconclusive, or `SCOPE_SPLIT` | `UNKNOWN` |
| mandatory verifier unavailable | `UNAVAILABLE` |
| valid `REFUTES_BASE` | `ISSUE` |
| corrupt or mismatched resolution binding | `ISSUE` |

The Soul release gate must later combine this with the current correct-module domain
receipt. A green challenge gate alone is not release evidence.

## Events

The store emits:

- `challenge.proposed`
- `challenge.selected`
- `challenge.running`
- `challenge.resolved`
- `challenge.unresolved`
- `challenge.unavailable`
- `challenge.dismissed`

Resolution events include the resolution ID, outcome, linked receipt ID, evidence
hash, and all binding hashes. Generic state never persists raw prompts or unrestricted
raw tool output.

## Authority and dependency invariants

1. No non-FOIL runtime imports `foil_*`.
2. FOIL-origin challenges remain proposals and do not execute.
3. A challenge or resolution never clears the original obligation.
4. The candidate producer cannot act as structural or semantic verifier.
5. Structural and semantic verifiers must be distinct.
6. A `COMMITTABLE` candidate still has `host_commit_required=true` and
   `execution_authorized=false`.
7. `UNKNOWN` and `UNAVAILABLE` never collapse to `CLEARED`.
8. Mechanical validity is not evidence of behavioral efficacy.

## First implemented module

Mind vNext is the first domain adapter. Soul, Gauntlet, Space, Reality, Power, Time,
Meditate, Council, and the optional FOIL bridge remain separate follow-on work orders.
The repository must remain in SHADOW until a prospective controlled evaluation
supports narrower enforcement.
