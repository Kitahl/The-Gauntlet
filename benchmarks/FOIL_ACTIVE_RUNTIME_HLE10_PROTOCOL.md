# FOIL active-runtime HLE-10 protocol

Status: preregistered diagnostic. This protocol cannot authorize production or
promotion.

## Question and gold boundary

- Dataset: `skylenage-ai/HLE-Verified` revision
  `0bc83643672d4f68a5f89998617a639d85e7318b`, five pinned Gold parquet shards.
- Preparation projects only `id`, `Verified_Classes`, `category`, and `question`.
  It never reads `answer` or embedded JSON.
- Every tracked and untracked repository artifact, including ZIP member names
  and bytes, is scanned for bounded 24-hex HLE IDs before selection.
- Eligible rows are Gold-subset, text-only by the frozen positive question-text
  filter, at most 12,000 characters, and absent from the exposure set.
- Exactly ten rows are selected by ascending SHA-256 of
  `20260828:FOIL_ACTIVE_RUNTIME_HLE10:<id>`. Applicability never changes this set.
- Gold is loaded only by the separate scorer after predictions are committed.

## Model and independence

- Executable: the installed native `codex` CLI, recorded with version and digest.
- Model/config: `gpt-5.6-terra`, reasoning effort `high`, for every model call.
  Prior committed Terra-High receipts measured A0 P50/P90 at 19,513/21,974
  tokens and route P50/P90 at 34,246/273,355 tokens. No aggregate ceiling applies.
- One question per ephemeral context. No item is retried, batched, replaced, or
  cancelled for coverage.
- Each item receives one closed-book, no-tool A0. Active FOIL starts from that
  exact persisted answer.

## Active runtime and authority

- Canonical entry: `tools/foil_runtime_active.py:run_foil` at core commit
  `a48b313f72b9c3e31c035cfa7dd380c9306101cd` via benchmark integration
  `2cd98dedf9378cd54fae115d1b7590b39d3fb744`.
- Four adapters are available only to FOIL: exact arithmetic, restricted Python,
  symbolic linear computation, and passage retrieval.
- The question-only opportunity replay is diagnostic. `COVERAGE_GAP` remains a
  fixed row and launches no route work.
- The runtime chooses the cheapest applicable positive-value route. Retrieval is
  at most two searches plus two HTTPS fetches, one constructor pass, no retry,
  and a 600-second provider-call timeout.
- Search snippets are discovery only. Evidence requires a fetched public HTTPS
  page and an exact quote slice with URL, offsets, content digest, and passage
  digest. Bind failures are retained.
- The constructor sees question plus admitted evidence, never A0 or gold.
- Comparator policy is symmetric and mechanical. Broader semantic entailment is
  uncalibrated and therefore unresolved; no semantic model judgment receives
  answer-changing authority.
- The selector changes A0 only when B is mechanically fully supported and A0 is
  mechanically critically contradicted under the same evidence.

## Bounds and accounting

- No aggregate token ceiling, budget cancellation, or artificial answer-length
  cap exists.
- Calls are finite: one A0, at most one retrieval pass and one constructor pass
  per item; zero retries; bounded tools, fetch bytes, evidence characters, and
  wall time.
- Terra metadata records a 272,000-token context window with 95% effective use;
  the receipt envelope records 258,400 as the provider-enforced per-field guard.
  This is not passed as an artificial output limit.
- Raw stdout, stderr, final JSON, prompts, fetches, and evidence are persisted
  before any progress line.
- Every row records full provider input/cached/output tokens, canonical
  `ledger_after.spent_usage`, and `cost_accounting_complete`. Missing or malformed
  usage yields `ACCOUNTING_INVALID`; it is never synthesized as zero.

## Scoring and claims

- Predictions and receipts are hashed and committed before the scorer loads gold.
- Strict score is exact string equality. Normalized score permits bounded case and
  whitespace/punctuation normalization, tuple spacing, and one final answer in a
  short explanation; multiple or contradictory answer candidates are rejected.
- Report paired A0/final raw and normalized counts, exact rows, rescues, damages,
  abstentions, invalids, coverage, stage outcomes, per-tool yield, token totals,
  and mean/median/P90 multipliers.
- Safety gate: zero damages. At least one genuine rescue is required to call the
  mechanism promising. The 1.35x mean multiplier is a target, not a hard limit.
- Classification is `DIAGNOSTIC_UNADMITTED_N10`; ten rows cannot calibrate,
  promote, or establish general HLE efficacy.
