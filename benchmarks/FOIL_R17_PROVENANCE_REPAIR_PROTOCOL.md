# FOIL R1.7 — Provenance Repair and Fresh No-Oracle Rerun

Status: preregistered; no R1.7 scanner outcomes may be observed before the
protocol commit and natural-label manifest are frozen.

## Scope boundary

R1.6 is development evidence. Its 60 reviewed questions, selected natural
misses, correct controls, and mutation bases are excluded by content digest.
R1.7 does not rescore those rows as held-out evidence. The route is the new,
default-off `gsm8k.annotated-arithmetic.v2`; v1 remains reproducible.

The v2 provenance grammar admits only closed source records: prompt roots,
arithmetic identity, bounded lexical factors/ratios, exact fractions and their
components, percentages, mechanically rederived percentage multipliers,
mechanically rederived one-step scale relations, and prior checked results.
It is still a narrow execution-class generator—not a prose formalizer.

## Frozen data and selection

- Source: OpenAI `grade-school-math` commit `3101c7d5072418e28b9008a6636bde82a006892c`.
- Source SHA-256: `4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b`.
- Selection seed: `2026082402`.
- R1.6 label/report file digests are bound in the executable protocol.
- Four fresh, distinct gold questions support all seven R1.6 operators (up to
  28 executed mutants).
- At most 30 fresh, distinct wrong-response candidates are reviewed in hash
  order. First causal divergence is labeled with the existing seven classes;
  ambiguity is `UNMAPPED`. One miss per class is selected where available.
- Twenty fresh, distinct correct controls are hash-selected across the four
  historical model variants.
- Mutation, natural-miss, and control question sets are mutually disjoint.
- Candidate labels are frozen before any v2 scanner execution. FOIL receives
  only question and model response; gold, correctness, and labels remain
  scorer-side until predictions are frozen.

## Outcomes and statistics

All rates use named Wilson two-sided 95% intervals. Exact-permutation Spearman
is primary and Pearson descriptive only when at least three supported common
classes exist and both vectors vary; otherwise the association is typed
`NOT_IDENTIFIABLE`.

The preregistered smoke decision is:

- `FAIL_NOISY` at 4 or more false fires among 20 controls;
- `FAIL_RECALL` when at least five natural misses exist and recall is at most 50%;
- `SMOKE_PROMISING` only with at most 1 false fire, at least five natural misses,
  and at most 1 missed natural error;
- otherwise `INCONCLUSIVE`.

Even `SMOKE_PROMISING` is historical-model smoke evidence only. It cannot
calibrate, admit, promote, mutate A0, or claim frontier-model recall.

## Authority and cost invariants

Provider, bot, runtime-model, token, profile-write, action, execution-authority,
answer-mutation, and promotion counts must all remain zero. The generated
origin remains visible as `GENERATED_UNADMITTED`; benchmark compilation is an
explicitly unadmitted local evaluation path.
