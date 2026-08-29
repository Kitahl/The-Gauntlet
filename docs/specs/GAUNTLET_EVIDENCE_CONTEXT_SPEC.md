# Gauntlet evidence-context hardening — additive specification

## 1. Scope

This specification adds an opt-in evidence-context layer to **Infinity Gauntlet / Process Assurance**. It does not replace or reinterpret `egrt.runtime.v1`, and it does not grant Gauntlet claim-native authority.

```text
authority = ASSURANCE_ONLY
target_domain_clearance_authorized = false
```

Historical receipts remain integrity-readable under their original schema. A historical receipt without the new envelope is labelled `LEGACY_UNQUALIFIED_READABLE`; no new admission status is inferred from it.

The research mechanisms motivating this slice are implementation patterns and benchmark axes, not evidence that Gauntlet improves behavioral outcomes.

## 2. Orthogonal evidence qualifiers

The content-addressed envelope records six separate dimensions:

```text
execution_status
  CLAIMED | EXECUTED | TESTED

validity_status
  UNCHECKED | FORMAL_PASS | STATISTICAL_PASS | DETERMINISTIC_PASS | FAIL

fidelity_status
  NOT_APPLICABLE | UNCHECKED | PASSED | FAILED

independence_status
  SELF | CROSS_CHECKED | INDEPENDENT

provenance_status
  MISSING | PARTIAL | BOUND

admission_status
  PENDING | ADMITTED | REJECTED
```

No dimension is converted into another. In particular:

- `FORMAL_PASS` does not imply `fidelity_status=PASSED`;
- `provenance_status=BOUND` does not imply validity;
- `independence_status=INDEPENDENT` does not imply admission;
- cryptographic integrity does not imply scientific truth.

The object is persisted under:

```text
EvidenceRef.metadata["gauntlet_evidence_context"]
```

with schema:

```text
egrt.gauntlet.evidence-context.v1
```

Its `content_hash` is canonical SHA-256 over every field except `content_hash` itself. Unknown top-level fields fail typed parsing; explicitly namespaced additions belong in `extensions`.

## 3. Opt-in requirement profile

A task or obligation opts into the stronger gate through:

```text
metadata["gauntlet_evidence_requirement"]
```

Supported requirements include:

- tested rather than merely claimed execution;
- formalization-fidelity evidence;
- independent verification;
- bound provenance;
- evaluator-context identity;
- named load-bearing evaluator fields;
- current source artifact hash;
- current rerun generation;
- registered deterministic transition rules.

Obligation metadata overrides task-level defaults. Omitting the profile preserves historical compatibility. Providing a malformed profile is a Process Assurance issue.

## 4. Proof-or-stop lifecycle cause

A lifecycle transition is not caused by model prose such as “tested,” “reviewed,” “fixed,” “complete,” or “ready.” A typed transition names exactly one cause:

```text
BOUND_RECEIPT
DETERMINISTIC_RULE
```

A `BOUND_RECEIPT` transition must bind:

- the exact receipt ID;
- the source-state hash;
- the target state;
- the evidence/rerun generation.

A `DETERMINISTIC_RULE` transition must bind:

- rule ID and version;
- source-state hash;
- target state;
- evidence/rerun generation;
- a host-registered `rule_id@version` entry in the requirement profile.

A caller cannot register a rule merely by naming it in the evidence envelope.

When an envelope declares `admission_status=ADMITTED` while another required dimension is unresolved, Gauntlet returns an issue for contradictory admission rather than accepting the self-assertion.

## 5. Formal validity versus fidelity

Gauntlet does not duplicate Mind's proof logic. It inspects the separate qualifier and binding supplied at the release boundary.

For a fidelity-required obligation:

```text
FORMAL_PASS + fidelity_status=FAILED     -> ISSUE
FORMAL_PASS + fidelity_status=UNCHECKED  -> UNKNOWN or contradictory admission ISSUE
FORMAL_PASS + fidelity_status=PASSED     -> continue checking other dimensions
```

A kernel-verified artifact cannot become fully admitted factual/process evidence solely because the formal artifact passed.

## 6. Evaluation-context identity

