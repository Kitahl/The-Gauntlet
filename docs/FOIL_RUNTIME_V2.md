# FOIL v2 active runtime

Status: **IMPLEMENTED / SOFTWARE-VERIFIED / EFFICACY-UNMEASURED**

This is the reusable FOIL runtime upgrade. It contains no HLE items, gold,
benchmark selection, or provider-specific model invocation.

## Public entry point

Import `run_foil` from `tools/foil_runtime_active.py`, or execute the mechanical
CLI in `tools/foil_runtime_cli.py`.

The runtime flow is:

1. Freeze a closed question-only opportunity (`foil_route_opportunity_v2.py`).
2. Probe exactly four families, cheapest first: exact arithmetic, restricted
   Python, bounded symbolic computation, and passage retrieval.
3. Apply a prelaunch expected-value decision and reserve a finite per-call
   resource envelope (`foil_runtime_token_ledger.py`). There is no aggregate
   token ceiling or benchmark cancellation.
4. Execute one read-only adapter under a closed v2 contract.
5. Persist the raw content-addressed receipt before reporting success
   (`foil_evidence_archive.py`). Search snippets are not evidence; retrieval must
   provide fetched content and exact passage offsets.
6. Build an evidence packet. A candidate constructor, when enabled, receives
   the question and admitted evidence but never A0 or tools.
7. Compare A0 and B independently against the same packet. Mechanical evidence
   may adjudicate; uncalibrated semantic comparison is supporting only.
8. Preserve A0 unless B is fully eligible and A0 has an admissible critical
   contradiction. Active answer change is an explicit caller policy and remains
   unadmitted for production.
9. Return exactly one typed outcome: `DIRECT`, `COVERAGE_GAP`,
   `VERIFY_RESOLVED`, `FULL_RESOLVED`, `PRESERVED_A0`, or a typed boundary error.

## Authority and profile boundary

- Tool contracts are read-only and never grant production authority.
- Model-generated Python/symbolic specifications require an independent
  formalization-admission digest. Host parsing of a literal task expression is
  not a generated specification.
- A semantic comparator cannot participate in active answer change unless its
  route is explicitly admitted.
- The runtime reads and writes no PERSON/profile state. Routing and acceptance
  evidence cannot train the profile from the same event.
- The original answer digest and selected origin are retained on every path.

## Verification

Focused tests cover closed schemas, unknown-field rejection, all four adapter
families, exact active repairs, correct-answer preservation, raw passage
archiving, constructor blindness, selector authority, per-call accounting,
aggregate-unbounded operation, timeout/malformed/overrun/persistence faults, and
the real CLI path.

The complete repository suite passes after removing generated Graphify files
that contained private local-path data. Green tests prove software contract
behavior; they do not prove generalized score improvement.

## Non-claims

- No production route is promoted.
- No semantic entailment model is calibrated by this build.
- No benchmark efficacy, score gain, or token multiplier is claimed here.
- Passage retrieval requires a host-supplied provider adapter.
