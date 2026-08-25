# FOIL adaptive-compute two-benchmark small pilot

Status: frozen smoke protocol; not calibration or production activation

## Question

On a tiny matched sample, what happens when a benchmark host actually executes
FOIL's `DIRECT`/`FULL` recommendation instead of recording it in shadow only?
Measure both answer changes and the *incremental* tokens of any second FULL call.

## Matrix

- Models: `gpt-5.6-terra` at low and high reasoning effort, and
  `gpt-5.6-sol` at low reasoning effort.
- Benchmarks: two hash-selected GSM8K ProcessBench rows (one labelled-clean and
  one labelled-error) and two hash-selected SimpleQA questions.
- Every unit first receives one closed-book, tool-free BASE call producing frozen
  A0. Runs are ephemeral and reject any tool event.
- SimpleQA has no host-declared decidable obligation and therefore routes DIRECT.
- For ProcessBench only, the benchmark host declares every certified fully
  numeric equality in the supplied trace as a closed exact-match obligation.
  Gold labels are unavailable to the router. A mechanically verified failure is
  passed to the checked-in adaptive controller. Positive frozen pilot EV permits
  FULL; otherwise the result is DIRECT.
- DIRECT preserves A0 and makes no second model call. FULL makes one separate,
  tool-free review call using the frozen public FOIL skill contract and A0.

This host declaration is a benchmark-only transformation boundary. It does not
admit the repository's generated-obligation routes, grant production authority,
or change the controller's default-off/shadow-only contract.

## Frozen selection and scoring

- Seed: `20260825`.
- ProcessBench source is the locally cached official parquet set already bound by
  the repository's P0.5 SHA-256 manifest. The clean row is hash-selected without
  regard to scanner outcome. The error row is an explicitly **route-positive
  integration sentinel**, hash-selected among labelled-error rows containing a
  certified false numeric equality. This guarantees that the tiny pilot executes
  FULL at least once, but makes route frequency and recall non-estimable.
- SimpleQA is fetched from OpenAI's official public CSV. Selection uses only the
  question text and seeded hash; reference answers remain scorer-side until all
  predictions are frozen and committed.
- ProcessBench requires `OK` for an all-correct trace or the zero-based index of
  the first erroneous step. SimpleQA uses conservative normalized exact match;
  this is reported as strict smoke accuracy, not official model-graded SimpleQA.

Primary descriptive outputs are BASE and adaptive accuracy, wrong-to-correct
rescue, correct-to-wrong damage, abstention, route counts, and incremental token
overhead. With four items and one replicate, no confidence, superiority,
calibration, promotion, or population claim is permitted.

## Safety and cost invariants

- No network, provider, tool, profile, write, or answer-mutation capability is
  exposed inside model calls. Dataset download during preparation/scoring is not
  model tool use.
- Gold, correctness, and source labels never appear in prompts.
- No retries. Hard cap: 21 calls (3 controls, 12 BASE, at most 6 FULL).
- Every public receipt binds prompt, model, effort, CLI version, frozen commit,
  raw-stream hashes, route, answer, and token usage.
- DIRECT must have no FULL receipt and must preserve A0 byte-for-byte.
- Predictions and receipts must be committed before gold can be opened.

## Interpretation boundary

The sample is intentionally tiny. It can expose damage, a broken route, or a
large cost mismatch. It cannot establish a 10% production average. In particular,
FULL is a second call here, so the report measures its actual incremental cost
instead of assuming the earlier prompt-only `+39.9%` result is an incremental
FULL-call price.
