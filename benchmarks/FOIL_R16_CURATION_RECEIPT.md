# FOIL R1.6 natural-miss curation receipt

Status: **FROZEN BEFORE SCANNER EXECUTION**

- Protocol commit: `0ad3e3ec47f96d44e7ea8bb8acec90049192efd1`.
- Source SHA-256:
  `4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b`.
- Candidate ordering seed: `20260824`.
- Candidate prefix reviewed: 60 of 60 allowed rows.
- Final reviewed manifest SHA-256:
  `60ed6f3ad4c3eefcd4b983b7d41d63c96a188cdad8d7a9a133ab520acae3dc6e`.

Terra independently compared question, official ground-truth derivation, and
historical response under the frozen first-causal-divergence taxonomy. It did
not inspect or execute the discovery scanner, runner scoring path, or reports.
All 60 rows were reviewed because the per-class target could not be closed.

The main review then checked every row that would enter the small benchmark and
all rows initially labelled `RESULT`, `FINAL`, or `CONSISTENT_LOCAL`. Three labels
were corrected before any scanner execution:

- one formula-plus-arithmetic compound error: `RESULT` to `UNMAPPED`;
- one multi-error food/tax rewrite: `CONSISTENT_LOCAL` to `UNMAPPED`;
- one omitted whole-pack rounding step: `FINAL` to `DROPSTEP`.

Final 60-row counts are:

| Label | Count |
|---|---:|
| `RESULT` | 1 |
| `FINAL` | 0 |
| `OPERAND` | 8 |
| `DROPSTEP` | 13 |
| `SWAPOP` | 8 |
| `CONSISTENT_LOCAL` | 9 |
| `CONSISTENT_GLOBAL` | 6 |
| `UNMAPPED` | 15 |

The frozen benchmark selection therefore contains 11 natural misses: two per
available mapped class except `RESULT` (one) and `FINAL` (zero). No case was
replaced or relabelled using scanner behavior.
