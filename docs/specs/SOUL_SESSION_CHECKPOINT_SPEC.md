# Soul durable session and checkpoint contract

Status: **implemented control-plane contract; no domain or release authority**  
Schemas: `egrt.soul.session.v1`, `egrt.soul.session-checkpoint.v1`,
`egrt.soul.session-resume.v1`

## 1. Purpose

Soul may be interrupted after planning and before every selected obligation has a
claim-native receipt. A host therefore needs a durable way to remember where its
control loop stopped without treating remembered progress as evidence. This contract
adds an append-only, content-addressed session lineage around the existing automatic
Soul planner.

A session is a bounded control object. It never:

1. executes a routed action;
2. clears an obligation;
3. validates a domain receipt;
4. authorizes candidate adoption or external writes;
5. grants release authority; or
6. turns a host progress assertion into evidence.

## 2. Persisted objects

### 2.1 Session head

`runtime/soul_sessions/<session_id>.json` contains the current head. Every head is
sealed by a canonical SHA-256 hash and binds the requested and resolved task IDs, the
validated supersession chain, task and obligation-set snapshots, optional route plan,
selected obligations, evidence and authority snapshots, generation, checkpoint head,
and explicit zero-authority fields.

### 2.2 Immutable revisions

Every generation is written once to
`runtime/soul_session_revisions/<session_id>/<generation>.json`. A current head may
advance, but an earlier generation is never overwritten.

### 2.3 Immutable checkpoints

`runtime/soul_session_checkpoints/<checkpoint_id>.json` binds the generation, parent
checkpoint hash, task/route/evidence/authority snapshots, bounded cursor,
content-addressed artifact references, and host-observed obligation IDs. Host-observed
progress is labelled `HOST_HINT_ONLY`; it cannot satisfy an obligation.

### 2.4 Idempotency

An optional caller idempotency key is persisted only as a hash. Reusing it with the
same complete binding returns the existing session. Reusing it with different bound
inputs fails closed.

## 3. State machine and concurrency

`OPEN -> PAUSED -> OPEN -> CLOSED`

Additional terminal states are `CANCELLED` and `INVALIDATED`. Every checkpoint and
terminal transition requires exact generation compare-and-swap. Stale writers cannot
overwrite a newer generation. Session mutation is bounded and atomic; checkpoint,
metadata, cursor, and artifact-reference counts are finite.

## 4. Resume validation

A resume revalidates:

1. task resolution and complete supersession chain;
2. task and obligation-set snapshots;
3. route-plan hash and selected obligations;
4. latest checkpoint seal and generation;
5. authority snapshot; and
6. evidence snapshot at the latest checkpoint boundary.

Drift produces a typed reason (`STALE_TASK`, `STALE_ROUTE`, `STALE_AUTHORITY`, or
`STALE_EVIDENCE`), persists an immutable `INVALIDATED` generation, and requires a fresh
Soul plan/session.

Resume output is a manifest only. It always states
`resume_authorized=false`, `execution_authorized=false`,
`domain_evidence_authority=false`, and `release_authority=false`.

## 5. Evidence advancement

Evidence may advance only at an explicit checkpoint. The checkpoint records the
previous and current evidence hashes. This observation does not judge the evidence;
ordinary claim-native receipt validation and Soul release checks remain mandatory.

## 6. Privacy and metadata boundary

Caller metadata is JSON-only, depth/size bounded, and recursively rejects reserved
task, release, identity, authority, raw-prompt, raw-tool-output, content-hash, and
`soul_*` fields before persistence. Artifact IDs are hashed; only their supplied
content hashes and small kind codes remain.

## 7. Public API

`tools/soul_session.py` exports:

- `open_session`
- `checkpoint_session`
- `resume_session`
- `close_session`
- `list_session_frontier`

Specialist claim-native modules remain unchanged.

## 8. Claim boundary

Mechanical tests can establish sealing, immutable revisions, idempotency, generation
CAS, drift invalidation, bounded persistence, and lack of represented authority. They
do not establish complete real-world obligation discovery, correct host execution,
harmless context reuse, globally optimal routing, scientific validity, lower cost, or
improved outcomes.
