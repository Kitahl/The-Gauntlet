# FOIL R1.5 Natural-Miss Pilot

Status: **completed; primary association not identifiable**

## Question

Does injected-fault kill behavior predict detection of naturally wrong model
answers?

This is a nine-miss smoke test, not calibration, certification, a promotion
gate, or an estimate of production recall. The old v4.1 aggregate claims do
not come with the raw per-mutant records, frozen sensor implementation, or an
independent operator-class label for each natural miss. Therefore the legacy
correlation is inadmissible unless those inputs are later supplied and hashed.

## Frozen candidate and data

- Runtime base: `4ca0e72c5cdc5fd852fe680efeeeef561aea3e84`.
- Historical ARC/HLE prediction file SHA-256:
  `745f05b5d7b077c5245dea1d3fa3965a1db7eeabe3145a935dc9c190ad26d3a8`.
- Historical GPQA prediction file SHA-256:
  `f7fd58b0ab2cf5393940d8360e37418a47ce135093fc7d10396dbc7319d5cc3d`.
- ARC source: the already-pinned ARC-AGI archive commit
  `399030444e0ab0cc8b4e199870fb20b863846f34`.
- GPQA source: the existing official dataset URL used by the historical
  harness. Its fetched bytes must be SHA-256 recorded because that URL is not
  commit-pinned.
- Historical positive control: ARC `9/12`, GPQA `18/24`, pooled `27/36`,
  exactly nine misses. Any mismatch aborts before an R1.5 report is admitted.

Only ARC and GPQA are in the replay. HLE is excluded because the documented
27/36 and nine-miss claim excludes HLE from primary evidence.

## Frozen measurements

The secondary RC4 replay uses the real strict compiler, residual scanner, and
closed in-process verifiers:

- GPQA: host-supplied `EXACT_MATCH` obligations; one valid deterministic
  `GPQA_CHOICE_SUBSTITUTION` mutant per item.
- ARC: host-supplied `JSON` obligations; one valid deterministic
  `ARC_CELL_SUBSTITUTION` mutant per item.
- Natural-miss detection: a wrong historical A0 produces `DEFECT`.
- Correct-output false fire: a correct historical A0 produces `DEFECT`.
- Mutation kill: a known-wrong deterministic mutant produces `DEFECT`.
- A0 identity must be preserved on every scan. No candidate is generated and
  no answer is changed.

These obligations contain benchmark gold. The replay is therefore
`ORACLE_BOUND`: it tests the executable declared-universe route, not FOIL's
ability to discover a defect or extract an obligation from prose.

## Correlation admissibility

An operator-level association is reported only if all conditions hold:

1. at least three operator classes have both valid mutants and at least one
   independently labelled natural miss;
2. synthetic and natural detection rates both have non-zero variance;
3. the frozen scanner and raw mutation records are available;
4. natural operator labels were assigned independently of scanner outcomes.

Otherwise the typed result is `NOT_IDENTIFIABLE`, with all failed conditions
listed. No zero, null, or missing value may be presented as a correlation.
Even an estimable result at nine misses would remain descriptive only.

## Fixed costs and non-claims

- Model/provider calls: `0`.
- External bots: `0`.
- Token spend: `0`.
- Candidate generations and answer mutations: `0`.
- Source retrieval: exactly two fixed public dataset downloads, performed only
  after this protocol and harness are committed. Source bytes are not written
  into the result; only their hashes and selected item identities are retained.

This pilot cannot validate the old S1-S4 bank, the v4.1 4,897-mutant aggregate,
mutation realism, extraction recall, semantic discovery, repair success,
repair damage, or product efficacy.

## Result

The protocol and harness were committed at
`951e04b1ddba4eb9e2d3cd61a6c5dd6e519bf129` before either source archive was
fetched or scored. Protocol SHA-256:
`9bfcb65b92ff42d515643ebafa16a2a26c5f07f7e278f53f398e4d908b026058`.

- Historical positive control: ARC **9/12**, GPQA **18/24**, pooled **27/36**;
  exactly **9** natural misses.
- Oracle-bound natural replay: **9/9** misses detected.
- Correct-output negative control: **0/27** false fires.
- Deterministic mutants: **36/36** killed across two operator classes.
- Primary R1.5 status: **`NOT_IDENTIFIABLE`**.
- Reasons: legacy raw scanner/mutation rows absent; independently adjudicated
  natural operator labels absent; only two common operator classes; mutation
  and natural detection rates both have zero variance (`1.00`, `1.00`).
- Provider calls / external bots / tokens: **0 / 0 / 0**.
- Candidate generations / answer mutations: **0 / 0**.
- Fixed public source downloads: **2**.
- Report SHA-256:
  `f392ea7b69cd2b814d3e4c54c3b1d9619494d51b64ab16e826eca1b8f4f3f260`.

The 9/9 result shows that the current exact executable routes work when the
host supplies benchmark gold. It does not show that FOIL finds natural defects
from prose, and the constant two-point data cannot test whether mutation kill
rate predicts natural detection. No gate or promotion state changed.

## Command

After committing this protocol and the harness, run exactly once with the
resulting protocol commit:

```powershell
python benchmarks/harness/foil_r15_natural_miss_pilot.py `
  --allow-source-network `
  --protocol-commit <40-hex-protocol-commit> `
  --output benchmark_runs/2026-08-24/r15_natural_miss_pilot/report.json
```
