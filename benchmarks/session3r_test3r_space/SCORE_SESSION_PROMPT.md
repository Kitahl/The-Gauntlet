# SESSION C — TEST #3R — SCORE ONLY

Score the two immutable receipts from independent BASE and SPACE sessions. Perform no new benchmark inference.

## Required user inputs

The user must provide:

- `SESSION3R_BASE_RECEIPT.jsonl`
- `SESSION3R_BASE_RECEIPT.sha256.txt`
- `SESSION3R_SPACE_RECEIPT.jsonl`
- `SESSION3R_SPACE_RECEIPT.sha256.txt`

If either receipt or committed hash is missing, stop with:

`SCORE PHASE BLOCKED — IMMUTABLE RECEIPTS REQUIRED`

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit: `__PACKAGE_COMMIT__`

Experiment: `SESSION3R_TEST3R_SPACE`

Frozen Space blob used by treatment:

`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Expected paired sample:

- 50 primary verified-release retrieval tasks
- 30 secondary multi-source comparison tasks
- 20 exploratory release-history navigation tasks
- 100 identical task IDs per arm

## No new inference

Do not answer or research any benchmark question in this session. Do not improve, repair, normalize, or rewrite either arm's predictions.

## Verify receipts before gold

Before accessing sealed gold:

1. Verify each supplied receipt SHA-256 against its hash file.
2. Verify each receipt contains exactly 100 unique IDs.
3. Verify BASE condition labels are BASE and SPACE labels are SPACE.
4. Verify BASE and SPACE ID sets are identical.
5. Fetch only the public package certification files at exact package commit and verify `SOURCE_VALIDATED = true`.

If any receipt integrity check fails, stop with:

`INVALID / INCONCLUSIVE — RECEIPT INTEGRITY FAILURE`

## Gold access is now allowed

Only after both immutable receipts pass verification may you access:

- `benchmarks/session3r_test3r_space/gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/gold.jsonl.gz.b64`
- `benchmarks/session3r_test3r_space/score.py`

at exact commit `__PACKAGE_COMMIT__`.

The gold is gzip-compressed JSONL encoded as base64. Decode only in this scoring session.

Use the frozen `score.py` logic. Do not substitute an LLM judge for mechanical scoring.

## Primary endpoint

For the 50 `primary_verified_release_retrieval` tasks, report three paired metrics:

1. exact answer accuracy;
2. first-party source coverage;
3. **verified success = exact answer correct + required first-party evidence recovered + no resource-budget violation**.

The primary efficacy endpoint is **verified success**.

Report:

- BASE verified successes /50
- SPACE verified successes /50
- percentage-point delta
- BASE fail / SPACE pass discordances
- BASE pass / SPACE fail discordances
- both pass
- both fail
- exact two-sided McNemar p-value

Also report answer accuracy and source coverage separately.

## Secondary endpoint

For the 30 `secondary_multi_source_comparison` tasks, report the same metrics and exact paired McNemar result. These tasks require first-party coverage for both repositories.

## Exploratory endpoint

For the 20 `exploratory_release_history_navigation` tasks, report the same metrics separately. Label this exploratory.

## Resource accounting

Report for each arm and each section:

- total search queries
- total source follow-up operations
- mean searches/task
- mean follow-ups/task
- budget violations
- visible output characters/tokens if present in receipts

Do not infer hidden reasoning cost.

## Discordant-pair audit

For every primary verified-success discordance, report:

- task ID
- which arm passed
- whether disagreement was answer correctness, first-party evidence recovery, budget compliance, or multiple factors

Do not infer private chain-of-thought.

## Validity audit

Explicitly report:

- fresh independent BASE session: YES/NO
- fresh independent SPACE session: YES/NO
- same 100 task IDs: YES/NO
- byte-identical frozen arm projections according to certification: YES/NO
- package commit pinned: YES/NO
- source certification passed before inference: YES/NO
- gold stored without plaintext semantic exposure: YES/NO
- gold concealed from BASE: YES/NO
- gold concealed from SPACE: YES/NO
- Space concealed from BASE: YES/NO
- BASE material concealed from SPACE: YES/NO
- benchmark-artifact firewall respected: YES/NO
- Mirror/FOIL used: MUST BE NO
- other Gauntlet skills used: MUST BE NO
- connected GitHub API used to solve target release questions: MUST BE NO
- matched search/read budgets: YES/NO
- prediction receipts immutable: YES/NO
- semantic gold exposure during either arm: MUST BE NO
- budget violations: list
- other protocol deviations: list

Any semantic answer-key exposure before both commitments forces:

`INVALID / INCONCLUSIVE`

## Verdict

Use exactly one:

`POSITIVE DIRECTION`

`MIXED`

`TIE / NO OBSERVED DIFFERENCE`

`NEGATIVE DIRECTION`

`INVALID / INCONCLUSIVE`

Prioritize the paired 50-item primary verified-success endpoint. Secondary/exploratory results cannot override a clearly negative primary outcome.

## Final report

### SESSION / TEST
`Session #3R — Test #3R — Space`

### MODEL
Model identity in each arm.

### PACKAGE
Exact frozen package commit.

### FROZEN SPACE
`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

### PRIMARY — VERIFIED RELEASE RETRIEVAL
BASE /50, SPACE /50, delta, McNemar, answer accuracy, source coverage.

### SECONDARY — MULTI-SOURCE COMPARISON
BASE /30, SPACE /30, delta, McNemar.

### EXPLORATORY — RELEASE HISTORY
BASE /20, SPACE /20, delta.

### RESOURCE USE
Matched-budget comparison.

### DISCORDANT PAIRS
Primary disagreements and observable failure class.

### VALIDITY AUDIT
Complete checklist.

### VERDICT
One allowed verdict.

### INTERPRETATION
State only what this paired, custom first-party-source retrieval experiment supports about the frozen Space procedure on GPT-5.6 Sol.