When evaluation evidence is load-bearing, its identity may bind:

- model identity and version;
- harness/CLI identity and version;
- prompt or instruction digest;
- evaluator version;
- oracle semantics;
- accepted equivalence relation;
- tool names and versions;
- environment identity;
- budget;
- retry policy;
- context policy;
- source artifact hash;
- session state.

The identity hash is canonical over applicable fields. Changing oracle semantics, harness identity, context policy, source artifact, or session state produces a different identity. Missing fields named as load-bearing produce unresolved evidence rather than fake reproducibility.

## 7. Provenance and attestation adapter boundary

`ProvenanceAdapter` is a neutral compatibility protocol. A backend normalizes its record into:

```text
backend
adapter_version
record_digest
subject_digest
attestation_digest (optional)
semantics = INTEGRITY_AND_LINEAGE_ONLY
```

Candidate backends include W3C PROV-compatible records, Flowcept lineage, and in-toto attestations. None is a mandatory dependency in this slice.

Gauntlet retains the epistemic decision. The adapter cannot set validity, fidelity, independence, admission, or release authority.

## 8. Session and memory-state axis

The envelope and evaluation identity distinguish:

```text
COLD_START
WARMED_STATE
EXTENDED_SESSION
RESUMED_STATE
STALE_STATE
SUPERSEDED_STATE
```

Rules:

- `STALE_STATE` cannot clear a current transition;
- `SUPERSEDED_STATE` is never current;
- `RESUMED_STATE` requires a SHA-256 lineage binding;
- cold and warm states create different evaluation identities;
- a task/source-state hash change invalidates the old envelope;
- a rerun-generation change invalidates prior evidence;
- session-depth effects are diagnostic measurements, not automatically model capability.

## 9. External failure taxonomy

Namespaced failure categories may be recorded as diagnostics, for example:

```text
AUTORESEARCHEVAL:TOOL_ERROR
```

The category changes evidence identity for auditability but does not alter the verdict. Unknown categories remain representable. External taxonomies are not release authority.

## 10. Automatic-controller integration

The existing ten canonical operations remain unchanged. In `AUTOMATIC_FULL`:

1. every applicable canonical operation still executes;
2. structural budgets remain advisory;
3. execution continues after an issue;
4. the receipt/event chain is checked;
5. the `audit` operation composes its existing receipt checks with the opt-in evidence-context gate;
6. one aggregate `ASSURANCE_ONLY` receipt is written.

Selective or early-stop behavior remains limited to explicitly named `*_EXPERIMENTAL` modes. A selective receipt cannot masquerade as production clearance.

The aggregate receipt records:

```text
evidence_context_schema
evidence_context_status
evidence_context_verdict
evidence_context_rows
```

A missing envelope does not affect a legacy obligation unless the task or obligation opted into the stronger profile. An invalid or tampered envelope is never ignored.

## 11. Required negative controls

The focused test suite covers:

1. self-report cannot promote lifecycle;
2. formal pass plus fidelity failure is rejected;
3. formal pass plus missing fidelity stays unresolved;
4. provenance-bound plus validity-unchecked is not valid;
5. changed oracle semantics changes identity;
6. changed harness/context policy changes identity;
7. stale evidence cannot clear;
8. superseded evidence is not current;
9. resumed state preserves lineage;
10. historical unqualified receipts remain readable;
11. historical receipts receive no inferred admission status;
12. source-state changes invalidate evidence;
13. reruns invalidate prior generations;
14. unregistered deterministic rules cannot promote;
15. tampering breaks the envelope hash;
16. external failure categories remain diagnostic;
17. Gauntlet remains `ASSURANCE_ONLY`;
18. production automatic mode retains all ten canonical operations;
19. selective reduction remains explicitly experimental.

## 12. Evidence boundary

This implementation establishes typed parsing, content binding, deterministic identity, opt-in release blocking, and regression behavior. It does **not** establish:

- truth of a claim;
- correctness of a formalization;
- independence merely from different labels;
- scientific validity from signed provenance;
- exhaustive real-world hazard coverage;
- behavioral superiority of Gauntlet.
