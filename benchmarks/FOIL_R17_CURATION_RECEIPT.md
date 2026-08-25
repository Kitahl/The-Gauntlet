# FOIL R1.7 natural-miss curation receipt

Status: **FROZEN BEFORE V2 SCANNER EXECUTION**

- Protocol/scanner commit: `aa377ad`.
- Source SHA-256:
  `4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b`.
- Selection seed: `2026082402`.
- R1.6 exclusions: 81 distinct questions derived from the digest-bound R1.6
  label and report artifacts.
- Frozen label-manifest SHA-256:
  `1a89975c1977c982e8d758c1e31e8699e11c1c039085e98d2e1628ddd2a0c5a6`.
- Candidate prefix reviewed: 30 of 30 allowed rows.

The main reviewer compared only question, official ground-truth derivation, and
historical response under the frozen first-causal-divergence taxonomy. It did
not invoke or inspect v2 discovery output. Ambiguous or compound errors were
left `UNMAPPED`. No row will be relabelled or replaced after scanner execution.

| Label | Count |
|---|---:|
| `RESULT` | 1 |
| `FINAL` | 0 |
| `OPERAND` | 4 |
| `DROPSTEP` | 8 |
| `SWAPOP` | 2 |
| `CONSISTENT_LOCAL` | 8 |
| `CONSISTENT_GLOBAL` | 1 |
| `UNMAPPED` | 6 |

The benchmark selection is one miss per available mapped class: six natural
misses, with no `FINAL` case. Twenty correct controls and four mutation bases
are selected by the already-committed runner and are disjoint from these rows
and from every R1.6 excluded question.
