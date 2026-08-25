# FOIL R1.5 Natural-Miss Validation Report

Date: 2026-08-24

## Verdict

The nine-item natural-miss replay is complete. It reproduced the historical
denominator exactly and verified RC4's oracle-bound exact routes, but it did not
make mutation kill rate a validated proxy for natural defect detection.

Primary outcome: **`NOT_IDENTIFIABLE`**.

## Reproduced controls

| Check | Result |
|---|---:|
| ARC historical score | 9/12 |
| GPQA historical score | 18/24 |
| Pooled historical score | 27/36 |
| Natural misses | 9 |
| RC4 detection of natural misses | 9/9 |
| Correct-output false fires | 0/27 |
| Deterministic mutants killed | 36/36 |
| Provider calls / external bots / tokens | 0 / 0 / 0 |
| Candidate generations / answer mutations | 0 / 0 |

The persisted report digest was independently recomputed and matched
`f392ea7b69cd2b814d3e4c54c3b1d9619494d51b64ab16e826eca1b8f4f3f260`.
The report stores item identities and typed outcomes, not raw answers or gold.

## Why the association is not identifiable

1. The raw v4.1 scanner/mutator rows are absent; only prose aggregates survive.
2. The nine natural misses have no independently adjudicated v4.1 operator
   labels.
3. The executable RC4 replay has only two common operator classes.
4. Both synthetic and natural detection rates are `(1.00, 1.00)`, so both axes
   have zero variance and Pearson/Spearman correlation is undefined.

Reporting `0`, `1`, or a missing-value substitution as a correlation would be
fabricated evidence. The harness therefore emits a typed non-estimable result.

## Scope boundary

The RC4 replay embeds benchmark gold in host-supplied exact obligations. Its
9/9 detection result proves that the strict compiler, residual scanner, and
closed exact verifiers catch these wrong final outputs inside that declared
universe while preserving A0. It does not measure whether FOIL discovers the
relevant obligation from prose, finds natural semantic defects without an
oracle, generates a repair, or improves final answers.

No release, gate, authority, personalization, or promotion state changed.
